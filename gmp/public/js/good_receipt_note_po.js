frappe.ui.form.on("Good Receipt Note", {
    setup(frm) {
        frm._po_items_loaded_for = null;
    },

    onload_post_render(frm) {
        // Disable add/delete rows every time the form renders
        frm.set_df_property("items", "cannot_add_rows", true);
        frm.set_df_property("items", "cannot_delete_all_rows", true);

        // Purchase Order filter
        frm.set_query("purchase_order", () => ({
            filters: {
                company: frm.doc.company,
                docstatus: 1
            }
        }));

        // Warehouse filter
        frm.set_query("set_warehouse", () => ({
            filters: {
                company: frm.doc.company
            }
        }));

        // Default receiver
        if (!frm.doc.received_by) {
            frm.set_value("received_by", frappe.session.user);
        }

        // Automatically fetch items when opened from Purchase Order
        frappe.after_ajax(() => {
            if (
                frm.doc.docstatus === 0 &&
                frm.doc.purchase_order &&
                (!frm.doc.items || frm.doc.items.length === 0)
            ) {
                frm.trigger("fetch_po_items");
            }
        });
    },

    purchase_order(frm) {
        if (frm.doc.purchase_order && frm.doc.docstatus === 0) {
            frm._po_items_loaded_for = null;
            frm.trigger("fetch_po_items");
        }
    },

    fetch_po_items(frm) {
        if (!frm.doc.purchase_order) return;

        if (frm._po_items_loaded_for === frm.doc.purchase_order) return;
        frm._po_items_loaded_for = frm.doc.purchase_order;

        frm.clear_table("items");
        frm.refresh_field("items");

        // First get whether the PO is subcontracted
        frappe.db.get_value(
            "Purchase Order",
            frm.doc.purchase_order,
            "is_subcontracted",
            (po) => {

                const is_subcontracted = cint(po.is_subcontracted);

                // Now fetch remaining PO items
                frappe.call({
                    method: "get_remaining_po_items",
                    args: {
                        purchase_order: frm.doc.purchase_order,
                        current_grn_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Fetching items from Purchase Order..."),

                    callback(r) {
                        const remaining_items = r.message || [];

                        if (!remaining_items.length) {
                            frappe.msgprint(__("All items from this Purchase Order are already fully received."));
                            return;
                        }

                        remaining_items.forEach(po_item => {

                            const row = frm.add_child("items");

                            Object.keys(po_item).forEach(key => {

                                if (
                                    [
                                        "doctype",
                                        "name",
                                        "parent",
                                        "parentfield",
                                        "parenttype",
                                        "idx",
                                        "creation",
                                        "modified",
                                        "modified_by",
                                        "owner",
                                        "docstatus"
                                    ].includes(key)
                                ) {
                                    return;
                                }

                                row[key] = po_item[key];
                            });

                            row.purchase_order = frm.doc.purchase_order;
                            row.purchase_order_item = po_item.name;

                            // ============================
                            // SUBCONTRACTED PO: use fg_item / fg_item_qty
                            // NON-SUBCONTRACTED PO: use item_code / qty
                            // ============================
                            if (is_subcontracted && po_item.fg_item) {
                                row.item_code = po_item.fg_item;
                                row.qty = po_item.fg_item_qty;
                            } else {
                                row.item_code = po_item.item_code;
                                row.qty = po_item.qty;
                            }

                            if (frm.doc.set_warehouse) {
                                row.warehouse = frm.doc.set_warehouse;
                            }

                            update_row_amount(frm, row);
                        });

                        frm.refresh_field("items");

                        frappe.show_alert({
                            message: __("Items loaded from Purchase Order"),
                            indicator: "green"
                        });
                    }
                });
            }
        );
    }
});

frappe.ui.form.on("Good Receipt Note Item", {
    qty: recalc_row,
    rate: recalc_row,
    base_rate: recalc_row,
    net_rate: recalc_row,
    base_net_rate: recalc_row
});

function recalc_row(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    update_row_amount(frm, row);
}

function update_row_amount(frm, row) {
    const qty = flt(row.qty);
    const rate = flt(row.rate);
    const base_rate = flt(row.base_rate);
    const net_rate = flt(row.net_rate);
    const base_net_rate = flt(row.base_net_rate);

    frappe.model.set_value(row.doctype, row.name, "amount", rate * qty);
    frappe.model.set_value(row.doctype, row.name, "base_amount", base_rate * qty);
    frappe.model.set_value(row.doctype, row.name, "net_amount", net_rate * qty);
    frappe.model.set_value(row.doctype, row.name, "base_net_amount", base_net_rate * qty);
}



//     public.js.good_receipt_note_po