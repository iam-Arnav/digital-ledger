from datetime import datetime
from database import get_db


def get_log_col():
    return get_db()["activity_logs"]


def log_action(merchant_id: str, action: str, details: str = ""):
    """Log a merchant action with timestamp."""
    get_log_col().insert_one({
        "merchant_id": merchant_id,
        "action": action,
        "details": details,
        "timestamp": datetime.utcnow(),
    })


def get_logs(merchant_id: str, limit: int = 100) -> list:
    logs = list(
        get_log_col()
        .find({"merchant_id": merchant_id})
        .sort("timestamp", -1)
        .limit(limit)
    )
    for log in logs:
        log["_id"] = str(log["_id"])
    return logs


def clear_logs(merchant_id: str):
    get_log_col().delete_many({"merchant_id": merchant_id})
