frappe.ui.form.on("Payment Entry", {
    custom_get_pis_paid_amount: function(frm) {
        calculate_pis_paid_amount(frm);
    }
});

function calculate_pis_paid_amount(frm) {
    if (frm.doc.docstatus !== 0) {
        frappe.msgprint(__("This action can only be performed on a Draft Payment Entry."));
        return;
    }

    let references = frm.doc.references || [];

    if (references.length === 0) {
        frappe.msgprint(__("No reference row found."));
        return;
    }

    // Multiple rows present -> clear all, don't calculate
    if (references.length > 1) {
        frm.clear_table("references");
        frm.refresh_field("references");
        frappe.msgprint(__("Multiple reference rows found — all rows cleared. Keep only a single Purchase Order row."));
        return;
    }

    // Only one row present - always check the first row
    let first_row = references[0];

    if (first_row.reference_doctype === "Purchase Invoice") {
        // Purchase Invoice reference -> just clear the row, no calculation
        frm.clear_table("references");
        frm.refresh_field("references");
        frappe.msgprint(__("Purchase Invoice reference cleared. Please set a Purchase Order reference instead."));
        return;
    }

    if (first_row.reference_doctype !== "Purchase Order") {
        frappe.msgprint(__("Reference row must be of type Purchase Order."));
        return;
    }

    // Proceed with calculation only when the single row is Purchase Order
    frappe.call({
        method: "gmp.gmp_machine.api.payment_entry_pis.calculate_pis_paid_amount",
        args: {
            payment_entry: frm.doc.name,
            purchase_order: first_row.reference_name
        },
        freeze: true,
        freeze_message: __("Calculating PIS paid amount..."),
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint(__("Could not calculate PIS paid amount for this Purchase Order."));
                return;
            }

            let data = r.message;

            frm.set_value("custom_pis_paid_amount", data.remaining);
            frm.set_value("paid_amount", data.remaining);

            frappe.model.set_value(first_row.doctype, first_row.name, "allocated_amount", data.remaining);

            frm.refresh_field("references");
            frm.refresh_field("custom_pis_paid_amount");
            frm.refresh_field("paid_amount");

            show_calculation_summary(data);
        },
        error: function() {
            frappe.msgprint(__("Failed to calculate PIS paid amount. Please check the error log."));
        }
    });
}

function show_calculation_summary(data) {
    // 1. PO breakdown
    let po_table = `
        <table class="table table-bordered">
            <tr><th>${__("Reference")}</th><th style="text-align:right">${__("Amount")}</th></tr>
            <tr>
                <td>${data.purchase_order}</td>
                <td style="text-align:right">${format_currency(data.po_payment_entry_amount)}</td>
            </tr>
        </table>`;

    // 2. PI breakdown
    let pi_rows_html = "";
    (data.pi_payment_entry_details || []).forEach(function(row) {
        pi_rows_html += `<tr>
            <td>${row.purchase_invoice}</td>
            <td style="text-align:right">${format_currency(row.amount)}</td>
        </tr>`;
    });
    if (!pi_rows_html) {
        pi_rows_html = `<tr><td colspan="2">${__("No Payment Entry found against linked Purchase Invoices")}</td></tr>`;
    }
    let pi_table = `
        <table class="table table-bordered">
            <tr><th>${__("Purchase Invoice")}</th><th style="text-align:right">${__("Amount")}</th></tr>
            ${pi_rows_html}
        </table>`;

    // Unallocated amount - Payment Entries found via direct PO/PI references
    let pe_unallocated_rows_html = "";
    (data.pe_unallocated_details || []).forEach(function(row) {
        pe_unallocated_rows_html += `<tr>
            <td>${row.name}</td>
            <td style="text-align:right">${format_currency(row.unallocated_amount)}</td>
        </tr>`;
    });
    if (!pe_unallocated_rows_html) {
        pe_unallocated_rows_html = `<tr><td colspan="2">${__("No Payment Entry found")}</td></tr>`;
    }
    let pe_unallocated_table = `
        <table class="table table-bordered">
            <tr><th>${__("Payment Entry")}</th><th style="text-align:right">${__("Unallocated Amount")}</th></tr>
            ${pe_unallocated_rows_html}
        </table>`;

    // Note + table: Unreconciled voucher_nos already linked via PO/PI directly -
    // shown with their Payment Entry's unallocated_amount instead
    let excluded_html = "";
    if ((data.unreconciled_matched_details || []).length > 0) {
        let excluded_rows_html = "";
        data.unreconciled_matched_details.forEach(function(row) {
            excluded_rows_html += `<tr>
                <td>${row.voucher_no}</td>
                <td style="text-align:right">${format_currency(row.unallocated_amount)}</td>
            </tr>`;
        });
        excluded_html = `
            <p style="color:#d9822b; margin-top:10px;">
                ${__("Note: the following Unreconciled Payment record(s), totalling {0}, were found but this Payment Entry is already considered — its unallocated_amount is used instead.",
                    [format_currency(data.unreconciled_matched_total)])}
            </p>
            <table class="table table-bordered">
                <tr><th>${__("Voucher No")}</th><th style="text-align:right">${__("Unallocated Amount")}</th></tr>
                ${excluded_rows_html}
            </table>`;
    }

    // Unreconciled voucher_nos NOT linked to any PO/PI - max row per voucher_no
    let unmatched_html = "";
    if ((data.unreconciled_unmatched_details || []).length > 0) {
        let unmatched_rows_html = "";
        data.unreconciled_unmatched_details.forEach(function(row) {
            unmatched_rows_html += `<tr>
                <td>${row.voucher_no}</td>
                <td style="text-align:right">${format_currency(row.amount)}</td>
            </tr>`;
        });
        unmatched_html = `
            <p style="margin-top:10px;">
                ${__("Unreconciled Payment Entries not linked to any Purchase Order/Invoice — max allocated amount per voucher considered, totalling {0}.",
                    [format_currency(data.unreconciled_unmatched_total)])}
            </p>
            <table class="table table-bordered">
                <tr><th>${__("Voucher No")}</th><th style="text-align:right">${__("Max Allocated Amount")}</th></tr>
                ${unmatched_rows_html}
            </table>`;
    }

    let remaining_html = "";
    if (flt(data.remaining) === 0) {
        remaining_html = `<p style="color:green; font-weight:bold;">${__("Fully paid — remaining PIS amount is 0.")}</p>`;
    } else if (flt(data.remaining) < 0) {
        remaining_html = `<p style="color:red; font-weight:bold;">${__("Excess paid — remaining amount is negative: {0}", [format_currency(data.remaining)])}</p>`;
    } else {
        remaining_html = `<p style="font-weight:bold;">${__("Remaining PIS amount: {0}", [format_currency(data.remaining)])}</p>`;
    }

    let message = `
        <p><strong>${__("Total PIS Amount")}:</strong> ${format_currency(data.total_pis_amount)}</p>

        <p><strong>${__("1. Payment Entry against Purchase Order")}</strong></p>
        ${po_table}

        <p><strong>${__("2. Payment Entry against linked Purchase Invoices")}</strong></p>
        ${pi_table}

        <p><strong>${__("Unallocated Amount (Payment Entries above)")}</strong></p>
        ${pe_unallocated_table}

        ${excluded_html}
        ${unmatched_html}

        <hr/>
        <p style="font-size:14px;"><strong>${__("Total Paid (PO + PI + Unallocated)")}:</strong> ${format_currency(data.total_paid)}</p>
        ${remaining_html}
    `;

    frappe.msgprint({
        title: __("PIS Payment Calculation Summary"),
        message: message,
        indicator: flt(data.remaining) === 0 ? "green" : "blue"
    });
}