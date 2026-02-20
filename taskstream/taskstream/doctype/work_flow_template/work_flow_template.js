// Copyright (c) 2026, Chethan - Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Flow Template", {
	refresh(frm) {
        if (frm.doc.docstatus && frm.doc.active) {
            frm.add_custom_button(__('Update Template'), function() {
                let clean_tasks = (frm.doc.tasks || []).map(row => {
                    let d = frappe.model.copy_doc(row); 
                    d.docstatus = 0; 
                    return d;
                });
                frappe.new_doc(frm.doc.doctype, {
                    "template_name": frm.doc.template_name,
                    "version": updateVersion(frm.doc.version),
                    "previous_template_version": frm.doc.name,
                    "tasks": clean_tasks
                });
            });
        } 
    },
});

function updateVersion(version) {
    const match = version.match(/(\d+)(?!.*\d)/);

    if (match) {
        const lastNumber = match[0];
        const newNumber = parseInt(lastNumber, 10) + 1;
        
        return version.substring(0, match.index) + 
               newNumber + 
               version.substring(match.index + lastNumber.length);
    }
    return version + "1";
}