import frappe


def work_item_user_condition(user=None):
	if not user:
		user = frappe.session.user

	escaped_user = frappe.db.escape(user)
	recurrence_filter = "COALESCE(`tabWork Item`.recurrence_type, '')"

	return (
		f"(({recurrence_filter} IN ('One Time', 'Recurring Instance') AND ("
		f"`tabWork Item`.requester = {escaped_user} OR "
		f"`tabWork Item`.assignee = {escaped_user} OR "
		f"`tabWork Item`.reviewer = {escaped_user} OR "
		f"`tabWork Item`.reporter = {escaped_user}"
		f")) OR ({recurrence_filter} NOT IN ('One Time', 'Recurring Instance') AND ("
		f"`tabWork Item`.requester = {escaped_user} OR "
		f"`tabWork Item`.reporter = {escaped_user}"
		f")))"
	)
