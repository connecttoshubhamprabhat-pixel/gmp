// // Copyright (c) 2026, gmp and contributors
// // For license information, please see license.txt

// frappe.query_reports["Purchase Order Approval Tracker"] = {
// 	"filters": [

// 	]
// };



frappe.query_reports["Purchase Order Approval Tracker"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_start()
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_end()
		}
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (
			data &&
			column.fieldname.match(/^\d{4}_\d{2}_\d{2}$/) &&
			data[column.fieldname]
		) {
			return `<a href="/app/purchase-order/${data[column.fieldname]}"
				target="_blank">
				${data[column.fieldname]}
			</a>`;
		}

		return value;
	}
};