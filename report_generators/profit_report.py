def _format_position_details(self, position_info: dict) -> str:
    """포지션 상세 포맷팅"""
    if not position_info or not position_info.get('has_position'):
        return "• 현재 보유 포지션 없음"
    
    # 청산까지 거리 계산
    current_price = position_info.get('current_price', 0)
    liquidation_price = position_info.get('liquidation_price', 0)
    side = position_info.get('side', '롱')
    side_en = position_info.get('side_en', 'long')
    
    distance_text = "계산불가"
    if liquidation_price > 0 and current_price > 0:
        if side_en in ['short', 'sell']:
            # 숏포지션: 가격이 올라가면 청산
            distance = ((liquidation_price - current_price) / current_price) * 100
            direction = "상승"
        else:
            # 롱포지션: 가격이 내려가면 청산
            distance = ((current_price - liquidation_price) / current_price) * 100
            direction = "하락"
        distance_text = f"{abs(distance):.1f}% {direction}시 청산"
    
    lines = [
        f"• 종목: {position_info.get('symbol', 'BTCUSDT')}",
        f"• 방향: {side}",  # (하락 베팅) 제거
        f"• 진입가: ${position_info.get('entry_price', 0):,.2f} / 현재가: ${current_price:,.2f}",
        # 포지션 크기 제거
        f"• 진입 증거금: {self._format_currency(position_info.get('margin', 0))}",
        f"• 레버리지: {position_info.get('leverage', 1)}배",
        f"• 청산가: ${liquidation_price:,.2f}" if liquidation_price > 0 else "• 청산가: 조회불가",
        f"• 청산까지 거리: {distance_text}"
    ]
    
    return '\n'.join(lines)

def _format_pnl_details(self, account_info: dict, position_info: dict, 
                      today_pnl: float, weekly_profit: dict) -> str:
    """손익 상세 포맷팅"""
    total_equity = account_info.get('total_equity', 0)
    available = account_info.get('available', 0)
    unrealized_pnl = account_info.get('unrealized_pnl', 0)
    
    # 포지션별 미실현손익이 더 정확할 수 있음
    if position_info and position_info.get('has_position'):
        position_unrealized = position_info.get('unrealized_pnl', 0)
        if abs(position_unrealized) > abs(unrealized_pnl):
            unrealized_pnl = position_unrealized
    
    # 금일 총 수익
    total_today = today_pnl + unrealized_pnl
    
    lines = [
        f"• 미실현 손익: {self._format_currency(unrealized_pnl)}",
        f"• 금일 실현 손익: {self._format_currency(today_pnl)}",  # 오늘 → 금일
        f"• 금일 총 수익: {self._format_currency(total_today)}",
        f"• 총 자산: {self._format_currency(total_equity, False)} ({total_equity * 1350 / 10000:.0f}만원)",
        f"• 가용 자산: {self._format_currency(available, False)} ({available * 1350 / 10000:.1f}만원)",
    ]
    
    # 포지션이 있을 때만 증거금 표시
    if position_info and position_info.get('has_position'):
        margin = position_info.get('margin', 0)
        lines.append(f"• 포지션 증거금: {self._format_currency(margin)}")
    
    # 수익률 계산
    if total_equity > 1000:  # 합리적인 자산 규모일 때만
        daily_roi = (total_today / total_equity) * 100
        lines.append(f"• 금일 수익률: {daily_roi:+.2f}%")
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━",
        f"📊 최근 7일 수익: {self._format_currency(weekly_profit['total'])}",
        f"📊 최근 7일 평균: {self._format_currency(weekly_profit['average'])}/일"
    ])
    
    # 7일 수익률 (total_equity로 계산)
    if weekly_profit['total'] != 0 and total_equity > 1000:
        weekly_roi = (weekly_profit['total'] / total_equity) * 100
        lines.append(f"📊 7일 수익률: {weekly_roi:+.1f}%")
    
    return '\n'.join(lines)
