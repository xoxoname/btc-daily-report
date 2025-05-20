def build_report(market_data, tech_data, psych_data, forecast, alerts, prev_check, pnl, user_prompt):
    lines = []
    lines.append("📡 GPT 매동 예측 분석 리포트")
    lines.append(f"📅 작성 시각: {pnl.get('작성 시각') or '실시간'}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📌 시장 이벤트 및 속보")
    for s in market_data:
        lines.append(f"- {s}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📉 기술적 분석")
    for s in tech_data:
        lines.append(f"- {s}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 심리·구조적 분석")
    for s in psych_data:
        lines.append(f"- {s}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("🔮 향후 12시간 예측")
    for s in forecast:
        lines.append(f"- {s}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("🚨 예외 감지")
    for s in alerts:
        lines.append(f"- {s}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 예측 검증 (지난 리포트 대비)")
    for s in prev_check:
        lines.append(f"- {s}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("💰 금일 수익 및 미실현 손익")
    for k, v in pnl.items():
        lines.append(f"- {k}: {v}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 멘탈 케어 코멘트\n오늘 수익은 의미 있는 걸음입니다. 내일도 차분히 기회를 기다리세요. 👟")
    return "\n".join(lines)
