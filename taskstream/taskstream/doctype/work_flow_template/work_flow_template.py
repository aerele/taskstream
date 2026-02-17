# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkFlowTemplate(Document):
	def on_submit(self):
		self.db_set("active", 1)
		if self.previous_template_version:
			frappe.db.set_value("Work Flow Template", self.previous_template_version, "active", 0)


