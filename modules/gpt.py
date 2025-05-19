import random

def get_dynamic_mental_comment(pnl_usd, pnl_krw):
    if pnl_usd > 0:
        candidates = [
            f"오늘 {pnl_krw:,}원의 수익! 이 정도면 하루 커피값 걱정 끝이죠. 하지만 오늘의 이득에 취하지 말고, 다음 기회가 올 때까지 침착하게!",
            f"수익 {pnl_krw:,}원, 현실 알바 6시간! 매매는 매일 오는 게 아니니, 내일은 휴식도 고려해보세요.",
            f"수익 축하! {pnl_krw:,}원은 정말 큰 성과입니다. 과도한 자신감은 금물, 항상 원칙을 지켜주세요."
        ]
    elif pnl_usd < 0:
        candidates = [
            f"{abs(pnl_krw):,}원의 손실이 발생했어요. 아직 1주일 전체로 보면 수익권입니다. 조급함 대신 침착함을 챙겨봐요.",
            f"오늘은 살짝 힘들었지만, {abs(pnl_krw):,}원 손실도 경험입니다. 충동 매매는 꼭 자제, 리프레시 하면서 다음 기회를!",
            f"손실 {abs(pnl_krw):,}원, 누구나 겪는 과정이니 자신을 탓하지 마세요. 내일 더 좋은 매매로 복구 가능합니다."
        ]
    else:
        candidates = [
            "큰 수익도, 큰 손실도 없는 하루. 평온한 마음으로 오늘 하루를 정리해보세요.",
            "시장 관망도 실력! 다음 기회엔 더 신중하게."
        ]
    return random.choice(candidates)
