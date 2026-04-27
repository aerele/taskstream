// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Item", {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.reporter) {
			frm.set_value("reporter", frappe.session.user);
			frm.set_value("requester", frappe.session.user);
		}
		// update_recurrence_description(frm);
		if (frm.is_new() && !frm.doc.target_end_date) {
			frm.set_value("target_end_date", `${frappe.datetime.get_today()} 23:59:59`);
		}
	},

	onload_post_render(frm) {
		reinit_datetime_pickers(frm);
	},

	refresh: function (frm) {
		custom_pill_type(frm);
		reinit_datetime_pickers(frm);
		frm.page.sidebar.hide();
		$(frm.page.wrapper).find(".sidebar-toggle-btn").hide();
		setup_two_col_layout(frm);
		add_recalculate_score_button(frm);
		set_wft_tasks(frm, frm.doc.work_flow_template);
		const { user } = frappe.session;
		const type = frm.doc.recurrence_type || "One Time";
		const work_item_type = frm.doc.work_item_type || null;
		const allowed = !(type === "One Time" || work_item_type === "Recurring Instance");
		//hide benefit_of_work_done if form is new
		if (frm.is_new()) {
			frm.set_df_property("benefit_of_work_done", "hidden", 1);
		}
		//Update Master Recurring Work Item
		if (allowed && (user === frm.doc.reporter || user === frm.doc.requester)) {
			frm.add_custom_button(__("Update Recurrence Item"), function () {
				UpdateWorkItemDetails(frm);
			});
		}
		// Mark Complete button
		if (
			(frm.doc.status === "Open" && !frm.doc.review_required && user === frm.doc.assignee) ||
			(frm.doc.status === "Under Review" && user === frm.doc.reviewer)
		) {
			frm.add_custom_button(__("Mark Complete"), function () {
				frappe.confirm(
					__("Are you sure you want to mark this item as complete?"),
					function () {
						frappe.call({
							method: "taskstream.taskstream.doctype.work_item.work_item.mark_complete",
							args: { docname: frm.doc.name },
							freeze: true,
							freeze_message: __("Applying updates..."),
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
			frm.doc.status === "Open" &&
			["One Time"].includes(frm.doc.recurrence_type) &&
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
		// if (!frm.is_new() && frm.doc.status === "To Do" && frm.doc.assignee === user) {
		// 	frm.add_custom_button(__("Start Now"), function () {
		// 		frappe.call({
		// 			method: "taskstream.taskstream.doctype.work_item.work_item.start_now",
		// 			args: { docname: frm.doc.name },
		// 			callback: function (r) {
		// 				if (!r.exc) {
		// 					frappe.msgprint(__("Work Item started!"));
		// 					frm.reload_doc();
		// 				}
		// 			},
		// 		});
		// 	});
		// }
		//Hold Button
		if (frm.doc.status === "Open" && frm.doc.assignee === user) {
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
				frappe.db.set_value("Work Item", frm.doc.name, "status", "Open").then(() => {
					frappe.msgprint(__("Work Item resumed!"));
					frm.reload_doc();
				});
			});
		}
		// Send for Review button
		if (!frm.is_new() && ["Open", "Under Review"].includes(frm.doc.status)) {
			const iscritical = frm.doc.review_required;

			if (iscritical && user === frm.doc.assignee && frm.doc.status == "Open") {
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
		if (frm.doc.status === "Open" && frm.doc.assignee === user) {
			frm.add_custom_button(__("Request Time Extension"), function () {
				let d = new frappe.ui.Dialog({
					title: "Request Time Extension",
					fields: [
						{
							label: "Requested Target Date and Time",
							fieldname: "req_target_date_time",
							fieldtype: "Datetime",
							reqd: 1,
							default: frm.doc.target_end_date,
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
			frm.doc.status === "Done" ||
			(!frm.is_new() &&
				// (frm.doc.first_mail == 1 ||
				user !== frm.doc.reporter &&
				user !== frm.doc.requester) //)
		) {
			const fieldnames = frm.meta.fields.map((f) => f.fieldname).filter(Boolean);
			fieldnames.forEach((field) => {
				if (field === "attachments") return;
				frm.set_df_property(field, "read_only", 1);
			});
		}
		//Update Recurrence Type options
		if (frm.doc.work_item_type != "Recurring Instance") {
			const options = "Daily\nWeekly\nMonthly\nYearly";
			frm.set_df_property("recurrence_type", "options", options);
			frm.refresh_field("recurrence_type");
		}
		//Reassignment
		const approved_users_for_reassignment = [
			frm.doc.assignee,
			frm.doc.reporter,
			frm.doc.requester,
		];
		if (
			frm.doc.status === "Open" &&
			approved_users_for_reassignment.includes(user) &&
			(frm.doc.recurrence_type === "One Time" ||
				frm.doc.work_item_type === "Recurring Instance") &&
			// ["One Time", "Recurring Instance"].includes(frm.doc.recurrence_type) &&
			!frm.is_new()
		) {
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
									frappe.set_route("List", "Work Item");
								}
							},
						});
						d.hide();
					},
				});
				d.show();
			});
		}
		//edit-able condition for benefit_of_work_done
		if (frm.doc.review_required && user === frm.doc.reviewer) {
			frm.set_df_property("benefit_of_work_done", "read_only", 0);
		} else if (
			!frm.doc.review_required &&
			(user === frm.doc.reporter || user === frm.doc.requester)
		) {
			frm.set_df_property("benefit_of_work_done", "read_only", 0);
		} else {
			frm.set_df_property("benefit_of_work_done", "read_only", 1);
		}
		//if status != Done, then score label should be Provisional Score
		if (frm.doc.status != "Done") {
			frm.set_df_property("score", "label", "Provisional Score");
		} else {
			frm.set_df_property("score", "label", "Score");
		}
	},

	validate: function (frm) {
		update_recurrence_description(frm);
	},

	recurring_task: function (frm) {
		if (frm.doc.recurring_task === 1) {
			frm.set_value("target_end_date", null);
			frm.set_value("start_from", frappe.datetime.add_days(frappe.datetime.get_today(), 1));
			frm.set_value("work_item_type", "Recurrence Master");
			frm.set_df_property("target_end_date", "read_only", 1);
			const detailsTab = (frm.layout?.tabs || []).find(
				(t) => t.df && (t.df.fieldname === "recurrence_tab" || t.label === "Recurrence")
			);
			if (detailsTab) {
				detailsTab.set_active();
			}
			add_row_to_table(frm);
		} else {
			frm.set_value("target_end_date", `${frappe.datetime.get_today()} 23:59:59`);
			const detailsTab = (frm.layout?.tabs || []).find(
				(t) => t.df && (t.df.fieldname === "details_tab" || t.label === "Details")
			);
			if (detailsTab) {
				detailsTab.set_active();
			}
			empty_fields(frm, [
				"recurrence_description",
				"recurrence_type",
				"repeat_until",
				"recurrence_frequency",
				"recurrence_day",
				"monthly_recurrence_based_on",
				"recurrence_month",
				"recurrence_date",
				"recurrence_day_occurrence",
				"recurrence_time",
				"start_from",
				"work_item_type",
			]);
			frm.set_value("recurrence_type", "One Time");
		}
	},

	work_flow: function (frm) {
		if (frm.doc.work_flow) {
			set_active_tab(frm, "work_flow_tab", "Work Flow");
			frm.set_value("target_end_date", null);
			frm.set_value("assignee", null);
			frm.set_df_property("target_end_date", "read_only", 1);
			frm.set_df_property("assignee", "read_only", 1);
		} else {
			set_active_tab(frm, "details_tab", "Details");
			frm.set_value("target_end_date", `${frappe.datetime.get_today()} 23:59:59`);
			frm.set_df_property("target_end_date", "read_only", 0);
			frm.set_df_property("assignee", "read_only", 0);
			empty_fields(frm, [
				"start_date_time",
				"work_flow_template",
				"html_aseg",
				"summary",
				"description",
				"assignee",
			]);
		}
	},

	review_required: function (frm) {
		if (frm.doc.review_required && !frm.doc.reviewer) {
			frm.set_df_property("reviewer", "reqd", frm.doc.review_required);
		}
		if (!frm.doc.review_required) {
			frm.set_value("reviewer", null);
		}
		frm.refresh_field("reviewer");
	},

	reviewer: function (frm) {
		if (frm.doc.reviewer) {
			if (frm.doc.reviewer == frm.doc.assignee) {
				frappe.throw("Reviewer cannot be same as the Assignee");
			}
		}
	},

	assignee: function (frm) {
		if (frm.doc.assignee) {
			if (frm.doc.reviewer == frm.doc.assignee) {
				frappe.throw("Assignee cannot be same as the Reviewer");
			}
		}
	},

	benefit_of_work_done: async function (frm) {
		const completion_score = await frappe.db.get_single_value(
			"Work Item Configuration",
			"completion_score"
		);
		const considerable_score = flt(completion_score) / 2;
		const { benefit_of_work_done } = frm.doc;
		const score = (flt(benefit_of_work_done) / 100) * considerable_score;
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
		setup_work_flow_template(frm);
		set_target_end_date_time(frm);
		set_wft_tasks(frm, frm.doc.work_flow_template);
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
	form_render(frm, cdt, cdn) {
		reinit_child_time_pickers(frm);
	},
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

frappe.ui.form.on("Work Item Attachment", {
	before_attachments_remove: function (frm, cdt, cdn) {
		const { user } = frappe.session;
		const row = locals[cdt][cdn];

		if (user === frm.doc.reporter || user === frm.doc.requester) {
			return;
		}

		if (row && row.owner === user) {
			return;
		}

		frappe.throw(
			__("Only the reporter/requester or the attachment owner can delete this attachment")
		);
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

		const formatted = times
			.map((t) => String(t || ""))
			.map((s) => {
				const parts = s.split(":");
				const hour = String(parseInt(parts[0], 10) || 0).padStart(2, "0");
				const minute = String(parseInt(parts[1], 10) || 0).padStart(2, "0");
				return { hour, minute, total: parseInt(hour, 10) * 60 + parseInt(minute, 10) };
			})
			.sort((a, b) => a.total - b.total)
			.map((o) => `${o.hour}:${o.minute}`);

		return " at " + formatted.join(", ");
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

	// if (type === "Weekly" && !weekdays.length) {
	// 	const desc = `Every ${freq} week${freq > 1 ? "s" : ""}`;
	// 	// frm.fields_dict.recurrence_frequency.set_description(desc);
	// 	// frm.fields_dict.recurrence_day.set_description("");
	// 	return;
	// }

	// if (
	// 	type === "Monthly" &&
	// 	!(frm.doc.recurrence_date?.length || frm.doc.recurrence_day_occurrence?.length)
	// ) {
	// 	const desc = `Every ${freq} month${freq > 1 ? "s" : ""}`;
	// 	frm.set_value("recurrence_description", desc);
	// 	// frm.fields_dict.recurrence_frequency.set_description(desc);
	// 	// frm.fields_dict.monthly_recurrence_based_on.set_description("");
	// 	return;
	// }

	// if (type === "Yearly" && !months.length && !times.length) {
	// 	const desc = `Every ${freq} year${freq > 1 ? "s" : ""}`;
	// 	frm.set_value("recurrence_description", desc);
	// 	// frm.fields_dict.recurrence_frequency.set_description(desc);
	// 	// frm.fields_dict.recurrence_month.set_description("");
	// 	return;
	// }
	if (type === "Daily") {
		frm.set_value("recurrence_description", null);
	}

	if (type === "Weekly") {
		let desc = `Every ${freq} week${freq > 1 ? "s" : ""}`;
		if (sorted_days.length) {
			desc += " on " + sorted_days.join(", ");
		}
		desc += formatTimes(times);
		frm.set_value("recurrence_description", desc);
		// frm.fields_dict.recurrence_details_column.set_description(desc);
		// frm.fields_dict.recurrence_frequency.set_description("");
		return;
	}

	if (type === "Monthly") {
		const base = `Every ${freq} month${freq > 1 ? "s" : ""}`;
		let desc = base;

		if (frm.doc.monthly_recurrence_based_on === "Date") {
			desc += formatDates(dates) + formatTimes(times);
			// frm.fields_dict.monthly_recurrence_based_on.set_description(desc);
			frm.set_value("recurrence_description", desc);
		} else if (frm.doc.monthly_recurrence_based_on === "Day") {
			const occurrences = (frm.doc.recurrence_day_occurrence || []).map(
				(d) => `${d.week_order} ${d.weekday}`
			);
			if (occurrences.length) {
				desc += " on " + occurrences.join(", ");
			}
			desc += formatTimes(times);
			// frm.fields_dict.monthly_recurrence_based_on.set_description(desc);
			frm.set_value("recurrence_description", desc);
		} else {
			frm.set_value("recurrence_description", desc);
			// frm.fields_dict.recurrence_frequency.set_description(base);
			// frm.fields_dict.monthly_recurrence_based_on.set_description("");
		}

		// frm.fields_dict.recurrence_frequency.set_description("");
		// frm.fields_dict.recurrence_day?.set_description("");
		// frm.set_value("recurrence_description", "");
		return;
	}

	if (type === "Yearly") {
		let desc = `Every ${freq} year${freq > 1 ? "s" : ""}`;
		desc += formatMonths(months) + formatDates(dates) + formatTimes(times);
		// frm.fields_dict.recurrence_month.set_description(desc);
		// frm.fields_dict.recurrence_frequency.set_description("");
		frm.set_value("recurrence_description", desc);
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
				// let first_activity = (frm.doc.activities || [])[0];

				// if (!first_activity) {
				// 	first_activity = frm.add_child("activities");
				// 	first_activity.action_type = "Target End Date";
				// }

				// frappe.model.set_value(
				// 	first_activity.doctype,
				// 	first_activity.name,
				// 	"time",
				// 	r.message
				// );
				// frm.refresh_field("activities");

				frm.set_value("target_end_date", r.message);
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
			frappe.confirm(
				__(
					"Proceeding will replace the existing documents with a new work item that includes the updates. Are you sure?"
				),
				function () {
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
								frappe.msgprint(
									r.message?.message || r.message || __("Update applied")
								);
								d.hide();
								frm.reload_doc();
							}
						},
					});
				}
			);
		},
	});
	d.show();
}

function setup_work_flow_template(frm) {
	if (frm.doc.work_flow_template) {
		frappe.call({
			method: "taskstream.taskstream.doctype.work_item.work_item.get_wft_data",
			args: {
				wft: frm.doc.work_flow_template,
			},
			callback: function (r) {
				if (!r.exc) {
					frm.set_value("assignee", r.message.assignee);
					frm.set_value("summary", r.message.task_name);
					frm.set_value("description", r.message.task_description);
				}
			},
		});
	}
}

function setup_two_col_layout(frm) {
	const SIDEBAR_SECTIONS = [
		"section_break_iwoa",
		"people_section",
		"settings_section",
		"section_break_maby",
	];
	const WRAP_CLASS = "wi-global-wrap";
	const MAIN_CLASS = "wi-main-content";
	const SIDE_CLASS = "wi-side-bar";

	function applyLayout() {
		let $wrapper = $(frm.wrapper);
		let $wrap = $wrapper.find("." + WRAP_CLASS);

		if (!$wrap.length) {
			let $formLayout = $wrapper.find(".form-layout");
			if (!$formLayout.length) {
				$formLayout = $wrapper.find(".layout-main-section");
			}
			if (!$formLayout.length) return;

			$wrap = $("<div>").addClass(WRAP_CLASS);
			let $mainContent = $("<div>").addClass(MAIN_CLASS);
			let $sideBar = $("<div>").addClass(SIDE_CLASS);

			$formLayout.children().appendTo($mainContent);
			$wrap.append($mainContent).append($sideBar);
			$formLayout.append($wrap);
		}

		let $sideBar = $wrapper.find("." + SIDE_CLASS);

		$wrapper.find(".form-section").each(function () {
			let fieldname = $(this).attr("data-fieldname");
			if (SIDEBAR_SECTIONS.includes(fieldname)) {
				if ($(this).parent()[0] !== $sideBar[0]) {
					$sideBar.append(this);
				}
			}
		});
	}

	if (!frm.layout._wi_refresh_patched) {
		frm.layout._wi_refresh_patched = true;
		const orig_refresh = frm.layout.refresh_sections;
		frm.layout.refresh_sections = function () {
			orig_refresh.apply(this, arguments);

			$(frm.wrapper)
				.find("." + WRAP_CLASS + " .form-section:not(.hide-control)")
				.each(function () {
					const $sec = $(this);
					if (!$sec.find(".frappe-control:not(.hide-control)").length) {
						$sec.addClass("empty-section");
					} else {
						$sec.removeClass("empty-section");
					}
				});

			setTimeout(applyLayout, 0);
		};
	}

	setTimeout(applyLayout, 50);
	setTimeout(applyLayout, 200);
}

function add_recalculate_score_button(frm) {
	const score_field = frm.get_field("score");
	if (!score_field?.$wrapper) return;

	score_field.$wrapper.find(".wi-recalculate-score-wrap").remove();

	const $wrapper = $(`
		<div class="wi-recalculate-score-wrap" style="margin-top: 8	px;">
			<button type="button" class="btn btn-xs btn-default wi-recalculate-score-btn">
				${__("Recalculate Score")}
			</button>
		</div>
	`);

	$wrapper.find(".wi-recalculate-score-btn").on("click", () => {
		if (frm.is_new()) {
			frappe.msgprint(__("Please save this Work Item before recalculating score."));
			return;
		}

		frappe.call({
			method: "taskstream.taskstream.doctype.work_item.work_item.recalculate_score",
			args: { docname: frm.doc.name },
			freeze: true,
			freeze_message: __("Recalculating score..."),
			callback: function (r) {
				if (r.exc) return;
				frappe.show_alert({ message: __("Score recalculated"), indicator: "green" });
				frm.reload_doc();
			},
		});
	});

	score_field.$wrapper.append($wrapper);
}

function set_active_tab(frm, tab_name, tab_label) {
	const detailsTab = (frm.layout?.tabs || []).find(
		(t) => t.df && (t.df.fieldname === tab_name || t.label === tab_label)
	);
	if (detailsTab) {
		detailsTab.set_active();
	}
}

function set_wft_tasks(frm, wft) {
	if (!wft) {
		if (frm.fields_dict.html_aseg && frm.fields_dict.html_aseg.$wrapper) {
			frm.fields_dict.html_aseg.$wrapper.html("");
		}
		return;
	}

	frappe.call({
		method: "taskstream.api.get_all_work_flow_template_tasks",
		args: {
			wft,
		},
		callback: function (r) {
			if (!r.exc && r.message) {
				const tasks = r.message;
				tasks.sort((a, b) => (a.idx || 0) - (b.idx || 0));
				let current_idx = frm.doc.idx || 0;
				let html = `<div class="wi-lsec" style="margin-top: 15px; border: 1px solid var(--border-color, #e2e6ea); border-radius: 8px; overflow: hidden; background: var(--card-bg, #fff);">
					<div class="wi-lsec-head" style="padding: 10px 16px; border-bottom: 1px solid var(--border-color, #f0f1f3); background: var(--control-bg, #fbfcfd); display: flex; justify-content: space-between; align-items: center;">
						<div style="font-size:11.5px;font-weight:600;color:var(--text-color, #1f272e);">Work Items in this Flow</div>
						<span style="font-size:11.5px;font-weight:400;color:var(--text-muted, #8d99a5);">${tasks.length} steps</span>
					</div>
					<div style="display:flex;flex-direction:column;gap:0;">`;

				tasks.forEach((t) => {
					let dur = "";
					if (t.target_end_date_time) {
						let parts = String(t.target_end_date_time).split(":");
						let hrs = parseInt(parts[0]) || 0;
						let mins = parseInt(parts[1]) || 0;
						if (hrs > 0) dur = `${hrs} hr${hrs !== 1 ? "s" : ""}`;
						else if (mins > 0) dur = `${mins} min`;
					}

					let numClass = "wi-task-num";
					let numText = t.idx || "";
					let sPill = "";
					let isCurrentPill = "";
					let cardClass = "wi-task-card";

					if (t.idx === current_idx) {
						cardClass += " wi-current-task";
						isCurrentPill = `<span style="font-size:10px; background:var(--control-bg, #f4f5f7); color:var(--text-color, #1f272e); padding:2px 6px; border-radius:12px; font-weight:600; border:1px solid var(--border-color, #e2e6ea);">Current</span>`;
					}

					if (t.idx < current_idx) {
						numClass = "wi-task-num tn-done";
						numText = "✓";
						sPill = `<span class="wi-status-pill p-done"><span class="pill-dot"></span><span style="font-size:11px; margin-left: 4px;">Done</span></span>`;
					} else if (t.idx === current_idx && frm.doc.status === "Done") {
						numClass = "wi-task-num tn-done";
						numText = "✓";
						sPill = `<span class="wi-status-pill p-done"><span class="pill-dot"></span><span style="font-size:11px; margin-left: 4px;">Done</span></span>`;
					} else if (
						t.idx === current_idx ||
						(t.idx === current_idx + 1 && frm.doc.status === "Done")
					) {
						numClass = "wi-task-num tn-ip";
						sPill = `<span class="wi-status-pill p-ip"><span class="pill-dot"></span><span style="font-size:11px; margin-left: 4px;">Open</span></span>`;
					} else {
						sPill = `<span class="wi-status-pill p-todo"><span class="pill-dot"></span><span style="font-size:11px; margin-left: 4px;">Pending</span></span>`;
					}

					let assignee_name = frappe.user?.full_name
						? frappe.user.full_name(t.assignee)
						: t.assignee;
					if (!assignee_name && t.assignee) assignee_name = t.assignee;

					html += `<div class="${cardClass}">
						<div class="${numClass}">${numText}</div>
						<div class="wi-task-body">
							<div class="wi-task-name">${t.task_name || ""}</div>
							<div class="wi-task-desc">${t.task_description || ""}</div>
							<div class="wi-task-meta">
								<span class="wi-task-meta-item">
									<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 8a3 3 0 100-6 3 3 0 000 6zm-5 6a5 5 0 0110 0H3z"/></svg>
									${assignee_name || ""}
								</span>
								<span class="wi-task-meta-item">
									<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 3.5a.5.5 0 00-1 0V9a.5.5 0 00.252.434l3.5 2a.5.5 0 00.496-.868L8 8.71V3.5zM8 16A8 8 0 108 0a8 8 0 000 16z"/></svg>
									${dur}
								</span>
							</div>
						</div>
						<div class="wi-task-status-col">${isCurrentPill}${sPill}</div>
					</div>`;
				});
				html += `</div></div>`;

				if (frm.fields_dict.html_aseg && frm.fields_dict.html_aseg.$wrapper) {
					frm.fields_dict.html_aseg.$wrapper.html(html);
				}
			}
		},
	});
}

function empty_fields(frm, fields) {
	if (!fields) return;
	if (Array.isArray(fields)) {
		for (let field of fields) {
			frm.set_value(field, null);
		}
		return;
	}

	// support object/map of fieldnames
	for (let field in fields) {
		if (Object.prototype.hasOwnProperty.call(fields, field)) {
			frm.set_value(field, null);
		}
	}
}

function add_row_to_table(frm) {
	if (frm.is_new()) {
		let child_tables = ["recurrence_date", "recurrence_day_occurrence", "recurrence_time"];

		child_tables.forEach((fieldname) => {
			if ((frm.doc[fieldname] || []).length === 0) {
				frm.add_child(fieldname);
				frm.refresh_field(fieldname);
			}
		});
	}
}

// ── 1. Override time format at runtime (session only, never persisted to DB) ──
frappe.sys_defaults.time_format = "HH:mm";

// ── 2. Force reinitialize pickers for the specific fields ─────────────────────
const DATETIME_FIELDS = ["target_end_date", "start_date_time", "actual_end_date"];

function reinit_datetime_pickers(frm) {
	DATETIME_FIELDS.forEach((fieldname) => {
		const ctrl = frm.fields_dict[fieldname];
		if (!ctrl || !ctrl.$input) return;

		const current_val = frm.doc[fieldname];

		// Destroy existing picker and rebuild with updated time_format
		if (ctrl.picker) {
			ctrl.picker.destroy?.();
			ctrl.picker = null;
		}
		ctrl.input_area?.replaceChildren?.();
		ctrl.$input.remove?.();
		ctrl.$input = null;

		ctrl.make_input();

		if (current_val) {
			ctrl.set_input(current_val);
		}
	});
}

function reinit_child_time_pickers(frm) {
	// Child table rows pick up frappe.sys_defaults.time_format on open,
	// so existing open rows need their picker refreshed
	const grid = frm.fields_dict?.recurrence_time_table?.grid;
	if (!grid) return;

	grid.grid_rows?.forEach((row) => {
		const ctrl = row.open_form?.fields_dict?.recurrence_time;
		if (!ctrl || !ctrl.$input) return;

		const val = ctrl.value;
		if (ctrl.timepicker_node) {
			ctrl.timepicker_node.remove?.();
			ctrl.timepicker_node = null;
		}
		ctrl.make_input();
		if (val) ctrl.set_input(val);
	});
}

function custom_pill_type(frm) {
	$(".custom-work-item-pill").remove();
	if (frm.doc.work_item_type) {
		$(frm.page.indicator).after(`
			<span class="indicator-pill blue custom-work-item-pill" style="margin-left: 8px;">
				${frm.doc.work_item_type}
			</span>
		`);
	}
}
