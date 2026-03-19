// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Item", {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.reporter) {
			frm.set_value("reporter", frappe.session.user);
		}
		update_recurrence_description(frm);
	},

	refresh: function (frm) {
		setup_two_col_layout(frm);
		const { user } = frappe.session;
		const type = frm.doc.recurrence_type || "One Time";
		const allowed = !(type === "One Time" || type === "Recurring Instance");
		//Update Master Recurring Work Item
		if (allowed && (user === frm.doc.reporter || user === frm.doc.requester)) {
			frm.add_custom_button(__("Update Recurrence Item"), function () {
				UpdateWorkItemDetails(frm);
			});
		}
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
		if (
			!frm.doc.first_mail &&
			!frm.is_dirty() &&
			frm.doc.status === "To Do" &&
			(user === frm.doc.reporter || user === frm.doc.requester)
		) {
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
		if (
			!frm.is_new() &&
			(frm.doc.first_mail == 1 || (user !== frm.doc.reporter && user !== frm.doc.requester))
		) {
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
		if (frm.doc.status === "In Progress" && approved_users_for_reassignment.includes(user)) {
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

	attachment: async function (frm) {
		let file_url = frm.doc.attachment;
		if (!file_url) return;

		const r = await frappe.db.get_value("File", { file_url: file_url }, ["name", "file_size"]);
		const file_doc = r?.message;
		if (!file_doc) return;

		const max_size = await frappe.db.get_single_value(
			"Work Item Configuration",
			"max_file_attachment_size"
		);
		const allowed_size = max_size;

		const size_mb = file_doc.file_size / (1024 * 1024);

		if (size_mb > allowed_size) {
			frappe.call({
				method: "taskstream.api.delete_file_if_exists",
				args: {
					file_name: file_doc.name,
				},
				callback: function () {
					frm.set_value("attachment", "");
					frappe.msgprint(__(`File must be less than ${allowed_size} MB`));
				},
			});
		}
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

function UpdateWorkItemDetails(frm) {
	let recurrence_time_data = (frm.doc.recurrence_time || []).map((row) => {
		return {
			recurrence_time: row.recurrence_time,
		};
	});
	let recurrence_date_data = (frm.doc.recurrence_date || []).map((row) => {
		return {
			recurrence_date: row.recurrence_date,
		};
	});
	let recurrence_day_data = (frm.doc.recurrence_day_occurrence || []).map((row) => {
		return {
			week_order: row.week_order,
			weekday: row.weekday,
		};
	});

	let d = new frappe.ui.Dialog({
		title: "Update Work Item",
		size: "extra-large",
		fields: [
			{
				fieldname: "one_time_change",
				fieldtype: "Check",
				label: "One Time Change",
			},
			{
				depends_on: "eval: doc.one_time_change",
				fieldname: "update_on_date",
				fieldtype: "Date",
				label: "Update On Date",
				mandatory_depends_on: "eval: doc.one_time_change",
			},
			{
				label: "Requester",
				fieldname: "requester",
				fieldtype: "Link",
				options: "User",
				default: frm.doc.requester,
			},
			{
				label: "Summary",
				fieldname: "summary",
				fieldtype: "Small Text",
				default: frm.doc.summary,
			},
			{
				label: "Description",
				fieldname: "description",
				fieldtype: "Text Editor",
				default: frm.doc.description,
			},
			{
				label: "Review Required",
				fieldname: "review_required",
				fieldtype: "Check",
				default: frm.doc.review_required,
			},
			{
				label: "Reviewer",
				fieldname: "reviewer",
				fieldtype: "Link",
				options: "User",
				depends_on: "eval:doc.review_required == 1",
				default: frm.doc.reviewer,
			},
			{
				label: "Recurrence Type",
				fieldname: "recurrence_type",
				fieldtype: "Select",
				options: "Daily\nWeekly\nMonthly\nYearly",
				default: frm.doc.recurrence_type,
				depends_on: "eval: doc.one_time_change == 0",
			},
			{
				fieldname: "repeat_until",
				fieldtype: "Date",
				label: "Repeat Until",
				default: frm.doc.repeat_until,
				depends_on: "eval: doc.one_time_change == 0",
			},
			{
				depends_on:
					"eval: !['One Time', 'Daily'].includes(doc.recurrence_type) && doc.one_time_change == 0",
				fieldname: "recurrence_frequency",
				fieldtype: "Int",
				label: "Recurrence Frequency",
				non_negative: 1,
				default: frm.doc.recurrence_frequency,
			},
			{
				depends_on: "eval: doc.recurrence_type == 'Weekly' && doc.one_time_change == 0",
				fieldname: "recurrence_day",
				fieldtype: "Table MultiSelect",
				label: "Recurrence Day",
				options: "Weekday Option",
				default: frm.doc.recurrence_day,
			},
			{
				depends_on: "eval: doc.recurrence_type == 'Monthly' && doc.one_time_change == 0",
				fieldname: "monthly_recurrence_based_on",
				fieldtype: "Select",
				label: "Monthly Recurrence Based On",
				options: "Date\nDay",
				default: frm.doc.monthly_recurrence_based_on,
			},
			{
				depends_on:
					'eval: ["Monthly", "Yearly"].includes(doc.recurrence_type) && doc.monthly_recurrence_based_on === "Date" && doc.one_time_change == 0',
				fieldname: "recurrence_date",
				fieldtype: "Table",
				label: "Recurrence Date",
				mandatory_depends_on:
					"eval:['Monthly', 'Yearly'].includes(doc.recurrence_type) && doc.monthly_recurrence_based_on == \"Date\"",
				in_place_edit: true,
				data: recurrence_date_data,
				fields: [
					{
						label: "Recurrence Date",
						fieldname: "recurrence_date",
						fieldtype: "Int",
						in_list_view: true,
					},
				],
			},
			{
				depends_on:
					"eval: doc.recurrence_type == 'Monthly' && doc.monthly_recurrence_based_on == 'Day' && doc.one_time_change == 0",
				fieldname: "recurrence_day_occurrence",
				fieldtype: "Table",
				label: "Recurrence Day Occurrence",
				mandatory_depends_on:
					"eval:['Monthly'].includes(doc.recurrence_type) && doc.monthly_recurrence_based_on == \"Day\"",
				in_place_edit: true,
				data: recurrence_day_data,
				fields: [
					{
						label: "Week Order",
						fieldname: "week_order",
						fieldtype: "Select",
						options: "First\nSecond\nThird\nFourth\nLast",
						in_list_view: true,
					},
					{
						label: "Weekday",
						fieldname: "weekday",
						fieldtype: "Select",
						options: "Sunday\nMonday\nTuesday\nWednesday\nThursday\nFriday\nSaturday",
						in_list_view: true,
					},
				],
			},
			{
				depends_on: "eval: doc.recurrence_type == 'Yearly' && doc.one_time_change == 0",
				fieldname: "recurrence_month",
				fieldtype: "Table MultiSelect",
				label: "Recurrence Month",
				options: "Month Option",
			},
			{
				depends_on: "eval: doc.one_time_change == 0",
				fieldname: "recurrence_time",
				fieldtype: "Table",
				label: "Recurrence Time",
				reqd: 1,
				in_place_edit: true,
				data: recurrence_time_data,
				fields: [
					{
						label: "Recurrence Time (Hour of the day (in IST)",
						fieldname: "recurrence_time",
						fieldtype: "Select",
						options:
							"00\n01\n02\n03\n04\n05\n06\n07\n08\n09\n10\n11\n12\n13\n14\n15\n16\n17\n18\n19\n20\n21\n22\n23",
						in_list_view: true,
					},
				],
			},
		],
		primary_action_label: "Submit",
		primary_action(values) {
			frappe.call({
				method: "taskstream.taskstream.doctype.work_item.work_item.apply_updates_to_work_item",
				args: {
					docname: frm.doc.name,
					updates: JSON.stringify(values),
					one_time: values.one_time_change ? 1 : 0,
					change_date: values.update_on_date || null,
				},
				callback: function (r) {
					if (!r.exc) {
						frappe.msgprint(r.message?.message || r.message || __("Update applied"));
						d.hide();
						frm.reload_doc();
					}
				},
			});
		},
	});
	d.show();
}

function setup_two_col_layout(frm) {
	const SIDEBAR_SECTIONS = ["people_section", "settings_section"];
	const WRAP_ATTR = "data-wi-wrap";

	// ── helpers ────────────────────────────────────────────────────────────────

	function getActivePane() {
		const $pane = $(frm.wrapper).find(".tab-pane.show.active, .tab-pane.active").first();
		return $pane.length ? $pane : null;
	}

	// Undo a previous applyLayout: move sections back to pane, reset inline styles
	function teardown() {
		$(frm.wrapper)
			.find(`[${WRAP_ATTR}]`)
			.each(function () {
				const $wrap = $(this);
				const $pane = $wrap.closest(".tab-pane.active, .tab-pane.show");
				$wrap.find(".form-section").each(function () {
					// Reset every inline style we injected so Frappe's layout is restored
					$(this).find(".row").css("display", "");
					$(this).find(".form-column").css({
						width: "",
						"max-width": "",
						float: "",
						"padding-left": "",
						"padding-right": "",
					});
					($pane.length ? $pane : $wrap.parent()).append(this);
				});
				$wrap.remove();
			});
	}

	// Force every .form-column inside a section to stretch 100 % wide.
	// jQuery .css() writes element.style.* (inline styles), which always
	// outranks any class-based rule including Bootstrap's @media col-sm-* rules.
	function stackColumns($section) {
		$section.find(".row").css("display", "block");
		$section.find(".form-column").css({
			width: "100%",
			"max-width": "100%",
			float: "none",
			"padding-left": "0",
			"padding-right": "0",
		});
	}

	// ── core ───────────────────────────────────────────────────────────────────

	function applyLayout() {
		teardown();

		const $pane = getActivePane();
		if (!$pane) return;

		// Work only with sections that are direct children of this tab pane
		const $sections = $pane.children(".form-section");
		const hasSidebar = $sections
			.toArray()
			.some((el) => SIDEBAR_SECTIONS.includes($(el).attr("data-fieldname")));
		if (!hasSidebar) return;

		// All layout geometry lives in inline styles — zero dependency on CSS classes
		const $wrap = $("<div>").attr(WRAP_ATTR, "1").css({
			display: "flex",
			gap: "20px",
			alignItems: "start",
		});
		const $main = $("<div>").css({ flex: "1", minWidth: "0" });
		const $side = $("<div>").css({ width: "272px", flexShrink: "0" });

		$sections.each(function () {
			if (SIDEBAR_SECTIONS.includes($(this).attr("data-fieldname"))) {
				stackColumns($(this));
				$side.append(this);
			} else {
				$main.append(this);
			}
		});

		$pane.append($wrap.append($main).append($side));
	}

	// ── tab-switch wiring (bound once per form lifetime) ───────────────────────

	if (!frm._wi_layout_bound) {
		frm._wi_layout_bound = true;
		$(frm.wrapper).on(
			"shown.bs.tab.wi click.wi",
			'.nav-tabs .nav-link, a[data-toggle="tab"]',
			function () {
				setTimeout(applyLayout, 80);
			}
		);
	}

	setTimeout(applyLayout, 0);
}
