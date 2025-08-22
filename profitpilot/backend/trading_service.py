"""
trading_service.py

Provides small orchestration methods for:
- turning strategy signals into mock/executable orders
- simple risk checks and position sizing guards
- an async `execute_order` placeholder which you can replace with exchange API calls

This module intentionally does NOT talk to any real exchange. Replace execute_order with
your exchange client logic (Deriv, Binance, Bitfinex, etc.) and secure credentials via
environment variables or a secrets manager.
"""

import asyncio
import uuid
import time
from typing import Dict, Any, Optional

from .strategy_service import default_strategy_manager

# Simple in-memory order store (for demo/testing). In production store orders to DB.
_ORDER_STORE: Dict[str, Dict[str, Any]] = {}
_PORTFOLIO: Dict[str, Dict[str, Any]] = {}  # keyed by symbol: {position, avg_price, size}


# Basic risk manager settings (can be loaded from config)
MAX_POSITION_PCT = float(0.5)  # max 50% of account per position (example)
ACCOUNT_SIZE = float(10000.0)  # placeholder account size in USD (replace with real)
MIN_ORDER_USD = float(10.0)


def calculate_order_size_usd(size_pct: float) -> float:
    size_pct = max(0.0, min(1.0, float(size_pct)))
    return max(MIN_ORDER_USD, ACCOUNT_SIZE * size_pct)


async def execute_order(order: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    Simulates sending order to an exchange. Replace with real API call code.
    order example:
    {
        "symbol": "BTCUSD",
        "action": "buy",
        "usd_size": 100,
        "price": 50000,  # optional
        "client_order_id": "..."
    }
    Returns standardized order receipt.
    """
    # simulate network latency
    await asyncio.sleep(0.1)

    order_id = str(uuid.uuid4())
    now = time.time()
    receipt = {
        "order_id": order_id,
        "client_order_id": order.get("client_order_id"),
        "symbol": order.get("symbol"),
        "action": order.get("action"),
        "usd_size": order.get("usd_size"),
        "price": order.get("price"),
        "status": "filled" if dry_run else "submitted",
        "filled_at": now if dry_run else None,
        "raw": {"simulated": True},
    }

    # save to store
    _ORDER_STORE[order_id] = receipt

    # update portfolio (very naive)
    symbol = order.get("symbol")
    if receipt["status"] == "filled" and symbol:
        pos = _PORTFOLIO.get(symbol, {"position": 0.0, "usd_exposure": 0.0})
        if order.get("action") == "buy":
            pos["position"] += 1
            pos["usd_exposure"] += receipt["usd_size"]
        elif order.get("action") == "sell":
            pos["position"] -= 1
            pos["usd_exposure"] -= receipt["usd_size"]
        _PORTFOLIO[symbol] = pos

    return receipt


def risk_check(symbol: str, usd_size: float) -> bool:
    """
    Basic check: don't exceed MAX_POSITION_PCT of ACCOUNT_SIZE for a single order.
    """
    if usd_size <= 0:
        return False
    if usd_size > ACCOUNT_SIZE * MAX_POSITION_PCT:
        return False
    return True


async def evaluate_and_trade(strategy_name: str, market_state: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    High-level orchestrator:
    - evaluate strategy
    - create order proposal
    - risk checks
    - execute order (placeholder)
    Returns dict: {signal, order_proposal, execute_receipt}
    """
    signal = default_strategy_manager.evaluate(strategy_name, market_state)

    action = signal.get("action", "hold")
    symbol = signal.get("symbol", market_state.get("symbol"))
    size_pct = float(signal.get("size_pct", 0.0))
    confidence = float(signal.get("confidence", 0.0))

    order_proposal = {
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "size_pct": size_pct,
        "client_order_id": f"pp-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    }

    if action == "hold" or size_pct <= 0.0:
        order_proposal.update({"approved": False, "reason": "no trade signal"})
        return {"signal": signal, "order_proposal": order_proposal, "execute_receipt": None}

    usd_size = calculate_order_size_usd(size_pct)
    order_proposal["usd_size"] = usd_size

    # risk check
    if not risk_check(symbol, usd_size):
        order_proposal.update({"approved": False, "reason": "risk check failed"})
        return {"signal": signal, "order_proposal": order_proposal, "execute_receipt": None}

    # Execute (simulate)
    execute_receipt = await execute_order({
        "symbol": symbol,
        "action": action,
        "usd_size": usd_size,
        "client_order_id": order_proposal["client_order_id"],
    }, dry_run=dry_run)

    order_proposal.update({"approved": True})
    return {"signal": signal, "order_proposal": order_proposal, "execute_receipt": execute_receipt}


# Utilities for external visibility
def list_orders() -> Dict[str, Dict[str, Any]]:
    return dict(_ORDER_STORE)


def get_portfolio() -> Dict[str, Dict[str, Any]]:
    return dict(_PORTFOLIO)

