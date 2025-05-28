import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
import hashlib
import re

logger = logging.getLogger(__name__)

class ExceptionDetector:
    """예외 상황 감지 및 알림"""
    
    def __init__(self, bitget_client=None, telegram_bot=None):
        self.bitget_client = bitget_client
        self.telegram_bot = telegram_bot
        self.logger = logging.getLogger('exception_detector')
        
        # 임계값 설정
        self.PRICE_CHANGE_THRESHOLD = 1.0  # 1% 이상 변동
        self.VOLUME_SPIKE_THRESHOLD = 3.0  # 평균 대비 3배
        self.FUNDING_RATE_THRESHOLD = 0.01  # 1% 이상
        self.LIQUIDATION_THRESHOLD = 10_000_000  # 1천만 달러
        
        # 마지막 알림 시간 추적
        self.last_alerts = {}
        self.alert_cooldown = timedelta(minutes=15)  # 쿨다운 시간 증가
        
        # 뉴스 중복 체크를 위한 해시 저장
        self.news_hashes = {}
        self.news_cooldown = timedelta(hours=4)  # 동일 뉴스는 4시간 쿨다운
        
        # 전송된 예외 리포트 해시 저장 (영구 중복 방지)
        self.sent_exception_hashes: Set[str] = set()
        
        # 예외 리포트 내용 캐시
        self.exception_content_cache = {}
        self.cache_expiry = timedelta(hours=6)
    
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
            companies = ['gamestop', 'tesla', 'microstrategy', 'metaplanet', '게임스탑', '테슬라', '메타플래닛']
            found_companies = [c for c in companies if c in clean_title]
            
            # 키워드 추출
            keywords = ['bitcoin', 'btc', 'purchase', 'bought', 'buys', '구매', '매입']
            found_keywords = [k for k in keywords if k in clean_title]
            
            # 회사명과 키워드로 해시 생성
            if found_companies and found_keywords:
                hash_content = f"{','.join(sorted(found_companies))}_{','.join(sorted(found_keywords))}"
            else:
                hash_content = clean_title
            
            return hashlib.md5(f"news_{hash_content}_{source}".encode()).hexdigest()
        
        elif anomaly_type == 'price_anomaly':
            # 가격 변동은 방향과 크기로 해시
            change = anomaly.get('change_24h', 0)
            direction = 'up' if change > 0 else 'down'
            magnitude = int(abs(change))  # 정수로 변환하여 비슷한 변동률 그룹화
            return hashlib.md5(f"price_{direction}_{magnitude}".encode()).hexdigest()
        
        elif anomaly_type == 'volume_anomaly':
            # 거래량은 대략적인 규모로 해시
            volume = anomaly.get('volume_24h', 0)
            scale = int(volume / 10000)  # 10000 단위로 그룹화
            return hashlib.md5(f"volume_{scale}".encode()).hexdigest()
        
        elif anomaly_type == 'funding_rate_anomaly':
            # 펀딩비는 부호와 크기로 해시
            rate = anomaly.get('funding_rate', 0)
            sign = 'positive' if rate > 0 else 'negative'
            magnitude = int(abs(rate * 1000))  # 0.001 단위로 그룹화
            return hashlib.md5(f"funding_{sign}_{magnitude}".encode()).hexdigest()
        
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
            
            # 70% 이상 유사하면 같은 것으로 간주
            return similarity > 0.7
        
        return False
    
    async def detect_all_anomalies(self) -> List[Dict]:
        """모든 이상 징후 감지"""
        anomalies = []
        
        try:
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
    
    async def check_price_volatility(self) -> Optional[Dict]:
        """가격 급변동 감지"""
        try:
            if not self.bitget_client:
                return None
            
            # 현재 가격 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            current_price = float(ticker.get('last', 0))
            change_24h = float(ticker.get('changeUtc', 0))
            
            # 24시간 변동률이 임계값 초과
            if abs(change_24h) >= self.PRICE_CHANGE_THRESHOLD:
                key = f"price_{current_price}"
                if not self._is_on_cooldown('price_volatility', key):
                    self._update_alert_time('price_volatility', key)
                    
                    return {
                        'type': 'price_anomaly',
                        'severity': 'critical' if abs(change_24h) >= 3 else 'high',
                        'current_price': current_price,
                        'change_24h': change_24h,
                        'description': f"BTC {'급등' if change_24h > 0 else '급락'} {abs(change_24h):.1f}%",
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
            
            volume_24h = float(ticker.get('baseVolume', 0))
            
            # 거래량이 특정 임계값 초과 (임시로 50000 BTC 기준)
            if volume_24h > 50000 * self.VOLUME_SPIKE_THRESHOLD:
                key = f"volume_{volume_24h}"
                if not self._is_on_cooldown('volume_anomaly', key):
                    self._update_alert_time('volume_anomaly', key)
                    
                    return {
                        'type': 'volume_anomaly',
                        'severity': 'high',
                        'volume_24h': volume_24h,
                        'ratio': volume_24h / 50000,
                        'description': f"거래량 급증: {volume_24h:,.0f} BTC",
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
            
            # API가 리스트를 반환하는 경우 처리
            if isinstance(funding_data, list):
                if len(funding_data) > 0:
                    funding_data = funding_data[0]
                else:
                    return None
            
            funding_rate = float(funding_data.get('fundingRate', 0))
            
            # 펀딩비가 임계값 초과
            if abs(funding_rate) >= self.FUNDING_RATE_THRESHOLD:
                key = f"funding_{funding_rate}"
                if not self._is_on_cooldown('funding_rate', key):
                    self._update_alert_time('funding_rate', key)
                    
                    return {
                        'type': 'funding_rate_anomaly',
                        'severity': 'high' if abs(funding_rate) >= 0.05 else 'medium',
                        'funding_rate': funding_rate,
                        'annual_rate': funding_rate * 365 * 3,
                        'description': f"펀딩비 이상: {funding_rate:.4f}%",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"펀딩비 체크 오류: {e}")
        
        return None
    
    async def send_alert(self, anomaly: Dict) -> bool:
        """이상 징후 알림 전송 - 강화된 중복 체크"""
        try:
            if not self.telegram_bot:
                return False
            
            # 예외 해시 생성
            exception_hash = self._generate_exception_hash(anomaly)
            
            # 이미 전송된 예외인지 확인
            if exception_hash in self.sent_exception_hashes:
                self.logger.info(f"🔄 이미 전송된 예외 리포트 스킵: {anomaly.get('title', anomaly.get('description', ''))[:30]}...")
                return False
            
            # 캐시에 있는 내용과 비교
            current_time = datetime.now()
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
                
                # 중복 체크
                if news_hash in self.news_hashes:
                    last_time = self.news_hashes[news_hash]
                    if datetime.now() - last_time < self.news_cooldown:
                        self.logger.info(f"중복 뉴스 알림 스킵: {anomaly.get('title', '')[:30]}...")
                        return False
                
                # 해시 저장
                self.news_hashes[news_hash] = datetime.now()
                
                # 오래된 해시 정리
                cutoff_time = datetime.now() - timedelta(hours=12)
                self.news_hashes = {
                    h: t for h, t in self.news_hashes.items()
                    if t > cutoff_time
                }
            
            # 알림 메시지 생성
            severity_emoji = {
                'critical': '🚨',
                'high': '⚠️',
                'medium': '📊'
            }
            
            emoji = severity_emoji.get(anomaly.get('severity', 'medium'), '📊')
            
            message = f"{emoji} 예외 상황 감지\n\n"
            message += f"유형: {anomaly.get('type', 'unknown')}\n"
            message += f"설명: {anomaly.get('description', '설명 없음')}\n"
            message += f"심각도: {anomaly.get('severity', 'medium')}\n"
            message += f"시간: {anomaly.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 전송 성공 시 기록
            await self.telegram_bot.send_message(message)
            
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
        """알림 쿨다운 체크"""
        last_alert_key = f"{alert_type}_{key}"
        last_time = self.last_alerts.get(last_alert_key)
        
        if last_time:
            if datetime.now() - last_time < self.alert_cooldown:
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
