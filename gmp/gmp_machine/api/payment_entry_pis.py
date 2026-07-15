# import frappe


# def get_purchase_invoices_against_po(po_name):
#     """Fetch all submitted Purchase Invoices made against the given Purchase Order."""
#     pi_rows = frappe.db.sql("""
#         select distinct pii.parent as pi_name
#         from `tabPurchase Invoice Item` pii
#         inner join `tabPurchase Invoice` pi on pi.name = pii.parent
#         where pii.purchase_order = %(po_name)s
#         and pii.docstatus = 1
#         and pi.docstatus = 1
#     """, {"po_name": po_name}, as_dict=True)

#     return [row.pi_name for row in pi_rows]


# def get_payment_entry_breakdown(reference_names):
#     """Return allocated_amount summed per reference (PO / each PI individually)
#     from submitted Payment Entries."""
#     rows = frappe.db.sql("""
#         select per.reference_doctype, per.reference_name, sum(per.allocated_amount) as total
#         from `tabPayment Entry Reference` per
#         inner join `tabPayment Entry` pe on pe.name = per.parent
#         where per.reference_doctype in ('Purchase Order', 'Purchase Invoice')
#         and per.reference_name in %(reference_names)s
#         and per.docstatus = 1
#         and pe.docstatus = 1
#         group by per.reference_doctype, per.reference_name
#     """, {"reference_names": reference_names}, as_dict=True)

#     return rows


# def get_unreconciled_details(reference_names):
#     """Informational only - NOT considered in the remaining amount calculation.
#     Multiple 'Unreconcile Payment' records can exist against the same
#     voucher_no (Payment Entry) - only one such record per voucher_no is
#     considered to avoid double counting."""
#     if not reference_names:
#         return {"total": 0, "count": 0, "voucher_nos": []}

#     # Distinct Unreconcile Payment parents (against Payment Entry voucher type)
#     # that have at least one allocation row matching our reference filter
#     parent_rows = frappe.db.sql("""
#         select distinct up.name, up.voucher_no, up.creation
#         from `tabUnreconcile Payment` up
#         inner join `tabUnreconcile Payment Entries` allocations on allocations.parent = up.name
#         where allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
#         and allocations.reference_name in %(reference_names)s
#         and allocations.unlinked = 1
#         and allocations.docstatus = 1
#         and up.voucher_type = 'Payment Entry'
#         and up.docstatus = 1
#         order by up.creation asc
#     """, {"reference_names": reference_names}, as_dict=True)

#     # Keep only one Unreconcile Payment record per voucher_no
#     seen_voucher_no = set()
#     selected_parents = []
#     for row in parent_rows:
#         if row.voucher_no in seen_voucher_no:
#             continue
#         seen_voucher_no.add(row.voucher_no)
#         selected_parents.append(row.name)

#     if not selected_parents:
#         return {"total": 0, "count": 0, "voucher_nos": []}

#     total_row = frappe.db.sql("""
#         select sum(allocations.allocated_amount) as total
#         from `tabUnreconcile Payment Entries` allocations
#         where allocations.parent in %(parents)s
#         and allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
#         and allocations.reference_name in %(reference_names)s
#         and allocations.unlinked = 1
#         and allocations.docstatus = 1
#     """, {"parents": selected_parents, "reference_names": reference_names}, as_dict=True)

#     return {
#         "total": total_row[0].total or 0,
#         "count": len(selected_parents),
#         "voucher_nos": list(seen_voucher_no)
#     }


# def get_pis_total_payment_amount(po_name):
#     """Sum payment_amount from submitted Payment Intimation Slip records
#     linked to the given Purchase Order (directly or via duplicate field)."""
#     result = frappe.db.sql("""
#         select sum(payment_amount) as total
#         from `tabPayment Intimation Slip`
#         where docstatus = 1
#         and (purchase_order = %(po_name)s or purchase_order_duplicate = %(po_name)s)
#     """, {"po_name": po_name}, as_dict=True)

#     return result[0].total or 0


# @frappe.whitelist()
# def calculate_pis_paid_amount(payment_entry=None, purchase_order=None):
#     """Calculate remaining PIS payment amount for a Purchase Order,
#     after netting off amounts already paid/allocated via submitted Payment
#     Entries only. Unreconciled Payment Entries are reported for information
#     but are NOT deducted from the remaining amount."""
#     if not purchase_order:
#         frappe.throw("Purchase Order is required")

#     pi_names = get_purchase_invoices_against_po(purchase_order)
#     all_reference_names = [purchase_order] + pi_names

#     pe_breakdown = get_payment_entry_breakdown(all_reference_names)

#     po_payment_entry_amount = 0
#     pi_payment_entry_details = []
#     pi_payment_entry_total = 0

#     for row in pe_breakdown:
#         if row.reference_doctype == "Purchase Order":
#             po_payment_entry_amount += row.total or 0
#         else:
#             pi_payment_entry_details.append({
#                 "purchase_invoice": row.reference_name,
#                 "amount": row.total or 0
#             })
#             pi_payment_entry_total += row.total or 0

#     total_paid = po_payment_entry_amount + pi_payment_entry_total

#     unreconciled = get_unreconciled_details(all_reference_names)

#     total_pis_amount = get_pis_total_payment_amount(purchase_order)
#     remaining = total_pis_amount - total_paid

#     return {
#         "purchase_order": purchase_order,
#         "linked_purchase_invoices": pi_names,
#         "total_pis_amount": total_pis_amount,
#         "po_payment_entry_amount": po_payment_entry_amount,
#         "pi_payment_entry_details": pi_payment_entry_details,
#         "pi_payment_entry_total": pi_payment_entry_total,
#         "total_paid": total_paid,
#         "unreconciled_total": unreconciled["total"],
#         "unreconciled_count": unreconciled["count"],
#         "remaining": remaining
#     }
































import frappe


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


def get_payment_entry_breakdown(po_names, pi_names):
    """Return allocated_amount summed per reference (PO / each PI individually)
    from submitted Payment Entries. Matches against all amendment-chain
    names for the PO, but groups PI amounts under their current (latest) name."""
    all_reference_names = po_names + pi_names

    rows = frappe.db.sql("""
        select per.reference_doctype, per.reference_name, sum(per.allocated_amount) as total
        from `tabPayment Entry Reference` per
        inner join `tabPayment Entry` pe on pe.name = per.parent
        where per.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and per.reference_name in %(reference_names)s
        and per.docstatus = 1
        and pe.docstatus = 1
        group by per.reference_doctype, per.reference_name
    """, {"reference_names": all_reference_names}, as_dict=True)

    return rows


def get_unreconciled_details(all_names):
    """Informational only - NOT considered in the remaining amount calculation.
    Checks the full amendment chain (PO + all its cancelled ancestors, and
    each PI + its cancelled ancestors) since Unreconcile Payment Entries
    reference the document name as it existed at the time of payment,
    which may since have been cancelled and amended.
    Multiple 'Unreconcile Payment' records can exist against the same
    voucher_no (Payment Entry) - only one such record per voucher_no is
    considered to avoid double counting."""
    if not all_names:
        return {"total": 0, "count": 0, "voucher_nos": []}

    parent_rows = frappe.db.sql("""
        select distinct up.name, up.voucher_no, up.creation
        from `tabUnreconcile Payment` up
        inner join `tabUnreconcile Payment Entries` allocations on allocations.parent = up.name
        where allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and allocations.reference_name in %(all_names)s
        and allocations.unlinked = 1
        and allocations.docstatus = 1
        and up.voucher_type = 'Payment Entry'
        and up.docstatus = 1
        order by up.creation asc
    """, {"all_names": all_names}, as_dict=True)

    # Keep only one Unreconcile Payment record per voucher_no
    seen_voucher_no = set()
    selected_parents = []
    for row in parent_rows:
        if row.voucher_no in seen_voucher_no:
            continue
        seen_voucher_no.add(row.voucher_no)
        selected_parents.append(row.name)

    if not selected_parents:
        return {"total": 0, "count": 0, "voucher_nos": []}

    total_row = frappe.db.sql("""
        select sum(allocations.allocated_amount) as total
        from `tabUnreconcile Payment Entries` allocations
        where allocations.parent in %(parents)s
        and allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
        and allocations.reference_name in %(all_names)s
        and allocations.unlinked = 1
        and allocations.docstatus = 1
    """, {"parents": selected_parents, "all_names": all_names}, as_dict=True)

    return {
        "total": total_row[0].total or 0,
        "count": len(selected_parents),
        "voucher_nos": list(seen_voucher_no)
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
    """Calculate remaining PIS payment amount for a Purchase Order,
    after netting off amounts already paid/allocated via submitted Payment
    Entries only. Unreconciled Payment Entries are reported for information
    but are NOT deducted from the remaining amount.
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

    pe_breakdown = get_payment_entry_breakdown(po_names, all_pi_names)

    po_payment_entry_amount = 0
    pi_amount_map = {}  # current pi name -> aggregated amount across its chain

    for row in pe_breakdown:
        if row.reference_doctype == "Purchase Order":
            po_payment_entry_amount += row.total or 0
        else:
            # Map whichever chain-name this row belongs to, back to the current PI name
            matched_current_pi = None
            for current_pi, chain in pi_current_to_chain.items():
                if row.reference_name in chain:
                    matched_current_pi = current_pi
                    break

            key = matched_current_pi or row.reference_name
            pi_amount_map[key] = pi_amount_map.get(key, 0) + (row.total or 0)

    pi_payment_entry_details = [
        {"purchase_invoice": pi, "amount": amount}
        for pi, amount in pi_amount_map.items()
    ]
    pi_payment_entry_total = sum(pi_amount_map.values())

    total_paid = po_payment_entry_amount + pi_payment_entry_total

    unreconciled = get_unreconciled_details(all_names)

    total_pis_amount = get_pis_total_payment_amount(po_names)
    remaining = total_pis_amount - total_paid

    return {
        "purchase_order": purchase_order,
        "linked_purchase_invoices": pi_names,
        "total_pis_amount": total_pis_amount,
        "po_payment_entry_amount": po_payment_entry_amount,
        "pi_payment_entry_details": pi_payment_entry_details,
        "pi_payment_entry_total": pi_payment_entry_total,
        "total_paid": total_paid,
        "unreconciled_total": unreconciled["total"],
        "unreconciled_count": unreconciled["count"],
        "remaining": remaining
    }