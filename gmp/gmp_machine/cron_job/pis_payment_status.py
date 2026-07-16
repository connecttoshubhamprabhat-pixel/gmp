import frappe
from frappe.utils import flt


def get_payment_entry_reference_details(po_names, pi_names):
    """Sum allocated_amount from 'Pay' type Payment Entries against the
    given PO / PI names (including amendment chains).
    Also returns the set of Payment Entry names (voucher_no) already
    considered here, so the same voucher_no is not double counted
    again from Unreconcile Payment Entries."""
    all_names = po_names + pi_names
    if not all_names:
        return 0, set()

    rows = frappe.db.sql("""
        select per.allocated_amount as amount, pe.name as voucher_no
        from `tabPayment Entry Reference` per
        inner join `tabPayment Entry` pe on pe.name = per.parent
        where per.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and per.reference_name in %(all_names)s
        and pe.payment_type = 'Pay'
        and pe.docstatus = 1
    """, {"all_names": all_names}, as_dict=True)

    total = sum(flt(row.amount) for row in rows)
    considered_voucher_nos = {row.voucher_no for row in rows}

    return total, considered_voucher_nos


def get_unreconciled_total(po_names, pi_names, exclude_voucher_nos=None):
    """Sum allocated_amount from Unreconcile Payment Entries against the
    given PO / PI names. Only one Unreconcile Payment record per
    voucher_no is considered, and any voucher_no already accounted for
    in Payment Entry Reference is skipped entirely, to avoid double counting."""
    all_names = po_names + pi_names
    if not all_names:
        return 0

    exclude_voucher_nos = exclude_voucher_nos or set()

    parent_rows = frappe.db.sql("""
        select distinct up.name, up.voucher_no, up.creation
        from `tabUnreconcile Payment` up
        inner join `tabUnreconcile Payment Entries` allocations on allocations.parent = up.name
        where allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and allocations.reference_name in %(all_names)s
        and up.voucher_type = 'Payment Entry'
        and up.docstatus = 1
        order by up.creation asc
    """, {"all_names": all_names}, as_dict=True)

    seen_voucher_no = set()
    selected_parents = []
    for row in parent_rows:
        if row.voucher_no in exclude_voucher_nos:
            # Already considered via Payment Entry Reference - skip entirely
            continue
        if row.voucher_no in seen_voucher_no:
            continue
        seen_voucher_no.add(row.voucher_no)
        selected_parents.append(row.name)

    if not selected_parents:
        return 0

    total_row = frappe.db.sql("""
        select sum(allocations.allocated_amount) as total
        from `tabUnreconcile Payment Entries` allocations
        where allocations.parent in %(parents)s
        and allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and allocations.reference_name in %(all_names)s
    """, {"parents": selected_parents, "all_names": all_names}, as_dict=True)

    return total_row[0].total or 0


def get_pis_records_for_po(po_names):
    """Fetch all Payment Intimation Slips for the given PO names,
    using purchase_order_duplicate only when purchase_order is blank.
    Results are returned oldest creation first (FIFO order)."""
    rows = frappe.db.sql("""
        select name, payment_amount, payment_status, percentage_paid, creation
        from `tabPayment Intimation Slip`
        where docstatus = 1
        and (
            purchase_order in %(po_names)s
            or (
                ifnull(purchase_order, '') = ''
                and purchase_order_duplicate in %(po_names)s
            )
        )
        order by creation asc
    """, {"po_names": po_names}, as_dict=True)

    return rows


def get_amendment_chain(doctype, name):
    """Return a document name together with all of its amended ancestors."""
    names = []
    current_name = name

    while current_name and current_name not in names:
        names.append(current_name)
        current_name = frappe.db.get_value(doctype, current_name, "amended_from")

    return names


def get_amendment_family(doctype, name):
    """Return a document's root, ancestors, and all amended descendants."""
    family_names = set(get_amendment_chain(doctype, name))
    names_to_check = list(family_names)

    while names_to_check:
        child_names = frappe.get_all(
            doctype,
            filters={"amended_from": ["in", names_to_check]},
            pluck="name",
        )
        names_to_check = [
            child_name for child_name in child_names if child_name not in family_names
        ]
        family_names.update(names_to_check)

    return list(family_names)


def get_purchase_invoice_names(po_names):
    """Return Purchase Invoices linked to the PO chain and their ancestors."""
    invoice_names = frappe.get_all(
        "Purchase Invoice",
        filters={"purchase_order": ["in", po_names]},
        pluck="name",
    )

    all_invoice_names = []
    for invoice_name in invoice_names:
        for name in get_amendment_chain("Purchase Invoice", invoice_name):
            if name not in all_invoice_names:
                all_invoice_names.append(name)

    return all_invoice_names



@frappe.whitelist()
def update_submitted_pis_payment_status():
    """Update submitted PIS payment statuses from PO/PI payment allocations.

    Payment is allocated FIFO: the oldest PIS for a PO is paid first, then
    any remaining amount is applied to the following PIS records. Draft and
    cancelled Payment Intimation Slips are not selected or updated.
    """
    pis_rows = frappe.get_all(
        "Payment Intimation Slip",
        filters={"docstatus": 1},
        fields=["purchase_order", "purchase_order_duplicate"],
    )

    po_roots = set()
    skipped_without_po = 0
    for pis in pis_rows:
        po_name = pis.purchase_order or pis.purchase_order_duplicate
        if po_name:
            # Group amended versions of the same PO into one FIFO allocation.
            po_roots.add(get_amendment_chain("Purchase Order", po_name)[-1])
        else:
            skipped_without_po += 1

    updated_count = 0
    for po_root in po_roots:
        po_names = get_amendment_family("Purchase Order", po_root)
        pi_names = get_purchase_invoice_names(po_names)
        pis_records = get_pis_records_for_po(po_names)

        payment_total, considered_voucher_nos = get_payment_entry_reference_details(
            po_names, pi_names
        )
        payment_total += get_unreconciled_total(
            po_names, pi_names, considered_voucher_nos
        )

        remaining_amount = flt(payment_total)
        for pis in pis_records:
            pis_amount = flt(pis.payment_amount)

            if pis_amount <= 0 or remaining_amount <= 0:
                payment_status = "Unpaid"
                percentage_paid = 0
            elif remaining_amount >= pis_amount:
                payment_status = "Paid"
                percentage_paid = 100
                remaining_amount -= pis_amount
            else:
                payment_status = "Partially Paid"
                percentage_paid = flt((remaining_amount / pis_amount) * 100, 2)
                remaining_amount = 0

            if (
                pis.payment_status != payment_status
                or flt(pis.percentage_paid) != percentage_paid
            ):
                frappe.db.set_value(
                    "Payment Intimation Slip",
                    pis.name,
                    {
                        "payment_status": payment_status,
                        "percentage_paid": percentage_paid,
                    },
                )
                updated_count += 1

    return {
        "submitted_pis": len(pis_rows),
        "purchase_order_groups": len(po_roots),
        "updated_pis": updated_count,
        "skipped_without_purchase_order": skipped_without_po,
    }
