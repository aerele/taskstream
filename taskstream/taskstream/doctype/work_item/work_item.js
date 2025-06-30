// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on('Work Item', {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Employee',
					filters: {
						user_id: frappe.session.user
					},
					fields: ['name']
				},
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						frm.set_value('requested_by', r.message[0].name);
					}
				}
			});
		}
		if (frm.is_new() && !frm.doc.planned_start) {
			frm.set_value('planned_start', frappe.datetime.now_datetime());
		}
	},
	refresh: function (frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.trigger('onload');
		}
		if (frm.is_new() && !frm.doc.planned_start) {
			frm.set_value('planned_start', frappe.datetime.now_datetime());
		}
	}
});
