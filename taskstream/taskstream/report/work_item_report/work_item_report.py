# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

from datetime import datetime, time, timedelta

import frappe
from frappe.query_builder import DocType
from frappe.utils import add_days, get_datetime, getdate, now_datetime


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
	)

	filters = filters or {}
	columns = get_columns(cycle_dates)
	data = get_data(filters, cycle_dates, no_of_cycles_in_report.no_of_cycles_in_report)
	return columns, data


def get_columns(cycle_dates):
	columns = [
		{"label": "Work Item", "fieldname": "work_item", "fieldtype": "Link", "options": "Work Item"},
		{"label": "Summary", "fieldname": "summary", "fieldtype": "Data"},
		{"label": "Description", "fieldname": "description", "fieldtype": "Data"},
		{"label": "Assignee", "fieldname": "assignee", "fieldtype": "Link", "options": "User"},
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
	start_dt, end_dt = _get_window(filters, no_of_cycles_in_report.reporting_frequency)
	reporting_type = filters.get("reporting_type") or "Upcoming"

	work_item = DocType("Work Item")
	work_item_summary = DocType("Work Item Score Summary")

	query = (
		frappe.qb.from_(work_item)
		.select(
			work_item.name.as_("work_item"),
			work_item.summary,
			work_item.description,
			work_item.assignee,
			work_item.status,
			work_item.reference_document,
			work_item.reference_doctype,
			work_item.benefit_of_work_done,
			work_item.target_end_date.as_("target_date"),
			work_item.actual_end_date.as_("actual_end"),
		)
		.where(work_item.target_end_date.isnotnull())
	)

	if reporting_type == "Upcoming":
		query = query.where(work_item.target_end_date.between(start_dt, end_dt))
	else:
		query = query.where(work_item.target_end_date.between(start_dt, end_dt))
		query = query.where(work_item.status != "Done")

	rows = query.orderby(work_item.target_end_date).run(as_dict=True)

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
			"description": row.get("description"),
			"assignee": row.get("assignee"),
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
				.select(work_item_summary.name, work_item_summary.score, work_item_summary.creation)
				.where(work_item_summary.work_item == row.get("work_item"))
				.where(work_item_summary.generated_from == "Reporting Window")
				.orderby(work_item_summary.creation)
				.limit(no_of_cycles)
			)
			summary_records = summary_query.run(as_dict=True)

			# Reverse to get oldest to newest for proper cycle mapping
			summary_records = list(reversed(summary_records))

			# Map scores to cycle dates
			for idx, summary_record in enumerate(summary_records):
				if idx < len(cycle_dates):
					cycle_key = f"score_{cycle_dates[idx]}"
					result_row[cycle_key] = summary_record.get("score") or 0

		results.append(result_row)

	return results


def _get_window(filters, reporting_frequency=0):
	reporting_type = filters.get("reporting_type") or "Upcoming"
	today = getdate()
	if reporting_type == "Overdue":
		end_date = add_days(today, -1)
		start_date = add_days(end_date, -reporting_frequency + 1)
	else:
		start_date = today
		end_date = add_days(today, reporting_frequency - 1)
	start_dt = datetime.combine(start_date, time.min)
	end_dt = datetime.combine(end_date, time.max)
	return start_dt, end_dt


def get_cycles(last_date, reporting_frequency, no_of_cycles):
	from datetime import datetime

	last_date = datetime.strptime(str(last_date), "%Y-%m-%d")
	cycles = []

	current_end = last_date

	for _ in range(no_of_cycles):
		start = current_end - timedelta(days=reporting_frequency - 1)
		cycles.append(f"{start.strftime('%b %d')} - {current_end.strftime('%b %d')}")
		current_end = start - timedelta(days=1)

	return list(cycles)
