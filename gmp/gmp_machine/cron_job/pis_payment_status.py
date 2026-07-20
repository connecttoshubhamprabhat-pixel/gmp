# import frappe
# from frappe.utils import flt


# def get_payment_entry_reference_details(po_names, pi_names):
#     """Sum allocated_amount from 'Pay' type Payment Entries against the
#     given PO / PI names (including amendment chains).
#     Also returns the set of Payment Entry names (voucher_no) already
#     considered here, so the same voucher_no is not double counted
#     again from Unreconcile Payment Entries."""
#     all_names = po_names + pi_names
#     if not all_names:
#         return 0, set()

#     rows = frappe.db.sql("""
#         select per.allocated_amount as amount, pe.name as voucher_no
#         from `tabPayment Entry Reference` per
#         inner join `tabPayment Entry` pe on pe.name = per.parent
#         where per.reference_doctype in ('Purchase Order', 'Purchase Invoice')
#         and per.reference_name in %(all_names)s
#         and pe.payment_type = 'Pay'
#         and pe.docstatus = 1
#     """, {"all_names": all_names}, as_dict=True)

#     total = sum(flt(row.amount) for row in rows)
#     considered_voucher_nos = {row.voucher_no for row in rows}

#     return total, considered_voucher_nos


# def get_unreconciled_total(po_names, pi_names, exclude_voucher_nos=None):
#     """Sum allocated_amount from Unreconcile Payment Entries against the
#     given PO / PI names. Only one Unreconcile Payment record per
#     voucher_no is considered, and any voucher_no already accounted for
#     in Payment Entry Reference is skipped entirely, to avoid double counting."""
#     all_names = po_names + pi_names
#     if not all_names:
#         return 0

#     exclude_voucher_nos = exclude_voucher_nos or set()

#     parent_rows = frappe.db.sql("""
#         select distinct up.name, up.voucher_no, up.creation
#         from `tabUnreconcile Payment` up
#         inner join `tabUnreconcile Payment Entries` allocations on allocations.parent = up.name
#         where allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
#         and allocations.reference_name in %(all_names)s
#         and up.voucher_type = 'Payment Entry'
#         and up.docstatus = 1
#         order by up.creation asc
#     """, {"all_names": all_names}, as_dict=True)

#     seen_voucher_no = set()
#     selected_parents = []
#     for row in parent_rows:
#         if row.voucher_no in exclude_voucher_nos:
#             # Already considered via Payment Entry Reference - skip entirely
#             continue
#         if row.voucher_no in seen_voucher_no:
#             continue
#         seen_voucher_no.add(row.voucher_no)
#         selected_parents.append(row.name)

#     if not selected_parents:
#         return 0

#     total_row = frappe.db.sql("""
#         select sum(allocations.allocated_amount) as total
#         from `tabUnreconcile Payment Entries` allocations
#         where allocations.parent in %(parents)s
#         and allocations.reference_doctype in ('Purchase Order', 'Purchase Invoice')
#         and allocations.reference_name in %(all_names)s
#     """, {"parents": selected_parents, "all_names": all_names}, as_dict=True)

#     return total_row[0].total or 0


# def get_pis_records_for_po(po_names):
#     """Fetch all Payment Intimation Slips for the given PO names,
#     using purchase_order_duplicate only when purchase_order is blank.
#     Results are returned oldest creation first (FIFO order)."""
#     rows = frappe.db.sql("""
#         select name, payment_amount, payment_status, percentage_paid, creation
#         from `tabPayment Intimation Slip`
#         where docstatus = 1
#         and (
#             purchase_order in %(po_names)s
#             or (
#                 ifnull(purchase_order, '') = ''
#                 and purchase_order_duplicate in %(po_names)s
#             )
#         )
#         order by creation asc
#     """, {"po_names": po_names}, as_dict=True)

#     return rows


# def get_amendment_chain(doctype, name):
#     """Return a document name together with all of its amended ancestors."""
#     names = []
#     current_name = name

#     while current_name and current_name not in names:
#         names.append(current_name)
#         current_name = frappe.db.get_value(doctype, current_name, "amended_from")

#     return names


# def get_amendment_family(doctype, name):
#     """Return a document's root, ancestors, and all amended descendants."""
#     family_names = set(get_amendment_chain(doctype, name))
#     names_to_check = list(family_names)

#     while names_to_check:
#         child_names = frappe.get_all(
#             doctype,
#             filters={"amended_from": ["in", names_to_check]},
#             pluck="name",
#         )
#         names_to_check = [
#             child_name for child_name in child_names if child_name not in family_names
#         ]
#         family_names.update(names_to_check)

#     return list(family_names)


# def get_purchase_invoice_names(po_names):
#     """Return Purchase Invoices linked to the PO chain and their ancestors."""
#     invoice_names = frappe.get_all(
#         "Purchase Invoice",
#         filters={"purchase_order": ["in", po_names]},
#         pluck="name",
#     )

#     all_invoice_names = []
#     for invoice_name in invoice_names:
#         for name in get_amendment_chain("Purchase Invoice", invoice_name):
#             if name not in all_invoice_names:
#                 all_invoice_names.append(name)

#     return all_invoice_names



# @frappe.whitelist()
# def update_submitted_pis_payment_status():
#     """Update submitted PIS payment statuses from PO/PI payment allocations.

#     Payment is allocated FIFO: the oldest PIS for a PO is paid first, then
#     any remaining amount is applied to the following PIS records. Draft and
#     cancelled Payment Intimation Slips are not selected or updated.
#     """
#     pis_rows = frappe.get_all(
#         "Payment Intimation Slip",
#         filters={"docstatus": 1},
#         fields=["purchase_order", "purchase_order_duplicate"],
#     )

#     po_roots = set()
#     skipped_without_po = 0
#     for pis in pis_rows:
#         po_name = pis.purchase_order or pis.purchase_order_duplicate
#         if po_name:
#             # Group amended versions of the same PO into one FIFO allocation.
#             po_roots.add(get_amendment_chain("Purchase Order", po_name)[-1])
#         else:
#             skipped_without_po += 1

#     updated_count = 0
#     for po_root in po_roots:
#         po_names = get_amendment_family("Purchase Order", po_root)
#         pi_names = get_purchase_invoice_names(po_names)
#         pis_records = get_pis_records_for_po(po_names)

#         payment_total, considered_voucher_nos = get_payment_entry_reference_details(
#             po_names, pi_names
#         )
#         payment_total += get_unreconciled_total(
#             po_names, pi_names, considered_voucher_nos
#         )

#         remaining_amount = flt(payment_total)
#         for pis in pis_records:
#             pis_amount = flt(pis.payment_amount)

#             if pis_amount <= 0 or remaining_amount <= 0:
#                 payment_status = "Unpaid"
#                 percentage_paid = 0
#             elif remaining_amount >= pis_amount:
#                 payment_status = "Paid"
#                 percentage_paid = 100
#                 remaining_amount -= pis_amount
#             else:
#                 payment_status = "Partially Paid"
#                 percentage_paid = flt((remaining_amount / pis_amount) * 100, 2)
#                 remaining_amount = 0

#             if (
#                 pis.payment_status != payment_status
#                 or flt(pis.percentage_paid) != percentage_paid
#             ):
#                 frappe.db.set_value(
#                     "Payment Intimation Slip",
#                     pis.name,
#                     {
#                         "payment_status": payment_status,
#                         "percentage_paid": percentage_paid,
#                     },
#                 )
#                 updated_count += 1

#     return {
#         "submitted_pis": len(pis_rows),
#         "purchase_order_groups": len(po_roots),
#         "updated_pis": updated_count,
#         "skipped_without_purchase_order": skipped_without_po,
#     }
















































































import frappe
from frappe.utils import flt


def get_purchase_invoices_against_po(purchase_order):
    """Exact Purchase Order ke against submitted Purchase Invoices fetch karega."""
    if not purchase_order:
        return []

    rows = frappe.db.sql(
        """
        SELECT DISTINCT
            pii.parent AS purchase_invoice
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        WHERE pii.purchase_order = %(purchase_order)s
        AND pi.docstatus = 1
        """,
        {
            "purchase_order": purchase_order,
        },
        as_dict=True,
    )

    return [
        row.purchase_invoice
        for row in rows
        if row.purchase_invoice
    ]


def get_payment_entry_reference_details(purchase_order, pi_names):
    """PO aur PI ke against directly linked submitted Pay-type Payment Entries
    ka allocated amount aur voucher numbers return karega.
    """
    reference_names = [purchase_order] + list(pi_names or [])

    if not reference_names:
        return 0, set()

    rows = frappe.db.sql(
        """
        SELECT
            per.allocated_amount AS amount,
            pe.name AS voucher_no
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe
            ON pe.name = per.parent
        WHERE per.reference_doctype IN (
            'Purchase Order',
            'Purchase Invoice'
        )
        AND per.reference_name IN %(reference_names)s
        AND pe.payment_type = 'Pay'
        AND pe.docstatus = 1
        """,
        {
            "reference_names": reference_names,
        },
        as_dict=True,
    )

    direct_payment_total = sum(
        flt(row.amount)
        for row in rows
    )

    linked_voucher_nos = {
        row.voucher_no
        for row in rows
        if row.voucher_no
    }

    return direct_payment_total, linked_voucher_nos


def get_payment_entry_unallocated_amounts(voucher_nos):
    """Payment Entry voucher numbers ka current unallocated_amount return karega."""
    if not voucher_nos:
        return {}

    rows = frappe.get_all(
        "Payment Entry",
        filters={
            "name": ["in", list(voucher_nos)],
            "payment_type": "Pay",
            "docstatus": 1,
        },
        fields=[
            "name",
            "unallocated_amount",
        ],
    )

    return {
        row.name: flt(row.unallocated_amount)
        for row in rows
    }


def get_unreconciled_payment_details(
    purchase_order,
    pi_names,
    linked_voucher_nos=None,
):
    """Unreconcile Payment calculation:

    1. Agar voucher Payment Entry Reference me PO/PI se linked hai:
       Payment Entry.unallocated_amount liya jayega.

    2. Agar voucher Payment Entry Reference me linked nahi hai:
       same voucher ke Unreconcile Payment Entries me se maximum
       allocated_amount liya jayega.

    3. Har voucher number ek hi baar consider hoga.
    """
    reference_names = [purchase_order] + list(pi_names or [])

    if not reference_names:
        return {
            "matched_details": [],
            "matched_total": 0,
            "unmatched_details": [],
            "unmatched_total": 0,
            "total": 0,
        }

    linked_voucher_nos = linked_voucher_nos or set()

    rows = frappe.db.sql(
        """
        SELECT
            up.voucher_no AS voucher_no,
            allocations.allocated_amount AS allocated_amount,
            allocations.parent AS unreconcile_payment
        FROM `tabUnreconcile Payment Entries` allocations
        INNER JOIN `tabUnreconcile Payment` up
            ON up.name = allocations.parent
        WHERE allocations.reference_doctype IN (
            'Purchase Order',
            'Purchase Invoice'
        )
        AND allocations.reference_name IN %(reference_names)s
        AND allocations.unlinked = 1
        AND allocations.docstatus = 1
        AND up.voucher_type = 'Payment Entry'
        AND up.docstatus = 1
        ORDER BY up.creation ASC
        """,
        {
            "reference_names": reference_names,
        },
        as_dict=True,
    )

    voucher_amounts = {}

    for row in rows:
        if not row.voucher_no:
            continue

        voucher_amounts.setdefault(
            row.voucher_no,
            [],
        ).append(
            flt(row.allocated_amount)
        )

    matched_voucher_nos = {
        voucher_no
        for voucher_no in voucher_amounts
        if voucher_no in linked_voucher_nos
    }

    unallocated_amount_map = get_payment_entry_unallocated_amounts(
        matched_voucher_nos
    )

    matched_details = []
    matched_total = 0

    unmatched_details = []
    unmatched_total = 0

    for voucher_no, amounts in voucher_amounts.items():
        if voucher_no in linked_voucher_nos:
            unallocated_amount = flt(
                unallocated_amount_map.get(
                    voucher_no,
                    0,
                )
            )

            matched_details.append(
                {
                    "voucher_no": voucher_no,
                    "unallocated_amount": unallocated_amount,
                }
            )

            matched_total += unallocated_amount

        else:
            maximum_allocated_amount = (
                max(amounts)
                if amounts
                else 0
            )

            unmatched_details.append(
                {
                    "voucher_no": voucher_no,
                    "maximum_allocated_amount": maximum_allocated_amount,
                }
            )

            unmatched_total += maximum_allocated_amount

    return {
        "matched_details": matched_details,
        "matched_total": matched_total,
        "unmatched_details": unmatched_details,
        "unmatched_total": unmatched_total,
        "total": matched_total + unmatched_total,
    }


def get_submitted_pis_records(purchase_order):
    """Exact Purchase Order ke submitted PIS oldest-first return karega.

    Pehle purchase_order check hoga. purchase_order blank hone par hi
    purchase_order_duplicate check hoga.
    """
    if not purchase_order:
        return []

    return frappe.db.sql(
        """
        SELECT
            name,
            payment_amount,
            payment_status,
            percentage_paid,
            creation
        FROM `tabPayment Intimation Slip`
        WHERE docstatus = 1
        AND (
            purchase_order = %(purchase_order)s
            OR (
                IFNULL(purchase_order, '') = ''
                AND purchase_order_duplicate = %(purchase_order)s
            )
        )
        ORDER BY creation ASC, name ASC
        """,
        {
            "purchase_order": purchase_order,
        },
        as_dict=True,
    )


@frappe.whitelist()
def update_submitted_pis_payment_status():
    """Submitted PIS payment statuses ko FIFO order me update karega."""

    pis_rows = frappe.get_all(
        "Payment Intimation Slip",
        filters={
            "docstatus": 1,
        },
        fields=[
            "name",
            "purchase_order",
            "purchase_order_duplicate",
        ],
    )

    purchase_orders = set()
    skipped_without_purchase_order = 0

    for pis in pis_rows:
        purchase_order = (
            pis.purchase_order
            if pis.purchase_order
            else pis.purchase_order_duplicate
        )

        if not purchase_order:
            skipped_without_purchase_order += 1
            continue

        purchase_orders.add(purchase_order)

    updated_count = 0

    total_direct_payment = 0
    total_matched_unallocated = 0
    total_unmatched_unreconciled = 0

    purchase_order_details = []

    for purchase_order in purchase_orders:
        pi_names = get_purchase_invoices_against_po(
            purchase_order
        )

        pis_records = get_submitted_pis_records(
            purchase_order
        )

        direct_payment_total, linked_voucher_nos = (
            get_payment_entry_reference_details(
                purchase_order,
                pi_names,
            )
        )

        unreconciled_details = get_unreconciled_payment_details(
            purchase_order,
            pi_names,
            linked_voucher_nos,
        )

        total_payment = (
            flt(direct_payment_total)
            + flt(unreconciled_details["total"])
        )

        total_direct_payment += flt(
            direct_payment_total
        )

        total_matched_unallocated += flt(
            unreconciled_details["matched_total"]
        )

        total_unmatched_unreconciled += flt(
            unreconciled_details["unmatched_total"]
        )

        remaining_amount = flt(
            total_payment
        )

        po_updated_count = 0

        for pis in pis_records:
            pis_amount = flt(
                pis.payment_amount
            )

            if (
                pis_amount <= 0
                or remaining_amount <= 0
            ):
                payment_status = "Unpaid"
                percentage_paid = 0

            elif remaining_amount >= pis_amount:
                payment_status = "Paid"
                percentage_paid = 100

                remaining_amount -= pis_amount

            else:
                payment_status = "Partially Paid"

                percentage_paid = flt(
                    (
                        remaining_amount
                        / pis_amount
                    )
                    * 100,
                    2,
                )

                remaining_amount = 0

            current_percentage = flt(
                pis.percentage_paid,
                2,
            )

            if (
                pis.payment_status != payment_status
                or current_percentage != percentage_paid
            ):
                frappe.db.set_value(
                    "Payment Intimation Slip",
                    pis.name,
                    {
                        "payment_status": payment_status,
                        "percentage_paid": percentage_paid,
                    },
                    update_modified=False,
                )

                updated_count += 1
                po_updated_count += 1

        purchase_order_details.append(
            {
                "purchase_order": purchase_order,
                "purchase_invoices": pi_names,
                "submitted_pis": len(pis_records),
                "direct_payment_amount": direct_payment_total,
                "linked_voucher_nos": list(linked_voucher_nos),
                "matched_unallocated_details": (
                    unreconciled_details["matched_details"]
                ),
                "matched_unallocated_total": (
                    unreconciled_details["matched_total"]
                ),
                "unmatched_unreconciled_details": (
                    unreconciled_details["unmatched_details"]
                ),
                "unmatched_unreconciled_total": (
                    unreconciled_details["unmatched_total"]
                ),
                "total_payment_considered": total_payment,
                "updated_pis": po_updated_count,
                "remaining_payment_after_fifo": remaining_amount,
            }
        )

    return {
        "submitted_pis": len(pis_rows),
        "purchase_orders": len(purchase_orders),
        "updated_pis": updated_count,
        "skipped_without_purchase_order": (
            skipped_without_purchase_order
        ),
        "direct_payment_entry_amount": (
            total_direct_payment
        ),
        "matched_payment_entry_unallocated_amount": (
            total_matched_unallocated
        ),
        "unmatched_unreconciled_amount": (
            total_unmatched_unreconciled
        ),
        "total_payment_considered": (
            total_direct_payment
            + total_matched_unallocated
            + total_unmatched_unreconciled
        ),
        "purchase_order_details": purchase_order_details,
    }