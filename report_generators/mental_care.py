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
        """수익 상황 기반 멘탈 케어 - 개선된 GPT 프롬프트"""
        
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
                return await self._generate_enhanced_gpt_mental_care(
                    total_equity, today_pnl, unrealized_pnl, weekly_total, weekly_avg, has_position
                )
            except Exception as e:
                self.logger.warning(f"GPT 멘탈 케어 생성 실패: {e}")
        
        # 폴백: 다양한 패턴의 멘탈 케어
        return self._generate_pattern_mental_care(
            total_equity, today_pnl, unrealized_pnl, weekly_total, weekly_avg, has_position
        )
    
    async def _generate_enhanced_gpt_mental_care(self, total_equity: float, today_pnl: float, 
                                               unrealized_pnl: float, weekly_total: float, 
                                               weekly_avg: float, has_position: bool) -> str:
        """향상된 GPT 기반 개인화 멘탈 케어 - 더 상세하고 개인적인 조언"""
        
        # 더 정교한 상황 분석
        situation_analysis = self._detailed_situation_analysis(
            today_pnl, unrealized_pnl, weekly_total, weekly_avg, total_equity
        )
        
        # 트레이딩 성과 계산
        today_total = today_pnl + unrealized_pnl
        monthly_projection = weekly_avg * 30
        roi_today = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        # 위험도 평가
        risk_level = self._assess_risk_level(unrealized_pnl, total_equity, has_position)
        
        # 성과 등급
        performance_grade = self._get_performance_grade(weekly_total, today_total)
        
        # 상황별 멘토링 전략
        mentoring_strategy = self._get_mentoring_strategy(situation_analysis, risk_level, performance_grade)
        
        prompt = f"""
당신은 경험 많은 트레이딩 멘토입니다. 다음 트레이더의 실제 상황을 분석하여 개인화된 멘탈 케어를 제공해주세요.

📊 트레이더 현황:
• 총 자산: ${total_equity:,.0f} (한화 약 {int(total_equity * 1350 / 10000)}만원)
• 오늘 실현손익: ${today_pnl:+,.0f}
• 오늘 미실현손익: ${unrealized_pnl:+,.0f}
• 오늘 총 손익: ${today_total:+,.0f} ({roi_today:+.1f}%)
• 최근 7일 누적: ${weekly_total:+,.0f}
• 일평균 수익: ${weekly_avg:+,.0f}
• 월 예상 수익: ${monthly_projection:+,.0f}
• 포지션 보유: {'있음' if has_position else '없음'}

📈 상황 분석:
• 거래 상황: {situation_analysis['situation']}
• 수익 패턴: {situation_analysis['pattern']}
• 위험도: {risk_level}
• 성과 등급: {performance_grade}

🎯 멘토링 전략: {mentoring_strategy}

다음 조건을 모두 만족하는 멘탈 케어 메시지를 작성해주세요:

1. **개인화**: 구체적인 금액과 수치를 언급하여 개인 맞춤형 조언
2. **실용성**: 현재 상황에 대한 구체적이고 실행 가능한 조언
3. **감정적 지지**: 따뜻하고 격려하는 톤으로 심리적 안정감 제공
4. **전문성**: 트레이딩 경험에 기반한 현실적이고 전문적인 조언
5. **균형감**: 과도한 낙관이나 비관 없이 균형잡힌 시각 제시

요구사항:
• 길이: 2-3문장 (50-80단어)
• 톤: 친근한 반말체 (예: ~네요, ~세요)
• 마지막에 적절한 이모티콘 1개 포함
• 구체적 수치 언급 (금액, 퍼센트 등)
• 향후 행동 가이드 포함
• 하드코딩된 표현 금지
• 따옴표나 특수문자 사용 금지

예시 스타일:
"오늘 {today_pnl}달러 수익으로 이번 주 총 {weekly_total}달러를 벌었네요! 현재 {total_equity}달러 자산 규모에서 안정적인 성장세를 보이고 있어요. 이 페이스라면 월 {monthly_projection}달러도 가능하니 욕심내지 말고 꾸준히 가세요 💪"

실제 상황에 맞는 멘탈 케어를 제공해주세요.
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 전문적이고 따뜻한 트레이딩 멘토입니다. 구체적인 수치와 개인화된 조언으로 트레이더의 심리적 안정과 성장을 돕습니다. 따옴표는 절대 사용하지 마세요."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.8,
                presence_penalty=0.6,  # 더 창의적이고 개인화된 응답
                frequency_penalty=0.3   # 반복 표현 방지
            )
            
            message = response.choices[0].message.content.strip()
            
            # 메시지 정리 및 검증
            cleaned_message = self._clean_and_validate_gpt_message(message)
            
            # 추가 검증: 구체적 수치 포함 여부 확인
            if not self._contains_specific_numbers(cleaned_message):
                self.logger.warning("GPT 응답에 구체적 수치가 없음, 패턴 기반으로 대체")
                return self._generate_pattern_mental_care(
                    total_equity, today_pnl, unrealized_pnl, weekly_total, weekly_avg, has_position
                )
            
            return cleaned_message
            
        except Exception as e:
            self.logger.error(f"향상된 GPT 멘탈 케어 생성 실패: {e}")
            return self._generate_pattern_mental_care(
                total_equity, today_pnl, unrealized_pnl, weekly_total, weekly_avg, has_position
            )
    
    def _detailed_situation_analysis(self, today_pnl: float, unrealized_pnl: float, 
                                   weekly_total: float, weekly_avg: float, total_equity: float) -> Dict:
        """상세한 상황 분석"""
        today_total = today_pnl + unrealized_pnl
        
        # 거래 상황 분류
        if today_total > 200:
            situation = "대폭 수익"
        elif today_total > 50:
            situation = "안정적 수익" 
        elif -50 <= today_total <= 50:
            situation = "손익분기"
        elif -150 <= today_total < -50:
            situation = "소폭 손실"
        else:
            situation = "큰 손실"
        
        # 수익 패턴 분석
        if weekly_avg > 20:
            pattern = "고수익 트레이더"
        elif weekly_avg > 10:
            pattern = "꾸준한 수익"
        elif weekly_avg > 0:
            pattern = "소폭 플러스"
        elif weekly_avg > -10:
            pattern = "등락 반복"
        else:
            pattern = "수익 개선 필요"
        
        return {
            'situation': situation,
            'pattern': pattern,
            'consistency': abs(weekly_total / 7) if weekly_total != 0 else 0
        }
    
    def _assess_risk_level(self, unrealized_pnl: float, total_equity: float, has_position: bool) -> str:
        """위험도 평가"""
        if not has_position:
            return "안전 (무포지션)"
        
        risk_ratio = abs(unrealized_pnl) / total_equity if total_equity > 0 else 0
        
        if risk_ratio < 0.02:
            return "낮음 (2% 이하)"
        elif risk_ratio < 0.05:
            return "보통 (2-5%)"
        elif risk_ratio < 0.10:
            return "높음 (5-10%)"
        else:
            return "매우 높음 (10% 초과)"
    
    def _get_performance_grade(self, weekly_total: float, today_total: float) -> str:
        """성과 등급 평가"""
        weekly_score = 0
        today_score = 0
        
        # 주간 점수
        if weekly_total > 500:
            weekly_score = 5
        elif weekly_total > 200:
            weekly_score = 4
        elif weekly_total > 50:
            weekly_score = 3
        elif weekly_total > 0:
            weekly_score = 2
        else:
            weekly_score = 1
        
        # 오늘 점수
        if today_total > 100:
            today_score = 5
        elif today_total > 50:
            today_score = 4
        elif today_total > 0:
            today_score = 3
        elif today_total > -50:
            today_score = 2
        else:
            today_score = 1
        
        avg_score = (weekly_score + today_score) / 2
        
        if avg_score >= 4.5:
            return "S급 (탁월)"
        elif avg_score >= 3.5:
            return "A급 (우수)"
        elif avg_score >= 2.5:
            return "B급 (양호)"
        elif avg_score >= 1.5:
            return "C급 (보통)"
        else:
            return "D급 (개선필요)"
    
    def _get_mentoring_strategy(self, situation_analysis: Dict, risk_level: str, performance_grade: str) -> str:
        """멘토링 전략 결정"""
        situation = situation_analysis['situation']
        pattern = situation_analysis['pattern']
        
        if "대폭 수익" in situation:
            return "과욕 경계, 리스크 관리 강화"
        elif "안정적 수익" in situation:
            return "현재 전략 유지, 꾸준함 격려"
        elif "손익분기" in situation:
            return "인내심 강조, 기회 포착 준비"
        elif "소폭 손실" in situation:
            return "감정 조절, 학습 기회 활용"
        else:
            return "손절 용기, 희망 메시지 전달"
    
    def _contains_specific_numbers(self, message: str) -> bool:
        """구체적 수치 포함 여부 확인"""
        import re
        
        # 달러 금액, 퍼센트, 숫자가 포함되어 있는지 확인
        patterns = [
            r'\$\d+',          # $100, $1,234 등
            r'\d+달러',          # 100달러 등  
            r'\d+%',           # 5%, 10% 등
            r'\d+만원',         # 100만원 등
            r'\d{2,}',         # 두 자리 이상 숫자
        ]
        
        for pattern in patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def _clean_and_validate_gpt_message(self, message: str) -> str:
        """GPT 메시지 정리 및 검증 - 강화된 버전"""
        try:
            # 기본 정리
            message = message.replace('"', '').replace("'", '').replace('`', '')
            
            # 금지 표현 제거 (더 많은 패턴 추가)
            forbidden_phrases = [
                "반갑습니다", "안녕하세요", "Bitget에서의", "화이팅하세요", "화이팅", 
                "레버리지", "좋은 결과를", "성공을 기원", "행운을 빕니다",
                "트레이딩을 시작", "투자는", "재테크", "돈을 벌어", "부자가"
            ]
            
            for phrase in forbidden_phrases:
                message = message.replace(phrase, "")
            
            # 연속 공백 정리
            message = ' '.join(message.split())
            
            # 문장 완성도 검사 및 수정
            message = self._ensure_complete_sentence(message)
            
            # 이모티콘 확인 및 추가
            message = self._ensure_emoji(message)
            
            # 길이 검사
            if len(message) > 200:
                sentences = message.split('.')
                if len(sentences) > 1:
                    message = '.'.join(sentences[:2]) + '.'
                else:
                    message = message[:180] + "..."
            
            return message.strip()
            
        except Exception as e:
            self.logger.error(f"GPT 메시지 정리 실패: {e}")
            return self._get_enhanced_fallback_message()
    
    def _ensure_complete_sentence(self, message: str) -> str:
        """완전한 문장인지 확인하고 수정"""
        try:
            # 문장 종료 문자 확인
            ending_chars = ['.', '!', '?', ')', '💪', '🎯', '🚀', '✨', '🌟', '😊', '👍', '🔥', '💎', '🏆', '💰', '📈']
            
            if not any(message.endswith(char) for char in ending_chars):
                # 마지막 완전한 문장 찾기
                sentences = message.split('.')
                if len(sentences) > 1 and sentences[-2].strip():
                    # 마지막에서 두 번째 문장까지 사용
                    message = '.'.join(sentences[:-1]) + '.'
                elif message.strip():
                    # 마침표 추가
                    message = message.strip() + '.'
                else:
                    # 빈 메시지인 경우 대체
                    return self._get_enhanced_fallback_message()
            
            return message
            
        except Exception:
            return self._get_enhanced_fallback_message()
    
    def _ensure_emoji(self, message: str) -> str:
        """이모티콘 확인 및 추가"""
        emoji_list = ['💪', '🎯', '🚀', '✨', '🌟', '😊', '👍', '🔥', '💎', '🏆', '💰', '📈', '🌱', '⭐']
        
        # 이미 이모티콘이 있는지 확인
        has_emoji = any(emoji in message for emoji in emoji_list)
        
        if not has_emoji:
            # 메시지 내용에 따라 적절한 이모티콘 선택
            if any(word in message for word in ['수익', '벌었', '플러스', '성공']):
                emoji = random.choice(['💪', '🎯', '🚀', '💰', '📈'])
            elif any(word in message for word in ['손실', '마이너스', '힘들']):
                emoji = random.choice(['🌱', '✨', '🌟', '⭐'])
            elif any(word in message for word in ['꾸준', '안정', '유지']):
                emoji = random.choice(['💎', '🏆', '👍'])
            else:
                emoji = random.choice(emoji_list)
            
            message = message.rstrip('.!?') + f' {emoji}'
        
        return message
    
    def _get_enhanced_fallback_message(self) -> str:
        """향상된 폴백 메시지"""
        enhanced_messages = [
            "현재 자산을 잘 관리하고 계시네요. 작은 수익이라도 꾸준히 쌓아가면 큰 부를 만들 수 있어요. 조급해하지 말고 차근차근 해나가세요 💪",
            "트레이딩에서 가장 중요한 건 감정 조절이에요. 오늘의 결과에 일희일비하지 말고 장기적인 관점으로 접근해보세요 🎯", 
            "시장은 예측할 수 없지만 준비된 투자자에게는 기회가 됩니다. 리스크 관리를 철저히 하면서 꾸준히 나아가세요 🚀",
            "수익이 날 때는 겸손하게, 손실이 날 때는 배우는 마음으로 접근하세요. 이런 균형감이 장기적 성공의 비결이에요 ✨"
        ]
        return random.choice(enhanced_messages)
    
    def _generate_pattern_mental_care(self, total_equity: float, today_pnl: float,
                                    unrealized_pnl: float, weekly_total: float,
                                    weekly_avg: float, has_position: bool) -> str:
        """패턴 기반 다양한 멘탈 케어 - 더 개인화된 버전"""
        
        # 상황 분류
        situation = self._analyze_trading_situation(today_pnl, unrealized_pnl, weekly_total)
        
        # 구체적 수치를 포함한 개인화된 메시지
        if situation == "큰 수익":
            return self._big_win_personalized_messages(today_pnl, total_equity, weekly_total, weekly_avg)
        elif situation == "안정적 수익":
            return self._steady_profit_personalized_messages(today_pnl, weekly_total, weekly_avg, total_equity)
        elif situation == "소폭 손실":
            return self._small_loss_personalized_messages(unrealized_pnl, weekly_total, weekly_avg)
        elif situation == "큰 손실":
            return self._big_loss_personalized_messages(unrealized_pnl, total_equity, weekly_total)
        elif situation == "손익분기":
            return self._break_even_personalized_messages(total_equity, weekly_total, weekly_avg)
        else:
            return self._general_personalized_messages(total_equity, weekly_total, weekly_avg)
    
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
    
    def _big_win_personalized_messages(self, today_pnl: float, total_equity: float, weekly_total: float, weekly_avg: float) -> str:
        """큰 수익 시 개인화된 메시지"""
        today_total = today_pnl + (0 if today_pnl > 0 else abs(today_pnl * 0.1))  # 추정 총 수익
        monthly_projection = weekly_avg * 30
        
        patterns = [
            f'오늘 {today_total:.0f}달러 대박이네요! 이번 주에만 {weekly_total:.0f}달러를 벌었으니 월 {monthly_projection:.0f}달러도 가능해 보여요. 하지만 과욕은 금물, 현재 자산 {total_equity:,.0f}달러를 지키는 게 우선이에요 💪',
            
            f'와! {today_total:.0f}달러 수익으로 총 자산이 {total_equity:,.0f}달러가 되었네요! 7일 평균 {weekly_avg:.0f}달러씩 번다면 연간 {weekly_avg*365:.0f}달러도 꿈이 아니에요. 지금 페이스를 유지하세요 🚀',
            
            f'{today_total:.0f}달러 벌면서 이번 주 {weekly_total:.0f}달러 달성! 편의점 알바 {int(today_total/15):.0f}시간치를 하루에 벌었네요. 이런 실력이면 월 {monthly_projection:.0f}달러는 문제없을 것 같아요 🎯',
            
            f'오늘의 {today_total:.0f}달러는 운이 아니라 실력이에요! 주간 평균 {weekly_avg:.0f}달러를 꾸준히 유지한다면 {total_equity:,.0f}달러 자산이 1년 후엔 {total_equity + weekly_avg*52:,.0f}달러가 될 수도 있어요 ⭐'
        ]
        return random.choice(patterns)
    
    def _steady_profit_personalized_messages(self, today_pnl: float, weekly_total: float, weekly_avg: float, total_equity: float) -> str:
        """꾸준한 수익 시 개인화된 메시지"""
        monthly_projection = weekly_avg * 30
        yearly_projection = weekly_avg * 365
        
        patterns = [
            f'오늘 {today_pnl:.0f}달러, 이번 주 {weekly_total:.0f}달러로 정말 꾸준하네요! 일평균 {weekly_avg:.0f}달러면 월 {monthly_projection:.0f}달러 예상이에요. 복리로 굴리면 {total_equity:,.0f}달러가 몇 배로 불어날 거예요 📈',
            
            f'{today_pnl:.0f}달러씩 꾸준히 벌고 있어요! 작아 보여도 이런 안정성이 {total_equity:,.0f}달러를 만들었죠. 년간 {yearly_projection:.0f}달러 페이스라면 정말 대단한 성과예요 💎',
            
            f'하루 {today_pnl:.0f}달러, 주간 {weekly_total:.0f}달러의 안정적인 수익! 커피값도 안 되는 것 같지만 월 {monthly_projection:.0f}달러면 훌륭한 부수입이에요. 이 꾸준함을 계속 유지하세요 🌱',
            
            f'오늘도 {today_pnl:.0f}달러 플러스네요! {total_equity:,.0f}달러 자산에서 주간 {weekly_avg:.0f}달러씩 번다는 건 연 {(weekly_avg*52/total_equity*100):.0f}% 수익률이에요. 은행 금리보다 훨씬 좋죠 ✨'
        ]
        return random.choice(patterns)
    
    def _small_loss_personalized_messages(self, unrealized_pnl: float, weekly_total: float, weekly_avg: float) -> str:
        """소폭 손실 시 개인화된 메시지"""
        loss_amount = abs(unrealized_pnl)
        
        patterns = [
            f'지금 {loss_amount:.0f}달러 마이너스지만 이번 주 {weekly_total:.0f}달러 벌었잖아요! 일평균 {weekly_avg:.0f}달러 실력이면 이 정도 손실은 금방 회복될 거예요. 감정적으로 대응하지 마세요 🌱',
            
            f'{loss_amount:.0f}달러 손실이 있지만 괜찮아요. 주간 평균 {weekly_avg:.0f}달러씩 벌고 있으니 {int(loss_amount/weekly_avg):.0f}일이면 회복 가능해요. 손실도 트레이딩의 일부라는 걸 기억하세요 💪',
            
            f'마이너스 {loss_amount:.0f}달러이지만 너무 걱정하지 마세요. 이번 주만 봐도 {weekly_total:.0f}달러 벌었으니 실력은 검증됐어요. 이런 경험이 더 나은 트레이더로 만들어줄 거예요 🎯',
            
            f'{loss_amount:.0f}달러 손실 중이네요. 하지만 주간 수익 {weekly_total:.0f}달러를 보면 일시적인 조정일 뿐이에요. 평균 일 수익 {weekly_avg:.0f}달러 실력으로 충분히 극복할 수 있어요 ✨'
        ]
        return random.choice(patterns)
    
    def _big_loss_personalized_messages(self, unrealized_pnl: float, total_equity: float, weekly_total: float) -> str:
        """큰 손실 시 개인화된 메시지"""
        loss_amount = abs(unrealized_pnl)
        loss_ratio = (loss_amount / total_equity * 100) if total_equity > 0 else 0
        
        patterns = [
            f'{loss_amount:.0f}달러 손실은 크지만 총 자산 {total_equity:,.0f}달러의 {loss_ratio:.1f}%일 뿐이에요. 이번 주 {weekly_total:.0f}달러 벌었던 실력을 믿고 차분하게 대응하세요. 감정적 거래는 더 큰 손실을 부르니까요 🛡️',
            
            f'{loss_amount:.0f}달러 마이너스... 힘들겠지만 아직 {total_equity-loss_amount:,.0f}달러가 남아있어요. 손절의 용기를 가지고 다시 시작하면 됩니다. 주간 실력 {weekly_total:.0f}달러를 보면 회복 가능해요 💪',
            
            f'지금 {loss_amount:.0f}달러 손실이지만 포기하지 마세요. 전체 자산의 {loss_ratio:.0f}%이고, 이번 주 수익 {weekly_total:.0f}달러를 고려하면 {int(loss_amount/abs(weekly_total)):.0f}주 정도면 회복 가능해요. 냉정함을 되찾으세요 🌱',
            
            f'{loss_amount:.0f}달러 손실은 아프지만 끝이 아니에요. {total_equity:,.0f}달러 자산으로 재기할 수 있어요. 먼저 감정을 추스르고 손절 타이밍을 놓치지 마세요. 시장은 항상 새로운 기회를 줍니다 🎯'
        ]
        return random.choice(patterns)
    
    def _break_even_personalized_messages(self, total_equity: float, weekly_total: float, weekly_avg: float) -> str:
        """손익 균형 시 개인화된 메시지"""
        patterns = [
            f'오늘은 변화가 없지만 {total_equity:,.0f}달러를 지킨 것만으로도 충분해요. 이번 주 {weekly_total:.0f}달러 벌었으니 실력은 있어요. 때로는 기다리는 것도 전략이에요 ⚖️',
            
            f'손익 제로, 나쁘지 않아요! 무리해서 거래하지 않은 게 현명해요. 주간 평균 {weekly_avg:.0f}달러 버는 실력이면 다음 기회에서 충분히 수익낼 수 있어요 🎯',
            
            f'오늘은 평온한 날이네요. {total_equity:,.0f}달러 자산을 안전하게 보존하면서 이번 주 {weekly_total:.0f}달러도 벌었잖아요. 매일 수익을 낼 필요는 없어요 📊',
            
            f'변동 없는 날도 있죠. 거래하지 않는 것이 최고의 거래일 때도 있어요. 주간 수익 {weekly_total:.0f}달러로 충분히 좋은 성과고, {total_equity:,.0f}달러 자산을 잘 관리하고 있어요 ✨'
        ]
        return random.choice(patterns)
    
    def _general_personalized_messages(self, total_equity: float, weekly_total: float, weekly_avg: float) -> str:
        """일반적인 개인화된 메시지"""
        yearly_projection = weekly_avg * 52
        
        patterns = [
            f'현재 자산 {total_equity:,.0f}달러, 꾸준히 관리하고 계시네요! 주간 평균 {weekly_avg:.0f}달러 수익이면 연간 {yearly_projection:.0f}달러 예상이에요. 감정보다는 시스템을 믿고 따르세요 📈',
            
            f'이번 주 {weekly_total:.0f}달러 수익으로 총 {total_equity:,.0f}달러를 운용 중이시네요! 일평균 {weekly_avg:.0f}달러씩 꾸준히 벌고 있어요. 이런 안정성이 장기적 성공의 열쇠예요 💪',
            
            f'자산 {total_equity:,.0f}달러에서 주간 {weekly_total:.0f}달러 수익! 매일의 작은 결정이 큰 결과를 만들어요. 현재 {(weekly_total/total_equity*100):.1f}% 주간 수익률이면 상당히 좋은 성과예요 🌟',
            
            f'꾸준한 성장세네요! {total_equity:,.0f}달러 자산에서 주간 {weekly_avg:.0f}달러씩 벌면 복리 효과로 몇 년 후엔 상당한 자산이 될 거예요. 지금처럼 계속 해나가세요 🚀'
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
