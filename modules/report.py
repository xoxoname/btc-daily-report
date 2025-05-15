from openai import OpenAI
import os
import requests

# OpenAI 클라이언트 초기화 (proxies 인자 제거됨)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def fetch_report_data():
    try:
        response = requests.get("https://btc-daily-report.onrender.com/report")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"message": str(e), "status": "error"}

def format_profit_report_text(data: dict) -> str:
    realized_pnl = data.get("realized_pnl", 0)
    unrealized_pnl = data.get("unrealized_pnl", 0)
    total_asset = data.get("total_asset", 0)
    krw_rate = data.get("krw_rate", 1350)

    realized_krw = int(realized_pnl * krw_rate)
    unrealized_krw = int(unrealized_pnl * krw_rate)
    total_krw = int(total_asset * krw_rate)

    return f"""📊 *수익 리포트*

- 실현 손익: {realized_pnl:.2f} USDT ({realized_krw:,}원)
- 미실현 손익: {unrealized_pnl:.2f} USDT ({unrealized_krw:,}원)
- 총 자산: {total_asset:.2f} USDT ({total_krw:,}원)
"""

def get_profit_report():
    data = fetch_report_data()
    if data.get("status") == "error":
        return f"⚠️ 오류: {data.get('message')}"
    return format_profit_report_text(data)
