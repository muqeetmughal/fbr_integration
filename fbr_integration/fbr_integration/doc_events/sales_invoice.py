import json
import frappe
from frappe.utils import flt


def before_save_sales_invoice(doc, method=None):
    """
    Hook: Sales Invoice Before Save
    Calculates FBR custom tax fields on Sales Invoice Item
    using Sales Taxes and Charges item_wise_tax_detail.
    """

    for item in doc.items:
        base_amount = flt(
            item.net_amount or item.amount or (flt(item.qty) * flt(item.rate)),
            2
        )

        # Reset Rates
        item.fbr_sales_tax_rate = 0
        item.fbr_further_tax_rate = 0
        item.fbr_extra_tax_rate = 0
        item.fbr_other_tax_1_rate = 0
        item.fbr_other_tax_2_rate = 0

        # Reset Amounts
        item.fbr_sales_tax = 0
        item.fbr_further_tax = 0
        item.fbr_extra_tax = 0
        item.fbr_other_tax_1 = 0
        item.fbr_other_tax_2 = 0
        item.fbr_total_tax_amount = 0
        item.fbr_tax_inclusive_amount = base_amount

        for tax_row in doc.taxes:
            tax_type = classify_fbr_tax(tax_row)

            rate, amount = get_item_tax_from_tax_row(tax_row, item)

            if not amount and rate:
                amount = flt(base_amount * rate / 100, 2)

            if tax_type == "sales":
                item.fbr_sales_tax_rate = rate
                item.fbr_sales_tax += amount

            elif tax_type == "further":
                item.fbr_further_tax_rate = rate
                item.fbr_further_tax += amount

            elif tax_type == "extra":
                item.fbr_extra_tax_rate = rate
                item.fbr_extra_tax += amount

            elif tax_type == "other1":
                item.fbr_other_tax_1_rate = rate
                item.fbr_other_tax_1 += amount

            elif tax_type == "other2":
                item.fbr_other_tax_2_rate = rate
                item.fbr_other_tax_2 += amount

        item.fbr_sales_tax = flt(item.fbr_sales_tax, 2)
        item.fbr_further_tax = flt(item.fbr_further_tax, 2)
        item.fbr_extra_tax = flt(item.fbr_extra_tax, 2)
        item.fbr_other_tax_1 = flt(item.fbr_other_tax_1, 2)
        item.fbr_other_tax_2 = flt(item.fbr_other_tax_2, 2)

        item.fbr_total_tax_amount = flt(
            item.fbr_sales_tax
            + item.fbr_further_tax
            + item.fbr_extra_tax
            + item.fbr_other_tax_1
            + item.fbr_other_tax_2,
            2
        )

        item.fbr_tax_inclusive_amount = flt(
            base_amount + item.fbr_total_tax_amount,
            2
        )


def classify_fbr_tax(tax_row):
    text = f"{tax_row.account_head or ''} {tax_row.description or ''}".lower()

    if "further" in text:
        return "further"
    if "extra" in text:
        return "extra"
    if "other tax 1" in text:
        return "other1"
    if "other tax 2" in text:
        return "other2"
    if "gst" in text or "sales tax" in text or "general sales tax" in text:
        return "sales"

    return "sales"


def get_item_tax_from_tax_row(tax_row, item):
    details = {}

    if tax_row.item_wise_tax_detail:
        try:
            details = json.loads(tax_row.item_wise_tax_detail)
        except Exception:
            details = {}

    possible_keys = [
        item.item_code,
        item.item_name,
        item.name,
    ]

    for key in possible_keys:
        if key and key in details:
            return flt(details[key][0], 2), flt(details[key][1], 2)

    return flt(tax_row.rate, 2), 0