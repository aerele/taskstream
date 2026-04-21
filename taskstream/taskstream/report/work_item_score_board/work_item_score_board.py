# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

import urllib.parse
from collections import defaultdict

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce, Count, Sum
from frappe.utils import get_datetime, getdate

from taskstream.api import get_cycles


def execute(filters=None):
	wic = frappe.get_doc("Work Item Configuration", "Work Item Configuration")
	if wic.last_executed_on is None or wic.no_of_cycles_in_report == 0 or wic.reporting_frequency == 0:
		frappe.throw("Please Complete the Work Item Configuration setup to run the report.")
	cycle_dates = get_cycles(
		wic.last_executed_on, wic.reporting_frequency, wic.no_of_cycles_in_report, wic.starting_date
	)
	columns = get_columns(cycle_dates)
	data = get_data(filters, cycle_dates)
	return columns, data


def get_columns(cycle_dates):
	columns = [
		{
			"label": "User / Team",
			"fieldname": "user",
			"fieldtype": "Data",
			"width": 360,
			"indent_based_on": "indent",
		},
		{"label": "Current Score", "fieldname": "score", "fieldtype": "Data", "width": 300},
	]
	for cycle in cycle_dates:
		columns.append({"label": f"{cycle}", "fieldname": f"score_{cycle}", "fieldtype": "Data"})
	return columns


def get_data(filters=None, cycle_dates=None):
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

	# Fetch per-cycle scores from Work Item Score Summary
	cycle_scores_raw = []
	if cycle_dates:
		try:
			cycle_scores_raw = frappe.get_all(
				"Work Item Score Summary",
				filters={"report_cycle": ("in", cycle_dates), "action": "Scheduled Job"},
				fields=["assignee", "report_cycle", "score", "work_item"],
			)
		except Exception:
			cycle_scores_raw = []

	# Build per-user per-cycle totals and counts
	user_cycle_wi_scores = defaultdict(lambda: defaultdict(dict))
	for rec in cycle_scores_raw:
		assignee = rec.get("assignee")
		cycle = rec.get("report_cycle")
		score = rec.get("score") or 0.0
		work_item = rec.get("work_item")

		if not assignee or not cycle or not work_item:
			continue

		if work_item not in user_cycle_wi_scores[assignee][cycle]:
			user_cycle_wi_scores[assignee][cycle][work_item] = score
		else:
			user_cycle_wi_scores[assignee][cycle][work_item] = max(
				user_cycle_wi_scores[assignee][cycle][work_item], score
			)

	user_cycle_stats = defaultdict(lambda: defaultdict(lambda: {"total": 0.0, "count": 0}))
	for assignee, cycles in user_cycle_wi_scores.items():
		for cycle, wi_scores in cycles.items():
			for max_score in wi_scores.values():
				user_cycle_stats[assignee][cycle]["total"] += max_score
				user_cycle_stats[assignee][cycle]["count"] += 1

	erpnext_with_employee = is_erpnext_installed()
	rows = (
		get_hierarchical_scores(base_rows, cycle_dates, user_cycle_stats)
		if erpnext_with_employee
		else build_average_rows(base_rows, cycle_dates, user_cycle_stats)
	)

	if user:
		rows = [row for row in rows if row.get("user_id") == user]

	return rows if erpnext_with_employee else sorted(rows, key=lambda row: row.get("user") or "")


def is_erpnext_installed():
	return "erpnext" in frappe.get_installed_apps() and frappe.db.exists("DocType", "Employee")


def build_average_rows(rows, cycle_dates=None, user_cycle_stats=None):
	cycle_dates = cycle_dates or []
	user_cycle_stats = user_cycle_stats or {}
	avg_rows = []
	for row in rows:
		count = row.get("work_item_count") or 0
		total_score = row.get("total_score") or 0
		user_id = row.get("user")
		row_data = {
			"user": row.get("user"),
			"user_id": user_id,
			"score": round(total_score / count, 0) if count else 0,
		}
		for cycle in cycle_dates:
			stats = user_cycle_stats.get(user_id, {}).get(cycle, {"total": 0.0, "count": 0})
			score_val = round(stats["total"] / stats["count"], 0) if stats["count"] else 0
			if user_id and stats["count"]:
				url_params = urllib.parse.urlencode(
					{"assignee": user_id, "report_cycle": cycle, "action": "Scheduled Job"}
				)
				row_data[f"score_{cycle}"] = (
					f"<a href='/app/work-item-score-summary?{url_params}' target='_blank'>{score_val}</a>"
				)
			else:
				row_data[f"score_{cycle}"] = score_val

		avg_rows.append(row_data)
	return avg_rows


def get_hierarchical_scores(base_rows, cycle_dates=None, user_cycle_stats=None):
	cycle_dates = cycle_dates or []
	user_cycle_stats = user_cycle_stats or {}

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
			employee.get("employee_name")
			or employee.get("company_email")
			or employee.get("personal_email")
			or employee_name
			or employee_user
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
			# cycle totals: zeros
			cycle_totals_zero = {cycle: {"total": 0.0, "count": 0} for cycle in cycle_dates}
			return 0, 0, cycle_totals_zero

		active_stack.add(employee_name)

		employee_user = employee_to_user.get(employee_name)
		own_stats = stats_by_user.get(employee_user, {"total_score": 0, "work_item_count": 0})
		total_score = own_stats["total_score"]
		work_item_count = own_stats["work_item_count"]

		# per-cycle totals for this node (employee)
		cycle_totals = {cycle: {"total": 0.0, "count": 0} for cycle in cycle_dates}
		if employee_user:
			for cycle in cycle_dates:
				st = user_cycle_stats.get(employee_user, {}).get(cycle)
				if st:
					cycle_totals[cycle]["total"] += st.get("total", 0.0)
					cycle_totals[cycle]["count"] += st.get("count", 0)

		for child_employee in children_by_manager.get(employee_name, []):
			child_total_score, child_work_item_count, child_cycle_totals = aggregate_employee(child_employee)
			total_score += child_total_score
			work_item_count += child_work_item_count
			for cycle in cycle_dates:
				ctot = child_cycle_totals.get(cycle, {"total": 0.0, "count": 0})
				cycle_totals[cycle]["total"] += ctot.get("total", 0.0)
				cycle_totals[cycle]["count"] += ctot.get("count", 0)

		active_stack.remove(employee_name)
		memo[employee_name] = (total_score, work_item_count, cycle_totals)
		return memo[employee_name]

	def to_score(total_score, work_item_count):
		return round(total_score / work_item_count, 0) if work_item_count else 0

	def make_row(user, user_id, total_score, work_item_count, indent, is_group, cycle_values=None):
		row = {
			"user": user,
			"user_id": user_id,
			"score": to_score(total_score, work_item_count),
			"indent": indent,
			"is_group": is_group,
		}
		cycle_values = cycle_values or {}
		for cycle in cycle_dates:
			c = cycle_values.get(cycle, {"total": 0.0, "count": 0})
			score_val = to_score(c.get("total", 0.0), c.get("count", 0))
			if user_id and not is_group and c.get("count", 0):
				url_params = urllib.parse.urlencode(
					{"assignee": user_id, "report_cycle": cycle, "action": "Scheduled Job"}
				)
				row[f"score_{cycle}"] = (
					f"<a href='/app/work-item-score-summary?{url_params}' target='_blank'>{score_val}</a>"
				)
			else:
				row[f"score_{cycle}"] = score_val
		return row

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
		team_total_score, team_work_item_count, team_cycle_totals = aggregate_employee(employee_name)
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
					cycle_values=team_cycle_totals,
				)
			)

			if employee_user:
				rows.append(
					make_row(
						user=employee_display_by_name.get(employee_name) or employee_user,
						user_id=employee_user,
						total_score=own_stats["total_score"],
						work_item_count=own_stats["work_item_count"],
						indent=indent + 1,
						is_group=0,
						cycle_values=user_cycle_stats.get(employee_user, {}),
					)
				)

			for child_employee in sorted(children, key=sort_key):
				add_employee_rows(child_employee, indent + 1)
			return

		if employee_user:
			# leaf employee row
			rows.append(
				make_row(
					user=employee_display_by_name.get(employee_name) or employee_user,
					user_id=employee_user,
					total_score=own_stats["total_score"],
					work_item_count=own_stats["work_item_count"],
					indent=indent,
					is_group=0,
					cycle_values=user_cycle_stats.get(employee_user, {}),
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
				cycle_values=user_cycle_stats.get(assignee, {}),
			)
		)

	if not rows:
		return build_average_rows(base_rows, cycle_dates, user_cycle_stats)

	return rows
