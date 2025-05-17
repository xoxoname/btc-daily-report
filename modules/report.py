import datetime
from modules.utils import format_usd, format_krw, get_current_timestamp
from modules.bitget_api import get_bitget_data

def generate_profit_report():
    data = get_bitget_data()
    pos = data["positions"][0]
    msg = f"""📆 *{get_current_timestamp()} 기준 수익 리포트*

💸 [실시간 수익 리포트]

🔹 *포지션:* {pos['symbol']}
🔹 *진입가:* {format_usd(pos['entry_price'])}
🔹 *현재가:* {format_usd(pos['current_price'])}
🔹 *미실현 손익:* {format_usd(pos['pnl_usd'])} (약 {format_krw(pos['pnl_krw'])})
🔹 *수익률:* {data['return_rate']}%

🧾 *오늘 실현 손익:* {format_usd(data['realized'])} (약 {format_krw(data['realized'] * 1370)})
💼 *입금 기준 자산:* ${data['deposit']} → ${data['now_asset']}
📊 *총 수익:* {format_usd(data['total_pnl'])} (약 {format_krw(data['total_krw'])})"""
    if data['total_pnl'] < 0:
        msg += f"""\n😥 *멘탈 코멘트:*
오늘은 살짝 흔들렸지만, 포커 게임에서도 한두 번 접는 건 전략입니다.
📊 지난 7일 누적 수익률은 여전히 +{data['weekly_return']}%로 수익권 유지 중이에요!
지금은 조급함보다 침착함이 자산을 지키는 열쇠입니다."""
    else:
        msg += """
😌 *멘탈 코멘트:*
오늘은 꽤 잘 버셨네요! 🍕 야식 3번은 시켜 먹을 수 있을 정도입니다.
무리하지 말고 이 흐름 유지해보세요. 장기전이니까요.
"""
    return msg