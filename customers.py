import bcrypt
from datetime import datetime, timedelta
from bson import ObjectId
from database import get_customers_col, get_transactions_col


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

def _verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


def add_customer(merchant_id: str, name: str, phone: str,
                 address: str = "", portal_pin: str = "") -> dict:
    col = get_customers_col()
    if col.find_one({"merchant_id": merchant_id, "phone": phone}):
        return {"success": False, "message": "Customer with this phone already exists."}
    customer = {
        "merchant_id":   merchant_id,
        "name":          name,
        "phone":         phone,
        "address":       address,
        "balance":       0.0,
        "total_credit":  0.0,
        "total_paid":    0.0,
        "credit_score":  100,
        "risk_category": "Low Risk",
        "portal_pin":    _hash_pin(portal_pin) if portal_pin else "",
        "created_at":    datetime.utcnow(),
        "last_transaction": None,
    }
    result = col.insert_one(customer)
    return {"success": True, "customer_id": str(result.inserted_id)}


def customer_portal_login(phone: str, pin: str) -> dict:
    col = get_customers_col()
    customer = col.find_one({"phone": phone})
    if not customer:
        return {"success": False, "message": "Phone number not found."}
    if not customer.get("portal_pin"):
        return {"success": False, "message": "Portal access not set up. Ask your merchant."}
    if not _verify_pin(pin, customer["portal_pin"]):
        return {"success": False, "message": "Incorrect PIN."}
    customer["_id"] = str(customer["_id"])
    return {"success": True, "customer": customer}


def update_customer_pin(customer_id: str, merchant_id: str, new_pin: str) -> dict:
    col = get_customers_col()
    result = col.update_one(
        {"_id": ObjectId(customer_id), "merchant_id": merchant_id},
        {"$set": {"portal_pin": _hash_pin(new_pin)}}
    )
    return {"success": True} if result.modified_count else {"success": False, "message": "Not found."}


def get_customers(merchant_id: str) -> list:
    col = get_customers_col()
    customers = list(col.find({"merchant_id": merchant_id}))
    for c in customers:
        c["_id"] = str(c["_id"])
    return customers


def get_customer_by_id(customer_id: str):
    col = get_customers_col()
    c = col.find_one({"_id": ObjectId(customer_id)})
    if c:
        c["_id"] = str(c["_id"])
    return c


def get_defaulters(merchant_id: str) -> list:
    col = get_customers_col()
    defaulters = list(col.find({"merchant_id": merchant_id, "balance": {"$gt": 0}}))
    for c in defaulters:
        c["_id"] = str(c["_id"])
    return defaulters


def compute_credit_score(customer_id: str):
    """
    Advanced rule-based credit scoring (0-100)

    FACTORS (total 100 points):
    1. Payment Ratio       — 30 pts  (how much % paid back)
    2. Overdue Credits     — 20 pts  (unpaid credits > 30 days)
    3. Balance Size        — 20 pts  (current outstanding amount)
    4. Payment Frequency   — 15 pts  (how many times paid)
    5. Recency             — 10 pts  (how recently paid)
    6. Consistency Bonus   —  5 pts  (paid for every credit)
    """
    txn_col  = get_transactions_col()
    cust_col = get_customers_col()

    customer = cust_col.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        return 100, "Low Risk"

    txns = list(txn_col.find({"customer_id": customer_id}).sort("date", 1))
    now  = datetime.utcnow()

    # No transactions yet — perfect score
    if not txns:
        score    = 100
        category = "Excellent"
        cust_col.update_one({"_id": ObjectId(customer_id)},
                            {"$set": {"credit_score": score, "risk_category": category}})
        return score, category

    credits  = [t for t in txns if t["type"] == "credit"]
    payments = [t for t in txns if t["type"] == "payment"]

    total_credit = sum(t["amount"] for t in credits)
    total_paid   = sum(t["amount"] for t in payments)
    balance      = customer.get("balance", 0)

    score = 0  # build up from 0

    # ── FACTOR 1: Payment Ratio (0–30 points) ────────────────────────────────
    if total_credit > 0:
        ratio = total_paid / total_credit
        if   ratio >= 1.0:  score += 30
        elif ratio >= 0.85: score += 26
        elif ratio >= 0.70: score += 22
        elif ratio >= 0.55: score += 17
        elif ratio >= 0.40: score += 12
        elif ratio >= 0.25: score += 7
        elif ratio >= 0.10: score += 3
        else:               score += 0
    else:
        score += 30  # no credit = perfect ratio

    # ── FACTOR 2: Overdue Credits (0–20 points) ──────────────────────────────
    overdue_count = sum(1 for t in credits if (now - t["date"]).days > 30)
    if   overdue_count == 0: score += 20
    elif overdue_count == 1: score += 14
    elif overdue_count == 2: score += 8
    elif overdue_count == 3: score += 3
    else:                    score += 0

    # ── FACTOR 3: Balance Size (0–20 points) ─────────────────────────────────
    if   balance <= 0:       score += 20  # fully settled
    elif balance <= 500:     score += 18
    elif balance <= 1000:    score += 16
    elif balance <= 3000:    score += 13
    elif balance <= 5000:    score += 10
    elif balance <= 10000:   score += 7
    elif balance <= 25000:   score += 4
    elif balance <= 100000:  score += 2
    else:                    score += 0   # above 1 lakh = worst

    # ── FACTOR 4: Payment Frequency (0–15 points) ────────────────────────────
    num_payments = len(payments)
    if   num_payments >= 10: score += 15
    elif num_payments >= 7:  score += 12
    elif num_payments >= 5:  score += 9
    elif num_payments >= 3:  score += 6
    elif num_payments >= 1:  score += 3
    else:                    score += 0

    # ── FACTOR 5: Recency of last payment (0–10 points) ──────────────────────
    if payments:
        days_since = (now - payments[-1]["date"]).days
        if   days_since <= 7:  score += 10
        elif days_since <= 15: score += 8
        elif days_since <= 30: score += 6
        elif days_since <= 60: score += 4
        elif days_since <= 90: score += 2
        else:                  score += 0
    # no payments = 0 points for recency

    # ── FACTOR 6: Consistency Bonus (0–5 points) ─────────────────────────────
    if credits and payments:
        ratio_txn = num_payments / len(credits)
        if   ratio_txn >= 1.0:  score += 5
        elif ratio_txn >= 0.75: score += 3
        elif ratio_txn >= 0.50: score += 1

    score = max(0, min(100, score))

    # ── Risk Categories ───────────────────────────────────────────────────────
    if   score >= 80: category = "Excellent"
    elif score >= 65: category = "Low Risk"
    elif score >= 50: category = "Medium Risk"
    elif score >= 30: category = "High Risk"
    else:             category = "Defaulter"

    cust_col.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {"credit_score": score, "risk_category": category}}
    )
    return score, category


def delete_customer(customer_id: str, merchant_id: str) -> dict:
    cust_col = get_customers_col()
    txn_col  = get_transactions_col()
    result = cust_col.delete_one({"_id": ObjectId(customer_id), "merchant_id": merchant_id})
    if result.deleted_count:
        txn_col.delete_many({"customer_id": customer_id})
        return {"success": True}
    return {"success": False, "message": "Customer not found."}
