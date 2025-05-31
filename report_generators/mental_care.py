# report_generators/mental_care.py
import random
from typing import Dict, Optional
import logging

class MentalCareGenerator:
    """멘탈 케어 메시지 전담 생성기"""
    
    def __init__(self, openai_client=None):
        self.openai_client = openai_client
        self.logger = logging.getLogger(__name__)
    
    async def generate_profit_mental_care(self, account_info: Dict, position_info: Dict, 
                                        today_pnl: float, weekly_profit: Dict) -> str:
        """수익 상황 기반 멘탈 케어"""
        
        # 상황 분석
        total_equity = account_info.get('total_equity', 0)
        unrealized_pnl = account_info.get('unrealized_pnl', 0)
        weekly_total = weekly_profit.get('total', 0)
        weekly_avg = weekly_profit.get('average', 0)
        has_position = position_info.get('has_position', False)
        
        # GPT 사용 가능하면 개인화된 메시지
        if self.openai_client:
            try:
                return await self._generate_gpt_mental_care(
                    total_equity, today_pnl, unrealized_pnl, weekly_total, has_position
                )
            except Exception as e:
                self.logger.warning(f"GPT 멘탈 케어 생성 실패: {e}")
        
        # 폴백: 다양한 패턴의 멘탈 케어
        return self._generate_pattern_mental_care(
            total_equity, today_pnl, unrealized_pnl, weekly_total, weekly_avg, has_position
        )
    
    async def _generate_gpt_mental_care(self, total_equity: float, today_pnl: float, 
                                      unrealized_pnl: float, weekly_total: float, 
                                      has_position: bool) -> str:
        """GPT 기반 개인화 멘탈 케어"""
        
        # 상황별 프롬프트 생성
        situation = self._analyze_trading_situation(today_pnl, unrealized_pnl, weekly_total)
        
        prompt = f"""
트레이더 현재 상황:
- 총 자산: ${total_equity:,.0f}
- 오늘 실현손익: ${today_pnl:+,.0f}  
- 미실현손익: ${unrealized_pnl:+,.0f}
- 최근 7일 수익: ${weekly_total:+,.0f}
- 포지션 보유: {'있음' if has_position else '없음'}
- 상황 평가: {situation}

이 트레이더에게 적합한 멘탈 케어 메시지를 작성해주세요.
조건:
- 구체적인 수익 금액과 자산을 언급
- 따뜻하고 격려하는 톤
- 2-3문장, 한국어
- 반드시 이모티콘 1개 포함 (마지막에)
- "오늘 ~을 벌었군요!" 같은 자연스러운 표현 사용
- 친근하면서도 전문적인 조언
"""
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 따뜻하고 현실적인 트레이딩 멘토입니다. 친근하면서도 전문적인 조언을 제공하세요."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=350,
            temperature=0.8
        )
        
        message = response.choices[0].message.content.strip()
        
        # 이모티콘 확인 및 추가
        emoji_list = ['🎯', '💪', '🚀', '✨', '🌟', '😊', '👍', '🔥', '💎', '🏆']
        has_emoji = any(emoji in message for emoji in emoji_list)
        
        if not has_emoji:
            message += f" {random.choice(emoji_list)}"
        
        return f'"{message}"'
    
    def _generate_pattern_mental_care(self, total_equity: float, today_pnl: float,
                                    unrealized_pnl: float, weekly_total: float,
                                    weekly_avg: float, has_position: bool) -> str:
        """패턴 기반 다양한 멘탈 케어"""
        
        # 상황 분류
        situation = self._analyze_trading_situation(today_pnl, unrealized_pnl, weekly_total)
        
        # 패턴별 메시지 템플릿
        if situation == "big_win":
            return self._big_win_messages(today_pnl, total_equity, weekly_total)
        elif situation == "steady_profit":
            return self._steady_profit_messages(today_pnl, weekly_avg, total_equity)
        elif situation == "small_loss":
            return self._small_loss_messages(unrealized_pnl, weekly_total)
        elif situation == "big_loss":
            return self._big_loss_messages(unrealized_pnl, total_equity)
        elif situation == "break_even":
            return self._break_even_messages(total_equity, weekly_total)
        else:
            return self._general_messages(total_equity, weekly_total)
    
    def _analyze_trading_situation(self, today_pnl: float, unrealized_pnl: float, 
                                 weekly_total: float) -> str:
        """거래 상황 분석"""
        total_today = today_pnl + unrealized_pnl
        
        if total_today > 200:
            return "big_win"
        elif total_today > 50:
            return "steady_profit"
        elif -50 <= total_today <= 50:
            return "break_even"
        elif -100 <= total_today < -50:
            return "small_loss"
        else:
            return "big_loss"
    
    def _big_win_messages(self, today_pnl: float, total_equity: float, weekly_total: float) -> str:
        """큰 수익 시 메시지"""
        patterns = [
            f'"오늘 ${today_pnl:.0f}을 벌어들였군요! 현재 자산 ${total_equity:,.0f}은 당신의 실력을 보여줍니다. 하지만 시장은 변덕스러우니 겸손함을 잊지 마세요. 🎯"',
            f'"와! 하루에 ${today_pnl:.0f} 수익이라니 대단해요! 최근 7일간 ${weekly_total:.0f}을 벌었다는 것은 일관된 전략의 결과겠죠. 이 기세를 유지하되 과욕은 금물입니다. 💪"',
            f'"${today_pnl:.0f} 수익 축하드려요! 편의점 알바 {int(today_pnl/15):.0f}시간치 벌었네요. 현재 총 자산 ${total_equity:,.0f}을 잘 관리하며 다음 기회를 준비하세요. 🚀"',
            f'"오늘의 ${today_pnl:.0f} 달러는 단순한 숫자가 아닙니다. 시장을 읽고 결정한 결과죠. 총 자산 ${total_equity:,.0f} 달러를 더 키우되, 리스크 관리는 필수입니다. ⭐"'
        ]
        return random.choice(patterns)
    
    def _steady_profit_messages(self, today_pnl: float, weekly_avg: float, total_equity: float) -> str:
        """꾸준한 수익 시 메시지"""
        patterns = [
            f'"오늘 ${today_pnl:.0f} 수익, 꾸준하네요! 일주일 평균 ${weekly_avg:.0f}/일을 유지하고 있어 인상적입니다. 이런 안정적인 수익이야말로 진정한 실력이죠. 📈"',
            f'"${today_pnl:.0f} 벌었군요! 큰 돈은 아니어도 꾸준함이 복리의 힘을 만듭니다. 현재 자산 ${total_equity:,.0f}을 바탕으로 차근차근 늘려가세요. 🌱"',
            f'"하루 ${today_pnl:.0f} 달러, 작지만 확실한 수익이에요. 이런 꾸준함이 장기적으로 큰 차이를 만들어냅니다. 현재 페이스를 유지하세요! 🎯"',
            f'"오늘도 ${today_pnl:.0f} 수익! 매일 이 정도씩만 벌어도 한 달이면 상당한 금액이 됩니다. 안정적인 전략을 계속 이어가세요. ✨"'
        ]
        return random.choice(patterns)
    
    def _small_loss_messages(self, unrealized_pnl: float, weekly_total: float) -> str:
        """소폭 손실 시 메시지"""
        patterns = [
            f'"현재 ${abs(unrealized_pnl):.0f} 마이너스 상태네요. 하지만 최근 7일간 ${weekly_total:.0f}을 벌었으니 일시적인 조정일 수 있어요. 손절 기준을 명확히 하고 차분하게 대응하세요. 🧘‍♂️"',
            f'"${abs(unrealized_pnl):.0f} 손실이 있지만 크게 걱정하지 마세요. 트레이딩에서 손실은 당연한 부분입니다. 감정적 판단보다는 계획된 전략을 따르세요. 💪"',
            f'"마이너스 ${abs(unrealized_pnl):.0f}지만 패닉할 필요 없어요. 지난 주 수익 ${weekly_total:.0f}을 보면 당신의 실력은 검증되었습니다. 이번 손실에서 배우고 성장하세요. 🌱"',
            f'"현재 ${abs(unrealized_pnl):.0f} 손실 상태군요. 모든 트레이더가 겪는 과정입니다. 중요한 건 손실을 제한하고 다음 기회를 기다리는 것이에요. 🎯"'
        ]
        return random.choice(patterns)
    
    def _big_loss_messages(self, unrealized_pnl: float, total_equity: float) -> str:
        """큰 손실 시 메시지"""
        patterns = [
            f'"${abs(unrealized_pnl):.0f} 손실이 크네요. 하지만 총 자산 ${total_equity:,.0f}이 있으니 회복할 수 있습니다. 지금은 포지션 정리를 고려하고 감정적 거래는 피하세요. 🛡️"',
            f'"큰 손실 ${abs(unrealized_pnl):.0f}달러... 힘들겠지만 이런 경험이 더 나은 트레이더로 만들어 줍니다. 잠시 쉬어가며 전략을 재정비하는 시간을 가져보세요. 🤝"',
            f'"${abs(unrealized_pnl):.0f} 손실은 아프지만 끝이 아닙니다. 자산의 일부일 뿐이에요. 손절의 용기와 다음 기회를 위한 준비가 더 중요합니다. 💪"',
            f'"지금 ${abs(unrealized_pnl):.0f} 마이너스 상황이지만, 시장은 항상 새로운 기회를 줍니다. 총 자산 ${total_equity:,.0f}을 지키며 현명한 결정을 내리세요. 🎯"'
        ]
        return random.choice(patterns)
    
    def _break_even_messages(self, total_equity: float, weekly_total: float) -> str:
        """손익 균형 시 메시지"""
        patterns = [
            f'"오늘은 손익이 거의 비슷하네요. 때로는 기다리는 것도 전략입니다. 총 자산 ${total_equity:,.0f}을 유지하며 다음 기회를 노려보세요. ⚖️"',
            f'"큰 움직임 없는 하루였네요. 하지만 최근 7일 ${weekly_total:.0f} 수익을 보면 당신의 실력은 확실합니다. 인내심을 갖고 기다려보세요. 🎯"',
            f'"손익 제로, 나쁘지 않아요! 손실 없이 시장을 경험한 것만으로도 가치가 있습니다. 차분히 다음 기회를 준비하세요. 📊"',
            f'"오늘은 평온한 하루였군요. 때로는 거래하지 않는 것이 최선의 거래입니다. 자산 ${total_equity:,.0f}을 지키는 것도 실력이에요. ✨"'
        ]
        return random.choice(patterns)
    
    def _general_messages(self, total_equity: float, weekly_total: float) -> str:
        """일반적인 메시지"""
        patterns = [
            f'"현재 총 자산 ${total_equity:,.0f}, 꾸준히 관리하고 계시는군요. 시장의 변동성을 염두에 두며 신중한 접근을 계속하세요. 📈"',
            f'"최근 7일간 ${weekly_total:.0f} 수익, 나쁘지 않은 성과입니다. 감정적 거래보다는 전략적 접근을 유지하며 꾸준히 성장하세요. 💪"',
            f'"트레이딩은 마라톤과 같습니다. 현재 자산 ${total_equity:,.0f}을 바탕으로 장기적 관점에서 접근하시길 바랍니다. 🏃‍♂️"',
            f'"매일의 등락에 일희일비하지 마세요. 중요한 건 꾸준한 학습과 발전입니다. 현재까지의 성과를 바탕으로 계속 전진하세요! 🌟"'
        ]
        return random.choice(patterns)
    
    def generate_general_mental_care(self, signal: str = "중립") -> str:
        """일반적인 멘탈 케어 메시지"""
        general_messages = [
            '"시장은 예측 불가능하지만, 준비된 마음은 기회를 놓치지 않습니다. 오늘도 차분하게 접근하세요. 📊"',
            '"성공적인 트레이딩의 비결은 감정 조절입니다. 탐욕과 공포를 다스리며 전략을 따르세요. 🧘‍♂️"',
            '"매일의 작은 수익이 큰 부를 만듭니다. 조급해하지 말고 꾸준히 쌓아가세요. 🌱"',
            '"손실도 배움의 일부입니다. 실패에서 교훈을 얻고 더 나은 트레이더가 되어가세요. 💪"',
            '"시장의 변동성은 기회이자 위험입니다. 리스크 관리를 잊지 말고 현명하게 대응하세요. ⚖️"'
        ]
        return random.choice(general_messages)
