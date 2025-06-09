import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
import hashlib
import re

logger = logging.getLogger(__name__)

class ExceptionDetector:
    """예외 상황 감지 및 알림 - 비트코인 전용 강화 + 크리티컬 뉴스 필터링 강화"""
    
    def __init__(self, bitget_client=None, telegram_bot=None):
        self.bitget_client = bitget_client
        self.telegram_bot = telegram_bot
        self.logger = logging.getLogger('exception_detector')
        
        # 임계값 설정 - 현실적으로
        self.PRICE_CHANGE_THRESHOLD = 2.0  # 2% 이상 변동
        self.VOLUME_SPIKE_THRESHOLD = 3.0  # 평균 대비 3배
        self.FUNDING_RATE_THRESHOLD = 0.02  # 2% 이상
        self.LIQUIDATION_THRESHOLD = 10_000_000  # 1천만 달러
        
        # 마지막 알림 시간 추적
        self.last_alerts = {}
        self.alert_cooldown = timedelta(minutes=30)  # 30분 쿨다운
        
        # 뉴스 중복 체크
        self.news_hashes = {}
        self.news_cooldown = timedelta(hours=4)  # 4시간 쿨다운
        
        # 전송된 예외 리포트 해시
        self.sent_exception_hashes: Set[str] = set()
        
        # 예외 리포트 내용 캐시
        self.exception_content_cache = {}
        self.cache_expiry = timedelta(hours=6)
        
        # 🔥🔥 가격 이력 및 검증 강화
        self.price_history = []
        self.max_price_history = 20
        self.last_valid_price = None  # 마지막 유효한 가격 저장
        self.price_validation_threshold = 1000  # 최소 유효 가격 ($1000)
        self.max_price_change_ratio = 0.5  # 최대 50% 가격 변동률 (오류 감지용)
        
        # 단기 변동성 체크
        self.short_term_threshold = 1.0  # 5분 내 1% 변동
        self.medium_term_threshold = 2.0  # 15분 내 2% 변동
        
        # 전송된 뉴스 제목 캐시 (중복 방지 강화)
        self.sent_news_titles = {}
        
        # 뉴스 후 시장 반응 추적
        self.news_market_reactions = {}  # 뉴스별 실제 시장 반응 기록
        
        # 가격 데이터 오류 추적
        self.price_error_count = 0
        self.max_price_errors = 5  # 최대 연속 오류 허용
        self.last_price_error_time = None
        
        # 🔥🔥 크리티컬 뉴스 필터링 강화
        self.critical_keywords = {
            'high_impact': [
                'etf approved', 'etf approval', 'etf launches', 'etf rejected',
                'fed rate', 'interest rate decision', 'fomc decision',
                'bought bitcoin', 'purchased bitcoin', 'adds bitcoin', 'buys bitcoin',
                'ban bitcoin', 'prohibited bitcoin', 'illegal bitcoin',
                'hack', 'exploit', 'stolen bitcoin', 'exchange hack'
            ],
            'medium_impact': [
                'regulation', 'legal framework', 'court decision',
                'institutional adoption', 'bank adoption',
                'treasury reserve', 'corporate strategy',
                'trump tariffs', 'trade war', 'inflation data'
            ],
            'company_direct_investment': [
                'microstrategy', 'tesla', 'gamestop', 'metaplanet'
            ],
            'low_impact_exclude': [  # 이런 키워드가 있으면 제외
                'how to', 'tutorial', 'guide', 'opinion', 'prediction',
                'analyst says', 'expert believes', 'could reach',
                'technical analysis', 'chart analysis', 'price target',
                'blog post', 'social media', 'tweet', 'reddit',
                'milestone', 'search volume', 'google trends'
            ]
        }
        
        self.logger.info(f"예외 감지기 초기화 완료 - 가격 {self.PRICE_CHANGE_THRESHOLD}%, 거래량 {self.VOLUME_SPIKE_THRESHOLD}배, 크리티컬 뉴스 필터링 강화")
    
    def _is_critical_bitcoin_news(self, event: Dict) -> bool:
        """🔥🔥 크리티컬 비트코인 뉴스 판별 - 매우 엄격한 기준"""
        try:
            title = event.get('title', '').lower()
            description = event.get('description', '').lower()
            content = f"{title} {description}"
            
            # 1. 비트코인 관련성 체크
            if not any(word in content for word in ['bitcoin', 'btc', 'crypto', 'cryptocurrency']):
                return False
            
            # 2. 제외 키워드 체크 (이런 내용들은 무조건 제외)
            for exclude_keyword in self.critical_keywords['low_impact_exclude']:
                if exclude_keyword in content:
                    self.logger.info(f"제외 키워드 감지로 크리티컬 뉴스 제외: {exclude_keyword}")
                    return False
            
            # 3. 높은 영향도 키워드 체크
            high_impact_score = 0
            for keyword in self.critical_keywords['high_impact']:
                if keyword in content:
                    high_impact_score += 3
                    self.logger.info(f"고영향 키워드 감지: {keyword}")
            
            # 4. 중간 영향도 키워드 체크
            medium_impact_score = 0
            for keyword in self.critical_keywords['medium_impact']:
                if keyword in content:
                    medium_impact_score += 2
                    self.logger.info(f"중영향 키워드 감지: {keyword}")
            
            # 5. 기업 직접 투자 체크
            company_investment_score = 0
            for company in self.critical_keywords['company_direct_investment']:
                if company in content:
                    if any(action in content for action in ['bought', 'purchased', 'adds', 'buys']):
                        company_investment_score += 4
                        self.logger.info(f"기업 직접 투자 감지: {company}")
            
            # 6. 구조화 상품 제외 (실제 BTC 수요 없음)
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure', 'tracks']):
                if not any(word in content for word in ['etf', 'direct purchase', 'treasury']):
                    self.logger.info("구조화 상품으로 판단, 크리티컬 뉴스 제외")
                    return False
            
            # 7. 총 점수 계산
            total_score = high_impact_score + medium_impact_score + company_investment_score
            
            # 8. 임계값 판단
            if total_score >= 6:  # 매우 높은 임계값
                self.logger.info(f"크리티컬 뉴스 승인: 총점 {total_score}점")
                return True
            elif total_score >= 3 and high_impact_score > 0:  # 고영향 키워드가 있어야 함
                self.logger.info(f"크리티컬 뉴스 승인: 총점 {total_score}점 (고영향 포함)")
                return True
            else:
                self.logger.info(f"크리티컬 뉴스 기준 미달: 총점 {total_score}점")
                return False
                
        except Exception as e:
            self.logger.error(f"크리티컬 뉴스 판별 오류: {e}")
            return False
    
    def _calculate_expected_price_impact(self, event: Dict) -> float:
        """🔥🔥 예상 가격 영향도 계산 - 현실적 기준"""
        try:
            title = event.get('title', '').lower()
            description = event.get('description', '').lower()
            content = f"{title} {description}"
            
            # 기본 영향도
            impact = 0.0
            
            # ETF 관련
            if 'etf approved' in content or 'etf approval' in content:
                impact = max(impact, 2.5)  # 2.5% 예상
            elif 'etf rejected' in content or 'etf delay' in content:
                impact = max(impact, 1.5)  # 1.5% 하락 예상
            
            # Fed 금리
            if any(word in content for word in ['fed rate cut', 'rate cut', 'lower rates']):
                impact = max(impact, 1.8)
            elif any(word in content for word in ['fed rate hike', 'rate hike', 'higher rates']):
                impact = max(impact, 1.2)
            
            # 기업 직접 투자
            if any(company in content for company in ['microstrategy', 'tesla']) and \
               any(action in content for action in ['bought', 'purchased', 'adds']):
                # 투자 규모 확인
                if any(amount in content for amount in ['billion', '1b', '$1b']):
                    impact = max(impact, 1.5)
                else:
                    impact = max(impact, 0.8)
            
            # 규제/법적
            if any(word in content for word in ['ban', 'prohibited', 'illegal']):
                impact = max(impact, 2.0)
            elif any(word in content for word in ['regulation approved', 'legal framework']):
                impact = max(impact, 0.8)
            
            # 해킹/보안
            if any(word in content for word in ['hack', 'stolen', 'exploit']):
                impact = max(impact, 1.0)
            
            # 구조화 상품 (영향도 매우 낮음)
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']):
                impact = min(impact, 0.2)
            
            return impact
            
        except Exception as e:
            self.logger.error(f"가격 영향도 계산 오류: {e}")
            return 0.0
    
    def _validate_price_data(self, price_data: Dict) -> Optional[float]:
        """🔥🔥 가격 데이터 검증 및 정제 - 오류 방지 강화"""
        try:
            if not price_data:
                self.logger.debug("가격 데이터가 None 또는 빈 값")
                return None
            
            # 'last' 필드에서 현재가 추출
            current_price = None
            if 'last' in price_data:
                try:
                    current_price = float(price_data['last'])
                except (ValueError, TypeError):
                    self.logger.warning(f"'last' 필드 변환 실패: {price_data.get('last')}")
            
            # 'close' 필드 백업
            if current_price is None and 'close' in price_data:
                try:
                    current_price = float(price_data['close'])
                except (ValueError, TypeError):
                    self.logger.warning(f"'close' 필드 변환 실패: {price_data.get('close')}")
            
            # 'price' 필드 백업
            if current_price is None and 'price' in price_data:
                try:
                    current_price = float(price_data['price'])
                except (ValueError, TypeError):
                    self.logger.warning(f"'price' 필드 변환 실패: {price_data.get('price')}")
            
            # 가격이 여전히 None이거나 0이면
            if current_price is None or current_price <= 0:
                self.price_error_count += 1
                self.last_price_error_time = datetime.now()
                
                if self.price_error_count <= 3:  # 처음 몇 번만 로그
                    self.logger.warning(f"유효하지 않은 가격 데이터: {current_price} (오류 {self.price_error_count}회)")
                    self.logger.debug(f"원본 데이터: {price_data}")
                
                # 마지막 유효한 가격이 있으면 사용
                if self.last_valid_price and self.last_valid_price > self.price_validation_threshold:
                    self.logger.debug(f"마지막 유효 가격 사용: ${self.last_valid_price:,.0f}")
                    return self.last_valid_price
                
                return None
            
            # 최소 가격 임계값 체크 (비트코인은 보통 $1000 이상)
            if current_price < self.price_validation_threshold:
                self.logger.warning(f"가격이 임계값보다 낮음: ${current_price:,.2f} < ${self.price_validation_threshold}")
                return None
            
            # 최대 가격 체크 (비현실적인 가격 방지 - 예: $1,000,000 이상)
            if current_price > 1_000_000:
                self.logger.warning(f"가격이 비현실적으로 높음: ${current_price:,.2f}")
                return None
            
            # 급격한 가격 변동 체크 (API 오류 방지)
            if self.last_valid_price and self.last_valid_price > 0:
                change_ratio = abs(current_price - self.last_valid_price) / self.last_valid_price
                if change_ratio > self.max_price_change_ratio:
                    self.logger.warning(f"급격한 가격 변동 감지: {change_ratio*100:.1f}% (${self.last_valid_price:,.0f} → ${current_price:,.0f})")
                    # 너무 급격한 변동은 API 오류일 가능성이 높으므로 마지막 유효 가격 사용
                    return self.last_valid_price
            
            # 모든 검증을 통과하면 유효한 가격으로 저장
            self.last_valid_price = current_price
            self.price_error_count = 0  # 오류 카운트 리셋
            
            return current_price
            
        except Exception as e:
            self.logger.error(f"가격 데이터 검증 중 오류: {e}")
            return self.last_valid_price  # 오류 시 마지막 유효 가격 반환
    
    async def detect_all_anomalies(self) -> List[Dict]:
        """모든 이상 징후 감지"""
        anomalies = []
        
        try:
            # 단기 변동성 체크
            short_term_anomaly = await self.check_short_term_volatility()
            if short_term_anomaly:
                anomalies.append(short_term_anomaly)
            
            # 가격 변동 체크
            price_anomaly = await self.check_price_volatility()
            if price_anomaly:
                anomalies.append(price_anomaly)
            
            # 거래량 이상 체크
            volume_anomaly = await self.check_volume_anomaly()
            if volume_anomaly:
                anomalies.append(volume_anomaly)
            
            # 펀딩비 이상 체크
            funding_anomaly = await self.check_funding_rate()
            if funding_anomaly:
                anomalies.append(funding_anomaly)
                
        except Exception as e:
            self.logger.error(f"이상 징후 감지 중 오류: {e}")
        
        return anomalies
    
    async def check_short_term_volatility(self) -> Optional[Dict]:
        """단기 변동성 감지 (5분, 15분 단위) - 가격 검증 강화"""
        try:
            if not self.bitget_client:
                return None
            
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            # 🔥🔥 가격 데이터 검증
            current_price = self._validate_price_data(ticker)
            if current_price is None:
                return None
            
            current_time = datetime.now()
            
            # 가격 이력에 추가
            self.price_history.append({
                'price': current_price,
                'time': current_time
            })
            
            # 오래된 이력 제거
            cutoff_time = current_time - timedelta(minutes=20)
            self.price_history = [
                p for p in self.price_history 
                if p['time'] > cutoff_time
            ]
            
            if len(self.price_history) < 3:
                return None
            
            # 5분 전 가격과 비교
            five_min_ago = current_time - timedelta(minutes=5)
            five_min_prices = [
                p['price'] for p in self.price_history 
                if p['time'] >= five_min_ago
            ]
            
            if len(five_min_prices) >= 2:
                min_price_5min = min(five_min_prices)
                max_price_5min = max(five_min_prices)
                
                # 🔥🔥 추가 검증 - 최소 가격이 0보다 커야 함
                if min_price_5min <= 0:
                    self.logger.warning(f"5분 이력에 유효하지 않은 가격: {min_price_5min}")
                    return None
                
                change_5min = ((max_price_5min - min_price_5min) / min_price_5min) * 100
                
                if change_5min >= self.short_term_threshold:
                    key = f"short_vol_5min_{int(current_price/100)*100}"
                    if not self._is_on_cooldown('short_term_volatility', key):
                        self._update_alert_time('short_term_volatility', key)
                        
                        return {
                            'type': 'short_term_volatility',
                            'severity': 'high',
                            'timeframe': '5분',
                            'change_percent': change_5min,
                            'min_price': min_price_5min,
                            'max_price': max_price_5min,
                            'current_price': current_price,
                            'description': f"5분 내 {change_5min:.1f}% 급변동",
                            'timestamp': current_time
                        }
            
        except Exception as e:
            self.logger.error(f"단기 변동성 체크 오류: {e}")
        
        return None
    
    async def check_price_volatility(self) -> Optional[Dict]:
        """가격 급변동 감지 - 가격 검증 포함"""
        try:
            if not self.bitget_client:
                return None
            
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            # 🔥🔥 가격 데이터 검증
            current_price = self._validate_price_data(ticker)
            if current_price is None:
                return None
            
            change_24h = float(ticker.get('changeUtc', 0))
            
            # 24시간 변동률이 임계값 초과
            if abs(change_24h) >= self.PRICE_CHANGE_THRESHOLD / 100:  # 백분율 변환
                key = f"price_{int(current_price/1000)*1000}"
                if not self._is_on_cooldown('price_volatility', key):
                    self._update_alert_time('price_volatility', key)
                    
                    severity = 'critical' if abs(change_24h) >= 0.05 else 'high' if abs(change_24h) >= 0.03 else 'medium'
                    
                    return {
                        'type': 'price_anomaly',
                        'severity': severity,
                        'current_price': current_price,
                        'change_24h': change_24h,
                        'description': f"BTC {'급등' if change_24h > 0 else '급락'} {abs(change_24h*100):.1f}%",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"가격 변동 체크 오류: {e}")
        
        return None
    
    async def check_volume_anomaly(self) -> Optional[Dict]:
        """거래량 이상 감지"""
        try:
            if not self.bitget_client:
                return None
            
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            # 가격 검증 (거래량 검증을 위해)
            current_price = self._validate_price_data(ticker)
            if current_price is None:
                return None
            
            volume_24h = float(ticker.get('baseVolume', 0))
            
            # 거래량이 특정 임계값 초과
            threshold_volume = 50000 * self.VOLUME_SPIKE_THRESHOLD
            if volume_24h > threshold_volume:
                key = f"volume_{int(volume_24h/10000)*10000}"
                if not self._is_on_cooldown('volume_anomaly', key):
                    self._update_alert_time('volume_anomaly', key)
                    
                    return {
                        'type': 'volume_anomaly',
                        'severity': 'critical' if volume_24h > threshold_volume * 1.5 else 'high',
                        'volume_24h': volume_24h,
                        'ratio': volume_24h / 50000,
                        'threshold': threshold_volume,
                        'description': f"거래량 급증: {volume_24h:,.0f} BTC ({volume_24h/50000:.1f}배)",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"거래량 체크 오류: {e}")
        
        return None
    
    async def check_funding_rate(self) -> Optional[Dict]:
        """펀딩비 이상 감지"""
        try:
            if not self.bitget_client:
                return None
            
            funding_data = await self.bitget_client.get_funding_rate('BTCUSDT')
            if not funding_data:
                return None
            
            if isinstance(funding_data, list):
                if len(funding_data) > 0:
                    funding_data = funding_data[0]
                else:
                    return None
            
            funding_rate = float(funding_data.get('fundingRate', 0))
            
            # 펀딩비가 임계값 초과
            if abs(funding_rate) >= self.FUNDING_RATE_THRESHOLD:
                key = f"funding_{int(abs(funding_rate)*10000)}"
                if not self._is_on_cooldown('funding_rate', key):
                    self._update_alert_time('funding_rate', key)
                    
                    severity = 'critical' if abs(funding_rate) >= 0.03 else 'high'
                    
                    return {
                        'type': 'funding_rate_anomaly',
                        'severity': severity,
                        'funding_rate': funding_rate,
                        'annual_rate': funding_rate * 365 * 3,
                        'description': f"펀딩비 {'과열' if funding_rate > 0 else '급락'}: {funding_rate*100:.3f}%",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"펀딩비 체크 오류: {e}")
        
        return None
    
    async def send_alert(self, anomaly: Dict) -> bool:
        """이상 징후 알림 전송 - 중복 방지 강화"""
        try:
            if not self.telegram_bot:
                return False
            
            # 🔥🔥 크리티컬 뉴스 필터링 강화
            if anomaly.get('type') == 'critical_news':
                # 크리티컬 뉴스 여부 재검증
                if not self._is_critical_bitcoin_news(anomaly):
                    self.logger.info(f"🔄 크리티컬 뉴스 기준 미달로 전송 취소: {anomaly.get('title', '')[:50]}...")
                    return False
                
                # 예상 가격 영향도 계산
                expected_impact = self._calculate_expected_price_impact(anomaly)
                if expected_impact < 0.3:  # 0.3% 미만이면 제외
                    self.logger.info(f"🔄 예상 가격 영향도 미달로 전송 취소: {expected_impact:.1f}%")
                    return False
                
                # 영향도 정보 추가
                anomaly['expected_impact'] = expected_impact
                
                # 뉴스 제목으로 중복 체크
                title = anomaly.get('title', '')
                title_hash = hashlib.md5(title.encode()).hexdigest()
                current_time = datetime.now()
                
                # 이미 전송된 제목인지 확인
                if title_hash in self.sent_news_titles:
                    last_sent = self.sent_news_titles[title_hash]
                    if current_time - last_sent < timedelta(hours=2):
                        self.logger.info(f"🔄 최근 전송된 뉴스 제목 스킵: {title[:50]}...")
                        return False
                
                # 제목 캐시에 추가
                self.sent_news_titles[title_hash] = current_time
                
                # 오래된 캐시 정리
                cutoff_time = current_time - timedelta(hours=6)
                self.sent_news_titles = {
                    h: t for h, t in self.sent_news_titles.items()
                    if t > cutoff_time
                }
            
            # 예외 해시 생성
            exception_hash = self._generate_exception_hash(anomaly)
            
            # 최근 전송 체크
            current_time = datetime.now()
            if anomaly.get('type') in ['short_term_volatility']:
                recent_cutoff = current_time - timedelta(minutes=10)
            else:
                recent_cutoff = current_time - timedelta(minutes=30)
            
            # 캐시에서 최근 전송 확인
            for cached_hash, (cached_time, cached_anomaly) in list(self.exception_content_cache.items()):
                if cached_time < current_time - self.cache_expiry:
                    del self.exception_content_cache[cached_hash]
                    continue
                
                if cached_time > recent_cutoff:
                    if self._is_similar_exception(anomaly, cached_anomaly):
                        self.logger.info(f"🔄 최근 전송된 유사 알림 스킵")
                        return False
            
            # 뉴스 중복 체크
            if anomaly.get('type') == 'critical_news':
                news_content = f"{anomaly.get('title', '')}{anomaly.get('source', '')}"
                news_hash = hashlib.md5(news_content.encode()).hexdigest()
                
                if news_hash in self.news_hashes:
                    last_time = self.news_hashes[news_hash]
                    if datetime.now() - last_time < self.news_cooldown:
                        return False
                
                self.news_hashes[news_hash] = datetime.now()
                
                # 오래된 해시 정리
                cutoff_time = datetime.now() - timedelta(hours=12)
                self.news_hashes = {
                    h: t for h, t in self.news_hashes.items()
                    if t > cutoff_time
                }
            
            # 알림 메시지 생성 (간단하게)
            anomaly_type = anomaly.get('type', 'unknown')
            
            if anomaly_type == 'critical_news':
                expected_impact = anomaly.get('expected_impact', 0)
                message = f"🚨 <b>비트코인 긴급 뉴스</b>\n\n"
                message += f"📰 {anomaly.get('title_ko', anomaly.get('title', ''))}\n"
                
                if expected_impact >= 2.0:
                    message += f"💡 🚀 매우 강한 호재\n"
                    message += f"📊 예상: 상승 {expected_impact:.1f}%"
                elif expected_impact >= 1.0:
                    message += f"💡 📈 강한 호재\n"
                    message += f"📊 예상: 상승 {expected_impact:.1f}%"
                elif expected_impact >= 0.5:
                    message += f"💡 📈 호재\n"
                    message += f"📊 예상: 상승 {expected_impact:.1f}%"
                else:
                    message += f"💡 📊 시장 관심\n"
                    message += f"📊 예상: 약간 상승 {expected_impact:.1f}%"
                
            elif anomaly_type == 'price_anomaly':
                change_24h = anomaly.get('change_24h', 0) * 100
                message = f"📊 <b>BTC {'급등' if change_24h > 0 else '급락'} 알림</b>\n\n"
                message += f"변동률: <b>{change_24h:+.1f}%</b>\n"
                message += f"현재가: <b>${anomaly.get('current_price', 0):,.0f}</b>"
                
            elif anomaly_type == 'volume_anomaly':
                message = f"📈 <b>BTC 거래량 급증</b>\n\n"
                message += f"평균 대비: <b>{anomaly.get('ratio', 0):.1f}배</b>\n"
                message += f"24시간: {anomaly.get('volume_24h', 0):,.0f} BTC"
                
            elif anomaly_type == 'funding_rate_anomaly':
                rate = anomaly.get('funding_rate', 0) * 100
                message = f"💰 <b>BTC 펀딩비 이상</b>\n\n"
                message += f"현재 펀딩비: <b>{rate:.3f}%</b>\n"
                message += f"{'롱 과열' if rate > 0 else '숏 과열'} 상태"
                
            elif anomaly_type == 'short_term_volatility':
                message = f"⚡ <b>BTC 단기 급변동</b>\n\n"
                message += f"{anomaly.get('timeframe', '')} 내 <b>{anomaly.get('change_percent', 0):.1f}%</b> 변동\n"
                message += f"현재가: <b>${anomaly.get('current_price', 0):,.0f}</b>"
                
            else:
                message = f"⚠️ <b>BTC 이상 신호</b>\n\n{anomaly.get('description', '')}"
            
            # 전송
            await self.telegram_bot.send_message(message, parse_mode='HTML')
            
            # 기록
            self.sent_exception_hashes.add(exception_hash)
            self.exception_content_cache[exception_hash] = (current_time, anomaly)
            
            # 크기 제한
            if len(self.sent_exception_hashes) > 500:
                self.sent_exception_hashes = set(list(self.sent_exception_hashes)[-250:])
            
            self.logger.info(f"✅ 예외 알림 전송: {anomaly_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"알림 전송 실패: {e}")
            return False
    
    def _generate_exception_hash(self, anomaly: Dict) -> str:
        """예외 상황의 고유 해시 생성 - 더 엄격하게"""
        anomaly_type = anomaly.get('type', '')
        
        if anomaly_type == 'critical_news':
            title = anomaly.get('title', '').lower()
            # 회사명과 주요 키워드 추출
            companies = []
            for company in ['microstrategy', 'tesla', 'sberbank', 'blackrock', 'gamestop']:
                if company in title:
                    companies.append(company)
            
            # 액션 추출
            actions = []
            for action in ['bought', 'purchased', 'buys', 'adds', 'launches', 'approves']:
                if action in title:
                    actions.append(action)
            
            # 숫자 추출
            numbers = re.findall(r'\d+(?:,\d+)*', title)
            
            # 고유 식별자 생성
            unique_id = f"news_{'-'.join(companies)}_{'-'.join(actions)}_{'-'.join(numbers)}"
            return hashlib.md5(unique_id.encode()).hexdigest()
        
        elif anomaly_type == 'price_anomaly':
            change = anomaly.get('change_24h', 0)
            direction = 'up' if change > 0 else 'down'
            magnitude = int(abs(change * 100) / 1.0)
            return hashlib.md5(f"price_{direction}_{magnitude}".encode()).hexdigest()
        
        elif anomaly_type == 'volume_anomaly':
            volume = anomaly.get('volume_24h', 0)
            scale = int(volume / 10000)
            return hashlib.md5(f"volume_{scale}".encode()).hexdigest()
        
        elif anomaly_type == 'funding_rate_anomaly':
            rate = anomaly.get('funding_rate', 0)
            sign = 'positive' if rate > 0 else 'negative'
            magnitude = int(abs(rate * 10000))
            return hashlib.md5(f"funding_{sign}_{magnitude}".encode()).hexdigest()
        
        elif anomaly_type == 'short_term_volatility':
            change = anomaly.get('change_percent', 0)
            timeframe = anomaly.get('timeframe', '5min')
            magnitude = int(abs(change * 100) / 0.5)
            return hashlib.md5(f"short_vol_{timeframe}_{magnitude}".encode()).hexdigest()
        
        else:
            content = f"{anomaly_type}_{anomaly.get('description', '')}_{anomaly.get('severity', '')}"
            return hashlib.md5(content.encode()).hexdigest()
    
    def _is_similar_exception(self, anomaly1: Dict, anomaly2: Dict) -> bool:
        """두 예외 상황이 유사한지 확인 - 더 엄격하게"""
        if anomaly1.get('type') != anomaly2.get('type'):
            return False
        
        if anomaly1.get('type') == 'critical_news':
            title1 = anomaly1.get('title', '').lower()
            title2 = anomaly2.get('title', '').lower()
            
            # 회사명 체크
            companies1 = set()
            companies2 = set()
            for company in ['microstrategy', 'tesla', 'sberbank', 'blackrock', 'gamestop']:
                if company in title1:
                    companies1.add(company)
                if company in title2:
                    companies2.add(company)
            
            # 같은 회사의 뉴스인지 확인
            if companies1 and companies2 and companies1 == companies2:
                # 액션도 유사한지 확인
                actions1 = set()
                actions2 = set()
                for action in ['bought', 'purchased', 'buys', 'adds', 'launches', 'approves']:
                    if action in title1:
                        actions1.add(action)
                    if action in title2:
                        actions2.add(action)
                
                if actions1 and actions2 and len(actions1 & actions2) > 0:
                    return True
            
            # 단어 유사도 체크
            clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1)
            clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2)
            
            clean1 = re.sub(r'\s+', ' ', clean1).strip()
            clean2 = re.sub(r'\s+', ' ', clean2).strip()
            
            words1 = set(clean1.split())
            words2 = set(clean2.split())
            
            if not words1 or not words2:
                return False
            
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            
            similarity = intersection / union if union > 0 else 0
            
            return similarity > 0.8  # 80% 이상 유사
        
        return False
    
    def _is_on_cooldown(self, alert_type: str, key: str) -> bool:
        """알림 쿨다운 체크"""
        last_alert_key = f"{alert_type}_{key}"
        last_time = self.last_alerts.get(last_alert_key)
        
        if last_time:
            if alert_type in ['short_term_volatility', 'rapid_change']:
                cooldown = timedelta(minutes=10)
            else:
                cooldown = self.alert_cooldown
                
            if datetime.now() - last_time < cooldown:
                return True
        
        return False
    
    def _update_alert_time(self, alert_type: str, key: str):
        """알림 시간 업데이트"""
        last_alert_key = f"{alert_type}_{key}"
        self.last_alerts[last_alert_key] = datetime.now()
        
        # 오래된 알림 기록 정리
        cutoff_time = datetime.now() - timedelta(hours=2)
        self.last_alerts = {
            k: v for k, v in self.last_alerts.items()
            if v > cutoff_time
        }
