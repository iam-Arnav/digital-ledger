import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(uri)
    db_name = os.getenv("DB_NAME", "ledger_db")
    return _client[db_name]

def get_users_col():
    return get_db()["users"]

def get_customers_col():
    return get_db()["customers"]

def get_transactions_col():
    return get_db()["transactions"]

def create_indexes():
    """Create indexes for performance."""
    get_users_col().create_index("username", unique=True)
    get_customers_col().create_index([("merchant_id", 1), ("phone", 1)])
    get_transactions_col().create_index([("merchant_id", 1), ("customer_id", 1)])
