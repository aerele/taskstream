// Copyright (c) 2026, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.query_reports["Work Item Score Board"] = {
	filters: [
		{
			fieldname: "user",
			label: __("User"),
			fieldtype: "Link",
			options: "User",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.is_group) {
			value = `<strong>${value}</strong>`;
		}
		return value;
	},
};
