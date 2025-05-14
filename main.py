import os
import requests
import ccxt
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import openai

# ✅ Render 환경변수 직접 사용
BITGET_APIKEY     = os.environ.get('BITGET_APIKEY')
BITGET_SECRET     = os.environ.get('BITGET_SECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')
TELEGRAM_TOKEN    = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY    = os.environ.get('OPENAI_API_KEY')
TELEGRAM_USER     = '@zzzzzzzz5555'

openai.api_key = OPENAI_API_KEY

if not all([BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE, TELEGRAM_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("⚠️ 환경변수가 누락되었습니다. (BITGET, TELEGRAM, OPENAI)")

# ✅ Flask 인스턴스
app = Flask(__name__)

# ✅ Bitget 객체 생성
def create_bitget():
    return ccxt.bitget({
        'apiKey': BITGET_APIKEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'options': {'defaultType': 'future'},
        'enableRateLimit': True
    })

# ✅ 실시간 BTC 시세
def fetch_btc_price():
    try:
        r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
        r.raise_for_status()
        return float(r.json()['data']['amount'])
    except Exception as e:
        return {"error": f"BTC 시세 오류: {e}"}

# ✅ Bitget 계정 정보
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
                    'symbol': p['symbol'],
                    'side': p['side'],
                    'size': p['contracts'],
                    'entryPrice': float(p.get('entryPrice', 0)),
                    'unrealized': float(p.get('unrealizedPnl', 0))
                })
        info['openPositions'] = open_pos
    except Exception as e:
        info['error_positions'] = str(e)
    return info

# ✅ 순입금 계산
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

# ✅ GPT 분석 응답
def gpt_reply(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "비트코인 매매 전문가로서 기술적 분석, 뉴스, 포지션 기반 전략을 제시하세요."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message['content']
    except Exception as e:
        return f"[GPT 오류] {e}"

# ✅ 텔레그램 핸들러
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 안녕하세요! 비트코인 리포트 챗봇입니다. '오늘 리포트 보여줘'처럼 말씀해 주세요.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "리포트" in text or "수익" in text:
        report = generate_report()
        reply = (
            f"📊 <b>BTC 리포트 - {report['timestamp']}</b>\n"
            f"• BTC: ${report['BTC_USD_spot']}\n"
            f"• 순입금: {report['netDeposit']} USDT\n"
            f"• 자산: {report['bitgetAccount'].get('equity', '?')} USDT\n"
            f"• 총 수익: {report['pnl']} USDT ({report['profitRate']})\n"
            f"• 포지션 수: {len(report['bitgetAccount'].get('openPositions', []))}\n"
            f"📈 분석: {report['technical']} / {report['forecast12h']['reason']}"
        )
        await update.message.reply_text(reply, parse_mode='HTML')
    else:
        reply = gpt_reply(text)
        await update.message.reply_text(reply)

# ✅ 예측
def forecast_12h():
    return {
        'upProbability': '57%',
        'downProbability': '43%',
        'reason': 'RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성'
    }

# ✅ 텔레그램 리포트 전송
def send_telegram_report(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_USER,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=3
        )
    except Exception as e:
        print(f"[텔레그램 전송 오류] {e}")

# ✅ 리포트 생성
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
        'timestamp': now,
        'BTC_USD_spot': price,
        'marketEvents': '📉 ETF / CPI 관련 뉴스 없음',
        'technical': 'RSI 54 / MACD 데드크로스 → ⚪️ 중립',
        'sentiment': 'Fear & Greed 45 → ⚪️ 중립',
        'forecast12h': forecast_12h(),
        'exceptionsRealtime': [],
        'bitgetAccount': acct,
        'netDeposit': nd,
        'realizedPnL': acct.get('realizedPnL', 0),
        'unrealizedPnL': acct.get('unrealizedPnL', 0),
        'pnl': pnl,
        'profitRate': prate
    }

    if send_telegram:
        msg = (
            f"📊 <b>BTC 리포트 {now}</b>\n"
            f"• BTC: ${price}\n"
            f"• 순입금: {nd} USDT\n"
            f"• 자산: {acct.get('equity', '?')} USDT\n"
            f"• 총 수익: {pnl} USDT ({prate})\n"
            f"• 포지션 수: {len(acct.get('openPositions', []))}\n"
            f"🔍 분석: RSI 54 / MACD 데드크로스 → ⚪️ 중립"
        )
        send_telegram_report(msg)

    return report

# ✅ Flask 라우터
@app.route('/')
def home(): return jsonify({'message': '✅ BTC 리포트 서버 작동 중'})

@app.route('/report')
def report(): return jsonify(generate_report())

@app.route('/instant')
def manual(): 
    generate_report(send_telegram=True)
    return jsonify({'message': '✅ 리포트를 텔레그램으로 전송 완료'})

# ✅ 스케줄러: 5분마다 + 09시 / 13시 / 23시 자동 텔레그램 전송
sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=9, minute=0)
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=13, minute=0)
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=23, minute=0)
sched.add_job(lambda: generate_report(send_telegram=False), 'interval', minutes=5)
sched.start()

# ✅ 실행부
if __name__ == '__main__':
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    bot_app.run_polling()

    app.run(host='0.0.0.0', port=10000)
