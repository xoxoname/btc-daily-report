import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
import hashlib
import re

logger = logging.getLogger(__name__)

class ExceptionDetector:
    """예외 상황 감지 및 알림 - 민감도 향상"""
    
    def __init__(self, bitget_client=None, telegram_bot=None):
        self.bitget_client = bitget_client
        self.telegram_bot = telegram_bot
        self.logger = logging.getLogger('exception_detector')
        
        # 임계값 설정 - 더 민감하게 조정
        self.PRICE_CHANGE_THRESHOLD = 0.6  # 0.6% 이상 변동 (기존 1.0%에서 하향)
        self.VOLUME_SPIKE_THRESHOLD = 2.0  # 평균 대비 2배 (기존 3.0배에서 하향)
        self.FUNDING_RATE_THRESHOLD = 0.008  # 0.8% 이상 (기존 1.0%에서 하향)
        self.LIQUIDATION_THRESHOLD = 8_000_000  # 800만 달러 (기존 1천만에서 하향)
        
        # 마지막 알림 시간 추적 - 쿨다운 시간 단축
        self.last_alerts = {}
        self.alert_cooldown = timedelta(minutes=10)  # 쿨다운 시간 15분→10분으로 단축
        
        # 뉴스 중복 체크를 위한 해시 저장
        self.news_hashes = {}
        self.news_cooldown = timedelta(hours=2)  # 동일 뉴스는 2시간 쿨다운 (기존 4시간에서 단축)
        
        # 전송된 예외 리포트 해시 저장 (영구 중복 방지)
        self.sent_exception_hashes: Set[str] = set()
        
        # 예외 리포트 내용 캐시
        self.exception_content_cache = {}
        self.cache_expiry = timedelta(hours=4)  # 캐시 만료시간 6시간→4시간으로 단축
        
        # 가격 변동 추적 강화
        self.price_history = []  # 최근 가격 이력
        self.max_price_history = 20  # 최대 20개 가격 저장
        
        # 급변동 감지를 위한 짧은 시간 체크
        self.short_term_threshold = 0.4  # 5분 내 0.4% 변동도 감지
        self.medium_term_threshold = 0.8  # 15분 내 0.8% 변동 감지
        
        self.logger.info(f"예외 감지기 초기화 - 민감도 향상: 가격변동 {self.PRICE_CHANGE_THRESHOLD}%, 거래량 {self.VOLUME_SPIKE_THRESHOLD}배, 펀딩비 {self.FUNDING_RATE_THRESHOLD}%")
    
    def _generate_exception_hash(self, anomaly: Dict) -> str:
        """예외 상황의 고유 해시 생성"""
        anomaly_type = anomaly.get('type', '')
        
        if anomaly_type == 'critical_news':
            # 뉴스는 제목과 소스로 해시 생성
            title = anomaly.get('title', '').lower()
            source = anomaly.get('source', '').lower()
            
            # 숫자와 특수문자 제거하여 유사한 뉴스 감지
            clean_title = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            # 회사명 추출
            companies = ['gamestop', 'tesla', 'microstrategy', 'metaplanet', '게임스탑', '테슬라', '메타플래닛', 'trump', '트럼프']
            found_companies = [c for c in companies if c in clean_title]
            
            # 키워드 추출
            keywords = ['bitcoin', 'btc', 'purchase', 'bought', 'buys', '구매', '매입', 'china', 'trade', 'fed', 'rate']
            found_keywords = [k for k in keywords if k in clean_title]
            
            # 회사명과 키워드로 해시 생성
            if found_companies and found_keywords:
                hash_content = f"{','.join(sorted(found_companies))}_{','.join(sorted(found_keywords))}"
            else:
                hash_content = clean_title
            
            return hashlib.md5(f"news_{hash_content}_{source}".encode()).hexdigest()
        
        elif anomaly_type == 'price_anomaly':
            # 가격 변동은 방향과 크기로 해시 - 더 세밀하게
            change = anomaly.get('change_24h', 0)
            direction = 'up' if change > 0 else 'down'
            magnitude = int(abs(change * 100) / 0.5)  # 0.5% 단위로 그룹화 (더 세밀)
            return hashlib.md5(f"price_{direction}_{magnitude}".encode()).hexdigest()
        
        elif anomaly_type == 'volume_anomaly':
            # 거래량은 대략적인 규모로 해시
            volume = anomaly.get('volume_24h', 0)
            scale = int(volume / 5000)  # 5000 단위로 그룹화 (더 세밀)
            return hashlib.md5(f"volume_{scale}".encode()).hexdigest()
        
        elif anomaly_type == 'funding_rate_anomaly':
            # 펀딩비는 부호와 크기로 해시
            rate = anomaly.get('funding_rate', 0)
            sign = 'positive' if rate > 0 else 'negative'
            magnitude = int(abs(rate * 10000))  # 0.0001 단위로 그룹화 (더 세밀)
            return hashlib.md5(f"funding_{sign}_{magnitude}".encode()).hexdigest()
        
        elif anomaly_type == 'short_term_volatility':
            # 단기 변동성 - 신규 추가
            change = anomaly.get('change_percent', 0)
            timeframe = anomaly.get('timeframe', '5min')
            magnitude = int(abs(change * 100) / 0.2)  # 0.2% 단위로 그룹화
            return hashlib.md5(f"short_vol_{timeframe}_{magnitude}".encode()).hexdigest()
        
        else:
            # 기타 타입은 전체 내용으로 해시
            content = f"{anomaly_type}_{anomaly.get('description', '')}_{anomaly.get('severity', '')}"
            return hashlib.md5(content.encode()).hexdigest()
    
    def _is_similar_exception(self, anomaly1: Dict, anomaly2: Dict) -> bool:
        """두 예외 상황이 유사한지 확인"""
        if anomaly1.get('type') != anomaly2.get('type'):
            return False
        
        if anomaly1.get('type') == 'critical_news':
            # 뉴스는 제목 유사도로 판단
            title1 = anomaly1.get('title', '').lower()
            title2 = anomaly2.get('title', '').lower()
            
            # 숫자 제거
            clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1)
            clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2)
            
            clean1 = re.sub(r'\s+', ' ', clean1).strip()
            clean2 = re.sub(r'\s+', ' ', clean2).strip()
            
            # 단어 집합 비교
            words1 = set(clean1.split())
            words2 = set(clean2.split())
            
            if not words1 or not words2:
                return False
            
            # 교집합 비율 계산
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            
            similarity = intersection / union if union > 0 else 0
            
            # 60% 이상 유사하면 같은 것으로 간주 (기존 70%에서 완화)
            return similarity > 0.6
        
        return False
    
    async def detect_all_anomalies(self) -> List[Dict]:
        """모든 이상 징후 감지 - 단기 변동성 추가"""
        anomalies = []
        
        try:
            # 단기 변동성 체크 (신규 추가)
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
            
            # 가격 급변동 체크 (신규 추가)
            rapid_change_anomaly = await self.check_rapid_price_change()
            if rapid_change_anomaly:
                anomalies.append(rapid_change_anomaly)
                
        except Exception as e:
            self.logger.error(f"이상 징후 감지 중 오류: {e}")
        
        return anomalies
    
    async def check_short_term_volatility(self) -> Optional[Dict]:
        """단기 변동성 감지 (5분, 15분 단위) - 신규 추가"""
        try:
            if not self.bitget_client:
                return None
            
            # 현재 가격 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            current_price = float(ticker.get('last', 0))
            current_time = datetime.now()
            
            # 가격 이력에 추가
            self.price_history.append({
                'price': current_price,
                'time': current_time
            })
            
            # 오래된 이력 제거 (20분 이상)
            cutoff_time = current_time - timedelta(minutes=20)
            self.price_history = [
                p for p in self.price_history 
                if p['time'] > cutoff_time
            ]
            
            if len(self.price_history) < 3:  # 최소 3개 데이터 필요
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
                change_5min = ((max_price_5min - min_price_5min) / min_price_5min) * 100
                
                # 5분 내 0.4% 이상 변동
                if change_5min >= self.short_term_threshold:
                    key = f"short_vol_5min_{current_price}"
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
            
            # 15분 전 가격과 비교
            fifteen_min_ago = current_time - timedelta(minutes=15)
            fifteen_min_prices = [
                p['price'] for p in self.price_history 
                if p['time'] >= fifteen_min_ago
            ]
            
            if len(fifteen_min_prices) >= 3:
                min_price_15min = min(fifteen_min_prices)
                max_price_15min = max(fifteen_min_prices)
                change_15min = ((max_price_15min - min_price_15min) / min_price_15min) * 100
                
                # 15분 내 0.8% 이상 변동
                if change_15min >= self.medium_term_threshold:
                    key = f"short_vol_15min_{current_price}"
                    if not self._is_on_cooldown('short_term_volatility', key):
                        self._update_alert_time('short_term_volatility', key)
                        
                        return {
                            'type': 'short_term_volatility',
                            'severity': 'medium',
                            'timeframe': '15분',
                            'change_percent': change_15min,
                            'min_price': min_price_15min,
                            'max_price': max_price_15min,
                            'current_price': current_price,
                            'description': f"15분 내 {change_15min:.1f}% 변동",
                            'timestamp': current_time
                        }
            
        except Exception as e:
            self.logger.error(f"단기 변동성 체크 오류: {e}")
        
        return None
    
    async def check_rapid_price_change(self) -> Optional[Dict]:
        """급속한 가격 변화 감지 - 신규 추가"""
        try:
            if not self.bitget_client or len(self.price_history) < 5:
                return None
            
            current_time = datetime.now()
            current_price = self.price_history[-1]['price']
            
            # 최근 2분 내 가격 변화 체크
            two_min_ago = current_time - timedelta(minutes=2)
            recent_prices = [
                p['price'] for p in self.price_history 
                if p['time'] >= two_min_ago
            ]
            
            if len(recent_prices) >= 3:
                # 연속적인 상승/하락 패턴 감지
                ascending = all(recent_prices[i] <= recent_prices[i+1] for i in range(len(recent_prices)-1))
                descending = all(recent_prices[i] >= recent_prices[i+1] for i in range(len(recent_prices)-1))
                
                if ascending or descending:
                    total_change = ((recent_prices[-1] - recent_prices[0]) / recent_prices[0]) * 100
                    
                    # 2분 내 0.3% 이상 연속 변동
                    if abs(total_change) >= 0.3:
                        direction = "상승" if ascending else "하락"
                        key = f"rapid_change_{direction}_{current_price}"
                        
                        if not self._is_on_cooldown('rapid_change', key):
                            self._update_alert_time('rapid_change', key)
                            
                            return {
                                'type': 'rapid_price_change',
                                'severity': 'high' if abs(total_change) >= 0.5 else 'medium',
                                'direction': direction,
                                'change_percent': total_change,
                                'timeframe': '2분',
                                'start_price': recent_prices[0],
                                'end_price': recent_prices[-1],
                                'description': f"2분 내 연속 {direction} {abs(total_change):.1f}%",
                                'timestamp': current_time
                            }
            
        except Exception as e:
            self.logger.error(f"급속 변화 체크 오류: {e}")
        
        return None
    
    async def check_price_volatility(self) -> Optional[Dict]:
        """가격 급변동 감지 - 임계값 낮춤"""
        try:
            if not self.bitget_client:
                return None
            
            # 현재 가격 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            current_price = float(ticker.get('last', 0))
            change_24h = float(ticker.get('changeUtc', 0))
            
            # 24시간 변동률이 임계값 초과 (0.6%로 하향)
            if abs(change_24h) >= self.PRICE_CHANGE_THRESHOLD:
                key = f"price_{int(current_price/100)*100}"  # 100달러 단위로 그룹화
                if not self._is_on_cooldown('price_volatility', key):
                    self._update_alert_time('price_volatility', key)
                    
                    # 심각도 조정 - 더 민감하게
                    severity = 'critical' if abs(change_24h) >= 2.0 else 'high' if abs(change_24h) >= 1.0 else 'medium'
                    
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
        """거래량 이상 감지 - 임계값 낮춤"""
        try:
            if not self.bitget_client:
                return None
            
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            volume_24h = float(ticker.get('baseVolume', 0))
            
            # 거래량이 특정 임계값 초과 (임시로 40000 BTC 기준, 2배로 낮춤)
            threshold_volume = 40000 * self.VOLUME_SPIKE_THRESHOLD  # 80000 BTC
            if volume_24h > threshold_volume:
                key = f"volume_{int(volume_24h/10000)*10000}"  # 10000 단위로 그룹화
                if not self._is_on_cooldown('volume_anomaly', key):
                    self._update_alert_time('volume_anomaly', key)
                    
                    return {
                        'type': 'volume_anomaly',
                        'severity': 'critical' if volume_24h > threshold_volume * 1.5 else 'high',
                        'volume_24h': volume_24h,
                        'ratio': volume_24h / 40000,
                        'threshold': threshold_volume,
                        'description': f"거래량 급증: {volume_24h:,.0f} BTC ({volume_24h/40000:.1f}배)",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"거래량 체크 오류: {e}")
        
        return None
    
    async def check_funding_rate(self) -> Optional[Dict]:
        """펀딩비 이상 감지 - 임계값 낮춤"""
        try:
            if not self.bitget_client:
                return None
            
            funding_data = await self.bitget_client.get_funding_rate('BTCUSDT')
            if not funding_data:
                return None
            
            # API가 리스트를 반환하는 경우 처리
            if isinstance(funding_data, list):
                if len(funding_data) > 0:
                    funding_data = funding_data[0]
                else:
                    return None
            
            funding_rate = float(funding_data.get('fundingRate', 0))
            
            # 펀딩비가 임계값 초과 (0.8%로 하향)
            if abs(funding_rate) >= self.FUNDING_RATE_THRESHOLD:
                key = f"funding_{int(abs(funding_rate)*10000)}"  # 0.0001 단위로 그룹화
                if not self._is_on_cooldown('funding_rate', key):
                    self._update_alert_time('funding_rate', key)
                    
                    # 심각도 조정 - 더 민감하게
                    severity = 'critical' if abs(funding_rate) >= 0.02 else 'high' if abs(funding_rate) >= 0.012 else 'medium'
                    
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
        """이상 징후 알림 전송 - 비트코인 관련성 필터링 강화"""
        try:
            if not self.telegram_bot:
                return False
            
            # 비트코인 관련성 체크 - 뉴스 타입만
            if anomaly.get('type') == 'critical_news':
                title = anomaly.get('title', '')
                impact = anomaly.get('impact', '')
                
                # 비트코인과 무관한 뉴스는 알림 생략
                if '비트코인 무관' in impact or '알트코인 (BTC 무관)' in impact:
                    self.logger.info(f"🔄 비트코인 무관 뉴스 알림 생략: {title[:30]}...")
                    return False
                
                # 트럼프 뉴스 중 비트코인 관련성 없는 것 생략
                if 'trump' in title.lower() or '트럼프' in title:
                    if '비트코인 무관' in impact:
                        self.logger.info(f"🔄 트럼프 비관련 뉴스 알림 생략: {title[:30]}...")
                        return False
            
            # 예외 해시 생성
            exception_hash = self._generate_exception_hash(anomaly)
            
            # 이미 전송된 예외인지 확인 - 시간 기반 체크 추가
            current_time = datetime.now()
            
            # 단기 변동성은 더 자주 알림 허용
            if anomaly.get('type') in ['short_term_volatility', 'rapid_price_change']:
                # 5분 쿨다운
                recent_cutoff = current_time - timedelta(minutes=5)
            else:
                # 10분 쿨다운
                recent_cutoff = current_time - timedelta(minutes=10)
            
            # 최근 알림된 해시 중에서 시간이 지난 것들 제거
            recent_hashes = {
                h for h, (cached_time, _) in self.exception_content_cache.items()
                if cached_time > recent_cutoff
            }
            
            if exception_hash in recent_hashes:
                self.logger.info(f"🔄 최근 전송된 예외 리포트 스킵: {anomaly.get('title', anomaly.get('description', ''))[:30]}...")
                return False
            
            # 캐시에 있는 내용과 비교
            for cached_hash, (cached_time, cached_anomaly) in list(self.exception_content_cache.items()):
                # 만료된 캐시 삭제
                if current_time - cached_time > self.cache_expiry:
                    del self.exception_content_cache[cached_hash]
                    continue
                
                # 유사한 예외인지 확인
                if self._is_similar_exception(anomaly, cached_anomaly):
                    self.logger.info(f"🔄 유사한 예외 리포트 스킵: {anomaly.get('title', anomaly.get('description', ''))[:30]}...")
                    return False
            
            # 뉴스 타입인 경우 추가 중복 체크
            if anomaly.get('type') == 'critical_news':
                # 뉴스 내용으로 해시 생성
                news_content = f"{anomaly.get('title', '')}{anomaly.get('source', '')}"
                news_hash = hashlib.md5(news_content.encode()).hexdigest()
                
                # 중복 체크 - 2시간으로 단축
                if news_hash in self.news_hashes:
                    last_time = self.news_hashes[news_hash]
                    if datetime.now() - last_time < self.news_cooldown:
                        self.logger.info(f"중복 뉴스 알림 스킵: {anomaly.get('title', '')[:30]}...")
                        return False
                
                # 해시 저장
                self.news_hashes[news_hash] = datetime.now()
                
                # 오래된 해시 정리
                cutoff_time = datetime.now() - timedelta(hours=6)  # 6시간으로 단축
                self.news_hashes = {
                    h: t for h, t in self.news_hashes.items()
                    if t > cutoff_time
                }
            
            # 알림 메시지 생성 - 더 상세하게
            severity_emoji = {
                'critical': '🚨',
                'high': '⚠️',
                'medium': '📊'
            }
            
            emoji = severity_emoji.get(anomaly.get('severity', 'medium'), '📊')
            anomaly_type = anomaly.get('type', 'unknown')
            
            # 타입별 메시지 생성
            if anomaly_type == 'critical_news':
                impact = anomaly.get('impact', '')
                title = anomaly.get('title', '')
                
                # 비트코인 관련성 표시
                bitcoin_relevance = ""
                if '비트코인 무관' in impact:
                    bitcoin_relevance = " (BTC 무관)"
                elif '알트코인' in impact:
                    bitcoin_relevance = " (알트코인)"
                elif any(word in title.lower() for word in ['bitcoin', 'btc', '비트코인']):
                    bitcoin_relevance = " (BTC 직접)"
                else:
                    bitcoin_relevance = " (간접 영향)"
                
                message = f"{emoji} <b>중요 뉴스{bitcoin_relevance}</b>\n\n"
                message += f"📰 제목: {title[:80]}{'...' if len(title) > 80 else ''}\n"
                message += f"📊 영향: {impact}\n"
                message += f"📈 예상 변동: {anomaly.get('expected_change', '±0.3%')}\n"
                message += f"📍 출처: {anomaly.get('source', 'Unknown')[:30]}\n"
                message += f"⏰ 시간: {anomaly.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"
                
            elif anomaly_type == 'short_term_volatility':
                message = f"{emoji} <b>단기 급변동 감지</b>\n\n"
                message += f"📊 {anomaly.get('timeframe', '')} 내 <b>{anomaly.get('change_percent', 0):.1f}%</b> 변동\n"
                message += f"💰 현재가: <b>${anomaly.get('current_price', 0):,.0f}</b>\n"
                message += f"📈 최고: ${anomaly.get('max_price', 0):,.0f}\n"
                message += f"📉 최저: ${anomaly.get('min_price', 0):,.0f}\n"
                message += f"⏰ 감지시간: {anomaly.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"
                
            elif anomaly_type == 'rapid_price_change':
                message = f"{emoji} <b>연속 {anomaly.get('direction', '')} 감지</b>\n\n"
                message += f"📊 {anomaly.get('timeframe', '')} 내 <b>{abs(anomaly.get('change_percent', 0)):.1f}%</b> {anomaly.get('direction', '')}\n"
                message += f"📍 시작가: ${anomaly.get('start_price', 0):,.0f}\n"
                message += f"💰 현재가: <b>${anomaly.get('end_price', 0):,.0f}</b>\n"
                message += f"⏰ 감지시간: {anomaly.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"
                
            elif anomaly_type == 'price_anomaly':
                change_24h = anomaly.get('change_24h', 0) * 100
                message = f"{emoji} <b>24시간 {'급등' if change_24h > 0 else '급락'}</b>\n\n"
                message += f"📊 변동률: <b>{change_24h:+.1f}%</b>\n"
                message += f"💰 현재가: <b>${anomaly.get('current_price', 0):,.0f}</b>\n"
                message += f"⏰ 감지시간: {anomaly.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"
                
            elif anomaly_type == 'volume_anomaly':
                message = f"{emoji} <b>거래량 급증</b>\n\n"
                message += f"📊 24시간 거래량: <b>{anomaly.get('volume_24h', 0):,.0f} BTC</b>\n"
                message += f"📈 평균 대비: <b>{anomaly.get('ratio', 0):.1f}배</b>\n"
                message += f"⚠️ 임계값: {anomaly.get('threshold', 0):,.0f} BTC\n"
                message += f"⏰ 감지시간: {anomaly.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"
                
            elif anomaly_type == 'funding_rate_anomaly':
                rate = anomaly.get('funding_rate', 0) * 100
                annual = anomaly.get('annual_rate', 0) * 100
                message = f"{emoji} <b>펀딩비 이상</b>\n\n"
                message += f"📊 현재 펀딩비: <b>{rate:.3f}%</b>\n"
                message += f"📈 연환산: <b>{annual:+.1f}%</b>\n"
                message += f"🎯 {'롱 과열' if rate > 0 else '숏 과열'} 상태\n"
                message += f"⏰ 감지시간: {anomaly.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"
                
            else:
                # 기본 포맷
                message = f"{emoji} <b>예외 상황 감지</b>\n\n"
                message += f"유형: {anomaly_type}\n"
                message += f"설명: {anomaly.get('description', '설명 없음')}\n"
                message += f"심각도: {anomaly.get('severity', 'medium')}\n"
                message += f"시간: {anomaly.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 전송 성공 시 기록
            await self.telegram_bot.send_message(message, parse_mode='HTML')
            
            # 전송 성공 기록
            self.sent_exception_hashes.add(exception_hash)
            self.exception_content_cache[exception_hash] = (current_time, anomaly)
            
            # 해시 세트가 너무 커지면 정리 (최대 1000개)
            if len(self.sent_exception_hashes) > 1000:
                # 가장 오래된 500개 제거
                self.sent_exception_hashes = set(list(self.sent_exception_hashes)[-500:])
            
            self.logger.info(f"✅ 예외 리포트 전송 완료: {anomaly.get('title', anomaly.get('description', ''))[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"알림 전송 실패: {e}")
            return False
    
    def _is_on_cooldown(self, alert_type: str, key: str) -> bool:
        """알림 쿨다운 체크 - 타입별 다른 쿨다운"""
        last_alert_key = f"{alert_type}_{key}"
        last_time = self.last_alerts.get(last_alert_key)
        
        if last_time:
            # 단기 변동성은 더 짧은 쿨다운
            if alert_type in ['short_term_volatility', 'rapid_change']:
                cooldown = timedelta(minutes=5)
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
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.last_alerts = {
            k: v for k, v in self.last_alerts.items()
            if v > cutoff_time
        }
