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
	},
});
