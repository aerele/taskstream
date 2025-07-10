// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on('Work Item', {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value('requested_by', frappe.session.user);
		}
	},

	refresh: function (frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value('requested_by', frappe.session.user);
		}

		frm.clear_custom_buttons();

		const user = frappe.session.user;

		if (!frm.is_new() && frm.doc.status === 'To Do' && frm.doc.assignee === user) {
			frm.add_custom_button(__('Start Now'), function () {
				frappe.call({
					method: 'taskstream.taskstream.doctype.work_item.work_item.start_now',
					args: { docname: frm.doc.name },
					callback: function (r) {
						if (!r.exc) {
							frappe.msgprint(__('Work Item started!'));
							frm.reload_doc();
						}
					}
				});
			});
		}
		if (!frm.is_new() && ['In Progress', 'Under Review'].includes(frm.doc.status)) {
			const isCritical = frm.doc.is_critical;

			if (isCritical) {
				if (user === frm.doc.assignee && frm.doc.status == 'In Progress') {
					frm.add_custom_button(__('Send for Review'), function () {
						frappe.call({
							method: 'taskstream.taskstream.doctype.work_item.work_item.send_for_review',
							args: { docname: frm.doc.name },
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__('Sent for review!'));
									frm.reload_doc();
								}
							}
						});
					});
				}

				if (user === frm.doc.reviewer && frm.doc.status == 'Under Review') {
					frm.add_custom_button(__('Resend for rework'), function () {
						frappe.call({
							method: 'taskstream.taskstream.doctype.work_item.work_item.resend_for_rework',
							args: { docname: frm.doc.name },
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__('Work Item has been sent for rework!'));
									frm.reload_doc();
								}
							}
						});
					});

					frm.add_custom_button(__('Mark Complete'), function () {
						frappe.call({
							method: 'taskstream.taskstream.doctype.work_item.work_item.mark_complete',
							args: { docname: frm.doc.name },
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__('Marked as Done!'));
									frm.reload_doc();
								}
							}
						});
					});
				}

			} else {
				if (user === frm.doc.assignee) {
					frm.add_custom_button(__('Mark Complete'), function () {
						frappe.call({
							method: 'taskstream.taskstream.doctype.work_item.work_item.mark_complete',
							args: { docname: frm.doc.name },
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__('Marked as Done.'));
									frm.reload_doc();
								}
							}
						});
					}, __('Actions'));
				}
			}
		}

		const isDone = frm.doc.status === 'Done';
		frm.set_df_property('actual_duration', 'read_only', isDone);
	},

	is_critical: function (frm) {
		if (frm.doc.is_critical && !frm.doc.reviewer) {
			frm.set_value('reviewer', frappe.session.user);
		}
		frm.set_df_property('reviewer', 'reqd', frm.doc.is_critical);
	},

	reviewer: function (frm) {
		if (frm.doc.reviewer == frm.doc.assignee) {
			frappe.throw("Reviwer cannot be same as the Assignee")
		}
	},

	assignee: function (frm) {
		if (frm.doc.reviewer == frm.doc.assignee) {
			frappe.throw("Assignee cannot be same as the Reviewer")
		}
	}
});

frappe.ui.form.on('Recurrence Date', {
	recurrence_date: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let val = row.recurrence_date;

		if (val) {
			if (!(val === -1 || (val >= 1 && val <= 31))) {
				frappe.msgprint(__('Recurrence Date must be -1 (for last day) or between 1 and 31.'));
				frappe.model.set_value(cdt, cdn, 'recurrence_date', '');
			}
		}
	}
});
