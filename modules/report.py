import os
import requests
import pytz
from datetime import datetime
import ccxt
import openai
from dotenv import load_dotenv

load_dotenv()

# 환경변수
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
BITGET_API_KEY    = os.getenv("BITGET_API_KEY")
BITGET_SECRET     = os.getenv("BITGET_SECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
REPORT_URL        = os.getenv("REPORT_URL").rstrip("/")

openai.api_key = OPENAI_API_KEY

# 실현/미실현 손익
def get_profit_report():
    try:
        resp = requests.get(f"{REPORT_URL}/report")
        return resp.json().get("data", {})
    except Exception as e:
        return {"error": str(e)}

def format_profit_report_text(data: dict) -> str:
    now = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    usdt_pnl = data.get("usdt_pnl", "N/A")
    krw_pnl  = data.get("krw_pnl",  "N/A")
    return (
        f"[{now}]\n"
        f"💰 *실현+미실현 손익*\n"
        f"- {usdt_pnl} USDT\n"
        f"- 약 {krw_pnl} KRW"
    )

# 예측 보고서
def get_prediction_report():
    try:
        exchange = ccxt.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_SECRET,
            'password': BITGET_PASSPHRASE,
        })
        price = exchange.fetch_ticker("BTC/USDT").get("last", "알 수 없음")
    except:
        price = "알 수 없음"

    prompt = build_predict_prompt(price)
    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    return resp.choices[0].message.content

def build_predict_prompt(price: float) -> str:
    return (
        f"현재 BTC 가격: {price} USD\n"
        "아래 기준으로 12시간 예측 보고서를 작성하세요.\n"
        "1. 시장 이벤트\n"
        "2. 기술 분석\n"
        "3. 심리 지표\n"
        "4. 전략 및 예외\n"
        "5. 피드백 루프"
    )

def format_prediction_report_text(text: str) -> str:
    return f"🔮 *BTC 예측 보고서*\n{text}"
