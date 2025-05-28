# report_generators/profit_report.py
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
            market_data = await self._get_market_data()
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            today_pnl = await self._get_today_realized_pnl()
            weekly_profit = await self._get_weekly_profit()
            
            # 누적 수익 계산 (초기 자산을 4000으로 가정, 실제로는 설정값 사용)
            initial_capital = 4000  # 초기 투자금
            total_equity = account_info.get('total_equity', initial_capital)
            cumulative_profit = total_equity - initial_capital
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            
            # 포지션 정보 포맷
            position_text = self._format_position_details(position_info, market_data.get('change_24h', 0))
            
            # 손익 정보 포맷 
            pnl_text = self._format_pnl_details(
                account_info, position_info, today_pnl, total_equity
            )
            
            # 자산 정보 포맷
            asset_text = self._format_asset_details(account_info, position_info)
            
            # 누적 성과 포맷
            cumulative_text = self._format_cumulative_performance(
                cumulative_profit, cumulative_roi
            )
            
            # 최근 수익 흐름 포맷
            recent_text = self._format_recent_performance(weekly_profit)
            
            # 멘탈 케어 - 완전히 동적 생성
            mental_text = await self._generate_dynamic_mental_care(
                account_info, position_info, today_pnl, weekly_profit,
                cumulative_profit, cumulative_roi
            )
            
            report = f"""💰 /profit 명령어 – 포지션 및 손익 정보
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📌 보유 포지션 정보
{position_text}

━━━━━━━━━━━━━━━━━━━

💸 손익 정보
{pnl_text}

━━━━━━━━━━━━━━━━━━━

💼 자산 정보
{asset_text}

━━━━━━━━━━━━━━━━━━━

📊 누적 성과
{cumulative_text}

━━━━━━━━━━━━━━━━━━━

📈 최근 수익 흐름
{recent_text}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"수익 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return "❌ 수익 현황 조회 중 오류가 발생했습니다."
    
    def _format_position_details(self, position_info: dict, change_24h: float) -> str:
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
            distance_text = f"{abs(distance):.1f}% {direction} 시 청산"
        
        # 포지션 크기 (BTC)
        size = position_info.get('size', 0)
        
        # 실제 투입 금액 계산
        # marginSize는 레버리지가 적용된 전체 포지션 가치
        # 실제 투입 금액 = marginSize / leverage
        margin = position_info.get('margin', 0)
        leverage = position_info.get('leverage', 1)
        actual_investment = margin / leverage if leverage > 0 else margin
        
        lines = [
            f"• 종목: {position_info.get('symbol', 'BTCUSDT')}",
            f"• 방향: {side}",
            f"• 진입가: ${position_info.get('entry_price', 0):,.2f}",
            f"• 현재가: {self._format_price_with_change(current_price, change_24h)}",
            f"• 포지션 크기: {size:.4f} BTC",
            f"• 실제 투입 금액: ${actual_investment:.2f} (약 {actual_investment * 1350 / 10000:.1f}만원)",
            f"• 청산가: ${liquidation_price:,.2f}" if liquidation_price > 0 else "• 청산가: 조회불가",
            f"• 청산까지 거리: {distance_text}"
        ]
        
        return '\n'.join(lines)
    
    def _format_pnl_details(self, account_info: dict, position_info: dict, 
                          today_pnl: float, total_equity: float) -> str:
        """손익 정보 포맷팅"""
        unrealized_pnl = account_info.get('unrealized_pnl', 0)
        
        # 포지션별 미실현손익이 더 정확할 수 있음
        if position_info and position_info.get('has_position'):
            position_unrealized = position_info.get('unrealized_pnl', 0)
            if abs(position_unrealized) > abs(unrealized_pnl):
                unrealized_pnl = position_unrealized
        
        # 금일 총 수익
        total_today = today_pnl + unrealized_pnl
        
        # 금일 수익률 (총 자산 대비)
        daily_roi = (total_today / total_equity * 100) if total_equity > 0 else 0
        
        lines = [
            f"• 미실현 손익: {self._format_currency(unrealized_pnl)}",
            f"• 오늘 실현 손익: {self._format_currency(today_pnl)}",
            f"• 금일 총 수익: {self._format_currency(total_today)}",
            f"• 금일 수익률: {daily_roi:+.2f}%"
        ]
        
        return '\n'.join(lines)
    
    def _format_asset_details(self, account_info: dict, position_info: dict) -> str:
        """자산 정보 포맷팅"""
        total_equity = account_info.get('total_equity', 0)
        available = account_info.get('available', 0)
        
        lines = [
            f"• 총 자산: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)",
            f"• 가용 자산: ${available:,.2f} (약 {available * 1350 / 10000:.1f}만원)"
        ]
        
        # 포지션 증거금 항목 제거 (실제 투입 금액과 중복)
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance(self, cumulative_profit: float, 
                                     cumulative_roi: float) -> str:
        """누적 성과 포맷팅"""
        return f"""• 전체 누적 수익: {self._format_currency(cumulative_profit)}
- 전체 누적 수익률: {cumulative_roi:+.2f}%"""
    
    def _format_recent_performance(self, weekly_profit: dict) -> str:
        """최근 수익 흐름 포맷팅"""
        return f"""• 최근 7일 수익: {self._format_currency(weekly_profit['total'])}
- 최근 7일 평균: {self._format_currency(weekly_profit['average'])}/일"""
    
    async def _generate_dynamic_mental_care(self, account_info: dict, 
                                          position_info: dict, today_pnl: float, 
                                          weekly_profit: dict, cumulative_profit: float,
                                          cumulative_roi: float) -> str:
        """완전히 동적인 멘탈 케어 생성"""
        if not self.openai_client:
            return "시장은 예측 불가능하지만, 준비된 마음은 기회를 놓치지 않습니다. 오늘도 차분하게 접근하세요. 📊"
        
        try:
            # 상황 분석
            total_equity = account_info.get('total_equity', 0)
            unrealized_pnl = account_info.get('unrealized_pnl', 0)
            has_position = position_info.get('has_position', False)
            position_side = position_info.get('side', '')
            
            # 실제 투입 금액 계산
            actual_investment = 0
            if has_position:
                margin = position_info.get('margin', 0)
                leverage = position_info.get('leverage', 1)
                actual_investment = margin / leverage if leverage > 0 else margin
            
            # 전체 상황 요약
            situation_summary = f"""
현재 트레이더 상황:
- 총 자산: ${total_equity:,.0f}
- 누적 수익: ${cumulative_profit:,.0f} (수익률 {cumulative_roi:+.1f}%)
- 오늘 실현손익: ${today_pnl:+,.0f}
- 미실현손익: ${unrealized_pnl:+,.0f}
- 최근 7일 수익: ${weekly_profit['total']:+,.0f} (일평균 ${weekly_profit['average']:+,.0f})
- 포지션: {'있음 (' + position_side + ', 실제 투입 $' + f"{actual_investment:.2f}" + ')' if has_position else '없음'}
"""
            
            prompt = f"""당신은 전문 트레이딩 심리 코치입니다. 
다음 트레이더의 상황을 분석하고, 맞춤형 멘탈 케어 메시지를 작성하세요.

{situation_summary}

요구사항:
1. 구체적인 숫자를 언급하며 개인화된 메시지
2. 현재 상황에 맞는 실질적 조언
3. 과도한 낙관이나 비관 지양
4. 2-3문장으로 간결하게
5. 따뜻하지만 전문적인 톤
6. 이모티콘 1개 포함
7. 매번 완전히 다른 표현과 관점 사용

절대 사용하지 말아야 할 표현:
- "꾸준한", "차분한", "시장은 예측 불가능"
- 일반적이고 뻔한 조언
- 이전에 사용했던 패턴의 반복"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 개인화된 조언을 제공하는 트레이딩 심리 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.9  # 다양성 증가
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            # 폴백: 상황별 간단한 메시지
            if cumulative_roi > 50:
                return f"${int(cumulative_profit)}의 수익, 인상적인 성과입니다. 리스크 관리를 잊지 마세요. 🎯"
            elif today_pnl > 0:
                return f"오늘 ${int(today_pnl)} 수익, 좋은 하루였네요. 내일도 기회는 있습니다. 📈"
            else:
                return f"총 자산 ${int(total_equity)}을 유지하고 계십니다. 시장은 인내심을 보상합니다. 💪"
