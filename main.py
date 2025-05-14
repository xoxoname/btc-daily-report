from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
scheduler = BackgroundScheduler(timezone='Asia/Seoul')

exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_API_SECRET'),
    'password': os.getenv('BITGET_API_PASSWORD'),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap'
    }
})

latest_report = {}


def fetch_data():
    global latest_report
    try:
        positions = exchange.fetch_positions()
        balance = exchange.fetch_balance({"type": "future"})

        total_equity = float(balance['total']['USDT'])
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        unrealized_pnl = 0
        position_details = []
        for pos in positions:
            if pos['contracts'] and float(pos['contracts']) > 0:
                pnl = float(pos['unrealizedPnl'])
                unrealized_pnl += pnl
                position_details.append({
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'entryPrice': pos['entryPrice'],
                    'contracts': pos['contracts'],
                    'unrealizedPnl': pnl
                })

        # 실현 PnL 추정값 (계정 변경 없음 가정)
        realized_pnl = 0
        if 'info' in balance and 'data' in balance['info']:
            data = balance['info']['data']
            if isinstance(data, list):
                for item in data:
                    if item.get('marginCoin') == 'USDT':
                        realized_pnl = float(item.get('realizedPL', 0))

        latest_report = {
            'timestamp': timestamp,
            'equity': round(total_equity, 4),
            'realized_pnl': round(realized_pnl, 4),
            'unrealized_pnl': round(unrealized_pnl, 4),
            'positions': position_details
        }

        print(f"[리포트 생성됨] {timestamp}")

    except Exception as e:
        print(f"[오류] 데이터 조회 실패: {e}")


@app.route("/report", methods=["GET"])
def report():
    return jsonify(latest_report)


scheduler.add_job(fetch_data, 'interval', minutes=5)
scheduler.start()

if __name__ == "__main__":
    fetch_data()
    app.run(host="0.0.0.0", port=8000)
