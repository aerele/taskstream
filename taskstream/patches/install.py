import frappe
from frappe.permissions import add_permission, update_permission_property


def execute():
	create_months()
	create_weekdays()
	create_permissions()


def create_months():
	months = [
		"January",
		"February",
		"March",
		"April",
		"May",
		"June",
		"July",
		"August",
		"September",
		"October",
		"November",
		"December",
	]
	for month in months:
		frappe.get_doc({"doctype": "Month", "month": month}).insert(
			ignore_permissions=True, ignore_if_duplicate=True
		)


def create_weekdays():
	weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	for day in weekdays:
		frappe.get_doc({"doctype": "Weekday", "day": day}).insert(
			ignore_permissions=True, ignore_if_duplicate=True
		)


def create_permissions():
	doctype_permissions = {
		"Month": ["read", "select"],
		"Weekday": ["read", "select"],
		"Work Flow Template": ["read", "select", "write", "create", "submit", "cancel"],
		"Work Item": ["read", "select", "write", "create", "submit", "cancel"],
	}

	for doctype, permissions in doctype_permissions.items():
		add_permission(doctype, "All", 0)
		for permission in permissions:
			update_permission_property(doctype, "All", 0, permission, 1)
