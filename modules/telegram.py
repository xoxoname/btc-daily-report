import os
import requests
import time
import hmac
import hashlib
import json
from telegram.ext import Application, CommandHandler
from datetime import datetime, timedelta
import pytz

# 환경변수에서 API 키 불러오기
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_APISECRET = os.getenv("BITGET_APISECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def bitget_signature(api_secret, timestamp, method, request_path, body=""):
    pre_sign = f"{timestamp}{method}{request_path}{body}"
    sign = hmac.new(api_secret.encode(), pre_sign.encode(), hashlib.sha256).hexdigest()
    return sign

def bitget_request(method, path, params=None, data=None):
    url = f"https://api.bitget.com{path}"
    timestamp = str(int(time.time() * 1000))
    body = json.dumps(data) if data else ""
    if method == "GET" and params:
        url += '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
    sign = bitget_signature(BITGET_APISECRET, timestamp, method, path, body)
    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }
    resp = requests.request(method, url, headers=headers, params=params if method=="GET" else None, data=body if data else None)
    if resp.status_code != 200:
        raise Exception(f"Bitget API 오류: {resp.text}")
    return resp.json()

def fetch_btcusdt_position():
    # BTCUSDT 선물 포지션 정보
    path = "/api/mix/v1/position/singlePosition"
    params = {
        "symbol": "BTCUSDT_UMCBL",  # Bitget USDⓈ-M 선물 BTC 심볼
        "marginCoin": "USDT"
    }
    result = bitget_request("GET", path, params=params)
    data = result.get('data', {})
    if not data or (isinstance(data, dict) and not data.get('openDelegateSize')):
        return None
    return data

def fetch_account_assets():
    # USDT 지갑 잔고
    path = "/api/mix/v1/account/account"
    params = {
        "symbol": "BTCUSDT_UMCBL",
            "marginCoin": "USDT"
    }
    result = bitget_request("GET", path, params=params)
    data = result.get('data', {})
    return data

def krw_format(amount):
    try:
        return f"{int(amount):,}원"
    except:
        return f"{amount}원"

def get_now_kst():
    tz = pytz.timezone("Asia/Seoul")
    now = datetime.now(tz)
    return now.strftime('%Y-%m-%d %H:%M:%S')

def make_mental_comment(pnl_krw):
    if pnl_krw > 0:
        if pnl_krw > 100000:
            return f"오늘 {krw_format(pnl_krw)} 벌었습니다! 이 정도면 편의점 알바 {int(pnl_krw//14000)}시간치 수익이에요. 급하게 또 진입하기보단, 오늘 수익을 잠깐 쉬며 지키는 것도 중요합니다!"
        return f"수익 {krw_format(pnl_krw)}! 무리한 추가 매매 대신, 이 수익을 지키는 게 진짜 실력입니다. 내일 기회가 올 때까지 기다려요!"
    else:
        return f"손실 {krw_format(pnl_krw)}... 하지만 아직 게임은 끝나지 않았어요. 무리해서 복구하려다 더 잃는 경우가 많으니, 천천히 다음 기회를 노려보세요!"

async def start(update, context):
    await update.message.reply_text("✅ 봇이 정상적으로 실행 중입니다! /profit 명령어로 실시간 수익 리포트를 받아보세요.")

async def profit(update, context):
    try:
        pos = fetch_btcusdt_position()
        assets = fetch_account_assets()
        now_kst = get_now_kst()
        if pos:
            entry_price = float(pos['openPrice'])
            mark_price = float(pos['marketPrice'])
            amount = float(pos['holdVol'])
            leverage = int(pos['leverage'])
            pnl = float(pos['unrealizedPL'])
            pnl_krw = int(pnl * 1350)
            liq_price = float(pos['liquidationPrice'])
            # 실현손익/예시용
            real_pnl = float(pos.get('realizedPL', 0))
            real_pnl_krw = int(real_pnl * 1350)
            # 진입 자산
            margin = float(pos['margin'])
            # 수익률
            rate = (pnl + real_pnl) / margin * 100 if margin > 0 else 0

            msg = f"""💰 *현재 수익 현황 요약*
📅 작성 시각: {now_kst}
━━━━━━━━━━━━━━━━━━━
📌 *포지션 정보*

종목: BTCUSDT
방향: {"롱" if amount > 0 else "숏"}
진입가: ${entry_price:,.2f} / 현재가: ${mark_price:,.2f}
레버리지: {leverage}x
청산가: ${liq_price:,.2f}

━━━━━━━━━━━━━━━━━━━
💸 *손익 정보*
미실현 손익: {pnl:.2f}달러 (약 {krw_format(pnl_krw)})
실현 손익: {real_pnl:.2f}달러 (약 {krw_format(real_pnl_krw)})
진입 자산: ${margin:,.2f}
수익률: {rate:.2f}%
━━━━━━━━━━━━━━━━━━━
🧠 *멘탈 케어*
{make_mental_comment(pnl_krw + real_pnl_krw)}
━━━━━━━━━━━━━━━━━━━
"""
        else:
            # 포지션 없을 때 - 최근 자산 기준(예시)
            assets_ = assets or {}
            equity = float(assets_.get('equity', 0))
            available = float(assets_.get('available', 0))
            msg = f"""💰 *수익 리포트*
📅 작성 시각: {now_kst}
━━━━━━━━━━━━━━━━━━━
현재 보유중인 BTCUSDT 선물 포지션이 없습니다.

계정 총 자산(USDT 기준): {equity:,.2f} USDT (한화 약 {krw_format(equity * 1350)})
가용 자산: {available:,.2f} USDT (한화 약 {krw_format(available * 1350)})

오늘은 새로운 기회가 오기 전까지, 내 자산을 지키는 시간도 소중하게 생각해요!
━━━━━━━━━━━━━━━━━━━
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❗️수익 정보 조회 오류: {e}")

def run_telegram_bot():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profit", profit))
    app.run_polling()
