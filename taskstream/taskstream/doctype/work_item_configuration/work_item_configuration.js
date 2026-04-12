// Copyright (c) 2026, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Item Configuration", {
	refresh(frm) {
		frappe.call({
			method: "frappe.core.doctype.module_def.module_def.get_installed_apps",
			callback: (r) => {
				if (r.message) {
					const has_erpnext = r.message.includes("erpnext");
					const options = has_erpnext ? "Weekdays\nHolidays" : "Weekdays";
					frm.set_df_property("skip_holidays_based_on", "options", options);
					frm.refresh_field("skip_holidays_based_on");
				}
			},
		});
		if (frm.doc.reporting_frequency) {
			frm.set_df_property("reporting_frequency", "read_only", 1);
		}
		if (frm.doc.no_of_cycles_in_report) {
			frm.set_df_property("no_of_cycles_in_report", "read_only", 1);
		}
		if (frm.doc.starting_date) {
			frm.set_df_property("starting_date", "read_only", 1);
		}
	},
	validate: function (frm) {
		if (
			frm.doc.completion_score +
				frm.doc.penalty_points_per_day +
				frm.doc.revision_impact +
				frm.doc.rework_impact >
			100
		) {
			frappe.throw(
				__(
					"Sum of Completion Score, Penalty Points per day, Revision Impact and Rework Impact cannot be greater than 100"
				)
			);
		}
	},
	penalty_points_per_day: function (frm) {
		frm.set_value("penalty_per_minute", frm.doc.penalty_points_per_day / 1440);
	},
});
