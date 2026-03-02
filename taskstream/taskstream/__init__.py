import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification


def send_notifications(work_item, content, to, doctype=None, docname=None):
	config = frappe.get_single("Work Item Configuration")
	if config.email_alert:
		frappe.sendmail(
			recipients=to,
			subject=f"Notification for Work Item: {work_item}",
			message=content,
		)

	if config.system_notification:
		for user in to:
			notification_doc = {
				"type": "Share",
				"document_type": "Work Item" if doctype is None else doctype,
				"subject": f"Notification for Work Item: {work_item}",
				"document_name": work_item if docname is None else docname,
				"from_user": frappe.session.user,
			}

			enqueue_create_notification(user, notification_doc)
