# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import timedelta, datetime, time
from frappe.utils import now_datetime, get_datetime

class WorkItem(Document):
	def validate(self):
		self.update_revision_count()
		self.validate_reviewer()
		self.validate_recurrence_date()
		self.validate_recurrence_time()

		if self.status == "In Progress" and self.start_time and self.estimated_duration:
			calculate_planned_target(self)

	def update_revision_count(self):
		if self.name and not self.is_new():
			old_duration = frappe.db.get_value("Work Item", self.name, "estimated_duration")
			if old_duration != self.estimated_duration:
				self.revision_count = self.revision_count + 1
	
	def validate_reviewer(self):
		if self.reviewer == self.assignee:
			frappe.throw("Assignee and Reviewer cannot be same")
	
	def validate_recurrence_date(self):
		seen = set()
		for row in self.recurrence_date:
			val = row.recurrence_date
			if val is None:
				continue
			if val != -1 and not (1 <= val <= 31):
				frappe.throw(
					f"<b>Invalid recurrence date: '{val}'</b><br> Date must be -1 (for last day) or between 1 and 31."
				)
			if val in seen:
				frappe.throw("Each recurrence date must be unique!")
			seen.add(val)
	
	def validate_recurrence_time(self):
		seen = set()
		for row in self.recurrence_time:
			val = row.recurrence_time
			if val is None:
				continue
			if val in seen:
				frappe.throw("Each recurrence time must be unique!")
			seen.add(val)

@frappe.whitelist()
def send_for_review(docname):
	doc = frappe.get_doc("Work Item", docname)
	
	reviewer_email = frappe.db.get_value("User", doc.reviewer, "email")
	if not reviewer_email:
		frappe.throw("Reviewer does not have a valid email.")

	frappe.sendmail(
		recipients=[reviewer_email],
		subject=f"Review Requested for Work Item: {doc.name}",
		message=f"A critical work item has been submitted for your review.<br><br><b>Name:</b> {doc.name}<br><b>Assignee:</b> {doc.assignee}<br><br><a href='{frappe.utils.get_url()}/app/work-item/{doc.name}'>View Work Item</a>"
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
	doc.start_time = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def resend_for_rework(docname):
	doc = frappe.get_doc("Work Item", docname)

	doc.status = "Rework Needed"
	doc.save(ignore_permissions=True)

def calculate_planned_target(doc):
	planned_start = get_datetime(doc.start_time)
	duration_hours = float(doc.estimated_duration or 0)
	if not planned_start or not duration_hours:
		return

	employee = frappe.db.get_value("Employee", {"user_id": doc.assignee}, ["name", "default_shift"], as_dict=True)
	shift_name = employee.default_shift if employee and employee.default_shift else "1st shift"

	shift = frappe.get_doc("Shift Type", shift_name)
	config = frappe.get_doc("Work Item Configuration", {"shift": shift_name})

	shift_start = ensure_time(shift.start_time)
	shift_end = ensure_time(shift.end_time)
	lunch_start = ensure_time(config.lunch_start_time)
	lunch_end = ensure_time(config.lunch_end_time)

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

	doc.planned_end = current_dt

	reminder_delta = timedelta(seconds=duration_hours * 3600 * 0.20)
	doc.twenty_percent_reminder_time = current_dt - reminder_delta
	doc.twenty_percent_reminder_sent = 0

def ensure_time(value):
	if isinstance(value, timedelta):
		total_seconds = int(value.total_seconds())
		hours = total_seconds // 3600
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		return time(hour=hours, minute=minutes, second=seconds)
	return value
