// Copyright (c) 2026, Active Minutes and contributors
// For license information, please see license.txt

frappe.ui.form.on("MongoDB Settings", {

    refresh(frm) {

        let btn = frm.add_custom_button('<i class="fa fa-plug"></i> Test Connection', () => {

            frappe.call({
                method: "mongo_bridge.mongo_bridge.doctype.mongodb_settings.mongodb_settings.test_connection",
                callback(r) {

                    if (!r.message) return;

                    if (r.message.status === "success") {

                        frappe.msgprint({
                            title: "MongoDB",
                            message: r.message.message,
                            indicator: "green"
                        });

                    } else {

                        frappe.msgprint({
                            title: "MongoDB Connection Failed",
                            message: r.message.message,
                            indicator: "red"
                        });

                    }

                }
            });

        });

        $(btn).css({
            "background-color": "#00684a",
            "color": "#ffffff",
            "border-color": "#00684a"
        });

    }

});