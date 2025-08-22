"""
backend/trading_service.py

Orchestration layer that:
- evaluates strategies (via strategy_service)
- performs risk checks and sizing
- executes orders (simulation) or delegates to a real exchange client
- provides order and portfolio listing utilities

This is intentionally simple and in-memory for development/demo. Replace execution
with real exchange clients and persist to DB in production.
"""

import asyncio
import uuid
import time
from typing import Dict, Any, Optional

from .strategy_service import default_strategy_manager

# In-memory stores (demo)
_ORDER_STORE: Dict[str, Dict[str, Any]] = {}
_PORTFOLIO: Dict[str, Dict[str, Any]] = {}

# Risk/account settings (can be wired to config/env)
MAX_POSITION_PCT = float(0.5)   # max exposure per asset
ACCOUNT_SIZE = float(10000.0)   # default demo account size (USD)
MIN_ORDER_USD = float(10.0)


def calculate_order_size_usd(size_pct: float, account_size: Optional[float] = None) -> float:
    a = float(account_size or ACCOUNT_SIZE)
    pct = max(0.0, min(1.0, float(size_pct)))
    return max(MIN_ORDER_USD, a * pct)


def risk_check(symbol: str, usd_size: float) -> bool:
    if usd_size <= 0:
        return False
    if usd_size > ACCOUNT_SIZE * MAX_POSITION_PCT:
        return False
    return True


async def _simulate_exchange_fill(order: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    # simulate latency
    await asyncio.sleep(0.05)
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
    # store
    _ORDER_STORE[order_id] = receipt
    # update portfolio simply by exposure
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


async def execute_order(order: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    Accepts an order dict and executes it (simulated).
    Expected fields: symbol, action ('buy'/'sell'), usd_size, client_order_id (optional)
    """
    # Basic validations
    symbol = order.get("symbol")
    if not symbol:
        raise ValueError("Order missing symbol")
    usd_size = float(order.get("usd_size", 0.0))
    if usd_size <= 0:
        raise ValueError("Order usd_size must be > 0")
    # Risk check
    if not risk_check(symbol, usd_size):
        return {"status": "rejected", "reason": "risk_check_failed"}
    # Execute (simulate)
    receipt = await _simulate_exchange_fill(order, dry_run=dry_run)
    return receipt


async def evaluate_and_trade(strategy_name: str, market_state: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    Evaluate a strategy, create an order proposal, risk-check and execute.
    Returns {"signal": ..., "order_proposal": ..., "execute_receipt": ...}
    """
    signal = default_strategy_manager.evaluate(strategy_name, market_state)
    action = signal.get("action", "hold")
    symbol = signal.get("symbol", market_state.get("symbol"))
    size_pct = float(signal.get("size_pct", 0.0))
    confidence = float(signal.get("confidence", 0.0))

    proposal = {
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "size_pct": size_pct,
        "client_order_id": f"pp-{int(time.time())}-{uuid.uuid4().hex[:6]}",
        "approved": False
    }

    if action == "hold" or size_pct <= 0:
        proposal["reason"] = "no_trade_signal"
        return {"signal": signal, "order_proposal": proposal, "execute_receipt": None}

    usd_size = calculate_order_size_usd(size_pct)
    proposal["usd_size"] = usd_size

    if not risk_check(symbol, usd_size):
        proposal["reason"] = "risk_check_failed"
        return {"signal": signal, "order_proposal": proposal, "execute_receipt": None}

    receipt = await execute_order({
        "symbol": symbol,
        "action": action,
        "usd_size": usd_size,
        "client_order_id": proposal["client_order_id"]
    }, dry_run=dry_run)

    proposal["approved"] = receipt.get("status") in ("filled", "submitted")
    return {"signal": signal, "order_proposal": proposal, "execute_receipt": receipt}


def list_orders() -> Dict[str, Dict[str, Any]]:
    return dict(_ORDER_STORE)


def get_portfolio() -> Dict[str, Dict[str, Any]]:
    return dict(_PORTFOLIO)
