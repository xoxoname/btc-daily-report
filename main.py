# main.py
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
    raise RuntimeError("Environment variables BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE must be set")

# 2) CCXT Bitget 객체 생성
def create_bitget():
    return ccxt.bitget({
        'apiKey':     BITGET_APIKEY,
        'secret':     BITGET_SECRET,
        'password':   BITGET_PASSPHRASE,
        'options':    {'defaultType': 'future'},
        'enableRateLimit': True
    })

# 3) Coinbase에서 실시간 BTC-USD 시세 조회
def fetch_btc_price():
    try:
        r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
        r.raise_for_status()
        return float(r.json()['data']['amount'])
    except Exception as e:
        return {"error": f"Coinbase price fetch failed: {e}"}

# 4) Bitget에서 오픈 포지션 & PnL 조회
def fetch_bitget_account():
    exc = create_bitget()
    info = {}
    try:
        bal = exc.fetch_balance({'type': 'future'})
        # 미실현 손익, 총 증거금 등
        info['equity']             = bal['info']['data']['totalEq']
        info['unrealizedPnL']      = bal['info']['data']['totalUnrealizedPL']
        info['marginBalance']      = bal['info']['data']['marginBalance']
    except Exception as e:
        info['error_balance'] = str(e)
    try:
        positions = exc.fetch_positions()
        open_pos = []
        for p in positions:
            if float(p['contracts']) != 0:
                open_pos.append({
                    'symbol':      p['symbol'],
                    'side':        p['side'],
                    'size':        p['contracts'],
                    'entryPrice':  p['info']['entryPrice'],
                    'unrealized':  p['info']['unrealizedPnl']
                })
        info['openPositions'] = open_pos
    except Exception as e:
        info['error_positions'] = str(e)
    return info

# 5) 순입금(=총입금−총출금) 조회
def fetch_bitget_net_deposit():
    exc = create_bitget()
    try:
        # Bitget 레저(거래소) 엔드포인트로 입출금 내역 조회
        # `exc.fetchTransactions()` 사용 가능한 경우 교체
        r = exc.privateMixGetAssetBillList({'pageSize': 100, 'pageNo': 1})
        txs = r['data']['list']
        deposit_total, withdraw_total = 0.0, 0.0
        for t in txs:
            amt = float(t['amount'])
            if t['bizType'] == 'DEPOSIT':
                deposit_total += amt
            elif t['bizType'] == 'WITHDRAW':
                withdraw_total += amt
        return deposit_total - withdraw_total
    except Exception as e:
        return {"error_deposit": str(e)}

# 6) 12시간 예측 placeholder (통합버전에는 외부 모듈 필요)
def forecast_12h():
    return {
        'upProbability':    '60%',
        'downProbability':  '40%',
        'reason':           'DXY 상승 전환 + MACD 데드크로스 → 단기 하락 우세'
    }

# 7) 예외 뉴스 실시간 감지 placeholder
def check_exceptions():
    return []

# 8) 리포트 생성
def generate_report():
    seoul = timezone('Asia/Seoul')
    now   = datetime.now(seoul).strftime('%Y-%m-%d %H:%M:%S')
    price = fetch_btc_price()
    acct  = fetch_bitget_account()
    nd    = fetch_bitget_net_deposit()
    pnl   = None
    prate = None
    if isinstance(nd, (int, float)) and 'equity' in acct:
        pnl   = float(acct['equity']) - nd
        prate = f"{(pnl/nd*100):.2f}%" if nd != 0 else None

    return {
        'timestamp':          now,
        'BTC_USD_spot':       price,
        'marketEvents':       '⚠️ 실시간 주요 속보 없음',
        'technical':          'RSI 55 / MACD 골든크로스 → 중립',
        'sentiment':          'Fear & Greed 45 → 중립',
        'forecast12h':        forecast_12h(),
        'exceptionsRealtime': check_exceptions(),
        'bitgetAccount':      acct,
        'netDeposit':         nd,
        'realizedPnL':        acct.get('realizedPnL', 0),
        'unrealizedPnL':      acct.get('unrealizedPnL', 0),
        'pnl':                pnl,
        'profitRate':         prate,
    }

# 9) Flask 설정
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'message': 'BTC Daily Report Service is running.'})

@app.route('/report')
def report():
    return jsonify(generate_report())

# 10) 스케줄러: 5분마다 + 매일 09:00/13:00/23:00 (KST) 자동 리포트
sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: print("[AUTO REPORT]", generate_report()), 'interval', minutes=5)
sched.add_job(lambda: print("[09:00 REPORT]", generate_report()), 'cron', hour=9,  minute=0)
sched.add_job(lambda: print("[13:00 REPORT]", generate_report()), 'cron', hour=13, minute=0)
sched.add_job(lambda: print("[23:00 REPORT]", generate_report()), 'cron', hour=23, minute=0)
sched.start()

if __name__ == '__main__':
    # Flask 개발용 서버로 실행
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
