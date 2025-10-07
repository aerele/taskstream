# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

from datetime import datetime, time, timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, get_weekday, now_datetime


class WorkItem(Document):
	def validate(self):
		self.update_revision_count()
		self.validate_reviewer()
		self.validate_recurrence_date()
		self.validate_recurrence_time()

		if self.status == "In Progress" and self.start_time and self.estimated_duration:
			calculate_planned_target(self)

		if self.status == "Done":
			calculate_score(self)

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

	def before_save(self):
		if self.isnotfirstsave == 0:
			calculate_remainders(self)


@frappe.whitelist()
def send_for_review(docname):
	doc = frappe.get_doc("Work Item", docname)

	reviewer_email = frappe.db.get_value("User", doc.reviewer, "email")
	if not reviewer_email:
		frappe.throw("Reviewer does not have a valid email.")

	frappe.sendmail(
		recipients=[reviewer_email],
		subject=f"Review Requested for Work Item: {doc.name}",
		message=f"A critical work item has been submitted for your review.<br><br><b>Name:</b> {doc.name}<br><b>Assignee:</b> {doc.assignee}<br><br><a href='{frappe.utils.get_url()}/app/work-item/{doc.name}'>View Work Item</a>",
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
	doc.start_time = now_datetime()
	doc.save(ignore_permissions=True)
	check_onetime(docname)


@frappe.whitelist()
def resend_for_rework(docname):
	doc = frappe.get_doc("Work Item", docname)

	doc.status = "Rework Needed"
	doc.save(ignore_permissions=True)


def check_onetime(docname):
	doc = frappe.get_doc("Work Item", docname)
	if doc.recurrence_type == "One Time":
		doc.isnotfirstsave = 1
		doc.next_remainders = []
		if doc.planned_end and doc.planned_end > now_datetime():
			doc.append("next_remainders", {"next_remainder": doc.planned_end})
		doc.save(ignore_permissions=True)


def calculate_monthly_days(doc, row, current_date, days, now=None, end_date=None):
	for _ in range(1, 8):
		if get_weekday(current_date) == row.weekday:
			for rt in doc.recurrence_time:
				hour = int(rt.recurrence_time)
				remainder_time = datetime.combine(current_date, time(hour))
				if remainder_time > now and remainder_time.date() <= end_date:
					doc.append("next_remainders", {"next_remainder": remainder_time})
			break
		current_date = add_to_date(current_date, days=days)


def calculate_remainders(doc):
	doc.isnotfirstsave = 1
	now = now_datetime().replace(minute=0, second=0, microsecond=0)
	end_date = get_datetime(doc.repeat_until).date()
	current_date = now.date()

	if doc.recurrence_type == "Daily":
		if doc.recurrence_time and doc.repeat_until:
			doc.next_remainders = []
			while current_date <= end_date:
				for rt in doc.recurrence_time:
					hour = int(rt.recurrence_time)
					remainder_time = datetime.combine(current_date, time(hour))
					if remainder_time > now:
						doc.append("next_remainders", {"next_remainder": remainder_time})
				current_date += timedelta(days=1)
	elif doc.recurrence_type == "Weekly":
		if doc.recurrence_day and doc.recurrence_time and doc.repeat_until:
			doc.next_remainders = []
			frequency = doc.recurrence_frequency or 1

			while current_date <= end_date:
				weekday = current_date.weekday()
				weekday_map = {
					"Monday": 0,
					"Tuesday": 1,
					"Wednesday": 2,
					"Thursday": 3,
					"Friday": 4,
					"Saturday": 5,
					"Sunday": 6,
				}

				selected_days = [weekday_map.get(d.weekday) for d in doc.recurrence_day if d.weekday]

				if weekday in selected_days:
					for rt in doc.recurrence_time:
						hour = int(rt.recurrence_time)
						remainder_time = datetime.combine(current_date, time(hour))

						if remainder_time > now:
							doc.append("next_remainders", {"next_remainder": remainder_time})
				current_date += timedelta(days=1)
				if current_date.weekday() == 0:
					current_date += timedelta(weeks=frequency - 1)
	elif doc.recurrence_type == "Monthly":
		rf = doc.recurrence_frequency or 1
		if doc.monthly_recurrence_based_on == "Day":
			doc.next_remainders = []

			for row in doc.recurrence_day_occurrence:
				if row.week_order == "First":
					current_date = now.replace(day=1)
					while current_date.date() <= end_date:
						calculate_monthly_days(doc, row, current_date, 1, now, end_date)
						current_date = add_to_date(current_date, months=rf)
				elif row.week_order == "Second":
					current_date = now.replace(day=7)
					while current_date.date() <= end_date:
						calculate_monthly_days(doc, row, current_date, 1, now, end_date)
						current_date = add_to_date(current_date, months=rf)
				elif row.week_order == "Third":
					current_date = now.replace(day=14)
					while current_date.date() <= end_date:
						calculate_monthly_days(doc, row, current_date, 1, now, end_date)
						current_date = add_to_date(current_date, months=rf)
				elif row.week_order == "Fourth":
					current_date = now.replace(day=21)
					while current_date.date() <= end_date:
						calculate_monthly_days(doc, row, current_date, 1, now, end_date)
						current_date = add_to_date(current_date, months=rf)
				elif row.week_order == "Last":
					current_date = now.replace(day=1)
					while current_date.date() <= end_date:
						next_month = add_to_date(current_date, months=1)
						last_day = add_to_date(next_month, days=-1).day
						current_date = current_date.replace(day=last_day)
						calculate_monthly_days(doc, row, current_date, -1, now, end_date)
						current_date = add_to_date(current_date, months=rf)
						current_date = current_date.replace(day=1)
		elif doc.monthly_recurrence_based_on == "Date":
			rf = doc.recurrence_frequency or 1
			doc.next_remainders = []
			while current_date <= end_date:
				for row in doc.recurrence_date:
					current_date = current_date.replace(day=row.recurrence_date)
					for rt in doc.recurrence_time:
						hour = int(rt.recurrence_time)

						remainder_time = datetime.combine(current_date, time(hour))
						if remainder_time > now and remainder_time.date() <= end_date:
							doc.append("next_remainders", {"next_remainder": remainder_time})
				current_date = add_to_date(current_date, months=rf)
	elif doc.recurrence_type == "Yearly":
		rf = doc.recurrence_frequency or 1
		while current_date <= end_date:
			for m in doc.recurrence_month:
				for rd in doc.recurrence_date:
					for rt in doc.recurrence_time:
						try:
							hour = int(rt.recurrence_time)
							r_time = current_date.replace(month=int(m.month), day=rd.recurrence_date)
							remainder_time = datetime.combine(r_time, time(hour))
						except ValueError:
							continue
						if remainder_time >= now and remainder_time.date() <= end_date:
							doc.append("next_remainders", {"next_remainder": remainder_time})

			current_date = add_to_date(current_date, years=rf)


def calculate_planned_target(doc):
	planned_start = get_datetime(doc.start_time)
	duration_hours = float(doc.estimated_duration or 0)
	if not planned_start or not duration_hours:
		return

	employee = frappe.db.get_value(
		"Employee", {"user_id": doc.assignee}, ["name", "default_shift"], as_dict=True
	)
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

	doc.planned_end = current_dt.replace(second=0, microsecond=0)

	reminder_delta = timedelta(seconds=duration_hours * 3600 * 0.20)
	doc.twenty_percent_reminder_time = current_dt - reminder_delta
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


def send_twenty_percent_reminders():
	now = now_datetime().replace(second=0, microsecond=0)
	items = frappe.get_all(
		"Work Item",
		filters={
			"status": "In Progress",
			"twenty_percent_reminder_sent": 0,
			"twenty_percent_reminder_time": ("=", now),
		},
		fields=["name", "assignee"],
	)

	for item in items:
		user_email = frappe.db.get_value("User", item.assignee, "email")
		if user_email:
			frappe.sendmail(
				recipients=[user_email],
				subject=f"Reminder: Work Item {item.name} nearing deadline",
				message=f"You're at 20% remaining time for the Work Item <b>{item.name}</b>. Please plan accordingly.<br><a href='{frappe.utils.get_url()}/app/work-item/{item.name}'>View Work Item</a>",
				now=True,
			)
			frappe.db.set_value("Work Item", item.name, "twenty_percent_reminder_sent", 1)
		else:
			frappe.log_error("Work Item Reminder Error", f"User {item.assignee} does not have a valid email.")


def send_deadline_reminders():
	now = now_datetime().replace(second=0, microsecond=0)
	items = frappe.get_all(
		"Work Item",
		filters={"status": "In Progress", "deadline_reminder_sent": 0, "planned_end": ("=", now)},
		fields=["name", "assignee"],
	)

	for item in items:
		user_email = frappe.db.get_value("User", item.assignee, "email")
		if user_email:
			frappe.sendmail(
				recipients=[user_email],
				subject=f"Work Item {item.name} Deadline Reached",
				message=f"The deadline is met for the Work Item <b>{item.name}</b>, but it's still marked as <i>In Progress</i>. Please review it.<br><a href='{frappe.utils.get_url()}/app/work-item/{item.name}'>View Work Item</a>",
				now=True,
			)
			frappe.db.set_value("Work Item", item.name, "deadline_reminder_sent", 1)
		else:
			frappe.log_error("Deadline Reminder Error", f"User {item.assignee} has no valid email.")


def calculate_score(doc):
	if doc.status == "Done":
		doc.score = 60

		if doc.estimated_duration and doc.actual_duration:
			estimated = doc.estimated_duration
			actual = doc.actual_duration
			if actual > estimated:
				return
			revisions = doc.revision_count or 0

			if actual == 0:
				extra_time_ratio = 0
			else:
				extra_time_ratio = max((estimated - actual) / actual, 0)

			penalty_percent = revisions * extra_time_ratio
			on_time_score = 40 - (penalty_percent * 40)
			on_time_score = max(min(on_time_score, 40), 0)

			doc.score += round(on_time_score, 2)


def send_remainder():
	now = now_datetime().replace(minute=0, second=0, microsecond=0)
	items = frappe.get_all(
		"Work Item",
		filters={
			"status": "To Do" or "In Progress",
		},
		fields=["name"],
	)
	for item in items:
		wi = frappe.get_doc("Work Item", item.name)
		for row in wi.next_remainders:
			if row.next_remainder and row.next_remainder == now:
				user_mail = frappe.db.get_value("User", wi.assignee, "email")
				if user_mail:
					frappe.sendmail(
						recipients=[user_mail],
						subject=f"Remainder: Work Item {wi.name} is scheduled for now",
						message=f"The Work Item <b>{wi.name}</b> is scheduled for now.<br><a href='{frappe.utils.get_url()}/app/work-item/{wi.name}'>View Work Item</a>",
						now=True,
					)
				wi.remove("next_remainders", row.name)
				wi.status = "Done"
				wi.save(ignore_permissions=True)
				frappe.db.commit()

				new_wi = frappe.copy_doc(wi)
				new_wi.status = "To Do"
				new_wi.insert(ignore_permissions=True)
				frappe.db.commit()
				break
