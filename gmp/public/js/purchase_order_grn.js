frappe.ui.form.on("Purchase Order", {
    refresh: function(frm) {
        setTimeout(() => {
            if (frm.doc.docstatus === 1 && (frm.doc.per_received || 0) < 100) {
                frm.add_custom_button(
                    __("Good Receipt Note"),
                    function() {
                        frappe.new_doc("Good Receipt Note", {
                            purchase_order: frm.doc.name
                        });
                    },
                    __("Create")
                );
            }
        }, 100);
    },
});


