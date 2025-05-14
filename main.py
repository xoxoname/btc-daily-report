import os
import ccxt
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSWORD = os.getenv("BITGET_API_PASSWORD")

app = Flask(__name__)

def fetch_report():
    exchange = ccxt.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_API_SECRET,
        'password': BITGET_API_PASSWORD,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap'
        }
    })

    try:
        balance = exchange.fetch_balance({'type': 'swap'})
        equity = balance['total']['USDT']

        positions = exchange.fetch_positions()
        total_unrealized = 0
        position_list = []

        for pos in positions:
            if pos['contracts'] == 0:
                continue
            unrealized = pos.get('unrealizedPnl', 0)
            total_unrealized += unrealized
            position_list.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'entryPrice': pos['entryPrice'],
                'unrealizedPnl': unrealized,
                'contracts': pos['contracts']
            })

        report = {
            "equity": equity,
            "pnl_today_realized": 0,  # 실제 구현 시 거래내역 분석 필요
            "pnl_today_unrealized": total_unrealized,
            "pnl_cumulative": 0,     # 누적 수익은 DB 연동이 필요
            "positions": position_list
        }

        return report

    except Exception as e:
        return {"error": str(e)}

@app.route('/report')
def get_report():
    return jsonify(fetch_report())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
