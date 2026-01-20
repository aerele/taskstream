import frappe

def work_item_user_condition(user=None):
    if not user:
        user = frappe.session.user

    return (
        "`tabWork Item`.requested_by = '{user}' OR "
        "`tabWork Item`.assignee = '{user}' OR "
        "`tabWork Item`.reviewer = '{user}' OR "
        "`tabWork Item`.report_to = '{user}'"
    ).format(user=user)
