# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import timedelta, datetime, time
from frappe.utils import now_datetime, get_datetime
from taskstream.taskstream import send_notifications

class WorkItem(Document):
	def validate(self):
		
		planned_start_exists = any(row.action_type == "Planned Start Time" for row in self.activities)
		planned_end_exists = any(row.action_type == "Planned End Time" for row in self.activities)
		if not planned_start_exists or not planned_end_exists:
			frappe.throw("Activities must include at least one 'Planned Start Time' and one 'Planned End Time' entry.")
		
		self.validate_reviewer()
		self.validate_recurrence_date()
		if self.recurrence_type != "One Time" and (self.monthly_recurrence_based_on != None and self.monthly_recurrence_based_on == "Date"):
			self.validate_recurrence_time()

		if self.status == "In Progress":
			calculate_planned_target(self)
		
		if self.status == "Done":
			calculate_score(self)
	
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

	def before_save(self):
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		key_field_changed = any(
			self.has_value_changed(field)
			for field in [
				"reviewer",
				"report_to",
				"summary",
				"description",
				"assignee",
				"is_critical"
			]
		)

		if not (key_field_changed):
			return

		if key_field_changed and self.owner != frappe.session.user:
			frappe.throw("Only the owner can modify key details of this Work Item.")

		if self.first_mail:
			sent_noti(self.name)

@frappe.whitelist()
def send_for_review(docname, reviewer):
	frappe.db.set_value("Work Item", docname, "status", "Under Review")
	content = f"A work item <b>{docname}</b> has been sent for review.<br><a href='{frappe.utils.get_url()}/app/work-item/{docname}'>View Work Item</a>"
	send_notifications(docname, content, to = [reviewer])

@frappe.whitelist()
def mark_complete(docname):
	doc = frappe.get_doc("Work Item", docname)

	doc.status = "Done"
	doc.append("activities", {
		"action_type": "Actual End Time",
		"time": now_datetime().replace(second=0, microsecond=0)
	})
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def start_now(docname):
	frappe.db.set_value("Work Item", docname, "status", "In Progress")

@frappe.whitelist()
def resend_for_rework(docname, rework_comments, planned_start_date, planned_end_date):
	doc = frappe.get_doc("Work Item", docname)

	doc.status = "To Do"
	doc.rework_count += 1
	doc.append("activities", {
		"action_type": "Planned Start Time",
		"time": get_datetime(planned_start_date).replace(second=0, microsecond=0),
	})
	doc.append("activities", {
		"action_type": "Planned End Time",
		"time": get_datetime(planned_end_date).replace(second=0, microsecond=0),
	})
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", rework_comments)
	content = f"A work item <b>{docname}</b> has been sent for Rework - {rework_comments}.<br><a href='{frappe.utils.get_url()}/app/work-item/{docname}'>View Work Item</a>"
	send_notifications(docname, content, to = [doc.assignee])

def calculate_planned_target(doc):
	planned_start_time = None
	planned_end_time = None
	
	for row in doc.activities:
		if row.action_type == "Planned Start Time":
			if planned_start_time is None or row.time > planned_start_time:
				planned_start_time = row.time
		if row.action_type == "Planned End Time":
			if planned_end_time is None or row.time > planned_end_time:
				planned_end_time = row.time
		
	sent_alert_on = frappe.get_single_value("Work Item Configuration", "sent_reminder_before")
	if planned_start_time and planned_end_time:
		planned_end_time = get_datetime(planned_end_time)

		hr, mm, sec = map(int, sent_alert_on.split(':'))
		total_minutes = hr * 60 + mm
		reminder_delta = timedelta(minutes=total_minutes)
		doc.twenty_percent_reminder_time = planned_end_time - reminder_delta
		doc.twenty_percent_reminder_time = doc.twenty_percent_reminder_time.replace(second=0, microsecond=0)
		doc.twenty_percent_reminder_sent = 0

def ensure_time(value):
	if isinstance(value, timedelta):
		total_seconds = int(value.total_seconds())
		hours = total_seconds // 3600
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		return time(hour=hours, minute=minutes, second=seconds)
	return value

# def send_twenty_percent_reminders():
# 	now = now_datetime().replace(second=0, microsecond=0)
# 	items = frappe.get_all("Work Item", filters={
# 		"status": "In Progress",
# 		"twenty_percent_reminder_sent": 0,
# 		"twenty_percent_reminder_time": ("=", now)
# 	}, fields=["name", "assignee"])

# 	for item in items:
# 		user_email = frappe.db.get_value("User", item.assignee, "email")
# 		if user_email:
# 			frappe.sendmail(
# 				recipients=[user_email],
# 				subject=f"Reminder: Work Item {item.name} nearing deadline",
# 				message=f"You're at 20% remaining time for the Work Item <b>{item.name}</b>. Please plan accordingly.<br><a href='{frappe.utils.get_url()}/app/work-item/{item.name}'>View Work Item</a>",
# 				now=True
# 			)
# 			frappe.db.set_value("Work Item", item.name, "twenty_percent_reminder_sent", 1)
# 		else:
# 			frappe.log_error("Work Item Reminder Error", f"User {item.assignee} does not have a valid email.")

# def send_deadline_reminders():
# 	now = now_datetime().replace(second=0, microsecond=0)
# 	items = frappe.get_all("Work Item", filters={
# 		"status": "In Progress",
# 		"deadline_reminder_sent": 0,
# 		"planned_end": ("=", now)
# 	}, fields=["name", "assignee"])

# 	for item in items:
# 		user_email = frappe.db.get_value("User", item.assignee, "email")
# 		if user_email:
# 			frappe.sendmail(
# 				recipients=[user_email],
# 				subject=f"Work Item {item.name} Deadline Reached",
# 				message=f"The deadline is met for the Work Item <b>{item.name}</b>, but it's still marked as <i>In Progress</i>. Please review it.<br><a href='{frappe.utils.get_url()}/app/work-item/{item.name}'>View Work Item</a>",
# 				now=True
# 			)
# 			frappe.db.set_value("Work Item", item.name, "deadline_reminder_sent", 1)
# 		else:
# 			frappe.log_error("Deadline Reminder Error", f"User {item.assignee} has no valid email.")

def calculate_score(doc):
	if doc.status != "Done":
		return
	
	planned_end_time = None
	actual_end_time = None
	for row in doc.activities:
		if row.action_type == "Planned End Time":
			if planned_end_time is None or row.time > planned_end_time:
				planned_end_time = row.time
		elif row.action_type == "Actual End Time":
			if actual_end_time is None or row.time > actual_end_time:
				actual_end_time = row.time
	
	planned_end_time = get_datetime(planned_end_time)
	actual_end_time = get_datetime(actual_end_time)

	if not (planned_end_time and actual_end_time):
		return
	
	if actual_end_time <= planned_end_time:
		doc.score = 0
		return
	
	config = frappe.get_single("Work Item Configuration")
	total_delay_minutes = (actual_end_time - planned_end_time).total_seconds() / 60
	if total_delay_minutes < 1440:
		penalty = total_delay_minutes * config.penalty_per_minute
	else:
		penalty = ((total_delay_minutes // 1440) * config.penalty_points_per_day) + (( total_delay_minutes % 1440) * config.penalty_per_minute)
	max_points = config.max_delay_penalty if doc.rework_count == 0 else config.max_rework_penalty
	doc.score = -min(penalty, max_points)

@frappe.whitelist()
def sent_noti(work_item):
	doc = frappe.get_doc("Work Item", work_item)
	to = []
	if not doc.first_mail:
		if doc.assignee:
			to.append(doc.assignee)
		content = f"A work item <b>{doc.name}</b> has been created and assigned to you.<br><a href='{frappe.utils.get_url()}/app/work-item/{doc.name}'>View Work Item</a>"
		send_notifications(doc.name, content, to)
		doc.first_mail = 1
		doc.save(ignore_permissions=True)
	else:
		if doc.reviewer:
			to.append(doc.reviewer)
		if doc.assignee:
			to.append(doc.assignee)
		if doc.report_to:
			to.append(doc.report_to)
		content = f"A work item <b>{doc.name}</b> has been updated.<br><a href='{frappe.utils.get_url()}/app/work-item/{doc.name}'>View Work Item</a>"
		send_notifications(doc.name, content, to)