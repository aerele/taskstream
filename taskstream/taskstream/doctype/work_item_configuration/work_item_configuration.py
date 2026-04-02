# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkItemConfiguration(Document):
	def validate(self):
		self.penalty_per_minute = self.penalty_points_per_day / 1440
		if self.reporting_frequency > 31:
			frappe.throw("Reporting frequency cannot be more than 31 days.")
