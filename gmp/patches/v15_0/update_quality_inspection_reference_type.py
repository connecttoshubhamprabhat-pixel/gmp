import frappe


def execute():
    options = """
Purchase Receipt
Purchase Invoice
Purchase Order
Subcontracting Receipt
Delivery Note
Sales Invoice
Stock Entry
Job Card
""".strip()

    frappe.db.set_value(
        "DocField",
        {
            "parent": "Quality Inspection",
            "fieldname": "reference_type",
        },
        "options",
        options,
        update_modified=False,
    )

    frappe.clear_cache(doctype="Quality Inspection")

    print("Quality Inspection Reference Type options updated successfully.")