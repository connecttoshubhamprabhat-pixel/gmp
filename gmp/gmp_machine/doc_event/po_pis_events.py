import frappe


def on_cancel_po(self, method):
	"""
	Before Purchase Order cancel completes, move its name from
	'purchase_order' to 'purchase_order_duplicate' in all linked
	Payment Intimation Slip records, and clear 'purchase_order'.
	"""
	frappe.db.sql("""
		UPDATE `tabPayment Intimation Slip`
		SET purchase_order_duplicate = purchase_order,
			purchase_order = ''
		WHERE purchase_order = %s
	""", (self.name,))


def after_rename_po(self, method, olddn, newdn, merge=False):
	"""
	After Purchase Order is renamed, update 'purchase_order_duplicate'
	in Payment Intimation Slip records that were pointing to the
	old PO name (olddn) so they now point to the new name (newdn).
	"""
	frappe.db.sql("""
		UPDATE `tabPayment Intimation Slip`
		SET purchase_order_duplicate = %s
		WHERE purchase_order_duplicate = %s
	""", (newdn, olddn))


def validate_delete_po(self, method):
	"""
	Before Purchase Order is deleted, check if its name is present
	in 'purchase_order_duplicate' of any Payment Intimation Slip.
	If found, block the deletion.
	"""
	linked = frappe.db.sql("""
		SELECT name FROM `tabPayment Intimation Slip`
		WHERE purchase_order_duplicate = %s
	""", (self.name,))

	if linked:
		frappe.throw(
			"Cannot delete Purchase Order {0}, because it's linked with Payment Intimation Slip {1}".format(
				frappe.bold(self.name), frappe.bold(linked[0][0])
			)
		)
		



########### gmp.gmp_machine.doc_event.po_pis_events.on_cancel_po
########### gmp.gmp_machine.doc_event.po_pis_events.after_rename_po
########### gmp.gmp_machine.doc_event.po_pis_events.validate_delete_po




doc_events = {
    "Purchase Order": {
        "on_cancel": "gmp.gmp_machine.doc_event.po_pis_events.on_cancel_po",
        "after_rename": "gmp.gmp_machine.doc_event.po_pis_events.after_rename_po",
        "on_trash": "gmp.gmp_machine.doc_event.po_pis_events.validate_delete_po",
    }
}