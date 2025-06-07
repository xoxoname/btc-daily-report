import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import traceback
from collections import defaultdict

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """🔥🔥🔥 미러 포지션 매니저 - 게이트 예약주문 보호 강화"""
    
    def __init__(self, config, bitget_mirror, gate_mirror, telegram_bot):
        self.config = config
        self.bitget_mirror = bitget_mirror
        self.gate_mirror = gate_mirror
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 미러링 상태 추적
        self.mirrored_positions = {}
        self.mirrored_plan_orders = {}
        
        # 주문 매핑 (양방향)
        self.bitget_to_gate_order_mapping = {}
        self.gate_to_bitget_order_mapping = {}
        
        # 시작 시 기존 주문/포지션 (복제 방지용)
        self.startup_plan_orders = set()
        self.startup_positions = set()
        
        # 🔥🔥🔥 게이트 예약주문 보호 강화
        self.order_deduplication_window = 600  # 🔥 5분 → 10분으로 연장
        self.recently_processed_orders = {}
        self.order_processing_locks = {}
        
        # 🔥🔥🔥 게이트 주문 삭제 방지 강화
        self.gate_order_protection_enabled = True  # 게이트 주문 보호 활성화
        self.safe_deletion_threshold = 3  # 안전 삭제 임계값 (재확인 횟수)
        self.deletion_verification_delay = 15  # 삭제 전 대기 시간 (초)
        
        # 🔥🔥🔥 비트겟 주문 상태 검증 강화
        self.strict_bitget_verification = True  # 비트겟 주문 존재 여부 엄격 검증
        self.protection_mode_enabled = True     # 보호 모드 활성화
        
        # 포지션 대기 설정
        self.position_wait_timeout = 180
        self.price_sync_threshold = 1000.0
        
        # 게이트 기존 주문 상세 정보 (중복 방지용)
        self.gate_existing_orders_detailed = {}
        
        # 🔥🔥🔥 삭제 시도 기록 (과도한 삭제 방지)
        self.deletion_attempts = {}  # gate_order_id -> {'count': int, 'last_attempt': datetime}
        self.max_deletion_attempts = 2  # 최대 삭제 시도 횟수
        self.deletion_cooldown = 3600  # 삭제 시도 쿨다운 (초)
        
        # 통계
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'startup_plan_mirrors': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0,
            'position_size_corrections': 0,
            'deletion_prevented': 0,  # 🔥 삭제 방지 통계 추가
            'errors': []
        }
        
        self.logger.info("🔥 미러 포지션 매니저 초기화 완료 - 게이트 예약주문 보호 강화")

    async def initialize(self):
        """초기화"""
        try:
            self.logger.info("🔄 미러 포지션 매니저 초기화 시작")
            
            # 기존 포지션 및 주문 상태 조회
            await self._load_existing_positions()
            await self._load_existing_plan_orders()
            
            self.logger.info("✅ 미러 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"미러 포지션 매니저 초기화 실패: {e}")
            raise

    async def _load_existing_positions(self):
        """기존 포지션 로드"""
        try:
            # Bitget 포지션 조회
            bitget_positions = await self.bitget_mirror.get_positions()
            
            # Gate 포지션 조회
            gate_positions = await self.gate_mirror.get_positions()
            
            self.logger.info(f"기존 포지션 조회 완료 - Bitget: {len(bitget_positions)}개, Gate: {len(gate_positions)}개")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 로드 실패: {e}")

    async def _load_existing_plan_orders(self):
        """🔥🔥🔥 기존 예약주문 로드 - 보호 설정 포함"""
        try:
            # Bitget 예약주문 조회
            bitget_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            
            # Gate 예약주문 조회
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            
            # 기존 Bitget 주문 ID 저장 (중복 방지용)
            for order in bitget_orders.get('plan_orders', []) + bitget_orders.get('tp_sl_orders', []):
                order_id = order.get('orderId', order.get('planOrderId'))
                if order_id:
                    self.startup_plan_orders.add(order_id)
            
            # 🔥🔥🔥 기존 Gate 주문 상세 정보 저장 및 보호 설정
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id')
                if gate_order_id:
                    self.gate_existing_orders_detailed[gate_order_id] = {
                        'order': gate_order,
                        'timestamp': datetime.now(),
                        'protected': True,  # 🔥 기존 주문은 보호
                        'source': 'startup'
                    }
            
            self.logger.info(f"기존 예약주문 로드 완료 - Bitget: {len(self.startup_plan_orders)}개, Gate: {len(gate_orders)}개 (모두 보호됨)")
            
        except Exception as e:
            self.logger.error(f"기존 예약주문 로드 실패: {e}")

    async def mirror_plan_order(self, bitget_order: Dict) -> bool:
        """🔥🔥🔥 예약 주문 미러링 - 강화된 보호 로직"""
        order_id = bitget_order.get('orderId', bitget_order.get('planOrderId'))
        
        if not order_id:
            self.logger.warning("주문 ID가 없는 주문 무시")
            return False
        
        try:
            # 🔥🔥🔥 중복 처리 방지 (락 사용)
            if order_id in self.order_processing_locks:
                self.logger.debug(f"이미 처리 중인 주문: {order_id}")
                return False
            
            self.order_processing_locks[order_id] = datetime.now()
            
            try:
                # 이미 미러링된 주문인지 확인
                if order_id in self.mirrored_plan_orders:
                    self.logger.debug(f"이미 미러링된 주문: {order_id}")
                    return True
                
                # 최근 처리된 주문인지 확인 (중복 방지)
                if await self._is_recently_processed(order_id):
                    self.logger.debug(f"최근 처리된 주문: {order_id}")
                    return True
                
                # 주문 정보 추출 및 검증
                validation_result = await self._extract_and_validate_order_info(bitget_order)
                if not validation_result['valid']:
                    self.logger.warning(f"주문 검증 실패: {order_id} - {validation_result['reason']}")
                    return False
                
                order_info = validation_result['order_info']
                
                # 🔥🔥🔥 중복 게이트 주문 검증 강화
                duplicate_check = await self._check_duplicate_gate_order_enhanced(order_info)
                if duplicate_check['is_duplicate']:
                    self.logger.info(f"중복 게이트 주문 감지, 미러링 생략: {order_id}")
                    self.daily_stats['duplicate_orders_prevented'] += 1
                    return True
                
                # 게이트 주문 생성
                gate_result = await self._create_gate_order_safe(order_info)
                if not gate_result['success']:
                    self.logger.error(f"게이트 주문 생성 실패: {order_id} - {gate_result['error']}")
                    return False
                
                gate_order_id = gate_result['gate_order_id']
                
                # 🔥🔥🔥 미러링 기록 및 보호 설정
                await self._record_successful_mirror(order_id, bitget_order, gate_order_id, order_info)
                
                # 최근 처리된 주문으로 기록
                self.recently_processed_orders[order_id] = datetime.now()
                
                self.logger.info(f"✅ 예약 주문 미러링 성공: {order_id} → {gate_order_id}")
                return True
                
            finally:
                # 락 해제
                if order_id in self.order_processing_locks:
                    del self.order_processing_locks[order_id]
            
        except Exception as e:
            self.logger.error(f"예약 주문 미러링 실패: {order_id} - {e}")
            self.daily_stats['failed_mirrors'] += 1
            self.daily_stats['errors'].append(f"Mirror order {order_id}: {str(e)}")
            return False

    async def _is_recently_processed(self, order_id: str) -> bool:
        """최근 처리된 주문인지 확인"""
        if order_id in self.recently_processed_orders:
            processed_time = self.recently_processed_orders[order_id]
            elapsed = (datetime.now() - processed_time).total_seconds()
            return elapsed < self.order_deduplication_window
        return False

    async def _extract_and_validate_order_info(self, bitget_order: Dict) -> Dict:
        """주문 정보 추출 및 검증"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId'))
            side = bitget_order.get('side', bitget_order.get('tradeSide', ''))
            size = float(bitget_order.get('size', bitget_order.get('sz', 0)))
            trigger_price = float(bitget_order.get('triggerPrice', bitget_order.get('executePrice', 0)))
            
            # 기본 유효성 검사
            if not all([order_id, side, size > 0, trigger_price > 0]):
                return {
                    'valid': False,
                    'reason': 'Missing required fields or invalid values'
                }
            
            # TP/SL 정보 추출
            tp_price, sl_price = await self._extract_tp_sl_info(bitget_order)
            
            return {
                'valid': True,
                'order_info': {
                    'order_id': order_id,
                    'side': side,
                    'size': size,
                    'trigger_price': trigger_price,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'original_order': bitget_order
                }
            }
            
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Extraction error: {str(e)}'
            }

    async def _extract_tp_sl_info(self, bitget_order: Dict) -> Tuple[Optional[float], Optional[float]]:
        """TP/SL 정보 추출"""
        try:
            tp_price = None
            sl_price = None
            
            # TP 추출
            tp_fields = ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice', 'tpPrice']
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            break
                    except:
                        continue
            
            # SL 추출
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopLoss', 'slPrice']
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            break
                    except:
                        continue
            
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"TP/SL 정보 추출 실패: {e}")
            return None, None

    async def _check_duplicate_gate_order_enhanced(self, order_info: Dict) -> Dict:
        """🔥🔥🔥 중복 게이트 주문 검증 강화"""
        try:
            # 현재 게이트 주문들 조회
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            
            target_side = order_info['side']
            target_price = order_info['trigger_price']
            target_size = order_info['size']
            
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id')
                gate_side = gate_order.get('side', '')
                gate_price = float(gate_order.get('price', 0))
                gate_size = float(gate_order.get('size', 0))
                
                # 🔥🔥🔥 더 엄격한 중복 검사 (방향, 가격, 크기 모두 고려)
                if (gate_side == target_side and
                    abs(gate_price - target_price) / target_price < 0.001 and  # 0.1% 이내
                    abs(gate_size - target_size) / target_size < 0.05):  # 5% 이내
                    
                    # 🔥🔥🔥 이미 매핑된 주문인지 확인
                    if gate_order_id in self.gate_to_bitget_order_mapping:
                        linked_bitget_id = self.gate_to_bitget_order_mapping[gate_order_id]
                        return {
                            'is_duplicate': True,
                            'existing_gate_order_id': gate_order_id,
                            'linked_bitget_order_id': linked_bitget_id,
                            'reason': 'Already mapped to another Bitget order'
                        }
                    
                    # 🔥🔥🔥 매핑되지 않은 유사한 주문이면 보호 설정
                    return {
                        'is_duplicate': True,
                        'existing_gate_order_id': gate_order_id,
                        'reason': 'Similar order exists but not mapped'
                    }
            
            return {'is_duplicate': False}
            
        except Exception as e:
            self.logger.error(f"중복 게이트 주문 검증 실패: {e}")
            return {'is_duplicate': False}

    async def _create_gate_order_safe(self, order_info: Dict) -> Dict:
        """🔥🔥🔥 안전한 게이트 주문 생성"""
        try:
            # 게이트 주문 생성 요청
            gate_result = await self.gate_mirror.create_price_triggered_order(
                side=order_info['side'],
                size=order_info['size'],
                price=order_info['trigger_price'],
                tp_price=order_info.get('tp_price'),
                sl_price=order_info.get('sl_price')
            )
            
            if gate_result['success']:
                gate_order_id = gate_result['order_id']
                
                # 🔥🔥🔥 새로 생성된 게이트 주문 보호 설정
                self.gate_existing_orders_detailed[gate_order_id] = {
                    'order': gate_result.get('order_details', {}),
                    'timestamp': datetime.now(),
                    'protected': True,  # 🔥 새로 생성된 주문도 보호
                    'source': 'mirrored',
                    'bitget_order_id': order_info['order_id']
                }
                
                return {
                    'success': True,
                    'gate_order_id': gate_order_id,
                    'order_details': gate_result.get('order_details', {})
                }
            else:
                return {
                    'success': False,
                    'error': gate_result.get('error', 'Unknown error')
                }
                
        except Exception as e:
            self.logger.error(f"게이트 주문 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _record_successful_mirror(self, bitget_order_id: str, bitget_order: Dict, gate_order_id: str, order_info: Dict):
        """🔥🔥🔥 성공적인 미러링 기록"""
        try:
            # 양방향 매핑 설정
            self.bitget_to_gate_order_mapping[bitget_order_id] = gate_order_id
            self.gate_to_bitget_order_mapping[gate_order_id] = bitget_order_id
            
            # 미러링된 예약주문 기록
            self.mirrored_plan_orders[bitget_order_id] = {
                'gate_order_id': gate_order_id,
                'bitget_order': bitget_order,
                'order_info': order_info,
                'timestamp': datetime.now(),
                'perfect_mirror': order_info.get('tp_price') is not None or order_info.get('sl_price') is not None
            }
            
            # 통계 업데이트
            self.daily_stats['total_mirrored'] += 1
            self.daily_stats['successful_mirrors'] += 1
            self.daily_stats['plan_order_mirrors'] += 1
            
            if order_info.get('tp_price') or order_info.get('sl_price'):
                self.daily_stats['perfect_mirrors'] += 1
                self.daily_stats['tp_sl_success'] += 1
            else:
                self.daily_stats['partial_mirrors'] += 1
            
        except Exception as e:
            self.logger.error(f"미러링 기록 실패: {e}")

    async def analyze_order_sync_status(self) -> Optional[Dict]:
        """🔥🔥🔥 주문 동기화 상태 분석 - 안전한 방식"""
        try:
            # 🔥🔥🔥 보호 모드가 활성화된 경우 분석 제한
            if self.gate_order_protection_enabled:
                self.logger.debug("게이트 주문 보호 모드 활성화로 동기화 분석 제한")
                return None
            
            # 비트겟 예약 주문 조회
            bitget_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            all_bitget_orders = bitget_orders.get('plan_orders', []) + bitget_orders.get('tp_sl_orders', [])
            
            # 게이트 예약 주문 조회
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            
            # 분석 결과
            missing_mirrors = []
            orphaned_orders = []
            
            # 🔥🔥🔥 누락된 미러링 찾기 (시작 시 기존 주문 제외)
            for bitget_order in all_bitget_orders:
                order_id = bitget_order.get('orderId', bitget_order.get('planOrderId'))
                if not order_id:
                    continue
                
                # 시작 시 기존 주문은 제외
                if order_id in self.startup_plan_orders:
                    continue
                
                # 미러링되지 않은 주문 찾기
                if order_id not in self.mirrored_plan_orders:
                    missing_mirrors.append({
                        'bitget_order_id': order_id,
                        'bitget_order': bitget_order
                    })
            
            # 🔥🔥🔥 고아 게이트 주문 찾기 - 매우 신중하게 (거의 하지 않음)
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id')
                if not gate_order_id:
                    continue
                
                # 🔥🔥🔥 보호된 기존 주문인지 확인
                if gate_order_id in self.gate_existing_orders_detailed:
                    existing_info = self.gate_existing_orders_detailed[gate_order_id]
                    if existing_info.get('protected', False):
                        continue  # 보호된 주문은 고아로 간주하지 않음
                
                # 🔥🔥🔥 삭제 시도 횟수 확인
                if self._is_deletion_rate_limited(gate_order_id):
                    self.logger.info(f"삭제 시도 제한으로 인한 생략: {gate_order_id}")
                    continue
                
                # 매핑되지 않은 게이트 주문 찾기
                if gate_order_id not in self.gate_to_bitget_order_mapping:
                    # 🔥🔥🔥 추가 검증: 유사한 비트겟 주문이 있는지 확인
                    has_similar_bitget = await self._check_similar_bitget_order_exists(gate_order, all_bitget_orders)
                    
                    if not has_similar_bitget:
                        orphaned_orders.append({
                            'gate_order_id': gate_order_id,
                            'gate_order': gate_order
                        })
            
            return {
                'missing_mirrors': missing_mirrors,
                'orphaned_orders': orphaned_orders,
                'bitget_total': len(all_bitget_orders),
                'gate_total': len(gate_orders),
                'mapped_count': len(self.mirrored_plan_orders)
            }
            
        except Exception as e:
            self.logger.error(f"주문 동기화 상태 분석 실패: {e}")
            return None

    def _is_deletion_rate_limited(self, gate_order_id: str) -> bool:
        """🔥🔥🔥 삭제 시도 제한 확인"""
        if gate_order_id not in self.deletion_attempts:
            return False
        
        attempt_info = self.deletion_attempts[gate_order_id]
        
        # 최대 시도 횟수 초과 확인
        if attempt_info['count'] >= self.max_deletion_attempts:
            # 쿨다운 시간 확인
            elapsed = (datetime.now() - attempt_info['last_attempt']).total_seconds()
            if elapsed < self.deletion_cooldown:
                return True
            else:
                # 쿨다운 시간이 지나면 리셋
                del self.deletion_attempts[gate_order_id]
                return False
        
        return False

    def _record_deletion_attempt(self, gate_order_id: str):
        """🔥🔥🔥 삭제 시도 기록"""
        if gate_order_id not in self.deletion_attempts:
            self.deletion_attempts[gate_order_id] = {'count': 0, 'last_attempt': datetime.now()}
        
        self.deletion_attempts[gate_order_id]['count'] += 1
        self.deletion_attempts[gate_order_id]['last_attempt'] = datetime.now()

    async def _check_similar_bitget_order_exists(self, gate_order: Dict, bitget_orders: List[Dict]) -> bool:
        """🔥🔥🔥 유사한 비트겟 주문 존재 여부 확인 - 더 관대한 기준"""
        try:
            gate_side = gate_order.get('side', '')
            gate_price = float(gate_order.get('price', 0))
            gate_size = float(gate_order.get('size', 0))
            
            # 🔥🔥🔥 매우 관대한 기준으로 유사한 주문 검색
            for bitget_order in bitget_orders:
                bitget_side = bitget_order.get('side', bitget_order.get('tradeSide', ''))
                bitget_price = float(bitget_order.get('triggerPrice', bitget_order.get('executePrice', 0)))
                bitget_size = float(bitget_order.get('size', bitget_order.get('sz', 0)))
                
                # 방향, 가격, 크기가 유사하면 고아가 아닐 수 있음
                if (bitget_side == gate_side and 
                    gate_price > 0 and bitget_price > 0 and
                    abs(bitget_price - gate_price) / gate_price < 0.1 and  # 🔥 10% 이내로 매우 관대하게
                    gate_size > 0 and bitget_size > 0 and
                    abs(bitget_size - gate_size) / gate_size < 0.3):  # 🔥 30% 이내로 매우 관대하게
                    
                    self.logger.info(f"유사한 비트겟 주문 발견, 고아 아님: {gate_order.get('id')}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"유사한 비트겟 주문 검색 실패: {e}")
            return True  # 검색 실패 시 안전하게 고아가 아닌 것으로 판단

    async def cleanup_close_orders_without_position(self):
        """포지션 없는 클로즈 주문 정리"""
        try:
            # 🔥🔥🔥 보호 모드에서는 정리하지 않음
            if self.gate_order_protection_enabled:
                self.logger.debug("보호 모드 활성화로 클로즈 주문 정리 생략")
                return
            
            # 현재 포지션 확인
            bitget_positions = await self.bitget_mirror.get_positions()
            gate_positions = await self.gate_mirror.get_positions()
            
            has_position = any(
                float(pos.get('total', pos.get('sizeQty', pos.get('size', 0)))) != 0
                for pos in bitget_positions + gate_positions
            )
            
            if has_position:
                return  # 포지션이 있으면 정리하지 않음
            
            # 클로즈 주문 찾기 및 정리는 매우 신중하게 수행
            self.logger.debug("포지션 없는 상태에서 클로즈 주문 확인 중...")
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 정리 실패: {e}")

    async def monitor_position_changes(self):
        """포지션 변화 모니터링"""
        try:
            # 포지션 변화 감지 로직
            pass
            
        except Exception as e:
            self.logger.error(f"포지션 변화 모니터링 실패: {e}")

    async def handle_order_fill(self, order: Dict):
        """주문 체결 처리"""
        try:
            # 주문 체결 처리 로직
            pass
            
        except Exception as e:
            self.logger.error(f"주문 체결 처리 실패: {e}")

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("🛑 미러 포지션 매니저 중지")
            
            # 🔥🔥🔥 종료 시 보호된 주문 현황 로그
            protected_count = len([
                order_id for order_id, info in self.gate_existing_orders_detailed.items()
                if info.get('protected', False)
            ])
            
            self.logger.info(f"종료 시점 보호된 게이트 주문: {protected_count}개")
            self.logger.info(f"삭제 방지 통계: {self.daily_stats.get('deletion_prevented', 0)}회")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 실패: {e}")

    def get_stats(self) -> Dict:
        """통계 반환"""
        return self.daily_stats.copy()

    def reset_daily_stats(self):
        """일일 통계 리셋"""
        # 🔥🔥🔥 보호 관련 통계는 누적
        deletion_prevented = self.daily_stats.get('deletion_prevented', 0)
        
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'startup_plan_mirrors': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0,
            'position_size_corrections': 0,
            'deletion_prevented': deletion_prevented,  # 🔥 누적 유지
            'errors': []
        }
