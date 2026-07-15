// frappe.ui.form.on("Payment Entry", {
//     custom_get_pis_paid_amount: function(frm) {
//         calculate_pis_paid_amount(frm);
//     }
// });

// function calculate_pis_paid_amount(frm) {
//     if (frm.doc.docstatus !== 0) {
//         frappe.msgprint(__("This action can only be performed on a Draft Payment Entry."));
//         return;
//     }

//     let references = frm.doc.references || [];

//     if (references.length === 0) {
//         frappe.msgprint(__("No reference row found."));
//         return;
//     }

//     // Multiple rows present -> clear all, don't calculate
//     if (references.length > 1) {
//         frm.clear_table("references");
//         frm.refresh_field("references");
//         frappe.msgprint(__("Multiple reference rows found — all rows cleared. Keep only a single Purchase Order row."));
//         return;
//     }

//     // Only one row present - always check the first row
//     let first_row = references[0];

//     if (first_row.reference_doctype === "Purchase Invoice") {
//         // Purchase Invoice reference -> just clear the row, no calculation
//         frm.clear_table("references");
//         frm.refresh_field("references");
//         frappe.msgprint(__("Purchase Invoice reference cleared. Please set a Purchase Order reference instead."));
//         return;
//     }

//     if (first_row.reference_doctype !== "Purchase Order") {
//         frappe.msgprint(__("Reference row must be of type Purchase Order."));
//         return;
//     }

//     // Proceed with calculation only when the single row is Purchase Order
//     frappe.call({
//         method: "gmp.gmp_machine.api.payment_entry_pis.calculate_pis_paid_amount",
//         args: {
//             payment_entry: frm.doc.name,
//             purchase_order: first_row.reference_name
//         },
//         freeze: true,
//         freeze_message: __("Calculating PIS paid amount..."),
//         callback: function(r) {
//             if (!r.message) {
//                 frappe.msgprint(__("Could not calculate PIS paid amount for this Purchase Order."));
//                 return;
//             }

//             let data = r.message;

//             frm.set_value("custom_pis_paid_amount", data.remaining);
//             frm.set_value("paid_amount", data.remaining);

//             frappe.model.set_value(first_row.doctype, first_row.name, "allocated_amount", data.remaining);

//             frm.refresh_field("references");
//             frm.refresh_field("custom_pis_paid_amount");
//             frm.refresh_field("paid_amount");

//             frappe.msgprint(__("PIS paid amount calculated and updated."));
//         },
//         error: function() {
//             frappe.msgprint(__("Failed to calculate PIS paid amount. Please check the error log."));
//         }
//     });
// }
























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

    let unreconciled_html = "";
    if (data.unreconciled_count > 0) {
        unreconciled_html = `
            <p style="color:#d9822b;">
                ${__("Note: {0} Unreconciled Payment record(s) found totalling {1}. This amount was NOT deducted from the remaining balance.",
                    [data.unreconciled_count, format_currency(data.unreconciled_total)])}
            </p>`;
    } else {
        unreconciled_html = `<p>${__("No Unreconciled Payment Entries found against this Purchase Order / linked Purchase Invoices.")}</p>`;
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
        <table class="table table-bordered">
            <tr><td>${__("Purchase Order")}</td><td style="text-align:right">${data.purchase_order}</td></tr>
            <tr><td>${__("Total PIS Amount")}</td><td style="text-align:right">${format_currency(data.total_pis_amount)}</td></tr>
            <tr><td>${__("Payment Entry against PO")}</td><td style="text-align:right">${format_currency(data.po_payment_entry_amount)}</td></tr>
        </table>
        <p><strong>${__("Payment Entry against each linked Purchase Invoice")}:</strong></p>
        <table class="table table-bordered">
            ${pi_rows_html}
        </table>
        ${unreconciled_html}
        ${remaining_html}
    `;

    frappe.msgprint({
        title: __("PIS Payment Calculation Summary"),
        message: message,
        indicator: flt(data.remaining) === 0 ? "green" : "blue"
    });
}







