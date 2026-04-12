# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

from datetime import datetime, time

import frappe
from frappe.query_builder import DocType
from frappe.utils import add_days, get_datetime, now_datetime

from taskstream.api import get_cycles


def execute(filters=None):
	no_of_cycles_in_report = frappe.get_doc("Work Item Configuration", "Work Item Configuration")
	if (
		no_of_cycles_in_report.last_executed_on is None
		or no_of_cycles_in_report.no_of_cycles_in_report == 0
		or no_of_cycles_in_report.reporting_frequency == 0
	):
		# If the report is being run for the first time and cycles are configured, set the last_executed_on to now
		frappe.throw("Please Complete the Work Item Configuration setup to run the report.")
	cycle_dates = get_cycles(
		no_of_cycles_in_report.last_executed_on,
		no_of_cycles_in_report.reporting_frequency,
		no_of_cycles_in_report.no_of_cycles_in_report,
		no_of_cycles_in_report.starting_date,
	)

	filters = filters or {}
	columns = get_columns(cycle_dates)
	data = get_data(filters, cycle_dates, no_of_cycles_in_report.no_of_cycles_in_report)
	return columns, data


def get_columns(cycle_dates):
	columns = [
		{"label": "Work Item", "fieldname": "work_item", "fieldtype": "Link", "options": "Work Item"},
		{"label": "Summary", "fieldname": "summary", "fieldtype": "Data"},
		{"label": "Assignee", "fieldname": "assignee", "fieldtype": "Data"},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data"},
		{"label": "Reference", "fieldname": "reference", "fieldtype": "Link", "options": "Work Item"},
		{"label": "Expected Target Date", "fieldname": "target_date", "fieldtype": "Datetime"},
		{"label": "Delay in Days", "fieldname": "delay_in_days", "fieldtype": "Int"},
		{"label": "Completion Percentage", "fieldname": "completion_percentage", "fieldtype": "Percentage"},
	]
	for cycle in cycle_dates:
		columns.append({"label": f"{cycle}", "fieldname": f"score_{cycle}", "fieldtype": "Data"})
	return columns


def get_data(filters=None, cycle_dates=None, no_of_cycles=0):
	filters = filters or {}
	no_of_cycles_in_report = frappe.get_doc("Work Item Configuration", "Work Item Configuration")
	start_dt, end_dt = _get_window(
		filters,
		no_of_cycles_in_report.last_executed_on,
		no_of_cycles_in_report.reporting_frequency,
	)
	# reporting_type = filters.get("reporting_type") or "Upcoming"

	work_item = DocType("Work Item")
	work_item_summary = DocType("Work Item Score Summary")

	base_query = frappe.qb.from_(work_item).select(
		work_item.name.as_("work_item"),
		work_item.summary,
		work_item.assignee,
		work_item.status,
		work_item.reference_document,
		work_item.reference_doctype,
		work_item.benefit_of_work_done,
		work_item.target_end_date.as_("target_date"),
		work_item.actual_end_date.as_("actual_end"),
	)

	query_open = base_query.where(work_item.target_end_date.between(start_dt, end_dt)).where(
		work_item.status != "Done"
	)

	query_done = base_query.where(work_item.actual_end_date.between(start_dt, end_dt)).where(
		work_item.status == "Done"
	)

	open_rows = query_open.orderby(work_item.target_end_date).run(as_dict=True)
	done_rows = query_done.orderby(work_item.actual_end_date).run(as_dict=True)

	rows = open_rows + done_rows

	results = []
	now = now_datetime()
	for row in rows:
		target_date = get_datetime(row.get("target_date")) if row.get("target_date") else None
		if not target_date:
			continue

		actual_end = get_datetime(row.get("actual_end")) if row.get("actual_end") else None
		anchor_time = actual_end if (row.get("status") == "Done" and actual_end) else now
		delay_days = (anchor_time - target_date).days if anchor_time > target_date else 0

		completion_percentage = 100 if row.get("status") == "Done" else (row.get("benefit_of_work_done") or 0)
		reference = row.get("reference_document") if row.get("reference_doctype") == "Work Item" else None

		result_row = {
			"work_item": row.get("work_item"),
			"summary": row.get("summary"),
			"assignee": frappe.get_cached_value("User", row.get("assignee"), "full_name")
			if row.get("assignee")
			else None,
			"status": row.get("status"),
			"reference": reference,
			"target_date": target_date,
			"delay_in_days": delay_days,
			"completion_percentage": completion_percentage,
		}

		# Fetch Work Item Summary records for this work item
		if no_of_cycles > 0 and cycle_dates:
			summary_query = (
				frappe.qb.from_(work_item_summary)
				.select(
					work_item_summary.name,
					work_item_summary.score,
					work_item_summary.creation,
					work_item_summary.report_cycle,
				)
				.where(work_item_summary.work_item == row.get("work_item"))
				.where(work_item_summary.generated_from == "Reporting Window")
				.where(work_item_summary.report_cycle.isnotnull())
				.where(work_item_summary.report_cycle.isin(cycle_dates))
				.orderby(work_item_summary.creation)
				.limit(no_of_cycles)
			)
			summary_records = summary_query.run(as_dict=True)

			# Map scores to cycle dates
			for summary_record in summary_records:
				report_cycle = summary_record.get("report_cycle")
				if report_cycle:
					cycle_key = f"score_{report_cycle}"
					score_val = summary_record.get("score") or 0
					result_row[cycle_key] = round(score_val, 2)

		results.append(result_row)

	return results


def _get_window(filters, last_executed_on, reporting_frequency=0):
	# reporting_type = filters.get("reporting_type") or "Upcoming"
	# if reporting_type == "Overdue":
	# end_date = last_executed_on
	start_date = add_days(last_executed_on, -reporting_frequency + 1)
	# else:
	# 	start_date = last_executed_on
	# 	end_date = add_days(last_executed_on, reporting_frequency - 1)
	start_dt = datetime.combine(datetime.strptime(start_date, "%Y-%m-%d"), time.min)
	end_dt = datetime.combine(datetime.strptime(last_executed_on, "%Y-%m-%d"), time.max)
	return start_dt, end_dt
