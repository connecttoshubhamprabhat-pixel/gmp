# # Copyright (c) 2026, gmp and contributors
# # For license information, please see license.txt

# # import frappe


# def execute(filters=None):
# 	columns, data = [], []
# 	return columns, data











# Copyright (c) 2026, gmp and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from datetime import timedelta


def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data


def get_columns(filters):
	columns = []

	# Hidden field for Dynamic Link
	columns.append({
		"fieldname": "doctype",
		"label": "DocType",
		"fieldtype": "Data",
		"hidden": 1
	})

	current_date = getdate(filters.get("from_date"))
	end_date = getdate(filters.get("to_date"))

	while current_date <= end_date:
		columns.append({
			"label": current_date.strftime("%d-%m-%Y"),
			"fieldname": current_date.strftime("%Y_%m_%d"),
			"fieldtype": "Dynamic Link",
			"options": "doctype",
			"width": 180
		})

		current_date += timedelta(days=1)

	return columns


def get_data(filters):
	comments = frappe.db.sql("""
		SELECT
			c.reference_name,
			DATE(c.creation) AS approved_date
		FROM `tabComment` c
		INNER JOIN `tabPurchase Order` po
			ON po.name = c.reference_name
		WHERE
			c.comment_type = 'Workflow'
			AND c.reference_doctype = 'Purchase Order'
			AND c.content = 'Approved'
			AND po.docstatus != 2
			AND DATE(c.creation) BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY c.creation
	""", filters, as_dict=True)

	date_wise_po = {}

	for d in comments:
		date_key = str(d.approved_date)

		if date_key not in date_wise_po:
			date_wise_po[date_key] = []

		date_wise_po[date_key].append(d.reference_name)

	max_rows = max((len(v) for v in date_wise_po.values()), default=0)

	data = []

	date_list = []

	current_date = getdate(filters.get("from_date"))
	end_date = getdate(filters.get("to_date"))

	while current_date <= end_date:
		date_list.append(current_date)
		current_date += timedelta(days=1)

	for i in range(max_rows):
		row = {
			"doctype": "Purchase Order"
		}

		for dt in date_list:
			fieldname = dt.strftime("%Y_%m_%d")
			date_key = str(dt)

			if date_key in date_wise_po and len(date_wise_po[date_key]) > i:
				row[fieldname] = date_wise_po[date_key][i]
			else:
				row[fieldname] = ""

		data.append(row)

	return data