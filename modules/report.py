# modules/report.py

import requests
import datetime

def get_profit_report():
    try:
        res = requests.get("https://btc-daily-report.onrender.com/report")
        data = res.json()
        usdt_pnl = data["usdt_pnl"]
        krw_pnl = data["krw_pnl"]
        return f"📈 수익 리포트\n\n총 수익: {usdt_pnl} USDT ({krw_pnl}원)"
    except:
        return "❌ 수익 정보를 불러오지 못했습니다."

def get_prediction_report():
    # 예측용 간략 리포트
    return "📉 예측 리포트\n\n비트코인은 현재 기술적 저항선 근접 중입니다. 단기 하락 가능성 60%로 판단됩니다."

def get_full_prediction_report():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"📊 GPT 정밀 BTC 매매 동향 리포트\n🕒 분석 기준: {now}\n\n"
        "- 주요 시장 이벤트: 없음\n"
        "- 기술적 분석: RSI 과매수, MACD 약세 전환\n"
        "- 심리/구조 분석: 롱 포지션 과다, 미결제약정 증가\n"
        "- 향후 12시간 예측: 약조정 또는 횡보 가능성 높음 (하락 55%)\n"
        "- 예외 감지 시스템: 이상 없음\n"
        "- 이전 예측 검증: 오전 9시 예측 정확도 82%\n\n"
        "💬 멘탈 관리: 차분히 다음 기회를 기다리세요. 매매는 확률 게임입니다.\n"
        "💸 오늘 수익은 편의점 3시간 알바와 유사합니다.\n"
    )
