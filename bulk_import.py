import io
import pandas as pd
from customers import add_customer


REQUIRED_COLUMNS = ["name", "phone"]
OPTIONAL_COLUMNS = ["address"]


def import_customers_from_excel(merchant_id: str, file) -> dict:
    """
    Import customers from an uploaded Excel file.
    Expected columns: name, phone, address (optional)
    Returns summary dict.
    """
    try:
        df = pd.read_excel(file, dtype=str)
        df.columns = [c.lower().strip() for c in df.columns]

        # Validate required columns
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            return {
                "success": False,
                "message": f"Missing required column(s): {', '.join(missing)}. "
                           f"Your file must have: name, phone (and optionally: address)"
            }

        results = {"added": 0, "failed": 0, "errors": []}

        for idx, row in df.iterrows():
            name    = str(row.get("name", "")).strip()
            phone   = str(row.get("phone", "")).strip()
            address = str(row.get("address", "")).strip() if "address" in df.columns else ""

            # Skip empty rows
            if not name or not phone or name == "nan" or phone == "nan":
                results["failed"] += 1
                results["errors"].append(f"Row {idx + 2}: missing name or phone — skipped")
                continue

            result = add_customer(merchant_id, name, phone, address)
            if result["success"]:
                results["added"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"Row {idx + 2} ({name}): {result['message']}")

        return {"success": True, "results": results}

    except Exception as e:
        return {"success": False, "message": f"Error reading file: {str(e)}"}


def generate_template() -> io.BytesIO:
    """Generate a downloadable Excel template for bulk import."""
    sample_data = {
        "name":    ["Ramesh Kumar", "Priya Sharma", "Anil Singh"],
        "phone":   ["+919876543210", "+919123456789", "+919000011111"],
        "address": ["123 Main St, Delhi", "45 Park Ave, Mumbai", ""],
    }
    df = pd.DataFrame(sample_data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Customers")
    buffer.seek(0)
    return buffer
