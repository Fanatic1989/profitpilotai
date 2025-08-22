"""
backend/routes/webhooks.py

Simple webhook endpoint example.
"""

from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/")
async def handle_webhook(request: Request):
    payload = await request.json()
    # process webhook payload here
    print("Webhook received:", payload)
    return {"status": "ok"}
