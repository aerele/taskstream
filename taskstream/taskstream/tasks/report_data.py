from datetime import timedelta

import frappe
from frappe.utils import add_days, get_datetime, now_datetime

from taskstream.taskstream.doctype.work_item.work_item import calculate_score


def get_report_data():
	last_executed_on, reporting_frequency = frappe.db.get_value(
		"Work Item Configuration", "Work Item Configuration", ["last_executed_on", "reporting_frequency"]
	)

	if last_executed_on:
		last_executed_on = get_datetime(last_executed_on).date()
		frequency = int(reporting_frequency or 0)
		next_execution_time = last_executed_on + timedelta(days=frequency)
		if next_execution_time > now_datetime().date():
			return

	else:
		frappe.db.set_value(
			"Work Item Configuration",
			"Work Item Configuration",
			"last_executed_on",
			now_datetime().date(),
		)

	work_items = frappe.get_list(
		"Work Item",
		filters={"status": ["!=", "Done"]},
	)

	for work_item in work_items:
		try:
			wi = frappe.get_doc("Work Item", work_item.name)
			calculate_score(wi, "Reporting Window")
			wi.save()
		except Exception as e:
			frappe.log_error(
				message=f"Error processing Work Item {work_item.name}: {e!s}",
				title="Report Data Scheduler",
			)

	frappe.db.set_value(
		"Work Item Configuration",
		"Work Item Configuration",
		"last_executed_on",
		now_datetime().date(),
	)
