import hashlib
from models import USERS, TRADE_LOGS

def verify_user(login_id, password):
    user = USERS.get(login_id)
    return user and user["password"] == hashlib.sha256(password.encode()).hexdigest()

def get_user_dashboard(login_id):
    return TRADE_LOGS.get(login_id, [])
