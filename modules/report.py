import openai
from modules.constants import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def request_gpt_prediction(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "비트코인 분석가로서 실시간 데이터를 바탕으로 논리적, 구조적 분석을 제공합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"[GPT 오류] {e}")
        return "GPT 응답 처리 중 오류가 발생했습니다."

def build_and_send_report():
    from modules.utils import (
        fetch_coinbase_price,
        fetch_bitget_position_data,
        format_currency,
        send_telegram_message,
        get_kst_now
    )
    from modules.constants import ANALYSIS_LOADING_MESSAGE

    send_telegram_message(ANALYSIS_LOADING_MESSAGE)

    try:
        price = fetch_coinbase_price()
        position = fetch_bitget_position_data()
        now = get_kst_now().strftime("%Y-%m-%d %H:%M")

        prompt = f"""
        현재 시각: {now}
        BTC 현재 가격: ${price:.2f}

        비트코인 가격과 관련된 최근 시장 뉴스, 미증시 일정, 매크로 이벤트, 온체인 데이터, 기술적 지표 등을 모두 고려하여 다음 항목을 포함한 리포트를 작성해줘:

        1. 시장 이벤트 및 속보 요약 + 호재/악재 판단
        2. 기술적 분석 요약 (예: 이동평균, RSI 등) + 판단
        3. 온체인 데이터 요약 (예: 유입/이탈량, HODL 비율 등) + 판단
        4. 심리/구조적 신호 (포지션 비율, 펀딩비 등)
        5. 향후 12시간 매매 동향 예측 (확률 포함)
        6. 예외 탐지 및 변동성 징후
        7. 예측 검증 및 개선 피드백 (이전 리포트 기준)
        8. 마지막엔 오늘 수익 요약 및 멘탈 관리 코멘트 포함

        초보자도 이해할 수 있게 쉽고 명확하게 작성해줘. 지표별로 "호재/중립/악재" 판단도 같이 적어줘.
        """

        gpt_report = request_gpt_prediction(prompt)

        position_str = (
            f"\n\n📌 [기본 수익 요약]\n"
            f"포지션: {position['symbol']}\n"
            f"진입가: ${position['entry_price']:.2f}\n"
            f"현재가: ${position['current_price']:.2f}\n"
            f"미실현 손익: {format_currency(position['pnl'])}\n"
            f"수익률: {position['roe']:.2f}%\n"
            f"실현 손익: {format_currency(position['realized_pnl'])}\n"
            f"오늘 총 수익: {format_currency(position['total_today_pnl'])}\n"
            f"총 자산 변화: ${position['initial_asset']:.2f} → ${position['current_asset']:.2f}"
        )

        send_telegram_message(gpt_report + position_str)

    except Exception as e:
        send_telegram_message(f"[리포트 오류] {e}")
