import frappe
from frappe.utils import flt

def validate(self,method):
    idx_value_as_per_subitem(self)

def  idx_value_as_per_subitem(self):
    count = 0
    sub_count = 1
    for row in self.items:
        if not row.is_subitem:
            count += 1
            row.index = count
            sub_count = 1
        elif row.is_subitem == 1:
            row.index = row.idx
            row.index = f"{count}.{sub_count}"
            sub_count += 1
