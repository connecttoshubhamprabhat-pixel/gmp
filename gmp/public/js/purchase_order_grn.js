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

// Extend ERPNext's core quality-inspection controller behavior to Purchase Order.
// These methods are intentionally scoped to the Purchase Order cscript instead of
// replacing erpnext.TransactionController globally.
cur_frm.cscript.setup_quality_inspection = function () {
    if (![
        "Delivery Note",
        "Sales Invoice",
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Subcontracting Receipt",
    ].includes(this.frm.doc.doctype)) {
        return;
    }

    let show_qc_button = true;
    if (["Sales Invoice", "Purchase Invoice"].includes(this.frm.doc.doctype)) {
        show_qc_button = this.frm.doc.update_stock;
    }

    const me = this;
    if (
        !this.frm.is_new()
        && this.frm.doc.docstatus < 2
        && frappe.model.can_create("Quality Inspection")
        && show_qc_button
    ) {
        this.frm.add_custom_button(
            __("Quality Inspection(s)"),
            () => me.make_quality_inspection(),
            __("Create")
        );
    }

    const incoming_doctypes = [
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Subcontracting Receipt",
    ];
    const incoming_purposes = ["Manufacture", "Material Receipt"];
    const inspection_type =
        incoming_doctypes.includes(this.frm.doc.doctype)
        || (
            this.frm.doc.doctype === "Stock Entry"
            && incoming_purposes.includes(this.frm.doc.purpose)
        )
            ? "Incoming"
            : "Outgoing";

    const quality_inspection_field = this.frm.get_docfield("items", "quality_inspection");
    if (!quality_inspection_field) {
        return;
    }

    quality_inspection_field.get_route_options_for_new_doc = function (row) {
        if (me.frm.is_new()) return {};

        return {
            inspection_type,
            reference_type: me.frm.doc.doctype,
            reference_name: me.frm.doc.name,
            child_row_reference: row.doc.name,
            item_code: me.frm.doc.is_subcontracted ? row.doc.fg_item : row.doc.item_code,
            description: row.doc.description,
            item_serial_no: row.doc.serial_no ? row.doc.serial_no.split("\n")[0] : null,
            batch_no: row.doc.batch_no,
        };
    };

    this.frm.set_query("quality_inspection", "items", function (doc, cdt, cdn) {
        const row = locals[cdt][cdn];
        return {
            filters: {
                docstatus: ["<", 2],
                inspection_type,
                reference_name: doc.name,
                item_code: me.frm.doc.is_subcontracted ? row.fg_item : row.item_code,
                child_row_reference: row.name,
            },
        };
    });
};

cur_frm.cscript.make_quality_inspection = function () {
    let data = [];
    const fields = [{
        label: "Items",
        fieldtype: "Table",
        fieldname: "items",
        cannot_add_rows: true,
        in_place_edit: true,
        data,
        get_data: () => data,
        fields: [
            { fieldtype: "Data", fieldname: "docname", hidden: true },
            {
                fieldtype: "Read Only",
                fieldname: "item_code",
                label: __("Item Code"),
                in_list_view: true,
            },
            {
                fieldtype: "Read Only",
                fieldname: "item_name",
                label: __("Item Name"),
                in_list_view: true,
            },
            {
                fieldtype: "Float",
                fieldname: "qty",
                label: __("Accepted Quantity"),
                in_list_view: true,
                read_only: true,
            },
            {
                fieldtype: "Float",
                fieldname: "sample_size",
                label: __("Sample Size"),
                reqd: true,
                in_list_view: true,
            },
            { fieldtype: "Data", fieldname: "description", hidden: true },
            { fieldtype: "Data", fieldname: "serial_no", hidden: true },
            { fieldtype: "Data", fieldname: "batch_no", hidden: true },
            { fieldtype: "Data", fieldname: "child_row_reference", hidden: true },
        ],
    }];

    const me = this;
    const incoming_doctypes = [
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Subcontracting Receipt",
    ];
    const incoming_purposes = ["Manufacture", "Material Receipt"];
    const inspection_type =
        incoming_doctypes.includes(this.frm.doc.doctype)
        || (
            this.frm.doc.doctype === "Stock Entry"
            && incoming_purposes.includes(this.frm.doc.purpose)
        )
            ? "Incoming"
            : "Outgoing";

    const dialog = new frappe.ui.Dialog({
        title: __("Select Items for Quality Inspection"),
        size: "extra-large",
        fields,
        primary_action() {
            const values = dialog.get_values();
            const selected_data = values.items.filter((item) => item?.__checked === 1);

            if (!selected_data.length) {
                frappe.msgprint(__("Please select at least one item."));
                return;
            }

            frappe.call({
                method: "erpnext.controllers.stock_controller.make_quality_inspections",
                args: {
                    company: me.frm.doc.company,
                    doctype: me.frm.doc.doctype,
                    docname: me.frm.doc.name,
                    items: selected_data,
                },
                freeze: true,
                callback(r) {
                    const inspections = r.message || [];
                    if (inspections.length === 1) {
                        frappe.set_route("Form", "Quality Inspection", inspections[0]);
                    } else if (inspections.length > 1) {
                        frappe.route_options = {
                            reference_type: me.frm.doc.doctype,
                            reference_name: me.frm.doc.name,
                        };
                        frappe.set_route("List", "Quality Inspection");
                    }
                    dialog.hide();
                },
            });
        },
        primary_action_label: __("Create"),
    });

    frappe.call({
        method: "gmp.gmp_machine.api.quality_inspection.get_purchase_order_items_for_quality_inspection",
        args: {
            docstatus: this.frm.doc.docstatus,
            items: this.frm.doc.items,
            is_subcontracted: this.frm.doc.is_subcontracted,
        },
        freeze: true,
        callback(r) {
            const eligible_items = r.message || [];
            if (!eligible_items.length) {
                const type = inspection_type === "Incoming" ? "Purchase" : "Delivery";
                const fieldname = inspection_type === "Incoming"
                    ? "Inspection Required before Purchase"
                    : "Inspection Required before Delivery";
                frappe.msgprint({
                    title: __("Quality Inspection Not Configured"),
                    message: __(
                        "Enable <b>{0}</b> on the Item master to proceed with {1} inspection.",
                        [fieldname, type]
                    ),
                });
                return;
            }

            eligible_items.forEach((item) => {
                if (me.has_inspection_required(item)) {
                    const dialog_items = dialog.fields_dict.items;
                    dialog_items.df.data.push({
                        item_code: item.item_code,
                        item_name: item.item_name,
                        qty: item.qty,
                        description: item.description,
                        serial_no: item.serial_no,
                        batch_no: item.batch_no,
                        sample_size: item.sample_quantity,
                        child_row_reference: item.name,
                    });
                    dialog_items.grid.refresh();
                }
            });

            data = dialog.fields_dict.items.df.data;
            if (!data.length) {
                frappe.msgprint(
                    __("All items in this document already have a linked Quality Inspection.")
                );
            } else {
                dialog.show();
            }
        },
    });
};
