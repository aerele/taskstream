# Copyright (c) 2026, Chethan - Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Collection(Document):
	def validate(self):
		work_items = []
		for item in self.work_items:
			if item.work_item in work_items:
				self.work_items.remove(item)
			work_items.append(item.work_item)
