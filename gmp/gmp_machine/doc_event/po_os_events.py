# ============================================================
# File: your_app/your_app/custom/purchase_order.py
#
# Wire this up in hooks.py (see bottom of this file for the
# doc_events entries you need to add). Linking now happens on
# "on_update" (every save, starting from insert) instead of
# "on_submit", so it syncs on draft, edit, and submit alike.
# ============================================================
import frappe
from frappe import _


def validate_order_sheet_linkage(doc, method):
    """
    Called on Purchase Order 'validate' (runs on every save AND submit).

    Checks:
    1. Order Sheet Item already linked to some other PO -> block save
    2. Linked Order Sheet is in Draft (0) or Cancelled (2) -> block save
    3. Multiple different Order Sheets referenced in the same PO -> block save
    4. PO Item's item_code != Order Sheet Item's item_code -> block save
    5. If a row was removed from PO Items, clear that Order Sheet Item's
       purchase_order / purchase_order_item fields (if it was linked to
       this same row).
    """
    order_sheets_in_po = set()

    # Previous version of the doc, before this save. None for a new doc.
    old_doc = doc.get_doc_before_save()

    current_row_names = set()

    for row in doc.items:
        current_row_names.add(row.name)

        if not (row.custom_order_sheet and row.custom_order_sheet_item):
            continue

        order_sheets_in_po.add(row.custom_order_sheet)

        # ---- Check 3: same PO should not reference multiple Order Sheets
        if len(order_sheets_in_po) > 1:
            frappe.throw(
                _("Row #{0}: All items must belong to the same Order Sheet. "
                  "This Purchase Order references multiple Order Sheets.").format(row.idx)
            )

        os_item = frappe.db.get_value(
            "Order Sheet Item",
            row.custom_order_sheet_item,
            ["purchase_order", "purchase_order_item", "item_code"],
            as_dict=True,
        )

        if not os_item:
            frappe.throw(
                _("Row #{0}: Linked Order Sheet Item {1} not found.").format(
                    row.idx, row.custom_order_sheet_item
                )
            )

        # ---- Check 1: Order Sheet Item already linked to another PO/row
        if os_item.purchase_order or os_item.purchase_order_item:
            already_this_row = (
                os_item.purchase_order == doc.name
                and os_item.purchase_order_item == row.name
            )
            if not already_this_row:
                frappe.throw(
                    _("Row #{0}: Order Sheet Item {1} is already linked to "
                      "Purchase Order {2}, Row {3}.").format(
                        row.idx,
                        row.custom_order_sheet_item,
                        os_item.purchase_order,
                        os_item.purchase_order_item,
                    )
                )

        # ---- Check 2: Order Sheet docstatus check (Draft / Cancelled)
        os_docstatus = frappe.db.get_value(
            "Order Sheet", row.custom_order_sheet, "docstatus"
        )
        if os_docstatus == 0:
            frappe.throw(
                _("Row #{0}: Order Sheet {1} is still in Draft. "
                  "Please submit the Order Sheet before creating a Purchase Order.").format(
                    row.idx, row.custom_order_sheet
                )
            )
        if os_docstatus == 2:
            frappe.throw(
                _("Row #{0}: Order Sheet {1} is Cancelled. "
                  "Cannot create a Purchase Order against a cancelled Order Sheet.").format(
                    row.idx, row.custom_order_sheet
                )
            )

        # ---- Check 4: item_code mismatch between PO row and Order Sheet Item
        if os_item.item_code != row.item_code:
            frappe.throw(
                _("Row #{0}: Item Code mismatch. Purchase Order has {1} but "
                  "linked Order Sheet Item has {2}.").format(
                    row.idx, row.item_code, os_item.item_code
                )
            )

    # ---- Check 5: row removed from PO items -> clear linked Order Sheet Item
    if old_doc:
        for old_row in old_doc.items:
            if old_row.name in current_row_names:
                continue
            if not old_row.custom_order_sheet_item:
                continue

            linked_purchase_order_item = frappe.db.get_value(
                "Order Sheet Item",
                old_row.custom_order_sheet_item,
                "purchase_order_item",
            )

            # Only clear if it was actually pointing to this removed row
            if linked_purchase_order_item == old_row.name:
                frappe.db.set_value(
                    "Order Sheet Item",
                    old_row.custom_order_sheet_item,
                    {
                        "purchase_order": None,
                        "purchase_order_item": None,
                    },
                    update_modified=False,
                )


def clear_order_sheet_item_link(doc, method):
    """
    Called on Purchase Order 'on_cancel' and 'on_trash' (delete).
    Clears purchase_order / purchase_order_item on every linked
    Order Sheet Item, so it becomes available again for a fresh PO.
    """
    updated_sheets = set()

    for row in doc.items:
        if not row.custom_order_sheet_item:
            continue

        linked_purchase_order_item = frappe.db.get_value(
            "Order Sheet Item",
            row.custom_order_sheet_item,
            "purchase_order_item",
        )

        # Only clear if it is actually pointing to this PO's row
        if linked_purchase_order_item == row.name:
            frappe.db.set_value(
                "Order Sheet Item",
                row.custom_order_sheet_item,
                {
                    "purchase_order": None,
                    "purchase_order_item": None,
                },
                update_modified=False,
            )
            if row.custom_order_sheet:
                updated_sheets.add(row.custom_order_sheet)

    if updated_sheets:
        notify_order_sheets(updated_sheets)


def update_order_sheet_item(doc, method):
    """
    Called on Purchase Order 'on_update' - runs on EVERY save,
    starting from the very first insert (draft) all the way through
    submit and any later saves. So the link is written on insert,
    and kept in sync on every subsequent update as well.

    For every PO Item linked to an Order Sheet Item, write the
    resulting Purchase Order / Purchase Order Item back onto the
    Order Sheet Item row.
    """
    updated_sheets = set()
    for row in doc.items:
        if row.custom_order_sheet and row.custom_order_sheet_item:
            frappe.db.set_value(
                "Order Sheet Item",
                row.custom_order_sheet_item,
                {
                    "purchase_order": doc.name,
                    "purchase_order_item": row.name,
                },
                update_modified=False,
            )
            updated_sheets.add(row.custom_order_sheet)

    if updated_sheets:
        notify_order_sheets(updated_sheets)


def notify_order_sheets(sheet_names):
    """Refresh cached copies and show a confirmation message."""
    for sheet_name in sheet_names:
        frappe.get_doc("Order Sheet", sheet_name).notify_update()

    links = ", ".join(
        frappe.utils.get_link_to_form("Order Sheet", name) for name in sheet_names
    )
    frappe.msgprint(
        _("Linked Order Sheet(s) updated: {0}").format(links),
        alert=True,
    )


# ============================================================
# Add this to your_app/hooks.py:
# ============================================================
#
# doc_events = {
#     "Purchase Order": {
#         "validate": "gmp.gmp_machine.doc_event.po_os_events.validate_order_sheet_linkage",
#         "on_update": "gmp.gmp_machine.doc_event.po_os_events.update_order_sheet_item",
#         "on_cancel": "gmp.gmp_machine.doc_event.po_os_events.clear_order_sheet_item_link",
#         "on_trash": "gmp.gmp_machine.doc_event.po_os_events.clear_order_sheet_item_link"
#     }
# }
#
# ============================================================

# ============================================================
# ######.  gmp.gmp_machine.doc_event.po_os_events.validate_order_sheet_linkage
# ######.  gmp.gmp_machine.doc_event.po_os_events.update_order_sheet_item


