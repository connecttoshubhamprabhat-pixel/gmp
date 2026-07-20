#### "gmp.gmp_machine.set_up.item__update_after_migrate.execute_after_migrate"

import frappe



def execute_after_migrate():
    frappe.db.sql("""
        UPDATE `tabItem`
        SET inspection_required_before_purchase = 1
        WHERE disabled = 0
          AND inspection_required_before_purchase = 0
    """)

    frappe.db.commit()


