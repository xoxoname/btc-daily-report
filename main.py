# main.py
import os
import ccxt
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# .env 파일이 있으면 로드 (로컬 테스트용)
load_dotenv()

# 환경 변수 읽기
API_KEY    = os.getenv('BITGET_APIKEY')
API_SECRET = os.getenv('BITGET_SECRET')
API_PASS   = os.getenv('BITGET_PASSPHRASE')

missing = [v for v,name in [(API_KEY,'BITGET_APIKEY'),(API_SECRET,'BITGET_SECRET'),(API_PASS,'BITGET_PASSPHRASE')] if not v]
if missing:
    # 런타임에 빠진 env var를 바로 알립니다.
    raise RuntimeError(f"Missing environment variables: {missing}")

def create_exchange():
    return ccxt.bitget({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'password': API_PASS,
        'enableRateLimit': True,
    })

def fetch_data():
    exch = create_exchange()

    # 1) 잔고(Equity)
    bal = exch.fetch_balance({'type': 'future'})
    equity = float(bal['info'].get('equity', bal['total'].get('USDT', 0)))

    # 2) 오픈 포지션
    pos_data = exch.fetch_positions()
    open_positions = []
    for p in pos_data:
        if float(p.get('contracts', 0)) != 0:
            open_positions.append({
                'symbol':      p['symbol'],
                'side':        'LONG' if float(p['contracts'])>0 else 'SHORT',
                'entryPrice':  float(p['entryPrice']),
                'contracts':   float(p['contracts']),
                'unrealizedPnl': float(p.get('unrealizedPnl', 0)),
            })

    # 3) 순입금액 → 전체 입금(deposit) 합산
    try:
        txns = exch.fetch_deposits({'currency': 'USDT'})
        total_deposit = sum(float(t['amount']) for t in txns if t['status'] in ('ok','pending') and t['network'])
    except Exception:
        total_deposit = None  # 입금 내역 조회 실패 시

    # 4) 수익 & 수익률
    profit = equity - total_deposit if total_deposit is not None else None
    roi_pct = (profit/total_deposit*100) if (total_deposit and profit is not None) else None

    # 5) Coinbase 실시간 BTC-USD 가격
    try:
        price = float(requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot').json()['data']['amount'])
    except Exception:
        price = None

    return {
        'timestamp':      datetime.utcnow().isoformat() + 'Z',
        'btc_price_usd':  price,
        'equity_usdt':    equity,
        'net_deposit':    total_deposit,
        'profit_usdt':    profit,
        'roi_percent':    roi_pct,
        'open_positions': open_positions,
    }

# Flask 앱 & 스케줄러
app = Flask(__name__)

# 5분마다 자동으로 fetch_data() 실행 (로그로만 확인)
sched = BackgroundScheduler()
sched.add_job(lambda: print("🕔 auto-fetch:", fetch_data()), 'interval', minutes=5)
sched.start()

@app.route('/')
def home():
    return "Crypto Report Service is running!"

@app.route('/report')
def report():
    try:
        return jsonify(fetch_data())
    except Exception as e:
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    # 개발 서버 경고는 무시하셔도 되고, 배포 환경에서는 WSGI(gunicorn) 쓰시면 됩니다.
    app.run(host='0.0.0.0', port=port)

