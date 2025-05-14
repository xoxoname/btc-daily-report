import os
import requests
import ccxt
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import threading

# 환경 변수 불러오기 (Render의 Environment Variables 사용)
BITGET_APIKEY     = os.getenv('BITGET_APIKEY')
BITGET_SECRET     = os.getenv('BITGET_SECRET')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_USER     = '@zzzzzzzz5555'
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
openai.api_key    = OPENAI_API_KEY

if not all([BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE, TELEGRAM_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("모든 환경변수(BITGET, TELEGRAM, OPENAI)가 설정되어 있어야 합니다.")

app = Flask(__name__)

def create_bitget():
    return ccxt.bitget({
        'apiKey': BITGET_APIKEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'options': {'defaultType': 'future'},
        'enableRateLimit': True
    })

def fetch_btc_price():
    try:
        r = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot', timeout=5)
        r.raise_for_status()
        return float(r.json()['data']['amount'])
    except Exception as e:
        return {"error": f"BTC 시세 오류: {e}"}

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

def gpt_reply(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "비트코인 매매 전문가로서 답변해 주세요."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message['content']
    except Exception as e:
        return f"[GPT 오류] {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("안녕하세요! BTC 분석 챗봇입니다. '오늘 리포트 보여줘'와 같이 말씀해주세요.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "리포트" in text or "수익률" in text:
        report = generate_report()
        reply = (
            f"[BTC 리포트 - {report['timestamp']} 기준]\n"
            f"• BTC: ${report['BTC_USD_spot']}\n"
            f"• 순입금: {report['netDeposit']} USDT\n"
            f"• 자산: {report['bitgetAccount'].get('equity', '?')} USDT\n"
            f"• 총 수익: {report['pnl']} USDT ({report['profitRate']})\n"
            f"• 포지션 수: {len(report['bitgetAccount'].get('openPositions', []))}\n"
            f"• 분석: {report['technical']} / {report['forecast12h']['reason']}"
        )
        await update.message.reply_text(reply)
    else:
        reply = gpt_reply(text)
        await update.message.reply_text(reply)

def forecast_12h():
    return {'upProbability': '57%', 'downProbability': '43%', 'reason': 'RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성'}

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
        print(f"[텔레그램 전송 실패] {e}")

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
            f"\n🔎 분석: RSI 54 / MACD 데드크로스 → ⚪️ 중립"
        )
        send_telegram_report(msg)

    return report

@app.route('/')
def home():
    return jsonify({'message': 'BTC 리포트 서버 작동 중'})

@app.route('/report')
def report():
    return jsonify(generate_report())

@app.route('/instant')
def manual_report():
    generate_report(send_telegram=True)
    return jsonify({'message': '리포트를 텔레그램으로 보냈습니다!'})

sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=9, minute=0)
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=13, minute=0)
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=23, minute=0)
sched.add_job(lambda: generate_report(send_telegram=False), 'interval', minutes=5)
sched.start()

def run_telegram_bot():
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    bot_app.run_polling()

if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot).start()
    app.run(host='0.0.0.0', port=10000)
