from modules.bitget_api import fetch_wallet_balance, fetch_position
from modules.utils import format_currency, get_kst_now

def generate_profit_report():
    available, total = fetch_wallet_balance()
    positions = fetch_position()
    kst_now = get_kst_now().strftime('%Y-%m-%d %H:%M:%S')

    msg = f"📊 [정규 리포트]\n⏰ 기준 시각: {kst_now}\n\n"
    msg += f"💰 총 자산: {format_currency(total)}\n🔓 사용 가능: {format_currency(available)}\n\n"

    if positions:
        msg += "📈 포지션:\n"
        for p in positions:
            msg += f"- {p['symbol']} | 진입가: {p['entry_price']} | 현재가: {p['market_price']} | PnL: {format_currency(p['pnl'])}\n"
    else:
        msg += "보유 중인 포지션이 없습니다."

    return msg

def generate_prediction_report():
    return (
        "📍 [비트코인 12시간 동향 예측 분석]\n"
        "발행 시각: 오늘 오전 9시\n"
        "분석 기준 시세: $10278.50 (Coinbase 기준)\n\n"
        "📌 1. 시장 이벤트 및 뉴스 요약 (중립)\n"
        "- 미국 PPI 발표 결과 예상치 부합\n"
        "- 트럼프 연설 예고 → 단기 변동성 가능성\n\n"
        "📈 2. 기술적 분석 (호재)\n"
        "- RSI 58, MACD 골든크로스 유지\n"
        "- 지지선 $10180 / 저항선 $10400\n\n"
        "🧠 3. 심리 분석 (중립)\n"
        "- 공포탐욕지수: 63 (탐욕)\n"
        "- 펀딩비: +0.009%\n\n"
        "⏱ 4. 향후 12시간 전망\n"
        "- 상승 63%, 횡보 24%, 하락 13%\n"
        "- 변동 범위: $10250 ~ $10400\n\n"
        "💰 수익 정보\n"
        "- 실현손익: +$55.40, 미실현: +$78.50, 총수익: +$133.90\n\n"
        "😌 멘탈\n"
        "야식 5번 시켜도 남는 수익입니다. 조급해하지 마세요!"
    )

def generate_schedule_report():
    return (
        "🗓️ 금일 보고 일정은 다음과 같습니다:\n"
        "- 오전 9시\n- 오후 1시\n- 오후 11시\n(모두 KST 기준)\n\n"
        "📅 향후 주요 일정:\n"
        "- 5월 17일: 트럼프 암호화폐 연설 (호재 가능성)\n"
        "- 5월 20일: 연준 금리 발표 (변동성 증가)\n"
        "- 5월 22일: 미-중 무역회담 (중립)\n"
        "- 5월 25일: BTC 국제 컨퍼런스 (관심도 증가)"
    )
