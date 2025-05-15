import datetime
import pytz

def get_profit_report():
    # 샘플 데이터 - 실제 데이터로 대체 필요
    total_usdt_pnl = 187.2
    total_krw_pnl = 252000
    today_usdt_pnl = 21.5
    today_krw_pnl = 28900

    report = {
        "generated_at": datetime.datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S"),
        "today": {
            "usdt_pnl": f"{today_usdt_pnl:+.2f}",
            "krw_pnl": f"{today_krw_pnl:,}원"
        },
        "total": {
            "usdt_pnl": f"{total_usdt_pnl:+.2f}",
            "krw_pnl": f"{total_krw_pnl:,}원"
        },
        "comment": get_emotional_comment(today_krw_pnl)
    }
    return report

def get_emotional_comment(today_krw):
    if today_krw >= 100000:
        return "오늘 하루 수익으로 5시간 카페 알바는 거뜬히 대체했어요! 👏"
    elif today_krw >= 30000:
        return "오늘 수익은 편의점 야간 2시간 알바 수준이에요. 무리한 진입은 자제하세요. 🤚"
    elif today_krw >= 0:
        return "소소한 수익도 누적되면 큽니다. 너무 조급해하지 마세요. 😊"
    else:
        return "손실은 회피보다 통제입니다. 무리한 복구매매는 금물! 🧘"

def format_profit_report_text(report: dict):
    t = report["today"]
    total = report["total"]
    comment = report["comment"]
    time = report["generated_at"]

    return f"""📊 *BTC 실시간 수익 리포트*
⏱ 기준시각: {time} (KST)

💵 *오늘 수익 (자정 이후)*  
└ USDT: `{t['usdt_pnl']}`  
└ 원화: `{t['krw_pnl']}`

📈 *총 누적 수익*  
└ USDT: `{total['usdt_pnl']}`  
└ 원화: `{total['krw_pnl']}`

🧠 *멘탈 관리 한마디*  
_{comment}_
"""

# 예시 테스트 (로컬 실행 시 활용)
if __name__ == "__main__":
    rpt = get_profit_report()
    print(format_profit_report_text(rpt))
