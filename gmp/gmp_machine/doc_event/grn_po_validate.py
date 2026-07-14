import frappe
from frappe import _
from frappe.utils import flt, cint




@frappe.whitelist()
def validate_grn_quantities(doc, method=None):
    """
    Validate that:
    1. If Set Warehouse is selected, update Warehouse in all item rows.
    2. Total quantity received against each Purchase Order Item does not exceed the ordered quantity.
    3. Item Code in GRN matches the corresponding Purchase Order Item.
       - Normal PO  : GRN Item == PO Item.item_code
       - Subcontracted PO : GRN Item == PO Item.fg_item
    """

    if not doc.items:
        return

    # Set warehouse in all rows if Set Warehouse is selected
    if doc.set_warehouse:
        for row in doc.items:
            row.warehouse = doc.set_warehouse

    po_item_totals = build_po_item_totals(doc.items)

    for po_item_name, data in po_item_totals.items():
        validate_single_po_item(
            doc_name=doc.name,
            po_item_name=po_item_name,
            purchase_order=data["purchase_order"],
            current_qty=data["qty"],
            item_code=data["item_code"],
        )


def build_po_item_totals(items):
    po_item_totals = {}

    for row in items:
        po_item_name = row.purchase_order_item
        purchase_order = row.purchase_order
        item_code = row.item_code
        qty = flt(row.qty)

        if not po_item_name or not purchase_order:
            frappe.throw(
                _("Row for Item {0} is missing Purchase Order or Purchase Order Item.").format(
                    item_code
                )
            )

        if po_item_name not in po_item_totals:
            po_item_totals[po_item_name] = {
                "purchase_order": purchase_order,
                "item_code": item_code,
                "qty": 0.0,
            }

        po_item_totals[po_item_name]["qty"] += qty

    return po_item_totals


def validate_single_po_item(
    doc_name,
    po_item_name,
    purchase_order,
    current_qty,
    item_code,
):
    is_subcontracted = cint(
        frappe.db.get_value("Purchase Order", purchase_order, "is_subcontracted")
    )

    po_item = get_po_item_details(po_item_name)

    # Validate that the selected GRN Item matches the Purchase Order Item
    if is_subcontracted:
        expected_item = po_item.get("fg_item")
    else:
        expected_item = po_item.get("item_code")

    if expected_item != item_code:
        frappe.throw(
            _(
                "Item mismatch for Purchase Order Item <b>{0}</b>.<br><br>"
                "Expected Item: <b>{1}</b><br>"
                "Selected Item: <b>{2}</b>"
            ).format(
                po_item_name,
                expected_item,
                item_code,
            )
        )

    if is_subcontracted:
        ordered_qty = flt(po_item.get("fg_item_qty"))
        item_label = po_item.get("fg_item") or item_code
    else:
        ordered_qty = flt(po_item.get("qty"))
        item_label = po_item.get("item_code") or item_code

    existing_qty = get_existing_received_qty(po_item_name, doc_name)
    total_qty = existing_qty + current_qty

    if total_qty > ordered_qty:
        remaining_qty = max(ordered_qty - existing_qty, 0)

        frappe.throw(
            _(
                "Item <b>{0}</b>: Cannot receive <b>{1}</b>. "
                "Only <b>{2}</b> quantity is remaining against Purchase Order <b>{3}</b>.<br><br>"
                "Ordered Qty: <b>{4}</b><br>"
                "Already Received: <b>{5}</b>"
            ).format(
                item_label,
                current_qty,
                remaining_qty,
                purchase_order,
                ordered_qty,
                existing_qty,
            )
        )


def get_po_item_details(po_item_name):
    po_item = frappe.db.get_value(
        "Purchase Order Item",
        po_item_name,
        ["qty", "fg_item_qty", "fg_item", "item_code"],
        as_dict=True,
    )

    if not po_item:
        frappe.throw(_("Purchase Order Item {0} not found.").format(po_item_name))

    return po_item


def get_existing_received_qty(po_item_name, current_grn_name=None):
    rows = frappe.get_all(
        "Good Receipt Note Item",
        filters={
            "purchase_order_item": po_item_name,
            "docstatus": ["in", [0, 1]],
        },
        fields=["qty", "parent"],
    )

    total = 0.0

    for row in rows:
        if current_grn_name and row.parent == current_grn_name:
            continue

        total += flt(row.qty)

    return total