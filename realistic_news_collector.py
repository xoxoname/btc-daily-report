import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from news_collector_core import NewsCollectorCore
from news_translator import NewsTranslator
from news_processor import NewsProcessor

logger = logging.getLogger(__name__)

class RealisticNewsCollector:
    """🔥🔥 통합 뉴스 수집기 - 3개 모듈 통합 관리"""
    
    def __init__(self, config):
        self.config = config
        
        # 3개 모듈 초기화
        self.core_collector = NewsCollectorCore(config)
        self.translator = NewsTranslator(config)
        self.processor = NewsProcessor(config)
        
        # 메인 뉴스 버퍼
        self.news_buffer = []
        self.events_buffer = []
        
        # 데이터 컬렉터 참조
        self.data_collector = None
        
        logger.info(f"🔥🔥 통합 뉴스 수집기 초기화 완료")
        logger.info(f"📡 RSS + API 수집: NewsCollectorCore")
        logger.info(f"🧠 번역/요약: NewsTranslator (GPT 우선, Claude 백업)")
        logger.info(f"📊 분석/처리: NewsProcessor (분류, 중복체크, 이벤트생성)")
    
    def set_data_collector(self, data_collector):
        """데이터 컬렉터 설정"""
        self.data_collector = data_collector
    
    async def start_monitoring(self):
        """뉴스 모니터링 시작"""
        logger.info("🔥🔥 통합 뉴스 모니터링 시작")
        
        # 핵심 수집 작업들
        tasks = [
            self.core_collector.start_monitoring(),  # RSS + API 수집
            self.process_collected_news(),           # 수집된 뉴스 처리
            self.cleanup_old_data()                  # 오래된 데이터 정리
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def process_collected_news(self):
        """수집된 뉴스를 주기적으로 처리"""
        while True:
            try:
                # 핵심 수집기에서 수집된 뉴스 가져오기
                collected_news = self.core_collector.news_buffer.copy()
                
                if not collected_news:
                    await asyncio.sleep(10)
                    continue
                
                processed_count = 0
                critical_count = 0
                
                for article in collected_news:
                    try:
                        # 최신 뉴스만 처리 (2시간 이내)
                        if not self._is_recent_news(article, hours=2):
                            continue
                        
                        # 비트코인 + 거시경제 관련성 체크
                        if not self.processor.is_bitcoin_or_macro_related(article):
                            continue
                        
                        # 기업명 추출
                        company = self.processor.extract_company_from_content(
                            article.get('title', ''),
                            article.get('description', '')
                        )
                        if company:
                            article['company'] = company
                        
                        # 크리티컬 뉴스 체크
                        if self.processor.is_critical_news(article):
                            # 번역 (필요시에만)
                            if self.translator.should_translate_for_emergency_report(article):
                                article['title_ko'] = await self.translator.translate_text(article.get('title', ''))
                            else:
                                article['title_ko'] = article.get('title', '')
                            
                            # 요약 (선택적)
                            if self.translator.should_use_gpt_summary(article):
                                summary = await self.translator.summarize_article(
                                    article['title'],
                                    article.get('description', '')
                                )
                                if summary:
                                    article['summary'] = summary
                            
                            # 중복 체크 후 이벤트 생성
                            if not self.processor.is_duplicate_emergency(article):
                                article['expected_change'] = self.processor.estimate_price_impact(article)
                                event = self.processor.create_emergency_event(article, self.translator)
                                
                                if event and self.data_collector:
                                    self.data_collector.events_buffer.append(event)
                                    critical_count += 1
                        
                        # 중요 뉴스는 버퍼에 추가
                        elif self.processor.is_important_news(article):
                            self.news_buffer.append(article)
                        
                        processed_count += 1
                        
                    except Exception as e:
                        logger.error(f"❌ 뉴스 처리 중 오류: {e}")
                        continue
                
                # 처리된 뉴스는 핵심 수집기 버퍼에서 제거
                self.core_collector.news_buffer = []
                
                if processed_count > 0:
                    logger.info(f"📰 뉴스 처리 완료: {processed_count}개 처리 (크리티컬: {critical_count}개)")
                
                # 버퍼 크기 관리
                if len(self.news_buffer) > 100:
                    self.news_buffer = self.news_buffer[-100:]
                
                await asyncio.sleep(15)  # 15초마다 처리
                
            except Exception as e:
                logger.error(f"❌ 뉴스 처리 루프 오류: {e}")
                await asyncio.sleep(30)
    
    async def cleanup_old_data(self):
        """오래된 데이터 정리 - 30분마다"""
        while True:
            try:
                # 뉴스 처리기의 정리 작업 실행
                self.processor.cleanup_old_data()
                
                # 메인 버퍼 정리
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=12)
                
                # 오래된 뉴스 제거
                old_buffer_size = len(self.news_buffer)
                self.news_buffer = [
                    article for article in self.news_buffer
                    if self._get_article_time(article) > cutoff_time
                ]
                
                removed_count = old_buffer_size - len(self.news_buffer)
                if removed_count > 0:
                    logger.info(f"🧹 오래된 뉴스 정리: {removed_count}개 제거")
                
                await asyncio.sleep(1800)  # 30분마다
                
            except Exception as e:
                logger.error(f"❌ 데이터 정리 오류: {e}")
                await asyncio.sleep(3600)
    
    def _is_recent_news(self, article: Dict, hours: int = 2) -> bool:
        """뉴스가 최근 것인지 확인"""
        try:
            pub_time_str = article.get('published_at', '')
            if not pub_time_str:
                return True
            
            try:
                if 'T' in pub_time_str:
                    pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                else:
                    from dateutil import parser
                    pub_time = parser.parse(pub_time_str)
                
                if pub_time.tzinfo is None:
                    import pytz
                    pub_time = pytz.UTC.localize(pub_time)
                
                time_diff = datetime.now(pytz.UTC) - pub_time
                return time_diff.total_seconds() < (hours * 3600)
            except:
                return True
        except:
            return True
    
    def _get_article_time(self, article: Dict) -> datetime:
        """기사 시간 추출"""
        try:
            pub_time_str = article.get('published_at', '')
            if pub_time_str:
                if 'T' in pub_time_str:
                    return datetime.fromisoformat(pub_time_str.replace('Z', ''))
                else:
                    from dateutil import parser
                    return parser.parse(pub_time_str)
        except:
            pass
        
        return datetime.now()
    
    async def get_recent_news(self, hours: int = 12) -> List[Dict]:
        """최근 뉴스 가져오기"""
        try:
            # 핵심 수집기에서 가져오기
            core_news = await self.core_collector.get_recent_news(hours)
            
            # 메인 버퍼에서 가져오기
            cutoff_time = datetime.now() - timedelta(hours=hours)
            buffer_news = [
                article for article in self.news_buffer
                if self._get_article_time(article) > cutoff_time
            ]
            
            # 합치고 정렬
            all_news = core_news + buffer_news
            
            # 중복 제거
            seen_hashes = set()
            unique_news = []
            
            for article in all_news:
                content_hash = self.processor.generate_content_hash(
                    article.get('title', ''),
                    article.get('description', '')
                )
                if content_hash not in seen_hashes:
                    unique_news.append(article)
                    seen_hashes.add(content_hash)
            
            # 가중치와 시간으로 정렬
            unique_news.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
            
            logger.info(f"📰 최근 {hours}시간 뉴스: {len(unique_news)}개")
            
            return unique_news[:25]
            
        except Exception as e:
            logger.error(f"❌ 최근 뉴스 조회 오류: {e}")
            return []
    
    def get_translation_stats(self) -> Dict:
        """번역 통계 반환"""
        return self.translator.get_translation_stats()
    
    def update_news_stats(self, news_type: str, translation_type: str = None):
        """뉴스 통계 업데이트 (호환성을 위해)"""
        pass
    
    async def close(self):
        """세션 종료"""
        try:
            await self.core_collector.close()
            
            # 통계 출력
            stats = self.get_translation_stats()
            logger.info("🔚 통합 뉴스 수집기 세션 종료")
            logger.info(f"🧠 최종 GPT 번역: {stats['gpt_translations']}, Claude 번역: {stats['claude_translations']}")
            logger.info(f"📝 최종 GPT 요약: {stats['summaries']}")
            logger.info(f"⚠️ Claude 에러: {stats['claude_errors']}회")
            logger.info(f"💰 번역 정책: 크리티컬 리포트 전송 시에만")
            
        except Exception as e:
            logger.error(f"❌ 세션 종료 중 오류: {e}")
