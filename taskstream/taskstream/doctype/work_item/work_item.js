// Copyright (c) 2025, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on('Work Item', {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value('requested_by', frappe.session.user);
		}
		update_recurrence_description(frm);
	},

	refresh: function (frm) {
		const user = frappe.session.user;
		// Mark Complete button
		if ((frm.doc.status === 'In Progress' && !frm.doc.is_critical) || (frm.doc.status === 'Under Review' && user === frm.doc.reviewer)) {
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
		// Send Notification button
		if (!frm.doc.first_mail && !frm.is_dirty()) {
			frm.add_custom_button(__('Sent Mail'), function () {
				frappe.call({
					method: 'taskstream.taskstream.doctype.work_item.work_item.sent_noti',
					args: { work_item: frm.doc.name },
					callback: function (r) {
						if (!r.exc) {
							frappe.msgprint(__('Mail Sent!'));
							frm.reload_doc();
						}
					}
				});
			});
		}
		// Rework button
		if (frm.doc.status === 'Under Review' && frm.doc.reviewer === user) {
			frm.add_custom_button(__('Rework'), function () {
				let d = new frappe.ui.Dialog({
					title: 'Rework Work Item',
					fields: [
						{
							label: 'Rework Comments',
							fieldname: 'rework_comments',
							fieldtype: 'Small Text',
							reqd: 1
						},
						{
							label: 'Planned Start Date',
							fieldname: 'planned_start_date',
							fieldtype: 'Datetime',
							reqd: 1
						},
						{
							label: 'Planned End Date',
							fieldname: 'planned_end_date',
							fieldtype: 'Datetime',
							reqd: 1
						}
					],
					primary_action_label: 'Submit',
					primary_action(values) {
						frappe.call({
							method: 'taskstream.taskstream.doctype.work_item.work_item.resend_for_rework',
							args: {
								docname: frm.doc.name,
								rework_comments: values.rework_comments,
								planned_start_date: values.planned_start_date,
								planned_end_date: values.planned_end_date
							},
							callback: function (r) {
								if (!r.exc) {
									frappe.msgprint(__('Work Item sent for rework!'));
									frm.reload_doc();
									d.hide();
								}
							}
						});
					}
				});
				d.show();
			});
		}
		// Set requested_by on new document
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value('requested_by', frappe.session.user);
		}

		// frm.clear_custom_buttons();

		// const user = frappe.session.user;
		// Start Now button
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
		// if (!frm.is_new() && frm.doc.status === 'Rework Needed' && frm.doc.assignee === user) {
		// 	frm.add_custom_button(__('Start Rework'), function () {
		// 		frappe.call({
		// 			method: 'taskstream.taskstream.doctype.work_item.work_item.start_now',
		// 			args: { docname: frm.doc.name },
		// 			callback: function (r) {
		// 				if (!r.exc) {
		// 					frappe.msgprint(__('Work Item re-started!'));
		// 					frm.reload_doc();
		// 				}
		// 			}
		// 		});
		// 	});
		// }
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

	is_critical: function (frm) {
		if (frm.doc.is_critical && !frm.doc.reviewer) {
			frm.set_value('reviewer', frappe.session.user);
		}
		frm.set_df_property('reviewer', 'reqd', frm.doc.is_critical);
	},

	reviewer: function (frm) {
		if (frm.doc.reviewer == frm.doc.assignee) {
			frappe.throw("Reviewer cannot be same as the Assignee")
		}
	},

	assignee: function (frm) {
		if (frm.doc.reviewer == frm.doc.assignee) {
			frappe.throw("Assignee cannot be same as the Reviewer")
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

			let is_duplicate = false;

			frm.doc.recurrence_date.forEach(d => {
				if (d.name !== row.name && d.recurrence_date === val) {
					is_duplicate = true;
				}
			});

			if (is_duplicate) {
				frappe.msgprint(__('Recurrence date cannot be repeated!'));
				frappe.model.set_value(cdt, cdn, 'recurrence_date', '');
			}
		}

		update_recurrence_description(frm);
	},
	recurrence_date_add: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	},
	recurrence_date_remove: function (frm, cdt, cdn) {
		update_recurrence_description(frm);
	}
});

frappe.ui.form.on('Recurrence Time', {
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
	}
});

frappe.ui.form.on('Recurrence Day Occurrence', {
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
	}
});

function validate_recurrence_time(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let val = row.recurrence_time;

	if (val) {
		let is_duplicate = false;

		frm.doc.recurrence_time.forEach(d => {
			if (d.name !== row.name && d.recurrence_time === val) {
				is_duplicate = true;
			}
		});

		if (is_duplicate && val == 10) {
			frappe.model.set_value(cdt, cdn, 'recurrence_time', '');
		}
		else if (is_duplicate) {
			frappe.msgprint(__('Recurrence time cannot be repeated!'));
			frappe.model.set_value(cdt, cdn, 'recurrence_time', '');
		}
	}
}

function update_recurrence_description(frm) {
	const freq = frm.doc.recurrence_frequency || 1;
	const type = frm.doc.recurrence_type || '';

	const weekdays = (frm.doc.recurrence_day || []).map(r => r.weekday);
	const day_order = {
		"Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3,
		"Thursday": 4, "Friday": 5, "Saturday": 6
	};
	const sorted_days = weekdays.sort((a, b) => day_order[a] - day_order[b]);

	const times = (frm.doc.recurrence_time || []).map(d => d.recurrence_time).filter(Boolean);
	const dates = (frm.doc.recurrence_date || []).map(d => d.recurrence_date).filter(Boolean);
	const months = (frm.doc.recurrence_month || []).map(d => d.month).filter(Boolean);

	const formatTimes = times => {
		if (!times.length) return "";
		const sorted = times.sort((a, b) => a - b).map(h => `${h}:00`);
		return " at " + sorted.join(", ") + " hrs";
	};

	const formatDates = date => {
		if (!dates.length) return "";
		const sorted = dates.sort((a, b) => a - b);
		return " on " + sorted.join(", ");
	};

	const formatMonths = months => {
		if (!months.length) return "";
		const order = [
			"January", "February", "March", "April", "May", "June",
			"July", "August", "September", "October", "November", "December"
		];
		const sorted = months.sort((a, b) => order.indexOf(a) - order.indexOf(b));
		return " in " + sorted.join(", ");
	};

	if (type === "Weekly" && !weekdays.length) {
		const desc = `Every ${freq} week${freq > 1 ? 's' : ''}`;
		frm.fields_dict.recurrence_frequency.set_description(desc);
		frm.fields_dict.recurrence_day.set_description("");
		return;
	}

	if (type === "Monthly" &&
		!(frm.doc.recurrence_date?.length || frm.doc.recurrence_day_occurrence?.length)) {
		const desc = `Every ${freq} month${freq > 1 ? 's' : ''}`;
		frm.fields_dict.recurrence_frequency.set_description(desc);
		frm.fields_dict.monthly_recurrence_based_on.set_description("");
		return;
	}

	if (type === "Yearly" && !months.length && !times.length) {
		const desc = `Every ${freq} year${freq > 1 ? 's' : ''}`;
		frm.fields_dict.recurrence_frequency.set_description(desc);
		frm.fields_dict.recurrence_month.set_description("");
		return;
	}

	if (type === "Weekly") {
		let desc = `Every ${freq} week${freq > 1 ? 's' : ''}`;
		if (sorted_days.length) {
			desc += " on " + sorted_days.join(", ");
		}
		desc += formatTimes(times);
		frm.fields_dict.recurrence_day.set_description(desc);
		frm.fields_dict.recurrence_frequency.set_description("");
		return;
	}

	if (type === "Monthly") {
		const base = `Every ${freq} month${freq > 1 ? 's' : ''}`;
		let desc = base;

		if (frm.doc.monthly_recurrence_based_on === "Date") {
			desc += formatDates(dates) + formatTimes(times);
			frm.fields_dict.monthly_recurrence_based_on.set_description(desc);
		} else if (frm.doc.monthly_recurrence_based_on === "Day") {
			const occurrences = (frm.doc.recurrence_day_occurrence || [])
				.map(d => `${d.week_order} ${d.weekday}`);
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
		let desc = `Every ${freq} year${freq > 1 ? 's' : ''}`;
		desc += formatMonths(months) + formatDates(dates) + formatTimes(times);
		frm.fields_dict.recurrence_month.set_description(desc);
		frm.fields_dict.recurrence_frequency.set_description("");
		return;
	}
}
