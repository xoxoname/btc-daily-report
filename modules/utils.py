import os, time, hmac, hashlib, requests
from datetime import datetime, timedelta
from pytz import timezone
from modules.bitget_api import fetch_bitget_positions, fetch_bitget_wallet_balance

def get_kst_now():
    return datetime.utcnow().replace(tzinfo=timezone("UTC")).astimezone(timezone("Asia/Seoul"))

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

def format_currency(value):
    return f"{value:,.2f} USDT"

def get_profit_report_text():
    try:
        positions = fetch_bitget_positions()
        wallet = fetch_bitget_wallet_balance()
        position_text = ""
        total_unrealized = 0

        for p in positions:
            symbol = p['symbol']
            entry = float(p['entryPrice'])
            mark = float(p['markPrice'])
            size = float(p['total'])
            pnl = float(p['unrealizedPL'])
            ratio = float(p['unrealizedRatio']) * 100
            total_unrealized += pnl

            position_text += (
                f"📌 <b>{symbol}</b>\n"
                f"진입가: {entry:.2f}, 현재가: {mark:.2f}\n"
                f"수량: {size}, 미실현손익: {pnl:.2f} USDT ({ratio:.2f}%)\n\n"
            )

        balance = float(wallet['totalEq'])
        available = float(wallet['available'])

        return (
            f"💼 <b>BTC 실시간 수익 리포트</b>\n\n"
            f"{position_text}"
            f"총 미실현 손익: {total_unrealized:.2f} USDT\n"
            f"총 자산: {balance:.2f} USDT (가용: {available:.2f})\n"
        )
    except Exception as e:
        return f"❌ 수익 리포트 생성 오류: {str(e)}"

def get_prediction_report_text():
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."

def get_schedule_report_text():
    now = get_kst_now()
    return f"🕒 현재 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}\n정규 리포트는 오전 9시, 오후 1시, 오후 11시에 전송됩니다."
