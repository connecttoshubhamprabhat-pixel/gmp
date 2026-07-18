# Server Script: Prevent multiple Purchase Orders in Purchase Invoice
# Doctype: Purchase Invoice
# Type: Before Save
# Enabled: Yes

import frappe

def validate_multiple_po(doc, method):
    # Collect all linked Purchase Orders from items
    purchase_orders = set()
    for item in doc.items:
        if item.purchase_order:
            purchase_orders.add(item.purchase_order)

    # If more than one unique Purchase Order is found, throw error
    if len(purchase_orders) > 1:
        frappe.throw("You cannot create a Purchase Invoice against multiple Purchase Orders. Please create separate invoices.")


############### gmp.gmp_machine.doc_event.purchae_invoice_po_validate.pvalidate_multiple_po



    # "Purchase Invoice": {
    #     "before_save": "gmp.gmp_machine.doc_event.purchae_invoice_po_validate.validate_multiple_po",
    # },