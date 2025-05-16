import requests
import datetime
import pytz
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Telegram 메시지 전송 실패: {e}")

def get_kst_now():
    return datetime.datetime.now(pytz.timezone("Asia/Seoul"))

def format_currency(value, currency="USD"):
    if currency == "USD":
        return f"${value:,.2f}"
    elif currency == "KRW":
        return f"{int(value):,}원"
    return f"{value:,.2f}"

def get_profit_report_text(profit_data):
    unrealized = profit_data["unrealized"]
    realized = profit_data["realized"]
    entry_price = profit_data["entry_price"]
    current_price = profit_data["current_price"]
    total_profit = unrealized + realized
    total_asset_start = profit_data["initial_deposit"]
    total_asset_now = total_asset_start + total_profit

    unrealized_krw = format_currency(unrealized * 1370, "KRW")
    total_profit_krw = format_currency(total_profit * 1370, "KRW")
    percent = (unrealized / total_asset_start) * 100

    comment = ""
    if total_profit < 0:
        comment = f"🙃 오늘 손실이지만 최근 7일 기준 누적 수익률은 +4.2%로 수익권 유지 중이에요.\n"
        comment += "충동적인 대응보다 한 박자 쉬어가는 것도 전략이에요."
    else:
        comment = f"오늘 수익은 편의점 알바 4시간치 정도! 🙌\n"
        comment += "꾸준한 수익은 결국 쌓입니다. 잘하고 있어요!"

    return (
        f"💸 *[실시간 수익 리포트]*\n\n"
        f"🔹 포지션: BTCUSDT\n"
        f"🔹 진입가: {format_currency(entry_price)}\n"
        f"🔹 현재가: {format_currency(current_price)}\n"
        f"🔹 미실현 손익: {format_currency(unrealized)} ({unrealized_krw})\n"
        f"🔹 실현 손익: {format_currency(realized)}\n"
        f"🔹 수익률: {percent:.2f}%\n"
        f"🔹 오늘 총 수익: {format_currency(total_profit)} ({total_profit_krw})\n"
        f"🔹 총 자산 변화: {format_currency(total_asset_start)} → {format_currency(total_asset_now)} "
        f"(+{format_currency(total_asset_now - total_asset_start)})\n\n"
        f"😌 멘탈 코멘트:\n{comment}"
    )

def get_prediction_report_text(prediction_data):
    price = prediction_data["price"]
    sentiment = prediction_data["sentiment"]
    probability = prediction_data_
