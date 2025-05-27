def _format_pnl_details(self, account_info: dict, position_info: dict, 
                      today_pnl: float, weekly_profit: dict) -> str:
    """손익 상세 포맷팅 - 정확한 계산"""
    total_equity = account_info.get('total_equity', 0)
    available = account_info.get('available', 0)
    used_margin = account_info.get('used_margin', 0)
    unrealized_pnl = account_info.get('unrealized_pnl', 0)
    
    # 포지션별 미실현손익이 더 정확할 수 있음
    if position_info and position_info.get('has_position'):
        position_unrealized = position_info.get('unrealized_pnl', 0)
        if abs(position_unrealized) > 0:
            unrealized_pnl = position_unrealized
    
    # 금일 총 수익
    total_today = today_pnl + unrealized_pnl
    
    lines = [
        f"• 미실현 손익: {self._format_currency(unrealized_pnl)}",
        f"• 오늘 실현 손익: {self._format_currency(today_pnl)}",
        f"• 금일 총 수익: {self._format_currency(total_today)}",
        f"• 총 자산: {self._format_currency(total_equity, False)} ({total_equity * 1350 / 10000:.0f}만원)",
        f"• 가용 자산: {self._format_currency(available, False)} ({available * 1350 / 10000:.1f}만원)",
    ]
    
    # 사용중인 증거금 표시
    if used_margin > 0:
        lines.append(f"• 사용중 증거금: {self._format_currency(used_margin, False)}")
    
    # 수익률 계산
    if total_equity > 1000:  # 합리적인 자산 규모일 때만
        daily_roi = (total_today / total_equity) * 100
        lines.append(f"• 금일 수익률: {daily_roi:+.2f}%")
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━",
        f"📊 최근 7일 수익: {self._format_currency(weekly_profit['total'])}",
        f"📊 최근 7일 평균: {self._format_currency(weekly_profit['average'])}/일"
    ])
    
    # 7일 수익률
    if weekly_profit['total'] != 0 and total_equity > 1000:
        weekly_roi = (weekly_profit['total'] / total_equity) * 100
        lines.append(f"📊 7일 수익률: {weekly_roi:+.1f}%")
    
    return '\n'.join(lines)
