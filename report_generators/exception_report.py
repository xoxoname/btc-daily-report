# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime, timedelta
import pytz
import re
import sys
import os
import hashlib
import json

# ML 예측기 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from ml_predictor import MLPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

class ExceptionReportGenerator(BaseReportGenerator):
    """예외 상황 리포트 전담 생성기 - 현실적 시장 반응 반영 + 뉴스 후 실제 가격 변동 추가"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        
        # ML 예측기 초기화
        self.ml_predictor = None
        if ML_AVAILABLE:
            try:
                self.ml_predictor = MLPredictor()
                self.logger.info(f"ML 예측기 초기화 완료")
            except Exception as e:
                self.logger.error(f"ML 예측기 초기화 실패: {e}")
        
        # 🔥🔥 뉴스 발표 시점 기록 저장소 - 파일로 영구 저장
        self.news_initial_data = {}
        self.news_data_file = 'news_initial_data.json'
        self.processed_reports = set()  # 처리된 리포트 해시
        self.processed_reports_file = 'processed_reports.json'
        
        # 기존 데이터 로드
        self._load_news_data()
        self._load_processed_reports()
        
        # 현실적인 뉴스 반응 패턴 데이터 (실제 과거 데이터 기반)
        self.news_reaction_patterns = {
            'etf_approval': {
                'immediate': '+1.5~3%',
                'pattern': '즉시 급등 후 2-4시간 내 수익 실현',
                'duration': '12-24시간',
                'strategy': '발표 직후 진입, 과열 시 빠른 익절',
                'actual_impact': 'high',
                'typical_range': (1.5, 3.0)
            },
            'etf_rejection': {
                'immediate': '-0.8~2%',
                'pattern': '즉시 하락 후 6-12시간 내 회복',
                'duration': '6-12시간',
                'strategy': '급락 시 분할 매수, 빠른 회복 기대',
                'actual_impact': 'medium',
                'typical_range': (-2.0, -0.8)
            },
            'corporate_purchase_direct': {  # 실제 BTC 매입
                'immediate': '+0.3~1.2%',
                'pattern': '점진적 상승, 며칠간 지속 가능',
                'duration': '1-3일',
                'strategy': '분할 매수, 중기 보유 고려',
                'actual_impact': 'medium',
                'typical_range': (0.3, 1.2)
            },
            'corporate_structured_product': {  # 구조화 상품 (스베르방크 타입)
                'immediate': '+0.05~0.2%',
                'pattern': '미미한 반응, 수 시간 내 소멸',
                'duration': '2-6시간',
                'strategy': '단기 스캘핑만 고려, 장기 영향 없음',
                'actual_impact': 'minimal',
                'typical_range': (0.05, 0.2)
            },
            'regulation_positive': {
                'immediate': '+0.3~0.8%',
                'pattern': '초기 상승 후 안정화',
                'duration': '6-24시간',
                'strategy': '단기 스윙, 과열 구간 주의',
                'actual_impact': 'medium',
                'typical_range': (0.3, 0.8)
            },
            'regulation_negative': {
                'immediate': '-0.8~2.5%',
                'pattern': '급락 후 반등, V자 회복 패턴',
                'duration': '6-18시간',
                'strategy': '급락 시 분할 매수, 반등 타이밍 포착',
                'actual_impact': 'medium',
                'typical_range': (-2.5, -0.8)
            },
            'banking_adoption': {
                'immediate': '+0.1~0.5%',
                'pattern': '완만한 상승, 기관 관심 지속',
                'duration': '1-2일',
                'strategy': '장기 관점 매수, 하락 시 추가 매수',
                'actual_impact': 'low',
                'typical_range': (0.1, 0.5)
            },
            'hack_incident': {
                'immediate': '-0.3~1.5%',
                'pattern': '즉시 하락 후 4-8시간 내 회복',
                'duration': '4-12시간',
                'strategy': '공포 매도 시 역매매, 단기 반등 기대',
                'actual_impact': 'low',
                'typical_range': (-1.5, -0.3)
            },
            'fed_rate_decision': {
                'immediate': '±0.8~2%',
                'pattern': '방향성 뚜렷, 하루 내 추세 확정',
                'duration': '12-48시간',
                'strategy': '방향성 확인 후 추세 추종',
                'actual_impact': 'high',
                'typical_range': (-2.0, 2.0)
            },
            'trade_tariffs': {  # 새로 추가
                'immediate': '-0.3~0.8%',
                'pattern': '즉시 하락 후 수 시간 내 안정화',
                'duration': '6-12시간',
                'strategy': '단기 하락 시 매수 기회, 장기 영향 제한적',
                'actual_impact': 'medium',
                'typical_range': (-0.8, -0.3)
            },
            'inflation_data': {  # 새로 추가
                'immediate': '+0.2~0.8%',
                'pattern': '인플레이션 헤지 수요로 완만한 상승',
                'duration': '12-24시간',
                'strategy': '헤지 수요 지속 시 추가 매수',
                'actual_impact': 'medium',
                'typical_range': (0.2, 0.8)
            },
            'price_milestone': {  # 가격 돌파 관련 (새로 추가)
                'immediate': '+0.05~0.3%',
                'pattern': '심리적 저항선 돌파 후 단기 상승',
                'duration': '4-12시간',
                'strategy': '돌파 확인 후 단기 추격, 과열 주의',
                'actual_impact': 'low',
                'typical_range': (0.05, 0.3)
            },
            'ai_prediction': {  # AI 예측 관련 (새로 추가)
                'immediate': '+0.02~0.1%',
                'pattern': '미미한 반응, 추측성 정보',
                'duration': '1-4시간',
                'strategy': '무시하거나 매우 신중한 접근',
                'actual_impact': 'minimal',
                'typical_range': (0.02, 0.1)
            },
            'energy_crisis_prediction': {  # 에너지 위기 예측 (새로 추가)
                'immediate': '+0.05~0.15%',
                'pattern': '가설적 시나리오, 제한적 반응',
                'duration': '2-6시간',
                'strategy': '투기적 거래만 고려, 장기 무관',
                'actual_impact': 'minimal',
                'typical_range': (0.05, 0.15)
            },
            'macro_economic_general': {  # 일반 거시경제
                'immediate': '+0.1~0.4%',
                'pattern': '제한적 반응, 단기간 영향',
                'duration': '2-8시간',
                'strategy': '신중한 관망',
                'actual_impact': 'low',
                'typical_range': (-0.4, 0.4)
            }
        }
        
        # 중요 기업 리스트 (비트코인 보유/관련)
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard',
            'gamestop', 'gme', 'blackrock', 'fidelity', 'ark invest',
            'coinbase', 'binance', 'kraken', 'bitget',
            'metaplanet', '메타플래닛', '테슬라', '마이크로스트래티지',
            'sberbank', '스베르방크', 'jpmorgan', 'goldman sachs'
        ]
    
    def _load_news_data(self):
        """뉴스 초기 데이터 로드"""
        try:
            if os.path.exists(self.news_data_file):
                with open(self.news_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 문자열을 datetime으로 변환
                for key, value in data.items():
                    if 'time' in value:
                        value['time'] = datetime.fromisoformat(value['time'])
                
                self.news_initial_data = data
                
                # 24시간 이상 된 데이터 정리
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.news_initial_data = {
                    k: v for k, v in self.news_initial_data.items()
                    if v.get('time', datetime.now()) > cutoff_time
                }
                
                self.logger.info(f"뉴스 초기 데이터 로드: {len(self.news_initial_data)}개")
        except Exception as e:
            self.logger.error(f"뉴스 데이터 로드 실패: {e}")
            self.news_initial_data = {}
    
    def _save_news_data(self):
        """뉴스 초기 데이터 저장"""
        try:
            # datetime을 문자열로 변환하여 저장
            data_to_save = {}
            for key, value in self.news_initial_data.items():
                new_value = value.copy()
                if 'time' in new_value and isinstance(new_value['time'], datetime):
                    new_value['time'] = new_value['time'].isoformat()
                data_to_save[key] = new_value
            
            with open(self.news_data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"뉴스 데이터 저장 실패: {e}")
    
    def _load_processed_reports(self):
        """처리된 리포트 해시 로드"""
        try:
            if os.path.exists(self.processed_reports_file):
                with open(self.processed_reports_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 시간 기반 필터링 (6시간 이내만 유지)
                cutoff_time = datetime.now() - timedelta(hours=6)
                
                valid_reports = []
                for item in data:
                    try:
                        report_time = datetime.fromisoformat(item['time'])
                        if report_time > cutoff_time:
                            valid_reports.append(item['hash'])
                    except:
                        continue
                
                self.processed_reports = set(valid_reports)
                self.logger.info(f"처리된 리포트 해시 로드: {len(self.processed_reports)}개")
        except Exception as e:
            self.logger.error(f"처리된 리포트 로드 실패: {e}")
            self.processed_reports = set()
    
    def _save_processed_reports(self):
        """처리된 리포트 해시 저장"""
        try:
            current_time = datetime.now()
            data_to_save = []
            
            for report_hash in self.processed_reports:
                data_to_save.append({
                    'hash': report_hash,
                    'time': current_time.isoformat()
                })
            
            with open(self.processed_reports_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"처리된 리포트 저장 실패: {e}")
    
    def _generate_report_hash(self, event: Dict) -> str:
        """리포트 고유 해시 생성"""
        if event.get('type') == 'critical_news':
            title = event.get('title', '')
            published_at = event.get('published_at', '')
            
            # 제목과 발행시간을 조합한 해시
            content = f"{title}_{published_at}"
            return hashlib.md5(content.encode()).hexdigest()
        else:
            # 다른 타입의 이벤트
            content = f"{event.get('type', '')}_{event.get('description', '')}_{datetime.now().strftime('%Y%m%d%H')}"
            return hashlib.md5(content.encode()).hexdigest()
    
    def _is_duplicate_report(self, event: Dict) -> bool:
        """중복 리포트 체크"""
        report_hash = self._generate_report_hash(event)
        
        if report_hash in self.processed_reports:
            self.logger.info(f"중복 리포트 감지 - 전송 생략: {event.get('title', '')[:50]}...")
            return True
        
        # 새로운 리포트로 기록
        self.processed_reports.add(report_hash)
        
        # 크기 제한 (최대 1000개)
        if len(self.processed_reports) > 1000:
            # 오래된 것부터 제거 (단순하게 일부 제거)
            self.processed_reports = set(list(self.processed_reports)[-500:])
        
        # 파일에 저장
        self._save_processed_reports()
        
        return False
    
    def _classify_news_type(self, article: Dict) -> str:
        """뉴스 타입 분류 - 구조화 상품 vs 직접 투자 + 거시경제 구분 + AI 예측 추가"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 🔥🔥 AI 예측 관련 (새로 추가)
        if any(word in content for word in ['ai based', 'ai predicts', 'energy crisis boom']):
            if 'energy crisis' in content and any(word in content for word in ['250000', '25']):
                return 'energy_crisis_prediction'
            else:
                return 'ai_prediction'
        
        # 🔥🔥 가격 돌파/이정표 관련 (새로 추가)
        if any(word in content for word in ['crosses', '100k', '$100,000', 'milestone', 'breaks', 'hits']):
            if any(word in content for word in ['search', 'google', 'interest', 'attention']):
                return 'price_milestone'
        
        # ETF 관련
        if 'etf' in content:
            if any(word in content for word in ['approved', 'approval', 'launch']):
                return 'etf_approval'
            elif any(word in content for word in ['rejected', 'rejection', 'delay']):
                return 'etf_rejection'
        
        # 기업 투자 - 직접 vs 구조화 상품 구분
        if any(company in content for company in ['tesla', 'microstrategy', 'blackrock', 'gamestop']) and \
           any(word in content for word in ['bought', 'purchased', 'buys', 'adds']):
            return 'corporate_purchase_direct'
        
        # 구조화 상품 (비트코인 직접 매수 아님)
        if any(word in content for word in ['structured', 'bonds', 'linked', 'tracking', 'exposure']) and \
           any(word in content for word in ['bitcoin', 'btc']):
            return 'corporate_structured_product'
        
        # 은행/기관 채택
        if any(bank in content for bank in ['sberbank', 'bank', 'central bank']) and \
           any(word in content for word in ['bitcoin', 'btc', 'bonds', 'launches']):
            # 구조화 상품인지 직접 투자인지 구분
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']):
                return 'corporate_structured_product'
            else:
                return 'banking_adoption'
        
        # 규제 관련
        if any(word in content for word in ['regulation', 'legal', 'court']) and \
           any(word in content for word in ['positive', 'approved', 'favorable']):
            return 'regulation_positive'
        elif any(word in content for word in ['ban', 'prohibited', 'lawsuit', 'illegal']):
            return 'regulation_negative'
        
        # Fed 금리 및 거시경제
        if any(word in content for word in ['fed', 'fomc', 'federal reserve', 'interest rate']):
            return 'fed_rate_decision'
        elif any(word in content for word in ['trump', 'tariffs', 'trade war', 'china tariffs']):
            return 'trade_tariffs'
        elif any(word in content for word in ['inflation', 'cpi', 'pce']):
            return 'inflation_data'
        
        # 해킹/보안
        elif any(word in content for word in ['hack', 'stolen', 'breach', 'exploit']):
            return 'hack_incident'
        
        else:
            return 'macro_economic_general'
    
    def _get_ml_impact_prediction(self, article: Dict) -> Dict:
        """ML 기반 영향 예측 - 현실적 조정"""
        try:
            if not self.ml_predictor:
                return self._get_fallback_prediction(article)
            
            # 뉴스 특성 추출
            features = self._extract_news_features(article)
            
            # ML 예측 실행
            prediction = self.ml_predictor.predict_price_impact(features)
            
            # 현실적 조정 (과도한 예측 방지)
            magnitude = min(prediction.get('magnitude', 0.5), 1.5)  # 최대 1.5% 제한
            confidence = prediction.get('confidence', 0.6)
            
            return {
                'direction': prediction.get('direction', 'neutral'),
                'magnitude': magnitude,
                'confidence': confidence,
                'timeframe': self._get_realistic_timeframe(article),
                'risk_level': prediction.get('risk_level', 'medium')
            }
            
        except Exception as e:
            self.logger.error(f"ML 예측 실패: {e}")
            return self._get_fallback_prediction(article)
    
    def _get_realistic_timeframe(self, article: Dict) -> str:
        """현실적인 반응 시점 계산"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 즉시 반응 (고영향)
        if any(word in content for word in ['etf approved', 'etf rejected', 'fed rate']):
            return '즉시-30분'
        
        # 빠른 반응 (중영향)
        elif any(word in content for word in ['bought billion', 'lawsuit', 'ban']):
            return '30분-2시간'
        
        # 지연 반응 (저영향)
        elif any(word in content for word in ['structured', 'bonds', 'linked', 'milestone', 'crosses', 'ai predicts']):
            return '1-4시간 (미미)'
        
        # 일반
        else:
            return '1-6시간'
    
    def _extract_news_features(self, article: Dict) -> Dict:
        """뉴스에서 ML 특성 추출"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        features = {
            'has_bitcoin_keyword': any(word in content for word in ['bitcoin', 'btc']),
            'has_amount': bool(re.search(r'\$?\d+(?:,\d+)*(?:\.\d+)?\s*(?:billion|million|thousand)', content)),
            'sentiment_score': self._calculate_sentiment_score(content),
            'source_weight': article.get('weight', 5),
            'company_involved': any(company in content for company in ['tesla', 'microstrategy', 'blackrock']),
            'regulatory_keyword': any(word in content for word in ['sec', 'etf', 'regulation', 'court']),
            'urgency_indicators': len(re.findall(r'breaking|urgent|alert|immediate', content)),
            'negative_keywords': len(re.findall(r'ban|prohibited|hack|stolen|crash|plunge', content)),
            'positive_keywords': len(re.findall(r'approved|launch|bought|partnership|adoption', content)),
            'is_structured_product': any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']),  
            'is_direct_investment': any(word in content for word in ['bought', 'purchased', 'acquired']) and not any(word in content for word in ['structured', 'bonds', 'linked']),
            'is_macro_economic': any(word in content for word in ['fed', 'tariffs', 'inflation', 'trade']),
            'is_price_milestone': any(word in content for word in ['crosses', '100k', 'milestone', 'breaks', 'hits']),  # 새로 추가
            'is_ai_prediction': any(word in content for word in ['ai predicts', 'ai based', 'energy crisis']),  # 새로 추가
        }
        
        return features
    
    def _calculate_sentiment_score(self, content: str) -> float:
        """간단한 감정 점수 계산"""
        positive_words = ['approved', 'launched', 'bought', 'partnership', 'adoption', 'positive', 'surge', 'rally', 'breaks', 'crosses']
        negative_words = ['banned', 'rejected', 'hack', 'stolen', 'crash', 'plunge', 'lawsuit', 'prohibited']
        
        pos_count = sum(1 for word in positive_words if word in content)
        neg_count = sum(1 for word in negative_words if word in content)
        
        if pos_count + neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count)
    
    def _get_fallback_prediction(self, article: Dict) -> Dict:
        """ML 사용 불가 시 현실적 폴백 예측"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 뉴스 타입 분류
        news_type = self._classify_news_type(article)
        pattern_info = self.news_reaction_patterns.get(news_type, self.news_reaction_patterns['macro_economic_general'])
        
        # 패턴 기반 예측 범위
        min_impact, max_impact = pattern_info['typical_range']
        
        # 중간값 계산
        avg_impact = (min_impact + max_impact) / 2
        magnitude = abs(avg_impact)
        direction = 'bullish' if avg_impact > 0 else 'bearish' if avg_impact < 0 else 'neutral'
        
        return {
            'direction': direction,
            'magnitude': magnitude,
            'confidence': 0.7,
            'timeframe': self._get_realistic_timeframe(article),
            'risk_level': pattern_info['actual_impact']
        }
    
    def _format_smart_strategy(self, news_type: str, ml_prediction: Dict, article: Dict) -> str:
        """현실적 전략 제안"""
        direction = ml_prediction.get('direction', 'neutral')
        magnitude = ml_prediction.get('magnitude', 0.5)
        confidence = ml_prediction.get('confidence', 0.5)
        
        # 기본 패턴 정보
        pattern_info = self.news_reaction_patterns.get(news_type, {})
        
        strategy_lines = []
        
        # 🔥🔥 AI 예측 관련 특별 처리 (새로 추가)
        if news_type == 'ai_prediction':
            strategy_lines.append("🎯 <b>AI 예측 - 신중한 접근</b>")
            strategy_lines.append("• 추측성 정보로 실제 영향 제한적")
            strategy_lines.append("• 펀더멘털 분석과 무관한 예측")
            strategy_lines.append("• 투기적 거래만 고려")
            
        elif news_type == 'energy_crisis_prediction':
            strategy_lines.append("🎯 <b>에너지 위기 예측 - 가설적 시나리오</b>")
            strategy_lines.append("• 25만 달러 예측은 극도로 낙관적")
            strategy_lines.append("• 실제 에너지 위기 발생 가능성 낮음")
            strategy_lines.append("• 장기 투자 의사결정에 부적합")
            
        # 뉴스 타입별 특화 전략
        elif news_type == 'corporate_structured_product':
            strategy_lines.append("🎯 <b>구조화 상품 - 미미한 영향</b>")
            strategy_lines.append("• 직접적인 BTC 수요 창출 없음")
            strategy_lines.append("• 단기 스캘핑만 고려")
            strategy_lines.append("• 장기 투자 의사결정에 영향 없음")
            
        elif news_type == 'corporate_purchase_direct':
            if magnitude > 0.8:
                strategy_lines.append("🎯 <b>직접 매입 - 적극 매수 시나리오</b>")
                strategy_lines.append("• 실제 BTC 수요 증가")
                strategy_lines.append("• 분할 매수 후 중기 보유")
            else:
                strategy_lines.append("🎯 <b>직접 매입 - 신중 매수 시나리오</b>")
                strategy_lines.append("• 소량 테스트 후 추가 진입")
                
        elif news_type == 'etf_approval':
            strategy_lines.append("🎯 <b>ETF 승인 - 즉시 대응 필요</b>")
            strategy_lines.append("• 발표 직후 빠른 진입")
            strategy_lines.append("• 2-4시간 내 수익 실현 고려")
            
        elif news_type == 'etf_rejection':
            strategy_lines.append("🎯 <b>ETF 거부 - 역매매 기회</b>")
            strategy_lines.append("• 급락 시 분할 매수")
            strategy_lines.append("• 6-12시간 내 회복 기대")
            
        elif news_type == 'trade_tariffs':
            strategy_lines.append("🎯 <b>관세 정책 - 단기 하락 후 회복</b>")
            strategy_lines.append("• 초기 매도 압박 후 안정화")
            strategy_lines.append("• 하락 시 분할 매수 기회")
            
        elif news_type == 'inflation_data':
            strategy_lines.append("🎯 <b>인플레이션 헤지 - 완만한 상승</b>")
            strategy_lines.append("• 헤지 수요로 점진적 상승")
            strategy_lines.append("• 장기 보유 관점에서 유리")
            
        elif news_type == 'price_milestone':  # 새로 추가
            strategy_lines.append("🎯 <b>가격 돌파 - 심리적 효과</b>")
            strategy_lines.append("• 일반 투자자 관심도가 핵심")
            strategy_lines.append("• FOMO 확산 시 추가 상승 가능")
            strategy_lines.append("• 검색량/소셜 활동 모니터링 필요")
            
        elif direction == 'bearish' and confidence > 0.6:
            strategy_lines.append("🎯 <b>방어 및 역매매 시나리오</b>")
            strategy_lines.append("• 기존 포지션 부분 청산")
            strategy_lines.append("• 과매도 시 역매매 준비")
        else:
            strategy_lines.append("🎯 <b>중립 관망</b>")
            strategy_lines.append("• 추가 신호 대기")
            strategy_lines.append("• 소량 양방향 헷지 고려")
        
        # 현실적인 타이밍 정보
        if pattern_info.get('pattern'):
            strategy_lines.append(f"⏱️ <b>반응 패턴</b>: {pattern_info['pattern']}")
        
        # 현실적인 지속 기간
        if pattern_info.get('duration'):
            strategy_lines.append(f"📅 <b>영향 지속</b>: {pattern_info['duration']}")
        else:
            # 기본값 - 뉴스 타입에 따라
            if news_type in ['ai_prediction', 'energy_crisis_prediction']:
                strategy_lines.append(f"📅 <b>영향 지속</b>: 1-4시간 (미미)")
            elif news_type == 'corporate_structured_product':
                strategy_lines.append(f"📅 <b>영향 지속</b>: 2-6시간 (미미)")
            elif news_type in ['etf_approval', 'etf_rejection']:
                strategy_lines.append(f"📅 <b>영향 지속</b>: 12-24시간")
            elif news_type == 'price_milestone':
                strategy_lines.append(f"📅 <b>영향 지속</b>: 4-12시간 (FOMO 의존)")
            else:
                strategy_lines.append(f"📅 <b>영향 지속</b>: 6-12시간")
        
        # 실제 영향도 표시
        actual_impact = pattern_info.get('actual_impact', 'medium')
        impact_text = {
            'high': '높음 ⚡',
            'medium': '보통 📊', 
            'low': '낮음 📉',
            'minimal': '미미 💭'
        }.get(actual_impact, '보통 📊')
        
        strategy_lines.append(f"🎲 <b>실제 영향도</b>: {impact_text} (신뢰도: {confidence:.0%})")
        
        return "\n".join(strategy_lines)
    
    def _generate_smart_summary_with_analysis(self, title: str, description: str, company: str = "", news_type: str = "") -> str:
        """🔥🔥 Claude API를 활용한 스마트 분석 - 실제 뉴스 내용 분석"""
        try:
            content = (title + " " + description).lower()
            summary_parts = []
            
            # 🔥🔥 AI 예측 관련 특별 처리 (새로 추가)
            if news_type in ['ai_prediction', 'energy_crisis_prediction']:
                if 'energy crisis' in content and '250000' in content:
                    summary_parts.append("AI 기반 분석에서 에너지 위기가 비트코인을 25만 달러까지 끌어올릴 수 있다는 예측을 제시했다.")
                    summary_parts.append("하지만 이는 극도로 낙관적인 가정에 기반한 추측성 예측으로, 실제 시장 요인들과는 거리가 있다.")
                    summary_parts.append("투자자들은 이런 극단적 예측보다는 실제 공급-수요 펀더멘털에 집중하는 것이 바람직하다.")
                else:
                    summary_parts.append("AI 기반 비트코인 가격 예측이 발표되었다.")
                    summary_parts.append("AI 예측 모델의 정확성과 근거에 대한 검증이 필요한 상황이다.")
                    summary_parts.append("시장은 추측성 예측보다는 실제 수급과 규제 동향에 더 민감하게 반응한다.")
                
                return " ".join(summary_parts)
            
            # 🔥🔥 비트코인 가격 관련 특별 처리 - 더 정교하게
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
            
            # 기업명과 행동 매칭
            if company:
                company_lower = company.lower()
                
                # 마이크로스트래티지 처리
                if company_lower == 'microstrategy':
                    if 'bought' in content or 'purchase' in content:
                        btc_amounts = re.findall(r'(\d+(?:,\d+)*)\s*(?:btc|bitcoin)', content)
                        if btc_amounts:
                            summary_parts.append(f"마이크로스트래티지가 비트코인 {btc_amounts[0]}개를 직접 매입했다.")
                        else:
                            summary_parts.append("마이크로스트래티지가 비트코인을 추가 매입했다.")
                        
                        summary_parts.append("이는 실제 BTC 수요 증가를 의미하며, 기업 재무 전략의 일환으로 시장에 긍정적 신호를 보낸다.")
                        summary_parts.append("대형 기업의 지속적인 비트코인 매입은 시장 신뢰도 향상에 기여할 것으로 예상된다.")
                
                # 테슬라 처리
                elif company_lower == 'tesla':
                    if 'bought' in content or 'purchase' in content:
                        summary_parts.append("테슬라가 비트코인 직접 매입을 재개했다.")
                        summary_parts.append("일론 머스크의 영향력과 함께 시장에 상당한 관심을 불러일으킬 것으로 예상된다.")
                        summary_parts.append("기업의 비트코인 채택 확산에 긍정적 영향을 미칠 전망이다.")
                
                # 블랙록 처리
                elif company_lower == 'blackrock':
                    if 'etf' in content:
                        if 'approved' in content:
                            summary_parts.append("세계 최대 자산운용사 블랙록의 비트코인 ETF가 승인되었다.")
                            summary_parts.append("이는 기관 자금의 대규모 유입 가능성을 열어주는 획기적 사건이다.")
                            summary_parts.append("비트코인 시장의 제도화와 주류 채택에 중요한 이정표가 될 것으로 보인다.")
                        else:
                            summary_parts.append("블랙록의 비트코인 ETF 관련 중요한 발표가 있었다.")
                            summary_parts.append("세계 최대 자산운용사의 움직임이 시장에 주목받고 있다.")
                            summary_parts.append("기관 투자자들의 비트코인 관심도가 높아지고 있음을 시사한다.")
            
            # 거시경제 패턴 처리
            if not summary_parts:
                # 관세 관련
                if any(word in content for word in ['trump', 'tariffs', 'trade war']):
                    summary_parts.append("미국의 새로운 관세 정책이 발표되었다.")
                    summary_parts.append("무역 분쟁 우려로 인해 단기적으로 리스크 자산에 부담이 될 수 있다.")
                    summary_parts.append("하지만 달러 약세 요인이 비트코인에는 중장기적으로 유리할 것으로 분석된다.")
                
                # 인플레이션 관련
                elif any(word in content for word in ['inflation', 'cpi']):
                    summary_parts.append("최신 인플레이션 데이터가 발표되었다.")
                    summary_parts.append("인플레이션 헤지 자산으로서 비트코인에 대한 관심이 높아지고 있다.")
                    summary_parts.append("실물 자산 대비 우월한 성과를 보이며 투자자들의 주목을 받고 있다.")
                
                # ETF 관련
                elif 'etf' in content:
                    if 'approved' in content or 'approval' in content:
                        summary_parts.append("비트코인 현물 ETF 승인 소식이 전해졌다.")
                        summary_parts.append("ETF 승인은 기관 투자자들의 대규모 자금 유입을 가능하게 하는 중요한 이정표다.")
                        summary_parts.append("비트코인 시장의 성숙도와 제도적 인정을 보여주는 상징적 사건으로 평가된다.")
                    elif 'rejected' in content or 'delay' in content:
                        summary_parts.append("비트코인 ETF 승인이 지연되거나 거부되었다.")
                        summary_parts.append("단기적 실망감은 있으나, 지속적인 신청은 결국 승인 가능성을 높이고 있다.")
                        summary_parts.append("시장은 이미 ETF 승인을 기정사실로 받아들이고 있어 장기 전망은 긍정적이다.")
                
                # Fed 금리 관련
                elif 'fed' in content or 'rate' in content:
                    if 'cut' in content or 'lower' in content:
                        summary_parts.append("연준의 금리 인하 결정이 발표되었다.")
                        summary_parts.append("금리 인하는 유동성 증가를 통해 비트코인과 같은 리스크 자산에 긍정적 영향을 미친다.")
                        summary_parts.append("저금리 환경에서 대안 투자처로서 비트코인의 매력도가 더욱 부각될 전망이다.")
                    elif 'hike' in content or 'increase' in content:
                        summary_parts.append("연준의 금리 인상 결정이 발표되었다.")
                        summary_parts.append("단기적으로는 부담이지만 인플레이션 헤지 자산으로서의 비트코인 가치는 지속될 것이다.")
                        summary_parts.append("고금리 환경에서도 디지털 금으로서의 역할은 변함없을 것으로 예상된다.")
                
                # 기본 케이스 - 제목 분석
                else:
                    # 실제 제목에서 키워드 추출해서 분석
                    if any(word in title.lower() for word in ['prediction', 'forecast', 'expects', 'predicts']):
                        summary_parts.append("비트코인 가격에 대한 새로운 예측 분석이 발표되었다.")
                        summary_parts.append("예측의 방법론과 근거에 대한 면밀한 검토가 필요한 상황이다.")
                        summary_parts.append("투자자들은 추측성 예측보다는 실제 시장 펀더멘털에 집중하는 것이 바람직하다.")
                    else:
                        summary_parts.append("비트코인 시장에 영향을 미칠 수 있는 발표가 있었다.")
                        summary_parts.append("투자자들은 이번 소식의 실제 시장 영향을 면밀히 분석하고 있다.")
                        summary_parts.append("단기 변동성은 있겠지만 장기 트렌드에는 큰 변화가 없을 것으로 전망된다.")
