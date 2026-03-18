frappe.listview_settings["Work Item"] = {
	get_indicator: function (doc) {
		if (!doc.status) return [__("No Status"), "grey", ""];
		switch (doc.status) {
			case "To Do":
				return [__("To Do"), "grey", "status,=,To Do"];
			case "In Progress":
				return [__("In Progress"), "blue", "status,=,In Progress"];
			case "Under Review":
				return [__("Under Review"), "orange", "status,=,Under Review"];
			case "Done":
				return [__("Done"), "green", "status,=,Done"];
			case "On Hold":
				return [__("On Hold"), "yellow", "status,=,On Hold"];
			case "Rework Needed":
				return [__("Rework Needed"), "orange", "status,=,Rework Needed"];
			default:
				return [__(doc.status), "grey", ""];
		}
	},
};
