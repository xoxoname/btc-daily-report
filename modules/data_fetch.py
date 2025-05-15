import os
import time
import ccxt
import requests
import pandas as pd
import pandas_ta as ta
from modules.constants import BITGET_API_KEY, BITGET_API_SECRET

# Bitget REST 클라이언트 초기화
_ex = ccxt.bitget({
    'apiKey':    BITGET_API_KEY,
    'secret':    BITGET_API_SECRET,
    'enableRateLimit': True,
})

def fetch_profit():
    """Bitget 현물/선물 포지션 손익 데이터 반환"""
    balance = _ex.fetch_balance({'type': 'future'})
    usdt_eq   = balance['total'].get('USDT', 0)
    pnl_real  = balance['info'].get('realizedPnl', 0)
    pnl_unreal= balance['info'].get('unrealizedPnl', 0)
    return {
        'realized_pnl': float(pnl_real),
        'unrealized_pnl': float(pnl_unreal),
        'equity_usdt': float(usdt_eq),
    }

def fetch_ohlcv(symbol="BTC/USDT", timeframe="1h", limit=200):
    """Binance 등 CCXT 지원 거래소에서 ohlcv 가져오기"""
    ohlcv = _ex.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','vol'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df

def calc_technical_indicators(df):
    """RSI, MACD, MA, Bollinger 등 기술적 지표 추가"""
    df = df.copy()
    df['rsi']  = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df = df.join(macd)
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.bbands(df['close'])
    return df

def get_latest_price(symbol="BTC/USDT"):
    """현재가 가져오기 (REST 티커)"""
    ticker = _ex.fetch_ticker(symbol)
    return float(ticker['last'])
