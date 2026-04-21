from datetime import timedelta

import frappe
from frappe.utils import add_days, get_datetime


@frappe.whitelist()
def delete_file_if_exists(file_name):
	if not frappe.db.exists("File", file_name):
		return
	frappe.delete_doc("File", file_name, ignore_permissions=True)


def get_reporting_window():
	last_executed_on, reporting_frequency = frappe.db.get_value(
		"Work Item Configuration", "Work Item Configuration", ["last_executed_on", "reporting_frequency"]
	)
	last_executed_on = get_datetime(last_executed_on).date()
	start_date = add_days(last_executed_on, 1)
	end_date = add_days(start_date, int(reporting_frequency or 0) - 1)
	return f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}"


def get_cycles(last_date, reporting_frequency, no_of_cycles, starting_date):
	from datetime import datetime

	last_date = datetime.strptime(str(last_date), "%Y-%m-%d")
	cycles = []

	current_end = last_date

	for _ in range(no_of_cycles):
		start = current_end - timedelta(days=reporting_frequency - 1)
		if starting_date and start >= get_datetime(starting_date):
			cycles.append(f"{start.strftime('%b %d')} - {current_end.strftime('%b %d')}")
		current_end = start - timedelta(days=1)

	return list(cycles)


@frappe.whitelist()
def get_all_work_flow_template_tasks(wft):
	return frappe.get_all(
		"Work Flow Template Item",
		filters={"parent": wft},
		fields=["assignee", "task_name", "task_description", "idx", "target_end_date_time"],
	)
