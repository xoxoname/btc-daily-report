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
BITGET_APIKEY     = os.environ.get("BITGET_APIKEY")
BITGET_SECRET     = os.environ.get("BITGET_SECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY")
TELEGRAM_USER     = '@zzzzzzzz5555'
openai.api_key    = OPENAI_API_KEY

if not all([BITGET_APIKEY, BITGET_SECRET, BITGET_PASSPHRASE, TELEGRAM_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("모든 환경변수(BITGET, TELEGRAM, OPENAI)가 설정되어 있어야 합니다.")

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

def usd_to_krw(usd):
    try:
        r = requests.get('https://api.exchangerate.host/latest?base=USD&symbols=KRW')
        rate = r.json()['rates']['KRW']
        return round(float(usd) * rate)
    except:
        return None

def gpt_reply(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "비트코인 매매 전문가로서 정확하고 신중하게 분석해 주세요."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message['content']
    except Exception as e:
        return f"[GPT 오류] {e}"

def send_telegram_report(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_USER, "text": message, "parse_mode": "HTML"}, timeout=3
        )
    except Exception as e:
        print(f"[텔레그램 전송 실패] {e}")

def forecast_12h():
    return {
        'upProbability': '57%',
        'downProbability': '43%',
        'reason': 'RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성'
    }

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

    krw_pnl = usd_to_krw(pnl) if pnl else None
    krw_nd = usd_to_krw(nd) if nd else None

    report = {
        'timestamp': now,
        'BTC_USD_spot': price,
        'netDeposit': nd,
        'netDeposit_krw': krw_nd,
        'bitgetAccount': acct,
        'pnl': pnl,
        'pnl_krw': krw_pnl,
        'profitRate': prate,
        'forecast12h': forecast_12h()
    }

    if send_telegram:
        hours = int((pnl or 0) / 10)
        msg = (
            f"📊 <b>BTC 리포트 {now}</b>\n"
            f"• BTC: ${price}\n"
            f"• 순입금: {nd} USDT ({krw_nd:,}원)\n"
            f"• 자산: {acct.get('equity', '?')} USDT\n"
            f"• 총 수익: {pnl} USDT ({krw_pnl:,}원 | {prate})\n"
            f"• 포지션 수: {len(acct.get('openPositions', []))}\n"
            f"\n📈 분석: {report['forecast12h']['reason']}\n"
            f"💡 오늘 수익은 편의점 알바 {hours}시간 분입니다. 침착하게 매매를 유지해 주세요."
        )
        send_telegram_report(msg)

    return report

# Flask API
@app.route('/')
def home():
    return jsonify({'message': 'BTC 리포트 서버 작동 중'})

@app.route('/report')
def report():
    return jsonify(generate_report())

@app.route('/instant')
def manual_report():
    generate_report(send_telegram=True)
    return jsonify({'message': '리포트를 텔레그램으로 전송했습니다'})

# 텔레그램 봇 핸들러
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BTC 챗봇입니다. /profit 또는 /forecast 명령어를 입력해주세요.")

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rpt = generate_report()
    await update.message.reply_text(
        f"[현재 수익]\n순입금: {rpt['netDeposit']} USDT\n총자산: {rpt['bitgetAccount'].get('equity')} USDT\n총 수익: {rpt['pnl']} USDT ({rpt['profitRate']})"
    )

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = gpt_reply("비트코인 향후 12시간 예측 리포트 작성해줘")
    await update.message.reply_text(result)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "수익" in text:
        await handle_profit(update, context)
    elif "예측" in text:
        await handle_forecast(update, context)
    else:
        await update.message.reply_text("지원 명령: 수익 / 예측")

# 스케줄러 실행
sched = BackgroundScheduler(timezone='Asia/Seoul')
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=9, minute=0)
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=13, minute=0)
sched.add_job(lambda: generate_report(send_telegram=True), 'cron', hour=23, minute=0)
sched.add_job(lambda: generate_report(send_telegram=False), 'interval', minutes=5)
sched.start()

# 앱 실행
if __name__ == '__main__':
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", handle_start))
    tg_app.add_handler(CommandHandler("profit", handle_profit))
    tg_app.add_handler(CommandHandler("forecast", handle_forecast))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    tg_app.run_polling()
    app.run(host='0.0.0.0', port=10000)
