import os
from datetime import datetime

def fetch_bitget_data():
    # Mock data (replace with actual Bitget API call)
    return {
        "symbol": "BTCUSDT",
        "side": "short",
        "entry_price": 66200,
        "mark_price": 65400,
        "leverage": 10,
        "unrealized_pnl": 75.0,
        "realized_pnl": 30.0,
        "margin": 2000
    }

def calculate_report(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    profit = data["unrealized_pnl"] + data["realized_pnl"]
    krw = profit * 1350
    report = "[수익 리포트]\n"
    report += f"작성 시각: {now}\n"
    report += "---------------------\n"
    report += "[포지션 정보]\n"
    report += f"- 종목: {data['symbol']}\n"
    report += f"- 방향: {data['side'].capitalize()}\n"
    report += f"- 진입가: ${data['entry_price']:,} / 현재가: ${data['mark_price']:,}\n"
    report += f"- 레버리지: {data['leverage']}x\n\n"
    report += "[손익 정보]\n"
    report += f"- 미실현 손익: +${data['unrealized_pnl']} ({int(data['unrealized_pnl'] * 1350):,}원)\n"
    report += f"- 실현 손익: +${data['realized_pnl']} ({int(data['realized_pnl'] * 1350):,}원)\n"
    report += f"- 총 수익: +${profit} ({int(krw):,}원)\n"
    report += f"- 수익률: +{(profit / data['margin']) * 100:.2f}%\n\n"
    report += "[멘탈 코멘트]\n"
    report += f"오늘 수익은 약 {int(krw):,}원으로 편의점 알바 약 {int(krw // 10000)}시간치에 해당해요!"
    return report

async def generate_report():
    try:
        data = fetch_bitget_data()
        return calculate_report(data)
    except Exception as e:
        return f"[수익 리포트]\nBitget API 오류: {e}"
