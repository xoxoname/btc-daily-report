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
        self.order_deduplication_window = 300  # 5분
        self.recently_processed_orders = {}
        self.order_processing_locks = {}
        
        # 🔥🔥🔥 비트겟 주문 상태 검증 강화
        self.strict_bitget_verification = True  # 비트겟 주문 존재 여부 엄격 검증
        self.protection_mode_enabled = True     # 보호 모드 활성화
        
        # 포지션 대기 설정
        self.position_wait_timeout = 180
        self.price_sync_threshold = 1000.0
        
        # 게이트 기존 주문 상세 정보 (중복 방지용)
        self.gate_existing_orders_detailed = {}
        
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
            'errors': []
        }
        
        self.logger.info("🔥 미러 포지션 매니저 초기화 완료 - 게이트 예약주문 보호 강화")

    async def initialize(self):
        """초기화"""
        try:
            self.logger.info("🔍 미러 포지션 매니저 초기화 시작")
            
            # 🔥🔥🔥 기존 상태 조회 및 보호 설정
            await self._load_existing_states()
            
            # 🔥🔥🔥 게이트 기존 주문 상세 정보 수집
            await self._collect_gate_existing_orders_detailed()
            
            # 정리 작업 스케줄링
            asyncio.create_task(self._periodic_cleanup())
            
            self.logger.info("✅ 미러 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"미러 포지션 매니저 초기화 실패: {e}")
            raise

    async def _load_existing_states(self):
        """기존 상태 로드 및 보호 설정"""
        try:
            # 기존 비트겟 예약 주문 로드
            bitget_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            
            plan_orders = bitget_orders.get('plan_orders', [])
            tp_sl_orders = bitget_orders.get('tp_sl_orders', [])
            
            for order in plan_orders + tp_sl_orders:
                order_id = order.get('orderId', order.get('planOrderId'))
                if order_id:
                    self.startup_plan_orders.add(order_id)
            
            # 기존 포지션 로드
            bitget_positions = await self.bitget_mirror.get_positions(self.config.symbol)
            for pos in bitget_positions:
                if float(pos.get('total', pos.get('sizeQty', 0))) > 0:
                    position_key = f"{pos.get('symbol', '')}_{pos.get('holdSide', '')}"
                    self.startup_positions.add(position_key)
            
            self.logger.info(f"기존 상태 로드 완료: 예약주문 {len(self.startup_plan_orders)}개, 포지션 {len(self.startup_positions)}개")
            
        except Exception as e:
            self.logger.error(f"기존 상태 로드 실패: {e}")

    async def _collect_gate_existing_orders_detailed(self):
        """🔥🔥🔥 게이트 기존 주문 상세 정보 수집 - 보호용"""
        try:
            self.logger.info("🔍 게이트 기존 주문 상세 정보 수집 시작")
            
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            
            for order in gate_orders:
                order_id = order.get('id')
                if order_id:
                    self.gate_existing_orders_detailed[order_id] = {
                        'order': order,
                        'recorded_at': datetime.now().isoformat(),
                        'protected': True,  # 🔥🔥🔥 기존 주문은 기본적으로 보호
                        'side': order.get('side', ''),
                        'price': float(order.get('price', 0)),
                        'size': float(order.get('size', 0))
                    }
            
            self.logger.info(f"✅ 게이트 기존 주문 상세 정보 수집 완료: {len(self.gate_existing_orders_detailed)}개 주문 보호 설정")
            
        except Exception as e:
            self.logger.error(f"게이트 기존 주문 상세 정보 수집 실패: {e}")

    async def mirror_plan_order(self, bitget_order: Dict) -> bool:
        """🔥🔥🔥 예약 주문 미러링 - 보호 로직 강화"""
        order_id = bitget_order.get('orderId', bitget_order.get('planOrderId'))
        if not order_id:
            return False
        
        try:
            # 🔥🔥🔥 중복 처리 방지 - 강화된 락 메커니즘
            if order_id in self.order_processing_locks:
                self.logger.debug(f"주문 처리 중 (락 설정됨): {order_id}")
                return False
            
            self.order_processing_locks[order_id] = datetime.now()
            
            try:
                # 이미 미러링된 주문인지 확인
                if order_id in self.mirrored_plan_orders:
                    self.logger.debug(f"이미 미러링된 주문: {order_id}")
                    return True
                
                # 🔥🔥🔥 시작 시 기존 주문은 미러링하지 않음 (보호)
                if order_id in self.startup_plan_orders:
                    self.logger.info(f"🛡️ 시작 시 기존 주문으로 미러링 제외 (보호): {order_id}")
                    self.daily_stats['startup_plan_mirrors'] += 1
                    return False
                
                # 🔥🔥🔥 최근 처리된 주문 체크 (더 강화)
                if self._is_recently_processed(order_id):
                    self.logger.debug(f"최근 처리된 주문: {order_id}")
                    self.daily_stats['duplicate_orders_prevented'] += 1
                    return False
                
                # 주문 정보 추출 및 검증
                result = await self._extract_and_validate_order_info(bitget_order)
                if not result['valid']:
                    self.logger.warning(f"주문 정보 검증 실패: {order_id} - {result['reason']}")
                    return False
                
                order_info = result['order_info']
                
                # 🔥🔥🔥 중복 게이트 주문 검증 강화
                duplicate_check = await self._check_duplicate_gate_order_enhanced(order_info)
                if duplicate_check['is_duplicate']:
                    self.logger.info(f"🛡️ 중복 게이트 주문 감지 (보호): {order_id} - {duplicate_check['reason']}")
                    self.daily_stats['duplicate_orders_prevented'] += 1
                    return False
                
                # 게이트 주문 생성
                gate_result = await self._create_gate_mirror_order(order_info)
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
                            'reason': f'Already mapped to bitget order {linked_bitget_id}'
                        }
                    
                    # 🔥🔥🔥 보호된 기존 주문인지 확인
                    if gate_order_id in self.gate_existing_orders_detailed:
                        existing_info = self.gate_existing_orders_detailed[gate_order_id]
                        if existing_info.get('protected', False):
                            return {
                                'is_duplicate': True,
                                'reason': f'Protected existing order {gate_order_id}'
                            }
                    
                    return {
                        'is_duplicate': True,
                        'reason': f'Similar order exists: {gate_order_id}'
                    }
            
            return {'is_duplicate': False}
            
        except Exception as e:
            self.logger.error(f"중복 게이트 주문 검증 실패: {e}")
            # 오류 시 안전하게 중복으로 간주
            return {
                'is_duplicate': True,
                'reason': f'Verification error: {str(e)}'
            }

    async def _create_gate_mirror_order(self, order_info: Dict) -> Dict:
        """게이트 미러 주문 생성"""
        try:
            # 계정 정보 조회
            gate_account = await self.gate_mirror.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            if gate_equity < 10:  # 최소 자산 체크
                return {
                    'success': False,
                    'error': f'Insufficient Gate equity: ${gate_equity:.2f}'
                }
            
            # 비율 기반 주문 크기 계산
            bitget_account = await self.bitget_mirror.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            if bitget_equity <= 0:
                return {
                    'success': False,
                    'error': 'Invalid Bitget equity'
                }
            
            # 원본 주문의 증거금 비율 계산
            original_margin_ratio = (order_info['size'] * order_info['trigger_price']) / bitget_equity
            
            # 게이트에서 동일한 비율로 계산
            gate_margin = gate_equity * original_margin_ratio
            gate_size = gate_margin / order_info['trigger_price']
            
            # 최소 주문 크기 체크
            if gate_size < 0.00001:
                return {
                    'success': False,
                    'error': f'Order size too small: {gate_size:.8f}'
                }
            
            # 게이트 주문 생성
            gate_order_data = {
                'contract': 'BTC_USDT',
                'side': order_info['side'],
                'size': gate_size,
                'price': order_info['trigger_price']
            }
            
            gate_result = await self.gate_mirror.create_price_triggered_order(**gate_order_data)
            
            if gate_result and gate_result.get('id'):
                return {
                    'success': True,
                    'gate_order_id': gate_result['id'],
                    'gate_size': gate_size
                }
            else:
                return {
                    'success': False,
                    'error': f'Gate order creation failed: {gate_result}'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Gate order creation error: {str(e)}'
            }

    async def _record_successful_mirror(self, order_id: str, bitget_order: Dict, gate_order_id: str, order_info: Dict):
        """성공적인 미러링 기록"""
        try:
            # 미러링 기록 저장
            self.mirrored_plan_orders[order_id] = {
                'bitget_order': bitget_order,
                'gate_order_id': gate_order_id,
                'order_info': order_info,
                'mirrored_at': datetime.now(),
                'perfect_mirror': order_info.get('tp_price') is not None or order_info.get('sl_price') is not None
            }
            
            # 양방향 매핑 설정
            self.bitget_to_gate_order_mapping[order_id] = gate_order_id
            self.gate_to_bitget_order_mapping[gate_order_id] = order_id
            
            # 통계 업데이트
            self.daily_stats['total_mirrored'] += 1
            self.daily_stats['successful_mirrors'] += 1
            self.daily_stats['plan_order_mirrors'] += 1
            
            if order_info.get('tp_price') or order_info.get('sl_price'):
                self.daily_stats['perfect_mirrors'] += 1
                self.daily_stats['tp_sl_success'] += 1
            else:
                self.daily_stats['partial_mirrors'] += 1
            
            # 텔레그램 알림
            await self._send_mirror_success_notification(order_id, gate_order_id, order_info)
            
        except Exception as e:
            self.logger.error(f"미러링 기록 저장 실패: {order_id} - {e}")

    async def _send_mirror_success_notification(self, order_id: str, gate_order_id: str, order_info: Dict):
        """미러링 성공 알림"""
        try:
            side_emoji = "🟢" if order_info['side'] == 'buy' else "🔴"
            
            message = f"""🔄 예약 주문 미러링 성공

{side_emoji} 방향: {order_info['side'].upper()}
💰 크기: {order_info['size']:.6f} BTC
📍 트리거가: ${order_info['trigger_price']:,.2f}

🎯 비트겟 주문: {order_id}
🎯 게이트 주문: {gate_order_id}"""

            if order_info.get('tp_price'):
                message += f"\n🎯 TP: ${order_info['tp_price']:,.2f}"
            if order_info.get('sl_price'):
                message += f"\n🛡️ SL: ${order_info['sl_price']:,.2f}"
            
            await self.telegram.send_message(message)
            
        except Exception as e:
            self.logger.error(f"미러링 성공 알림 전송 실패: {e}")

    def _is_recently_processed(self, order_id: str) -> bool:
        """최근 처리된 주문인지 확인"""
        if order_id not in self.recently_processed_orders:
            return False
        
        time_diff = (datetime.now() - self.recently_processed_orders[order_id]).total_seconds()
        return time_diff < self.order_deduplication_window

    async def handle_order_fill(self, filled_order: Dict):
        """주문 체결 처리"""
        try:
            order_id = filled_order.get('orderId', filled_order.get('id'))
            if not order_id:
                return
            
            # 신규 진입 주문인지 확인
            reduce_only = filled_order.get('reduceOnly', 'false')
            if reduce_only != 'false' and reduce_only is not False:
                return  # 청산 주문은 처리하지 않음
            
            # 포지션 생성 후 미러링
            await self._mirror_position_from_fill(filled_order)
            
        except Exception as e:
            self.logger.error(f"주문 체결 처리 실패: {order_id} - {e}")

    async def _mirror_position_from_fill(self, filled_order: Dict):
        """체결된 주문으로부터 포지션 미러링"""
        try:
            # 구현 필요 시 추가
            pass
        except Exception as e:
            self.logger.error(f"포지션 미러링 실패: {e}")

    async def monitor_position_changes(self):
        """포지션 변화 모니터링"""
        try:
            # 구현 필요 시 추가
            pass
        except Exception as e:
            self.logger.error(f"포지션 변화 모니터링 실패: {e}")

    async def analyze_order_sync_status(self) -> Optional[Dict]:
        """🔥🔥🔥 주문 동기화 상태 분석 - 보호 강화"""
        try:
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
            
            # 🔥🔥🔥 고아 게이트 주문 찾기 - 매우 신중하게
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id')
                if not gate_order_id:
                    continue
                
                # 🔥🔥🔥 보호된 기존 주문인지 확인
                if gate_order_id in self.gate_existing_orders_detailed:
                    existing_info = self.gate_existing_orders_detailed[gate_order_id]
                    if existing_info.get('protected', False):
                        continue  # 보호된 주문은 고아로 간주하지 않음
                
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

    async def _check_similar_bitget_order_exists(self, gate_order: Dict, bitget_orders: List[Dict]) -> bool:
        """🔥🔥🔥 유사한 비트겟 주문 존재 여부 확인"""
        try:
            gate_side = gate_order.get('side', '')
            gate_price = float(gate_order.get('price', 0))
            gate_size = float(gate_order.get('size', 0))
            
            for bitget_order in bitget_orders:
                bitget_side = bitget_order.get('side', bitget_order.get('tradeSide', ''))
                bitget_price = float(bitget_order.get('triggerPrice', bitget_order.get('executePrice', 0)))
                bitget_size = float(bitget_order.get('size', bitget_order.get('sz', 0)))
                
                # 유사도 검사 (더 관대한 기준)
                if (bitget_side == gate_side and
                    bitget_price > 0 and gate_price > 0 and
                    abs(bitget_price - gate_price) / gate_price < 0.02 and  # 2% 이내
                    bitget_size > 0 and gate_size > 0 and
                    abs(bitget_size - gate_size) / gate_size < 0.2):  # 20% 이내
                    
                    self.logger.info(f"유사한 비트겟 주문 발견 - 게이트 주문 보호: {gate_order.get('id')}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"유사한 비트겟 주문 확인 실패: {e}")
            return True  # 오류 시 안전하게 존재한다고 가정

    async def cleanup_close_orders_without_position(self):
        """🔥🔥🔥 포지션 없는 클로즈 주문 정리 - 신중한 검증"""
        try:
            # 현재 포지션 상태 확인
            bitget_positions = await self.bitget_mirror.get_positions(self.config.symbol)
            gate_positions = await self.gate_mirror.get_positions('BTC_USDT')
            
            # 포지션 존재 여부 확인
            has_bitget_position = any(
                float(pos.get('total', pos.get('sizeQty', 0))) > 0 
                for pos in bitget_positions
            )
            
            has_gate_position = any(
                float(pos.get('size', 0)) != 0 
                for pos in gate_positions
            )
            
            # 포지션이 있으면 정리하지 않음
            if has_bitget_position or has_gate_position:
                return
            
            self.logger.info("🔍 포지션 없음 감지 - 클로즈 주문 정리 검토")
            
            # 게이트 클로즈 주문 찾기
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            close_orders_to_delete = []
            
            for gate_order in gate_orders:
                side = gate_order.get('side', '')
                
                # 클로즈 주문 여부 확인
                if side in ['close_long', 'close_short']:
                    # 🔥🔥🔥 추가 검증: 정말 포지션과 연관된 주문인지 확인
                    if await self._verify_close_order_validity(gate_order):
                        close_orders_to_delete.append(gate_order)
            
            if close_orders_to_delete:
                self.logger.info(f"🗑️ 포지션 없음 → {len(close_orders_to_delete)}개 클로즈 주문 자동 정리 시작")
                
                deleted_count = 0
                for close_order in close_orders_to_delete:
                    try:
                        gate_order_id = close_order.get('id')
                        if gate_order_id:
                            await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                            deleted_count += 1
                            
                            # 미러링 기록에서도 제거
                            bitget_order_id = self.gate_to_bitget_order_mapping.get(gate_order_id)
                            if bitget_order_id:
                                if bitget_order_id in self.mirrored_plan_orders:
                                    del self.mirrored_plan_orders[bitget_order_id]
                                del self.gate_to_bitget_order_mapping[gate_order_id]
                                if bitget_order_id in self.bitget_to_gate_order_mapping:
                                    del self.bitget_to_gate_order_mapping[bitget_order_id]
                            
                            self.logger.info(f"✅ 클로즈 주문 삭제 완료: {gate_order_id}")
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        if any(keyword in error_msg for keyword in [
                            "not found", "order not exist", "invalid order",
                            "order does not exist", "auto_order_not_found"
                        ]):
                            deleted_count += 1
                            self.logger.info(f"클로즈 주문이 이미 처리됨: {gate_order_id}")
                        else:
                            self.logger.error(f"클로즈 주문 삭제 실패: {gate_order_id} - {e}")
                
                if deleted_count > 0:
                    self.daily_stats['auto_close_order_cleanups'] += deleted_count
                    self.daily_stats['position_closed_cleanups'] += 1
                    
                    await self.telegram.send_message(
                        f"🗑️ 자동 클로즈 주문 정리 완료\n"
                        f"포지션 상태: 없음 (모두 익절/손절됨)\n"
                        f"정리된 클로즈 주문: {deleted_count}개\n"
                        f"게이트가 깔끔하게 정리되었습니다!"
                    )
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 정리 실패: {e}")

    async def _verify_close_order_validity(self, gate_order: Dict) -> bool:
        """🔥🔥🔥 클로즈 주문 유효성 검증"""
        try:
            # 기본적으로 클로즈 주문이면 정리 대상
            side = gate_order.get('side', '')
            
            if side not in ['close_long', 'close_short']:
                return False
            
            # 🔥🔥🔥 최근에 생성된 주문은 보호 (1분 이내)
            gate_order_id = gate_order.get('id')
            if gate_order_id in self.gate_existing_orders_detailed:
                recorded_at_str = self.gate_existing_orders_detailed[gate_order_id].get('recorded_at', '')
                if recorded_at_str:
                    try:
                        recorded_at = datetime.fromisoformat(recorded_at_str)
                        if (datetime.now() - recorded_at).total_seconds() < 60:
                            self.logger.info(f"최근 생성된 클로즈 주문 보호: {gate_order_id}")
                            return False
                    except:
                        pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 유효성 검증 실패: {e}")
            return False

    async def handle_bitget_plan_order_cancellation(self, bitget_order_id: str):
        """🔥🔥🔥 비트겟 예약 주문 취소 처리 - 새로운 안전한 방식"""
        try:
            self.logger.info(f"🔍 비트겟 예약 주문 취소 처리: {bitget_order_id}")
            
            # 🔥🔥🔥 연결된 게이트 주문 찾기
            gate_order_id = self.bitget_to_gate_order_mapping.get(bitget_order_id)
            
            if not gate_order_id:
                self.logger.info(f"연결된 게이트 주문 없음: {bitget_order_id}")
                return
            
            # 🔥🔥🔥 게이트 주문이 실제로 존재하는지 확인
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            gate_order_exists = any(
                order.get('id') == gate_order_id 
                for order in gate_orders
            )
            
            if not gate_order_exists:
                self.logger.info(f"게이트 주문이 이미 존재하지 않음: {gate_order_id}")
                # 매핑만 정리
                await self._cleanup_order_mappings(bitget_order_id, gate_order_id)
                return
            
            try:
                # 🔥🔥🔥 게이트 주문 취소 실행
                await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                
                self.logger.info(f"✅ 비트겟 주문 취소에 따른 게이트 주문 동기화 취소: {gate_order_id}")
                
                # 통계 및 기록 정리
                await self._cleanup_order_mappings(bitget_order_id, gate_order_id)
                
                self.daily_stats['plan_order_cancels'] += 1
                
                await self.telegram.send_message(
                    f"🔄 예약주문 취소 동기화\n"
                    f"비트겟 주문 취소: {bitget_order_id}\n"
                    f"게이트 주문 동기화 취소: {gate_order_id}\n"
                    f"정상적인 동기화 처리입니다."
                )
                
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order",
                    "order does not exist", "auto_order_not_found"
                ]):
                    self.logger.info(f"게이트 주문이 이미 처리됨: {gate_order_id}")
                    await self._cleanup_order_mappings(bitget_order_id, gate_order_id)
                else:
                    self.logger.error(f"게이트 주문 취소 실패: {gate_order_id} - {e}")
                    raise
            
        except Exception as e:
            self.logger.error(f"비트겟 예약 주문 취소 처리 중 예외 발생: {e}")
            
            # 🔥🔥🔥 오류 발생 시에도 미러링 기록에서 제거하여 일관성 유지
            await self._cleanup_order_mappings(bitget_order_id, gate_order_id)

    async def _cleanup_order_mappings(self, bitget_order_id: str, gate_order_id: str = None):
        """주문 매핑 정리"""
        try:
            # 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            # 주문 매핑에서 제거
            if bitget_order_id in self.bitget_to_gate_order_mapping:
                mapped_gate_id = self.bitget_to_gate_order_mapping[bitget_order_id]
                del self.bitget_to_gate_order_mapping[bitget_order_id]
                
                if mapped_gate_id in self.gate_to_bitget_order_mapping:
                    del self.gate_to_bitget_order_mapping[mapped_gate_id]
            
            if gate_order_id and gate_order_id in self.gate_to_bitget_order_mapping:
                del self.gate_to_bitget_order_mapping[gate_order_id]
                
        except Exception as e:
            self.logger.error(f"주문 매핑 정리 실패: {e}")

    async def _periodic_cleanup(self):
        """주기적 정리 작업"""
        while True:
            try:
                await asyncio.sleep(300)  # 5분마다 실행
                await self._cleanup_expired_timestamps()
            except Exception as e:
                self.logger.error(f"주기적 정리 작업 실패: {e}")
                await asyncio.sleep(600)  # 오류 시 10분 대기

    async def _cleanup_expired_timestamps(self):
        """만료된 타임스탬프 정리"""
        try:
            current_time = datetime.now()
            
            expired_orders = []
            for order_id, timestamp in self.recently_processed_orders.items():
                if (current_time - timestamp).total_seconds() > self.order_deduplication_window:
                    expired_orders.append(order_id)
            
            for order_id in expired_orders:
                del self.recently_processed_orders[order_id]
                if order_id in self.order_processing_locks:
                    del self.order_processing_locks[order_id]
            
            # 게이트 기존 주문 상세 정보도 정리
            expired_gate_orders = []
            for order_id, details in self.gate_existing_orders_detailed.items():
                recorded_at_str = details.get('recorded_at', '')
                if recorded_at_str:
                    try:
                        recorded_at = datetime.fromisoformat(recorded_at_str)
                        if (current_time - recorded_at).total_seconds() > 600:  # 10분 후 만료
                            expired_gate_orders.append(order_id)
                    except:
                        expired_gate_orders.append(order_id)
                else:
                    expired_gate_orders.append(order_id)
            
            for order_id in expired_gate_orders:
                del self.gate_existing_orders_detailed[order_id]
            
            if expired_orders or expired_gate_orders:
                self.logger.debug(f"만료된 기록 정리: 처리 기록 {len(expired_orders)}개, 게이트 기록 {len(expired_gate_orders)}개")
                
        except Exception as e:
            self.logger.error(f"만료된 타임스탬프 정리 실패: {e}")

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("미러 포지션 매니저 중지")
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 중 오류: {e}")
