import frappe
import requests
import json
import urllib3
import os
import qrcode
from frappe import _

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def safe_float(val):
    try:
        num = float(val)
        return num if num >= 0 else 0
    except (TypeError, ValueError):
        return 0


def extra_tax_value(val, sale_type_str):
    reduced_types = ("goodsatreducedrate", "reducedrate", "rr")

    if sale_type_str in reduced_types:
        return ""

    try:
        num = float(val)
        return num if num > 0 else ""
    except (TypeError, ValueError):
        return ""


def safe_update_doc(doc, **values):
    try:
        for field, value in values.items():
            if hasattr(doc, field):
                setattr(doc, field, value)

        doc.save(ignore_permissions=True)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "FBR: Failed to update invoice status")


def get_fbr_api_config(settings):
    if settings.integration_type == "Sandbox":
        return settings.sandbox_api_url, settings.sandbox_security_token

    if settings.integration_type == "Production":
        return settings.production_api_url, settings.production_security_token

    frappe.throw(_("Invalid FBR integration type. Please set Sandbox or Production."))


def get_address_details(address_name):
    if not address_name:
        return "", ""

    try:
        address_doc = frappe.get_doc("Address", address_name)

        address_parts = [
            address_doc.address_line1,
            address_doc.address_line2,
            address_doc.city,
        ]

        full_address = ", ".join([part for part in address_parts if part])
        province = address_doc.state or ""

        return full_address, province

    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"FBR: Failed to get address {address_name}"
        )
        return "", ""


def build_fbr_payload(doc):
    seller_address, seller_province = get_address_details(
        getattr(doc, "company_address", None)
    )

    buyer_address, buyer_province = get_address_details(
        getattr(doc, "customer_address", None)
    )

    items_list = []
    print("doc.items", doc.items)

    for item in doc.items:
        sale_type_str = str(item.fbr_sale_type or "").lower().replace(" ", "")

        if doc.fbr_scenario_id == "SN006":
            rate_val = "Exempt"
        else:
            rate_val = "{:.2f}%".format(safe_float(item.fbr_sales_tax_rate))
            rate_val = "18%"
        
        items_list.append(
            {
                # "hsCode": item.fbr_hs_code or "",
                "hsCode": "3306.1010" or "",
                "productDescription": item.item_name or "",
                "rate": rate_val,
                "uoM": "Numbers, pieces, units",
                # "uoM": item.fbr_fbr_uom or "",
                "quantity": safe_float(item.qty),
                "totalValues": safe_float(item.fbr_tax_inclusive_amount),
                "valueSalesExcludingST": safe_float(item.amount),
                "fixedNotifiedValueOrRetailPrice": safe_float(item.rate),
                "salesTaxApplicable": safe_float(item.fbr_sales_tax),
                "salesTaxWithheldAtSource": 0,
                "extraTax": extra_tax_value(item.fbr_extra_tax, sale_type_str),
                "furtherTax": safe_float(item.fbr_further_tax),
                "sroScheduleNo": item.fbr_sro_schedule_no or "",
                "fedPayable": 0,
                "discount": safe_float(item.discount_amount),
                "saleType": item.fbr_sale_type or "Goods at standard rate (default)",
                "sroItemSerialNo": item.fbr_sro_item_sno or "",
            }
        )

    return {
        "invoiceType": doc.fbr_invoice_type or "",
        "invoiceDate": str(doc.posting_date),
        "sellerNTNCNIC": doc.company_tax_id or "3520262991913",
        "sellerBusinessName": doc.company or "",
        "sellerAddress": seller_address,
        "sellerProvince": seller_province or "Punjab",
        "buyerNTNCNIC": doc.tax_id or "",
        "buyerBusinessName": doc.customer or "",
        "buyerAddress": buyer_address,
        "buyerProvince": buyer_province or "Punjab",
        "invoiceRefNo": doc.name,
        "scenarioId": doc.fbr_scenario_id or "",
        "buyerRegistrationType": doc.fbr_tax_payer_type or "Unregistered",
        "items": items_list,
    }


def handle_disabled_integration(doc):
    message = (
        "FBR Integration is disabled in FBR Invoice Settings. "
        "Invoice was not sent to FBR."
    )

    response_data = {
        "status": "Disabled",
        "message": message,
        "invoice": doc.name,
    }

    frappe.logger().info(f"{message} Sales Invoice: {doc.name}")

    safe_update_doc(
        doc,
        fbr_responsed="Disabled",
        fbr_invoice_status="Disabled",
        fbr_invoice_status_code="",
        fbr_invoice_error=message,
        fbr_digital_invoice_response=json.dumps(response_data, indent=2),
    )

    frappe.msgprint(
        msg=f"""
            <div style="font-size:14px; line-height:1.6;">
                ⚠️ <b>FBR Integration Disabled</b><br>
                Sales Invoice <b>{doc.name}</b> was submitted locally,
                but it was not sent to FBR.
                <br><br>
                Enable <b>FBR Invoice Settings</b> to send invoices to FBR.
            </div>
        """,
        title="FBR Disabled",
        indicator="orange",
    )

    return {
        "status": "disabled",
        "message": message,
        "invoice": doc.name,
    }


def handle_success_response(doc, settings, res_json):
    validation = res_json.get("validationResponse") or {}
    invoice_number = res_json.get("invoiceNumber", "")

    invoice_item_nos = []

    for status in validation.get("invoiceStatuses", []):
        invoice_item_no = status.get("invoiceNo", "")
        if invoice_item_no:
            invoice_item_nos.append(invoice_item_no)

    safe_update_doc(
        doc,
        fbr_integration_type=settings.integration_type,
        fbr_invoice_no=invoice_number,
        fbr_submission_time=res_json.get("dated", frappe.utils.now_datetime()),
        fbr_invoice_status=validation.get("status", ""),
        fbr_invoice_status_code=validation.get("statusCode", ""),
        fbr_invoice_error=validation.get("error", ""),
        fbr_invoice_statuses=json.dumps(
            validation.get("invoiceStatuses", []), indent=2
        ),
        fbr_invoice_item_no=", ".join(invoice_item_nos),
        fbr_qr_code=invoice_number,
        fbr_digital_invoice_response=json.dumps(res_json, indent=2),
        fbr_responsed="Success",
    )

    generate_fbr_barcode(invoice_number, doc.name)

    frappe.msgprint(
        msg=f"""
            <div style="font-size:14px; line-height:1.6;">
                <p>🟢 <b>Invoice Sent</b></p>
                <p>🎉 <b>Congratulations!</b></p>
                <p>
                    Your Sales Invoice <b>{doc.name}</b> has been successfully
                    submitted to the <b>IRIS Portal – FBR</b>.
                </p>
                <p>
                    <b>FBR Invoice No:</b> {invoice_number}
                </p>
                <p style="color:green;">
                    ☑ Thank you for staying compliant and digital by
                    InfintrixERP Pakistan!
                </p>
            </div>
        """,
        title="Invoice Sent",
        indicator="green",
    )

    return {
        "status": "success",
        "invoice": doc.name,
        "fbr_invoice_no": invoice_number,
        "response": res_json,
    }


def handle_fbr_error_response(doc, res_json):
    validation = res_json.get("validationResponse") or {}

    error_message = validation.get("error") or json.dumps(res_json)

    safe_update_doc(
        doc,
        fbr_responsed="Error",
        fbr_invoice_status=validation.get("status", "Error"),
        fbr_invoice_status_code=validation.get("statusCode", ""),
        fbr_invoice_error=error_message,
        fbr_digital_invoice_response=json.dumps(res_json, indent=2),
    )

    error_msg, pretty_json = format_fbr_error(res_json)

    frappe.throw(f"""
    <div style="font-size:14px; line-height:1.6; color:red;">
        ❌ <b>FBR Error</b><br><br>

        <b>Message:</b><br>
        {error_msg}<br><br>

        <b>Full Response:</b>
        <pre style="
            background:#f6f6f6;
            padding:10px;
            border-radius:5px;
            font-size:12px;
            overflow-x:auto;
        ">{pretty_json}</pre>
    </div>
    """)


def format_fbr_error(res_json):
    try:
        # If API returned wrapped JSON string inside raw_response
        if "raw_response" in res_json:
            raw = res_json.get("raw_response")

            if isinstance(raw, str):
                parsed = json.loads(raw)
            else:
                parsed = raw
        else:
            parsed = res_json

        # Extract meaningful part
        validation = parsed.get("validationResponse", {})

        pretty_json = json.dumps(parsed, indent=2)
        error_msg = validation.get("error", "Unknown error")

        return error_msg, pretty_json

    except Exception:
        # fallback if parsing fails
        return "Unable to parse FBR response", json.dumps(res_json, indent=2)


def send_invoice_to_fbr(doc, method=None):
    try:
        settings = frappe.get_single("FBR Invoice Settings")

        if not settings.enabled:
            return handle_disabled_integration(doc)

        api_url, token = get_fbr_api_config(settings)

        if not api_url:
            frappe.throw(_("FBR API URL is missing."))

        if not token:
            frappe.throw(_("FBR security token is missing."))

        payload = build_fbr_payload(doc)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        frappe.logger().info(
            f"Sending Invoice to FBR ({settings.integration_type}): "
            f"{json.dumps(payload, indent=2)}"
        )
        print("Payload: ", json.dumps(payload, indent=2))

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            verify=False,
            timeout=60,
        )

        try:
            res_json = response.json()

        except ValueError:
            res_json = {
                "raw_response": response.text,
                "status_code": response.status_code,
            }

        print("Response JSON: ", json.dumps(res_json, indent=2))

        response.raise_for_status()

        frappe.logger().info(f"FBR Response: {json.dumps(res_json, indent=2)}")

        validation = res_json.get("validationResponse") or {}

        if validation.get("statusCode") == "00":
            return handle_success_response(doc, settings, res_json)

        return handle_fbr_error_response(doc, res_json)

    except requests.exceptions.Timeout:
        message = "FBR API request timed out."

        safe_update_doc(
            doc,
            fbr_responsed="Timeout",
            fbr_invoice_error=message,
            fbr_digital_invoice_response=message,
        )

        frappe.throw(_(message))

    except requests.exceptions.ConnectionError:
        message = "Could not connect to FBR API. Please check internet or API URL."

        safe_update_doc(
            doc,
            fbr_responsed="ConnectionError",
            fbr_invoice_error=message,
            fbr_digital_invoice_response=message,
        )

        frappe.throw(_(message))

    except requests.exceptions.HTTPError as e:
        response_text = ""

        if getattr(e, "response", None) is not None:
            response_text = e.response.text
        else:
            response_text = str(e)

        safe_update_doc(
            doc,
            fbr_responsed="HTTPError",
            fbr_invoice_error=response_text,
            fbr_digital_invoice_response=response_text,
        )

        frappe.throw(f"""
            <div>
            <div style="font-size:14px; line-height:1.6; color:green;">
                ❌ <b>FBR Payload</b><br>
                {json.dumps(payload, indent=2)}
            </div>
            <div style="font-size:14px; line-height:1.6; color:red;">
                ❌ <b>FBR HTTP Error</b><br>
                {response_text}
            </div>
            </div>
            
            """)

    # except Exception as e:
    #     safe_update_doc(
    #         doc,
    #         fbr_responsed="Exception",
    #         fbr_invoice_error=str(e),
    #         fbr_digital_invoice_response=str(e),
    #     )

    #     frappe.log_error(
    #         frappe.get_traceback(),
    #         "FBR Invoice Submission Failed"
    #     )

    #     frappe.throw(
    #         f"""
    #         <div style="font-size:14px; line-height:1.6; color:red;">
    #             ❌ <b>FBR Exception</b><br>
    #             {str(e)}
    #         </div>
    #         """
    #     )


def after_submit_invoice(doc, method=None):
    return send_invoice_to_fbr(doc)


@frappe.whitelist()
def generate_fbr_barcode(code=None, docname=None):
    try:
        if not code or not docname:
            frappe.throw(_("Invalid QR Code data or document name."))

        name_tobe = f"{docname}.png"

        site_dir_path = frappe.utils.get_bench_path()
        current_site = frappe.local.site or frappe.get_site_path().split("/")[-1]
        site_path = os.path.join(site_dir_path, "sites", current_site)

        qrcode_dir = os.path.join(site_path, "public", "files", "qrcodes")

        os.makedirs(qrcode_dir, mode=0o775, exist_ok=True)

        qr_file_path = os.path.join(qrcode_dir, name_tobe)

        if not os.path.isfile(qr_file_path):
            img = qrcode.make(code)
            img.save(qr_file_path)

        return qr_file_path

    except Exception:
        frappe.log_error(frappe.get_traceback(), "FBR Barcode Generation Failed")

        frappe.throw(_("Failed to generate FBR barcode. Check error logs."))
