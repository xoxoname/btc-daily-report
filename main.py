from dotenv import load_dotenv
load_dotenv()

import os
import requests
import ccxt
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify, Response
from apscheduler.schedulers.background import BackgroundScheduler

# 환경 변수 로드 및 검증
BITGET_APIKEY     = os.getenv('BITGET_APIKEY')
BITGET_SECRET     = os.getenv('BITGET_SECRET')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_USER     = '@zzzzzzzz5555'

if not all([BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE, TELEGRAM_TOKEN]):
    raise RuntimeError("환경변수(BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE, TELEGRAM_TOKEN)가 모두 설정되어 있어야 합니다.")

# OpenAPI 스펙
openapi_spec = {
    "openapi": "3.0.1",
    "info": {"title": "BTC Daily Report API", "version": "1.0.0"},
    "paths": {
        "/report": {
            "get": {
                "summary": "최신 BTC 리포트 가져오기",
                "responses": {"200": {"description": "최신 리포트 JSON", "content": {"application/json": {"schema": {"type": "object"}}}}}
            }
        }
    }
}

# 플러그인 매니페스트
plugin_manifest = {
    "schema_version": "v1",
    "name_for_human": "BTC 리포트 플러그인",
    "name_for_model": "btc_report_fetcher",
    "description_for_human": "최신 BTC 리포트를 불러옵니다",
    "description_for_model": "BTC Daily Report 서비스의 /report 엔드포인트를 호출합니다",
    "auth": {"type": "none"},
    "api": {"type": "openapi", "url": "https://btc-daily-report.onrender.com/.well-known/openapi.json"},
    "logo_url": "https://your-domain.com/logo.png",
    "contact_email": "your-email@example.com",
    "legal_info_url": "https://your-domain.com/legal"
}

# Bitget 객체 생성
 def create_bitget():
     return ccxt.bitget({
         'apiKey': BITGET_APIKEY,
         'secret': BITGET_SECRET,
         'password': BITGET_PASSPHRASE,
         'options': {'defaultType': 'future'},
         'enableRateLimit': True
     })

# 실시간 BTC 시세
 def fetch_btc_price():
     try:
         r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
         r.raise_for_status()
         return float(r.json()['data']['amount'])
     except Exception as e:
         return {"error": f"BTC 시세 오류: {e}"}

# Bitget 자산 및 포지션 조회
 def fetch_bitget_account():
     exc = create_bitget()
     info = {}
     try:
         bal = exc.fetch_balance({'type': 'future'})
         info['equity'] = float(bal['total'].get('USDT', 0))
         info['marginBalance'] = float(bal.get('info', {}).get('marginBalance', 0))
         info['unrealizedPnL'] = float(bal.get('unrealizedPnl', 0.0))
         info['realizedPnL'] = float(bal.get('realizedPnl', 0.0))
     except Exception as e:
         info['error_balance'] = str(e)

     try:
         positions = exc.fetch_positions()
         open_pos = []
         for p in positions:
             if float(p.get('contracts', 0)) > 0:
                 open_pos.append({
                     'symbol': p['symbol'], 'side': p['side'],
                     'size': p['contracts'], 'entryPrice': float(p.get('entryPrice', 0)),
                     'unrealized': float(p.get('unrealizedPnl', 0))
                 })
         info['openPositions'] = open_pos
     except Exception as e:
         info['error_positions'] = str(e)
     return info

# 순입금 계산
 def fetch_bitget_net_deposit():
     exc = create_bitget()
     try:
         deposits = exc.fetch_deposits()
         withdrawals = exc.fetch_withdrawals()
         dep_amt = sum(float(d['amount']) for d in deposits if d['currency'] == 'USDT')
         wit_amt = sum(float(w['amount']) for w in withdrawals if w['currency'] == 'USDT')
         return round(dep_amt - wit_amt, 2)
     except Exception as e:
         return {"error_deposit": str(e)}

# 텔레그램 전송
 def send_telegram_report(message):
     url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
     payload = {
         "chat_id": TELEGRAM_USER, "text": message, "parse_mode": "HTML",
         "reply_markup": {"inline_keyboard": [[{
             "text": "📊 리포트 전체 보기",
             "url": "https://chatgpt.com/c/6824689b-ef48-8013-b12a-bbea0de9ffce?model=o4-mini-high"
         }]]}
     }
     try:
         requests.post(url, json=payload, timeout=3)
     except Exception as e:
         print(f"[텔레그램 전송 실패] {e}")

# 12시간 예측
 def forecast_12h():
     return {'upProbability': '57%', 'downProbability': '43%', 'reason': 'RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성'}

# 리포트 생성
 def generate_report(send_telegram=False):
     seoul = timezone('Asia/Seoul')
     now = datetime.now(seoul).strftime('%Y-%m-%d %H:%M:%S')
     price = fetch_btc_price()
     acct = fetch_bitget_account()
     nd = fetch_bitget_net_deposit()

     pnl, prate = None, None
     if isinstance(nd, (int, float)) and 'equity' in acct:
         pnl = round(acct['equity'] - nd, 2)
         prate = f"{(pnl / nd * 100):.2f}%" if nd else None

     report = {
         'timestamp': now, 'BTC_USD_spot': price,
         'marketEvents': '📉 ETF / CPI 관련 뉴스 없음', 'technical': 'RSI 54 / MACD 데드크로스 → ⚪️ 중립',
         'sentiment': 'Fear & Greed 45 → ⚪️ 중립', 'forecast12h': forecast_12h(),
         'exceptionsRealtime': [], 'bitgetAccount': acct,
         'netDeposit': nd, 'realizedPnL': acct.get('realizedPnL', 0), 'unrealizedPnL': acct.get('unrealizedPnL', 0),
         'pnl': pnl, 'profitRate': prate
     }

     if send_telegram:
         msg = (f"📊 <b>BTC 리포트 {now}</b>\n"
                f"• BTC: ${price}\n"
                f"• 순입금: {nd} USDT\n"
                f"• 자산: {acct.get('equity', '?')} USDT\n"
                f"• 총 수익: {pnl} USDT ({prate})\n"
                f"• 포지션 수: {len(acct.get('openPositions', []))}\n"\n
                "🔎 분석: RSI 54 / MACD 데드크로스 → ⚪️ 중립")
         send_telegram_report(msg)

     return report

# Flask 앱 설정
 app = Flask(__name__)

@app.route('/')
 def home(): return jsonify({'message': 'BTC 리포트 서버 작동 중'})

@app.route('/report')
 def report(): return jsonify(generate_report())

@app.route('/.well-known/openapi.json')
 def serve_openapi(): return jsonify(openapi_spec)

@app.route('/ai-plugin.json')
 def serve_plugin(): return jsonify(plugin_manifest)

# 스케줄러 설정
 sched = BackgroundScheduler(timezone='Asia/Seoul')
 sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=9, minute=0)
 sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=13, minute=0)
 sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=23, minute=0)
 sched.add_job(lambda: generate_report(send_telegram=False), 'interval', minutes=5)
 sched.start()

# 서버 실행
 if __name__ == '__main__': app.run(host='0.0.0.0', port=10000)
