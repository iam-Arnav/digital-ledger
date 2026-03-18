from datetime import datetime
from bson import ObjectId
from database import get_transactions_col, get_customers_col
from customers import compute_credit_score


def add_transaction(merchant_id: str, customer_id: str, txn_type: str,
                    amount: float, note: str = "") -> dict:
    if amount <= 0:
        return {"success": False, "message": "Amount must be positive."}
    if txn_type not in ("credit", "payment"):
        return {"success": False, "message": "Invalid transaction type."}

    txn_col  = get_transactions_col()
    cust_col = get_customers_col()

    customer = cust_col.find_one({"_id": ObjectId(customer_id), "merchant_id": merchant_id})
    if not customer:
        return {"success": False, "message": "Customer not found."}

    txn = {
        "merchant_id":   merchant_id,
        "customer_id":   customer_id,
        "customer_name": customer["name"],
        "type":          txn_type,
        "amount":        amount,
        "note":          note,
        "date":          datetime.utcnow(),
        "edited":        False,
    }
    txn_col.insert_one(txn)

    balance_delta = amount if txn_type == "credit" else -amount
    credit_delta  = amount if txn_type == "credit" else 0
    paid_delta    = amount if txn_type == "payment" else 0

    cust_col.update_one(
        {"_id": ObjectId(customer_id)},
        {"$inc": {"balance": balance_delta, "total_credit": credit_delta, "total_paid": paid_delta},
         "$set": {"last_transaction": datetime.utcnow()}}
    )
    compute_credit_score(customer_id)

    # Return new balance for receipt
    updated = cust_col.find_one({"_id": ObjectId(customer_id)})
    return {"success": True, "new_balance": updated.get("balance", 0)}


def edit_transaction(txn_id: str, merchant_id: str,
                     new_amount: float, new_note: str) -> dict:
    """Edit a transaction amount/note and recalculate customer balance."""
    txn_col  = get_transactions_col()
    cust_col = get_customers_col()

    txn = txn_col.find_one({"_id": ObjectId(txn_id), "merchant_id": merchant_id})
    if not txn:
        return {"success": False, "message": "Transaction not found."}

    old_amount = txn["amount"]
    txn_type   = txn["type"]
    customer_id = txn["customer_id"]

    # Reverse old effect, apply new effect
    if txn_type == "credit":
        balance_delta = new_amount - old_amount
        credit_delta  = new_amount - old_amount
        paid_delta    = 0
    else:
        balance_delta = -(new_amount - old_amount)
        credit_delta  = 0
        paid_delta    = new_amount - old_amount

    txn_col.update_one(
        {"_id": ObjectId(txn_id)},
        {"$set": {"amount": new_amount, "note": new_note, "edited": True,
                  "edited_at": datetime.utcnow()}}
    )
    cust_col.update_one(
        {"_id": ObjectId(customer_id)},
        {"$inc": {"balance": balance_delta, "total_credit": credit_delta, "total_paid": paid_delta}}
    )
    compute_credit_score(customer_id)
    return {"success": True}


def delete_transaction(txn_id: str, merchant_id: str) -> dict:
    """Delete a transaction and reverse its effect on customer balance."""
    txn_col  = get_transactions_col()
    cust_col = get_customers_col()

    txn = txn_col.find_one({"_id": ObjectId(txn_id), "merchant_id": merchant_id})
    if not txn:
        return {"success": False, "message": "Transaction not found."}

    amount      = txn["amount"]
    txn_type    = txn["type"]
    customer_id = txn["customer_id"]

    # Reverse the balance effect
    balance_delta = -amount if txn_type == "credit" else amount
    credit_delta  = -amount if txn_type == "credit" else 0
    paid_delta    = -amount if txn_type == "payment" else 0

    txn_col.delete_one({"_id": ObjectId(txn_id)})
    cust_col.update_one(
        {"_id": ObjectId(customer_id)},
        {"$inc": {"balance": balance_delta, "total_credit": credit_delta, "total_paid": paid_delta}}
    )
    compute_credit_score(customer_id)
    return {"success": True}


def get_transactions(merchant_id: str, customer_id: str = None) -> list:
    txn_col = get_transactions_col()
    query = {"merchant_id": merchant_id}
    if customer_id:
        query["customer_id"] = customer_id
    txns = list(txn_col.find(query).sort("date", -1))
    for t in txns:
        t["_id"] = str(t["_id"])
    return txns


def get_monthly_summary(merchant_id: str) -> list:
    txn_col = get_transactions_col()
    pipeline = [
        {"$match": {"merchant_id": merchant_id}},
        {"$group": {
            "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}, "type": "$type"},
            "total": {"$sum": "$amount"},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
    ]
    return list(txn_col.aggregate(pipeline))
