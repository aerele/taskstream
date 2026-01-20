import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

def send_notifications(work_item, content, to):
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
                "document_type": "Work Item",
                "subject": f"Notification for Work Item: {work_item}",
                "document_name": work_item,
                "from_user": frappe.session.user,
            }

            enqueue_create_notification(user, notification_doc)