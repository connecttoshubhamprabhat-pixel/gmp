import frappe
from frappe.utils import getdate, today, cint

def set_custom_name(doc, method=None):
	today_date = getdate(today())

	if today_date.month >= 4:
		start_year = today_date.year
	else:
		start_year = today_date.year - 1

	end_year = start_year + 1
	fy = str(start_year) + "-" + str(end_year)[-2:]

	series_key = "OS/" + fy

	result = frappe.db.sql(
		"select current from `tabSeries` where name = %s",
		(series_key,)
	)

	if not result:
		next_val = 1
		frappe.db.sql(
			"insert into `tabSeries` (name, current) values (%s, %s)",
			(series_key, next_val)
		)
	else:
		next_val = cint(result[0][0]) + 1
		frappe.db.sql(
			"update `tabSeries` set current = %s where name = %s",
			(next_val, series_key)
		)

	padded_val = str(next_val).zfill(4)
	doc.name = "OS/" + padded_val + "/" + fy + "/" + doc.title_name





############ gmp.gmp_machine.doc_event.os_auto_name.set_custom_name