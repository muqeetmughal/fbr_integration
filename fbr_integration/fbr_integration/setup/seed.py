import frappe
from fbr_integration.fbr_integration.api.fbr_api import (
    get_fbr_api_config,
    handle_disabled_integration,
)
import os
import tqdm
import requests
import json

url = "https://gw.fbr.gov.pk/pdi/v1"


def get_access_token():
    settings = frappe.get_single("FBR Invoice Settings")
    if not settings.enabled:
        return None

    api_url, token = get_fbr_api_config(settings)

    return token


def title_case(s):
    return " ".join(word.capitalize() for word in s.split())


def hs_code():

    path = frappe.get_module_path("fbr_integration")
    full_path = os.path.join(path, "setup")
    print("Module path:", path)

    json_file = os.path.join(full_path, "hs_codes.json")

    # Check if JSON file exists
    if os.path.exists(json_file):
        print("Loading HS Codes from file...")
        with open(json_file, "r") as f:
            hs_codes = json.load(f)
    else:
        print("Fetching HS Codes from FBR API...")
        headers = {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        }

        response = requests.get(f"{url}/itemdesccode", headers=headers)
        if response.status_code == 200:
            hs_codes = response.json()
        else:
            hs_codes = []

        # Save to JSON file
        with open(json_file, "w") as f:
            json.dump(hs_codes, f)

    # Insert HS Codes into Doctype
    # Delete all existing HS Codes first
    frappe.db.delete("HS Code")
    frappe.db.commit()

    for hs in tqdm.tqdm(hs_codes, desc="Inserting HS Codes"):
        hs_code = hs.get("hS_CODE")
        description = title_case(str(hs.get("description")))

        if description.startswith("-"):
            description = description.replace("-", "").strip()

        if hs_code:
            try:
                existing = frappe.get_doc("HS Code", hs_code)
                existing.hs_code_detail = description
                existing.save()
            except frappe.DoesNotExistError:
                doc = frappe.get_doc(
                    {
                        "doctype": "HS Code",
                        "hs_code": hs_code,
                        "hs_code_detail": description,
                    }
                )
                doc.insert(ignore_if_duplicate=True)
            except Exception as e:
                frappe.log_error(f"Error inserting HS Code {hs_code}: {str(e)}")


def provinces():

    path = frappe.get_module_path("fbr_integration")
    full_path = os.path.join(path, "setup")
    print("Module path:", path)

    json_file = os.path.join(full_path, "provinces.json")

    # Check if JSON file exists
    if os.path.exists(json_file):
        print("Loading Provinces from file...")
        with open(json_file, "r") as f:
            provinces = json.load(f)
    else:
        print("Fetching Provinces from FBR API...")
        headers = {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        }

        response = requests.get(f"{url}/provinces", headers=headers)
        if response.status_code == 200:
            provinces = response.json()
        else:
            provinces = []

        # Save to JSON file
        with open(json_file, "w") as f:
            json.dump(provinces, f)

    # Insert Provinces into Doctype
    # Delete all existing Provinces first
    frappe.db.delete("Buyer Province")
    frappe.db.commit()

    for prov in tqdm.tqdm(provinces, desc="Inserting Provinces"):
        province_name = prov.get("stateProvinceDesc")

        if province_name:
            try:
                existing = frappe.get_doc("Buyer Province", province_name)
                existing.save()
            except frappe.DoesNotExistError:
                doc = frappe.get_doc(
                    {"doctype": "Buyer Province", "buyer_province": province_name}
                )
                doc.insert(ignore_if_duplicate=True)
            except Exception as e:
                frappe.log_error(f"Error inserting Province {province_name}: {str(e)}")


def uom():
    path = frappe.get_module_path("fbr_integration")
    full_path = os.path.join(path, "setup")
    print("Module path:", path)

    json_file = os.path.join(full_path, "uoms.json")

    # Check if JSON file exists
    if os.path.exists(json_file):
        print("Loading UOMs from file...")
        with open(json_file, "r") as f:
            uoms = json.load(f)
    else:
        print("Fetching UOMs from FBR API...")
        headers = {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        }

        response = requests.get(f"{url}/uom", headers=headers)
        if response.status_code == 200:
            uoms = response.json()
        else:
            uoms = []

        # Save to JSON file
        with open(json_file, "w") as f:
            json.dump(uoms, f)

    # Insert UOMs into Doctype
    # Delete all existing UOMs first
    frappe.db.delete("FBR UoM")
    frappe.db.commit()

    for u in tqdm.tqdm(uoms, desc="Inserting UOMs"):
        uom_name = u.get("description")

        if uom_name:
            try:
                existing = frappe.get_doc("FBR UoM", uom_name)
                existing.save()
            except frappe.DoesNotExistError:
                doc = frappe.get_doc({"doctype": "FBR UoM", "fbr_uom": uom_name})
                doc.insert(ignore_if_duplicate=True)
            except Exception as e:
                frappe.log_error(f"Error inserting UOM {uom_name}: {str(e)}")


def sale_type():
    path = frappe.get_module_path("fbr_integration")
    full_path = os.path.join(path, "setup")
    print("Module path:", path)
    json_file = os.path.join(full_path, "sale_types.json")
    # Check if JSON file exists
    if os.path.exists(json_file):
        print("Loading Sale Types from file...")
        with open(json_file, "r") as f:
            sale_types = json.load(f)
    else:
        print("Fetching Sale Types from FBR API...")
        headers = {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        }
        response = requests.get(f"{url}/transtypecode", headers=headers)
        if response.status_code == 200:
            sale_types = response.json()
        else:
            sale_types = []
        # Save to JSON file
        with open(json_file, "w") as f:
            json.dump(sale_types, f)

    # Insert Sale Types into Doctype
    # Delete all existing Sale Types first

    frappe.db.delete("Sale Type")
    frappe.db.commit()

    for st in tqdm.tqdm(sale_types, desc="Inserting Sale Types"):
        sale_type_desc = st.get("transactioN_DESC")

        if sale_type_desc:
            try:
                existing = frappe.get_doc("Sale Type", sale_type_desc)
                existing.sale_type = sale_type_desc
                existing.save()
            except frappe.DoesNotExistError:
                doc = frappe.get_doc(
                    {
                        "doctype": "Sale Type",
                        "sale_type": sale_type_desc,
                    }
                )
                doc.insert(ignore_if_duplicate=True)
            except Exception as e:
                frappe.log_error(
                    f"Error inserting Sale Type {sale_type_desc}: {str(e)}"
                )


# @frappe.whitelist()
def seed_fbr_data():
    sale_type()
    hs_code()
    provinces()
    uom()