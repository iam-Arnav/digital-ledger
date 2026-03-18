from database import get_transactions_col, get_customers_col
from transactions import get_monthly_summary
import pandas as pd
from datetime import datetime


def get_summary_stats(merchant_id: str) -> dict:
    cust_col = get_customers_col()
    txn_col  = get_transactions_col()

    customers   = list(cust_col.find({"merchant_id": merchant_id}))
    total_cust  = len(customers)
    defaulters  = sum(1 for c in customers if c.get("balance", 0) > 0)
    total_outstanding = sum(c.get("balance", 0) for c in customers if c.get("balance", 0) > 0)

    txns = list(txn_col.find({"merchant_id": merchant_id}))
    total_credit  = sum(t["amount"] for t in txns if t["type"] == "credit")
    total_payment = sum(t["amount"] for t in txns if t["type"] == "payment")

    collection_rate = (total_payment / total_credit * 100) if total_credit > 0 else 0.0

    return {
        "total_customers":   total_cust,
        "defaulters":        defaulters,
        "total_outstanding": total_outstanding,
        "total_credit":      total_credit,
        "total_payment":     total_payment,
        "collection_rate":   round(collection_rate, 1),
    }


def get_monthly_trend_df(merchant_id: str) -> pd.DataFrame:
    raw = get_monthly_summary(merchant_id)
    if not raw:
        return pd.DataFrame(columns=["month", "credit", "payment"])

    rows = {}
    for r in raw:
        key = f"{r['_id']['year']}-{r['_id']['month']:02d}"
        if key not in rows:
            rows[key] = {"month": key, "credit": 0.0, "payment": 0.0}
        rows[key][r["_id"]["type"]] = r["total"]

    df = pd.DataFrame(list(rows.values())).sort_values("month")
    return df


def get_risk_distribution(merchant_id: str) -> pd.DataFrame:
    cust_col = get_customers_col()
    customers = list(cust_col.find({"merchant_id": merchant_id}))
    cats = [c.get("risk_category", "Low Risk") for c in customers]
    if not cats:
        return pd.DataFrame(columns=["category", "count"])
    df = pd.DataFrame(cats, columns=["category"])
    return df.groupby("category").size().reset_index(name="count")
