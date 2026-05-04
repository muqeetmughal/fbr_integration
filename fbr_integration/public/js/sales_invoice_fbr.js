// Client Script
// Doctype: Sales Invoice
// Apply To: Form

frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && !frm.doc.fbr_invoice_no) {
            add_fbr_button(frm);
        }
        // Do not calculate here, otherwise form becomes "Not Saved" after reload.
    },

  before_save(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    validate(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    taxes_and_charges(frm) {
        calculate_all_fbr_item_taxes(frm);
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    items_add(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    items_remove(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    qty(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    rate(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    amount(frm) {
        calculate_all_fbr_item_taxes(frm);
    }
});

frappe.ui.form.on("Sales Taxes and Charges", {
    rate(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    tax_amount(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    item_wise_tax_detail(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    account_head(frm) {
        calculate_all_fbr_item_taxes(frm);
    },

    description(frm) {
        calculate_all_fbr_item_taxes(frm);
    }
});

function classify_tax(tax_row) {
    const text = `${tax_row.account_head || ""} ${tax_row.description || ""}`.toLowerCase();

    if (text.includes("further")) return "further";
    if (text.includes("extra")) return "extra";
    if (text.includes("other tax 1")) return "other1";
    if (text.includes("other tax 2")) return "other2";
    if (
        text.includes("gst") ||
        text.includes("sales tax") ||
        text.includes("general sales tax")
    ) {
        return "sales";
    }

    return "sales";
}

function get_item_tax_from_row(tax_row, item) {
    let details = {};

    try {
        details = JSON.parse(tax_row.item_wise_tax_detail || "{}");
    } catch (e) {
        details = {};
    }

    const possible_keys = [
        item.item_code,
        item.item_name,
        item.name
    ].filter(Boolean);

    for (const key of possible_keys) {
        if (details[key]) {
            return {
                rate: flt(details[key][0] || 0, 2),
                amount: flt(details[key][1] || 0, 2)
            };
        }
    }

    return {
        rate: flt(tax_row.rate || 0, 2),
        amount: 0
    };
}

function calculate_all_fbr_item_taxes(frm) {
    if (!frm.doc.items || !frm.doc.items.length) return;

    frm.doc.items.forEach(item => {
        const base_amount = flt(
            item.net_amount || item.amount || (flt(item.qty || 0) * flt(item.rate || 0)),
            2
        );

        let sales_tax = 0;
        let further_tax = 0;
        let extra_tax = 0;
        let other_tax_1 = 0;
        let other_tax_2 = 0;

        let sales_rate = 0;
        let further_rate = 0;
        let extra_rate = 0;
        let other_rate_1 = 0;
        let other_rate_2 = 0;

        (frm.doc.taxes || []).forEach(tax_row => {
            const tax_type = classify_tax(tax_row);
            const item_tax = get_item_tax_from_row(tax_row, item);

            if (!item_tax.amount && item_tax.rate) {
                item_tax.amount = flt(base_amount * item_tax.rate / 100, 2);
            }

            if (tax_type === "sales") {
                sales_tax += item_tax.amount;
                sales_rate = item_tax.rate;
            } else if (tax_type === "further") {
                further_tax += item_tax.amount;
                further_rate = item_tax.rate;
            } else if (tax_type === "extra") {
                extra_tax += item_tax.amount;
                extra_rate = item_tax.rate;
            } else if (tax_type === "other1") {
                other_tax_1 += item_tax.amount;
                other_rate_1 = item_tax.rate;
            } else if (tax_type === "other2") {
                other_tax_2 += item_tax.amount;
                other_rate_2 = item_tax.rate;
            }
        });

        sales_tax = flt(sales_tax, 2);
        further_tax = flt(further_tax, 2);
        extra_tax = flt(extra_tax, 2);
        other_tax_1 = flt(other_tax_1, 2);
        other_tax_2 = flt(other_tax_2, 2);

        const total_tax = flt(
            sales_tax + further_tax + extra_tax + other_tax_1 + other_tax_2,
            2
        );

        item.fbr_sales_tax = sales_tax;
        item.fbr_further_tax = further_tax;
        item.fbr_extra_tax = extra_tax;
        item.fbr_other_tax_1 = other_tax_1;
        item.fbr_other_tax_2 = other_tax_2;

        item.fbr_sales_tax_rate = flt(sales_rate, 2);
        item.fbr_further_tax_rate = flt(further_rate, 2);
        item.fbr_extra_tax_rate = flt(extra_rate, 2);
        item.fbr_other_tax_1_rate = flt(other_rate_1, 2);
        item.fbr_other_tax_2_rate = flt(other_rate_2, 2);

        item.fbr_total_tax_amount = total_tax;
        item.fbr_tax_inclusive_amount = flt(base_amount + total_tax, 2);
    });

    frm.refresh_field("items");
}
function add_fbr_button(frm) {
    // if (frm.__fbr_button_added) return;
    // frm.__fbr_button_added = true;

    const btn = frm.add_custom_button(__("Send to FBR"), function () {
        if (frm.doc.fbr_invoice_no) {
            frappe.msgprint({
                title: __("Already Submitted"),
                indicator: "red",
                message: `
                    <div style="font-size:14px; line-height:1.6;">
                        <p>🚫 <b>Invoice already sent to Iris-FBR Portal</b></p>
                        <p>FBR Invoice No.: <b>${frm.doc.fbr_invoice_no}</b></p>
                    </div>
                `
            });
            return;
        }

        frappe.confirm(__("Are you sure you want to send this invoice to FBR?"), function () {
            frappe.call({
                method: "fbr_integration.fbr_integration.api.handler.send_to_fbr_si",
                args: {
                    name: frm.doc.name
                },
                freeze: true,
                freeze_message: __("Sending invoice to FBR..."),
                callback(r) {
                    const resp = r.message;

                    if (!resp) {
                        frappe.msgprint({
                            title: __("Error"),
                            indicator: "red",
                            message: __("No response from server")
                        });
                        return;
                    }

                    if (resp.success === false) {
                        frappe.msgprint({
                            title: __("FBR Error"),
                            indicator: "red",
                            message: `<pre>${frappe.utils.escape_html(resp.error || "Unknown error")}</pre>`
                        });
                        return;
                    }

                    frappe.msgprint({
                        title: __("Invoice Sent"),
                        indicator: "green",
                        message: `
                            <div style="font-size:14px; line-height:1.6;">
                                <p>🟢 <b>Invoice submitted successfully.</b></p>
                                <p><b>FBR Invoice No:</b> ${resp.invoice_no || ""}</p>
                            </div>
                        `
                    });

                    frm.reload_doc();
                }
            });
        });
    });

    btn.removeClass("btn-default").addClass("btn-danger");
}