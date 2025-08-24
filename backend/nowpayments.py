import os, hmac, hashlib, json, httpx
from typing import Optional

NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NP_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")
SITE_BASE = os.getenv("SITE_BASE", "http://localhost:8000")

API = "https://api.nowpayments.io/v1"

async def create_invoice(email: str, price_amount: float = 100.0, price_currency: str = "usd") -> Optional[str]:
    if not NP_API_KEY:
        return None
    payload = {
        "price_amount": price_amount,
        "price_currency": price_currency,
        "order_id": f"ppai-{email}",
        "order_description": "ProfitPilotAI Monthly Subscription",
        "success_url": f"{SITE_BASE}/dashboard",
        "cancel_url": f"{SITE_BASE}/dashboard",
        "ipn_callback_url": f"{SITE_BASE}/crypto/ipn",
        "is_fixed_rate": True,
    }
    headers = {"x-api-key": NP_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{API}/invoice", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data.get("invoice_url")

def verify_ipn_signature(raw_body: bytes, signature: str) -> bool:
    # NOWPayments sends HMAC-SHA512 over raw body using your IPN secret
    if not NP_IPN_SECRET or not signature:
        return False
    mac = hmac.new(NP_IPN_SECRET.encode(), msg=raw_body, digestmod=hashlib.sha512)
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, signature)
