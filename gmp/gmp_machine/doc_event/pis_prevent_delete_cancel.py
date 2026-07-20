# Frappe Server Script
# DocType: Payment Intimation Slip
# Events: Before Cancel  AND  Before Delete  (create this as TWO Server Script
# records, one per event — a Server Script can only be bound to one event)
#
# Purpose:
# Prevent cancelling/deleting a Payment Intimation Slip (PIS) if its linked
# Purchase Order(s) (doc.purchase_order / doc.purchase_order_duplicate) or
# those PO's Purchase Invoice(s) are referenced in:
#   1. Payment Entry -> references child table (reference_doctype/reference_name)
#   2. Unreconcile Payment -> "Unreconcile Payment Entries" child table
#      (allocations.reference_doctype / allocations.reference_name)
# regardless of whether the linking document is Draft, Submitted or Cancelled.
#
# Register in hooks.py like this:
#
# doc_events = {
#     "Payment Intimation Slip": {
#         "before_cancel": "custom_app.custom_app.pis_events.prevent_pis_cancel_or_delete",
#         "on_trash": "custom_app.custom_app.pis_events.prevent_pis_cancel_or_delete",
#     }
# }
#

import frappe


def get_linked_purchase_orders(doc):
    """Collect PO names referenced on the PIS itself."""
    pos = []
    if doc.get("purchase_order"):
        pos.append(doc.purchase_order)
    if doc.get("purchase_order_duplicate"):
        pos.append(doc.purchase_order_duplicate)
    return list(set(pos))


def get_linked_purchase_invoices(purchase_orders):
    """Find Purchase Invoices linked to the given Purchase Orders via PI Item table."""
    if not purchase_orders:
        return []

    pi_names = frappe.get_all(
        "Purchase Invoice Item",
        filters={"purchase_order": ["in", purchase_orders]},
        pluck="parent",
        distinct=True
    )
    return list(set(pi_names))


def build_reference_list(doc):
    """Build list of (doctype, name) tuples to check against Payment Entry / Unreconcile Payment."""
    purchase_orders = get_linked_purchase_orders(doc)
    purchase_invoices = get_linked_purchase_invoices(purchase_orders)

    ref_list = [("Purchase Order", po) for po in purchase_orders]
    ref_list += [("Purchase Invoice", pi) for pi in purchase_invoices]
    return ref_list


def get_payment_entry_links(ref_list):
    """Check if any reference is used in a Payment Entry's references child table."""
    linked = []
    for ref_doctype, ref_name in ref_list:
        matches = frappe.get_all(
            "Payment Entry Reference",
            filters={
                "reference_doctype": ref_doctype,
                "reference_name": ref_name,
                "docstatus": ["in", [0, 1, 2]]  # draft, submitted, cancelled
            },
            fields=["parent as payment_entry", "docstatus"],
            distinct=True
        )
        for m in matches:
            linked.append({
                "source": f"{ref_doctype} {ref_name}",
                "linked_doctype": "Payment Entry",
                "linked_name": m.payment_entry,
                "docstatus": m.docstatus
            })
    return linked


def get_unreconcile_payment_links(ref_list):
    """Check if any reference is used in an Unreconcile Payment's allocations child table."""
    linked = []
    for ref_doctype, ref_name in ref_list:
        matches = frappe.get_all(
            "Unreconcile Payment Entries",
            filters={
                "reference_doctype": ref_doctype,
                "reference_name": ref_name
            },
            fields=["parent as unreconcile_payment", "docstatus"],
            distinct=True
        )
        for m in matches:
            linked.append({
                "source": f"{ref_doctype} {ref_name}",
                "linked_doctype": "Unreconcile Payment",
                "linked_name": m.unreconcile_payment,
                "docstatus": m.docstatus
            })
    return linked


def prevent_pis_cancel_or_delete(doc, method):
    """
    hooks.py doc_event handler.
    Frappe calls this with (doc, method) automatically for before_cancel / on_trash.
    `doc` here is the Payment Intimation Slip document being cancelled or deleted.
    """
    ref_list = build_reference_list(doc)

    if not ref_list:
        return

    all_links = get_payment_entry_links(ref_list) + get_unreconcile_payment_links(ref_list)

    if all_links:
        status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
        messages = []
        for link in all_links:
            status = status_map.get(link["docstatus"], "")
            messages.append(
                f"{link['source']} is referenced in {link['linked_doctype']} "
                f"<b>{link['linked_name']}</b> ({status})"
            )

        frappe.throw(
            msg="<br>".join(messages) +
                "<br><br>This Payment Intimation Slip cannot be cancelled or deleted "
                "because its linked Purchase Order / Purchase Invoice is referenced "
                "in the document(s) above. Please unlink or handle those references first.",
            title="Cannot Cancel/Delete Payment Intimation Slip"
        )
################ Not in use this code ###############, not committed #############
