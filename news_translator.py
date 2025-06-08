import openai
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import hashlib
import re

logger = logging.getLogger(__name__)

class NewsTranslator:
    """🔥🔥 번역 및 요약 전담 클래스 - GPT 위주, Claude 백업"""
    
    def __init__(self, config):
        self.config = config
        
        # GPT API 클라이언트 (주력)
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            logger.info("✅ GPT API 클라이언트 초기화 완료 (주력)")
        
        # Claude API 클라이언트 (백업)
        self.anthropic_client = None
        if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
                logger.info("✅ Claude API 클라이언트 초기화 완료 (백업)")
            except ImportError:
                logger.warning("❌ anthropic 라이브러리가 설치되지 않음: pip install anthropic")
            except Exception as e:
                logger.warning(f"❌ Claude API 초기화 실패: {e}")
        
        # 번역 사용량 추적
        self.gpt_translation_count = 0
        self.claude_translation_count = 0
        self.claude_error_count = 0
        self.last_translation_reset = datetime.now()
        self.max_gpt_translations_per_15min = 30
        self.max_claude_translations_per_15min = 15
        self.translation_reset_interval = 900  # 15분
        self.claude_cooldown_until = None
        self.claude_cooldown_duration = 300  # 5분 쿨다운
        
        # 요약 사용량 추적
        self.summary_count = 0
        self.max_summaries_per_15min = 20
        self.last_summary_reset = datetime.now()
        
        # 번역 캐시
        self.translation_cache = {}
        
        logger.info(f"🧠 GPT API: {'활성화' if self.openai_client else '비활성화'} (주력)")
        logger.info(f"🤖 Claude API: {'활성화' if self.anthropic_client else '비활성화'} (백업)")
        logger.info(f"💰 번역 정책: 크리티컬 리포트 전송 시에만")
    
    def _reset_translation_count_if_needed(self):
        """필요시 번역 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_translation_reset).total_seconds() > self.translation_reset_interval:
            old_claude_count = self.claude_translation_count
            old_gpt_count = self.gpt_translation_count
            old_error_count = self.claude_error_count
            self.claude_translation_count = 0
            self.gpt_translation_count = 0
            self.claude_error_count = 0
            self.last_translation_reset = now
            
            # Claude 쿨다운 해제
            if self.claude_cooldown_until and now > self.claude_cooldown_until:
                self.claude_cooldown_until = None
                logger.info("✅ Claude 쿨다운 해제")
            
            if old_claude_count > 0 or old_gpt_count > 0:
                logger.info(f"🔄 번역 카운트 리셋: GPT {old_gpt_count} → 0, Claude {old_claude_count} → 0, 에러 {old_error_count} → 0")
    
    def _reset_summary_count_if_needed(self):
        """필요시 요약 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_summary_reset).total_seconds() > self.translation_reset_interval:
            old_count = self.summary_count
            self.summary_count = 0
            self.last_summary_reset = now
            if old_count > 0:
                logger.info(f"🔄 요약 카운트 리셋: {old_count} → 0")
    
    def should_translate_for_emergency_report(self, article: Dict) -> bool:
        """🔥🔥 긴급 리포트 전송 시에만 번역 (API 비용 최소화)"""
        # 이미 한글 제목이 있으면 번역 불필요
        if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
            return False
        
        # 번역 한도 체크
        self._reset_translation_count_if_needed()
        
        # 번역이 가능한 상태인지 확인
        can_use_gpt = self.openai_client and self.gpt_translation_count < self.max_gpt_translations_per_15min
        can_use_claude = self._is_claude_available()
        
        if not (can_use_gpt or can_use_claude):
            logger.warning(f"⚠️ 번역 한도 초과 - GPT: {self.gpt_translation_count}/{self.max_gpt_translations_per_15min}, Claude: {self.claude_translation_count}/{self.max_claude_translations_per_15min}")
            return False
        
        return True
    
    def _is_claude_available(self) -> bool:
        """Claude API 사용 가능 여부 확인"""
        if not self.anthropic_client:
            return False
        
        # 쿨다운 중인지 확인
        if self.claude_cooldown_until and datetime.now() < self.claude_cooldown_until:
            return False
        
        # 번역 카운트 리셋 체크
        self._reset_translation_count_if_needed()
        
        # Rate limit 체크
        if self.claude_translation_count >= self.max_claude_translations_per_15min:
            return False
        
        # 에러가 너무 많으면 일시 중단
        if self.claude_error_count >= 2:
            self.claude_cooldown_until = datetime.now() + timedelta(seconds=self.claude_cooldown_duration)
            logger.warning(f"⚠️ Claude API 에러가 {self.claude_error_count}회 발생, {self.claude_cooldown_duration//60}분 쿨다운 시작")
            return False
        
        return True
    
    async def translate_with_gpt(self, text: str, max_length: int = 400) -> str:
        """🔥🔥 GPT API를 사용한 번역 - 주력 사용"""
        if not self.openai_client:
            logger.warning("⚠️ GPT API 클라이언트가 없습니다")
            return text
        
        # 번역 카운트 리셋 체크
        self._reset_translation_count_if_needed()
        
        # GPT Rate limit 체크
        if self.gpt_translation_count >= self.max_gpt_translations_per_15min:
            logger.warning(f"⚠️ GPT 번역 한도 초과: {self.gpt_translation_count}/{self.max_gpt_translations_per_15min}")
            return text
        
        # 캐시 확인
        cache_key = f"gpt_{hashlib.md5(text.encode()).hexdigest()}"
        if cache_key in self.translation_cache:
            logger.debug(f"🔄 GPT 번역 캐시 히트")
            return self.translation_cache[cache_key]
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 전문 번역가입니다. 영문을 자연스러운 한국어로 번역하세요."},
                    {"role": "user", "content": f"다음을 한국어로 번역 (최대 {max_length}자):\n\n{text}"}
                ],
                max_tokens=150,
                temperature=0.2,
                timeout=15.0
            )
            
            translated = response.choices[0].message.content.strip()
            
            # 길이 체크
            if len(translated) > max_length:
                translated = translated[:max_length-3] + "..."
            
            # 캐시 저장
            self.translation_cache[cache_key] = translated
            
            # 캐시 크기 제한
            if len(self.translation_cache) > 500:
                keys_to_remove = list(self.translation_cache.keys())[:250]
                for key in keys_to_remove:
                    del self.translation_cache[key]
            
            self.gpt_translation_count += 1
            logger.info(f"🧠 GPT 번역 완료 ({self.gpt_translation_count}/{self.max_gpt_translations_per_15min}) - 크리티컬 전용")
            return translated
            
        except Exception as e:
            logger.warning(f"❌ GPT 번역 실패: {str(e)[:50]}")
            return text
    
    async def translate_with_claude(self, text: str, max_length: int = 400) -> str:
        """🔥🔥 Claude API를 사용한 번역 - 에러 처리 강화 (백업용)"""
        if not self._is_claude_available():
            return ""  # 빈 문자열 반환하여 GPT로 넘어가도록
        
        # 캐시 확인
        cache_key = f"claude_{hashlib.md5(text.encode()).hexdigest()}"
        if cache_key in self.translation_cache:
            logger.debug(f"🔄 Claude 번역 캐시 히트")
            return self.translation_cache[cache_key]
        
        try:
            response = await self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",  # 빠르고 저렴한 모델
                max_tokens=200,
                timeout=10.0,
                messages=[{
                    "role": "user", 
                    "content": f"""다음 영문 뉴스 제목을 자연스러운 한국어로 번역해주세요. 전문 용어는 다음과 같이 번역하세요:

- Bitcoin/BTC → 비트코인
- ETF → ETF
- Tesla → 테슬라
- MicroStrategy → 마이크로스트래티지
- SEC → SEC
- Fed/Federal Reserve → 연준
- Trump → 트럼프
- China → 중국
- Russia → 러시아
- tariffs → 관세

최대 {max_length}자 이내로 번역하되, 의미가 명확하게 전달되도록 해주세요.

제목: {text}"""
                }]
            )
            
            translated = response.content[0].text.strip()
            
            # 길이 체크
            if len(translated) > max_length:
                sentences = translated.split('.')
                result = ""
                for sentence in sentences:
                    if len(result + sentence + ".") <= max_length - 3:
                        result += sentence + "."
                    else:
                        break
                translated = result.strip()
                if not translated:
                    translated = translated[:max_length-3] + "..."
            
            # 캐시 저장 및 카운트 증가
            self.translation_cache[cache_key] = translated
            self.claude_translation_count += 1
            
            logger.info(f"🤖 Claude 번역 완료 ({self.claude_translation_count}/{self.max_claude_translations_per_15min}) - 크리티컬 전용")
            return translated
            
        except Exception as e:
            # 에러 카운트 증가
            self.claude_error_count += 1
            error_str = str(e)
            
            # 529 에러 (rate limit) 특별 처리
            if "529" in error_str or "rate" in error_str.lower() or "limit" in error_str.lower():
                logger.warning(f"⚠️ Claude API rate limit 감지 (에러 {self.claude_error_count}/2), 30분 쿨다운")
                self.claude_cooldown_until = datetime.now() + timedelta(minutes=30)
            else:
                logger.warning(f"❌ Claude 번역 실패 (에러 {self.claude_error_count}/2): {error_str[:50]}")
            
            return ""  # 빈 문자열 반환하여 GPT로 넘어가도록
    
    async def translate_text(self, text: str, max_length: int = 400) -> str:
        """🔥🔥 통합 번역 함수 - GPT 우선, Claude 백업"""
        # 1순위: GPT (안정적)
        if self.openai_client:
            result = await self.translate_with_gpt(text, max_length)
            if result != text:  # 번역이 성공했으면
                return result
        
        # 2순위: Claude (보조용)
        if self._is_claude_available():
            result = await self.translate_with_claude(text, max_length)
            if result:  # 빈 문자열이 아니면
                return result
        
        # 모든 번역 실패 시 원문 반환
        logger.warning(f"⚠️ 모든 번역 실패, 원문 반환: {text[:50]}...")
        return text
    
    def should_use_gpt_summary(self, article: Dict) -> bool:
        """🔥🔥 GPT 요약 사용 여부 결정 - 크리티컬 리포트만"""
        # 요약 카운트 리셋 체크
        self._reset_summary_count_if_needed()
        
        # Rate limit 체크
        if self.summary_count >= self.max_summaries_per_15min:
            return False
        
        # description이 충분히 길어야 함 (요약할 가치가 있어야 함)
        description = article.get('description', '')
        if len(description) < 200:
            return False
        
        return True
    
    async def summarize_article(self, title: str, description: str, max_length: int = 200) -> str:
        """🔥🔥 개선된 요약 - 기본 요약 우선, GPT는 백업"""
        
        # 🔥🔥 먼저 기본 요약으로 시도
        basic_summary = self._generate_basic_summary(title, description)
        if basic_summary and len(basic_summary.strip()) > 50:
            logger.debug(f"🔄 기본 요약 사용")
            return basic_summary
        
        # GPT 요약이 정말 필요한 경우만
        if not self.openai_client or not description:
            return basic_summary or "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
        
        if len(description) <= 200:
            return basic_summary or self._generate_basic_summary(title, description)
        
        # 요약 카운트 리셋 체크
        self._reset_summary_count_if_needed()
        
        # Rate limit 체크
        if self.summary_count >= self.max_summaries_per_15min:
            logger.warning(f"⚠️ 요약 한도 초과: {self.summary_count}/{self.max_summaries_per_15min} - 기본 요약 사용")
            return basic_summary or "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
        
        try:
            news_type = self._classify_news_for_summary(title, description)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"비트코인 투자 전문가입니다. 다음 뉴스를 정확하고 객관적으로 3문장으로 요약하세요.\n\n1문장: 핵심 사실\n2문장: 중요성/배경\n3문장: 시장 영향\n\n뉴스 타입: {news_type}"},
                    {"role": "user", "content": f"다음 뉴스를 정확히 3문장으로 요약해주세요 (최대 {max_length}자):\n\n제목: {title}\n\n내용: {description[:800]}"}
                ],
                max_tokens=250,
                temperature=0.1,
                timeout=15.0
            )
            
            summary = response.choices[0].message.content.strip()
            
            # 3문장으로 제한
            sentences = summary.split('.')
            if len(sentences) > 3:
                summary = '. '.join(sentences[:3]) + '.'
            
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."
            
            self.summary_count += 1
            logger.info(f"📝 GPT 요약 완료 ({self.summary_count}/{self.max_summaries_per_15min})")
            
            return summary
            
        except Exception as e:
            logger.warning(f"❌ GPT 요약 실패: {str(e)[:50]} - 기본 요약 사용")
            return basic_summary or "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
    
    def _classify_news_for_summary(self, title: str, description: str) -> str:
        """뉴스 타입 분류"""
        content = (title + " " + description).lower()
        
        if any(word in content for word in ['ai predicts', 'energy crisis', 'boom']):
            return 'ai_prediction'
        elif any(word in content for word in ['crosses', '100k', 'milestone']) and 'bitcoin' in content:
            return 'price_milestone'
        elif any(word in content for word in ['etf approved', 'etf rejected', 'etf filing']):
            return 'etf'
        elif any(word in content for word in ['fed rate', 'fomc', 'powell', 'interest rate']):
            return 'fed_policy'
        elif any(word in content for word in ['inflation', 'cpi', 'pce', 'unemployment']):
            return 'economic_data'
        elif any(company in content for company in ['tesla', 'microstrategy', 'blackrock']):
            return 'corporate_action'
        elif any(word in content for word in ['sec', 'regulation', 'ban', 'lawsuit']):
            return 'regulation'
        elif any(word in content for word in ['tariff', 'trade war', 'trade deal']):
            return 'trade_policy'
        elif any(word in content for word in ['hack', 'stolen', 'breach', 'security']):
            return 'security_incident'
        elif any(word in content for word in ['war', 'conflict', 'sanctions', 'geopolitical']):
            return 'geopolitical'
        else:
            return 'general'
    
    def _generate_basic_summary(self, title: str, description: str) -> str:
        """🔥🔥 강화된 기본 요약 생성 - GPT 대신 사용할 고품질 요약"""
        try:
            content = (title + " " + description).lower()
            summary_parts = []
            
            # AI 예측 관련 특별 처리
            if any(word in content for word in ['ai based', 'ai predicts', 'energy crisis']) and 'bitcoin' in content:
                if 'energy crisis' in content and '250000' in content:
                    summary_parts.append("AI 기반 예측에 따르면 에너지 위기가 비트코인 가격을 25만 달러까지 상승시킬 수 있다고 한다.")
                    summary_parts.append("하지만 이는 추측성 예측에 불과하며 실제 시장 요인들과는 거리가 있을 수 있다.")
                    summary_parts.append("투자자들은 이런 예측보다는 실제 시장 동향과 펀더멘털에 집중하는 것이 바람직하다.")
                else:
                    summary_parts.append("AI 기반 비트코인 가격 예측이 발표되었다.")
                    summary_parts.append("예측 모델의 정확성과 신뢰도는 검증이 필요한 상황이다.")
                    summary_parts.append("시장은 이런 예측보다는 실제 수급과 규제 동향에 더 민감하게 반응한다.")
                
                return " ".join(summary_parts)
            
            # 비트코인 가격 관련 특별 처리
            if any(word in content for word in ['crosses', '100k', '$100', 'milestone']) and 'bitcoin' in content:
                if any(word in content for word in ['search', 'google', 'interest', 'attention']):
                    summary_parts.append("비트코인이 10만 달러를 돌파했지만 구글 검색량은 예상보다 낮은 수준을 보이고 있다.")
                    summary_parts.append("이는 기관 투자자 중심의 상승으로 일반 투자자들의 관심은 아직 제한적임을 시사한다.")
                    summary_parts.append("향후 소매 투자자들의 FOMO가 본격화될 경우 추가 상승 여력이 있을 것으로 분석된다.")
                else:
                    summary_parts.append("비트코인이 10만 달러 이정표를 돌파하며 역사적인 순간을 기록했다.")
                    summary_parts.append("심리적 저항선 돌파로 단기적인 상승 모멘텀이 형성될 수 있다.")
                    summary_parts.append("하지만 과열 구간에서는 수익 실현 압박도 동시에 증가할 것으로 예상된다.")
                
                return " ".join(summary_parts)
            
            # 구조화 상품 특별 처리
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']):
                if 'sberbank' in content:
                    summary_parts.append("러시아 최대 은행 스베르방크가 비트코인 가격에 연동된 구조화 채권을 출시했다.")
                    summary_parts.append("이는 직접적인 비트코인 매수가 아닌 가격 추적 상품으로, 실제 BTC 수요 창출 효과는 제한적이다.")
                    summary_parts.append("러시아 제재 상황과 OTC 거래로 인해 글로벌 시장에 미치는 즉각적 영향은 미미할 것으로 예상된다.")
                else:
                    summary_parts.append("새로운 비트코인 연계 구조화 상품이 출시되었다.")
                    summary_parts.append("직접적인 비트코인 수요보다는 간접적 노출 제공에 중점을 둔 상품으로 평가된다.")
                    summary_parts.append("시장에 미치는 실질적 영향은 제한적일 것으로 전망된다.")
                
                return " ".join(summary_parts)
            
            # ETF 관련
            if 'etf' in content:
                if 'approved' in content or 'approval' in content:
                    summary_parts.append("비트코인 현물 ETF 승인 소식이 전해졌다.")
                    summary_parts.append("ETF 승인은 기관 투자자들의 대규모 자금 유입을 가능하게 하는 중요한 이정표다.")
                    summary_parts.append("비트코인 시장의 성숙도와 제도적 인정을 보여주는 상징적 사건으로 평가된다.")
                elif 'rejected' in content or 'delay' in content:
                    summary_parts.append("비트코인 ETF 승인이 지연되거나 거부되었다.")
                    summary_parts.append("단기적 실망감은 있으나, 지속적인 신청은 결국 승인 가능성을 높이고 있다.")
                    summary_parts.append("시장은 이미 ETF 승인을 기정사실로 받아들이고 있어 장기 전망은 긍정적이다.")
            
            # 기본 케이스
            if not summary_parts:
                summary_parts.append("비트코인 시장에 영향을 미칠 수 있는 발표가 있었다.")
                summary_parts.append("투자자들은 이번 소식의 실제 시장 영향을 면밀히 분석하고 있다.")
                summary_parts.append("단기 변동성은 있겠지만 장기 트렌드에는 큰 변화가 없을 것으로 전망된다.")
            
            return " ".join(summary_parts[:3]) if summary_parts else "비트코인 관련 소식이 발표되었다. 실제 영향을 분석해야 한다. 투자자들은 신중한 접근이 필요하다."
            
        except Exception as e:
            logger.error(f"❌ 기본 요약 생성 실패: {e}")
            return "비트코인 시장 관련 소식이 발표되었다. 자세한 내용은 원문을 확인하시기 바란다. 실제 시장 반응을 면밀히 분석할 필요가 있다."
    
    def get_translation_stats(self) -> Dict:
        """번역 통계 반환"""
        return {
            'gpt_translations': self.gpt_translation_count,
            'claude_translations': self.claude_translation_count,
            'claude_errors': self.claude_error_count,
            'summaries': self.summary_count,
            'cache_size': len(self.translation_cache),
            'claude_available': self._is_claude_available()
        }
