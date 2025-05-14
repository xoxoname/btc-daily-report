import os
import requests
import ccxt
import openai
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 환경 변수 로드
BITGET_APIKEY     = os.environ.get('BITGET_APIKEY')
BITGET_SECRET     = os.environ.get('BITGET_SECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')
TELEGRAM_TOKEN    = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY    = os.environ.get('OPENAI_API_KEY')
TELEGRAM_USER     = '@zzzzzzzz5555'
openai.api_key    = OPENAI_API_KEY

if not all([BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE, TELEGRAM_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("모든 환경변수(BITGET, TELEGRAM, OPENAI)가 설정되어 있어야 합니다.")

app = Flask(__name__)

# 환율 가져오기 (기본: 1340원/USD)
def usd_to_krw(usd, rate=1340):
    return f"{round(usd * rate / 1000, 1)}만원"

# Bitget 객체
def create_bitget():
    return ccxt.bitget({
        'apiKey': BITGET_APIKEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'options': {'defaultType': 'future'},
        'enableRateLimit': True
    })

# BTC 시세
def fetch_btc_price():
    try:
        r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
        r.raise_for_status()
        return float(r.json()['data']['amount'])
    except:
        return 0

# 잔고 및 포지션
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
        open_pos = [
            {
                'symbol': p['symbol'], 'side': p['side'],
                'size': p['contracts'], 'entryPrice': float(p.get('entryPrice', 0)),
                'unrealized': float(p.get('unrealizedPnl', 0))
            } for p in positions if float(p.get('contracts', 0)) > 0
        ]
        info['openPositions'] = open_pos
    except Exception as e:
        info['error_positions'] = str(e)
    return info

# 순입금
def fetch_bitget_net_deposit():
    exc = create_bitget()
    try:
        deposits = exc.fetch_deposits()
        withdrawals = exc.fetch_withdrawals()
        dep_amt = sum(float(d['amount']) for d in deposits if d['currency'] == 'USDT')
        wit_amt = sum(float(w['amount']) for w in withdrawals if w['currency'] == 'USDT')
        return round(dep_amt - wit_amt, 2)
    except Exception as e:
        return 0

# GPT 예측
def gpt_forecast():
    prompt = "비트코인 기술적/심리/온체인 분석, 뉴스요약, 향후 12시간 예측, 예외상황, 이전 예측 검증을 Research Preview 수준으로 작성해줘."
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "비트코인 매매 전략 전문가로서 분석해줘."},
                {"role": "user", "content": prompt}
            ]
        )
        return res.choices[0].message['content']
    except Exception as e:
        return f"[GPT 오류] {e}"

# 텔레그램 전송
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_USER, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=3)
    except: pass

# 리포트 생성
def generate_report(send_tg=False, full=False):
    now = datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    price = fetch_btc_price()
    acct = fetch_bitget_account()
    deposit = fetch_bitget_net_deposit()
    pnl = round(acct['equity'] - deposit, 2)
    prate = f"{(pnl / deposit * 100):.2f}%" if deposit else "-"

    krw_pnl = usd_to_krw(pnl)
    krw_deposit = usd_to_krw(deposit)
    krw_equity = usd_to_krw(acct['equity'])

    msg = (
        f"📊 <b>BTC 리포트 - {now}</b>\n"
        f"• BTC: ${price}\n"
        f"• 순입금: {deposit} USDT ({krw_deposit})\n"
        f"• 자산: {acct['equity']} USDT ({krw_equity})\n"
        f"• 총 수익: {pnl} USDT ({krw_pnl}, {prate})\n"
        f"• 포지션 수: {len(acct.get('openPositions', []))}\n"
    )

    if full:
        forecast = gpt_forecast()
        msg += f"\n📈 <b>GPT 매동 예측 예상</b>\n{forecast}\n\n🧾 오늘 수익은 편의점 알바 {int(pnl//10)}시간 분이에요. 무리하지 마세요."

    if send_tg:
        send_telegram(msg)
    return msg

# 텔레그램 봇
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BTC 리포트 봇입니다. /수익 또는 /예측 을 입력해보세요.")

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_report()
    await update.message.reply_text(msg)

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_report(full=True)
    await update.message.reply_text(msg)

# Flask 라우터
@app.route('/')
def home(): return jsonify({"msg": "OK"})

@app.route('/report')
def report(): return jsonify({"msg": generate_report()})

# 스케줄
sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: generate_report(send_tg=True, full=True), 'cron', hour=9)
sched.add_job(lambda: generate_report(send_tg=True, full=True), 'cron', hour=13)
sched.add_job(lambda: generate_report(send_tg=True, full=True), 'cron', hour=23)
sched.start()

if __name__ == '__main__':
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("수익", handle_profit))
    tg_app.add_handler(CommandHandler("예측", handle_forecast))
    tg_app.run_polling()
    app.run(host='0.0.0.0', port=10000)
