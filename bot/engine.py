import math
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional, Literal

# Type alias for trade direction
Side = Literal["long", "short"]

@dataclass
class BotConfig:
    """
    Configuration class for bot parameters.
    These can be customized per user or globally.
    """
    ema_fast: int = 50  # Fast EMA period
    ema_slow: int = 200  # Slow EMA period
    use_rsi: bool = True  # Enable RSI-based filtering
    rsi_buy: int = 55  # RSI threshold for bullish signal
    rsi_sell: int = 45  # RSI threshold for bearish signal
    fib_window: int = 150  # Lookback window for Fibonacci retracement
    fib_levels: tuple = (0.382, 0.5, 0.618)  # Fibonacci retracement levels
    atr_period: int = 14  # ATR period for volatility calculation
    atr_mult_trail: float = 2.5  # Multiplier for trailing stop-loss
    rr: float = 1.8  # Risk-reward ratio (take profit multiple)


def ema(series: pd.Series, n: int) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    """
    return series.ewm(span=n, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    """
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / (loss.replace(0, np.nan))
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    """
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def last_swing(df: pd.DataFrame, lookback: int) -> tuple:
    """
    Identify the last swing high and swing low in the given lookback period.
    """
    window = df.tail(lookback)
    swing_high = window["high"].max()
    swing_low = window["low"].min()
    return swing_high, swing_low


def near_fib(price: float, swing_high: float, swing_low: float, levels: tuple, tol_bps: float = 20) -> bool:
    """
    Check if the current price is near a Fibonacci retracement level.
    tol_bps = tolerance in basis points (e.g., 20 = 0.20%).
    """
    if swing_high == swing_low:
        return False
    for lvl in levels:
        retrace = swing_high - (swing_high - swing_low) * lvl
        if abs(price - retrace) / price <= (tol_bps / 10000):
            return True
    return False


def is_bullish_engulfing(df: pd.DataFrame) -> bool:
    """
    Detect bullish engulfing candlestick pattern.
    """
    if len(df) < 2:
        return False
    p, c = df.iloc[-2], df.iloc[-1]
    return (p.close < p.open) and (c.close > c.open) and (c.close >= p.open) and (c.open <= p.close)


def is_bearish_engulfing(df: pd.DataFrame) -> bool:
    """
    Detect bearish engulfing candlestick pattern.
    """
    if len(df) < 2:
        return False
    p, c = df.iloc[-2], df.iloc[-1]
    return (p.close > p.open) and (c.close < c.open) and (c.close <= p.open) and (c.open >= p.close)


def compute_signal(df: pd.DataFrame, cfg: BotConfig) -> Optional[Side]:
    """
    Compute trading signals based on technical indicators and patterns.
    """
    df = df.copy()

    # Add indicators
    df["ema_fast"] = ema(df["close"], cfg.ema_fast)
    df["ema_slow"] = ema(df["close"], cfg.ema_slow)
    df["atr"] = atr(df, cfg.atr_period)
    df["rsi"] = rsi(df["close"], 14)

    last = df.iloc[-1]

    # Trend detection
    trend_long = last["ema_fast"] > last["ema_slow"]
    trend_short = last["ema_fast"] < last["ema_slow"]

    # Fibonacci retracement
    swing_high, swing_low = last_swing(df, cfg.fib_window)
    fib_confluence = near_fib(last["close"], swing_high, swing_low, cfg.fib_levels)

    # Signal conditions
    if trend_long and fib_confluence and is_bullish_engulfing(df):
        return "long"
    elif trend_short and fib_confluence and is_bearish_engulfing(df):
        return "short"
    return None


def fetch_market_data(symbol: str, timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
    """
    Fetch market data for a given symbol.
    Replace this with actual API calls to your exchange/broker.
    """
    # Simulated data for demonstration purposes
    timestamps = [pd.Timestamp.now() - pd.Timedelta(minutes=i) for i in range(limit)]
    opens = np.random.uniform(100, 110, limit)
    highs = np.random.uniform(110, 120, limit)
    lows = np.random.uniform(90, 100, limit)
    closes = np.random.uniform(100, 110, limit)
    volumes = np.random.uniform(1000, 2000, limit)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })


def place_order(user_id: str, side: Side, entry_price: float, sl: float, tp: float):
    """
    Place an order via your broker/exchange API.
    Replace this with actual broker integration.
    """
    print(f"Placing {side} order for user {user_id}: Entry={entry_price}, SL={sl}, TP={tp}")


def run_bot(supabase_client, exchange_client):
    """
    Main bot runner: Fetches active users, computes signals, and places orders.
    """
    try:
        # Fetch active users from Supabase
        result = supabase_client.table("user_settings").select("*").eq("bot_status", "active").execute()
        users = result.data or []

        for user in users:
            try:
                # Load user-specific configuration
                cfg = BotConfig(**user.get("strategy_params", {}))

                # Fetch candles from exchange
                symbol = user.get("symbol", "BTCUSD")  # Default to BTCUSD if not specified
                candles = exchange_client.get_candles(symbol, timeframe="1h", limit=cfg.fib_window + 10)
                df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])

                # Compute trading signal
                signal = compute_signal(df, cfg)
                if signal:
                    last = df.iloc[-1]
                    atr_value = df["atr"].iloc[-1]

                    # Calculate stop-loss and take-profit
                    if signal == "long":
                        sl = last["close"] - cfg.atr_mult_trail * atr_value
                        tp = last["close"] + cfg.rr * (last["close"] - sl)
                    else:  # short
                        sl = last["close"] + cfg.atr_mult_trail * atr_value
                        tp = last["close"] - cfg.rr * (sl - last["close"])

                    # Place order
                    place_order(user["login_id"], signal, last["close"], sl, tp)

            except Exception as e:
                print(f"Error processing user {user['login_id']}: {str(e)}")

    except Exception as e:
        print(f"Critical error in bot execution: {str(e)}")
