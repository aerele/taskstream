# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta, time
from frappe.utils import get_datetime

class WorkItem(Document):
	def validate(self):
		self.update_revision_count()
		self.validate_reviewer()
		calculate_planned_target(self)

	def update_revision_count(self):
		if self.name and not self.is_new():
			old_duration = frappe.db.get_value("Work Item", self.name, "estimated_duration")
			if old_duration != self.estimated_duration:
				self.revision_count = self.revision_count + 1
	
	def validate_reviewer(self):
		if self.reviewer == self.assignee:
			frappe.throw("Assignee and Reviewer cannot be same")

@frappe.whitelist()
def send_for_review(docname):
	doc = frappe.get_doc("Work Item", docname)
	
	reviewer_email = frappe.db.get_value("User", doc.reviewer, "email")
	if not reviewer_email:
		frappe.throw("Reviewer does not have a valid email.")

	frappe.sendmail(
		recipients=[reviewer_email],
		subject=f"Review Requested for Work Item: {doc.name}",
		message=f"A critical work item has been submitted for your review.<br><br><b>Name:</b> {doc.name}<br><b>Assignee:</b> {doc.assignee}<br><b>Started on:</b> {doc.actual_start}<br><br><a href='{frappe.utils.get_url()}/app/work-item/{doc.name}'>View Work Item</a>"
	)

	doc.status = "Under Review"
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def mark_complete(docname):
	doc = frappe.get_doc("Work Item", docname)

	doc.status = "Done"
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def start_now(docname):
	doc = frappe.get_doc("Work Item", docname)

	doc.status = "In Progress"
	doc.actual_start = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def calculate_planned_target(doc):
	planned_start = get_datetime(doc.planned_start)
	duration_hours = doc.estimated_duration

	employee = frappe.db.get_value("Employee", {"user_id": doc.assignee}, ["name", "default_shift"], as_dict=True)
	shift_name = employee.default_shift if employee and employee.default_shift else "1st shift"

	shift = frappe.get_doc("Shift Type", shift_name)
	config = frappe.get_doc("Work Item Configuration", {"shift": shift_name})

	shift_start = time_from_timedelta(shift.start_time)
	shift_end = time_from_timedelta(shift.end_time)
	lunch_start = time_from_timedelta(config.lunch_start_time)
	lunch_end = time_from_timedelta(config.lunch_end_time)

	current_dt = planned_start
	remaining_hours = duration_hours

	while remaining_hours > 0:
		current_day = current_dt.date()
		shift_start_dt = datetime.combine(current_day, shift_start)
		shift_end_dt = datetime.combine(current_day, shift_end)

		if current_dt < shift_start_dt:
			current_dt = shift_start_dt

		if current_dt >= shift_end_dt:
			current_dt = datetime.combine(current_day + timedelta(days=1), shift_start)
			continue

		available_start = current_dt
		available_end = min(shift_end_dt, datetime.combine(current_day, lunch_start))
		available_hours_before_lunch = max(0, (available_end - available_start).total_seconds() / 3600)

		if available_hours_before_lunch > 0:
			used = min(remaining_hours, available_hours_before_lunch)
			remaining_hours -= used
			current_dt += timedelta(hours=used)
			if remaining_hours <= 0:
				break

		lunch_start_dt = datetime.combine(current_day, lunch_start)
		lunch_end_dt = datetime.combine(current_day, lunch_end)
		if lunch_start_dt <= current_dt < lunch_end_dt:
			current_dt = lunch_end_dt

		available_end = shift_end_dt
		available_hours_after_lunch = max(0, (available_end - current_dt).total_seconds() / 3600)
		if available_hours_after_lunch > 0:
			used = min(remaining_hours, available_hours_after_lunch)
			remaining_hours -= used
			current_dt += timedelta(hours=used)
			if remaining_hours <= 0:
				break

		current_dt = datetime.combine(current_day + timedelta(days=1), shift_start)

	doc.planned_target = current_dt


def time_from_timedelta(td):
	if isinstance(td, timedelta):
		full_seconds = int(td.total_seconds())
		hours = full_seconds // 3600
		minutes = (full_seconds % 3600) // 60
		seconds = full_seconds % 60
		return time(hour=hours, minute=minutes, second=seconds)
	return td
