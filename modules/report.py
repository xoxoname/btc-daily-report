import requests
from datetime import datetime, timedelta

def fetch_report_data():
    try:
        response = requests.get("https://btc-daily-report.onrender.com/report", timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_profit_report():
    data = fetch_report_data()
    if "error" in data:
        return f"❌ 오류 발생: {data['error']}"

    total_usdt = data["total_usdt"]
    total_krw = data["total_krw"]
    realized_pnl = data["realized_pnl"]
    unrealized_pnl = data["unrealized_pnl"]
    roi = data["roi"]

    return (
        f"📊 실시간 수익 리포트\n\n"
        f"- 총 자산: {total_usdt} USDT ({total_krw}원)\n"
        f"- 실현 손익: {realized_pnl} USDT\n"
        f"- 미실현 손익: {unrealized_pnl} USDT\n"
        f"- 수익률(ROI): {roi} %"
    )

def get_prediction_report():
    data = fetch_report_data()
    if "error" in data:
        return f"❌ 오류 발생: {data['error']}"

    prediction = data["prediction"]
    signals = data["signals"]
    confidence = data["confidence"]

    return (
        f"📈 단기 매매 예측 리포트\n\n"
        f"- 예측 방향: {prediction}\n"
        f"- 주요 신호: {', '.join(signals)}\n"
        f"- 신뢰도: {confidence} %"
    )

def get_full_prediction_report():
    data = fetch_report_data()
    if "error" in data:
        return f"❌ 오류 발생: {data['error']}"

    prediction = data["prediction"]
    signals = data["signals"]
    confidence = data["confidence"]
    context = data["market_context"]
    feedback = data["previous_feedback"]
    pnl_today = data["pnl_today"]
    equivalent_job = data["equivalent_job"]

    return (
        f"🧠 GPT 매매 동향 예측 리포트\n\n"
        f"1. 📉 시장 요약: {context}\n"
        f"2. 🔍 주요 신호: {', '.join(signals)}\n"
        f"3. 📊 예측 방향: {prediction}\n"
        f"4. 📌 예측 신뢰도: {confidence} %\n"
        f"5. 🧪 지난 예측 검증 결과: {feedback}\n\n"
        f"💰 오늘의 수익: {pnl_today} USDT\n"
        f"💡 알바 환산: {equivalent_job}\n\n"
        f"⚠️ 위 리포트는 구조적 지표, 심리 흐름, 실시간 기술 분석을 기반으로 작성되었습니다."
    )
