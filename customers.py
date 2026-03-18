import bcrypt
from datetime import datetime
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
    txn_col  = get_transactions_col()
    cust_col = get_customers_col()
    customer = cust_col.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        return 100, "Low Risk"
    txns  = list(txn_col.find({"customer_id": customer_id}))
    score = 100
    now   = datetime.utcnow()
    total_credit = sum(t["amount"] for t in txns if t["type"] == "credit")
    total_paid   = sum(t["amount"] for t in txns if t["type"] == "payment")
    overdue = sum(1 for t in txns if t["type"] == "credit" and (now - t["date"]).days > 30)
    score -= overdue * 10
    if total_credit > 0 and (total_paid / total_credit) < 0.5:
        score -= 20
    if customer.get("balance", 0) > 5000:
        score -= 15
    score = max(0, min(100, score))
    if   score >= 75: category = "Low Risk"
    elif score >= 50: category = "Medium Risk"
    elif score >= 25: category = "High Risk"
    else:             category = "Defaulter"
    cust_col.update_one({"_id": ObjectId(customer_id)}, {"$set": {"credit_score": score, "risk_category": category}})
    return score, category


def delete_customer(customer_id: str, merchant_id: str) -> dict:
    cust_col = get_customers_col()
    txn_col  = get_transactions_col()
    result = cust_col.delete_one({"_id": ObjectId(customer_id), "merchant_id": merchant_id})
    if result.deleted_count:
        txn_col.delete_many({"customer_id": customer_id})
        return {"success": True}
    return {"success": False, "message": "Customer not found."}
