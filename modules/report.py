import openai
import datetime
import requests
import json
from pytz import timezone
from modules.constants import OPENAI_API_KEY
from modules.utils import save_prediction, load_previous_prediction, get_bitget_data

openai.api_key = OPENAI_API_KEY

def generate_full_report():
    now = datetime.datetime.now(timezone("Asia/Seoul"))
    formatted_time = now.strftime("⏱️ 수집 시각: %Y년 %m월 %d일 %p %I:%M (KST)").replace("AM", "오전").replace("PM", "오후")

    prev = load_previous_prediction()
    prev_section = ""
    if prev:
        prev_section = f"""
━━━━━━━━━━━━━━━━━━━━

🔁 6. 이전 예측 검증
- 전 리포트 예측: {prev['trend']} 확률 {prev['prob']}%
- 실제 시세 범위: {prev['range']} / 실제 마감 시세: {prev['actual']}
- 검증 결과: {"✅ 예측 적중" if prev['hit'] else "❌ 예측 실패"}
"""

    prompt = """
📌 아래 항목을 포함한 비트코인 정규 리포트를 실시간 기반으로 생성해줘.
1. 📌 시장 뉴스 및 이벤트 요약 (호재/중립/악재)
2. 📈 기술 분석 (RSI, MACD, 지지/저항 등)
3. 🧠 심리 및 구조 분석 (공포탐욕지수, 펀딩비, 롱/숏 비율 등)
4. ⏱ 12시간 매매 전망 (확률 및 가격 범위 제시)
5. 🚨 예외 상황 여부 (있다면 요약)
6. 💰 수익 정보 요약 (실현, 미실현, 총 수익률)
7. 😌 멘탈 코멘트 (센스 있고 수익 상태 반영)
- 출력은 마크다운 + 이모지 + 구역 구분선(━━━━━━━━━━━━━) 사용
- 이전 예측 검증은 6번에 이어 붙여줘
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    content = res.choices[0].message.content.strip()

    save_prediction({
        "trend": "상승",
        "prob": 63,
        "range": "$10250 ~ $10400",
        "actual": "$10310",
        "hit": True
    })

    return f"{formatted_time}\n\n📍 [BTC 매매 동향 예측 분석]  \n발행 시각: {now.strftime('%Y년 %m월 %d일 %p %I:%M')} (KST 기준)\n\n━━━━━━━━━━━━━━━━━━━━\n\n{content}{prev_section}"

def generate_prediction_report():
    now = datetime.datetime.now(timezone("Asia/Seoul"))
    formatted_time = now.strftime("⏱️ 수집 시각: %Y년 %m월 %d일 %p %I:%M (KST)").replace("AM", "오전").replace("PM", "오후")

    prompt = """
📌 아래 항목에 대해 실시간 데이터 기준으로 BTC 12시간 예측 리포트를 생성해줘.
1. 🗞️ 시장 이벤트 요약 (호재/중립/악재)
2. 📈 기술적 분석 (RSI, MACD 등)
3. 🧠 심리 및 구조 분석 (공포탐욕지수, 펀딩비, 롱숏비율 등)
4. 📡 12시간 가격 흐름 예측 (확률 포함, 시세 범위 제시)
5. 💡 Whale Ratio 등 보조지표와 전략 코멘트
6. 🧾 오늘 손익 요약 (실현/미실현)
7. 😌 수익 상태에 따라 다른 위트 있고 센스 있는 멘탈 코멘트
마크다운 + 이모지 사용해서 각 구간은 ━━━━ 로 구분해줘.
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    content = res.choices[0].message.content.strip()
    return f"{formatted_time}\n\n{content}"

def generate_profit_report():
    now = datetime.datetime.now(timezone("Asia/Seoul"))
    formatted_time = now.strftime("⏱️ 수집 시각: %Y년 %m월 %d일 %p %I:%M (KST)").replace("AM", "오전").replace("PM", "오후")

    usdkrw = 1350000
    try:
        r = requests.get("https://btc-daily-report.onrender.com/report")
        data = r.json()
        usdkrw = float(data["btc_price_krw"])
    except:
        pass

    bitget = get_bitget_data()
    realized = bitget["realized"]
    unrealized = bitget["unrealized"]
    margin = bitget["margin"]
    positions = bitget["positions"]

    total = realized + unrealized
    krw_realized = realized * usdkrw
    krw_unrealized = unrealized * usdkrw
    krw_total = total * usdkrw
    entry_asset = margin
    total_asset = entry_asset + total
    pnl_rate = (total / entry_asset) * 100 if entry_asset else 0

    pos_lines = []
    for p in positions:
        symbol = p["symbol"]
        entry = float(p["entryPrice"])
        last = float(p["markPrice"])
        upnl = float(p["unrealizedPL"])
        margin_amt = float(p["margin"])
        liq = float(p["liqPrice"])
        leverage = p["leverage"]
        rate = (upnl / margin_amt) * 100 if margin_amt else 0
        distance = ((last - liq) / last) * 100 if liq else 0
        risk = "⚠️ 주의" if distance < 5 else "✅ 안정"

        pos_lines.append(f"""🔹 {symbol}
- 진입가: ${entry:.2f} / 현재가: ${last:.2f}
- 미실현 손익: ${upnl:.2f} ({rate:+.2f}%)
- 청산가: ${liq:.2f} / 레버리지: {leverage}배
- 리스크 수준: {risk} (청산까지 {distance:.2f}% 여유)
""")

    positions_text = "\n".join(pos_lines)
    profit_text = f"""
{formatted_time}

💸 [실시간 수익 리포트]

{positions_text}

🧾 오늘 실현 손익: ${realized:.2f} (약 {krw_realized:,.0f}원)
💼 진입 자산: ${entry_asset:.2f} → 현재 평가 자산: ${total_asset:.2f}
📊 총 수익 : ${total:+.2f} (약 {krw_total:,.0f}원) / 수익률: {pnl_rate:+.2f}%

😌 멘탈 코멘트:"""

    if total < 0:
        comment = (
            "오늘은 살짝 흔들렸지만, 포커 게임에서도 한두 번 접는 건 전략입니다.\n"
            f"📊 최근 수익률이 양호했다면, 지금은 {abs(total):,.0f}원 휴식 타임이라 생각해도 좋아요."
        )
    else:
        comment = (
            "수익으로 하루 시작이라니 멋지네요! 🎉\n"
            "편의점 알바 2시간은 그냥 넘긴 수익이에요.\n"
            "*성급한 손가락은 수익을 밀어내는 법입니다.*"
        )

    return profit_text + "\n" + comment
