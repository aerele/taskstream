// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on('Work Item', {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value('requested_by', frappe.session.user);
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
	},
	is_critical: function (frm) {
		if (frm.is_new() && frm.doc.is_critical) {
			frm.set_value('reviewer', frappe.session.user);
		}
	}
});
