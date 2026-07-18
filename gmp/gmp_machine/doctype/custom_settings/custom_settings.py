# Copyright (c) 2026, BOM Fix and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class CustomSettings(Document):
	pass














# Copyright (c) 2015, Frappe Technologies Pvt. Ltd.
# License: GNU General Public License v3

from math import ceil
import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate
import erpnext


# =========================================================
# MAIN
# =========================================================

def reorder_item():
    if not (frappe.db.a_row_exists("Company") and frappe.db.a_row_exists("Fiscal Year")):
        return

    if cint(frappe.db.get_value("Custom Settings", None, "auto_indent")):
        return _reorder_item()


def _reorder_item():
    material_requests = {"Purchase": {}, "Transfer": {}, "Material Issue": {}, "Manufacture": {}}

    warehouse_company = frappe._dict(
        frappe.db.sql("""SELECT name, company FROM `tabWarehouse` WHERE disabled=0""")
    )

    default_company = (
        erpnext.get_default_company()
        or frappe.db.sql("""SELECT name FROM tabCompany LIMIT 1""")[0][0]
    )

    items_to_consider = get_items_for_reorder()
    if not items_to_consider:
        return

    settings = get_custom_settings()
    item_stock = get_item_warehouse_stock(items_to_consider)

    def add_to_material_request(**kwargs):
        kwargs = frappe._dict(kwargs)

        if kwargs.warehouse not in warehouse_company:
            return

        stock = flt(item_stock.get(kwargs.item_code, {}).get(kwargs.warehouse, 0))
        reorder_level = flt(kwargs.reorder_level)
        reorder_qty = flt(kwargs.reorder_qty)

        # Skip if stock is sufficient
        if stock > reorder_level:
            return

        # 🔥 Dynamic qty calculation
        if not settings.calculate_qty_dynamically:
            final_qty = reorder_qty
        else:
            pending_qty = get_pending_receiving_qty(
                kwargs.item_code,
                kwargs.warehouse,
                settings
            )
            final_qty = reorder_qty - pending_qty

        if final_qty <= 0:
            return

        company = warehouse_company.get(kwargs.warehouse) or default_company

        material_requests[kwargs.material_request_type].setdefault(company, []).append(
            {
                "item_code": kwargs.item_code,
                "warehouse": kwargs.warehouse,
                "reorder_qty": final_qty,
                "item_details": kwargs.item_details,
            }
        )

    for item_code, reorder_levels in items_to_consider.items():
        for d in reorder_levels:
            if d.has_variants:
                continue

            add_to_material_request(
                item_code=item_code,
                warehouse=d.warehouse,
                reorder_level=d.warehouse_reorder_level,
                reorder_qty=d.warehouse_reorder_qty,
                material_request_type=d.material_request_type,
                warehouse_group=d.warehouse_group,
                item_details=frappe._dict(
                    {
                        "item_code": item_code,
                        "name": item_code,
                        "item_name": d.item_name,
                        "item_group": d.item_group,
                        "brand": d.brand,
                        "description": d.description,
                        "stock_uom": d.stock_uom,
                        "purchase_uom": d.purchase_uom,
                        "lead_time_days": d.lead_time_days,
                    }
                ),
            )

    if material_requests:
        return create_material_request(material_requests)


# =========================================================
# SETTINGS
# =========================================================

def get_custom_settings():
    s = frappe.get_single("Custom Settings")

    return frappe._dict({
        "consider_draft": cint(s.consider_draft_mreq_before_mreq_raise),
        "consider_approved": cint(s.consider_approved_mreq_before_mreq_raise),
        "calculate_qty_dynamically": cint(s.calculate_qty_dynamically),

        # NEW FLAGS
        "consider_purchase": cint(s.consider_material_request_type_purchase),
        "consider_transfer": cint(s.consider_material_request_type_material_transfer),
    })


# =========================================================
# PENDING MREQ QTY
# =========================================================

def get_pending_receiving_qty(item_code, warehouse, settings):

    values = {"item_code": item_code, "warehouse": warehouse}
    conditions = []

    # Docstatus filter
    status_conditions = []
    if settings.consider_draft:
        status_conditions.append("mr.docstatus = 0")
    if settings.consider_approved:
        status_conditions.append("mr.docstatus = 1")

    if not status_conditions:
        return 0

    conditions.append("(" + " OR ".join(status_conditions) + ")")

    # Material Request Type filter
    type_conditions = []
    if settings.consider_purchase:
        type_conditions.append("mr.material_request_type = 'Purchase'")
    if settings.consider_transfer:
        type_conditions.append("mr.material_request_type = 'Material Transfer'")

    if not type_conditions:
        return 0

    conditions.append("(" + " OR ".join(type_conditions) + ")")

    condition_str = " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT mri.qty, mri.received_qty, mr.docstatus
        FROM `tabMaterial Request Item` mri
        INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
        WHERE 
            mri.item_code = %(item_code)s
            AND mri.warehouse = %(warehouse)s
            AND mr.custom_created_by_scheduled_job = 1
            AND {condition_str}
        """,
        values,
        as_dict=True,
    )

    total_pending = 0

    for row in data:
        if row.docstatus == 0:
            total_pending += flt(row.qty)
        elif row.docstatus == 1:
            pending = flt(row.qty) - flt(row.received_qty)
            if pending > 0:
                total_pending += pending

    return total_pending


# =========================================================
# STOCK
# =========================================================

def get_item_warehouse_stock(items):
    stock = {}
    item_list = list(items.keys())

    if not item_list:
        return stock

    for item_code, warehouse, actual_qty in frappe.db.sql(
        """SELECT item_code, warehouse, actual_qty
        FROM tabBin
        WHERE item_code IN ({})
        AND warehouse IS NOT NULL AND warehouse != ''""".format(
            ", ".join(["%s"] * len(item_list))
        ),
        item_list,
    ):
        stock.setdefault(item_code, {})[warehouse] = flt(actual_qty)

    return stock


# =========================================================
# ITEMS
# =========================================================

def get_items_for_reorder():
    reorder = frappe.qb.DocType("Item Reorder")
    item = frappe.qb.DocType("Item")

    data = (
        frappe.qb.from_(reorder)
        .inner_join(item)
        .on(reorder.parent == item.name)
        .select(
            reorder.warehouse,
            reorder.material_request_type,
            reorder.warehouse_reorder_level,
            reorder.warehouse_reorder_qty,
            item.name,
            item.stock_uom,
            item.purchase_uom,
            item.description,
            item.item_name,
            item.item_group,
            item.brand,
            item.variant_of,
            item.has_variants,
            item.lead_time_days,
        )
        .where((item.disabled == 0) & (item.is_stock_item == 1))
    ).run(as_dict=True)

    out = frappe._dict({})
    for d in data:
        out.setdefault(d.name, []).append(d)

    return out


# =========================================================
# CREATE MATERIAL REQUEST
# =========================================================

def create_material_request(material_requests):
    mr_list = []

    for req_type in material_requests:
        for company in material_requests[req_type]:

            items = material_requests[req_type][company]
            if not items:
                continue

            mr = frappe.new_doc("Material Request")
            mr.update({
                "company": company,
                "transaction_date": nowdate(),
                "material_request_type": "Material Transfer"
                if req_type == "Transfer"
                else req_type,
                "custom_created_by_scheduled_job": 1
            })

            for d in items:
                item = d["item_details"]

                uom = item.stock_uom
                cf = 1.0

                if req_type == "Purchase":
                    uom = item.purchase_uom or item.stock_uom
                    if uom != item.stock_uom:
                        cf = frappe.db.get_value(
                            "UOM Conversion Detail",
                            {"parent": item.name, "uom": uom},
                            "conversion_factor",
                        ) or 1.0

                qty = d["reorder_qty"] / cf

                if frappe.db.get_value("UOM", uom, "must_be_whole_number"):
                    qty = ceil(qty)

                mr.append("items", {
                    "item_code": d["item_code"],
                    "schedule_date": add_days(nowdate(), cint(item.lead_time_days)),
                    "qty": qty,
                    "uom": uom,
                    "conversion_factor": cf,
                    "stock_uom": item.stock_uom,
                    "warehouse": d["warehouse"],
                    "item_name": item.item_name,
                    "description": item.description,
                })

            mr.schedule_date = max([i.schedule_date for i in mr.items] or [nowdate()])
            mr.flags.ignore_mandatory = True
            mr.insert()

            mr_list.append(mr)

    return mr_list






# =========================================================
# EMAIL + ERRORS
# =========================================================

def send_email_notification(data):
    for company, mrs in data.items():
        emails = get_email_list(company)
        if not emails:
            continue

        msg = frappe.render_template(
            "templates/emails/reorder_item.html",
            {"mr_list": mrs}
        )

        frappe.sendmail(
            recipients=emails,
            subject=_("Auto Material Requests Generated"),
            message=msg,
        )


def get_email_list(company):
    users = get_comapny_wise_users(company)

    user = frappe.qb.DocType("User")
    role = frappe.qb.DocType("Has Role")

    q = (
        frappe.qb.from_(user)
        .inner_join(role)
        .on(user.name == role.parent)
        .select(user.email)
        .where(
            (role.role.isin(["Purchase Manager", "Stock Manager"]))
            & (user.enabled == 1)
            & (user.name.notin(["Administrator", "Guest"]))
        )
    )

    if users:
        q = q.where(user.name.isin(users))

    return list(set([d.email for d in q.run(as_dict=True)]))


def get_comapny_wise_users(company):
    companies = [company]
    parent = frappe.db.get_value("Company", company, "parent_company")

    if parent:
        companies.append(parent)

    return [
        d.user for d in frappe.get_all(
            "User Permission",
            filters={
                "allow": "Company",
                "for_value": ("in", companies),
                "apply_to_all_doctypes": 1,
            },
            fields=["user"],
        )
    ]


def notify_errors(exceptions):
    from frappe.email import sendmail_to_system_managers

    content = _("Errors occurred:<br><br>")
    for e in exceptions:
        content += f"{e}<br><br>"

    sendmail_to_system_managers(
        _("[Important] Auto Reorder Errors"),
        content
    )










########.  erpnext.stock.reorder_item.reorder_item
######## gmp.gmp_machine.doctype.custom_settings.custom_settings.reorder_item