# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import json
from datetime import datetime, time, timedelta
from functools import wraps

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import get_datetime, getdate, now_datetime

from taskstream.taskstream import send_notifications
from taskstream.taskstream.doctype.work_item_score_summary.work_item_score_summary import (
	create_summary_record,
)


def safe_exec(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except Exception as e:
			if hasattr(frappe, "ValidationError") and isinstance(e, frappe.ValidationError):
				raise
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{func.__name__} Error")
			except Exception:
				pass
			frappe.throw("An error occurred, please contact admin")

	return wrapper


class WorkItem(Document):
	def autoname(self):
		is_recurring_selected = self.recurrence_type not in ("One Time", "Recurring Instance")
		if is_recurring_selected and not getattr(self, "reference_document", None):
			self.name = make_autoname("WIM-.####", self.doctype)
		else:
			self.name = make_autoname("WI-.####", self.doctype)

	@safe_exec
	def validate(self):
		if self.is_new():
			if self.recurrence_type == "One Time" or self.recurrence_type == "Recurring Instance":
				is_end_date_not_in_past(self.target_end_date)
			else:
				is_end_date_not_in_past(self.repeat_until)
		if not self.assigned_on:
			self.assigned_on = now_datetime().date()
		if self.recurrence_type in ["One Time", "Recurring Instance"]:
			planned_end_exists = (
				self.target_end_date
			)  # any(row.action_type == "Target End Date" for row in self.activities)
			if not planned_end_exists:
				frappe.throw("Activities must include one 'Target End Date' entry.")

			self.validate_reviewer()
			self.validate_recurrence_date()
			if (
				self.recurrence_type not in ["One Time", "Recurring Instance"]
				and self.monthly_recurrence_based_on == "Date"
			):
				self.validate_recurrence_time()

		if self.status == "Open":
			calculate_planned_target(self)

		calculate_score(self, "Work Item Update")
		if self.work_flow_template and self.work_flow:
			if self.idx == 0:
				self.idx = 1
			if self.status == "Done":
				create_sub_task(self, self.idx)

		if self.recurrence_type == "Recurring Instance" and self.status == "Done":
			self.create_work_item_recurrences()

	@safe_exec
	def create_work_item_recurrences(self):
		if not (self.reference_document and self.reference_doctype):
			return
		valid_dates = json.loads(self.valid_dates) if self.valid_dates else []
		valid_dates = [
			(datetime.fromisoformat(d["date"]).date(), timedelta(seconds=d["time_seconds"]))
			for d in valid_dates
		]
		# current_slot = None
		# for rows in self.activities:
		# 	if rows.action_type == "Target End Date":
		# 		date_time = rows.time
		# 		date = date_time.date()
		# 		t = date_time.time()
		# 		target_time = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
		# 		current_slot = (date, target_time)

		target_end_datetime = get_datetime(self.target_end_date)
		date = target_end_datetime.date()
		t = target_end_datetime.time()
		target_time = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
		current_slot = (date, target_time)

		if current_slot and current_slot in valid_dates:
			current_index = valid_dates.index(current_slot)
			for next_date in valid_dates[current_index + 1 :]:
				target_end_datetime = datetime.combine(next_date[0], datetime.min.time()) + next_date[1]
				existing_wi = bool(
					frappe.db.exists(
						"Work Item",
						{
							"reference_document": self.reference_document,
							"reference_doctype": self.reference_doctype,
							"target_end_date": target_end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
							"summary": self.summary,
							"description": self.description,
						},
					)
				)
				if not existing_wi:
					create_work_item_recurrences(self, next_date[0], next_date[1])
					break

	@safe_exec
	def validate_reviewer(self):
		if self.reviewer == self.assignee:
			frappe.throw("Assignee and Reviewer cannot be same")

	@safe_exec
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

	@safe_exec
	def validate_recurrence_time(self):
		seen = set()
		for row in self.recurrence_time:
			val = row.recurrence_time
			if val is None:
				continue
			if val in seen:
				frappe.throw("Each recurrence time must be unique!")
			seen.add(val)

	@safe_exec
	def before_save(self):
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		key_field_changed = any(
			self.has_value_changed(field)
			for field in ["reviewer", "reporter", "summary", "description", "assignee", "review_required"]
		)

		if not (key_field_changed):
			return

		if frappe.session.user not in [self.reporter, self.requester]:
			frappe.throw("Only the owner can modify key details of this Work Item.")

		if self.first_mail:
			sent_noti(self.name)

	@safe_exec
	def after_insert(self):
		if self.recurrence_type in ["One Time", "Recurring Instance"]:
			return
		creation_limit = frappe.get_single_value("Work Item Configuration", "recurrence_creation_limit")

		start_date = getdate(self.start_from)
		end_date = datetime.strptime(self.repeat_until, "%Y-%m-%d").date()
		max_creation_date = start_date + timedelta(days=creation_limit)
		values = _get_valid_dates(self, start_date, end_date)

		serialized_valid_dates = []
		serialized_valid_dates.extend(
			{
				"date": valid_date.isoformat(),
				"time_seconds": (
					int(recurrence_time.total_seconds()) if isinstance(recurrence_time, timedelta) else 0
				),
			}
			for valid_date, recurrence_time in values
		)
		self.db_set("valid_dates", json.dumps(serialized_valid_dates))

		creatable_values = [value for value in values if value[0] <= max_creation_date]

		if len(creatable_values) > creation_limit:
			creatable_values = creatable_values[:creation_limit]
		if len(creatable_values) > 0:
			for value in creatable_values:
				create_work_item_recurrences(self, value[0], value[1])
		else:
			create_work_item_recurrences(self, values[0][0], values[0][1])

		frappe.db.commit()


def is_end_date_not_in_past(date):
	now = now_datetime()
	if get_datetime(date) < now:
		frappe.throw("End date cannot be in the past.")


def _get_valid_dates(self, start_date, end_date):
	import calendar
	import datetime as dt

	def _parse_recurrence_time(recurrence_time):
		try:
			if isinstance(recurrence_time, str) and ":" in recurrence_time:
				t = recurrence_time.split(":")
				return timedelta(hours=int(t[0]), minutes=int(t[1]), seconds=0)
			else:
				return timedelta(hours=int(recurrence_time))
		except (ValueError, TypeError, IndexError):
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
			"Monday": 0,
			"Tuesday": 1,
			"Wednesday": 2,
			"Thursday": 3,
			"Friday": 4,
			"Saturday": 5,
			"Sunday": 6,
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
			"January": 1,
			"February": 2,
			"March": 3,
			"April": 4,
			"May": 5,
			"June": 6,
			"July": 7,
			"August": 8,
			"September": 9,
			"October": 10,
			"November": 11,
			"December": 12,
		}

		days = [int(d.recurrence_date) for d in self.recurrence_date]
		months = [m.month for m in self.recurrence_month]

		years = list(range(start_date.year, end_date.year + 1, frequency))
		date_combinations = [
			(year, month_map.get(month), day) for year in years for month in months for day in days
		]
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
		dates = []
		now = now_datetime()

		def _as_datetime(date_value, time_value):
			base = datetime.combine(date_value, datetime.min.time())
			if isinstance(time_value, timedelta):
				return base + time_value
			if isinstance(time_value, time):  # time is class
				return datetime.combine(date_value, time_value)
			return base

		settings = frappe.get_single("Work Item Configuration")
		skip_type = skip_map.get(settings.skip_holidays_based_on)
		if skip_type == 4 and settings.include_saturday:
			skip_type = 5

		if skip_type == 0:
			holiday_doc = (
				settings.default_holiday
				or frappe.db.get_value("Employee", {"user_id": self.assignee}, "holiday_list")
				or None
			)
			if not holiday_doc:
				skip_type = 5 if settings.include_saturday_nonemp else 4

		if frappe.db.exists("Module Def", "Setup") and skip_type == 0 and holiday_doc:
			for date, time in valid_dates:
				if _as_datetime(date, time) < now:
					continue
				if frappe.db.exists("Holiday", {"holiday_date": date, "parent": holiday_doc}):
					while True:
						if not frappe.db.exists("Holiday", {"holiday_date": date, "parent": holiday_doc}):
							break
						date -= timedelta(days=1)
				if _as_datetime(date, time) < now:
					continue
				if (date, time) not in dates and date <= get_datetime(self.repeat_until).date():
					dates.append((date, time))
		else:
			for date, time in valid_dates:
				if _as_datetime(date, time) < now:
					continue
				while True:
					if date.weekday() <= skip_type:
						break
					date -= timedelta(days=1)
				if _as_datetime(date, time) < now:
					continue
				if (date, time) not in dates and date <= get_datetime(self.repeat_until).date():
					dates.append((date, time))

		return dates
	except Exception as e:
		frappe.log_error(f"Error in checking date validity: {e!s}", "Work Item Date Validity Error")
		frappe.db.commit()


def _get_nth_weekday(year, month, weekday, occurrence):
	days_map = {
		"Monday": 0,
		"Tuesday": 1,
		"Wednesday": 2,
		"Thursday": 3,
		"Friday": 4,
		"Saturday": 5,
		"Sunday": 6,
	}
	week_order_map = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Last": 5}
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

	return None if target_date.month != month else target_date.date()


def create_work_item_recurrences(wi_doc, date, recurrence_time):
	new_wi = frappe.copy_doc(wi_doc)
	new_wi.name = None
	new_wi.score = 0
	new_wi.rework_count = 0
	new_wi.revision_count = 0
	new_wi.recurrence_frequency = 0
	new_wi.benefit_of_work_done = 100
	new_wi.recurrence_type = "Recurring Instance"
	new_wi.recurrence_date = []
	new_wi.recurrence_time = []
	new_wi.activities = []

	if isinstance(recurrence_time, timedelta):
		time_delta = recurrence_time
	else:
		try:
			if isinstance(recurrence_time, str) and ":" in recurrence_time:
				t = recurrence_time.split(":")
				time_delta = timedelta(hours=int(t[0]), minutes=int(t[1]), seconds=0)
			else:
				time_delta = timedelta(hours=int(recurrence_time))
		except (ValueError, TypeError, IndexError):
			time_delta = timedelta(hours=0)

	# new_wi.append(
	# 	"activities",
	# 	{
	# 		"action_type": "Target End Date",
	# 		"time": datetime.combine(date, datetime.min.time()) + time_delta,
	# 	},
	# )
	new_wi.target_end_date = datetime.combine(date, datetime.min.time()) + time_delta
	new_wi.actual_end_date = None
	new_wi.status = "Open"
	new_wi.reference_doctype = "Work Item"
	new_wi.reference_document = (
		wi_doc.reference_document if wi_doc.recurrence_type == "Recurring Instance" else wi_doc.name
	)
	new_wi.owner = wi_doc.owner
	new_wi.save(ignore_permissions=True)
	return new_wi


@frappe.whitelist()
@safe_exec
def send_for_review(docname, reviewer):
	frappe.db.set_value("Work Item", docname, "status", "Under Review")
	content = f"A work item <b>{docname}</b> has been sent for review.<br><a href='{frappe.utils.get_url()}/app/work-item/{docname}'>View Work Item</a>"
	send_notifications(docname, content, to=[reviewer])


@frappe.whitelist()
@safe_exec
def mark_complete(docname):
	doc = frappe.get_doc("Work Item", docname)
	if doc.benefit_of_work_done < 1 and doc.review_required == 1:
		frappe.throw("Please enter a valid benefit of work done")
	doc.status = "Done"
	doc.actual_end_date = now_datetime().replace(second=0, microsecond=0)
	# doc.append(
	# 	"activities",
	# 	{"action_type": "Actual End Time", "time": now_datetime().replace(second=0, microsecond=0)},
	# )
	doc.save(ignore_permissions=True)


# @frappe.whitelist()
# def start_now(docname):
# 	frappe.db.set_value("Work Item", docname, "status", "In Progress")
# 	frappe.db.set_value("Work Item", docname, "first_mail", 1)


@frappe.whitelist()
@safe_exec
def resend_for_rework(docname, rework_comments, target_end_date):
	doc = frappe.get_doc("Work Item", docname)
	doc.status = "Open"
	doc.rework_count += 1
	if target_end_date:
		doc.target_end_date = get_datetime(target_end_date).replace(second=0, microsecond=0)
		# doc.append(
		# 	"activities",
		# 	{
		# 		"action_type": "Target End Date",
		# 		"time": get_datetime(target_end_date).replace(second=0, microsecond=0),
		# 	},
		# )
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", rework_comments)
	content = f"A work item <b>{docname}</b> has been sent for Rework - {rework_comments}.<br><a href='{frappe.utils.get_url()}/app/work-item/{docname}'>View Work Item</a>"
	send_notifications(docname, content, to=[doc.assignee])


@safe_exec
def calculate_planned_target(doc):
	# planned_end_time = None

	# for row in doc.activities:
	# 	if row.action_type == "Target End Date" and (planned_end_time is None or row.time > planned_end_time):
	# 		planned_end_time = row.time

	if planned_end_time := doc.target_end_date:
		planned_end_time = get_datetime(planned_end_time)
		sent_alert_on = frappe.get_single_value("Work Item Configuration", "sent_reminder_before")
		hr, mm, sec = [int(float(x)) for x in sent_alert_on.split(":")]
		total_minutes = hr * 60 + mm
		reminder_delta = timedelta(minutes=total_minutes)
		doc.twenty_percent_reminder_time = planned_end_time - reminder_delta
		doc.twenty_percent_reminder_time = doc.twenty_percent_reminder_time.replace(second=0, microsecond=0)
		doc.twenty_percent_reminder_sent = 0


@safe_exec
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


@safe_exec
def calculate_score(doc, type):
	# if doc.is_new():
	# 	return
	# if doc.status != "Done":
	# 	return

	# planned_end_time = None
	# actual_end_time = None
	# for row in doc.activities:
	# if row.action_type == "Target End Date":
	# 	if planned_end_time is None or row.time > planned_end_time:
	# 		planned_end_time = row.time
	# elif row.action_type == "Actual End Time":
	# if actual_end_time is None or row.time > actual_end_time:
	# 	actual_end_time = row.time

	planned_end_time = get_datetime(doc.target_end_date) if doc.target_end_date else None
	actual_end_time = get_datetime(doc.actual_end_date) if doc.actual_end_date else now_datetime()

	if not planned_end_time:
		return

	# if actual_end_time <= planned_end_time:
	# 	doc.score = 0
	# 	return

	if actual_end_time:
		config = frappe.get_single("Work Item Configuration")
		total_delay_minutes = (actual_end_time - planned_end_time).total_seconds() / 60
		if actual_end_time <= planned_end_time:
			delay_penalty = 0
		elif total_delay_minutes < 1440:
			delay_penalty = total_delay_minutes * config.penalty_per_minute
		else:
			delay_penalty = ((total_delay_minutes // 1440) * config.penalty_points_per_day) + (
				(total_delay_minutes % 1440) * config.penalty_per_minute
			)
		delay_penalty = min(delay_penalty, config.max_delay_penalty)
	else:
		delay_penalty = 0
	benefit_penalty = _get_benefit_penelty(doc.benefit_of_work_done, config.completion_score)
	revision_penalty = ((doc.revision_count or 0) / config.max_allowed_revision) * config.revision_impact
	rework_penalty = ((doc.rework_count or 0) / config.max_allowed_rework) * config.rework_impact
	rework_penalty = min(rework_penalty, config.max_rework_penalty)
	total_score = 0 - benefit_penalty - delay_penalty - revision_penalty - rework_penalty
	doc.score = max(total_score, -100)
	if doc.is_new():
		return
	doc.score_summary = score_summary(
		delay_penalty,
		rework_penalty,
		revision_penalty,
		benefit_penalty,
		doc.score,
		doc.target_end_date,
		doc.actual_end_date,
		total_delay_minutes,
		config.penalty_per_minute,
		doc.rework_count,
		config.rework_impact,
		config.max_allowed_rework,
		config.max_rework_penalty,
		doc.revision_count,
		config.revision_impact,
		config.max_allowed_revision,
		max_delay_points=config.max_delay_penalty,
		benefit_of_work_done=doc.benefit_of_work_done,
		completion_score=config.completion_score,
	)
	# run create_summary_record if type = Scheduled Job or if there are changes in score, status, rework_count, revision_count, target_end_date (check with data before save)
	if type == "Scheduled Job" or (
		type == "Work Item Update"
		and any(
			doc.has_value_changed(f)
			for f in ("score", "status", "rework_count", "revision_count", "target_end_date")
		)
	):
		create_summary_record(doc.score_summary, doc.name, doc.score, type)


@frappe.whitelist()
@safe_exec
def recalculate_score(docname):
	doc = frappe.get_doc("Work Item", docname)
	calculate_score(doc, "Work Item Update")
	doc.save()


@safe_exec
def _get_benefit_penelty(benefit_of_work_done, completion_score):
	benefit_of_work_done = 100 - float(benefit_of_work_done or 0)
	return (benefit_of_work_done / 100) * completion_score


@frappe.whitelist()
@safe_exec
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
		if doc.reporter:
			to.append(doc.reporter)
		content = f"A work item <b>{doc.name}</b> has been updated.<br><a href='{frappe.utils.get_url()}/app/work-item/{doc.name}'>View Work Item</a>"
		send_notifications(doc.name, content, to)


@safe_exec
def create_sub_task(self, idx):
	if frappe.db.exists("Work Flow Template Item", {"parent": self.work_flow_template, "idx": idx + 1}):
		task = frappe.get_doc("Work Flow Template Item", {"parent": self.work_flow_template, "idx": idx + 1})
		doc = frappe.copy_doc(self)
		doc.activities = []
		doc.status = "Open"
		doc.summary = task.task_name
		doc.idx = idx + 1
		doc.description = task.task_description
		doc.assignee = task.assignee or self.assignee  # TODO: implementation based on role
		hours_as_float = task.target_end_date_time.total_seconds() / 3600

		# doc.append(
		# 	"activities",
		# 	{
		# 		"action_type": "Target End Date",
		# 		"time": (now_datetime() + timedelta(hours=hours_as_float)).replace(second=0, microsecond=0),
		# 	},
		# )
		doc.target_end_date = (now_datetime() + timedelta(hours=hours_as_float)).replace(
			second=0, microsecond=0
		)
		doc.save(ignore_permissions=True)
		sent_noti(doc.name)


@frappe.whitelist()
@safe_exec
def update_target_end_on_start_date_change(work_flow_template, start_date_time):
	duration = frappe.get_value(
		"Work Flow Template Item", {"parent": work_flow_template, "idx": 1}, "target_end_date_time"
	)
	if duration and start_date_time:
		target_end = get_datetime(start_date_time) + duration
		return target_end.replace(second=0, microsecond=0)


@frappe.whitelist()
@safe_exec
def time_extension_request(doc, reason, req_target_date_time):
	doc = frappe.get_doc("Work Item", doc)
	to = []
	# for row in doc.activities:
	# 	if row.action_type == "Target End Date":
	# 		current_target_date = row.time

	ext_doc = frappe.new_doc("Work Item Time Extension")
	ext_doc.work_item_reference = doc.name
	ext_doc.current_target_date = doc.target_end_date
	ext_doc.requested_due_date = req_target_date_time
	ext_doc.reason = reason
	ext_doc.requester = doc.assignee
	for approver in {doc.requester, doc.reporter}:
		if approver:
			ext_doc.append("approver", {"user": approver})
			to.append(approver)
	ext_doc.requested_date = now_datetime()
	ext_doc.save()
	content = f"A time extension request has been raised by {doc.assignee} for work item {doc.name}. Click <a href='{frappe.utils.get_url()}/app/work-item-time-extension/{ext_doc.name}'>here</a> to view the request"
	send_notifications(doc.name, content, to, doctype="Work Item Time Extension", docname=ext_doc.name)


@frappe.whitelist()
@safe_exec
def reassign(wi, new_assignee, current_assignee, reason):
	reassign_doc = frappe.new_doc("Reassignment History")
	reassign_doc.work_item_ref = wi
	reassign_doc.assignee_from = current_assignee
	reassign_doc.assignee_to = new_assignee
	reassign_doc.reasonremarks = reason
	reassign_doc.reassignment_date_time = now_datetime()
	reassign_doc.reassigned_by = frappe.session.user
	reassign_doc.save()
	frappe.db.set_value("Work Item", wi, "assignee", new_assignee)
	content = "Re-Assignment has been initiated. Click <a href='{frappe.utils.get_url()}/app/work-item/{wi}'>here</a> to view the work item"
	to = [
		current_assignee,
		new_assignee,
	]
	send_notifications(wi, content, to, doctype=None, docname=None)


@frappe.whitelist()
@safe_exec
def apply_updates_to_work_item(docname, updates, one_time=False, change_date=None):
	updates = json.loads(updates)
	if one_time and change_date:
		wi_names = _get_work_item(docname, change_date)
		for name in wi_names:
			_update_work_item(name, updates)
	else:
		_purge_work_item(docname)
		_update_work_item(docname, updates)


@safe_exec
def _get_work_item(docname, change_date=None):
	# query = """
	#     SELECT DISTINCT wi.name
	#     FROM `tabWork Item` wi
	#     INNER JOIN `tabWork Item Log` wil
	#         ON wil.parent = wi.name
	#         AND wil.parenttype = 'Work Item'
	#         AND wil.parentfield = 'activities'
	#     WHERE wi.reference_document = %s
	#         AND wi.reference_doctype = 'Work Item'
	#         AND wi.status != 'Done'
	#         AND wi.status != 'Under Review'
	#         AND wi.status != 'In Progress'
	#         AND wil.action_type = 'Target End Date'
	# """
	query = """
        SELECT DISTINCT wi.name
        FROM `tabWork Item` wi
        WHERE wi.reference_document = %s
            AND wi.reference_doctype = 'Work Item'
            AND wi.status != 'Done'
            AND wi.status != 'Under Review'
    """
	params = [docname]

	if change_date:
		target_dt = get_datetime(change_date)
		start_dt = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
		end_dt = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

		query += " AND wi.target_end_date BETWEEN %s AND %s"
		params.extend([start_dt, end_dt])

	if not change_date:
		work_item = frappe.db.sql(query, tuple(params))
		work_item = work_item[1:]
		return work_item
	else:
		return frappe.db.sql(query, tuple(params))


@safe_exec
def _update_work_item(item_name, updates):
	fields_restricted = ["status", "assignee", "reference_document", "reference_doctype", "recurrence_type"]
	work_item = frappe.get_doc("Work Item", item_name)
	has_changes = False

	for key, value in updates.items():
		if isinstance(value, list):
			work_item.set(key, [])
			for row in value:
				row = {k: v for k, v in row.items() if k not in ["idx", "name", "__islocal"]}
				work_item.append(key, row)
			has_changes = True

		elif key in work_item.as_dict():
			if work_item.get(key) != value and key not in fields_restricted:
				work_item.set(key, value)
				has_changes = True

	if has_changes:
		work_item.save()
		# sent_noti(work_item.name)
		if not updates.get("one_time_change"):
			work_item.after_insert()


@safe_exec
def _purge_work_item(docname):
	work_items = _get_work_item(docname)
	for item in work_items:
		frappe.delete_doc("Work Item", item[0], force=True)


@frappe.whitelist()
@safe_exec
def get_wft_data(wft):
	return frappe.get_doc("Work Flow Template Item", {"parent": wft, "idx": 1})


@safe_exec
def score_summary(
	delay_penalty,
	rework_penalty,
	revision_penalty,
	benefit_penalty,
	total_penalty,
	target_end_date,
	actual_end_date,
	delay_time,
	ppm,
	rework_count,
	rework_impact,
	max_allowed_rework,
	max_rework_penalty,
	revision_count,
	revision_impact,
	max_allowed_revision,
	max_delay_points,
	benefit_of_work_done,
	completion_score,
):
	delay_hours = delay_time / 60

	summary = "Delay Penalty          : " + str(round(delay_penalty, 2)) + " <br>"
	summary += "Revision Penalty       : " + str(round(revision_penalty, 2)) + " <br>"
	summary += "Rework Penalty         : " + str(round(rework_penalty, 2)) + " <br>"
	summary += "Benefit Penalty        : " + str(round(benefit_penalty, 2)) + " <br>"
	summary += "-----------------------------" + " <br>"
	summary += "Total Penalty          : " + str(round(total_penalty, 2)) + " <br>"
	summary += "-----------------------------" + " <br>"

	summary += "<b><u>Delay Penalty Breakdown</u></b>" + " <br>"
	summary += "<ul>"
	summary += "<li>Planned Target Time: " + str(target_end_date) + "</li>"
	summary += "<li>Actual Target Time: " + str(actual_end_date) + "</li>"
	summary += "<li>Delay Hours: " + str(round(delay_hours, 2)) + "</li>"
	summary += "<li>Max Delay Points: " + str(max_delay_points) + "</li>"
	summary += "</ul>"
	summary += "<u>Delay Penalty Calculation</u><br>"
	summary += "Penalty Points per Minute: " + str(ppm) + "<br>"
	summary += (
		"Delay Penalty: ("
		+ str(round(delay_hours, 2))
		+ " * 60 * "
		+ str(round(ppm, 2))
		+ ") = "
		+ str(round(delay_hours * 60 * round(ppm, 2), 2))
		+ " or "
		+ str(round(max_delay_points, 2))
		+ "(Whichever is lowest)"
		+ "<br><br>"
	)

	summary += "<b><u>Rework Penalty Breakdown</u></b>"
	summary += "<ul>"
	summary += "<li>Rework count: " + str(rework_count) + "</li>"
	summary += "<li>Rework Impact: " + str(rework_impact) + "</li>"
	summary += "<li>Max Rework Penalty: " + str(max_rework_penalty) + "</li>"
	summary += "<li>Max allowed rework: " + str(max_allowed_rework) + "</li>"
	summary += "</ul>"
	summary += "<u>Rework Penalty Calculation</u><br>"
	summary += (
		"Rework Penalty: (("
		+ str(rework_count)
		+ " / "
		+ str(max_allowed_rework)
		+ ") * "
		+ str(rework_impact)
		+ " = "
		+ str(((rework_count or 0) / max_allowed_rework) * rework_impact)
		+ " or "
		+ str(round(max_rework_penalty, 2))
		+ "(Whichever is lowest)"
		+ "<br><br>"
	)

	summary += "<b><u>Revision Penalty Breakdown</u></b>"
	summary += "<ul>"
	summary += "<li>Revision count: " + str(revision_count) + "</li>"
	summary += "<li>Revision Impact: " + str(revision_impact) + "</li>"
	summary += "<li>Max allowed revision: " + str(max_allowed_revision) + "</li>"
	summary += "</ul>"
	summary += "<u>Revision Penalty Calculation</u><br>"
	summary += (
		"Revision Penalty: (("
		+ str(revision_count)
		+ " / "
		+ str(max_allowed_revision)
		+ ") * "
		+ str(revision_impact)
		+ " = "
		+ str(round(((revision_count or 0) / max_allowed_revision) * revision_impact, 2))
		+ "<br><br>"
	)

	summary += "<b><u>Work Benefit Penalty Breakdown</u></b>"
	summary += "<ul>"
	summary += "<li>Work Benefit of Work Done %: " + str(benefit_of_work_done) + "</li>"
	summary += "<li>Benefit Penalty Weightage: " + str(completion_score) + "</li>"
	summary += "</ul>"
	summary += "<u>Work Benefit Penalty Calculation</u><br>"
	summary += (
		"Work Benefit Penalty: ((100 - "
		+ str(benefit_of_work_done)
		+ "%) of "
		+ str(completion_score)
		+ ") = "
		+ str(round(((100 - (int(benefit_of_work_done) or 0)) / completion_score), 2))
	)

	return summary
