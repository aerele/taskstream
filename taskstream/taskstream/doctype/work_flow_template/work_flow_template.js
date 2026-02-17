// Copyright (c) 2026, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Flow Template", {
	refresh(frm) {
        if (frm.doc.docstatus && frm.doc.active) {
            frm.add_custom_button(__('Update Template'), function() {
                frappe.new_doc(frm.doc.doctype, {
                    "template_name": frm.doc.template_name,
                    "previous_template_version": frm.doc.name,
                    "tasks": frm.doc.tasks
                });
            });
        } 
    },
});
