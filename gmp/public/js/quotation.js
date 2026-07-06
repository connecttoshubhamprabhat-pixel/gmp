function sleep (time) {
    return new Promise((resolve) => setTimeout(resolve, time));
  }

frappe.ui.form.on("Quotation", {
    validate: function(frm){
		frm.doc.items.forEach(function (d){
			if(d.item_code){
				frappe.call({
					method: "gmp.gmp_machine.doc_event.sales_order.get_tech_specs",
					args: {
						item_code: d.item_code
					},
					callback: function(r) {
						frappe.model.set_value(d.doctype, d.name, "technical_specifications_", r.message);
					}
				})
			}
		})
	},
    conversion_rate: function (frm) {
        sleep(300).then(() => frm.doc.items.forEach(function (d) {
            frm.events.calculate_vendor_rates_and_discount(frm, d.doctype, d.name);
        }));
    },
    before_save: function (frm) {
        sleep(300).then(() => frm.doc.items.forEach(function (d) {
            frm.events.calculate_vendor_rates_and_discount(frm, d.doctype, d.name);
        }));
    },
    
    calculate_vendor_rates_and_discount(frm, cdt, cdn) {
        let d = locals[cdt][cdn];

        let rate_after_amount = flt(d.vendor_ratecompany_currency) * (1 - (flt(d.vendor__discount) / 100));
        let vendor_amount = flt(d.vendor_ratecompany_currency) * flt(d.qty);
        let discount__amount = (flt(d.vendor_ratecompany_currency) * flt(d.vendor__discount) / 100);
        let amount_after_discount = rate_after_amount * flt(d.qty);
        let percent_amount = flt(d.vendor_ratecompany_currency) * flt(d.percent) / 100;
        let rate_added = percent_amount + flt(d.vendor_ratecompany_currency);
        let rate_inr = rate_added + flt(d.packing_charges) + flt(d.transport_charges);
        let amount_company_currency = rate_inr * flt(d.qty);
        let rate_foreign_currency = rate_inr / flt(frm.doc.conversion_rate);
        let discounted_amount = rate_foreign_currency * flt(d.discounted_percent) / 100;
        let rate_discount = rate_foreign_currency - discounted_amount;
        let commission__amount = rate_discount * flt(d.commission_percentage) / 100;
        let rate = rate_discount + commission__amount;

        frappe.model.set_value(cdt, cdn, 'rate_after_amount', rate_after_amount);
        frappe.model.set_value(cdt, cdn, 'vendor_amount', vendor_amount);
        frappe.model.set_value(cdt, cdn, 'discount__amount', discount__amount);
        frappe.model.set_value(cdt, cdn, 'amount_after_discount', amount_after_discount);
        frappe.model.set_value(cdt, cdn, 'percent_amount', percent_amount);
        frappe.model.set_value(cdt, cdn, 'rate_added', rate_added);
        frappe.model.set_value(cdt, cdn, 'rate_inr', rate_inr);
        frappe.model.set_value(cdt, cdn, 'amount_company_currency', amount_company_currency);
        frappe.model.set_value(cdt, cdn, 'rate_foreign_currency', rate_foreign_currency);
        frappe.model.set_value(cdt, cdn, 'rate_discount', rate_discount);
        frappe.model.set_value(cdt, cdn, 'discounted_amount', discounted_amount);
        frappe.model.set_value(cdt, cdn, 'commission__amount', commission__amount);
        frappe.model.set_value(cdt, cdn, 'rate', rate);
    }
})


frappe.ui.form.on("Quotation Item", {
    qty: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    vendor_ratecompany_currency: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    vendor__discount: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    percent: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    packing_charges: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    transport_charges: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    discounted_percent: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    },
    commission_percentage: function (frm, cdt, cdn) {
        frm.events.calculate_vendor_rates_and_discount(frm, cdt, cdn);
    }
})
