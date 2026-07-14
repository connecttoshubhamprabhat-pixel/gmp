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


# def validate_delete_po(self, method):
# 	"""
# 	Before Purchase Order is deleted, check if its name is present
# 	in 'purchase_order_duplicate' of any Payment Intimation Slip.
# 	If found, block the deletion.
# 	"""
# 	linked = frappe.db.sql("""
# 		SELECT name FROM `tabPayment Intimation Slip`
# 		WHERE purchase_order_duplicate = %s
# 	""", (self.name,))

# 	if linked:
# 		frappe.throw(
# 			"Cannot delete Purchase Order {0}, because it's linked with Payment Intimation Slip {1}".format(
# 				frappe.bold(self.name), frappe.bold(linked[0][0])
# 			)
# 		)
		








import frappe

def validate_delete_po(self, method):
	"""
	Prevent deletion of an original PO if linked with Payment Intimation Slip.
	If an amended PO is being deleted, move the link back to the original PO.
	"""

	if not self.amended_from:
		linked = frappe.get_all(
			"Payment Intimation Slip",
			filters={"purchase_order_duplicate": self.name},
			pluck="name"
		)

		if linked:
			frappe.throw(
				"Cannot delete Purchase Order {0} because it is linked with Payment Intimation Slip {1}.".format(
					frappe.bold(self.name),
					frappe.bold(", ".join(linked))
				)
			)

	else:
		frappe.db.sql("""
			UPDATE `tabPayment Intimation Slip`
			SET
				purchase_order = %s,
				purchase_order_duplicate = %s
			WHERE purchase_order = %s
		""", (
			self.amended_from,
			self.amended_from,
			self.name
		))













# def on_amend_po(self, method):
# 	"""
# 	Code Type 4 (Amend)
# 	When a Purchase Order is amended, a new PO doc is created with
# 	'amended_from' pointing to the old (cancelled) PO name.
# 	Check if that old name exists in any Payment Intimation Slip's
# 	'purchase_order' or 'purchase_order_duplicate' field.
# 	If found, update 'purchase_order' with the new amended PO name.
# 	"""
# 	if not self.amended_from:
# 		return

# 	linked = frappe.db.sql("""
# 		SELECT name FROM `tabPayment Intimation Slip`
# 		WHERE purchase_order_duplicate = %s OR purchase_order = %s
# 	""", (self.amended_from, self.amended_from))

# 	if not linked:
# 		return

# 	frappe.db.sql("""
# 		UPDATE `tabPayment Intimation Slip`
# 		SET purchase_order = %s,
# 		WHERE purchase_order_duplicate = %s OR purchase_order = %s
# 	""", (self.name, self.amended_from, self.amended_from))












import frappe

def on_amend_po(self, method):
	"""
	When a Purchase Order is amended:
	- purchase_order -> New amended PO
	- purchase_order_duplicate -> Original cancelled PO (amended_from)
	"""

	if not self.amended_from:
		return

	frappe.db.sql("""
		UPDATE `tabPayment Intimation Slip`
		SET
			purchase_order = %s,
			purchase_order_duplicate = %s
		WHERE purchase_order = %s
		   OR purchase_order_duplicate = %s
	""", (
		self.name,
		self.amended_from,
		self.amended_from,
		self.amended_from
	))










# ########### gmp.gmp_machine.doc_event.po_pis_events.on_cancel_po
# ########### gmp.gmp_machine.doc_event.po_pis_events.after_rename_po
# ########### gmp.gmp_machine.doc_event.po_pis_events.validate_delete_po
# ########### gmp.gmp_machine.doc_event.po_pis_events.on_amend_po


