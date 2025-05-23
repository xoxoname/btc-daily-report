
from datetime import datetime
import pytz
from modules.bitget_api import get_positions

def generate_profit_report():
    now = datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
    try:
        data = get_positions()
        print("📡 Bitget API 응답 원문:", data)
        pos = data.get('data')

        if not pos:
            return "[수익 리포트]\n작성 시각: {}\n---------------------\nBitget API 응답 없음.".format(now)

        if float(pos.get('openPrice', 0)) == 0 or float(pos.get('margin', 0)) == 0:
            return "[수익 리포트]\n작성 시각: {}\n---------------------\n현재 활성 포지션이 없습니다. 📭".format(now)

        entry_price = float(pos.get('openPrice'))
        mark_price = float(pos.get('markPrice'))
        leverage = int(pos.get('leverage'))
        pnl = float(pos.get('unrealizedPL'))
        margin = float(pos.get('margin'))
        direction = "롱" if pos.get('holdSide') == 'long' else '숏'
        rate = (pnl / margin) * 100 if margin != 0 else 0
        krw_total = pnl * 1350

        if rate >= 10:
            comment = "오늘 선물로 {:,.0f}원을 벌었습니다. 여행 경비로 충분해요!".format(krw_total)
        elif rate >= 5:
            comment = "오늘 수익은 약 {:,.0f}원, 편의점 알바 약 10시간치입니다.".format(krw_total)
        elif rate > 0:
            comment = "오늘도 +수익 마감. 작지만 소중합니다."
        elif rate > -5:
            comment = "소폭 손실({:.2f}%)은 전략적 휴식일 수 있어요.".format(rate)
        else:
            comment = "손실이 큽니다. 무리한 매매는 피해주세요."

        return "[현재 수익 현황 요약]\n작성 시각: {}\n---------------------\n[포지션 정보]\n- 종목: BTCUSDT\n- 방향: {}\n- 진입가: ${} / 현재가: ${}\n- 레버리지: {}x\n---------------------\n[손익 정보]\n- 미실현 손익: ${:.2f} (약 {:,.0f}원)\n- 진입 자산: ${}\n- 수익률: {:.2f}%\n---------------------\n[멘탈 코멘트]\n{}".format(
            now, direction, entry_price, mark_price, leverage, pnl, krw_total, margin, rate, comment)

    except Exception as e:
        return "Bitget API 오류: {}".format(str(e))
