# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import timedelta, datetime, time
from frappe.utils import now_datetime, get_datetime
from taskstream.taskstream import send_notifications

class WorkItem(Document):
	def validate(self):
		if self.recurrence_type == "One Time":
			planned_end_exists = any(row.action_type == "Target End Date" for row in self.activities)
			if not planned_end_exists:
				frappe.throw("Activities must include one 'Target End Date' entry.")
		
		self.validate_reviewer()
		self.validate_recurrence_date()
		if self.recurrence_type != "One Time" and (self.monthly_recurrence_based_on != None and self.monthly_recurrence_based_on == "Date"):
			self.validate_recurrence_time()

		if self.status == "In Progress":
			calculate_planned_target(self)
		
		if self.status == "Done":
			calculate_score(self)
			if self.work_flow_template:
				create_sub_task(self, self.idx)
	
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
				"review_required"
			]
		)

		if not (key_field_changed):
			return

		if key_field_changed and self.owner != frappe.session.user:
			frappe.throw("Only the owner can modify key details of this Work Item.")

		if self.first_mail:
			sent_noti(self.name)
		
	def after_insert(self):
		if self.recurrence_type == "One Time":
			return
		creation_limit = frappe.get_single_value("Work Item Configuration", "recurrence_creation_limit")

		start_date = now_datetime().date()
		end_date = datetime.strptime(self.repeat_until, "%Y-%m-%d").date()
		max_creation_date = start_date + timedelta(days=creation_limit)
		end_date = min(end_date, max_creation_date)
		values = _get_valid_dates(self, start_date, end_date)
		
		for value in values:
			create_work_item_recurrences(self, value[0], value[1])

		frappe.db.commit()

def _get_valid_dates(self, start_date, end_date):
	import datetime as dt
	import calendar

	def _parse_recurrence_time(recurrence_time):
		try:
			if isinstance(recurrence_time, timedelta):
				return recurrence_time
			hours = int(recurrence_time)
			return timedelta(hours=hours)
		except (ValueError, TypeError):
			return timedelta(hours=0)
	
	parsed_times = [_parse_recurrence_time(t.recurrence_time) for t in self.recurrence_time]
	valid_dates = []
	
	if self.recurrence_type == "Daily":
		current_date = start_date
		while current_date <= end_date:
			for time_delta in parsed_times:
				valid_dates.append((current_date, time_delta))
			current_date += timedelta(days=1)
	
	elif self.recurrence_type == "Weekly":
		days_map = {
			"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
			"Friday": 4, "Saturday": 5, "Sunday": 6
		}
		
		target_days = [days_map[d.weekday] for d in self.recurrence_day if d.weekday in days_map]
		frequency = int(self.recurrence_frequency or 1)
		
		current_date = start_date
		while current_date <= end_date:
			if current_date.weekday() in target_days:
				weeks_diff = (current_date - start_date).days // 7
				if weeks_diff % frequency == 0:
					for time_delta in parsed_times:
						valid_dates.append((current_date, time_delta))
			current_date += timedelta(days=1)
	
	elif self.recurrence_type == "Monthly":
		frequency = int(self.recurrence_frequency or 1)
		current_month = start_date.month
		current_year = start_date.year
		while dt.date(current_year, current_month, 1) <= end_date:
			if self.monthly_recurrence_based_on == "Date":
				for row in self.recurrence_date:
					last_day = calendar.monthrange(current_year, current_month)[1]
					actual_day = min(row.recurrence_date, last_day)
					generated_date = dt.date(current_year, current_month, actual_day)

					if start_date < generated_date <= end_date:
						for time_delta in parsed_times:
							if (generated_date, time_delta) not in valid_dates:
								valid_dates.append((generated_date, time_delta))

				current_month += frequency
				while current_month > 12:
					current_month -= 12
					current_year += 1
			if self.monthly_recurrence_based_on == "Day":
				for row in self.recurrence_day_occurrence:
					order = row.week_order
					week_day = row.weekday
					generated_date = _get_nth_weekday(current_year, current_month, week_day, order)
					
					if start_date < generated_date <= end_date:
						for time_delta in parsed_times:
							if (generated_date, time_delta) not in valid_dates:
								valid_dates.append((generated_date, time_delta))
								
				current_month += frequency
				while current_month > 12:
					current_month -= 12
					current_year += 1
					
	elif self.recurrence_type == "Yearly":
		frequency = int(self.recurrence_frequency or 1)
		month_map = {
			"January": 1, "February": 2, "March": 3, "April": 4,
			"May": 5, "June": 6, "July": 7, "August": 8,
			"September": 9, "October": 10, "November": 11, "December": 12
		}
		
		days = [int(d.recurrence_date) for d in self.recurrence_date]
		months = [m.month for m in self.recurrence_month]

		years = [year for year in range(start_date.year, end_date.year + 1, frequency)]
		date_combinations = [(year, month_map.get(month), day) for year in years for month in months for day in days]
		for y, m, d in date_combinations:
			last_day = calendar.monthrange(y, m)[1]
			actual_day = min(d, last_day)
			generated_date = dt.date(y, m, actual_day)
			if start_date < generated_date <= end_date:
				for time_delta in parsed_times:
					valid_dates.append((generated_date, time_delta))

		
	return check_date_validity(self, valid_dates)

def check_date_validity(self, valid_dates):
	try:
		skip_map = {
			"Holidays": 0,
			"Weekdays": 4,
		}
		dates=[]
		settings = frappe.get_single("Work Item Configuration")
		skip_type = skip_map.get(settings.skip_holidays_based_on)
		if skip_type == 4 and settings.include_saturday:
			skip_type = 5
			
		if skip_type == 0:
			holiday_doc = settings.default_holiday or frappe.db.get_value("Employee", {"user_id": self.assignee}, "holiday_list") or None
			if not holiday_doc:
				skip_type = 5 if settings.include_saturday_nonemp else 4
				
		if frappe.db.exists("Module Def", "Setup") and skip_type == 0 and holiday_doc:
			for date, time in valid_dates:
				if frappe.db.exists("Holiday", {"holiday_date": date, "parent": holiday_doc}):
					while True:
						if not frappe.db.exists("Holiday", {"holiday_date": date, "parent": holiday_doc}):
							break
						date -= timedelta(days=1)
				if (date, time) not in dates and date <= get_datetime(self.repeat_until).date():
					dates.append((date, time))
		else:
			for date, time in valid_dates:
				if date.weekday() <= skip_type:
					dates.append((date, time))
		
		return dates
	except Exception as e:
		frappe.log_error(f"Error in checking date validity: {str(e)}", "Work Item Date Validity Error")
		frappe.db.commit()

def _get_nth_weekday(year, month, weekday, occurrence):
	days_map = {
		"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
		"Friday": 4, "Saturday": 5, "Sunday": 6
	}
	week_order_map = {
		"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Last": 5
	}
	from datetime import datetime
	weekday = days_map.get(weekday)
	occurrence = week_order_map.get(occurrence)
	first_day = datetime(year, month, 1)
	
	days_until_target = (weekday - first_day.weekday()) % 7
	first_occurrence = first_day + timedelta(days=days_until_target)
	
	if occurrence <= 4:
		target_date = first_occurrence + timedelta(weeks=occurrence - 1)
	else:
		target_date = first_occurrence + timedelta(weeks=3)
		if (target_date + timedelta(weeks=1)).month == month:
			target_date += timedelta(weeks=1)
	
	if target_date.month != month:
		return None
	
	return target_date.date()


def create_work_item_recurrences(wi_doc, date, recurrence_time):
	new_wi = frappe.copy_doc(wi_doc)
	new_wi.name = None
	new_wi.recurrence_type = "One Time"
	new_wi.recurrence_date = []
	new_wi.recurrence_time = []
	new_wi.activities = []
	
	if isinstance(recurrence_time, timedelta):
		time_delta = recurrence_time
	else:
		try:
			time_delta = timedelta(hours=int(recurrence_time))
		except (ValueError, TypeError):
			time_delta = timedelta(hours=0)
	
	new_wi.append("activities", {
		"action_type": "Target End Date",
		"time": datetime.combine(date, datetime.min.time()) + time_delta,
	})
	new_wi.status = "To Do"
	new_wi.reference_doctype = "Work Item"
	new_wi.reference_document = wi_doc.name
	new_wi.owner = wi_doc.owner
	new_wi.save(ignore_permissions=True)
	return new_wi


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
def resend_for_rework(docname, rework_comments, target_end_date):
	doc = frappe.get_doc("Work Item", docname)
	doc.status = "To Do"
	doc.rework_count += 1
	doc.append("activities", {
		"action_type": "Target End Date",
		"time": get_datetime(target_end_date).replace(second=0, microsecond=0),
	})
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", rework_comments)
	content = f"A work item <b>{docname}</b> has been sent for Rework - {rework_comments}.<br><a href='{frappe.utils.get_url()}/app/work-item/{docname}'>View Work Item</a>"
	send_notifications(docname, content, to = [doc.assignee])

def calculate_planned_target(doc):
	planned_end_time = None
	
	for row in doc.activities:
		if row.action_type == "Target End Date":
			if planned_end_time is None or row.time > planned_end_time:
				planned_end_time = row.time
		
	sent_alert_on = frappe.get_single_value("Work Item Configuration", "sent_reminder_before")
	if planned_end_time:
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
		if row.action_type == "Target End Date":
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

def create_sub_task(self, idx):
	if frappe.db.exists("Work Flow Template Item", {"parent": self.work_flow_template, "idx":idx+1}):
		task = frappe.get_doc("Work Flow Template Item", {"parent": self.work_flow_template, "idx":idx+1})
		doc = frappe.copy_doc(self)
		doc.activities = []
		doc.status = "To Do"
		doc.summary = task.task_name
		doc.idx = idx + 1
		doc.description = task.task_description
		doc.assignee = task.assignee or self.assignee
		hours_as_float = task.target_end_date_time.total_seconds() / 3600

		doc.append("activities", {
			"action_type": "Target End Date",
			"time": (now_datetime() + timedelta(hours=hours_as_float)).replace(second=0, microsecond=0)
		})
		doc.save(ignore_permissions=True)
		sent_noti(doc.name)