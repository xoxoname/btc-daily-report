import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from mirror_position_manager import MirrorPositionManager

@dataclass
class MirrorStats:
    timestamp: datetime
    success: bool
    error: Optional[str] = None
    order_type: Optional[str] = None

class MirrorTradingSystem:
    def __init__(self, config, bitget_client, gate_client, bitget_mirror, gate_mirror, telegram_bot, utils):
        # 기본 클라이언트
        self.bitget = bitget_client
        self.gate = gate_client
        
        # 미러링 전용 클라이언트
        self.bitget_mirror = bitget_mirror
        self.gate_mirror = gate_mirror
        
        # 텔레그램 봇
        self.telegram = telegram_bot
        
        # 유틸리티
        self.utils = utils
        
        # 로깅
        self.logger = logging.getLogger('mirror_trading')
        
        # 🔥🔥🔥 포지션 매니저 먼저 초기화
        self.position_manager = MirrorPositionManager(
            config, self.bitget_mirror, gate_client, self.gate_mirror, telegram_bot, self.utils
        )
        
        # 미러링 상태 관리 (포지션 매니저에 위임)
        self.mirrored_positions = self.position_manager.mirrored_positions
        self.startup_positions = self.position_manager.startup_positions
        self.failed_mirrors = self.position_manager.failed_mirrors
        
        # 기본 설정
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 🔥🔥🔥 시세 차이 관리 - 처리 차단 없음으로 완전 변경
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        self.price_sync_threshold: float = 999999.0  # 🔥🔥🔥 사실상 무제한으로 설정
        self.position_wait_timeout: int = 0  # 🔥🔥🔥 대기 시간 완전 제거
        
        # 시세 조회 실패 관리 강화
        self.last_valid_bitget_price: float = 0.0
        self.last_valid_gate_price: float = 0.0
        self.bitget_price_failures: int = 0
        self.gate_price_failures: int = 0
        self.max_price_failures: int = 10
        
        # 🔥🔥🔥 예약 주문 동기화 강화 설정 - 더 빠르게
        self.order_sync_enabled: bool = True
        self.order_sync_interval: int = 10  # 🔥🔥🔥 15초 → 10초로 단축
        self.last_order_sync_time: datetime = datetime.min
        self.force_sync_enabled: bool = True  # 🔥🔥🔥 강제 동기화 활성화
        
        # 🔥🔥🔥 슬리피지 보호 설정 개선 - 0.05% (약 50달러)
        self.slippage_protection_enabled: bool = True
        self.max_slippage_percent: float = 0.05  # 🔥🔥🔥 0.05% (약 50달러)로 변경
        self.price_check_interval: float = 0.5  # 가격 체크 간격 0.5초
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        
        # 🔥🔥🔥 예약 주문 복제 강화를 위한 추가 설정
        self.PLAN_ORDER_CHECK_INTERVAL = 5  # 🔥🔥🔥 예약 주문 체크 간격을 5초로 단축
        self.MAX_RETRY_ATTEMPTS = 3  # 실패 시 재시도 횟수
        
        # 모니터링 상태
        self.monitoring = False
        
        # 통계
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'startup_plan_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'duplicate_orders_prevented': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0,
            'force_sync_count': 0  # 🔥🔥🔥 강제 동기화 횟수 추가
        }

    def _get_valid_price_difference(self) -> Optional[float]:
        """🔥🔥🔥 유효한 시세 차이 반환 - 차단 없이 정보용으로만"""
        if self.bitget_current_price > 0 and self.gate_current_price > 0:
            return abs(self.bitget_current_price - self.gate_current_price)
        
        # 최근 유효한 가격이 있으면 사용
        if self.last_valid_bitget_price > 0 and self.last_valid_gate_price > 0:
            return abs(self.last_valid_bitget_price - self.last_valid_gate_price)
        
        return None

    async def _update_current_prices(self):
        """현재 시세 업데이트 - 실패해도 처리는 계속"""
        try:
            # 비트겟 가격 조회
            try:
                bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
                if bitget_ticker and 'last' in bitget_ticker:
                    new_bitget_price = float(bitget_ticker['last'])
                    if new_bitget_price > 0:
                        self.bitget_current_price = new_bitget_price
                        self.last_valid_bitget_price = new_bitget_price
                        self.bitget_price_failures = 0
                    else:
                        raise ValueError("비트겟 가격이 0")
                else:
                    raise ValueError("비트겟 티커 데이터 없음")
            except Exception as e:
                self.bitget_price_failures += 1
                if self.bitget_price_failures <= 3:
                    self.logger.warning(f"비트겟 가격 조회 실패 ({self.bitget_price_failures}/10): {e}")

            # 게이트 가격 조회
            try:
                gate_ticker = await self.gate_mirror.get_ticker(self.GATE_CONTRACT)
                if gate_ticker and 'last' in gate_ticker:
                    new_gate_price = float(gate_ticker['last'])
                    if new_gate_price > 0:
                        self.gate_current_price = new_gate_price
                        self.last_valid_gate_price = new_gate_price
                        self.gate_price_failures = 0
                    else:
                        raise ValueError("게이트 가격이 0")
                else:
                    raise ValueError("게이트 티커 데이터 없음")
            except Exception as e:
                self.gate_price_failures += 1
                if self.gate_price_failures <= 3:
                    self.logger.warning(f"게이트 가격 조회 실패 ({self.gate_price_failures}/10): {e}")

            # 시세 차이 계산 (정보용)
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                self.price_diff_percent = abs(self.bitget_current_price - self.gate_current_price) / self.bitget_current_price * 100
                self.last_price_update = datetime.now()

        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.monitoring = True
            self.logger.info("🔥🔥🔥 미러 트레이딩 시스템 시작")
            
            # 포지션 매니저 시작
            await self.position_manager.start()
            
            # 🔥🔥🔥 통계 객체 동기화
            self.position_manager.daily_stats = self.daily_stats
            
            # 계정 상태 조회 및 알림
            await self._log_account_status()
            
            # 🔥🔥🔥 모든 모니터링 태스크 시작 - 예약 주문 모니터링 강화
            tasks = [
                self.monitor_order_fills(),
                self.monitor_plan_orders(),  # 🔥🔥🔥 예약 주문 모니터링 우선 순위 상승
                self.monitor_order_synchronization(),  # 🔥🔥🔥 동기화 모니터링 강화
                self.monitor_position_changes(),
                self._periodic_price_update(),
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n오류: {str(e)[:200]}"
            )
            raise

    async def monitor_order_synchronization(self):
        """🔥🔥🔥 예약 주문 동기화 모니터링 강화"""
        try:
            self.logger.info("🔄 예약 주문 동기화 모니터링 시작 (강화 버전)")
            
            while self.monitoring:
                try:
                    if not self.order_sync_enabled:
                        await asyncio.sleep(self.order_sync_interval)
                        continue
                    
                    current_time = datetime.now()
                    
                    # 🔥🔥🔥 더 빠른 정기 동기화 체크 (10초마다)
                    if (current_time - self.last_order_sync_time).total_seconds() >= self.order_sync_interval:
                        self.logger.info(f"🔄 정기 예약 주문 동기화 시작 (마지막: {self.last_order_sync_time})")
                        await self._perform_comprehensive_order_sync()
                        self.last_order_sync_time = current_time
                    
                    # 🔥🔥🔥 강제 동기화 (30초마다)
                    if self.force_sync_enabled and (current_time - self.last_order_sync_time).total_seconds() >= 30:
                        self.logger.info("🔥 강제 예약 주문 동기화 실행")
                        await self._perform_force_sync()
                        self.daily_stats['force_sync_count'] += 1
                    
                    await asyncio.sleep(2)  # 🔥🔥🔥 체크 간격을 2초로 단축
                    
                except Exception as e:
                    self.logger.error(f"예약 주문 동기화 모니터링 오류: {e}")
                    await asyncio.sleep(self.order_sync_interval)
                    
        except Exception as e:
            self.logger.error(f"예약 주문 동기화 모니터링 시스템 실패: {e}")

    async def _perform_comprehensive_order_sync(self):
        """🔥🔥🔥 종합적인 예약 주문 동기화 강화"""
        try:
            self.logger.info("🔄 종합 예약 주문 동기화 시작 (강화 버전)")
            
            # 1. 비트겟 예약 주문 조회 - 더 광범위하게
            plan_data = await self.bitget_mirror.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            self.logger.info(f"📊 비트겟 예약 주문 발견: 일반 {len(bitget_plan_orders)}개, TP/SL {len(bitget_tp_sl_orders)}개")
            
            # 모든 비트겟 예약 주문 (TP/SL 클로즈 주문 포함)
            all_bitget_orders = []
            all_bitget_orders.extend(bitget_plan_orders)
            
            # 🔥🔥🔥 TP/SL 주문 중 클로즈 주문과 일반 주문 모두 포함
            for tp_sl_order in bitget_tp_sl_orders:
                side = tp_sl_order.get('side', tp_sl_order.get('tradeSide', '')).lower()
                reduce_only = tp_sl_order.get('reduceOnly', False)
                order_type = tp_sl_order.get('orderType', tp_sl_order.get('planType', ''))
                
                # 🔥🔥🔥 모든 TP/SL 주문을 포함 (클로즈 여부와 관계없이)
                all_bitget_orders.append(tp_sl_order)
                self.logger.debug(f"TP/SL 주문 추가: {tp_sl_order.get('orderId', '')} - {side} - {order_type}")
            
            # 2. 게이트 예약 주문 조회
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            self.logger.info(f"📊 게이트 예약 주문 발견: {len(gate_orders)}개")
            
            # 3. 동기화 분석
            sync_analysis = await self._analyze_comprehensive_sync(all_bitget_orders, gate_orders)
            
            # 4. 문제가 있으면 수정
            if sync_analysis['requires_action']:
                self.logger.warning(f"🔍 동기화 문제 발견: {sync_analysis['total_issues']}건")
                await self._fix_sync_issues(sync_analysis)
            else:
                self.logger.debug(f"✅ 예약 주문 동기화 상태 양호: 비트겟 {len(all_bitget_orders)}개, 게이트 {len(gate_orders)}개")
            
        except Exception as e:
            self.logger.error(f"종합 예약 주문 동기화 실패: {e}")
            self.logger.error(traceback.format_exc())

    async def _perform_force_sync(self):
        """🔥🔥🔥 강제 동기화 - 누락된 주문 강제 복제"""
        try:
            self.logger.info("🔥 강제 예약 주문 동기화 시작")
            
            # 비트겟 모든 예약 주문 조회
            plan_data = await self.bitget_mirror.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_bitget_orders = bitget_plan_orders + bitget_tp_sl_orders
            
            # 게이트 예약 주문 조회
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 🔥🔥🔥 미러링되지 않은 주문 찾기
            missing_count = 0
            for bitget_order in all_bitget_orders:
                order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 스타트업 주문은 제외하되, 오래된 주문은 강제 포함
                order_time = bitget_order.get('cTime', 0)
                current_time = datetime.now().timestamp() * 1000
                
                # 1시간 이상 된 주문이고 미러링 기록이 없으면 강제 복제
                if order_id not in self.position_manager.mirrored_plan_orders:
                    if (current_time - order_time) > 3600000:  # 1시간
                        self.logger.info(f"🔥 강제 복제 대상: {order_id} (1시간 이상 된 미복제 주문)")
                        
                        # 강화된 클로즈 주문 감지
                        close_details = await self.position_manager._enhanced_close_order_detection(bitget_order)
                        
                        if close_details['is_close_order']:
                            result = await self.position_manager._process_enhanced_close_order(bitget_order, close_details)
                        else:
                            result = await self.position_manager._process_perfect_mirror_order(bitget_order)
                        
                        if result in ["perfect_success", "partial_success"]:
                            missing_count += 1
                            self.logger.info(f"🔥 강제 복제 성공: {order_id}")
            
            if missing_count > 0:
                await self.telegram.send_message(
                    f"🔥 강제 동기화 완료\n"
                    f"복제된 주문: {missing_count}개\n"
                    f"기존 미복제 주문들을 강제로 복제했습니다."
                )
                
        except Exception as e:
            self.logger.error(f"강제 동기화 실패: {e}")

    async def _analyze_comprehensive_sync(self, bitget_orders: List[Dict], gate_orders: List[Dict]) -> Dict:
        """🔥🔥🔥 종합적인 동기화 분석 강화"""
        try:
            analysis = {
                'requires_action': False,
                'missing_mirrors': [],
                'orphaned_orders': [],
                'price_mismatches': [],
                'size_mismatches': [],
                'total_issues': 0
            }
            
            self.logger.info(f"🔍 동기화 분석 시작: 비트겟 {len(bitget_orders)}개, 게이트 {len(gate_orders)}개")
            
            # 🔥🔥🔥 비트겟 주문 분석 강화
            for bitget_order in bitget_orders:
                bitget_order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
                if not bitget_order_id:
                    continue
                
                order_type = bitget_order.get('orderType', bitget_order.get('planType', 'unknown'))
                side = bitget_order.get('side', bitget_order.get('tradeSide', 'unknown'))
                trigger_price = bitget_order.get('triggerPrice', bitget_order.get('executePrice', 0))
                
                self.logger.debug(f"📝 분석 중인 비트겟 주문: {bitget_order_id} - {order_type} - {side} - ${trigger_price}")
                
                # 🔥🔥🔥 스타트업 주문 제외하되, 1시간 이상 된 주문은 포함
                if bitget_order_id in self.position_manager.startup_plan_orders:
                    order_time = bitget_order.get('cTime', 0)
                    current_time = datetime.now().timestamp() * 1000
                    
                    # 1시간 이상 된 주문은 스타트업 제외에서 해제
                    if (current_time - order_time) <= 3600000:  # 1시간 이내만 제외
                        continue
                    else:
                        self.logger.info(f"🕐 1시간 이상 된 스타트업 주문 포함: {bitget_order_id}")
                
                # 미러링 기록 확인
                if bitget_order_id in self.position_manager.mirrored_plan_orders:
                    mirror_info = self.position_manager.mirrored_plan_orders[bitget_order_id]
                    expected_gate_id = mirror_info.get('gate_order_id')
                    
                    # 게이트에서 해당 주문 찾기
                    gate_order_found = None
                    for gate_order in gate_orders:
                        if gate_order.get('id') == expected_gate_id:
                            gate_order_found = gate_order
                            break
                    
                    if not gate_order_found:
                        # 🔥🔥🔥 미러링 기록은 있지만 게이트에 주문이 없음
                        analysis['missing_mirrors'].append({
                            'bitget_order_id': bitget_order_id,
                            'bitget_order': bitget_order,
                            'expected_gate_id': expected_gate_id,
                            'type': 'missing_gate_order'
                        })
                        self.logger.warning(f"❌ 미러링 기록 있으나 게이트 주문 없음: {bitget_order_id} -> {expected_gate_id}")
                else:
                    # 🔥🔥🔥 미러링 기록 자체가 없음
                    analysis['missing_mirrors'].append({
                        'bitget_order_id': bitget_order_id,
                        'bitget_order': bitget_order,
                        'type': 'no_mirror_record'
                    })
                    self.logger.warning(f"❌ 미러링 기록 없음: {bitget_order_id} - {order_type} - {side}")
            
            # 🔥🔥🔥 게이트 고아 주문 찾기
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id')
                if not gate_order_id:
                    continue
                
                # 이 게이트 주문과 연결된 비트겟 주문 찾기
                bitget_order_id = None
                for bid, mirror_info in self.position_manager.mirrored_plan_orders.items():
                    if mirror_info.get('gate_order_id') == gate_order_id:
                        bitget_order_id = bid
                        break
                
                if bitget_order_id:
                    # 비트겟에 해당 주문이 실제로 존재하는지 확인
                    bitget_exists = any(
                        order.get('orderId', order.get('planOrderId', '')) == bitget_order_id 
                        for order in bitget_orders
                    )
                    
                    if not bitget_exists:
                        analysis['orphaned_orders'].append({
                            'gate_order_id': gate_order_id,
                            'gate_order': gate_order,
                            'mapped_bitget_id': bitget_order_id,
                            'type': 'orphaned_mapped'
                        })
                        self.logger.warning(f"🗑️ 고아 주문 발견: 게이트 {gate_order_id} -> 비트겟 {bitget_order_id} (비트겟에 없음)")
            
            # 총 문제 개수 계산
            analysis['total_issues'] = (
                len(analysis['missing_mirrors']) + 
                len(analysis['orphaned_orders']) + 
                len(analysis['price_mismatches']) + 
                len(analysis['size_mismatches'])
            )
            
            analysis['requires_action'] = analysis['total_issues'] > 0
            
            if analysis['requires_action']:
                self.logger.warning(f"🔍 동기화 문제 발견: {analysis['total_issues']}건")
                self.logger.warning(f"   - 누락 미러링: {len(analysis['missing_mirrors'])}건")
                self.logger.warning(f"   - 고아 주문: {len(analysis['orphaned_orders'])}건")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"종합 동기화 분석 실패: {e}")
            return {'requires_action': False, 'total_issues': 0, 'missing_mirrors': [], 'orphaned_orders': [], 'price_mismatches': [], 'size_mismatches': []}

    async def _fix_sync_issues(self, sync_analysis: Dict):
        """🔥🔥🔥 동기화 문제 해결 강화"""
        try:
            fixed_count = 0
            
            # 1. 누락된 미러링 복제
            for missing_item in sync_analysis['missing_mirrors']:
                try:
                    bitget_order = missing_item['bitget_order']
                    bitget_order_id = missing_item['bitget_order_id']
                    
                    self.logger.info(f"🔄 누락 미러링 복제 시도: {bitget_order_id}")
                    
                    # 🔥🔥🔥 강화된 클로즈 주문 감지 및 처리
                    close_details = await self.position_manager._enhanced_close_order_detection(bitget_order)
                    
                    # 재시도 로직 추가
                    for attempt in range(self.MAX_RETRY_ATTEMPTS):
                        try:
                            if close_details['is_close_order']:
                                result = await self.position_manager._process_enhanced_close_order(bitget_order, close_details)
                            else:
                                result = await self.position_manager._process_perfect_mirror_order(bitget_order)
                            
                            if result in ["perfect_success", "partial_success"]:
                                fixed_count += 1
                                self.daily_stats['sync_corrections'] += 1
                                self.logger.info(f"✅ 누락 미러링 복제 성공: {bitget_order_id} (시도 {attempt + 1})")
                                break
                            else:
                                self.logger.warning(f"⚠️ 누락 미러링 복제 실패: {bitget_order_id} - {result} (시도 {attempt + 1})")
                                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                                    await asyncio.sleep(2)  # 재시도 전 대기
                        except Exception as retry_e:
                            self.logger.error(f"누락 미러링 복제 재시도 오류 (시도 {attempt + 1}): {retry_e}")
                            if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                                await asyncio.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"누락 미러링 복제 실패: {bitget_order_id} - {e}")
            
            # 2. 고아 주문 삭제
            for orphaned_item in sync_analysis['orphaned_orders']:
                try:
                    gate_order_id = orphaned_item['gate_order_id']
                    
                    self.logger.info(f"🗑️ 고아 주문 삭제 시도: {gate_order_id}")
                    
                    # 고아 주문 삭제
                    try:
                        await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                        fixed_count += 1
                        self.daily_stats['sync_deletions'] += 1
                        self.logger.info(f"✅ 고아 주문 삭제 성공: {gate_order_id}")
                        
                        # 미러링 기록에서도 제거
                        bitget_order_id = orphaned_item.get('mapped_bitget_id')
                        if bitget_order_id and bitget_order_id in self.position_manager.mirrored_plan_orders:
                            del self.position_manager.mirrored_plan_orders[bitget_order_id]
                            self.logger.info(f"🗑️ 미러링 기록에서 제거: {bitget_order_id}")
                            
                    except Exception as cancel_e:
                        self.logger.error(f"고아 주문 삭제 실패: {gate_order_id} - {cancel_e}")
                        
                except Exception as e:
                    self.logger.error(f"고아 주문 처리 실패: {e}")
            
            # 동기화 결과 알림 (3개 이상 문제가 해결되었을 때만)
            if fixed_count >= 3:
                price_diff = abs(self.bitget_current_price - self.gate_current_price) if (self.bitget_current_price > 0 and self.gate_current_price > 0) else 0
                await self.telegram.send_message(
                    f"🔄 예약 주문 대규모 동기화 완료\n"
                    f"해결된 문제: {fixed_count}건\n"
                    f"- 누락 미러링 복제: {len(sync_analysis['missing_mirrors'])}건\n"
                    f"- 고아 주문 삭제: {len(sync_analysis['orphaned_orders'])}건\n\n"
                    f"📊 현재 시세 차이: ${price_diff:.2f}\n"
                    f"🔥 시세 차이와 무관하게 모든 주문 즉시 처리\n"
                    f"🛡️ 슬리피지 보호 0.05% (약 $50) 적용"
                )
            elif fixed_count > 0:
                self.logger.info(f"🔄 예약 주문 동기화 완료: {fixed_count}건 해결")
            
        except Exception as e:
            self.logger.error(f"동기화 문제 해결 실패: {e}")

    async def monitor_plan_orders(self):
        """🔥🔥🔥 예약 주문 모니터링 강화 - 포지션 매니저로 위임"""
        self.logger.info("🎯 예약 주문 모니터링 시작 (강화 버전)")
        
        while self.monitoring:
            try:
                await self.position_manager.monitor_plan_orders_cycle()
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)  # 🔥🔥🔥 5초로 단축
                
            except Exception as e:
                self.logger.error(f"예약 주문 모니터링 중 오류: {e}")
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 2)

    async def monitor_order_fills(self):
        """🔥🔥🔥 실시간 주문 체결 감지 - 슬리피지 보호 0.05% 적용"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 현재 시세 업데이트 (정보용)
                await self._update_current_prices()
                
                # 🔥🔥🔥 시세 차이 확인만 하고 처리는 항상 즉시 진행
                valid_price_diff = self._get_valid_price_difference()
                if valid_price_diff is not None:
                    self.logger.debug(f"시세 차이 ${valid_price_diff:.2f} 확인됨, 슬리피지 보호 0.05% 적용하여 즉시 처리")
                
                # 미러링 클라이언트로 체결 주문 조회
                filled_orders = await self.bitget_mirror.get_recent_filled_orders(
                    symbol=self.SYMBOL, 
                    minutes=1
                )
                
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id or order_id in self.position_manager.processed_orders:
                        continue
                    
                    try:
                        result = await self.position_manager.process_filled_order(order)
                        if result in ["perfect_success", "partial_success"]:
                            self.daily_stats['order_mirrors'] += 1
                            self.daily_stats['total_mirrored'] += 1
                            self.daily_stats['successful_mirrors'] += 1
                            if result == "perfect_success":
                                self.daily_stats['perfect_mirrors'] += 1
                            else:
                                self.daily_stats['partial_mirrors'] += 1
                        elif result == "failed":
                            self.daily_stats['failed_mirrors'] += 1
                        
                        self.position_manager.processed_orders.add(order_id)
                        
                    except Exception as e:
                        self.logger.error(f"체결 주문 처리 실패: {order_id} - {e}")
                        self.daily_stats['failed_mirrors'] += 1
                
                # 포지션 변경 감지 (보조)
                await self.position_manager.check_position_changes()
                
                consecutive_errors = 0
                await asyncio.sleep(2)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"주문 체결 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 주문 체결 모니터링 연속 오류\n"
                        f"연속 오류: {consecutive_errors}회\n"
                        f"오류: {str(e)[:100]}"
                    )
                    consecutive_errors = 0
                
                await asyncio.sleep(5)

    async def monitor_position_changes(self):
        """포지션 변경 모니터링"""
        while self.monitoring:
            try:
                await self.position_manager.check_position_changes()
                await asyncio.sleep(3)
                
            except Exception as e:
                self.logger.error(f"포지션 모니터링 오류: {e}")
                await asyncio.sleep(10)

    async def _periodic_price_update(self):
        """주기적 시세 업데이트"""
        while self.monitoring:
            try:
                await self._update_current_prices()
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"주기적 시세 업데이트 오류: {e}")
                await asyncio.sleep(10)

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
                price_info = f"""📈 시세 상태:
• 비트겟: ${self.bitget_current_price:,.2f}
• 게이트: ${self.gate_current_price:,.2f}
• 차이: ${valid_price_diff:.2f}
• 🔥 처리: 시세 차이와 무관하게 즉시 처리
• 🛡️ 슬리피지 보호: 0.05% (약 $50) 제한
• ⏰ 지정가 대기: 5초 후 시장가 전환"""
            else:
                price_info = f"""📈 시세 상태:
• 시세 조회 중 문제 발생
• 시스템이 자동으로 복구 중
• 🔥 처리: 시세 조회 실패와 무관하게 정상 처리
• 🛡️ 슬리피지 보호: 0.05% 활성화됨"""
            
            await self.telegram.send_message(
                f"🔄 미러 트레이딩 시스템 시작\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f}\n"
                f"• 게이트: ${gate_equity:,.2f}\n\n"
                f"{price_info}\n\n"
                f"📊 현재 상태:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.position_manager.startup_plan_orders)}개\n"
                f"• 현재 복제된 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개\n\n"
                f"⚡ 핵심 기능:\n"
                f"• 🎯 완벽한 TP/SL 미러링\n"
                f"• 🔄 10초마다 자동 동기화 (강화)\n"
                f"• 🔥 30초마다 강제 동기화\n"
                f"• 🛡️ 중복 복제 방지\n"
                f"• 🗑️ 고아 주문 자동 정리\n"
                f"• 📊 클로즈 주문 포지션 체크\n"
                f"• 🔥 시세 차이와 무관하게 즉시 처리\n"
                f"• 🛡️ 슬리피지 보호 0.05% (약 $50)\n"
                f"• ⏰ 지정가 주문 5초 대기 후 시장가 전환\n"
                f"• 📱 시장가 체결 시 즉시 텔레그램 알림\n\n"
                f"🚀 시스템이 정상적으로 시작되었습니다."
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                # 오전 9시 리포트
                if now.hour == 9 and now.minute == 0 and (now - self.last_report_time).seconds > 3600:
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    self.last_report_time = now
                
                # 6시간마다 시세 차이 리포트
                if now.hour in [3, 9, 15, 21] and now.minute == 0:
                    await self._send_price_status_report()
                
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(300)

    async def _create_daily_report(self) -> str:
        """일일 리포트 생성"""
        try:
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            gate_account = await self.gate_mirror.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            success_rate = (self.daily_stats['successful_mirrors'] / max(self.daily_stats['total_mirrored'], 1)) * 100
            
            # 시세 차이 현황
            valid_price_diff = self._get_valid_price_difference()
            
            if valid_price_diff is not None:
                price_status_info = f"""📈 시세 차이 현황:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: ${valid_price_diff:.2f} ({self.price_diff_percent:.3f}%)
- 🔥 처리 상태: 시세 차이와 무관하게 모든 주문 즉시 처리
- 🛡️ 슬리피지 보호: 0.05% (약 $50) 제한
- ⏰ 지정가 대기: 5초 후 시장가 전환"""
            else:
                price_status_info = f"""📈 시세 차이 현황:
- 시세 조회에 문제가 있었습니다
- 비트겟 조회 실패: {self.bitget_price_failures}회
- 게이트 조회 실패: {self.gate_price_failures}회
- 🔥 처리 상태: 시세 조회 실패와 무관하게 모든 주문 정상 처리
- 🛡️ 슬리피지 보호: 0.05% 활성화됨"""
            
            # TP/SL 미러링 성과 통계
            perfect_mirrors = self.daily_stats.get('perfect_mirrors', 0)
            partial_mirrors = self.daily_stats.get('partial_mirrors', 0)
            tp_sl_success = self.daily_stats.get('tp_sl_success', 0)
            tp_sl_failed = self.daily_stats.get('tp_sl_failed', 0)
            
            report = f"""📊 미러 트레이딩 일일 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

💰 계정 잔고:
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}

{price_status_info}

⚡ 실시간 포지션 미러링:
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

🎯 완벽한 TP/SL 미러링 성과:
- 완벽한 미러링: {perfect_mirrors}회 ✨
- 부분 미러링: {partial_mirrors}회
- TP/SL 성공: {tp_sl_success}회 🎯
- TP/SL 실패: {tp_sl_failed}회 ❌
- 완벽 성공률: {(perfect_mirrors / max(perfect_mirrors + partial_mirrors, 1) * 100):.1f}%

🔄 예약 주문 미러링 (강화):
- 시작 시 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 미러링: {self.daily_stats['plan_order_mirrors']}회
- 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 클로즈 주문: {self.daily_stats['close_order_mirrors']}회
- 중복 방지: {self.daily_stats['duplicate_orders_prevented']}회

📈 동기화 성과 (강화):
- 자동 동기화 수정: {self.daily_stats.get('sync_corrections', 0)}회
- 고아 주문 삭제: {self.daily_stats.get('sync_deletions', 0)}회
- 강제 동기화: {self.daily_stats.get('force_sync_count', 0)}회
- 자동 클로즈 주문 정리: {self.daily_stats.get('auto_close_order_cleanups', 0)}회
- 포지션 종료 정리: {self.daily_stats.get('position_closed_cleanups', 0)}회

📉 포지션 관리:
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

🔧 시스템 최적화:
- 예약 주문 체크: 5초마다
- 동기화 체크: 10초마다
- 강제 동기화: 30초마다
- 슬리피지 보호: 0.05% 제한

🔥 시세 차이와 무관하게 모든 주문을 즉시 처리하여
완벽한 미러링을 보장합니다. 📊"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"일일 리포트 생성 실패: {e}")
            return f"❌ 일일 리포트 생성 중 오류 발생: {str(e)[:100]}"

    async def _send_price_status_report(self):
        """시세 차이 현황 리포트"""
        try:
            valid_price_diff = self._get_valid_price_difference()
            
            if valid_price_diff is not None:
                status = f"""📊 시세 차이 현황 리포트
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 현재 시세:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: ${valid_price_diff:.2f} ({self.price_diff_percent:.3f}%)

🔥 처리 정책:
- 시세 차이와 무관하게 모든 주문 즉시 처리
- 슬리피지 보호: 0.05% (약 $50) 제한
- 지정가 주문 5초 대기 후 시장가 전환

📈 복제된 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개
🔄 오늘 동기화 수정: {self.daily_stats.get('sync_corrections', 0)}건"""
            else:
                status = f"""📊 시세 차이 현황 리포트
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ 시세 조회 문제:
- 비트겟 조회 실패: {self.bitget_price_failures}회
- 게이트 조회 실패: {self.gate_price_failures}회

🔥 처리 정책:
- 시세 조회 실패와 무관하게 모든 주문 정상 처리
- 슬리피지 보호: 0.05% 활성화됨

📈 복제된 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개
🔄 오늘 동기화 수정: {self.daily_stats.get('sync_corrections', 0)}건"""
            
            await self.telegram.send_message(status)
            
        except Exception as e:
            self.logger.error(f"시세 현황 리포트 전송 실패: {e}")

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
