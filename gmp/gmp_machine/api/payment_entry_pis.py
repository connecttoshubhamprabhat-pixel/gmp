import frappe
from frappe.utils import flt


def get_amendment_chain(doctype, docname):
    """Walk the amendment chain backwards (via amended_from) to collect
    the given document name plus all its cancelled ancestor names."""
    chain = [docname]
    current = docname

    while True:
        amended_from = frappe.db.get_value(doctype, current, "amended_from")
        if not amended_from:
            break
        chain.append(amended_from)
        current = amended_from

    return chain


def get_purchase_invoices_against_po(po_names):
    """Fetch all submitted Purchase Invoices made against any of the given
    Purchase Order names (current PO + its cancelled ancestors)."""
    pi_rows = frappe.db.sql("""
        select distinct pii.parent as pi_name
        from `tabPurchase Invoice Item` pii
        inner join `tabPurchase Invoice` pi on pi.name = pii.parent
        where pii.purchase_order in %(po_names)s
        and pii.docstatus = 1
        and pi.docstatus = 1
    """, {"po_names": po_names}, as_dict=True)

    return [row.pi_name for row in pi_rows]


def get_payment_entry_rows(po_names, pi_names):
    """Row-level detail (not grouped) from submitted Payment Entry references
    against the given PO / PI names. `parent` on Payment Entry Reference is
    itself the Payment Entry name (voucher_no) - no join needed, since child
    table docstatus already mirrors the parent Payment Entry's docstatus."""
    all_reference_names = po_names + pi_names
    if not all_reference_names:
        return []

    rows = frappe.db.sql("""
        select per.reference_doctype, per.reference_name,
               per.allocated_amount as amount, per.parent as voucher_no
        from `tabPayment Entry Reference` per
        where per.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and per.reference_name in %(reference_names)s
        and per.docstatus = 1
    """, {"reference_names": all_reference_names}, as_dict=True)

    return rows


def get_payment_entries_unallocated_amount(voucher_nos):
    """Fetch id + unallocated_amount for the given list of Payment Entry names."""
    if not voucher_nos:
        return []

    rows = frappe.get_all(
        "Payment Entry",
        filters={"name": ["in", list(voucher_nos)]},
        fields=["name", "unallocated_amount"]
    )

    return [
        {"name": row.name, "unallocated_amount": flt(row.unallocated_amount)}
        for row in rows
    ]


def get_unreconciled_rows_with_voucher(all_names):
    """Fetch every Unreconcile Payment Entries row matching the given
    PO / PI names, along with the voucher_no of its parent Unreconcile
    Payment document (only where voucher_type = Payment Entry)."""
    if not all_names:
        return []

    rows = frappe.db.sql("""
        select allocations.allocated_amount as amount,
               allocations.parent as unrec_payment_name,
               up.voucher_no as voucher_no
        from `tabUnreconcile Payment Entries` allocations
        inner join `tabUnreconcile Payment` up on up.name = allocations.parent
        where allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and allocations.reference_name in %(all_names)s
        and allocations.unlinked = 1
        and allocations.docstatus = 1
        and up.voucher_type = 'Payment Entry'
        and up.docstatus = 1
    """, {"all_names": all_names}, as_dict=True)

    return rows


def get_unreconciled_unallocated_breakdown(all_names, considered_voucher_nos, pe_unallocated_map):
    """Group Unreconcile Payment Entries rows by their parent's voucher_no:
    - if that voucher_no is ALREADY linked to PO/PI directly (considered_voucher_nos),
      skip the Unreconcile rows entirely and use that Payment Entry's own
      unallocated_amount instead.
    - otherwise, take the MAXIMUM single allocated_amount row for that
      voucher_no (not the sum) as its contribution."""
    rows = get_unreconciled_rows_with_voucher(all_names)

    grouped = {}
    for row in rows:
        grouped.setdefault(row.voucher_no, []).append(flt(row.amount))

    matched_details = []
    matched_total = 0
    unmatched_details = []
    unmatched_total = 0

    for voucher_no, amounts in grouped.items():
        if voucher_no in considered_voucher_nos:
            unallocated = pe_unallocated_map.get(voucher_no, 0)
            matched_details.append({"voucher_no": voucher_no, "unallocated_amount": unallocated})
            matched_total += unallocated
        else:
            max_amount = max(amounts)
            unmatched_details.append({"voucher_no": voucher_no, "amount": max_amount})
            unmatched_total += max_amount

    return {
        "matched_details": matched_details,
        "matched_total": matched_total,
        "unmatched_details": unmatched_details,
        "unmatched_total": unmatched_total,
        "unallocated_amount_total": matched_total + unmatched_total
    }


def get_pis_total_payment_amount(po_names):
    """Sum payment_amount from submitted Payment Intimation Slip records
    linked to any of the given Purchase Order names (current + cancelled ancestors)."""
    result = frappe.db.sql("""
        select sum(payment_amount) as total
        from `tabPayment Intimation Slip`
        where docstatus = 1
        and (purchase_order in %(po_names)s or purchase_order_duplicate in %(po_names)s)
    """, {"po_names": po_names}, as_dict=True)

    return result[0].total or 0


@frappe.whitelist()
def calculate_pis_paid_amount(payment_entry=None, purchase_order=None):
    """Calculate remaining PIS payment amount for a Purchase Order.
    remaining = total_pis_amount - (po_amount + pi_amount + unallocated_amount)
    where unallocated_amount combines, per unique voucher_no found in
    Unreconcile Payment Entries against PO/PI:
    - Payment Entry's own unallocated_amount, if that voucher_no is
      ALSO directly linked to PO/PI via Payment Entry Reference
    - the MAXIMUM single allocated_amount row from Unreconcile Payment
      Entries, if that voucher_no is NOT directly linked to PO/PI
    Handles amendment chains for both the PO and each linked PI, since
    cancel + amend creates a new document name while old payment
    records still reference the original (now cancelled) name."""
    if not purchase_order:
        frappe.throw("Purchase Order is required")

    # Collect current PO + all its cancelled ancestor names
    po_names = get_amendment_chain("Purchase Order", purchase_order)

    # Purchase Invoices are looked up against the full PO amendment chain
    pi_names = get_purchase_invoices_against_po(po_names)

    # For each PI, collect its own amendment chain too
    all_pi_names = []
    pi_current_to_chain = {}
    for pi in pi_names:
        pi_chain = get_amendment_chain("Purchase Invoice", pi)
        pi_current_to_chain[pi] = pi_chain
        all_pi_names.extend(pi_chain)

    all_names = po_names + all_pi_names

    pe_rows = get_payment_entry_rows(po_names, all_pi_names)

    po_payment_entry_amount = 0
    pi_amount_map = {}  # current pi name -> aggregated amount across its chain
    considered_voucher_nos = set()

    for row in pe_rows:
        considered_voucher_nos.add(row.voucher_no)

        if row.reference_doctype == "Purchase Order":
            po_payment_entry_amount += flt(row.amount)
        else:
            # Map whichever chain-name this row belongs to, back to the current PI name
            matched_current_pi = None
            for current_pi, chain in pi_current_to_chain.items():
                if row.reference_name in chain:
                    matched_current_pi = current_pi
                    break

            key = matched_current_pi or row.reference_name
            pi_amount_map[key] = pi_amount_map.get(key, 0) + flt(row.amount)

    pi_payment_entry_details = [
        {"purchase_invoice": pi, "amount": amount}
        for pi, amount in pi_amount_map.items()
    ]
    pi_payment_entry_total = sum(pi_amount_map.values())

    # Unallocated amount for Payment Entries found via direct PO/PI references
    pe_unallocated_details = get_payment_entries_unallocated_amount(considered_voucher_nos)
    pe_unallocated_map = {d["name"]: d["unallocated_amount"] for d in pe_unallocated_details}

    unreconciled = get_unreconciled_unallocated_breakdown(all_names, considered_voucher_nos, pe_unallocated_map)

    total_paid = po_payment_entry_amount + pi_payment_entry_total + unreconciled["unallocated_amount_total"]

    total_pis_amount = get_pis_total_payment_amount(po_names)
    remaining = total_pis_amount - total_paid

    return {
        "purchase_order": purchase_order,
        "linked_purchase_invoices": pi_names,
        "total_pis_amount": total_pis_amount,
        "po_payment_entry_amount": po_payment_entry_amount,
        "pi_payment_entry_details": pi_payment_entry_details,
        "pi_payment_entry_total": pi_payment_entry_total,
        "pe_unallocated_details": pe_unallocated_details,
        "unreconciled_matched_details": unreconciled["matched_details"],
        "unreconciled_matched_total": unreconciled["matched_total"],
        "unreconciled_unmatched_details": unreconciled["unmatched_details"],
        "unreconciled_unmatched_total": unreconciled["unmatched_total"],
        "unallocated_amount_total": unreconciled["unallocated_amount_total"],
        "total_paid": total_paid,
        "remaining": remaining
    }