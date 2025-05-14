import os
import time
import requests
import ccxt
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# 1) 환경변수 로드
load_dotenv()
BITGET_APIKEY     = os.getenv('BITGET_APIKEY')
BITGET_SECRET     = os.getenv('BITGET_SECRET')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')

if not all([BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE]):
    raise RuntimeError("환경변수(BITGET_APIKEY 등) 누락됨")

# 2) Bitget 객체 생성
def create_bitget():
    return ccxt.bitget({
        'apiKey':    BITGET_APIKEY,
        'secret':    BITGET_SECRET,
        'password':  BITGET_PASSPHRASE,
        'options':   {'defaultType': 'future'},
        'enableRateLimit': True
    })

# 3) Coinbase 실시간 BTC 시세
def fetch_btc_price():
    try:
        r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
        r.raise_for_status()
        return float(r.json()['data']['amount'])
    except Exception as e:
        return {"error": f"BTC 시세 오류: {e}"}

# 4) Bitget 자산, 포지션, 수익 정보
def fetch_bitget_account():
    exc = create_bitget()
    info = {}
    try:
        bal = exc.fetch_balance({'type': 'future'})
        info['equity']        = float(bal['info']['data']['totalEq'])
        info['unrealizedPnL'] = float(bal['info']['data']['totalUnrealizedPL'])
        info['marginBalance'] = float(bal['info']['data']['marginBalance'])
        info['realizedPnL']   = float(bal['info']['data'].get('totalRealizedPNL', 0.0))
    except Exception as e:
        info['error_balance'] = str(e)

    try:
        positions = exc.fetch_positions()
        open_pos = []
        for p in positions:
            if float(p['contracts']) > 0:
                open_pos.append({
                    'symbol':     p['symbol'],
                    'side':       p['side'],
                    'size':       p['contracts'],
                    'entryPrice': float(p['entryPrice']),
                    'unrealized': float(p['info']['unrealizedPnl'])
                })
        info['openPositions'] = open_pos
    except Exception as e:
        info['error_positions'] = str(e)
    return info

# 5) 순입금 계산 (입금 - 출금)
def fetch_bitget_net_deposit():
    exc = create_bitget()
    try:
        r = exc.privateMixGetAssetBillList({'pageSize': 100, 'pageNo': 1})
        txs = r['data']['list']
        deposit_total = sum(float(t['amount']) for t in txs if t['bizType'] == 'DEPOSIT')
        withdraw_total = sum(float(t['amount']) for t in txs if t['bizType'] == 'WITHDRAW')
        return round(deposit_total - withdraw_total, 2)
    except Exception as e:
        return {"error_deposit": str(e)}

# 6) 12시간 예측 (임시)
def forecast_12h():
    return {
        'upProbability':    '57%',
        'downProbability':  '43%',
        'reason': 'RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성'
    }

# 7) 예외 감지 (placeholder)
def check_exceptions():
    return []

# 8) 통합 리포트 생성
def generate_report():
    seoul = timezone('Asia/Seoul')
    now   = datetime.now(seoul).strftime('%Y-%m-%d %H:%M:%S')
    price = fetch_btc_price()
    acct  = fetch_bitget_account()
    nd    = fetch_bitget_net_deposit()

    pnl = None
    prate = None
    if isinstance(nd, (int, float)) and 'equity' in acct:
        pnl = round(float(acct['equity']) - nd, 2)
        prate = f"{(pnl / nd * 100):.2f}%" if nd != 0 else None

    return {
        'timestamp':         now,
        'BTC_USD_spot':      price,
        'marketEvents':      '📉 ETF / CPI 관련 뉴스 없음',
        'technical':         'RSI 54 / MACD 데드크로스 → ⚪️ 중립',
        'sentiment':         'Fear & Greed 45 → ⚪️ 중립',
        'forecast12h':       forecast_12h(),
        'exceptionsRealtime': check_exceptions(),
        'bitgetAccount':     acct,
        'netDeposit':        nd,
        'realizedPnL':       acct.get('realizedPnL', 0),
        'unrealizedPnL':     acct.get('unrealizedPnL', 0),
        'pnl':               pnl,
        'profitRate':        prate,
    }

# 9) Flask 앱
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'message': 'BTC Daily Report Service is running.'})

@app.route('/report')
def report():
    return jsonify(generate_report())

# 10) APScheduler: 5분 + 09시 / 13시 / 23시 정규 리포트
sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: print("[AUTO REPORT]", generate_report()), 'interval', minutes=5)
sched.add_job(lambda: print("[09:00 REPORT]", generate_report()), 'cron', hour=9, minute=0)
sched.add_job(lambda: print("[13:00 REPORT]", generate_report()), 'cron', hour=13, minute=0)
sched.add_job(lambda: print("[23:00 REPORT]", generate_report()), 'cron', hour=23, minute=0)
sched.start()

# 11) 실행
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
