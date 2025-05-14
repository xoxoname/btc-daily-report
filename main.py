import os
import ccxt
import json
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def fetch_data():
    bitget = ccxt.bitget({
        'apiKey': os.getenv("BITGET_API_KEY"),
        'secret': os.getenv("BITGET_API_SECRET"),
        'password': os.getenv("BITGET_API_PASSWORD"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })

    result = {
        "equity": None,
        "realized_pnl": None,
        "unrealized_pnl": None,
        "positions": []
    }

    try:
        # 자산 정보
        balance = bitget.fetch_balance({'type': 'swap'})
        result["equity"] = float(balance.get('total', {}).get('USDT', 0.0))

        # 포지션 정보
        positions = bitget.fetch_positions()
        total_unrealized = 0.0

        for pos in positions:
            if pos['contracts'] > 0:
                entry_price = float(pos['entryPrice'])
                current_price = float(pos['markPrice'])
                qty = float(pos['contracts'])
                side = pos['side']
                pnl = float(pos['unrealizedPnl'])
                total_unrealized += pnl
                result['positions'].append({
                    "symbol": pos['symbol'],
                    "side": side,
                    "entry_price": entry_price,
                    "mark_price": current_price,
                    "contracts": qty,
                    "unrealized_pnl": pnl
                })

        result["unrealized_pnl"] = total_unrealized

        # 실현 손익 추정 (Bitget은 API 제공 미흡)
        result["realized_pnl"] = 0.0  # 정확한 실현 수익은 별도 처리 필요

    except Exception as e:
        result["error"] = str(e)

    return result

@app.route("/")
def home():
    return "BTC Daily Report is Live!"

@app.route("/report")
def report():
    data = fetch_data()
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
