import frappe
from frappe.permissions import add_permission, update_permission_property


def execute():
	create_months()
	create_weekdays()
	create_permissions()
	create_role()
	update_user_list_link()


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
		"Work Item Configuration": ["read", "select"],
		"Work Flow Template": ["read", "select", "write", "create", "submit"],
		"Work Item": ["read", "select", "write", "create", "submit"],
		"Work Item Time Extension": ["read", "select", "write", "create"],
		"Collection": {
			"permissions": ["read", "select", "write", "create", "submit", "delete"],
			"if_owner": 1,
		},
		"Reassignment History": ["read", "select", "write", "create"],
		"Work Item Score Summary": ["read", "select"],
	}

	for doctype, config in doctype_permissions.items():
		if isinstance(config, dict):
			permissions = config.get("permissions", [])
			if_owner = config.get("if_owner", 0)
		else:
			permissions = config
			if_owner = 0

		add_permission(doctype, "All", 0)
		for permission in permissions:
			update_permission_property(doctype, "All", 0, permission, 1)
		if if_owner:
			update_permission_property(doctype, "All", 0, "if_owner", 1)


def create_role():
	frappe.get_doc({"doctype": "Role", "role_name": "Work Item Admin"}).insert(
		ignore_permissions=True, ignore_if_duplicate=True
	)


def update_user_list_link():
	prop_setter = frappe.new_doc("Property Setter")
	prop_setter.doctype_or_field = "DocType"
	prop_setter.doc_type = "User"
	prop_setter.property = "show_title_field_in_link"
	prop_setter.property_type = "check"
	prop_setter.value = 1
	prop_setter.module = "taskstream"
	prop_setter.insert(ignore_if_duplicate=True)
