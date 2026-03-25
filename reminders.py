import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv()


def _get_twilio_credentials():
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise EnvironmentError("Twilio credentials not set in .env")
    return sid, token


def _twilio_request(method: str, path: str, data: dict | None = None) -> dict:
    sid, token = _get_twilio_credentials()
    base_url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}"
    url = f"{base_url}{path}"
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()

    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode())
        code = payload.get("code")
        message = payload.get("message", "Unknown Twilio error")
        friendly = _friendly_twilio_error(code, message)
        return {"success": False, "error": friendly, "error_code": code}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _friendly_twilio_error(code: int | None, message: str) -> str:
    known = {
        21608: (
            "SMS blocked by Twilio trial limits. Trial accounts can only send SMS "
            "to phone numbers you verify in the Twilio console."
        ),
        30044: (
            "SMS failed because the message is too long for your Twilio trial account. "
            "Use a shorter SMS body or upgrade the account."
        ),
        63015: (
            "WhatsApp delivery failed. This number likely has not joined your "
            "Twilio WhatsApp sandbox yet."
        ),
    }
    detail = known.get(code, message)
    return f"Twilio error {code}: {detail}" if code else detail


def _maybe_check_message_status(message_sid: str) -> dict | None:
    for _ in range(3):
        time.sleep(2)
        payload = _twilio_request("GET", f"/Messages/{message_sid}.json")
        if not payload.get("success", True):
            return payload

        status = payload.get("status")
        if status == "delivered":
            return {"success": True, "sid": message_sid, "status": status}
        if status == "failed":
            code = payload.get("error_code")
            friendly = _friendly_twilio_error(code, payload.get("error_message") or "Delivery failed")
            return {"success": False, "error": friendly, "error_code": code}
    return None


def _build_sms_reminder_message(business_name: str, customer_name: str, balance: float) -> str:
    return (
        f"Reminder from {business_name}: {customer_name}, due Rs {balance:.2f}. "
        "Please pay soon."
    )


def send_sms(to_number: str, message: str) -> dict:
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    if not from_number:
        return {"success": False, "error": "TWILIO_PHONE_NUMBER is not set in .env"}

    payload = _twilio_request(
        "POST",
        "/Messages.json",
        {"Body": message, "From": from_number, "To": to_number},
    )
    if not payload.get("success", True):
        return payload

    sid = payload["sid"]
    checked = _maybe_check_message_status(sid)
    if checked:
        return checked

    return {"success": True, "sid": sid, "status": payload.get("status", "queued")}


def send_whatsapp(to_number: str, message: str) -> dict:
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    wa_to = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number

    payload = _twilio_request(
        "POST",
        "/Messages.json",
        {"Body": message, "From": from_number, "To": wa_to},
    )
    if not payload.get("success", True):
        return payload

    sid = payload["sid"]
    checked = _maybe_check_message_status(sid)
    if checked:
        return checked

    return {"success": True, "sid": sid, "status": payload.get("status", "queued")}


def build_reminder_message(business_name: str, customer_name: str, balance: float) -> str:
    return (
        f"Dear {customer_name},\n\n"
        f"This is a friendly reminder from {business_name}. "
        f"You have an outstanding balance of ₹{balance:.2f}. "
        f"Please make your payment at your earliest convenience.\n\n"
        f"Thank you!"
    )


def run_monthly_reminders(merchant_id: str = None, channel: str = "sms") -> list:
    """
    Send reminders to all customers with outstanding balances.
    If merchant_id is None, runs for ALL merchants (scheduled job).
    channel: 'sms' or 'whatsapp'
    Returns list of result dicts.
    """
    from bson import ObjectId
    from database import get_customers_col, get_users_col

    cust_col = get_customers_col()
    users_col = get_users_col()
    results   = []

    query = {"balance": {"$gt": 0}}
    if merchant_id:
        query["merchant_id"] = merchant_id

    defaulters = list(cust_col.find(query))

    for customer in defaulters:
        # Get merchant business name
        try:
            merchant = users_col.find_one({"_id": ObjectId(customer["merchant_id"])})
            biz_name = merchant["business_name"] if merchant else "Your Merchant"
        except Exception:
            biz_name = "Your Merchant"

        if channel == "whatsapp":
            message = build_reminder_message(biz_name, customer["name"], customer["balance"])
            result = send_whatsapp(customer["phone"], message)
        else:
            message = _build_sms_reminder_message(biz_name, customer["name"], customer["balance"])
            result = send_sms(customer["phone"], message)

        results.append({
            "customer": customer["name"],
            "phone": customer["phone"],
            "balance": customer["balance"],
            "status": "sent" if result["success"] else "failed",
            "detail": result.get("sid") or result.get("error"),
        })

    return results


# ── Scheduler (runs automatically on the 1st of every month) ──────────────────
def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: run_monthly_reminders(channel="whatsapp"),
        trigger=CronTrigger(day=1, hour=9, minute=0),   # 1st of month, 9 AM UTC
        id="monthly_reminder",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
