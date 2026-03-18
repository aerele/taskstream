import frappe


@frappe.whitelist()
def delete_file_if_exists(file_name):
	if not frappe.db.exists("File", file_name):
		return
	frappe.delete_doc("File", file_name, ignore_permissions=True)
