from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback

class ProfitReportGenerator(BaseReportGenerator):
    """수익 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
    
    async def generate_report(self) -> str:
        """💰 /profit 명령어 리포트 생성"""
        try:
            current_time = self._get_current_time_kst()
            
            # 실시간 데이터 조회
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            today_pnl = await self._get_today_realized_pnl()
            weekly_profit = await self._get_weekly_profit()
            
            # 포지션 정보 포맷
            position_text = self._format_position_details(position_info)
            
            # 손익 정보 포맷
            pnl_text = self._format_pnl_details(account_info, position_info, today_pnl, weekly_profit)
            
            # 멘탈 케어
            mental_text = await self.mental_care.generate_profit_mental_care(
                account_info, position_info, today_pnl, weekly_profit
            )
            
            report = f"""💰 /profit 명령어 – 포지션 및 손익 정보
💰 현재 보유 포지션 및 수익 요약
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📌 보유 포지션 정보
{position_text}

━━━━━━━━━━━━━━━━━━━

💸 손익 정보
{pnl_text}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"수익 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return "❌ 수익 현황 조회 중 오류가 발생했습니다."
    
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
            f"• 방향: {side} ({'하락 베팅' if side == '숏' else '상승 베팅'})",
            f"• 진입가: ${position_info.get('entry_price', 0):,.2f} / 현재가: ${current_price:,.2f}",
            f"• 포지션 크기: {position_info.get('size', 0):.4f} BTC",
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
            f"• 오늘 실현 손익: {self._format_currency(today_pnl)}",
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
        
        # 7일 수익률
        if weekly_profit['total'] > 0 and total_equity > 1000:
            weekly_roi = (weekly_profit['total'] / total_equity) * 100
            lines.append(f"📊 7일 수익률: {weekly_roi:+.1f}%")
        
        return '\n'.join(lines)
