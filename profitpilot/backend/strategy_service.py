"""
strategy_service.py

Contains example strategy implementations and utilities for evaluating signals.
This is intentionally simple and synchronous-friendly. In production you'd replace
with backtests, statistical models, risk management, position sizing, etc.

Exports:
- StrategyManager class with:
    - register_strategy(name, callable)
    - evaluate(strategy_name, market_state) -> signal dict
- A sample momentum strategy and mean_reversion strategy
"""

from typing import Callable, Dict, Any, Optional
import math
import statistics


class StrategyError(Exception):
    pass


class StrategyManager:
    def __init__(self):
        self._strategies: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_strategy(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        if not callable(func):
            raise StrategyError("Strategy must be callable")
        self._strategies[name] = func

    def evaluate(self, name: str, market_state: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._strategies:
            raise StrategyError(f"Strategy '{name}' not found")
        return self._strategies[name](market_state)

    def list_strategies(self):
        return list(self._strategies.keys())


# -------------------------
# Example simple strategies
# -------------------------

def simple_momentum_strategy(market_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expects market_state to contain:
    - 'prices': list of recent close prices (oldest..newest)
    - 'symbol': symbol string
    - optional 'threshold' numeric
    Returns a signal dict like: {'action': 'buy'/'sell'/'hold', 'size_pct': 0.01, 'confidence': 0.7}
    """
    prices = market_state.get("prices", [])
    symbol = market_state.get("symbol", "UNKNOWN")
    if len(prices) < 2:
        return {"action": "hold", "confidence": 0.0, "reason": "not enough data", "symbol": symbol}

    lookback = min(5, len(prices))
    recent = prices[-lookback:]
    # compute simple momentum: pct change over lookback
    start = recent[0]
    end = recent[-1]
    if start == 0:
        return {"action": "hold", "confidence": 0.0, "reason": "invalid price data", "symbol": symbol}

    pct_change = (end - start) / start
    threshold = market_state.get("threshold", 0.01)

    if pct_change > threshold:
        action = "buy"
    elif pct_change < -threshold:
        action = "sell"
    else:
        action = "hold"

    # crude confidence: scaled from abs(pct_change)
    confidence = min(1.0, abs(pct_change) / (threshold * 3 + 1e-9))
    size_pct = min(0.5, confidence * 0.1)  # cap position size at 50% (example)

    return {
        "symbol": symbol,
        "action": action,
        "confidence": float(confidence),
        "size_pct": float(size_pct),
        "metric": {"pct_change": pct_change, "lookback": lookback}
    }


def simple_mean_reversion_strategy(market_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expects 'prices' list. If latest price deviates from moving average by some sigma, trade against it.
    """
    prices = market_state.get("prices", [])
    symbol = market_state.get("symbol", "UNKNOWN")
    window = market_state.get("window", 20)
    if len(prices) < 5:
        return {"action": "hold", "confidence": 0.0, "reason": "not enough data", "symbol": symbol}

    window = min(window, len(prices))
    window_prices = prices[-window:]
    mean = statistics.mean(window_prices)
    stdev = statistics.pstdev(window_prices) if len(window_prices) > 1 else 0.0
    latest = prices[-1]

    if stdev == 0:
        return {"action": "hold", "confidence": 0.0, "reason": "zero volatility", "symbol": symbol}

    z_score = (latest - mean) / stdev
    threshold = market_state.get("z_threshold", 1.5)

    if z_score > threshold:
        # price well above mean -> short (sell)
        action = "sell"
    elif z_score < -threshold:
        # price well below mean -> buy
        action = "buy"
    else:
        action = "hold"

    confidence = min(1.0, abs(z_score) / (threshold * 2))
    size_pct = min(0.3, confidence * 0.1)

    return {
        "symbol": symbol,
        "action": action,
        "confidence": float(confidence),
        "size_pct": float(size_pct),
        "metric": {"z_score": z_score, "mean": mean, "stdev": stdev}
    }


# -------------------------
# Instantiate and register
# -------------------------
default_strategy_manager = StrategyManager()
default_strategy_manager.register_strategy("momentum_v1", simple_momentum_strategy)
default_strategy_manager.register_strategy("mean_reversion_v1", simple_mean_reversion_strategy)

