# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce, Count, Sum
from frappe.utils import get_datetime, getdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "User", "fieldname": "user", "fieldtype": "Link", "options": "User"},
		{"label": "Score", "fieldname": "score", "fieldtype": "Float"},
	]


def get_data(filters=None):
	filters = filters or {}
	from_date = filters.get("from_date") or frappe.utils.add_months(frappe.utils.today(), -1)
	to_date = filters.get("to_date") or frappe.utils.today()
	user = filters.get("user")

	work_item = DocType("Work Item")
	work_item_log = DocType("Work Item Log")

	start_dt = get_datetime(getdate(from_date))
	end_dt = get_datetime(getdate(to_date)).replace(hour=23, minute=59, second=59, microsecond=999999)

	filtered_work_items = (
		frappe.qb.from_(work_item_log)
		.select(work_item_log.parent)
		.where(
			(work_item_log.parenttype == "Work Item")
			& (work_item_log.parentfield == "activities")
			& (work_item_log.time.between(start_dt, end_dt))
		)
		.distinct()
	)
	query = (
		frappe.qb.from_(work_item)
		.select(
			work_item.assignee.as_("user"),
			Sum(Coalesce(work_item.score, 0)).as_("total_score"),
			Count(work_item.name).as_("work_item_count"),
		)
		.where(work_item.name.isin(filtered_work_items))
		.groupby(work_item.assignee)
		.orderby(work_item.assignee)
		.where(work_item.status == "Done")
	)

	base_rows = query.run(as_dict=True)
	if is_erpnext_installed():
		rows = get_hierarchical_scores(base_rows)
	else:
		rows = build_average_rows(base_rows)

	if user:
		rows = [row for row in rows if row.get("user") == user]

	return sorted(rows, key=lambda row: row.get("user") or "")


def is_erpnext_installed():
	return "erpnext" in frappe.get_installed_apps() and frappe.db.exists("DocType", "Employee")


def build_average_rows(rows):
	avg_rows = []
	for row in rows:
		count = row.get("work_item_count") or 0
		total_score = row.get("total_score") or 0
		avg_rows.append(
			{
				"user": row.get("user"),
				"work_item_count": count,
				"score": (total_score / count) if count else 0,
			}
		)
	return avg_rows


def get_hierarchical_scores(base_rows):
	stats_by_user = defaultdict(lambda: {"total_score": 0, "work_item_count": 0})
	for row in base_rows:
		assignee = row.get("user")
		if not assignee:
			continue
		stats_by_user[assignee]["total_score"] = row.get("total_score") or 0
		stats_by_user[assignee]["work_item_count"] = row.get("work_item_count") or 0

	employees = frappe.get_all("Employee", fields=["name", "user_id", "reports_to"])
	employee_to_user = {}
	children_by_manager = defaultdict(list)
	for employee in employees:
		employee_name = employee.get("name")
		employee_user = employee.get("user_id")
		reports_to = employee.get("reports_to")

		if employee_name and employee_user:
			employee_to_user[employee_name] = employee_user
			stats_by_user.setdefault(employee_user, {"total_score": 0, "work_item_count": 0})
		if employee_name and reports_to:
			children_by_manager[reports_to].append(employee_name)

	memo = {}
	active_stack = set()

	def aggregate_employee(employee_name):
		if employee_name in memo:
			return memo[employee_name]
		if employee_name in active_stack:
			return 0, 0

		active_stack.add(employee_name)

		employee_user = employee_to_user.get(employee_name)
		own_stats = stats_by_user.get(employee_user, {"total_score": 0, "work_item_count": 0})
		total_score = own_stats["total_score"]
		work_item_count = own_stats["work_item_count"]

		for child_employee in children_by_manager.get(employee_name, []):
			child_total_score, child_work_item_count = aggregate_employee(child_employee)
			total_score += child_total_score
			work_item_count += child_work_item_count

		active_stack.remove(employee_name)
		memo[employee_name] = (total_score, work_item_count)
		return memo[employee_name]

	final_stats_by_user = {}
	for employee_name, employee_user in employee_to_user.items():
		total_score, work_item_count = aggregate_employee(employee_name)
		final_stats_by_user[employee_user] = {
			"user": employee_user,
			"total_score": total_score,
			"work_item_count": work_item_count,
		}

	for assignee, stats in stats_by_user.items():
		final_stats_by_user.setdefault(
			assignee,
			{
				"user": assignee,
				"total_score": stats["total_score"],
				"work_item_count": stats["work_item_count"],
			},
		)

	return build_average_rows(final_stats_by_user.values())
