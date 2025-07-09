import frappe

def execute():
	create_months()

def create_months():
	months = [
		"January", "February", "March", "April", "May", "June",
		"July", "August", "September", "October", "November", "December"
	]
	for month in months:
		frappe.get_doc({
			"doctype": "Month",
			"month": month
		}).insert(ignore_permissions=True)