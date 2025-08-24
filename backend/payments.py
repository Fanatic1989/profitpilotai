import os, stripe
from typing import Optional

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # recurring $100/mo price

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

def create_checkout_session(customer_email: str, success_url: str, cancel_url: str) -> Optional[str]:
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return None
    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        customer_email=customer_email,
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,
    )
    return session.url
