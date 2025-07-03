# Copyright (c) 2025, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WorkItem(Document):
	def validate(self):
		self.update_revision_count()

	def update_revision_count(self):
		if self.name and not self.is_new():
			old_duration = frappe.db.get_value("Work Item", self.name, "estimated_duration")
			if old_duration != self.estimated_duration:
				self.revision_count = self.revision_count + 1
