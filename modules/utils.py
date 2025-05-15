import pandas as pd
import numpy as np

def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return float(100 - (100 / (1 + rs))).round(2)

def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal_line.iloc[-1])

def moving_averages(series: pd.Series, periods=(20,50,200)) -> dict:
    return {p: float(series.rolling(p).mean().iloc[-1].round(2)) for p in periods}

def bollinger_bands(series: pd.Series, period: int = 20, devs: int = 2) -> dict:
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = ma + devs * std
    lower = ma - devs * std
    return {
        "upper": float(upper.iloc[-1].round(2)),
        "middle": float(ma.iloc[-1].round(2)),
        "lower": float(lower.iloc[-1].round(2)),
    }
