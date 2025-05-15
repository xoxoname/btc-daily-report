import os
import json
import requests
from datetime import datetime
import pytz
from flask import Flask, jsonify

# Timezone 설정 (한국 시간)
kst = pytz.timezone("Asia/Seoul")

def get_current_time_str(fmt='%Y-%m-%d %H:%M:%S'):
    return datetime.now(kst).strftime(fmt)

# 실현 및 미실현 손익 데이터를 외부 엔드포인트에서 가져옵니다.
def get_profit_report():
    try:
        response = requests.get("https://btc-daily-report.onrender.com/report")
        data = response.json()
        return data
    except Exception as e:
        return {"error": str(e)}

# 손익 데이터를 텍스트로 포맷팅합니다.
def format_profit_report_text(data):
    try:
        krw_pnl = data.get("krw_pnl", "N/A")
        usdt_pnl = data.get("usdt_pnl", "N/A")
        now_str = get_current_time_str()
        return f"[{now_str} 기준]\n💰 실현 + 미실현 총 손익:\n- {usdt_pnl} USDT\n- 약 {krw_pnl} KRW"
    except:
        return "손익 정보 분석 실패"

# 예측 보고서 데이터를 생성합니다.
def get_prediction_report():
    try:
        return {
            "market": "미국 CPI 발표: 예상치 부합 (2.4%) → 시장 안도감\nFOMC 발언 없음\n긴급 속보 없음",
            "technical": "MACD 하락 전환, RSI 68, MA(20/50) 이격 축소 → 기술적 조정 가능성",
            "psychology": "공포탐욕지수 72 (탐욕), 커뮤니티 정서는 낙관\nDXY 상승세 유지, BTC Dominance 상승",
            "forecast": {
                "up_probability": 42,
                "down_probability": 58,
                "summary": "📉 하락 가능성 우세: DXY 상승 + MACD 약세"
            },
            "exceptions": [],
            "feedback": {
                "match": "이전 예측과 유사함",
                "reason": "DXY 영향 지속 반영됨",
                "next": "심리 지표 반영 비중 보완 예정"
            }
        }
    except Exception as e:
        return {"error": str(e)}

# 예측 보고서를 텍스트로 포맷팅합니다.
def format_prediction_report_text(data):
    try:
        forecast = data.get("forecast", {})
        up = forecast.get("up_probability", "N/A")
        down = forecast.get("down_probability", "N/A")
        summary = forecast.get("summary", "")

        result = f"""📌 BTC 매동 예측 보고서 ({get_current_time_str('%Y-%m-%d %H:%M')} KST)

[1. 시장 요인 요약]
{data.get('market', '정보 없음')}

[2. 기술적 분석]
{data.get('technical', '정보 없음')}

[3. 심리 및 구조 분석]
{data.get('psychology', '정보 없음')}

[4. 12시간 예측]
- 상승 확률: {up}%
- 하락 확률: {down}%
- 요약: {summary}

[5. 예외 감지]
{", ".join(data.get('exceptions', [])) or '특이사항 없음'}

[6. 이전 예측 피드백]
- 평가: {data.get('feedback', {}).get('match', '정보 없음')}
- 사유: {data.get('feedback', {}).get('reason', '정보 없음')}
- 다음 보완 방향: {data.get('feedback', {}).get('next', '정보 없음')}

🧾 멘탈 코멘트: "한 순간의 수익에 흔들리지 마세요. 오늘도 꾸준한 전략이 답입니다."
"""
        return result
    except:
        return "예측 리포트 분석 실패"

# Flask 앱 구성
app = Flask(__name__)

@app.route('/')
def index():
    return 'BTC Report Service Running'

@app.route('/report')
def report():
    try:
        profit = get_profit_report()
        prediction = get_prediction_report()

        profit_text = format_profit_report_text(profit)
        prediction_text = format_prediction_report_text(prediction)

        response = {
            "profit_raw": profit,
            "prediction_raw": prediction,
            "profit_text": profit_text,
            "prediction_text": prediction_text
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
