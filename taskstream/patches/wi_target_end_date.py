import frappe


def execute():
	logs = frappe.get_all(
		"Work Item Log",
		fields=["parent", "time"],
		filters={"parenttype": "Work Item", "action_type": "Target End Date"},
		order_by="creation desc",
	)

	updated_items = set()
	for log in logs:
		if log.parent not in updated_items:
			frappe.db.set_value("Work Item", log.parent, "target_end_date", log.time, update_modified=False)
			updated_items.add(log.parent)
