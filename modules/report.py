# modules/report.py
from .data_fetch import fetch_spot_klines, fetch_ticker
from .utils import compute_rsi, compute_macd, moving_averages, bollinger_bands
from .utils import compute_rsi, compute_macd, moving_averages, bollinger_bands
from .constants import CHAT_ID, TELEGRAM_BOT_TOKEN
import requests

def build_report(symbol="BTCUSDT"):
    # 1. 현재 ticker
    tk = fetch_ticker(symbol)
    price = float(tk["last"])
    change_24h = float(tk["percentage"])  # % change

    # 2. 차트 데이터
    df = fetch_spot_klines(symbol, granularity=3600, limit=500)["close"]

    # 3. 지표 계산
    rsi = compute_rsi(df)
    macd, signal = compute_macd(df)
    ma = moving_averages(df)
    bb = bollinger_bands(df)

    # 4. 텍스트 조합
    txt = [
        f"💰 Symbol: {symbol}",
        f"• 현재가: {price:.2f} USD (24h {change_24h:+.2f}%)",
        "",
        "📈 기술 지표",
        f"• RSI(14): {rsi}",
        f"• MACD: {macd:.4f}, Signal: {signal:.4f}",
        f"• MA20/50/200: {ma[20]}/{ma[50]}/{ma[200]}",
        f"• Bollinger BB(20): Upper {bb['upper']}, Middle {bb['middle']}, Lower {bb['lower']}",
        "",
        "🔍 전략 제안",
        "- RSI 30~70 사이면 중립, MACD 크로스 확인, BB 상단 근접 시 과열 주의",
    ]
    return "\n".join(txt)

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()

def build_and_send_report():
    rpt = build_report()
    send_telegram(rpt)
    return rpt
