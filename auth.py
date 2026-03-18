import bcrypt
from datetime import datetime
from bson import ObjectId
from database import get_users_col


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def register_user(username: str, password: str, business_name: str, phone: str) -> dict:
    col = get_users_col()
    if col.find_one({"username": username}):
        return {"success": False, "message": "Username already exists."}
    
    user = {
        "username": username,
        "password": hash_password(password),
        "business_name": business_name,
        "phone": phone,
        "created_at": datetime.utcnow(),
    }
    result = col.insert_one(user)
    return {"success": True, "user_id": str(result.inserted_id)}


def login_user(username: str, password: str) -> dict:
    col = get_users_col()
    user = col.find_one({"username": username})
    if not user:
        return {"success": False, "message": "User not found."}
    if not verify_password(password, user["password"]):
        return {"success": False, "message": "Incorrect password."}
    return {
        "success": True,
        "user_id": str(user["_id"]),
        "username": user["username"],
        "business_name": user["business_name"],
    }
