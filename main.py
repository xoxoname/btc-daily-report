# main.py
import os
import time
import ccxt
from flask import Flask, Response

app = Flask(__name__)

def fetch_report() -> str:
    # Bitget 연결
    exch = ccxt.bitget({
        "apiKey": os.environ["BITGET_API_KEY"],
        "secret": os.environ["BITGET_SECRET_KEY"],
        "password": os.environ["BITGET_PASSPHRASE"],
        "enableRateLimit": True,
    })
    # 잔고 조회 (마진 타입)
    bal = exch.fetch_balance({"type": "swap"})
    total_usdt = bal["total"].get("USDT", 0)
    # 미실현 PnL: 전체잔고 − 초기증거금 합계
    initial_margin = sum(item.get("initialMargin", 0) for item in bal["info"]["data"])
    unrealized_pnl = total_usdt - initial_margin

    # 오늘 실현 PnL: accountBill 엔드포인트로 조회
    now = int(time.time() * 1000)
    start_of_day = int(time.time() // 86400 * 86400 * 1000)
    params = {
        "productType": "USDT-Futures",
        "marginCoin": "USDT",
        "startTime": start_of_day,
        "endTime": now,
        "pageSize": 50
    }
    try:
        bills = exch.private_get_mix_account_accountBill(params)
        realized = sum(float(b["realizedPnl"]) for b in bills["data"]["bills"])
    except Exception:
        realized = 0.0

    text = (
        f"📊 리포트 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"💰 전체 USDT 잔고: {total_usdt:.4f}\n"
        f"📈 미실현 PnL: {unrealized_pnl:+.4f} USDT\n"
        f"🎯 실현 PnL(오늘): {realized:+.4f} USDT\n"
    )
    return text

@app.route("/report")
def report():
    return Response(fetch_report(), mimetype="text/plain; charset=utf-8")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
