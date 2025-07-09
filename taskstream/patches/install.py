import frappe

def execute():
	create_months()
	create_weekdays()

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

def create_weekdays():
	weekdays = [
		"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
	]
	for day in weekdays:
		frappe.get_doc({
			"doctype": "Weekday",
			"day": day
		}).insert(ignore_permissions=True)