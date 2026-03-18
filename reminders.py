import os
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv
from database import get_customers_col, get_users_col
from bson import ObjectId

load_dotenv()


def _get_twilio_client():
    sid   = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise EnvironmentError("Twilio credentials not set in .env")
    return Client(sid, token)


def send_sms(to_number: str, message: str) -> dict:
    try:
        client = _get_twilio_client()
        from_number = os.getenv("TWILIO_PHONE_NUMBER")
        msg = client.messages.create(body=message, from_=from_number, to=to_number)
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_whatsapp(to_number: str, message: str) -> dict:
    try:
        client = _get_twilio_client()
        from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        wa_to = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
        msg = client.messages.create(body=message, from_=from_number, to=wa_to)
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    cust_col  = get_customers_col()
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

        message = build_reminder_message(biz_name, customer["name"], customer["balance"])

        if channel == "whatsapp":
            result = send_whatsapp(customer["phone"], message)
        else:
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
