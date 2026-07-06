frappe.ui.form.on("Sales Order", {
	validate: function(frm){
		frm.doc.items.forEach(function (d){
			if(d.item_code){
				frappe.call({
					method: "gmp.gmp_machine.doc_event.sales_order.get_tech_specs",
					args: {
						item_code: d.item_code
					},
					callback: function(r) {
						frappe.model.set_value(d.doctype, d.name, "technical_specifications", r.message);
					}
				})
			}
		})
	}
})