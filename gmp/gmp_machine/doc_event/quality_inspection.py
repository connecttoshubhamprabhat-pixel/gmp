import frappe


def update_purchase_order_item(doc, method=None):
    """Link subcontracted PO inspections by child row, not service item_code."""
    if doc.reference_type != "Purchase Order" or not doc.child_row_reference:
        return

    purchase_order_item = frappe.db.get_value(
        "Purchase Order Item",
        doc.child_row_reference,
        ["parent", "fg_item"],
        as_dict=True,
    )
    if not purchase_order_item or purchase_order_item.parent != doc.reference_name:
        return

    if purchase_order_item.fg_item and purchase_order_item.fg_item != doc.item_code:
        return

    quality_inspection = doc.name if doc.docstatus < 2 and method != "on_trash" else None
    frappe.db.set_value(
        "Purchase Order Item",
        doc.child_row_reference,
        "quality_inspection",
        quality_inspection,
        update_modified=False,
    )
