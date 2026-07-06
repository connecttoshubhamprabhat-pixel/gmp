import frappe
from frappe.utils import flt

def validate(self,method):
    idx_value_as_per_subitem(self)

def idx_value_as_per_subitem(self):
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

@frappe.whitelist()
def get_tech_specs(item_code = None ):
    if(item_code):
        data = frappe.get_doc("Item", item_code)
        if data.specification:
            message = ''
            for row in data.specification:
                message = message + table_content(row)
            final_message = header() + message + """</tbody></table></div>"""

            return final_message

def header():
    message = """
    <style>
            .tbspace>tbody>tr>td {
        padding: 0 2px 0 2px !important;
        margin: 0 !important;
        border-spacing: 0 !important;
        }
    </style>
    <div>
        <table border="1" cellspacing="0" cellpadding="0" width="100%" class="tbspace">
            <tbody>
                """
    return message

def table_content(row):
    if row.separate:
        message = """</tbody></table></div>
        <div>
            <p align="center" style="font-size:11px;"><b><u> {0} </u></b></p>
            <p align="justify" style="font-size:11px;"> {1} </p>
                <table border="1" cellspacing="0" cellpadding="0" width="100%" class="tbspace">
            <tbody>""".format(row.specification or "",row.description or "")
        return message
    elif row.bold:
        message = """<tr align="left">
                <td width="35%"><b> {0} </b></td>
                <td valign="top"><b> {1} </b></td>
            </tr>""".format(row.specification or "", row.value)
        return message
    else:
        message = """<tr align="left">
                <td width="35%"> {0} </td>
                <td valign="top"> {1} </td>
            </tr>""".format(row.specification or "", row.value)
        return message