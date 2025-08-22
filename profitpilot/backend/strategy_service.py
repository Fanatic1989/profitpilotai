"""
backend/strategy_service.py

Simple strategy registry and a few example strategies.
- Strategies are simple deterministic functions that accept a market_state dict and return a dict
  containing at least: {symbol, action, confidence, size_pct}
- This file exposes default_strategy_manager for other modules to use.
"""

from typing import Callable, Dict, Any
import statistics

class StrategyError(Exception):
    pass


class StrategyManager:
    def __init__(self):
        self._strategies: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_strategy(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        if not callable(func):
            raise StrategyError("Provided strategy is not callable")
        self._strategies[name] = func

    def evaluate(self, name: str, market_state: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._strategies:
            raise StrategyError(f"Strategy '{name}' not registered")
        return self._strategies[name](market_state)

    def list_strategies(self):
        return list(self._strategies.keys())


# -------------------------
# Example strategies
# -------------------------
def momentum_v1(market_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input expects:
      - market_state['prices'] = list of recent prices (oldest..newest)
      - market_state['symbol'] = symbol
      - optional market_state['threshold'] default 0.01
    Output:
      {symbol, action, confidence (0..1), size_pct (0..1), metric: {...}}
    """
    prices = market_state.get("prices", [])
    symbol = market_state.get("symbol", "UNK")
    if len(prices) < 3:
        return {"symbol": symbol, "action": "hold", "confidence": 0.0, "size_pct": 0.0, "metric": {"reason": "not enough prices"}}

    threshold = market_state.get("threshold", 0.01)
    lookback = min(5, len(prices))
    start = prices[-lookback]
    end = prices[-1]
    if start == 0:
        return {"symbol": symbol, "action": "hold", "confidence": 0.0, "size_pct": 0.0, "metric": {"reason": "zero start price"}}
    pct = (end - start) / start
    if pct > threshold:
        action = "buy"
    elif pct < -threshold:
        action = "sell"
    else:
        action = "hold"

    confidence = min(1.0, abs(pct) / (threshold * 3 + 1e-9))
    size_pct = min(0.5, confidence * 0.2)
    return {"symbol": symbol, "action": action, "confidence": float(confidence), "size_pct": float(size_pct), "metric": {"pct_change": pct, "lookback": lookback}}


def mean_reversion_v1(market_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    If latest price deviates from moving average by z threshold, take opposite trade.
    """
    prices = market_state.get("prices", [])
    symbol = market_state.get("symbol", "UNK")
    window = min(len(prices), market_state.get("window", 20))
    if window < 3:
        return {"symbol": symbol, "action": "hold", "confidence": 0.0, "size_pct": 0.0, "metric": {"reason": "insufficient data"}}

    window_prices = prices[-window:]
    mean = statistics.mean(window_prices)
    stdev = statistics.pstdev(window_prices) if len(window_prices) > 1 else 0.0
    latest = prices[-1]
    if stdev == 0:
        return {"symbol": symbol, "action": "hold", "confidence": 0.0, "size_pct": 0.0, "metric": {"reason": "zero volatility"}}

    z = (latest - mean) / stdev
    threshold = market_state.get("z_threshold", 1.5)
    if z > threshold:
        action = "sell"
    elif z < -threshold:
        action = "buy"
    else:
        action = "hold"

    confidence = min(1.0, abs(z) / (threshold * 2))
    size_pct = min(0.3, confidence * 0.15)
    return {"symbol": symbol, "action": action, "confidence": float(confidence), "size_pct": float(size_pct), "metric": {"z_score": z, "mean": mean, "stdev": stdev}}


# -------------------------
# Expose default manager
# -------------------------
default_strategy_manager = StrategyManager()
default_strategy_manager.register_strategy("momentum_v1", momentum_v1)
default_strategy_manager.register_strategy("mean_reversion_v1", mean_reversion_v1)
