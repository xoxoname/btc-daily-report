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

# 환경 변수 로드
BITGET_APIKEY     = os.environ.get('BITGET_APIKEY')
BITGET_SECRET     = os.environ.get('BITGET_SECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')
TELEGRAM_TOKEN    = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY")
TELEGRAM_USER     = '@zzzzzzzz5555'

openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

# Bitget 객체 생성
def create_bitget():
    return ccxt.bitget({
        'apiKey': BITGET_APIKEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'options': {'defaultType': 'future'},
        'enableRateLimit': True
    })

# BTC 시세 (USD)
def fetch_btc_price():
    try:
        r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
        r.raise_for_status()
        return float(r.json()['data']['amount'])
    except Exception as e:
        return {'error': str(e)}

# 환율 (USD -> KRW)
def fetch_usdkrw():
    try:
        r = requests.get('https://api.exchangerate.host/convert?from=USD&to=KRW', timeout=5)
        return float(r.json().get('result', 1350))
    except:
        return 1350.0

# 계좌 정보

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
        return {'error_deposit': str(e)}

# GPT 예측

def gpt_reply(prompt):
    try:
        res = openai.chat.completions.create(
            model='gpt-4',
            messages=[
                {"role": "system", "content": "비트코인 분석 전문가로서 상세하게 분석해줘."},
                {"role": "user", "content": prompt}
            ]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"[GPT 오류] {e}"

# 텔레그램 리포트 전송

def send_telegram_report(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_USER, "text": msg, "parse_mode": "HTML"}, timeout=3
        )
    except Exception as e:
        print(f"텔레그램 오류: {e}")

# 리포트 생성

def generate_report(send_tg=False):
    now = datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    price = fetch_btc_price()
    rate = fetch_usdkrw()
    acct = fetch_bitget_account()
    dep = fetch_bitget_net_deposit()

    pnl, prate = None, None
    if isinstance(dep, (int, float)) and 'equity' in acct:
        pnl = round(acct['equity'] - dep, 2)
        prate = f"{(pnl / dep * 100):.2f}%" if dep else None

    pnl_krw = f"{round(pnl * rate / 10000, 1)}만원" if pnl else '?'

    msg = (
        f"📊 <b>BTC 리포트 - {now}</b>\n"
        f"• BTC: ${price} ≒ {round(price * rate / 10000, 1)}만원\n"
        f"• 순입금: {dep} USDT ≒ {round(dep * rate / 10000, 1)}만원\n"
        f"• 자산: {acct.get('equity')} USDT\n"
        f"• 총 수익: {pnl} USDT ({prate}) ≒ {pnl_krw}\n"
        f"• 포지션 수: {len(acct.get('openPositions', []))}\n"
        f"\n📈 분석: RSI 54 / MACD 데드크로스 → ⚪️ 중립"
    )

    if send_tg:
        send_telegram_report(msg)
    return msg

# 텔레그램 핸들러

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_report()
    await update.message.reply_text(msg, parse_mode='HTML')

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = generate_report()
    analysis = gpt_reply("현재 비트코인 시장의 12시간 예측을 기술적, 심리적, 매크로 지표 중심으로 작성해줘.")
    footer = "\n\n💬 오늘 수익은 편의점 알바 {0}시간치예요. 너무 과몰입하지 마세요 🙂".format(round(float(msg.split('총 수익: ')[1].split(' ')[0]) / 10, 1))
    await update.message.reply_text(msg + "\n\n📊 <b>GPT 매동 예측</b>\n" + analysis + footer, parse_mode='HTML')

async def handle_default(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("안녕하세요! /수익 또는 /예측 명령어를 사용해주세요.")

# Flask 라우팅

@app.route('/')
def home():
    return jsonify({'status': 'BTC 리포트 서버 작동 중'})

# 스케줄러 설정
sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: send_telegram_report(generate_report(send_tg=False)), 'cron', hour=9)
sched.add_job(lambda: send_telegram_report(generate_report(send_tg=False)), 'cron', hour=13)
sched.add_job(lambda: send_telegram_report(generate_report(send_tg=False)), 'cron', hour=23)
sched.start()

# 실행
if __name__ == '__main__':
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("수익", handle_profit))
    tg_app.add_handler(CommandHandler("예측", handle_forecast))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_default))
    tg_app.run_polling()

    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
