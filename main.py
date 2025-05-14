import os
import time
import ccxt
import pytz
import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSWORD = os.getenv("BITGET_API_PASSWORD")

tz = pytz.timezone("Asia/Seoul")

def get_bitget_exchange():
    return ccxt.bitget({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "password": API_PASSWORD,
        "enableRateLimit": True,
        "options": {"defaultType": "swap"},
    })

def fetch_positions(exchange):
    try:
        positions = exchange.fetch_positions()
        btc_positions = [p for p in positions if "BTC/USDT" in p["symbol"] and float(p["contracts"]) > 0]
        return btc_positions
    except Exception as e:
        print(f"❌ 포지션 조회 실패: {e}")
        return []

def fetch_balance(exchange):
    try:
        return exchange.fetch_balance({"type": "swap"})
    except Exception as e:
        print(f"❌ 자산 조회 실패: {e}")
        return {}

def fetch_today_pnl(exchange):
    try:
        since = int(datetime.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        now = int(datetime.datetime.now(tz).timestamp() * 1000)
        response = exchange.fetch('https://api.bitget.com/api/mix/v1/account/accountBill', method='GET', params={
            'productType': 'USDT-Futures',
            'marginCoin': 'USDT',
            'startTime': since,
            'endTime': now,
            'pageSize': 100
        })
        pnl = 0
        for tx in response.get("data", []):
            if tx["billType"] == "realised_pnl":
                pnl += float(tx["amount"])
        return pnl
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")
        return 0

def get_equity(balance):
    return balance.get("total", {}).get("USDT", 0)

def report():
    exch = get_bitget_exchange()
    balance = fetch_balance(exch)
    equity = get_equity(balance)
    positions = fetch_positions(exch)
    realized_pnl = fetch_today_pnl(exch)

    position_lines = []
    unrealized_total = 0
    for pos in positions:
        symbol = pos["symbol"]
        side = pos["side"]
        size = pos["contracts"]
        entry = pos["entryPrice"]
        mark = pos["markPrice"]
        pnl = pos["unrealizedPnl"]
        unrealized_total += float(pnl)
        position_lines.append(
            f"📊 {symbol} | {side} | 수량: {size} | 진입가: {entry} | 미실현 PNL: {pnl:.4f} USDT"
        )

    now = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"✅ [BTC 실시간 리포트] {now}",
        "----------------------------------------",
        *position_lines if position_lines else ["🚫 오픈 포지션 없음"],
        f"🧮 총 미실현 PNL: {unrealized_total:.4f} USDT",
        f"📊 오늘 실현 PNL: {realized_pnl:.4f} USDT",
        f"💎 총 자산(Equity): {equity:.4f} USDT",
        "----------------------------------------"
    ]
    print("\n".join(lines))

if __name__ == "__main__":
    while True:
        report()
        time.sleep(300)  # 5분마다 실행
