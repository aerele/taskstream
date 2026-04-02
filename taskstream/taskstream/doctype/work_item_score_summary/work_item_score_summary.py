# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkItemScoreSummary(Document):
	pass


def create_summary_record(summary, wi, generated_from):
	summary_doc = frappe.new_doc("Work Item Score Summary")
	summary_doc.work_item = wi
	summary_doc.summary = summary
	summary_doc.generated_from = generated_from
	summary_doc.insert(ignore_permissions=True)
