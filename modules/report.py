import os
from datetime import datetime
from openai import OpenAI
from modules.utils import fetch_report_data

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_profit_report():
    data = fetch_report_data()
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

def get_prediction_report():
    data = fetch_report_data()
    market = data.get("market_summary", "정보 없음")
    tech = data.get("technical_analysis", "정보 없음")
    sentiment = data.get("sentiment", "정보 없음")
    prediction = data.get("next_12h_prediction", "정보 없음")
    risk = data.get("risk_flags", [])
    feedback = data.get("previous_feedback", "이전 예측 정보 없음")

    risk_alert = "\n⚠️ *주의 요인 감지됨*" if risk else ""

    return f"""📈 *매동 예측 리포트*

🗞 *시장 이슈*: {market}
📊 *기술 분석*: {tech}
🧠 *심리/구조*: {sentiment}
⏳ *12시간 예측*: {prediction}{risk_alert}

📌 *예측 검증 및 피드백*
{feedback}
"""

def get_full_report():
    return get_profit_report() + "\n" + get_prediction_report()
