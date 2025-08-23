import asyncio
import json
import websockets
from loguru import logger

DERIV_APP_ID = "your_app_id"
DERIV_TOKEN = "your_token"

async def connect_deriv():
    url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    async with websockets.connect(url) as ws:
        logger.info("Connected to Deriv WebSocket")

        # Authorize
        await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_response = await ws.recv()
        logger.info(f"Auth Response: {auth_response}")

        # Example: Subscribe to ticks for EURUSD
        await ws.send(json.dumps({"ticks": "frxEURUSD"}))

        while True:
            msg = await ws.recv()
            logger.info(f"Tick Data: {msg}")

if __name__ == "__main__":
    asyncio.run(connect_deriv())
