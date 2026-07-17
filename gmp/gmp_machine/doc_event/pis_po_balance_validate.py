##########################################################################################
import frappe
from frappe.utils import flt


def update_po_balance_amount(doc, method=None):
    if not doc.purchase_order or not doc.po_original_amount:
        doc.po_balance_amount = 0
        return

    previous_pis = frappe.get_all(
        "Payment Intimation Slip",
        filters={
            "purchase_order": doc.purchase_order,
            "docstatus": 1,
            "creation": ["<", doc.creation or "9999-12-31 23:59:59"]
        },
        fields=["name", "payment_amount"],
        order_by="creation asc"
    )

    previous_payment = sum(flt(d.payment_amount) for d in previous_pis)

    current_payment = flt(doc.payment_amount)
    po_original_amount = flt(doc.po_original_amount)

    balance = po_original_amount - (previous_payment + current_payment)

    # Update balance on the document
    doc.po_balance_amount = balance

    # Allow overpayment up to ₹1.00 (rounding tolerance)
    tolerance = 1.0

    if balance < -tolerance:

        actual_exceeded = abs(balance)
        exceeded = actual_exceeded - tolerance

        rows = ""

        for d in previous_pis:
            rows += f"""
                <tr>
                    <td>
                        <a href="/app/payment-intimation-slip/{d.name}"
                           target="_blank"
                           rel="noopener noreferrer"
                           style="font-weight:600; text-decoration:underline;">
                            {d.name}
                        </a>
                    </td>
                    <td style="text-align:right;">
                        {frappe.format_value(
                            d.payment_amount,
                            {"fieldtype": "Currency", "options": getattr(doc, "currency", None)}
                        )}
                    </td>
                </tr>
            """

        if not rows:
            rows = """
                <tr>
                    <td colspan="2" style="text-align:center;">
                        No Previous Submitted Payment Intimation Slip Found
                    </td>
                </tr>
            """

        currency_options = {
            "fieldtype": "Currency",
            "options": getattr(doc, "currency", None)
        }

        frappe.throw(
            f"""
            <h3 style="color:#d9534f;margin-bottom:15px;">
                Payment Amount exceeds the allowed PO Balance tolerance.
            </h3>

            <p>
                A tolerance of <b>{frappe.format_value(tolerance, currency_options)}</b>
                is allowed to account for minor rounding differences.
            </p>

            <table class="table table-bordered">
                <tbody>
                    <tr>
                        <th style="width:45%;">PO Original Amount (A)</th>
                        <td>{frappe.format_value(po_original_amount, currency_options)}</td>
                    </tr>

                    <tr>
                        <th>Previous Paid Amount (B)</th>
                        <td>{frappe.format_value(previous_payment, currency_options)}</td>
                    </tr>

                    <tr>
                        <th>Current Payment (C)</th>
                        <td>{frappe.format_value(current_payment, currency_options)}</td>
                    </tr>

                    <tr>
                        <th>Allowed Tolerance</th>
                        <td>{frappe.format_value(tolerance, currency_options)}</td>
                    </tr>

                    <tr>
                        <th>Actual Excess ((B + C) − A)</th>
                        <td>{frappe.format_value(actual_exceeded, currency_options)}</td>
                    </tr>

                    <tr style="background:#ffeaea;font-weight:bold;color:#d9534f;">
                        <th>Excess Beyond Tolerance</th>
                        <td>{frappe.format_value(exceeded, currency_options)}</td>
                    </tr>
                </tbody>
            </table>

            <br>

            <h4>Previous Submitted Payment Intimation Slips</h4>

            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>PIS ID</th>
                        <th style="text-align:right;">Paid Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>

            <div style="margin-top:12px;padding:10px;background:#f8f9fa;border-radius:4px;">
                <b>Note:</b> Overpayment up to <b>{frappe.format_value(tolerance, currency_options)}</b> is allowed for rounding adjustments.
                <br>
                Click on a <b>PIS ID</b> to open it in a new browser tab.
            </div>
            """,
            title="Payment Limit Exceeded",
        )
################      gmp.gmp_machine.doc_event.pis_po_balance_validate.update_po_balance_amount
##########################################################################################










##########################################################################################
################      gmp.gmp_machine.doc_event.pis_po_balance_validate.validate_single_draft_pis

import frappe
from frappe.utils import format_datetime


def validate_single_draft_pis(doc, method=None):
    if not doc.purchase_order:
        return

    draft_pis = frappe.get_all(
        "Payment Intimation Slip",
        filters={
            "purchase_order": doc.purchase_order,
            "docstatus": 0,
            "name": ["!=", doc.name]
        },
        fields=["name", "owner", "modified"],
        limit=1
    )

    if not draft_pis:
        return

    draft = draft_pis[0]

    frappe.throw(
        f"""
        <h3 style="color:#d9534f;">
            Draft Payment Intimation Slip Already Exists
            Do not allowed multiple Draft PIS agasint the same PO at same time.
        </h3>

        <p>
            A Draft <b>Payment Intimation Slip</b> already exists for this
            <b>Purchase Order</b>.
        </p>

        <table class="table table-bordered">
            <tbody>
                <tr>
                    <th style="width:35%;">Purchase Order</th>
                    <td>{doc.purchase_order}</td>
                </tr>
                <tr>
                    <th>Draft PIS</th>
                    <td>
                        <a href="/app/payment-intimation-slip/{draft.name}"
                           target="_blank"
                           rel="noopener noreferrer"
                           style="font-weight:600;text-decoration:underline;">
                            {draft.name}
                        </a>
                    </td>
                </tr>
                <tr>
                    <th>Owner</th>
                    <td>{draft.owner}</td>
                </tr>
                <tr>
                    <th>Last Modified</th>
                    <td>{format_datetime(draft.modified)}</td>
                </tr>
            </tbody>
        </table>

        <div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:4px;">
            Please submit or cancel the existing Draft Payment Intimation Slip before creating a new one.
        </div>
        """,
        title="Draft Payment Intimation Slip Exists"
    )

##########################################################################################










##########################################################################################

import frappe
from frappe.utils import flt


def update_grand_totals(doc, method=None):
    # Mandatory Posting Date
    if not doc.posting_date:
        frappe.throw("Posting Date is mandatory.")

    doc.grand_basic_material_value = 0
    doc.grand_total_transport = 0
    doc.grand_total_packing = 0
    doc.grand_total_other_charges = 0
    doc.grand_total_material = 0
    doc.grand_gst_total = 0
    doc.grand_grand_total_material = 0

    for row in doc.material_details:
        doc.grand_basic_material_value += flt(row.basic_material_value)
        doc.grand_total_transport += flt(row.transport)
        doc.grand_total_packing += flt(row.packing)
        doc.grand_total_other_charges += flt(row.other_charges)
        doc.grand_total_material += flt(row.total_material)
        doc.grand_gst_total += flt(row.gst_amount)
        doc.grand_grand_total_material += flt(row.grand_total_material)

#################  gmp.gmp_machine.doc_event.pis_po_balance_validate.update_grand_totals
##########################################################################################