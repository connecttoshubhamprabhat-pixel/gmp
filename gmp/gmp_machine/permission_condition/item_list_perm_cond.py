import frappe


def item_list(doc, user=None):
    if not user:
        user = frappe.session.user

    restricted_creators = [
        "abhishek@gmpmachpro.com",
        "marketing@gmpmachpro.com",
        "pradeep@gmpmachpro.com"
    ]

    restricted_users = [
        "purchase1@gmpmachpro.com",
        "purchase@gmpmachpro.com",
        "planning1@gmpmachpro.com",
        "planning3@gmpmachpro.com",
        "planning2@gmpmachpro.com",
        "erp.design@gmpmachpro.com",
        "design1@gmpmachpro.com",
        "design2@gmpmachpro.com",
        "design3@gmpmachpro.com",
        "store2@gmpmachpro.com",
        "store1@gmpmachpro.com"
    ]

    if user in restricted_users:
        creators = ", ".join(
            frappe.db.escape(creator)
            for creator in restricted_creators
        )

        return f"`tabItem`.owner NOT IN ({creators})"

    return ""


def has_item_permission(doc, user=None, permission_type=None):
    if not user:
        user = frappe.session.user

    restricted_creators = [
        "abhishek@gmpmachpro.com",
        "marketing@gmpmachpro.com",
        "pradeep@gmpmachpro.com"
    ]

    restricted_users = [
        "purchase1@gmpmachpro.com",
        "purchase@gmpmachpro.com",
        "planning1@gmpmachpro.com",
        "planning3@gmpmachpro.com",
        "planning2@gmpmachpro.com",
        "erp.design@gmpmachpro.com",
        "design1@gmpmachpro.com",
        "design2@gmpmachpro.com",
        "design3@gmpmachpro.com",
        "store2@gmpmachpro.com",
        "store1@gmpmachpro.com"
    ]

    if user in restricted_users:
        if doc.owner in restricted_creators:
            return False

    return True