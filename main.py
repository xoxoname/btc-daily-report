import ccxt
import requests
import time
import os
from dotenv import load_dotenv
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)
report_data = {}

def get_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USDT/spot")
        return float(res.json()['data']['amount'])
    except Exception as e:
        return None

def fetch_report():
    global report_data

    api_key = os.getenv("BITGET_API_KEY")
    api_secret = os.getenv("BITGET_API_SECRET")
    api_passphrase = os.getenv("BITGET_API_PASSPHRASE")

    exchange = ccxt.bitget({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_passphrase,
        'enableRateLimit': True,
    })

    try:
        # 현재 시세
        price = get_coinbase_price()

        # 잔고 (총 자산)
        bal = exchange.fetch_balance({'type': 'swap'})
        total_equity = float(bal['total']['USDT']) if 'USDT' in bal['total'] else 0

        # 오늘 날짜 시작 시각 (UTC 00:00)
        now = int(time.time() * 1000)
        start_time = now - (now % 86400000)

        # 수익 내역
        realized_pnl = 0
        try:
            bills = exchange.private_mix_get_account_account_bill({
                "symbol": "BTCUSDT_UMCBL",
                "marginCoin": "USDT",
                "startTime": start_time,
                "endTime": now,
                "pageSize": 100
            })
            for entry in bills.get("data", []):
                if entry["billType"] == "RealizedPNL":
                    realized_pnl += float(entry["amount"])
        except Exception:
            realized_pnl = 0

        # 포지션
        unrealized_pnl = 0
        pos_summary = ""
        try:
            positions = exchange.fetch_positions(["BTC/USDT:USDT"], {
                "productType": "UMCBL",
                "marginCoin": "USDT"
            })

            for pos in positions:
                amt = float(pos['contracts'])
                entry_price = float(pos['entryPrice'])
                side = pos['side'].lower()
                unreal = float(pos['unrealizedPnl'])
                unrealized_pnl += unreal
                pos_summary += f"📊 {pos['symbol']} | {side} | 수량: {amt:.4f} | 진입가: {entry_price:.1f} | 미실현 PNL: {unreal:.2f} USDT\n"
        except Exception:
            pos_summary = "❌ 포지션 조회 실패"

        # 수익률 계산
        if total_equity > 0:
            pnl_rate = (realized_pnl + unrealized_pnl) / (total_equity - realized_pnl - unrealized_pnl) * 100
        else:
            pnl_rate = 0

        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "price": price,
            "equity": round(total_equity, 2),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_rate": round(pnl_rate, 2),
            "positions": pos_summary.strip()
        }

    except Exception as e:
        report_data = {
            "error": str(e)
        }

@app.route("/report")
def report():
    return jsonify(report_data)

# 앱 시작 시 한 번 실행
fetch_report()

# 5분마다 자동 실행
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_report, "interval", minutes=5)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
