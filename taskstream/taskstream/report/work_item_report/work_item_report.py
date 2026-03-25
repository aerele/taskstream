# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

from datetime import datetime, time

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Max
from frappe.utils import add_days, get_datetime, getdate, now_datetime


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
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


def get_data(filters=None):
	filters = filters or {}
	start_dt, end_dt = _get_window(filters)
	reporting_type = filters.get("reporting_type") or "Upcoming"

	work_item = DocType("Work Item")
	work_item_log = DocType("Work Item Log")

	target_subquery = (
		frappe.qb.from_(work_item_log)
		.select(work_item_log.parent, Max(work_item_log.time).as_("target_date"))
		.where(
			(work_item_log.parenttype == "Work Item")
			& (work_item_log.parentfield == "activities")
			& (work_item_log.action_type == "Target End Date")
		)
		.groupby(work_item_log.parent)
	).as_("target_log")

	actual_subquery = (
		frappe.qb.from_(work_item_log)
		.select(work_item_log.parent, Max(work_item_log.time).as_("actual_end"))
		.where(
			(work_item_log.parenttype == "Work Item")
			& (work_item_log.parentfield == "activities")
			& (work_item_log.action_type == "Actual End Time")
		)
		.groupby(work_item_log.parent)
	).as_("actual_log")

	query = (
		frappe.qb.from_(work_item)
		.left_join(target_subquery)
		.on(target_subquery.parent == work_item.name)
		.left_join(actual_subquery)
		.on(actual_subquery.parent == work_item.name)
		.select(
			work_item.name.as_("work_item"),
			work_item.summary,
			work_item.description,
			work_item.assignee,
			work_item.status,
			work_item.reference_document,
			work_item.reference_doctype,
			work_item.benefit_of_work_done,
			target_subquery.target_date,
			actual_subquery.actual_end,
		)
		.where(target_subquery.target_date.isnotnull())
	)

	if reporting_type == "Upcoming":
		query = query.where(target_subquery.target_date.between(start_dt, end_dt))
	else:
		query = query.where(target_subquery.target_date.between(start_dt, end_dt))
		query = query.where(work_item.status != "Done")

	rows = query.orderby(target_subquery.target_date).run(as_dict=True)

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

		results.append(
			{
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
		)

	return results


def _get_window(filters):
	reporting_period = filters.get("reporting_period") or "Daily"
	reporting_type = filters.get("reporting_type") or "Upcoming"
	span = {"Daily": 1, "Weekly": 7, "Fortnight": 14, "Monthly": 30}.get(reporting_period, 1)

	if reporting_period == "Custom":
		start_date = getdate(filters.get("from_date") or now_datetime())
		end_date = getdate(filters.get("to_date") or start_date)
	else:
		today = getdate()
		if reporting_type == "Overdue":
			end_date = add_days(today, -1)
			start_date = add_days(end_date, -(span - 1))
		else:
			start_date = today
			end_date = add_days(today, span - 1)

	start_dt = datetime.combine(start_date, time.min)
	end_dt = datetime.combine(end_date, time.max)
	return start_dt, end_dt
