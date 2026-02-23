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
		const user = frappe.session.user;
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
							reqd: 1,
						},
					],
					primary_action_label: "Submit",
					primary_action(values) {
						frappe.call({
							method: "taskstream.taskstream.doctype.work_item.work_item.resend_for_rework",
							args: {
								docname: frm.doc.name,
								rework_comments: values.rework_comments,
								target_end_date: values.target_end_date,
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
		if (frm.doc.status === "In Progress" && frm.doc.assignee === user) {
			frm.add_custom_button(__("Hold"), function () {
				frappe.db.set_value("Work Item", frm.doc.name, "status", "On Hold").then(() => {
					frappe.msgprint(__("Work Item put on hold!"));
					frm.reload_doc();
				});
			});
		}
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
		if (!frm.is_new() && ["In Progress", "Under Review"].includes(frm.doc.status)) {
			const isCritical = frm.doc.review_required;

			if (isCritical) {
				if (user === frm.doc.assignee && frm.doc.status == "In Progress") {
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

				// if (user === frm.doc.reviewer && frm.doc.status == 'Under Review') {
				// frm.add_custom_button(__('Resend for rework'), function () {
				// 	frappe.call({
				// 		method: 'taskstream.taskstream.doctype.work_item.work_item.resend_for_rework',
				// 		args: { docname: frm.doc.name },
				// 		callback: function (r) {
				// 			if (!r.exc) {
				// 				frappe.msgprint(__('Work Item has been sent for rework!'));
				// 				frm.reload_doc();
				// 			}
				// 		}
				// 	});
				// });

				// frm.add_custom_button(__('Mark Complete'), function () {
				// 	frappe.call({
				// 		method: 'taskstream.taskstream.doctype.work_item.work_item.mark_complete',
				// 		args: { docname: frm.doc.name },
				// 		callback: function (r) {
				// 			if (!r.exc) {
				// 				frappe.msgprint(__('Marked as Done!'));
				// 				frm.reload_doc();
				// 			}
				// 		}
				// 	});
				// });
				// }
			}
			// else {
			// 	if (user === frm.doc.assignee) {
			// 		frm.add_custom_button(__('Mark Complete'), function () {
			// 			frappe.call({
			// 				method: 'taskstream.taskstream.doctype.work_item.work_item.mark_complete',
			// 				args: { docname: frm.doc.name },
			// 				callback: function (r) {
			// 					if (!r.exc) {
			// 						frappe.msgprint(__('Marked as Done!'));
			// 						frm.reload_doc();
			// 					}
			// 				}
			// 			});
			// 		});
			// 	}
			// }
		}

		// const isDone = frm.doc.status === 'Done';
		// frm.set_df_property('actual_duration', 'read_only', isDone);
	},

	validate: function (frm) {
		update_recurrence_description(frm);
	},

	review_required: function (frm) {
		if (frm.doc.review_required && !frm.doc.reviewer) {
			frm.set_value("reviewer", frappe.session.user);
		}
		frm.set_df_property("reviewer", "reqd", frm.doc.review_required);
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

	// async work_flow_template(frm) {
	// 	const template = frm.doc.work_flow_template;
	// 	if (!template) return;

	// 	try {
	// 		const template_doc = await frappe.db.get_doc("Work Flow Template", template);
	// 		const first_task = (template_doc.tasks || [])[0];

	// 		await frm.set_value("summary", first_task.task_name || "");
	// 		await frm.set_value("description", first_task.task_description || "");
	// 		await frm.set_value("idx", 1);

	// 		if (first_task?.assignment_based_on === "User" && first_task.assignee) {
	// 			await frm.set_value("assignee", first_task.assignee);
	// 		}

	// 		frappe.model.clear_table(frm.doc, "activities");
	// 		if (first_task?.target_end_date_time) {
	// 			const target_end = get_target_end_datetime(
	// 				first_task.target_end_date_time,
	// 				frm.doc.start_date_time
	// 			);
	// 			const row = frm.add_child("activities");
	// 			row.action_type = "Target End Date";
	// 			row.time = target_end;
	// 		}
	// 		frm.refresh_field("activities");
	// 	} catch (error) {
	// 		console.error(error);
	// 		frappe.msgprint(__("Unable to load selected Work Flow Template."));
	// 	}
	// },

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
