from modules.utils import kr_now_str, with_krw, format_number
from modules.gpt_analysis import gpt_analyze, random_mental_comment

def build_report(market_data, tech_data, psych_data, forecast, alerts, pnl, prev_check, user_prompt):
    # user_prompt: "실시간 BTC 시장 리포트 및 전략 분석을 아래 항목 순서대로 한국어로 작성: ..."
    report = []
    report.append(f"📡 GPT 매동 예측 분석 리포트\n📅 작성 시각: {kr_now_str()}")
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("📌 시장 이벤트 및 속보")
    report.extend([f"- {line}" for line in market_data])
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("📉 기술적 분석")
    report.extend([f"- {line}" for line in tech_data])
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("🧠 심리·구조적 분석")
    report.extend([f"- {line}" for line in psych_data])
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("🔮 향후 12시간 예측")
    report.extend([f"- {line}" for line in forecast])
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("🚨 예외 감지")
    report.extend([f"- {line}" for line in alerts])
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("📊 예측 검증 (지난 리포트 대비)")
    report.extend([f"- {line}" for line in prev_check])
    report.append("━━━━━━━━━━━━━━━━━━━")
    report.append("💰 금일 수익 및 미실현 손익")
    for k, v in pnl.items():
        report.append(f"- {k}: {v}")
    report.append("━━━━━━━━━━━━━━━━━━━")
    # 멘탈 케어 코멘트
    try:
        report.append("🧠 멘탈 케어 코멘트")
        report.append(random_mental_comment(float(pnl.get("수익률", "0").replace('%', ''))))
    except Exception:
        report.append("🧠 멘탈 케어 코멘트\n오늘은 시스템 점검 중입니다.")
    return "\n".join(report)
