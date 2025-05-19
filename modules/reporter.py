import os
import pytz
import datetime
import random
from modules.bitget import get_futures_account, get_asset_balance, test_bitget_api
from modules.coinbase import get_coinbase_btc_price
import openai
from modules.telegram_bot import send_long_message

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_krw(usd):
    try:
        import requests
        r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=KRW")
        rate = r.json()["rates"]["KRW"]
        return int(float(usd) * rate)
    except:
        return int(float(usd) * 1350)

def gpt_generate_mental_comment(pnl, pnl_ratio, pnl_krw):
    # 상황·손익·충동억제 기반 GPT 멘탈 멘트 자동 생성
    prompt = (
        f"비트코인 선물 트레이더에게 충동적 매매를 억제할 현실적이고 재치 있는 멘탈 케어 코멘트를 작성하세요.\n"
        f"- 오늘 실현/미실현 합산 수익: {pnl:.2f} USD ({pnl_krw:,}원)\n"
        f"- 오늘 수익률: {pnl_ratio:.2f}%\n"
        f"수익은 {pnl_krw // 14000}시간 편의점 알바와 같다고 가정해, 오늘은 무리한 추가 매매 대신 휴식·복기·다음 전략 준비를 유도하세요. 내일도 무조건 투자하라는 메시지는 금지! 조언은 매번 다르게 작성하고, 중복된 표현을 피해 최대 2문장, 100자 이내로 자연스럽고 위트있게 써주세요."
    )
    try:
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "멘탈 케어 코멘트 생성기"}, {"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        # Fallback
        basic = [
            "오늘 벌어들인 수익은 알바 몇 시간치! 잠깐 쉬며 내일을 준비하세요.",
            "수익에 취하지 말고, 오늘은 전략 복기에 집중해보는 건 어떨까요?",
            "시장은 언제든 열려있어요. 무리하지 않는 것도 능력입니다!"
        ]
        return random.choice(basic)

def format_profit_report():
    now = datetime.datetime.now(pytz.timezone("Asia/Seoul"))
    price = get_coinbase_btc_price()
    pos = get_futures_account()
    asset = get_asset_balance()
    test_api_msg = test_bitget_api() if isinstance(pos, dict) and "error" in pos else ""
    # 실제 파싱 예시
    entry_price = float(pos.get("openPrice", price or 0)) if isinstance(pos, dict) else 0
    current_price = price or entry_price
    leverage = float(pos.get("leverage", 1)) if isinstance(pos, dict) else 1
    pnl = float(pos.get("unrealizedPL", 0)) if isinstance(pos, dict) else 0
    realized_pnl = float(pos.get("realizedPL", 0)) if isinstance(pos, dict) else 0
    position_amt = float(pos.get("holdVol", 0)) if isinstance(pos, dict) else 0
    asset_balance = asset.get("data", [{}])[0].get("marginBalance", 0) if isinstance(asset, dict) and "data" in asset else 0
    margin = float(asset_balance)
    total_pnl = pnl + realized_pnl
    pnl_ratio = ((total_pnl) / margin * 100) if margin else 0
    pnl_krw = get_krw(total_pnl)
    mental = gpt_generate_mental_comment(total_pnl, pnl_ratio, pnl_krw)
    # 알바 환산
    alba_hr = max(1, pnl_krw // 14000)
    report = f"""💰 현재 수익 현황 요약
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
종목: BTCUSDT
방향: {"롱" if position_amt > 0 else "숏" if position_amt < 0 else "미보유"}
진입가: ${entry_price:,.0f} / 현재가: ${current_price:,.0f}
레버리지: {leverage}x
━━━━━━━━━━━━━━━━━━━
💸 손익 정보
미실현 손익: {pnl:+.2f} USD ({get_krw(pnl):,}원)
실현 손익: {realized_pnl:+.2f} USD ({get_krw(realized_pnl):,}원)
금일 총 수익: {total_pnl:+.2f} USD ({pnl_krw:,}원)
진입 자산: ${margin:,.0f}
수익률: {pnl_ratio:+.2f}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{mental}
━━━━━━━━━━━━━━━━━━━
{test_api_msg}
"""
    return report

def send_scheduled_reports():
    msg = format_profit_report()
    send_long_message(msg)

# 명령어별 리포트 생성 함수도 같은 구조로 제작 가능
