import json

import frappe
from frappe.utils import cint


@frappe.whitelist()
def get_purchase_order_items_for_quality_inspection(
    docstatus: str | int,
    items: str | list[dict],
    is_subcontracted: str | int = 0,
):
    """Return PO rows eligible for QI, using fg_item for subcontracted orders."""
    if isinstance(items, str):
        items = json.loads(items)

    is_subcontracted = cint(is_subcontracted)
    normalized_items = []
    for item in items:
        quality_item_code = (
            item.get("fg_item") if is_subcontracted else item.get("item_code")
        )
        if not quality_item_code:
            continue

        normalized_item = dict(item)
        normalized_item["item_code"] = quality_item_code
        if is_subcontracted and item.get("fg_item_qty") is not None:
            normalized_item["qty"] = item.get("fg_item_qty")

        normalized_items.append(normalized_item)

    allow_after_transaction = cint(docstatus) == 1 and frappe.get_single_value(
        "Stock Settings", "allow_to_make_quality_inspection_after_purchase_or_delivery"
    )
    if allow_after_transaction:
        eligible_items = normalized_items
    else:
        item_codes = list({item.get("item_code") for item in normalized_items})
        if not item_codes:
            return []

        Item = frappe.qb.DocType("Item")
        results = (
            frappe.qb.from_(Item)
            .select(Item.name)
            .where(
                (Item.name.isin(item_codes))
                & (Item.inspection_required_before_purchase == 1)
            )
            .run(as_dict=True)
        )
        inspection_required_items = {row.name for row in results}
        eligible_items = [
            item
            for item in normalized_items
            if item.get("item_code") in inspection_required_items
        ]

    if not eligible_items:
        return []

    item_names = dict(
        frappe.get_all(
            "Item",
            filters={"name": ["in", [item["item_code"] for item in eligible_items]]},
            fields=["name", "item_name"],
            as_list=True,
        )
    )
    for item in eligible_items:
        item["item_name"] = item_names.get(item["item_code"], item.get("item_name"))

    return eligible_items
