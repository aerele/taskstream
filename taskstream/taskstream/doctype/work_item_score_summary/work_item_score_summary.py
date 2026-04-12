# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from taskstream.api import _get_reporting_window


class WorkItemScoreSummary(Document):
	pass


def create_summary_record(summary, wi, score, generated_from):
	summary_doc = frappe.new_doc("Work Item Score Summary")
	summary_doc.work_item = wi
	summary_doc.summary = summary
	summary_doc.score = score
	summary_doc.generated_from = generated_from
	summary_doc.created_on = now_datetime().date()
	summary_doc.report_cycle = _get_reporting_window()
	summary_doc.insert(ignore_permissions=True)
