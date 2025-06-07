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
        self.price_failure_count: int = 0
        
        # 🔥🔥🔥 강화된 예약 주문 동기화
        self.last_order_sync_check = datetime.min
        self.order_sync_interval = 5  # 5초마다 체크
        self.force_sync_interval = 15  # 🔥🔥🔥 15초마다 강제 동기화 (30초에서 단축)
        self.last_force_sync = datetime.min
        
        # 상수 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        
        # 일일 통계
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'position_mirrors': 0,
            'order_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'startup_plan_mirrors': 0,
            'close_order_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'force_sync_count': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0
        }
        
        # 작업 지연 관리
        self.current_tasks = set()
        self.max_concurrent_tasks = 10
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 시스템 초기화 완료 - 강화된 예약 주문 동기화")
    
    async def start(self):
        """미러 트레이딩 시스템 시작"""
        try:
            self.logger.info("🚀 미러 트레이딩 시스템 시작")
            
            # 클라이언트 초기화
            await self.position_manager.initialize_clients()
            
            # 시작 시 기존 상태 확인 및 복제
            await self.position_manager.record_startup_state()
            
            # 백그라운드 모니터링 시작
            asyncio.create_task(self._background_monitoring())
            
            # 🔥🔥🔥 강화된 주기적 동기화 시작
            asyncio.create_task(self._enhanced_periodic_sync())
            
            # 시세 업데이트 시작
            asyncio.create_task(self._periodic_price_update())
            
            # 계정 상태 로깅
            await self._log_account_status()
            
            self.logger.info("✅ 미러 트레이딩 시스템 시작 완료")
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시스템 시작 실패: {e}")
            self.logger.error(traceback.format_exc())
            raise
    
    async def _background_monitoring(self):
        """백그라운드 모니터링 루프"""
        self.logger.info("🔍 백그라운드 모니터링 시작")
        
        while True:
            try:
                # 새로운 포지션 감지 및 미러링
                await self.position_manager.check_and_mirror_positions()
                
                # 새로운 예약 주문 감지 및 미러링 
                await self.position_manager.check_and_mirror_plan_orders()
                
                await asyncio.sleep(5)  # 5초마다 체크
                
            except Exception as e:
                self.logger.error(f"백그라운드 모니터링 오류: {e}")
                await asyncio.sleep(10)
    
    async def _enhanced_periodic_sync(self):
        """🔥🔥🔥 강화된 주기적 동기화 - 더 적극적인 복제"""
        self.logger.info("🔄 강화된 주기적 동기화 시작")
        
        while True:
            try:
                current_time = datetime.now()
                
                # 🔥🔥🔥 5초마다 예약 주문 동기화 체크
                if (current_time - self.last_order_sync_check).total_seconds() >= self.order_sync_interval:
                    await self._perform_comprehensive_order_sync()
                    self.last_order_sync_check = current_time
                
                # 🔥🔥🔥 15초마다 강제 동기화 (기존 30초에서 단축)
                if (current_time - self.last_force_sync).total_seconds() >= self.force_sync_interval:
                    await self._perform_aggressive_force_sync()
                    self.last_force_sync = current_time
                    self.daily_stats['force_sync_count'] += 1
                
                await asyncio.sleep(3)  # 3초마다 체크
                
            except Exception as e:
                self.logger.error(f"주기적 동기화 오류: {e}")
                await asyncio.sleep(10)
    
    async def _perform_comprehensive_order_sync(self):
        """🔥🔥🔥 종합적인 예약 주문 동기화 - 모든 유형 포함"""
        try:
            self.logger.info("📊 종합적인 예약 주문 동기화 시작")
            
            # 1. 비트겟 모든 예약 주문 조회 - 더 광범위하게
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

    async def _perform_aggressive_force_sync(self):
        """🔥🔥🔥 적극적인 강제 동기화 - 누락된 주문 강제 복제"""
        try:
            self.logger.info("🔥 적극적인 강제 동기화 시작")
            
            # 비트겟 모든 예약 주문 조회
            plan_data = await self.bitget_mirror.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_bitget_orders = bitget_plan_orders + bitget_tp_sl_orders
            
            # 게이트 예약 주문 조회
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 🔥🔥🔥 미러링되지 않은 주문 찾기 - 조건 완화
            missing_count = 0
            for bitget_order in all_bitget_orders:
                order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 🔥🔥🔥 스타트업 주문 제외 조건 완화 (30분으로 단축)
                order_time = bitget_order.get('cTime', 0)
                current_time = datetime.now().timestamp() * 1000
                
                # 30분 이상 된 주문이고 미러링 기록이 없으면 강제 복제
                if order_id not in self.position_manager.mirrored_plan_orders:
                    if (current_time - order_time) > 1800000:  # 30분 (기존 1시간에서 단축)
                        self.logger.info(f"🔥 강제 복제 대상: {order_id} (30분 이상 된 미복제 주문)")
                        
                        # 강화된 클로즈 주문 감지
                        close_details = await self.position_manager._enhanced_close_order_detection(bitget_order)
                        
                        if close_details['is_close_order']:
                            result = await self.position_manager._process_enhanced_close_order(bitget_order, close_details)
                        else:
                            result = await self.position_manager._process_perfect_mirror_order(bitget_order)
                        
                        if result in ["perfect_success", "partial_success"]:
                            missing_count += 1
                            self.logger.info(f"🔥 강제 복제 성공: {order_id}")
                    elif (current_time - order_time) > 300000:  # 5분 이상 된 주문도 적극 검토
                        self.logger.debug(f"🔍 5분 이상 된 주문 검토: {order_id}")
                        
                        # 클로즈 주문인지 확인
                        close_details = await self.position_manager._enhanced_close_order_detection(bitget_order)
                        if close_details['is_close_order']:
                            self.logger.info(f"🔥 클로즈 주문 즉시 복제: {order_id}")
                            result = await self.position_manager._process_enhanced_close_order(bitget_order, close_details)
                            if result in ["perfect_success", "partial_success"]:
                                missing_count += 1
            
            if missing_count > 0:
                await self.telegram.send_message(
                    f"🔥 적극적인 강제 동기화 완료\n"
                    f"복제된 주문: {missing_count}개\n"
                    f"기존 미복제 주문들을 강제로 복제했습니다."
                )
                self.logger.info(f"🔥 적극적인 강제 동기화 완료: {missing_count}개 복제")
            
        except Exception as e:
            self.logger.error(f"적극적인 강제 동기화 실패: {e}")

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
                
                # 🔥🔥🔥 스타트업 주문 제외하되, 15분 이상 된 주문은 포함 (기존 1시간에서 대폭 단축)
                if bitget_order_id in self.position_manager.startup_plan_orders:
                    order_time = bitget_order.get('cTime', 0)
                    current_time = datetime.now().timestamp() * 1000
                    
                    # 15분 이상 된 주문은 스타트업 제외에서 해제
                    if (current_time - order_time) <= 900000:  # 15분 이내만 제외 (기존 1시간에서 단축)
                        continue
                    else:
                        self.logger.info(f"🕐 15분 이상 된 스타트업 주문 포함: {bitget_order_id}")
                
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
                
                if not bitget_order_id:
                    # 연결된 비트겟 주문이 없는 고아 주문
                    analysis['orphaned_orders'].append({
                        'gate_order_id': gate_order_id,
                        'gate_order': gate_order
                    })
                    self.logger.warning(f"👻 고아 게이트 주문: {gate_order_id}")
            
            # 문제 집계
            analysis['total_issues'] = (len(analysis['missing_mirrors']) + 
                                      len(analysis['orphaned_orders']) + 
                                      len(analysis['price_mismatches']) + 
                                      len(analysis['size_mismatches']))
            
            analysis['requires_action'] = analysis['total_issues'] > 0
            
            if analysis['requires_action']:
                self.logger.warning(f"🚨 동기화 문제 요약: 누락 {len(analysis['missing_mirrors'])}개, 고아 {len(analysis['orphaned_orders'])}개")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"동기화 분석 실패: {e}")
            return {'requires_action': False, 'total_issues': 0}

    async def _fix_sync_issues(self, sync_analysis: Dict):
        """🔥🔥🔥 동기화 문제 수정 - 적극적인 복제"""
        try:
            fixed_count = 0
            
            # 1. 누락된 미러링 수정
            for missing in sync_analysis['missing_mirrors']:
                bitget_order = missing['bitget_order']
                bitget_order_id = missing['bitget_order_id']
                missing_type = missing['type']
                
                self.logger.info(f"🔧 누락된 미러링 수정 시도: {bitget_order_id} ({missing_type})")
                
                try:
                    # 🔥🔥🔥 클로즈 주문 감지 강화
                    close_details = await self.position_manager._enhanced_close_order_detection(bitget_order)
                    
                    if close_details['is_close_order']:
                        self.logger.info(f"🎯 클로즈 주문으로 감지: {bitget_order_id}")
                        result = await self.position_manager._process_enhanced_close_order(bitget_order, close_details)
                    else:
                        self.logger.info(f"📊 일반 주문으로 처리: {bitget_order_id}")
                        result = await self.position_manager._process_perfect_mirror_order(bitget_order)
                    
                    if result in ["perfect_success", "partial_success"]:
                        fixed_count += 1
                        self.logger.info(f"✅ 누락 미러링 복제 성공: {bitget_order_id}")
                    else:
                        self.logger.warning(f"❌ 누락 미러링 복제 실패: {bitget_order_id} - {result}")
                
                except Exception as e:
                    self.logger.error(f"누락 미러링 수정 실패 {bitget_order_id}: {e}")
            
            # 2. 고아 주문 정리
            deleted_count = 0
            for orphan in sync_analysis['orphaned_orders']:
                gate_order_id = orphan['gate_order_id']
                
                try:
                    # 🔥🔥🔥 고아 주문 삭제
                    delete_result = await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                    if delete_result.get('success', False):
                        deleted_count += 1
                        self.logger.info(f"🗑️ 고아 주문 삭제 성공: {gate_order_id}")
                    
                except Exception as e:
                    self.logger.error(f"고아 주문 삭제 실패 {gate_order_id}: {e}")
            
            # 통계 업데이트
            self.daily_stats['sync_corrections'] += fixed_count
            self.daily_stats['sync_deletions'] += deleted_count
            
            if fixed_count > 0 or deleted_count > 0:
                await self.telegram.send_message(
                    f"🔧 동기화 문제 수정 완료\n"
                    f"• 복제된 주문: {fixed_count}개\n"
                    f"• 삭제된 고아 주문: {deleted_count}개"
                )
                
                self.logger.info(f"🔧 동기화 문제 수정 완료: 복제 {fixed_count}개, 삭제 {deleted_count}개")
            
        except Exception as e:
            self.logger.error(f"동기화 문제 수정 실패: {e}")

    async def _periodic_price_update(self):
        """주기적 시세 업데이트"""
        while True:
            try:
                await asyncio.sleep(30)  # 30초마다 시세 업데이트
                
                # 비트겟 시세 조회
                try:
                    bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
                    self.bitget_current_price = float(bitget_ticker.get('last', 0))
                    if self.bitget_current_price > 0:
                        self.last_valid_bitget_price = self.bitget_current_price
                except:
                    pass
                
                # 게이트 시세 조회
                try:
                    gate_ticker = await self.gate.get_ticker(self.GATE_CONTRACT)
                    self.gate_current_price = float(gate_ticker.get('last', 0))
                    if self.gate_current_price > 0:
                        self.last_valid_gate_price = self.gate_current_price
                except:
                    pass
                
                # 시세 차이 계산
                if self.bitget_current_price > 0 and self.gate_current_price > 0:
                    self.price_diff_percent = abs(self.bitget_current_price - self.gate_current_price) / self.bitget_current_price * 100
                    self.last_price_update = datetime.now()
                    self.price_failure_count = 0
                else:
                    self.price_failure_count += 1
                
                # 🔥🔥🔥 시세 차이와 관계없이 처리 계속 - 정보용으로만 사용
                
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
                f"• 🔄 5초마다 예약 주문 동기화\n"
                f"• 🔥 15초마다 강제 동기화 (강화)\n"
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
            self.logger.error(f"계정 상태 로깅 실패: {e}")
    
    def _get_valid_price_difference(self) -> Optional[float]:
        """유효한 시세 차이 반환"""
        try:
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                return abs(self.bitget_current_price - self.gate_current_price)
            elif self.last_valid_bitget_price > 0 and self.last_valid_gate_price > 0:
                return abs(self.last_valid_bitget_price - self.last_valid_gate_price)
            else:
                return None
        except:
            return None
    
    async def get_daily_report(self) -> str:
        """일일 리포트 생성"""
        try:
            # 성공률 계산
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / self.daily_stats['total_mirrored']) * 100
            
            # TP/SL 성과 통계
            perfect_mirrors = self.daily_stats.get('perfect_mirrors', 0)
            partial_mirrors = self.daily_stats.get('partial_mirrors', 0)
            tp_sl_success = self.daily_stats.get('tp_sl_success', 0)
            tp_sl_failed = self.daily_stats.get('tp_sl_failed', 0)
            
            return f"""🔄 <b>미러 트레이딩 일일 성과</b>

📊 기본 미러링 성과:
- 주문 기반: {self.daily_stats['order_mirrors']}회
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

🔧 시스템 최적화 (강화):
- 예약 주문 체크: 5초마다
- 동기화 체크: 5초마다
- 강제 동기화: 15초마다 (강화)
- 슬리피지 보호: 0.05% 제한

🔥 시세 차이와 무관하게 모든 주문을 즉시 처리하여
완벽한 미러링을 보장합니다."""
            
        except Exception as e:
            self.logger.error(f"일일 리포트 생성 실패: {e}")
            return f"일일 리포트 생성 중 오류 발생: {str(e)}"
