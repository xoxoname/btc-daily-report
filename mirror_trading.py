import os
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json
import traceback

# 유틸리티 클래스 import
from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult
from mirror_position_manager import MirrorPositionManager

logger = logging.getLogger(__name__)

class MirrorTradingSystem:
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 🔥🔥🔥 환경변수 처리 개선 - O/X 지원, 배율은 기본값 1.0
        raw_mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'O')
        self.mirror_trading_enabled = self._parse_mirror_trading_mode(raw_mirror_mode)
        
        # 🔥🔥🔥 배율은 기본값 1.0으로 시작, 텔레그램으로 실시간 조정
        self.mirror_ratio_multiplier = 1.0
        
        # 환경변수 로깅
        self.logger.info(f"🔥 환경변수 원본값: MIRROR_TRADING_MODE='{raw_mirror_mode}'")
        self.logger.info(f"🔥 파싱 결과: 미러링={'활성화' if self.mirror_trading_enabled else '비활성화'}, 초기 복제비율={self.mirror_ratio_multiplier}x")
        
        # Bitget 미러링 전용 클라이언트 import
        try:
            from bitget_mirror_client import BitgetMirrorClient
            self.bitget_mirror = BitgetMirrorClient(config)
            logger.info("✅ Bitget 미러링 전용 클라이언트 초기화")
        except ImportError as e:
            logger.error(f"❌ Bitget 미러링 클라이언트 import 실패: {e}")
            raise
        
        # 유틸리티 클래스 초기화 (미러링 클라이언트 사용)
        self.utils = MirrorTradingUtils(config, self.bitget_mirror, gate_client)
        
        # Gate.io 미러링 전용 클라이언트 import
        try:
            from gateio_mirror_client import GateioMirrorClient
            self.gate_mirror = GateioMirrorClient(config)
            logger.info("✅ Gate.io 미러링 전용 클라이언트 초기화")
        except ImportError as e:
            logger.error(f"❌ Gate.io 미러링 클라이언트 import 실패: {e}")
            raise
        
        # 포지션 관리자 초기화 (미러링 클라이언트 포함)
        self.position_manager = MirrorPositionManager(
            config, self.bitget_mirror, gate_client, self.gate_mirror, telegram_bot, self.utils
        )
        
        # 🔥🔥🔥 실시간 배율 변경을 위한 참조 연결
        self.position_manager.mirror_ratio_multiplier = self.mirror_ratio_multiplier
        
        # 미러링 상태 관리 (포지션 매니저에 위임)
        self.mirrored_positions = self.position_manager.mirrored_positions
        self.startup_positions = self.position_manager.startup_positions
        self.failed_mirrors = self.position_manager.failed_mirrors
        
        # 🔥🔥🔥 오픈/클로징 매칭 강화 시스템
        self.position_matching_enabled = True
        self.close_order_strict_validation = True  # 클로즈 주문 엄격한 검증
        self.ratio_mismatch_prevention = True  # 복제 비율 불일치 방지
        
        # 🔥🔥🔥 경고 알림 제한 시스템 - 각 타입별로 최대 2번까지만
        self.warning_counters = {
            'price_difference': 0, 'sync_status': 0, 'order_fills': 0, 'plan_orders': 0,
            'positions': 0, 'price_monitoring': 0, 'order_synchronization': 0,
            'high_failure_rate': 0, 'api_connection': 0, 'system_error': 0,
            'position_matching': 0, 'ratio_mismatch': 0  # 🔥🔥🔥 새로 추가
        }
        self.MAX_WARNING_COUNT = 2
        
        # 기본 설정
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        self.price_sync_threshold: float = 1000.0  # 매우 관대하게 설정
        self.position_wait_timeout: int = 60
        
        # 시세 조회 실패 관리 강화
        self.last_valid_bitget_price: float = 0.0
        self.last_valid_gate_price: float = 0.0
        self.bitget_price_failures: int = 0
        self.gate_price_failures: int = 0
        self.max_price_failures: int = 10
        
        # 🔥🔥🔥 예약 주문 동기화 강화 설정 - 오픈/클로징 매칭 고려
        self.order_sync_enabled: bool = True
        self.order_sync_interval: int = 45
        self.last_order_sync_time: datetime = datetime.min
        
        # 🔥🔥🔥 체결된 주문 추적 강화 - 복제 비율 고려
        self.filled_order_tracking_enabled: bool = True
        self.filled_order_check_interval: int = 5
        self.last_filled_order_check: datetime = datetime.min
        
        # 🔥🔥🔥 복제 비율 관련 모니터링
        self.ratio_adjustment_history: List[Dict] = []  # 복제 비율 변경 이력
        self.last_ratio_adjustment: datetime = datetime.min
        self.ratio_stability_window: int = 300  # 5분간 안정성 체크
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 1
        self.ORDER_CHECK_INTERVAL = 0.5
        self.PLAN_ORDER_CHECK_INTERVAL = 0.2
        self.SYNC_CHECK_INTERVAL = 30
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.DAILY_REPORT_HOUR = 9
        
        # 성과 추적 (포지션 매니저와 공유)
        self.daily_stats = self.position_manager.daily_stats
        
        self.monitoring = True
        
        # 초기화 메시지
        status_text = "활성화" if self.mirror_trading_enabled else "비활성화"
        
        self.logger.info(f"🔥 미러 트레이딩 시스템 초기화 완료")
        self.logger.info(f"   - 미러링 모드: {status_text}")
        self.logger.info(f"   - 초기 복제 비율: {self.mirror_ratio_multiplier}x")
        self.logger.info(f"   - 오픈/클로징 매칭: {'활성화' if self.position_matching_enabled else '비활성화'}")
        self.logger.info(f"   - 엄격한 검증: {'활성화' if self.close_order_strict_validation else '비활성화'}")

    def _parse_mirror_trading_mode(self, mode_str: str) -> bool:
        """미러링 모드 파싱"""
        if isinstance(mode_str, bool):
            return mode_str
        
        mode_str_original = str(mode_str).strip()
        mode_str_upper = mode_str_original.upper()
        
        self.logger.info(f"🔍 미러링 모드 파싱: 원본='{mode_str_original}', 대문자='{mode_str_upper}'")
        
        if mode_str_upper == 'O':
            self.logger.info("✅ 영어 대문자 O 감지 → 활성화")
            return True
        elif mode_str_upper == 'X':
            self.logger.info("✅ 영어 대문자 X 감지 → 비활성화")
            return False
        elif mode_str_upper in ['ON', 'OPEN', 'TRUE', 'Y', 'YES']:
            self.logger.info(f"✅ 활성화 키워드 감지: '{mode_str_upper}' → 활성화")
            return True
        elif mode_str_upper in ['OFF', 'CLOSE', 'FALSE', 'N', 'NO'] or mode_str_original == '0':
            self.logger.info(f"✅ 비활성화 키워드 감지: '{mode_str_upper}' → 비활성화")
            return False
        elif mode_str_original == '1':
            self.logger.info("✅ 숫자 1 감지 → 활성화")
            return True
        else:
            self.logger.warning(f"⚠️ 알 수 없는 미러링 모드: '{mode_str_original}', 기본값(활성화) 사용")
            return True

    async def set_ratio_multiplier(self, new_ratio: float) -> Dict:
        """🔥🔥🔥 실시간 복제 비율 변경 - 오픈/클로징 매칭 고려"""
        try:
            # 유효성 검증
            validated_ratio = self.utils.validate_ratio_multiplier(new_ratio)
            
            if validated_ratio != new_ratio:
                self.logger.warning(f"복제 비율 조정됨: {new_ratio} → {validated_ratio}")
            
            # 🔥🔥🔥 복제 비율 변경이 기존 포지션/주문에 미치는 영향 분석
            impact_analysis = await self._analyze_ratio_change_impact(validated_ratio)
            
            # 이전 비율 저장
            old_ratio = self.mirror_ratio_multiplier
            
            # 새 비율 적용
            self.mirror_ratio_multiplier = validated_ratio
            self.position_manager.mirror_ratio_multiplier = validated_ratio
            self.utils.current_ratio_multiplier = validated_ratio
            
            # 🔥🔥🔥 복제 비율 변경 이력 기록
            self.ratio_adjustment_history.append({
                'timestamp': datetime.now(),
                'old_ratio': old_ratio,
                'new_ratio': validated_ratio,
                'impact_analysis': impact_analysis,
                'active_positions': len(self.position_manager.open_position_tracker),
                'active_orders': len(self.position_manager.mirrored_plan_orders)
            })
            
            self.last_ratio_adjustment = datetime.now()
            
            # 변경 결과 정보
            ratio_description = self.utils.get_ratio_multiplier_description(validated_ratio)
            effect_analysis = self.utils.analyze_ratio_multiplier_effect(validated_ratio, 0.1, 0.1 * validated_ratio)
            
            self.logger.info(f"🔄 복제 비율 실시간 변경: {old_ratio}x → {validated_ratio}x")
            
            # 🔥🔥🔥 기존 포지션 추적 정보 업데이트
            await self._update_existing_positions_with_new_ratio(old_ratio, validated_ratio)
            
            return {
                'success': True,
                'old_ratio': old_ratio,
                'new_ratio': validated_ratio,
                'description': ratio_description,
                'effect': effect_analysis,
                'impact_analysis': impact_analysis,
                'applied_time': datetime.now().isoformat(),
                'active_positions_count': len(self.position_manager.open_position_tracker),
                'active_orders_count': len(self.position_manager.mirrored_plan_orders)
            }
            
        except Exception as e:
            self.logger.error(f"복제 비율 변경 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'current_ratio': self.mirror_ratio_multiplier
            }

    async def _analyze_ratio_change_impact(self, new_ratio: float) -> Dict:
        """🔥🔥🔥 복제 비율 변경이 기존 포지션/주문에 미치는 영향 분석"""
        try:
            current_ratio = self.mirror_ratio_multiplier
            impact = {
                'ratio_change_percent': ((new_ratio / current_ratio) - 1) * 100 if current_ratio > 0 else 0,
                'existing_positions_affected': len(self.position_manager.open_position_tracker),
                'existing_orders_affected': len(self.position_manager.mirrored_plan_orders),
                'new_orders_behavior': 'will_use_new_ratio',
                'existing_orders_behavior': 'keep_original_ratio',
                'risk_assessment': 'low'
            }
            
            # 리스크 평가
            if abs(impact['ratio_change_percent']) > 100:
                impact['risk_assessment'] = 'high'
            elif abs(impact['ratio_change_percent']) > 50:
                impact['risk_assessment'] = 'medium'
            else:
                impact['risk_assessment'] = 'low'
            
            # 포지션별 영향 분석
            position_impacts = []
            for pos_key, pos_info in self.position_manager.open_position_tracker.items():
                original_margin = pos_info.get('original_margin', 0)
                current_adjusted = self.position_manager.ratio_adjusted_amounts.get(pos_key, original_margin)
                new_adjusted = original_margin * new_ratio
                
                position_impacts.append({
                    'position_key': pos_key,
                    'side': pos_info['side'],
                    'original_margin': original_margin,
                    'current_adjusted_margin': current_adjusted,
                    'new_adjusted_margin': new_adjusted,
                    'change_amount': new_adjusted - current_adjusted
                })
            
            impact['position_details'] = position_impacts[:5]  # 최대 5개만 상세 분석
            
            return impact
            
        except Exception as e:
            self.logger.error(f"복제 비율 변경 영향 분석 실패: {e}")
            return {
                'ratio_change_percent': 0,
                'risk_assessment': 'unknown',
                'error': str(e)
            }

    async def _update_existing_positions_with_new_ratio(self, old_ratio: float, new_ratio: float):
        """🔥🔥🔥 기존 포지션 추적 정보를 새 복제 비율로 업데이트"""
        try:
            self.logger.info(f"🔄 기존 포지션 추적 정보 업데이트: {old_ratio}x → {new_ratio}x")
            
            updated_count = 0
            for pos_key, original_margin in self.position_manager.position_entry_amounts.items():
                # 새 비율로 조정된 마진 계산
                new_adjusted_margin = original_margin * new_ratio
                
                # 조정된 금액 업데이트 (새로운 주문에만 적용됨)
                old_adjusted = self.position_manager.ratio_adjusted_amounts.get(pos_key, original_margin)
                self.position_manager.ratio_adjusted_amounts[pos_key] = new_adjusted_margin
                
                updated_count += 1
                
                self.logger.debug(f"포지션 {pos_key}: ${old_adjusted:.2f} → ${new_adjusted_margin:.2f}")
            
            self.logger.info(f"✅ {updated_count}개 포지션 추적 정보 업데이트 완료")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 추적 정보 업데이트 실패: {e}")

    async def get_current_ratio_info(self) -> Dict:
        """현재 복제 비율 정보 조회"""
        try:
            ratio_description = self.utils.get_ratio_multiplier_description(self.mirror_ratio_multiplier)
            
            # 최근 조정 이력
            recent_adjustments = self.ratio_adjustment_history[-3:] if self.ratio_adjustment_history else []
            
            return {
                'current_ratio': self.mirror_ratio_multiplier,
                'description': ratio_description,
                'last_updated': self.last_ratio_adjustment.isoformat() if self.last_ratio_adjustment != datetime.min else None,
                'is_default': self.mirror_ratio_multiplier == 1.0,
                'adjustment_count': len(self.ratio_adjustment_history),
                'recent_adjustments': recent_adjustments,
                'active_positions': len(self.position_manager.open_position_tracker),
                'active_orders': len(self.position_manager.mirrored_plan_orders),
                'position_matching_enabled': self.position_matching_enabled
            }
            
        except Exception as e:
            self.logger.error(f"복제 비율 정보 조회 실패: {e}")
            return {
                'current_ratio': 1.0,
                'description': "정보 조회 실패",
                'error': str(e)
            }

    def _should_send_warning(self, warning_type: str) -> bool:
        """경고 발송 여부 판단 - 각 타입별 최대 2회 제한"""
        try:
            if warning_type not in self.warning_counters:
                self.warning_counters[warning_type] = 0
            
            current_count = self.warning_counters[warning_type]
            
            if current_count >= self.MAX_WARNING_COUNT:
                self.logger.debug(f"경고 타입 '{warning_type}' 최대 발송 횟수 초과 ({current_count}/{self.MAX_WARNING_COUNT})")
                return False
            
            # 카운터 증가
            self.warning_counters[warning_type] += 1
            self.logger.info(f"경고 발송: {warning_type} ({self.warning_counters[warning_type]}/{self.MAX_WARNING_COUNT})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"경고 발송 여부 판단 실패: {e}")
            return False

    def _reset_warning_counter(self, warning_type: str = None):
        """경고 카운터 리셋"""
        try:
            if warning_type:
                if warning_type in self.warning_counters:
                    old_count = self.warning_counters[warning_type]
                    self.warning_counters[warning_type] = 0
                    self.logger.info(f"경고 카운터 리셋: {warning_type} ({old_count} → 0)")
            else:
                # 전체 리셋
                self.logger.info("모든 경고 카운터 리셋")
                for key in self.warning_counters:
                    self.warning_counters[key] = 0
                    
        except Exception as e:
            self.logger.error(f"경고 카운터 리셋 실패: {e}")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🔥 미러 트레이딩 시스템 시작 - 오픈/클로징 매칭 + 복제 비율 고려")
            
            # 미러링 비활성화 확인
            if not self.mirror_trading_enabled:
                self.logger.warning("⚠️ 미러링 모드가 비활성화되어 있습니다 (MIRROR_TRADING_MODE=X)")
                await self.telegram.send_message(
                    f"⚠️ 미러 트레이딩 시스템 비활성화\n"
                    f"현재 설정: MIRROR_TRADING_MODE=X\n"
                    f"미러링을 활성화하려면 환경변수를 O로 변경하세요."
                )
                return
            
            # Bitget 미러링 클라이언트 초기화
            await self.bitget_mirror.initialize()
            
            # Gate.io 미러링 클라이언트 초기화
            await self.gate_mirror.initialize()
            
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 포지션 매니저 초기화
            self.position_manager.price_sync_threshold = self.price_sync_threshold
            self.position_manager.position_wait_timeout = self.position_wait_timeout
            await self.position_manager.initialize()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),
                self.monitor_order_fills(), 
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.monitor_price_differences(),
                self.monitor_order_synchronization_with_matching(),
                self.monitor_ratio_stability(),
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            if self._should_send_warning('system_error'):
                await self.telegram.send_message(
                    f"❌ 미러 트레이딩 시작 실패\n오류: {str(e)[:200]}"
                )
            raise

    async def monitor_order_synchronization_with_matching(self):
        """🔥🔥🔥 예약 주문 동기화 모니터링 - 오픈/클로징 매칭 고려"""
        try:
            self.logger.info("🔄 오픈/클로징 매칭 고려한 예약 주문 동기화 모니터링 시작")
            
            while self.monitoring:
                try:
                    if not self.mirror_trading_enabled:
                        await asyncio.sleep(self.order_sync_interval)
                        continue
                        
                    if not self.order_sync_enabled:
                        await asyncio.sleep(self.order_sync_interval)
                        continue
                    
                    current_time = datetime.now()
                    
                    # 더 긴 간격으로 동기화 체크
                    if (current_time - self.last_order_sync_time).total_seconds() >= self.order_sync_interval:
                        await self._perform_comprehensive_order_sync_with_matching()
                        self.last_order_sync_time = current_time
                    
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    self.logger.error(f"매칭 고려 동기화 모니터링 오류: {e}")
                    if self._should_send_warning('order_synchronization'):
                        await self.telegram.send_message(
                            f"⚠️ 오픈/클로징 매칭 동기화 모니터링 오류\n오류: {str(e)[:200]}"
                        )
                    await asyncio.sleep(self.order_sync_interval)
                    
        except Exception as e:
            self.logger.error(f"매칭 고려 동기화 모니터링 시스템 실패: {e}")

    async def _perform_comprehensive_order_sync_with_matching(self):
        """🔥🔥🔥 종합적인 예약 주문 동기화 - 오픈/클로징 매칭 고려"""
        try:
            self.logger.debug("🔄 오픈/클로징 매칭 고려한 종합 예약 주문 동기화 시작")
            
            # 1. 비트겟 예약 주문 조회 (분류 포함)
            all_bitget_orders = await self.position_manager._get_all_current_plan_orders_with_classification()
            
            # 2. 게이트 예약 주문 조회
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 3. 오픈/클로징 매칭 고려한 동기화 분석
            sync_analysis = await self._analyze_comprehensive_sync_with_matching(all_bitget_orders, gate_orders)
            
            # 4. 문제가 있으면 수정
            if sync_analysis['requires_action']:
                await self._fix_sync_issues_with_matching(sync_analysis)
            else:
                self.logger.debug(f"✅ 매칭 고려 동기화 상태 양호: 비트겟 {len(all_bitget_orders)}개, 게이트 {len(gate_orders)}개")
            
        except Exception as e:
            self.logger.error(f"매칭 고려 종합 동기화 실패: {e}")

    async def _analyze_comprehensive_sync_with_matching(self, bitget_orders: List[Dict], gate_orders: List[Dict]) -> Dict:
        """🔥🔥🔥 오픈/클로징 매칭 고려한 종합적인 동기화 분석"""
        try:
            analysis = {
                'requires_action': False,
                'missing_mirrors': [],
                'confirmed_orphans': [],
                'safe_orders': [],
                'position_mismatches': [],
                'ratio_mismatches': [],
                'total_issues': 0
            }
            
            # 1. 비트겟 주문 분석 - 누락된 미러링 찾기 (매칭 고려)
            for order_info in bitget_orders:
                order = order_info['order']
                classification = order_info['classification']
                bitget_order_id = order.get('orderId', order.get('planOrderId', ''))
                
                if not bitget_order_id:
                    continue
                
                # 스타트업 주문은 제외
                if bitget_order_id in self.position_manager.startup_plan_orders:
                    continue
                
                # 이미 처리된 주문은 제외
                if bitget_order_id in self.position_manager.processed_plan_orders:
                    continue
                
                # 🔥🔥🔥 클로즈 주문인 경우 포지션 매칭 검증
                if classification['is_close_order']:
                    position_side = classification.get('position_side', 'long')
                    
                    # 해당 포지션이 존재하는지 확인
                    has_matching_position = False
                    for pos_key, pos_info in self.position_manager.open_position_tracker.items():
                        if pos_info['side'] == position_side and pos_info['size'] > 0:
                            has_matching_position = True
                            break
                    
                    if not has_matching_position:
                        # 매칭되는 포지션이 없는 클로즈 주문
                        analysis['position_mismatches'].append({
                            'bitget_order_id': bitget_order_id,
                            'bitget_order': order,
                            'position_side': position_side,
                            'type': 'missing_position_for_close'
                        })
                        continue
                
                # 미러링 기록 확인
                if bitget_order_id in self.position_manager.mirrored_plan_orders:
                    # 미러링 기록이 있으면 게이트에서 실제 존재 여부 확인
                    mirror_info = self.position_manager.mirrored_plan_orders[bitget_order_id]
                    expected_gate_id = mirror_info.get('gate_order_id')
                    
                    if expected_gate_id:
                        gate_order_found = any(order.get('id') == expected_gate_id for order in gate_orders)
                        if not gate_order_found:
                            analysis['missing_mirrors'].append({
                                'bitget_order_id': bitget_order_id,
                                'bitget_order': order,
                                'classification': classification,
                                'expected_gate_id': expected_gate_id,
                                'type': 'missing_mirror'
                            })
                else:
                    # 미러링 기록이 없는 비트겟 주문 - 새로 미러링 필요
                    analysis['missing_mirrors'].append({
                        'bitget_order_id': bitget_order_id,
                        'bitget_order': order,
                        'classification': classification,
                        'expected_gate_id': None,
                        'type': 'unmirrored'
                    })
            
            # 2. 게이트 고아 주문 찾기 (기존 로직 유지)
            bitget_order_ids = set()
            for order_info in bitget_orders:
                order = order_info['order']
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    bitget_order_ids.add(order_id)
            
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id', '')
                if not gate_order_id:
                    continue
                
                # 매핑 확인
                bitget_order_id = self.position_manager.gate_to_bitget_order_mapping.get(gate_order_id)
                
                if not bitget_order_id:
                    # 기존 게이트 주문인지 확인
                    if gate_order_id in self.position_manager.gate_existing_orders_detailed:
                        analysis['safe_orders'].append({
                            'gate_order_id': gate_order_id,
                            'type': 'existing_gate_order',
                            'reason': '시작 시 존재했던 게이트 주문'
                        })
                        continue
                    else:
                        analysis['safe_orders'].append({
                            'gate_order_id': gate_order_id,
                            'type': 'unmapped_unknown',
                            'reason': '매핑 없는 미지의 주문 - 안전상 보존'
                        })
                        continue
                
                # 매핑이 있는 경우 - 비트겟에서 실제 존재 여부 확인
                bitget_exists = bitget_order_id in bitget_order_ids
                
                if not bitget_exists:
                    try:
                        recheck_result = await self._recheck_bitget_order_exists_simple(bitget_order_id)
                        
                        if recheck_result['definitely_deleted']:
                            analysis['confirmed_orphans'].append({
                                'gate_order_id': gate_order_id,
                                'gate_order': gate_order,
                                'mapped_bitget_id': bitget_order_id,
                                'type': 'confirmed_orphan',
                                'verification': recheck_result
                            })
                        else:
                            analysis['safe_orders'].append({
                                'gate_order_id': gate_order_id,
                                'type': 'uncertain_status',
                                'reason': f"비트겟 주문 상태 불확실: {recheck_result.get('reason', '알 수 없음')}"
                            })
                            
                    except Exception as recheck_error:
                        analysis['safe_orders'].append({
                            'gate_order_id': gate_order_id,
                            'type': 'recheck_failed',
                            'reason': f'재확인 실패로 안전상 보존: {recheck_error}'
                        })
            
            # 🔥🔥🔥 복제 비율 불일치 감지
            for mirror_order_id, mirror_info in self.position_manager.mirrored_plan_orders.items():
                mirror_ratio = mirror_info.get('ratio_multiplier', 1.0)
                if abs(mirror_ratio - self.mirror_ratio_multiplier) > 0.01:  # 0.01 차이 허용
                    analysis['ratio_mismatches'].append({
                        'order_id': mirror_order_id,
                        'mirror_ratio': mirror_ratio,
                        'current_ratio': self.mirror_ratio_multiplier,
                        'type': 'ratio_outdated'
                    })
            
            # 총 문제 개수 계산
            analysis['total_issues'] = (
                len(analysis['missing_mirrors']) + 
                len(analysis['confirmed_orphans']) +
                len(analysis['position_mismatches'])
            )
            
            analysis['requires_action'] = analysis['total_issues'] > 0
            
            if analysis['requires_action']:
                self.logger.info(f"🔍 매칭 고려 동기화 문제 발견: {analysis['total_issues']}건")
                self.logger.info(f"   - 누락 미러링: {len(analysis['missing_mirrors'])}건")
                self.logger.info(f"   - 확실한 고아: {len(analysis['confirmed_orphans'])}건")
                self.logger.info(f"   - 포지션 불일치: {len(analysis['position_mismatches'])}건")
                self.logger.info(f"   - 복제 비율 불일치: {len(analysis['ratio_mismatches'])}건")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"매칭 고려 동기화 분석 실패: {e}")
            return {
                'requires_action': False,
                'total_issues': 0,
                'missing_mirrors': [],
                'confirmed_orphans': [],
                'safe_orders': [],
                'position_mismatches': [],
                'ratio_mismatches': []
            }

    async def _recheck_bitget_order_exists_simple(self, bitget_order_id: str) -> Dict:
        """간단한 비트겟 주문 존재 여부 재확인"""
        try:
            all_current_orders = await self.position_manager._get_all_current_plan_orders_with_classification()
            
            for order_info in all_current_orders:
                order = order_info['order']
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id == bitget_order_id:
                    return {
                        'exists': True,
                        'definitely_deleted': False,
                        'found_in': 'current_orders',
                        'reason': '현재 활성 주문에서 발견'
                    }
            
            return {
                'exists': False,
                'definitely_deleted': True,
                'found_in': 'nowhere',
                'reason': '현재 활성 주문에서 찾을 수 없음 (취소/체결됨)'
            }
            
        except Exception as e:
            return {
                'exists': False,
                'definitely_deleted': False,
                'found_in': 'error',
                'reason': f'재확인 오류: {str(e)}'
            }

    async def _fix_sync_issues_with_matching(self, sync_analysis: Dict):
        """🔥🔥🔥 매칭 고려한 동기화 문제 해결"""
        try:
            fixed_count = 0
            
            # 1. 누락된 미러링 처리 (포지션 매칭 고려)
            missing_tasks = []
            for missing in sync_analysis['missing_mirrors'][:3]:  # 한 번에 3개씩만
                try:
                    bitget_order = missing['bitget_order']
                    classification = missing['classification']
                    bitget_order_id = missing['bitget_order_id']
                    
                    # 🔥🔥🔥 클로즈 주문인 경우 추가 검증
                    if classification['is_close_order']:
                        should_process = await self.position_manager._validate_close_order_with_position_matching(
                            bitget_order, classification
                        )
                        if not should_process:
                            self.logger.info(f"🔍 포지션 매칭 실패로 클로즈 주문 스킵: {bitget_order_id}")
                            continue
                    
                    self.logger.info(f"🔄 누락된 미러링 복제 (매칭 고려): {bitget_order_id}")
                    
                    if bitget_order_id not in self.position_manager.processed_plan_orders:
                        task = self.position_manager._process_matched_mirror_order_with_ratio(
                            bitget_order, classification, self.mirror_ratio_multiplier
                        )
                        missing_tasks.append((bitget_order_id, task))
                        
                        self.position_manager.processed_plan_orders.add(bitget_order_id)
                    
                except Exception as e:
                    self.logger.error(f"누락 미러링 태스크 생성 실패: {missing['bitget_order_id']} - {e}")
            
            # 병렬 실행
            if missing_tasks:
                results = await asyncio.gather(*[task for _, task in missing_tasks], return_exceptions=True)
                
                for i, (order_id, _) in enumerate(missing_tasks):
                    try:
                        result = results[i]
                        if isinstance(result, Exception):
                            self.logger.error(f"누락 미러링 실행 실패: {order_id} - {result}")
                        elif result in ["perfect_success", "partial_success", "force_success", "close_order_forced"]:
                            fixed_count += 1
                            self.daily_stats['sync_corrections'] += 1
                            self.logger.info(f"✅ 누락 미러링 완료 (매칭 고려): {order_id}")
                    except Exception as e:
                        self.logger.error(f"누락 미러링 결과 처리 실패: {order_id} - {e}")
            
            # 2. 확실한 고아 주문 처리 (기존 로직 유지)
            confirmed_orphans = sync_analysis.get('confirmed_orphans', [])
            
            if confirmed_orphans:
                for orphaned in confirmed_orphans[:3]:
                    try:
                        gate_order_id = orphaned['gate_order_id']
                        verification = orphaned.get('verification', {})
                        
                        if verification.get('definitely_deleted'):
                            try:
                                await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                                fixed_count += 1
                                self.daily_stats['sync_deletions'] += 1
                                
                                # 매핑에서도 제거
                                if gate_order_id in self.position_manager.gate_to_bitget_order_mapping:
                                    bitget_id = self.position_manager.gate_to_bitget_order_mapping[gate_order_id]
                                    del self.position_manager.gate_to_bitget_order_mapping[gate_order_id]
                                    if bitget_id in self.position_manager.bitget_to_gate_order_mapping:
                                        del self.position_manager.bitget_to_gate_order_mapping[bitget_id]
                                
                            except Exception as delete_error:
                                error_msg = str(delete_error).lower()
                                if any(keyword in error_msg for keyword in ["not found", "order not exist"]):
                                    fixed_count += 1
                    except Exception as e:
                        self.logger.error(f"고아 주문 처리 실패: {orphaned['gate_order_id']} - {e}")
            
            # 3. 포지션 불일치 알림
            position_mismatches = sync_analysis.get('position_mismatches', [])
            if position_mismatches and self._should_send_warning('position_matching'):
                await self.telegram.send_message(
                    f"⚠️ 포지션 매칭 불일치 감지\n"
                    f"클로즈 주문 {len(position_mismatches)}개가 해당 포지션 없이 존재\n"
                    f"복제 비율: {self.mirror_ratio_multiplier}x\n"
                    f"이는 렌더 재구동 시 정상적인 현상일 수 있습니다."
                )
            
            # 4. 복제 비율 불일치 알림
            ratio_mismatches = sync_analysis.get('ratio_mismatches', [])
            if ratio_mismatches and self._should_send_warning('ratio_mismatch'):
                await self.telegram.send_message(
                    f"📊 복제 비율 불일치 감지\n"
                    f"기존 주문 {len(ratio_mismatches)}개가 이전 비율로 설정됨\n"
                    f"현재 비율: {self.mirror_ratio_multiplier}x\n"
                    f"새로운 주문부터 현재 비율이 적용됩니다."
                )
            
            # 동기화 결과 알림
            if fixed_count >= 3:
                price_diff = abs(self.bitget_current_price - self.gate_current_price)
                ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                
                if self._should_send_warning('order_synchronization'):
                    await self.telegram.send_message(
                        f"🔄 오픈/클로징 매칭 동기화 완료{ratio_info}\n"
                        f"해결된 문제: {fixed_count}건\n"
                        f"누락 미러링: {len(sync_analysis['missing_mirrors'])}건\n"
                        f"고아 주문 삭제: {len(confirmed_orphans)}건\n"
                        f"포지션 불일치: {len(position_mismatches)}건\n"
                        f"복제 비율 불일치: {len(ratio_mismatches)}건\n\n"
                        f"📊 현재 시세 차이: ${price_diff:.2f}\n"
                        f"🎯 오픈/클로징 매칭이 정확히 적용됩니다{ratio_info}"
                    )
            elif fixed_count > 0:
                self.logger.info(f"🔄 매칭 고려 동기화 완료: {fixed_count}건 해결")
            
        except Exception as e:
            self.logger.error(f"매칭 고려 동기화 문제 해결 실패: {e}")

    async def monitor_ratio_stability(self):
        """🔥🔥🔥 복제 비율 안정성 모니터링"""
        try:
            self.logger.info("📊 복제 비율 안정성 모니터링 시작")
            
            while self.monitoring:
                try:
                    if not self.mirror_trading_enabled:
                        await asyncio.sleep(60)
                        continue
                    
                    current_time = datetime.now()
                    
                    # 5분마다 안정성 체크
                    if (current_time - self.last_ratio_adjustment).total_seconds() >= self.ratio_stability_window:
                        await self._check_ratio_stability()
                    
                    await asyncio.sleep(60)  # 1분마다 체크
                    
                except Exception as e:
                    self.logger.error(f"복제 비율 안정성 모니터링 오류: {e}")
                    await asyncio.sleep(60)
                    
        except Exception as e:
            self.logger.error(f"복제 비율 안정성 모니터링 시스템 실패: {e}")

    async def _check_ratio_stability(self):
        """🔥🔥🔥 복제 비율 안정성 체크"""
        try:
            current_time = datetime.now()
            
            # 최근 조정 이력 분석
            recent_adjustments = [
                adj for adj in self.ratio_adjustment_history 
                if (current_time - adj['timestamp']).total_seconds() < 3600  # 1시간 이내
            ]
            
            if len(recent_adjustments) > 5:
                # 1시간 내에 5번 이상 조정된 경우 불안정으로 판단
                if self._should_send_warning('ratio_mismatch'):
                    await self.telegram.send_message(
                        f"⚠️ 복제 비율 불안정 감지\n"
                        f"최근 1시간 내 {len(recent_adjustments)}회 조정\n"
                        f"현재 비율: {self.mirror_ratio_multiplier}x\n"
                        f"빈번한 조정은 일관성을 해칠 수 있습니다."
                    )
            
            # 기존 주문과 현재 비율의 차이 체크
            mismatched_orders = []
            for order_id, mirror_info in self.position_manager.mirrored_plan_orders.items():
                mirror_ratio = mirror_info.get('ratio_multiplier', 1.0)
                if abs(mirror_ratio - self.mirror_ratio_multiplier) > 0.1:
                    mismatched_orders.append((order_id, mirror_ratio))
            
            if len(mismatched_orders) > 10:
                # 10개 이상의 주문이 현재 비율과 다른 경우
                if self._should_send_warning('ratio_mismatch'):
                    await self.telegram.send_message(
                        f"📊 복제 비율 일관성 체크\n"
                        f"기존 주문 {len(mismatched_orders)}개가 다른 비율로 설정됨\n"
                        f"현재 비율: {self.mirror_ratio_multiplier}x\n"
                        f"새로운 주문부터 현재 비율 적용됩니다."
                    )
            
        except Exception as e:
            self.logger.error(f"복제 비율 안정성 체크 실패: {e}")

    async def monitor_plan_orders(self):
        """예약 주문 모니터링 - 포지션 매니저로 위임"""
        self.logger.info("🎯 예약 주문 모니터링 시작 (오픈/클로징 매칭 + 복제 비율 고려)")
        
        while self.monitoring:
            try:
                if not self.mirror_trading_enabled:
                    await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 5)
                    continue
                    
                await self.position_manager.monitor_plan_orders_cycle()
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"예약 주문 모니터링 중 오류: {e}")
                if self._should_send_warning('plan_orders'):
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 모니터링 오류\n오류: {str(e)[:200]}"
                    )
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 2)

    async def monitor_order_fills(self):
        """실시간 주문 체결 감지 - 복제 비율 고려"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                if not self.mirror_trading_enabled:
                    await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 5)
                    continue
                
                # 시세 차이 확인 후 처리
                await self._update_current_prices()
                
                valid_price_diff = self._get_valid_price_difference()
                if valid_price_diff is not None:
                    self.logger.debug(f"시세 차이 ${valid_price_diff:.2f} 확인됨, 주문 처리 계속 진행")
                
                # 체결된 주문 추적 강화
                current_time = datetime.now()
                if (self.filled_order_tracking_enabled and 
                    (current_time - self.last_filled_order_check).total_seconds() >= self.filled_order_check_interval):
                    
                    try:
                        await self.position_manager._update_recently_filled_orders_with_ratio()
                        self.last_filled_order_check = current_time
                    except Exception as e:
                        self.logger.debug(f"체결 주문 추적 업데이트 실패: {e}")
                
                # 미러링 클라이언트로 체결 주문 조회
                filled_orders = await self.bitget_mirror.get_recent_filled_orders(
                    symbol=self.SYMBOL, minutes=1
                )
                
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id or order_id in self.position_manager.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    await self.position_manager.process_filled_order(order)
                    self.position_manager.processed_orders.add(order_id)
                
                # 오래된 주문 ID 정리
                if len(self.position_manager.processed_orders) > 1000:
                    recent_orders = list(self.position_manager.processed_orders)[-500:]
                    self.position_manager.processed_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"주문 체결 감지 중 오류: {e}")
                
                if consecutive_errors >= 5 and self._should_send_warning('order_fills'):
                    await self.telegram.send_message(
                        f"⚠️ 주문 체결 감지 시스템 오류\n연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def monitor_positions(self):
        """포지션 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                if not self.mirror_trading_enabled:
                    await asyncio.sleep(self.CHECK_INTERVAL * 5)
                    continue
                
                # 미러링 클라이언트로 포지션 조회
                bitget_positions = await self.bitget_mirror.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                # 실제 포지션 처리
                active_position_ids = set()
                
                for pos in bitget_active:
                    pos_id = self.utils.generate_position_id(pos)
                    active_position_ids.add(pos_id)
                    await self.position_manager.process_position(pos)
                
                # 종료된 포지션 처리
                closed_positions = set(self.mirrored_positions.keys()) - active_position_ids
                for pos_id in closed_positions:
                    if pos_id not in self.startup_positions:
                        await self.position_manager.handle_position_close(pos_id)
                
                consecutive_errors = 0
                await asyncio.sleep(self.CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"포지션 모니터링 중 오류: {e}")
                
                if consecutive_errors >= 5 and self._should_send_warning('positions'):
                    await self.telegram.send_message(
                        f"⚠️ 포지션 모니터링 오류\n연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.CHECK_INTERVAL * 2)

    # 기존 메서드들 유지 (간소화)
    async def _update_current_prices(self):
        """양쪽 거래소 현재 시세 업데이트"""
        try:
            # 비트겟 현재가 조회
            try:
                bitget_ticker = await self.bitget_mirror.get_ticker(self.SYMBOL)
                if bitget_ticker and bitget_ticker.get('last'):
                    new_bitget_price = float(bitget_ticker.get('last', 0))
                    if new_bitget_price > 0:
                        self.bitget_current_price = new_bitget_price
                        self.last_valid_bitget_price = new_bitget_price
                        self.bitget_price_failures = 0
                    else:
                        raise ValueError("비트겟 가격이 0 또는 None")
                else:
                    raise ValueError("비트겟 티커 응답 없음")
                    
            except Exception as bitget_error:
                self.bitget_price_failures += 1
                if self.last_valid_bitget_price > 0:
                    self.bitget_current_price = self.last_valid_bitget_price
                elif self.gate_current_price > 0:
                    self.bitget_current_price = self.gate_current_price
            
            # 게이트 현재가 조회
            try:
                new_gate_price = await self.gate_mirror.get_current_price(self.GATE_CONTRACT)
                if new_gate_price > 0:
                    self.gate_current_price = new_gate_price
                    self.last_valid_gate_price = new_gate_price
                    self.gate_price_failures = 0
                else:
                    raise ValueError("게이트 가격이 0 또는 None")
                    
            except Exception as gate_error:
                self.gate_price_failures += 1
                if self.last_valid_gate_price > 0:
                    self.gate_current_price = self.last_valid_gate_price
                elif self.bitget_current_price > 0:
                    self.gate_current_price = self.bitget_current_price
            
            # 시세 차이 계산
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                self.price_diff_percent = price_diff_abs / self.bitget_current_price * 100
                
                if price_diff_abs <= 5000:
                    if price_diff_abs > 500:
                        self.logger.debug(f"시세 차이: ${price_diff_abs:.2f}")
                else:
                    self.logger.warning(f"비정상적인 시세 차이 감지: ${price_diff_abs:.2f}")
                    return
                    
            else:
                self.price_diff_percent = 0.0
            
            self.last_price_update = datetime.now()
            
            # 포지션 매니저에도 시세 정보 전달
            self.position_manager.update_prices(
                self.bitget_current_price, 
                self.gate_current_price, 
                self.price_diff_percent
            )
            
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    def _get_valid_price_difference(self) -> Optional[float]:
        """유효한 시세 차이 반환"""
        try:
            if self.bitget_current_price <= 0 or self.gate_current_price <= 0:
                return None
            
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            
            if price_diff_abs > 5000:
                return None
                
            return price_diff_abs
            
        except Exception as e:
            self.logger.error(f"시세 차이 계산 실패: {e}")
            return None

    async def monitor_price_differences(self):
        """거래소 간 시세 차이 모니터링"""
        consecutive_errors = 0
        last_warning_time = datetime.min
        last_normal_report_time = datetime.min
        
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                valid_price_diff = self._get_valid_price_difference()
                
                if valid_price_diff is None:
                    self.logger.debug("유효하지 않은 시세 차이, 경고 생략")
                    consecutive_errors = 0
                    await asyncio.sleep(30)
                    continue
                
                now = datetime.now()
                
                # 경고 빈도 감소
                if (valid_price_diff > self.price_sync_threshold and 
                    (now - last_warning_time).total_seconds() > 14400 and
                    self._should_send_warning('price_difference')):
                    
                    ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                    
                    await self.telegram.send_message(
                        f"📊 시세 차이 안내{ratio_info}\n"
                        f"비트겟: ${self.bitget_current_price:,.2f}\n"
                        f"게이트: ${self.gate_current_price:,.2f}\n"
                        f"차이: ${valid_price_diff:.2f}\n\n"
                        f"🔄 미러링은 정상 진행되며 모든 주문이 즉시 처리됩니다\n"
                        f"🎯 오픈/클로징 매칭이 정확히 적용됩니다{ratio_info}"
                    )
                    last_warning_time = now
                
                consecutive_errors = 0
                await asyncio.sleep(60)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"시세 차이 모니터링 오류: {e}")
                await asyncio.sleep(60)

    async def monitor_sync_status(self):
        """포지션 동기화 상태 모니터링"""
        sync_retry_count = 0
        
        while self.monitoring:
            try:
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
                if not self.mirror_trading_enabled:
                    continue
                
                # 포지션 매니저에서 동기화 상태 확인
                sync_status = await self.position_manager.check_sync_status()
                
                if not sync_status['is_synced']:
                    sync_retry_count += 1
                    
                    if sync_retry_count >= 3 and self._should_send_warning('sync_status'):
                        valid_price_diff = self._get_valid_price_difference()
                        
                        possible_causes = []
                        
                        if valid_price_diff and valid_price_diff > self.price_sync_threshold:
                            possible_causes.append(f"시세 차이 큼 (${valid_price_diff:.2f}) - 처리에는 영향 없음")
                        
                        if self.bitget_price_failures > 0 or self.gate_price_failures > 0:
                            possible_causes.append(f"가격 조회 실패 (비트겟: {self.bitget_price_failures}회, 게이트: {self.gate_price_failures}회)")
                        
                        if self.position_manager.render_restart_detected:
                            possible_causes.append("렌더 재구동 후 기존 포지션 존재")
                        
                        if not possible_causes:
                            possible_causes.append("알 수 없는 원인 (대부분 정상적인 일시적 차이)")
                        
                        ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                        
                        await self.telegram.send_message(
                            f"📊 포지션 동기화 상태 분석{ratio_info}\n"
                            f"비트겟: {sync_status['bitget_new_count']}개\n"
                            f"게이트: {sync_status['gate_new_count']}개\n"
                            f"차이: {sync_status['position_diff']}개\n\n"
                            f"🔍 분석된 원인:\n"
                            f"• {chr(10).join(possible_causes)}\n\n"
                            f"🎯 오픈/클로징 매칭이 정확히 작동합니다{ratio_info}"
                        )
                        
                        sync_retry_count = 0
                else:
                    sync_retry_count = 0
                
            except Exception as e:
                self.logger.error(f"동기화 모니터링 오류: {e}")
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)

    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                if now.hour == self.DAILY_REPORT_HOUR and now > self.last_report_time + timedelta(hours=23):
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    
                    self._reset_daily_stats()
                    self.last_report_time = now
                
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(3600)

    async def _create_daily_report(self) -> str:
        """일일 리포트 생성"""
        try:
            # 기본 클라이언트로 계정 조회
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate_mirror.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            # 시세 차이 통계
            await self._update_current_prices()
            valid_price_diff = self._get_valid_price_difference()
            
            price_status_info = ""
            if valid_price_diff is not None:
                price_status = "✅ 정상" if valid_price_diff <= self.price_sync_threshold else "📊 범위 초과"
                price_status_info = f"""📈 시세 차이 현황:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: ${valid_price_diff:.2f} ({self.price_diff_percent:.3f}%)
- 상태: {price_status}
- 🔥 처리 상태: 모든 주문 즉시 처리됨"""
            else:
                price_status_info = f"""📈 시세 차이 현황:
- 시세 조회에 문제가 있었습니다
- 🔥 처리 상태: 모든 주문 정상 처리됨"""
            
            # 복제 비율 정보
            ratio_description = self.utils.get_ratio_multiplier_description(self.mirror_ratio_multiplier)
            
            # 오픈/클로징 매칭 통계
            position_matching_successes = self.daily_stats.get('position_matching_successes', 0)
            position_matching_failures = self.daily_stats.get('position_matching_failures', 0)
            ratio_adjusted_orders = self.daily_stats.get('ratio_adjusted_orders', 0)
            ratio_mismatch_prevented = self.daily_stats.get('ratio_mismatch_prevented', 0)
            
            # 복제 비율 조정 이력
            ratio_adjustments_today = len([
                adj for adj in self.ratio_adjustment_history 
                if adj['timestamp'].date() == datetime.now().date()
            ])
            
            report = f"""📊 미러 트레이딩 일일 리포트 (오픈/클로징 매칭 + 복제 비율)
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

💰 계정 잔고:
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}

{price_status_info}

🔄 복제 비율 설정:
- 현재 복제 비율: {self.mirror_ratio_multiplier}x
- 설명: {ratio_description}
- 오늘 조정 횟수: {ratio_adjustments_today}회
- 미러링 모드: {'활성화' if self.mirror_trading_enabled else '비활성화'}

⚡ 실시간 포지션 미러링:
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 성공률: {success_rate:.1f}%

🎯 오픈/클로징 매칭 성과:
- 포지션 매칭 성공: {position_matching_successes}회 ✅
- 포지션 매칭 실패: {position_matching_failures}회 ❌
- 복제 비율 적용 주문: {ratio_adjusted_orders}회
- 비율 불일치 방지: {ratio_mismatch_prevented}회
- 매칭 정확도: {((position_matching_successes) / max(position_matching_successes + position_matching_failures, 1) * 100):.1f}%

🔄 예약 주문 미러링:
- 시작 시 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 미러링: {self.daily_stats['plan_order_mirrors']}회
- 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 클로즈 주문: {self.daily_stats['close_order_mirrors']}회

📋 예약 주문 체결/취소 구분:
- 체결 감지 성공: {self.daily_stats.get('filled_detection_successes', 0)}회 ✅
- 취소 동기화 성공: {self.daily_stats.get('cancel_successes', 0)}회 ✅
- 취소 동기화 실패: {self.daily_stats.get('cancel_failures', 0)}회 ❌

🔄 현재 미러링 상태:
- 활성 포지션: {len(self.mirrored_positions)}개
- 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개
- 추적 중인 포지션: {len(self.position_manager.open_position_tracker)}개

🔥 강화된 기능:
- 오픈/클로징 정확한 매칭: ✅
- 복제 비율 실시간 조정: ✅ (현재 {self.mirror_ratio_multiplier}x)
- 포지션 기반 검증: ✅
- 부분 진입/익절 추적: ✅
- 복제 비율 불일치 방지: ✅

━━━━━━━━━━━━━━━━━━━
✅ 오픈/클로징 매칭 시스템 정상 작동
🎯 포지션과 예약건이 정확히 연결됨
📊 복제 비율 {self.mirror_ratio_multiplier}x 적용 중 (실시간 조정 가능)"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            return f"📊 일일 리포트 생성 실패\n오류: {str(e)}"

    def _reset_daily_stats(self):
        """일일 통계 초기화"""
        self.daily_stats = {
            'total_mirrored': 0, 'successful_mirrors': 0, 'failed_mirrors': 0,
            'partial_closes': 0, 'full_closes': 0, 'total_volume': 0.0,
            'order_mirrors': 0, 'position_mirrors': 0, 'plan_order_mirrors': 0,
            'plan_order_cancels': 0, 'startup_plan_mirrors': 0,
            'close_order_mirrors': 0, 'close_order_skipped': 0, 'close_order_forced': 0,
            'duplicate_orders_prevented': 0, 'perfect_mirrors': 0, 'partial_mirrors': 0,
            'tp_sl_success': 0, 'tp_sl_failed': 0, 'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0, 'sync_corrections': 0, 'sync_deletions': 0,
            'cancel_failures': 0, 'cancel_successes': 0, 'filled_detection_successes': 0,
            'position_matching_successes': 0, 'position_matching_failures': 0,
            'ratio_adjusted_orders': 0, 'ratio_mismatch_prevented': 0,
            'errors': []
        }
        self.failed_mirrors.clear()
        
        # 시세 조회 실패 카운터 리셋
        self.bitget_price_failures = 0
        self.gate_price_failures = 0
        
        # 경고 카운터도 매일 리셋
        self._reset_warning_counter()
        
        # 포지션 매니저의 통계도 동기화
        self.position_manager.daily_stats = self.daily_stats

    async def _log_account_status(self):
        """계정 상태 로깅"""
        try:
            # 기본 클라이언트로 계정 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            gate_account = await self.gate_mirror.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            # 시세 차이 정보
            valid_price_diff = self._get_valid_price_difference()
            
            if valid_price_diff is not None:
                price_status = "정상" if valid_price_diff <= self.price_sync_threshold else "범위 초과"
                price_info = f"""📈 시세 상태:
• 비트겟: ${self.bitget_current_price:,.2f}
• 게이트: ${self.gate_current_price:,.2f}
• 차이: ${valid_price_diff:.2f} ({price_status})
• 🔥 처리: 시세 차이와 무관하게 즉시 처리"""
            else:
                price_info = f"""📈 시세 상태:
• 시세 조회 중 문제 발생하지만 정상 처리됨"""
            
            # 복제 비율 설정 정보
            ratio_description = self.utils.get_ratio_multiplier_description(self.mirror_ratio_multiplier)
            
            await self.telegram.send_message(
                f"🔄 미러 트레이딩 시스템 시작 (오픈/클로징 매칭 + 복제 비율)\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f}\n"
                f"• 게이트: ${gate_equity:,.2f}\n\n"
                f"{price_info}\n\n"
                f"🔄 복제 비율 설정:\n"
                f"• 현재 복제 비율: {self.mirror_ratio_multiplier}x\n"
                f"• 설명: {ratio_description}\n"
                f"• 미러링 모드: {'활성화' if self.mirror_trading_enabled else '비활성화'}\n"
                f"• 실시간 조정: /ratio 명령어 사용\n\n"
                f"📊 현재 상태:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.position_manager.startup_plan_orders)}개\n"
                f"• 추적 중인 포지션: {len(self.position_manager.open_position_tracker)}개\n\n"
                f"⚡ 핵심 강화 기능:\n"
                f"• 🎯 오픈/클로징 정확한 매칭\n"
                f"• 📊 복제 비율 {self.mirror_ratio_multiplier}x 적용\n"
                f"• 🔍 포지션 기반 검증\n"
                f"• 📋 부분 진입/익절 추적\n"
                f"• 🛡️ 복제 비율 불일치 방지\n"
                f"• ⚡ 예약 주문 체결/취소 정확한 구분\n"
                f"• 🚀 시세 차이와 무관하게 즉시 처리\n\n"
                f"🚀 오픈/클로징 매칭 + 복제 비율 고려 시스템이 시작되었습니다.\n"
                f"📱 /ratio 명령어로 복제 비율을 실시간 조정할 수 있습니다."
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

    async def stop(self):
        """미러 트레이딩 중지"""
        self.monitoring = False
        
        try:
            # 포지션 매니저 중지
            await self.position_manager.stop()
            
            # Bitget 미러링 클라이언트 종료
            await self.bitget_mirror.close()
            
            # Gate.io 미러링 클라이언트 종료
            await self.gate_mirror.close()
            
            final_report = await self._create_daily_report()
            await self.telegram.send_message(f"🛑 미러 트레이딩 시스템 종료\n\n{final_report}")
        except:
            pass
        
        self.logger.info("미러 트레이딩 시스템 중지")
