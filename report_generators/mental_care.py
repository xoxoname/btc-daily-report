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
        total_equity = account_info.get('accountEquity', 0)
        if isinstance(total_equity, str):
            total_equity = float(total_equity)
        
        unrealized_pnl = account_info.get('unrealizedPL', 0)
        if isinstance(unrealized_pnl, str):
            unrealized_pnl = float(unrealized_pnl)
            
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
        
        # 상황별 구체적인 가이드
        situation_guide = {
            "큰 수익": "과욕을 경계하고 리스크 관리의 중요성을 강조하세요",
            "안정적 수익": "꾸준함의 가치를 인정하고 현재 전략을 유지하도록 격려하세요",
            "손익분기": "인내심의 중요성과 기회를 기다리는 지혜를 전달하세요",
            "소폭 손실": "손실은 학습의 기회임을 상기시키고 감정적 대응을 경계하세요",
            "큰 손실": "희망을 잃지 않도록 격려하되 손절의 중요성도 언급하세요"
        }
        
        guide = situation_guide.get(situation, "균형잡힌 조언을 제공하세요")
        
        prompt = f"""
트레이더의 현재 상황:
- 총 자산: ${total_equity:,.0f}
- 오늘 실현손익: ${today_pnl:+,.0f}  
- 미실현손익: ${unrealized_pnl:+,.0f}
- 최근 7일 수익: ${weekly_total:+,.0f}
- 포지션 보유: {'있음' if has_position else '없음'}
- 상황: {situation}

이 트레이더에게 적합한 멘탈 케어 메시지를 작성해주세요.

조건:
1. 구체적인 금액 언급하여 현실감 있게
2. 따뜻하고 격려하는 톤
3. 2-3문장으로 간결하게
4. 반드시 이모티콘 1개 포함 (마지막에)
5. {guide}
6. 친근한 반말 사용 (예: ~했네요, ~하세요)
7. 따옴표나 특수문자 사용 금지
8. 완전한 문장으로만 구성

예시:
- 오늘 200달러 수익을 냈네요! 꾸준한 수익이 복리의 힘을 만듭니다. 욕심내지 말고 현재 페이스를 유지하세요 💪
- 지금 150달러 손실이 있지만 너무 걱정하지 마세요. 지난주 900달러 수익을 생각하면 일시적인 조정일 뿐입니다 🌱
"""
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 따뜻하고 현실적인 트레이딩 멘토입니다. 구체적인 숫자와 함께 실질적인 조언을 제공하세요. 따옴표는 절대 사용하지 마세요."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.8
        )
        
        message = response.choices[0].message.content.strip()
        
        # 메시지 정리
        message = self._clean_gpt_message(message)
        
        # 이모티콘 확인 및 추가
        emoji_list = ['🎯', '💪', '🚀', '✨', '🌟', '😊', '👍', '🔥', '💎', '🏆']
        has_emoji = any(emoji in message for emoji in emoji_list)
        
        if not has_emoji:
            message += f" {random.choice(emoji_list)}"
        
        return message
    
    def _clean_gpt_message(self, message: str) -> str:
        """GPT 메시지 정리"""
        try:
            # 따옴표 제거
            message = message.replace('"', '').replace("'", '').replace('`', '')
            
            # 금지 표현 제거
            forbidden_phrases = ["반갑습니다", "Bitget에서의", "화이팅하세요", "화이팅", "안녕하세요", "레버리지"]
            for phrase in forbidden_phrases:
                message = message.replace(phrase, "")
            
            # 연속 공백 정리
            message = ' '.join(message.split())
            
            # 문장이 완전히 끝나지 않은 경우 처리
            if message and not message.endswith(('.', '!', '?', ')', '💪', '🎯', '🚀', '✨', '🌟', '😊', '👍', '🔥', '💎', '🏆')):
                # 마지막 완전한 문장까지만 사용
                sentences = message.split('.')
                if len(sentences) > 1:
                    complete_sentences = sentences[:-1]
                    message = '.'.join(complete_sentences) + '.'
                else:
                    # 불완전한 문장인 경우 기본 메시지로 대체
                    return self._get_fallback_message()
            
            # 시작 부분의 불필요한 문자 제거
            message = message.lstrip('!"\'`')
            
            return message.strip()
            
        except Exception as e:
            self.logger.error(f"GPT 메시지 정리 실패: {e}")
            return self._get_fallback_message()
    
    def _get_fallback_message(self) -> str:
        """폴백 메시지"""
        messages = [
            "꾸준한 투자가 성공의 열쇠입니다. 감정에 휘둘리지 말고 계획을 따르세요 🎯",
            "시장은 예측할 수 없지만 준비된 투자자에게는 기회가 됩니다. 차분하게 대응하세요 💪",
            "단기적인 변동에 일희일비하지 마세요. 장기적인 관점을 유지하는 것이 중요합니다 🌟"
        ]
        return random.choice(messages)
    
    def _generate_pattern_mental_care(self, total_equity: float, today_pnl: float,
                                    unrealized_pnl: float, weekly_total: float,
                                    weekly_avg: float, has_position: bool) -> str:
        """패턴 기반 다양한 멘탈 케어"""
        
        # 상황 분류
        situation = self._analyze_trading_situation(today_pnl, unrealized_pnl, weekly_total)
        
        # 패턴별 메시지 템플릿
        if situation == "큰 수익":
            return self._big_win_messages(today_pnl, total_equity, weekly_total)
        elif situation == "안정적 수익":
            return self._steady_profit_messages(today_pnl, weekly_avg, total_equity)
        elif situation == "소폭 손실":
            return self._small_loss_messages(unrealized_pnl, weekly_total)
        elif situation == "큰 손실":
            return self._big_loss_messages(unrealized_pnl, total_equity)
        elif situation == "손익분기":
            return self._break_even_messages(total_equity, weekly_total)
        else:
            return self._general_messages(total_equity, weekly_total)
    
    def _analyze_trading_situation(self, today_pnl: float, unrealized_pnl: float, 
                                 weekly_total: float) -> str:
        """거래 상황 분석"""
        total_today = today_pnl + unrealized_pnl
        
        if total_today > 200:
            return "큰 수익"
        elif total_today > 50:
            return "안정적 수익"
        elif -50 <= total_today <= 50:
            return "손익분기"
        elif -100 <= total_today < -50:
            return "소폭 손실"
        else:
            return "큰 손실"
    
    def _big_win_messages(self, today_pnl: float, total_equity: float, weekly_total: float) -> str:
        """큰 수익 시 메시지"""
        patterns = [
            f'오늘 {today_pnl:.0f}달러 벌었네요! 대단합니다! 하지만 시장은 항상 겸손해야 한다는 것을 기억하세요. 수익을 지키는 것이 버는 것보다 중요합니다 🎯',
            f'와! {today_pnl:.0f}달러 수익이라니 정말 잘했어요! 이제 총 자산이 {total_equity:,.0f}달러가 되었네요. 하지만 과욕은 금물, 리스크 관리를 잊지 마세요 💪',
            f'{today_pnl:.0f}달러 수익 축하해요! 편의점 알바 {int(today_pnl/15):.0f}시간 번 셈이네요. 이 기세를 유지하되 신중함도 함께 가져가세요 🚀',
            f'오늘의 {today_pnl:.0f}달러는 당신의 실력입니다. 7일간 {weekly_total:.0f}달러 벌었다는 건 운이 아니에요. 계속 시스템을 믿고 따르세요 ⭐'
        ]
        return random.choice(patterns)
    
    def _steady_profit_messages(self, today_pnl: float, weekly_avg: float, total_equity: float) -> str:
        """꾸준한 수익 시 메시지"""
        patterns = [
            f'오늘도 {today_pnl:.0f}달러 수익, 정말 꾸준하네요! 일주일 평균 {weekly_avg:.0f}달러씩이면 월 {weekly_avg*30:.0f}달러 예상이에요. 복리의 마법이 시작됐네요 📈',
            f'{today_pnl:.0f}달러 벌었군요! 작아 보여도 이런 꾸준함이 {total_equity:,.0f}달러를 만들었어요. 천천히 그러나 확실하게 가는 거예요 🌱',
            f'하루 {today_pnl:.0f}달러, 훌륭해요! 커피값이라도 매일 벌면 한 달이면 {today_pnl*30:.0f}달러에요. 이 페이스 유지하세요 🎯',
            f'오늘도 {today_pnl:.0f}달러 플러스! 급하게 큰 돈 벌려고 하지 마세요. 지금처럼만 하면 충분해요. 꾸준함이 최고의 전략입니다 ✨'
        ]
        return random.choice(patterns)
    
    def _small_loss_messages(self, unrealized_pnl: float, weekly_total: float) -> str:
        """소폭 손실 시 메시지"""
        patterns = [
            f'지금 {abs(unrealized_pnl):.0f}달러 마이너스지만 괜찮아요. 최근 7일간 {weekly_total:.0f}달러 벌었잖아요. 일시적인 조정일 뿐이에요. 차분하게 대응하세요 🧘‍♂️',
            f'{abs(unrealized_pnl):.0f}달러 손실이 있네요. 하지만 손실도 트레이딩의 일부예요. 중요한 건 감정적으로 대응하지 않는 거예요. 계획을 따르세요 💪',
            f'마이너스 {abs(unrealized_pnl):.0f}달러지만 너무 신경 쓰지 마세요. 지난주 {weekly_total:.0f}달러 수익을 보세요. 당신은 할 수 있어요. 이번 경험에서 배우세요 🌱',
            f'{abs(unrealized_pnl):.0f}달러 손실 중이네요. 모든 트레이더가 겪는 일이에요. 손실을 최소화하고 다음 기회를 준비하는 게 프로의 자세입니다 🎯'
        ]
        return random.choice(patterns)
    
    def _big_loss_messages(self, unrealized_pnl: float, total_equity: float) -> str:
        """큰 손실 시 메시지"""
        patterns = [
            f'{abs(unrealized_pnl):.0f}달러 손실이 크긴 하네요. 하지만 아직 {total_equity:,.0f}달러가 있어요. 지금은 멈추고 다시 계획을 세울 때예요. 감정적 거래는 금물입니다 🛡️',
            f'{abs(unrealized_pnl):.0f}달러 손실... 힘들겠지만 이것도 성장의 과정이에요. 지금 중요한 건 더 큰 손실을 막는 거예요. 잠시 쉬어가도 괜찮아요 🤝',
            f'{abs(unrealized_pnl):.0f}달러 마이너스는 아프지만 끝이 아니에요. 총 자산의 {abs(unrealized_pnl)/total_equity*100:.0f}%일 뿐이에요. 손절의 용기를 가지세요 💪',
            f'지금 {abs(unrealized_pnl):.0f}달러 손실이지만 포기하지 마세요. 시장은 항상 기회를 줍니다. 하지만 먼저 감정을 추스르고 냉정해지세요 🎯'
        ]
        return random.choice(patterns)
    
    def _break_even_messages(self, total_equity: float, weekly_total: float) -> str:
        """손익 균형 시 메시지"""
        patterns = [
            f'오늘은 큰 변화가 없네요. 때로는 기다리는 것도 실력이에요. {total_equity:,.0f}달러를 지킨 것만으로도 잘한 거예요. 기회는 곧 옵니다 ⚖️',
            f'손익 제로, 나쁘지 않아요! 잃지 않은 것도 이긴 거예요. 최근 7일 {weekly_total:.0f}달러 수익도 있고요. 인내심을 가지세요 🎯',
            f'오늘은 평온한 날이네요. 매일 수익을 낼 필요는 없어요. 지금처럼 차분히 기회를 기다리는 것도 전략입니다 📊',
            f'변동이 없는 날도 있죠. 거래하지 않는 것이 최고의 거래일 때도 있어요. 자산 {total_equity:,.0f}달러를 잘 지키고 있네요 ✨'
        ]
        return random.choice(patterns)
    
    def _general_messages(self, total_equity: float, weekly_total: float) -> str:
        """일반적인 메시지"""
        patterns = [
            f'현재 자산 {total_equity:,.0f}달러, 잘 관리하고 있네요. 트레이딩은 마라톤이에요. 꾸준히 가는 게 중요합니다. 화이팅 📈',
            f'최근 7일간 {weekly_total:.0f}달러 수익, 나쁘지 않아요! 감정보다는 전략을 믿고 따르세요. 그게 성공의 비결이에요 💪',
            f'자산 {total_equity:,.0f}달러를 운용 중이시네요. 매일의 작은 결정이 큰 결과를 만들어요. 오늘도 현명한 선택을 하세요 🌟',
            f'일희일비하지 마세요. 중요한 건 꾸준한 성장이에요. 지금까지 잘해왔듯이 앞으로도 할 수 있어요 🚀'
        ]
        return random.choice(patterns)
    
    def generate_general_mental_care(self, signal: str = "중립") -> str:
        """일반적인 멘탈 케어 메시지"""
        general_messages = [
            '시장은 예측할 수 없지만, 준비된 사람에게는 기회가 옵니다. 오늘도 차분하게 시작하세요 📊',
            '성공의 비결은 감정 조절이에요. 탐욕과 공포를 다스리고 계획을 따르세요 🧘‍♂️',
            '작은 수익이 모여 큰 부를 만들어요. 조급해하지 말고 천천히 쌓아가세요 🌱',
            '손실도 배움의 기회예요. 실패에서 교훈을 얻고 더 나은 트레이더가 되세요 💪',
            '변동성은 기회이자 위험이에요. 리스크 관리를 잊지 말고 현명하게 대응하세요 ⚖️'
        ]
        return random.choice(general_messages)
