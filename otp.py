import random
from datetime import datetime, timedelta
from database import get_users_col
from auth import hash_password


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def send_otp_to_phone(phone: str) -> dict:
    """Find user by phone, generate OTP, send via SMS."""
    users_col = get_users_col()
    user = users_col.find_one({"phone": phone})
    if not user:
        return {"success": False, "message": "No account found with this phone number."}

    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)

    users_col.update_one(
        {"phone": phone},
        {"$set": {"reset_otp": otp, "otp_expiry": expiry}}
    )

    # Send via Twilio SMS
    try:
        from reminders import send_sms
        message = f"Your Digital Ledger password reset OTP is: {otp}. Valid for 10 minutes."
        result = send_sms(phone, message)
        if result["success"]:
            return {"success": True, "message": "OTP sent to your phone."}
        else:
            # Fallback: return OTP in message for dev/testing
            return {"success": True, "message": f"OTP (dev mode): {otp}", "otp": otp}
    except Exception:
        return {"success": True, "message": f"OTP (dev mode - Twilio not configured): {otp}", "otp": otp}


def verify_otp(phone: str, otp: str) -> dict:
    users_col = get_users_col()
    user = users_col.find_one({"phone": phone})
    if not user:
        return {"success": False, "message": "User not found."}
    if user.get("reset_otp") != otp:
        return {"success": False, "message": "Invalid OTP."}
    if datetime.utcnow() > user.get("otp_expiry", datetime.utcnow()):
        return {"success": False, "message": "OTP has expired. Please request a new one."}
    return {"success": True}


def reset_password_with_otp(phone: str, otp: str, new_password: str) -> dict:
    verify = verify_otp(phone, otp)
    if not verify["success"]:
        return verify

    users_col = get_users_col()
    users_col.update_one(
        {"phone": phone},
        {
            "$set": {"password": hash_password(new_password)},
            "$unset": {"reset_otp": "", "otp_expiry": ""},
        }
    )
    return {"success": True, "message": "Password reset successfully!"}
