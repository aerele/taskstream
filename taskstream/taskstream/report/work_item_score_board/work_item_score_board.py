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
		{
			"label": "User / Team",
			"fieldname": "user",
			"fieldtype": "Data",
			"width": 360,
			"indent_based_on": "indent",
		},
		{"label": "Score", "fieldname": "score", "fieldtype": "Float", "width": 300},
	]


def get_data(filters=None):
	filters = filters or {}
	from_date = filters.get("from_date") or frappe.utils.add_months(frappe.utils.today(), -1)
	to_date = filters.get("to_date") or frappe.utils.today()
	user = filters.get("user")

	work_item = DocType("Work Item")

	start_dt = get_datetime(getdate(from_date))
	end_dt = get_datetime(getdate(to_date)).replace(hour=23, minute=59, second=59, microsecond=999999)

	query = (
		frappe.qb.from_(work_item)
		.select(
			work_item.assignee.as_("user"),
			Sum(Coalesce(work_item.score, 0)).as_("total_score"),
			Count(work_item.name).as_("work_item_count"),
		)
		.where(work_item.target_end_date.between(start_dt, end_dt))
		.groupby(work_item.assignee)
		.orderby(work_item.assignee)
		.where(work_item.status == "Done")
	)

	base_rows = query.run(as_dict=True)
	erpnext_with_employee = is_erpnext_installed()
	rows = get_hierarchical_scores(base_rows) if erpnext_with_employee else build_average_rows(base_rows)

	if user:
		rows = [row for row in rows if row.get("user_id") == user]

	return rows if erpnext_with_employee else sorted(rows, key=lambda row: row.get("user") or "")


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
				"user_id": row.get("user"),
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

	employees = frappe.get_all(
		"Employee",
		fields=["name", "employee_name", "user_id", "company_email", "personal_email", "reports_to"],
		filters={"status": "Active"},
	)
	employee_to_user = {}
	employee_display_by_name = {}
	reports_to_by_employee = {}
	children_by_manager = defaultdict(list)
	for employee in employees:
		employee_name = employee.get("name")
		employee_user = employee.get("user_id")
		employee_display = (
			employee_user
			or employee.get("company_email")
			or employee.get("personal_email")
			or employee.get("employee_name")
			or employee_name
		)
		reports_to = employee.get("reports_to")
		if not employee_name:
			continue

		reports_to_by_employee[employee_name] = reports_to
		employee_display_by_name[employee_name] = employee_display
		if employee_user:
			employee_to_user[employee_name] = employee_user
			stats_by_user.setdefault(employee_user, {"total_score": 0, "work_item_count": 0})
		if reports_to:
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

	def to_score(total_score, work_item_count):
		return (total_score / work_item_count) if work_item_count else 0

	def make_row(user, user_id, total_score, work_item_count, indent, is_group):
		return {
			"user": user,
			"user_id": user_id,
			"score": to_score(total_score, work_item_count),
			"indent": indent,
			"is_group": is_group,
		}

	def get_user_stats(employee_user):
		return stats_by_user.get(employee_user, {"total_score": 0, "work_item_count": 0})

	def sort_key(employee_name):
		return (
			employee_to_user.get(employee_name)
			or employee_display_by_name.get(employee_name)
			or employee_name
		)

	rows = []
	visited = set()

	def add_employee_rows(employee_name, indent=0):
		if employee_name in visited:
			return
		visited.add(employee_name)

		employee_user = employee_to_user.get(employee_name)
		own_stats = get_user_stats(employee_user)
		team_total_score, team_work_item_count = aggregate_employee(employee_name)
		children = children_by_manager.get(employee_name, [])
		has_children = bool(children)

		if has_children:
			rows.append(
				make_row(
					user=f"{employee_display_by_name.get(employee_name)} (Team)",
					user_id=employee_user,
					total_score=team_total_score,
					work_item_count=team_work_item_count,
					indent=indent,
					is_group=1,
				)
			)

			if employee_user:
				rows.append(
					make_row(
						user=employee_user,
						user_id=employee_user,
						total_score=own_stats["total_score"],
						work_item_count=own_stats["work_item_count"],
						indent=indent + 1,
						is_group=0,
					)
				)

			for child_employee in sorted(children, key=sort_key):
				add_employee_rows(child_employee, indent + 1)
			return

		if employee_user:
			rows.append(
				make_row(
					user=employee_user,
					user_id=employee_user,
					total_score=own_stats["total_score"],
					work_item_count=own_stats["work_item_count"],
					indent=indent,
					is_group=0,
				)
			)

	all_employee_names = set(reports_to_by_employee)
	root_employees = sorted(
		[
			employee_name
			for employee_name in all_employee_names
			if not reports_to_by_employee.get(employee_name)
			or reports_to_by_employee.get(employee_name) not in all_employee_names
		],
		key=sort_key,
	)
	if not root_employees:
		root_employees = sorted(all_employee_names, key=sort_key)

	for root_employee in root_employees:
		add_employee_rows(root_employee, indent=0)

	# If any employee was not reachable from roots (broken/cyclic hierarchy), still show them.
	for employee_name in sorted(all_employee_names, key=sort_key):
		if employee_name not in visited:
			add_employee_rows(employee_name, indent=0)

	# Handle users with scores who are not mapped to Employee
	employee_users = set(employee_to_user.values())
	non_employee_users = sorted(set(stats_by_user) - employee_users)
	for assignee in non_employee_users:
		stats = stats_by_user.get(assignee, {})
		rows.append(
			make_row(
				user=assignee,
				user_id=assignee,
				total_score=stats.get("total_score") or 0,
				work_item_count=stats.get("work_item_count") or 0,
				indent=0,
				is_group=0,
			)
		)

	if not rows:
		return build_average_rows(base_rows)

	return rows
