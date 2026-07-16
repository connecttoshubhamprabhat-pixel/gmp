frappe.ui.form.on("Payment Intimation Slip", {
    refresh(frm) {
        frm.add_custom_button(__("Update Payment Status"), function () {

            frappe.call({
                method: "gmp.gmp_machine.cron_job.pis_payment_status.update_submitted_pis_payment_status",
                freeze: true,
                freeze_message: __("Updating Payment Status..."),
                callback: function(r) {
                    frappe.show_alert({
                        message: __("Payment Status Updated Successfully"),
                        indicator: "green"
                    });

                    frm.reload_doc();
                },
                error: function(err) {
                    frappe.msgprint({
                        title: __("Error"),
                        indicator: "red",
                        message: __("Failed to update Payment Status.")
                    });
                    console.error(err);
                }
            });

        }, __("Tools"));
    }
});













async function update_po_balance_amount(frm) {
    if (!frm.doc.purchase_order || !frm.doc.po_original_amount) {
        await frm.set_value("po_balance_amount", 0);
        return 0;
    }

    let filters = {
        purchase_order: frm.doc.purchase_order,
        docstatus: 1
    };

    // Only consider PIS created before the current document
    if (!frm.is_new() && frm.doc.creation) {
        filters.creation = ["<", frm.doc.creation];
    }

    try {
        const result = await frappe.db.get_list("Payment Intimation Slip", {
            filters: filters,
            fields: ["payment_amount"],
            limit: 0
        });

        let previous_payment = 0;

        (result || []).forEach(row => {
            previous_payment += flt(row.payment_amount);
        });

        let balance = flt(frm.doc.po_original_amount) -
            (previous_payment + flt(frm.doc.payment_amount));

        // Set exact value (can be negative)
        await frm.set_value("po_balance_amount", balance);

        return balance;

    } catch (err) {
        console.error(err);
        frappe.msgprint(__("Unable to calculate PO Balance Amount."));
        return 0;
    }
}

frappe.ui.form.on("Payment Intimation Slip", {
    refresh(frm) {
        update_po_balance_amount(frm);
    },

    async validate(frm) {
        const balance = await update_po_balance_amount(frm);

        // Prevent save if negative
        // if (flt(balance) < 0) {
        //     frappe.throw(__(
        //         "Payment Amount exceeds the available PO Balance Amount."
        //     ));
        // }
    },

    purchase_order(frm) {
        update_po_balance_amount(frm);
    },

    payment_amount(frm) {
        update_po_balance_amount(frm);
    },

    po_original_amount(frm) {
        update_po_balance_amount(frm);
    }
});