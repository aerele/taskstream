# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WorkItem(Document):
	def validate(self):
		self.update_revision_count()
		self.validate_reviewer()

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
