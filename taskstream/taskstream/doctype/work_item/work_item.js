// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

// const UPDATE_WI_MODAL_EXCLUDED_FIELDS = [
// 	"name",
// 	"owner",
// 	"creation",
// 	"modified",
// 	"modified_by",
// 	"amended_from",
// 	"docstatus",
// 	"status",
// 	"first_mail",
// 	"twenty_percent_reminder_time",
// 	"twenty_percent_reminder_sent",
// 	"deadline_reminder_sent",
// 	"valid_dates",
// ];
// const RECURRENCE_MODAL_FIELDNAMES = [
// 	"recurrence_type",
// 	"recurrence_frequency",
// 	"recurrence_day",
// 	"recurrence_month",
// 	"monthly_recurrence_based_on",
// 	"recurrence_date",
// 	"recurrence_day_occurrence",
// 	"recurrence_time",
// 	"repeat_until",
// ];
// const UPDATE_WI_MODAL_ALWAYS_INCLUDE_FIELDS = ["reviewer", ...RECURRENCE_MODAL_FIELDNAMES];

frappe.ui.form.on("Work Item", {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.reporter) {
			frm.set_value("reporter", frappe.session.user);
		}
		update_recurrence_description(frm);
	},

	refresh: function (frm) {
		// if (!frm.is_new()) {
		// 	frm.add_custom_button(__("Update WI"), function () {
		// 		const editable_fields = get_visible_dialog_fields(frm);
		// 		const dialog_fields = editable_fields
		// 			.map((df) => build_dialog_field(df, frm))
		// 			.concat([
		// 				{
		// 					fieldname: "one_time_change",
		// 					fieldtype: "Check",
		// 					label: "One time Change",
		// 					default: 0,
		// 				},
		// 				{
		// 					fieldname: "change_date",
		// 					fieldtype: "Date",
		// 					label: "Change Date",
		// 					depends_on: "eval:doc.one_time_change==1",
		// 				},
		// 			]);

		// 		const d = new frappe.ui.Dialog({
		// 			title: __("Update Work Item"),
		// 			fields: dialog_fields,
		// 			primary_action_label: __("Submit"),
		// 			primary_action(values) {
		// 				if (values.one_time_change && !values.change_date) {
		// 					frappe.msgprint(__("Change Date is required when One time Change is checked."));
		// 					return;
		// 				}

		// 				const field_values = {};
		// 				editable_fields.forEach((df) => {
		// 					if (values[df.fieldname] !== undefined) {
		// 						field_values[df.fieldname] = values[df.fieldname];
		// 					}
		// 				});

		// 				frappe.call({
		// 					method: "taskstream.taskstream.doctype.work_item.work_item.update_work_items",
		// 					args: {
		// 						work_item: frm.doc.name,
		// 						field_values,
		// 						one_time_change: !!values.one_time_change,
		// 						change_date: values.change_date || null,
		// 					},
		// 					callback: function (r) {
		// 						if (r.exc) return;
		// 						frappe.show_alert({
		// 							message: __("Work Item(s) updated"),
		// 							indicator: "green",
		// 						});
		// 						d.hide();
		// 						frm.reload_doc();
		// 					},
		// 				});
		// 			},
		// 		});

		// 		d.show();
		// 		initialize_dialog_table_data(d, frm, editable_fields, 0);
		// 	});
		// }
		const { user } = frappe.session;
		// Mark Complete button
		if (
			(frm.doc.status === "In Progress" && !frm.doc.review_required) ||
			(frm.doc.status === "Under Review" && user === frm.doc.reviewer)
		) {
			frm.add_custom_button(__("Mark Complete"), function () {
				frappe.confirm(
					__("Are you sure you want to mark this item as complete?"),
					function () {
						frappe.call({
							method: "taskstream.taskstream.doctype.work_item.work_item.mark_complete",
							args: { docname: frm.doc.name },
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__("Marked as Done!"));
									frm.reload_doc();
								}
							},
						});
					}
				);
			});
		}
		// Send Notification button
		if (!frm.doc.first_mail && !frm.is_dirty() && frm.doc.status === "To Do") {
			frm.add_custom_button(__("Sent Mail"), function () {
				frappe.call({
					method: "taskstream.taskstream.doctype.work_item.work_item.sent_noti",
					args: { work_item: frm.doc.name },
					callback: function (r) {
						if (!r.exc) {
							frappe.msgprint(__("Mail Sent!"));
							frm.reload_doc();
						}
					},
				});
			});
		}
		// Rework button
		if (frm.doc.status === "Under Review" && frm.doc.reviewer === user) {
			frm.add_custom_button(__("Rework"), function () {
				let d = new frappe.ui.Dialog({
					title: "Rework Work Item",
					fields: [
						{
							label: "Rework Comments",
							fieldname: "rework_comments",
							fieldtype: "Small Text",
							reqd: 1,
						},
						{
							label: "Target End Date",
							fieldname: "target_end_date",
							fieldtype: "Datetime",
						},
					],
					primary_action_label: "Submit",
					primary_action(values) {
						frappe.call({
							method: "taskstream.taskstream.doctype.work_item.work_item.resend_for_rework",
							args: {
								docname: frm.doc.name,
								rework_comments: values.rework_comments,
								target_end_date: values.target_end_date || null,
							},
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__("Work Item sent for rework!"));
									frm.reload_doc();
									d.hide();
								}
							},
						});
					},
				});
				d.show();
			});
		}
		// Start Now Button
		if (!frm.is_new() && frm.doc.status === "To Do" && frm.doc.assignee === user) {
			frm.add_custom_button(__("Start Now"), function () {
				frappe.call({
					method: "taskstream.taskstream.doctype.work_item.work_item.start_now",
					args: { docname: frm.doc.name },
					callback: function (r) {
						if (!r.exc) {
							frappe.msgprint(__("Work Item started!"));
							frm.reload_doc();
						}
					},
				});
			});
		}
		//Hold Button
		if (frm.doc.status === "In Progress" && frm.doc.assignee === user) {
			frm.add_custom_button(__("Hold"), function () {
				frappe.db.set_value("Work Item", frm.doc.name, "status", "On Hold").then(() => {
					frappe.msgprint(__("Work Item put on hold!"));
					frm.reload_doc();
				});
			});
		}
		//Resume Button
		if (frm.doc.status === "On Hold" && frm.doc.assignee === user) {
			frm.add_custom_button(__("Resume"), function () {
				frappe.db
					.set_value("Work Item", frm.doc.name, "status", "In Progress")
					.then(() => {
						frappe.msgprint(__("Work Item resumed!"));
						frm.reload_doc();
					});
			});
		}
		// Send for Review button
		if (!frm.is_new() && ["In Progress", "Under Review"].includes(frm.doc.status)) {
			const iscritical = frm.doc.review_required;

			if (iscritical && user === frm.doc.assignee && frm.doc.status == "In Progress") {
				frm.add_custom_button(__("Send for Review"), function () {
					frappe.call({
						method: "taskstream.taskstream.doctype.work_item.work_item.send_for_review",
						args: {
							docname: frm.doc.name,
							reviewer: frm.doc.reviewer,
						},
						callback: function (r) {
							if (!r.exc) {
								frappe.msgprint(__("Sent for review!"));
								frm.reload_doc();
							}
						},
					});
				});
			}
		}
		//Time extension button
		if (frm.doc.status === "In Progress" && frm.doc.assignee === user) {
			frm.add_custom_button(__("Request Time Extension"), function () {
				let d = new frappe.ui.Dialog({
					title: "Request Time Extension",
					fields: [
						{
							label: "Requested Target Date and Time",
							fieldname: "req_target_date_time",
							fieldtype: "Datetime",
							reqd: 1,
						},
						{
							label: "Reason",
							fieldname: "reason",
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					primary_action_label: "Submit",
					primary_action(values) {
						frappe.call({
							method: "taskstream.taskstream.doctype.work_item.work_item.time_extension_request",
							args: {
								doc: frm.doc.name,
								reason: values.reason,
								req_target_date_time: values.req_target_date_time,
							},
							callback: function (r) {
								if (!r.exc) {
									frm.reload_doc();
									d.hide();
								}
							},
						});
					},
				});
				d.show();
			});
		}
		// Set Read Only for non reporter and non requester
		if (!frm.is_new() && user !== frm.doc.reporter && user !== frm.doc.requester) {
			const fieldnames = frm.meta.fields.map((f) => f.fieldname).filter(Boolean);
			fieldnames.forEach((field) => {
				if (field != "percent_completed") {
					frm.set_df_property(field, "read_only", 1);
				}
			});
		}
		//Update Recurrence Type options
		if (frm.doc.recurrence_type != "Recurring Instance") {
			const options = "One Time\nDaily\nWeekly\nMonthly\nYearly";
			frm.set_df_property("recurrence_type", "options", options);
			frm.refresh_field("recurrence_type");
		}
		//Reassignment
		const approved_users_for_reassignment = [
			frm.doc.assignee,
			frm.doc.reporter,
			frm.doc.requester,
		];
		if (frm.doc.status === "In Progress" && user in approved_users_for_reassignment) {
			frm.add_custom_button(__("Reassign"), function () {
				let d = new frappe.ui.Dialog({
					title: "Reassignment",
					fields: [
						{
							label: "Current Assignee",
							fieldname: "current_assignee",
							fieldtype: "Link",
							options: "User",
							read_only: 1,
							default: frm.doc.assignee,
						},
						{
							label: "Assign To",
							fieldname: "new_assignee",
							fieldtype: "Link",
							options: "User",
							reqd: 1,
						},
						{
							label: "Reason/Remarks",
							fieldname: "reason",
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					primary_action_label: "Submit",
					primary_action(values) {
						frappe.call({
							method: "taskstream.taskstream.doctype.work_item.work_item.reassign",
							args: {
								wi: frm.doc.name,
								new_assignee: values.new_assignee,
								current_assignee: values.current_assignee,
								reason: values.reason,
							},
							callback: function (r) {
								if (!r.exc) {
									frm.reload_doc();
									d.hide();
								}
							},
						});
						d.hide();
					},
				});
				d.show();
			});
		}
	},

	validate: function (frm) {
		update_recurrence_description(frm);
	},

	review_required: function (frm) {
		if (frm.doc.review_required && !frm.doc.reviewer) {
			frm.set_value("reviewer", frappe.session.user);
			frm.set_df_property("reviewer", "reqd", frm.doc.review_required);
		}
		if (!frm.doc.review_required) {
			frm.set_value("reviewer", "");
		}
		frm.refresh_field("reviewer");
	},

	reviewer: function (frm) {
		if (frm.doc.reviewer == frm.doc.assignee) {
			frappe.throw("Reviewer cannot be same as the Assignee");
		}
	},

	assignee: function (frm) {
		if (frm.doc.reviewer == frm.doc.assignee) {
			frappe.throw("Assignee cannot be same as the Reviewer");
		}
	},

	percent_completed: async function (frm) {
		const completion_score = await frappe.db.get_single_value(
			"Work Item Configuration",
			"completion_score"
		);
		const considerable_score = flt(completion_score) / 2;
		const { percent_completed } = frm.doc;
		const score = (flt(percent_completed) / 100) * considerable_score;
		frm.set_value("score", score);
	},

	recurrence_type(frm) {
		update_recurrence_description(frm);
	},

	recurrence_frequency(frm) {
		update_recurrence_description(frm);
	},

	recurrence_day(frm) {
		update_recurrence_description(frm);
	},

	monthly_recurrence_based_on(frm) {
		update_recurrence_description(frm);
	},

	recurrence_month(frm) {
		update_recurrence_description(frm);
	},

	work_flow_template(frm) {
		set_target_end_date_time(frm);
	},

	start_date_time(frm) {
		set_target_end_date_time(frm);
	},
});

frappe.ui.form.on("Recurrence Date", {
	recurrence_date: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let val = row.recurrence_date;

		if (val) {
			if (!(val === -1 || (val >= 1 && val <= 31))) {
				frappe.msgprint(
					__("Recurrence Date must be -1 (for last day) or between 1 and 31.")
				);
				frappe.model.set_value(cdt, cdn, "recurrence_date", "");
			}

			let is_duplicate = false;

			frm.doc.recurrence_date.forEach((d) => {
				if (d.name !== row.name && d.recurrence_date === val) {
					is_duplicate = true;
				}
			});

			if (is_duplicate) {
				frappe.msgprint(__("Recurrence date cannot be repeated!"));
				frappe.model.set_value(cdt, cdn, "recurrence_date", "");
			}
		}

		update_recurrence_description(frm);
	},
	recurrence_date_add: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
	recurrence_date_remove: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
});

frappe.ui.form.on("Recurrence Time", {
	recurrence_time: function (frm, cdt, cdn) {
		validate_recurrence_time(frm, cdt, cdn);
		update_recurrence_description(frm);
	},
	recurrence_time_add: function (frm, cdt, cdn) {
		validate_recurrence_time(frm, cdt, cdn);
		update_recurrence_description(frm);
	},
	recurrence_time_remove: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
});

frappe.ui.form.on("Recurrence Day Occurrence", {
	weekday: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
	week_order: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
	recurrence_day_occurrence_add: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
	recurrence_day_occurrence_remove: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
});

function validate_recurrence_time(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let val = row.recurrence_time;

	if (val) {
		let is_duplicate = false;

		frm.doc.recurrence_time.forEach((d) => {
			if (d.name !== row.name && d.recurrence_time === val) {
				is_duplicate = true;
			}
		});

		if (is_duplicate && val == 10) {
			frappe.model.set_value(cdt, cdn, "recurrence_time", "");
		} else if (is_duplicate) {
			frappe.msgprint(__("Recurrence time cannot be repeated!"));
			frappe.model.set_value(cdt, cdn, "recurrence_time", "");
		}
	}
}

// function build_dialog_field(df, frm) {
// 	const field = { ...df };
// 	const value = frm.doc[df.fieldname];
// 	if (["Table", "Table MultiSelect"].includes(df.fieldtype)) {
// 		// Dialog dependencies can prevent child grids from being instantiated in time.
// 		// Keep table fields visible so existing rows can always be bound.
// 		delete field.depends_on;
// 		delete field.mandatory_depends_on;
// 		const child_meta = frappe.get_meta(df.options);
// 		field.in_place_edit = true;
// 		field.cannot_add_rows = false;
// 		field.data = (value || []).map(row => normalize_child_row(df.fieldname, sanitize_child_row(row)));
// 		field.fields = (child_meta.fields || [])
// 			.filter(col =>
// 				!col.hidden &&
// 				!col.read_only &&
// 				!["Section Break", "Column Break", "Tab Break", "Button", "Fold", "HTML"].includes(col.fieldtype)
// 			)
// 			.map(col => ({ ...col, in_list_view: 1 }));
// 		field.get_data = () => field.data;
// 	} else {
// 		field.default = value;
// 	}
// 	return field;
// }

// function initialize_dialog_table_data(dialog, frm, fields, attempt = 0) {
// 	let pending = false;
// 	fields
// 		.filter(df => ["Table", "Table MultiSelect"].includes(df.fieldtype))
// 		.forEach(df => {
// 			const table_field = dialog.fields_dict[df.fieldname];
// 			if (!table_field || !table_field.grid) {
// 				pending = true;
// 				return;
// 			}

// 			const rows = (frm.doc[df.fieldname] || []).map(row =>
// 				normalize_child_row(df.fieldname, sanitize_child_row(row))
// 			);
// 			table_field.df.data = rows;
// 			table_field.grid.df.data = rows;
// 			table_field.df.get_data = () => table_field.df.data || [];
// 			table_field.grid.refresh();
// 		});

// 	if (pending && attempt < 5) {
// 		setTimeout(() => initialize_dialog_table_data(dialog, frm, fields, attempt + 1), 120);
// 	}
// }

// async function apply_dialog_values_to_form(frm, fields, values) {
// 	for (const df of fields) {
// 		if (!df.fieldname) continue;
// 		if (["Table", "Table MultiSelect"].includes(df.fieldtype)) {
// 			frm.clear_table(df.fieldname);
// 			(values[df.fieldname] || []).forEach(row => {
// 				frm.add_child(df.fieldname, normalize_child_row(df.fieldname, sanitize_child_row(row)));
// 			});
// 			frm.refresh_field(df.fieldname);
// 		} else if (values[df.fieldname] !== undefined) {
// 			await frm.set_value(df.fieldname, values[df.fieldname]);
// 		}
// 	}
// }

// function normalize_child_row(parent_fieldname, row) {
// 	const clean_row = { ...row };
// 	if (parent_fieldname === "recurrence_time") {
// 		clean_row.recurrence_time = normalize_recurrence_hour(clean_row.recurrence_time);
// 	}
// 	return clean_row;
// }

// function normalize_recurrence_hour(value) {
// 	if (value === undefined || value === null || value === "") return value;
// 	const raw = String(value).trim();
// 	if (/^\d{2}$/.test(raw)) return raw;
// 	if (/^\d{1}$/.test(raw)) return raw.padStart(2, "0");
// 	const hour = raw.includes(":") ? raw.split(":")[0] : raw;
// 	const numeric_hour = parseInt(hour, 10);
// 	if (!Number.isNaN(numeric_hour) && numeric_hour >= 0 && numeric_hour <= 23) {
// 		return String(numeric_hour).padStart(2, "0");
// 	}
// 	return raw;
// }

// function sanitize_child_row(row) {
// 	const clean_row = { ...row };
// 	delete clean_row.name;
// 	delete clean_row.parent;
// 	delete clean_row.parentfield;
// 	delete clean_row.parenttype;
// 	delete clean_row.docstatus;
// 	delete clean_row.__islocal;
// 	delete clean_row.__unsaved;
// 	delete clean_row.owner;
// 	delete clean_row.creation;
// 	delete clean_row.modified;
// 	delete clean_row.modified_by;
// 	return clean_row;
// }

// function get_visible_dialog_fields(frm) {
// 	const excluded_fieldtypes = ["Section Break", "Column Break", "Tab Break", "Button", "Fold", "HTML"];
// 	const excluded_fieldnames = new Set(UPDATE_WI_MODAL_EXCLUDED_FIELDS);

// 	return (frm.meta.fields || []).filter((df) => {
// 		if (!df.fieldname) return false;
// 		if (excluded_fieldtypes.includes(df.fieldtype)) return false;
// 		if (excluded_fieldnames.has(df.fieldname)) return false;
// 		if (df.hidden) return false;
// 		if (is_field_visible(frm, df.fieldname)) return true;
// 		return UPDATE_WI_MODAL_ALWAYS_INCLUDE_FIELDS.includes(df.fieldname);
// 	});
// }

// function is_field_visible(frm, fieldname) {
// 	const field = frm.get_field(fieldname);
// 	if (!field || !field.$wrapper) return true;
// 	return field.$wrapper.is(":visible");
// }

function update_recurrence_description(frm) {
	const freq = frm.doc.recurrence_frequency || 1;
	const type = frm.doc.recurrence_type || "";

	const weekdays = (frm.doc.recurrence_day || []).map((r) => r.weekday);
	const day_order = {
		Sunday: 0,
		Monday: 1,
		Tuesday: 2,
		Wednesday: 3,
		Thursday: 4,
		Friday: 5,
		Saturday: 6,
	};
	const sorted_days = weekdays.sort((a, b) => day_order[a] - day_order[b]);

	const times = (frm.doc.recurrence_time || []).map((d) => d.recurrence_time).filter(Boolean);
	const dates = (frm.doc.recurrence_date || []).map((d) => d.recurrence_date).filter(Boolean);
	const months = (frm.doc.recurrence_month || []).map((d) => d.month).filter(Boolean);

	const formatTimes = (times) => {
		if (!times.length) return "";
		const sorted = times.sort((a, b) => a - b).map((h) => `${h}:00`);
		return " at " + sorted.join(", ") + " hrs";
	};

	const formatDates = (date) => {
		if (!dates.length) return "";
		const sorted = dates.sort((a, b) => a - b);
		return " on " + sorted.join(", ");
	};

	const formatMonths = (months) => {
		if (!months.length) return "";
		const order = [
			"January",
			"February",
			"March",
			"April",
			"May",
			"June",
			"July",
			"August",
			"September",
			"October",
			"November",
			"December",
		];
		const sorted = months.sort((a, b) => order.indexOf(a) - order.indexOf(b));
		return " in " + sorted.join(", ");
	};

	if (type === "Weekly" && !weekdays.length) {
		const desc = `Every ${freq} week${freq > 1 ? "s" : ""}`;
		frm.fields_dict.recurrence_frequency.set_description(desc);
		frm.fields_dict.recurrence_day.set_description("");
		return;
	}

	if (
		type === "Monthly" &&
		!(frm.doc.recurrence_date?.length || frm.doc.recurrence_day_occurrence?.length)
	) {
		const desc = `Every ${freq} month${freq > 1 ? "s" : ""}`;
		frm.fields_dict.recurrence_frequency.set_description(desc);
		frm.fields_dict.monthly_recurrence_based_on.set_description("");
		return;
	}

	if (type === "Yearly" && !months.length && !times.length) {
		const desc = `Every ${freq} year${freq > 1 ? "s" : ""}`;
		frm.fields_dict.recurrence_frequency.set_description(desc);
		frm.fields_dict.recurrence_month.set_description("");
		return;
	}

	if (type === "Weekly") {
		let desc = `Every ${freq} week${freq > 1 ? "s" : ""}`;
		if (sorted_days.length) {
			desc += " on " + sorted_days.join(", ");
		}
		desc += formatTimes(times);
		frm.fields_dict.recurrence_day.set_description(desc);
		frm.fields_dict.recurrence_frequency.set_description("");
		return;
	}

	if (type === "Monthly") {
		const base = `Every ${freq} month${freq > 1 ? "s" : ""}`;
		let desc = base;

		if (frm.doc.monthly_recurrence_based_on === "Date") {
			desc += formatDates(dates) + formatTimes(times);
			frm.fields_dict.monthly_recurrence_based_on.set_description(desc);
		} else if (frm.doc.monthly_recurrence_based_on === "Day") {
			const occurrences = (frm.doc.recurrence_day_occurrence || []).map(
				(d) => `${d.week_order} ${d.weekday}`
			);
			if (occurrences.length) {
				desc += " on " + occurrences.join(", ");
			}
			desc += formatTimes(times);
			frm.fields_dict.monthly_recurrence_based_on.set_description(desc);
		} else {
			frm.fields_dict.recurrence_frequency.set_description(base);
			frm.fields_dict.monthly_recurrence_based_on.set_description("");
		}

		frm.fields_dict.recurrence_frequency.set_description("");
		frm.fields_dict.recurrence_day?.set_description("");
		return;
	}

	if (type === "Yearly") {
		let desc = `Every ${freq} year${freq > 1 ? "s" : ""}`;
		desc += formatMonths(months) + formatDates(dates) + formatTimes(times);
		frm.fields_dict.recurrence_month.set_description(desc);
		frm.fields_dict.recurrence_frequency.set_description("");
		return;
	}
}

function get_target_end_datetime(duration, base_datetime) {
	const [hours = 0, minutes = 0, seconds = 0] = String(duration || "00:00:00")
		.split(":")
		.map((value) => parseInt(value, 10) || 0);

	let target = moment(base_datetime || undefined)
		.add(hours, "hours")
		.add(minutes, "minutes")
		.add(seconds, "seconds")
		.seconds(0)
		.milliseconds(0);

	return target.format("YYYY-MM-DD HH:mm:ss");
}

function set_target_end_date_time(frm) {
	if (!frm.doc.start_date_time || !frm.doc.work_flow_template) return;
	frappe.call({
		method: "taskstream.taskstream.doctype.work_item.work_item.update_target_end_on_start_date_change",
		args: {
			work_flow_template: frm.doc.work_flow_template,
			start_date_time: frm.doc.start_date_time,
		},
		callback: function (r) {
			if (!r.exc && r.message) {
				let first_activity = (frm.doc.activities || [])[0];

				if (!first_activity) {
					first_activity = frm.add_child("activities");
					first_activity.action_type = "Target End Date";
				}

				frappe.model.set_value(
					first_activity.doctype,
					first_activity.name,
					"time",
					r.message
				);
				frm.refresh_field("activities");
			}
		},
	});
}
