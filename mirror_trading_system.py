import os
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import traceback

from mirror_position_manager import MirrorPositionManager
from mirror_trading_utils import MirrorTradingUtils

logger = logging.getLogger(__name__)

class MirrorTradingSystem:
    """🔥🔥🔥 미러 트레이딩 시스템 - 텔레그램 실시간 배율 조정 + 예약 주문 취소 동기화"""
    
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading_system')
        
        # 🔥🔥🔥 환경변수 처리 - O/X 지원
        raw_mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'O')
        self.mirror_trading_enabled = self._parse_mirror_trading_mode(raw_mirror_mode)
        
        # 🔥🔥🔥 텔레그램 실시간 배율 조정 시스템
        self.mirror_ratio_multiplier = 1.0  # 기본 복제 비율 1배
        self.ratio_adjustment_enabled = True
        self.ratio_change_history = []
        
        self.logger.info(f"🔥 미러 트레이딩 시스템 환경변수: 미러링모드='{raw_mirror_mode}' → {'활성화' if self.mirror_trading_enabled else '비활성화'}")
        self.logger.info(f"🔥 초기 복제 비율: {self.mirror_ratio_multiplier}x (텔레그램으로 실시간 조정 가능)")
        
        # 유틸리티 초기화
        self.utils = MirrorTradingUtils(config, bitget_client, gate_client)
        
        # 포지션 매니저 초기화
        self.position_manager = MirrorPositionManager(
            config, bitget_client, gate_client, gate_client, telegram_bot, self.utils
        )
        
        # 미러링 상태 관리
        self.is_running = False
        self.last_price_update = datetime.min
        self.price_update_interval = 5  # 5초마다 시세 업데이트
        
        # 통계 추적
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'ratio_adjustments': 0,
            'errors': []
        }
        
        # 모니터링 설정
        self.monitor_interval = int(os.getenv('MIRROR_CHECK_INTERVAL', '45'))  # 45초 기본값
        
        # 상속된 속성들 (포지션 매니저에서 사용)
        self.mirrored_positions = {}
        self.failed_mirrors = []
        
        self.logger.info(f"✅ 미러 트레이딩 시스템 초기화 완료 - 모드: {'활성화' if self.mirror_trading_enabled else '비활성화'}")
        self.logger.info(f"   - 복제 비율: {self.mirror_ratio_multiplier}x (실시간 조정 가능)")
        self.logger.info(f"   - 모니터링 주기: {self.monitor_interval}초")

    def _parse_mirror_trading_mode(self, mode_str: str) -> bool:
        """🔥🔥🔥 미러링 모드 파싱 - O/X 정확한 구분"""
        if isinstance(mode_str, bool):
            return mode_str
        
        mode_str_original = str(mode_str).strip()
        mode_str_upper = mode_str_original.upper()
        
        self.logger.info(f"🔍 미러링 시스템 모드 파싱: 원본='{mode_str_original}', 대문자='{mode_str_upper}'")
        
        if mode_str_upper == 'O':
            self.logger.info("✅ 미러링 시스템: 영어 대문자 O 감지 → 활성화")
            return True
        elif mode_str_upper == 'X':
            self.logger.info("✅ 미러링 시스템: 영어 대문자 X 감지 → 비활성화")
            return False
        elif mode_str_upper in ['ON', 'OPEN', 'TRUE', 'Y', 'YES']:
            self.logger.info(f"✅ 미러링 시스템 활성화 키워드: '{mode_str_upper}' → 활성화")
            return True
        elif mode_str_upper in ['OFF', 'CLOSE', 'FALSE', 'N', 'NO'] or mode_str_original == '0':
            self.logger.info(f"✅ 미러링 시스템 비활성화 키워드: '{mode_str_upper}' → 비활성화")
            return False
        elif mode_str_original == '1':
            self.logger.info("✅ 미러링 시스템: 숫자 1 감지 → 활성화")
            return True
        else:
            self.logger.warning(f"⚠️ 미러링 시스템: 알 수 없는 모드: '{mode_str_original}', 기본값(활성화) 사용")
            return True

    async def initialize(self):
        """미러 트레이딩 시스템 초기화"""
        try:
            if not self.mirror_trading_enabled:
                self.logger.warning("⚠️ 미러 트레이딩이 비활성화되어 있습니다")
                return
            
            self.logger.info("🔄 미러 트레이딩 시스템 초기화 시작...")
            
            # 포지션 매니저 초기화
            await self.position_manager.initialize()
            
            # 포지션 매니저에 현재 배율 설정
            self.position_manager.mirror_ratio_multiplier = self.mirror_ratio_multiplier
            
            self.logger.info("✅ 미러 트레이딩 시스템 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시스템 초기화 실패: {e}")
            raise

    async def start(self):
        """미러 트레이딩 시스템 시작"""
        try:
            if not self.mirror_trading_enabled:
                self.logger.info("미러 트레이딩이 비활성화되어 있어 시작하지 않습니다")
                return
            
            self.is_running = True
            self.logger.info("🚀 미러 트레이딩 시스템 시작")
            
            # 초기화
            await self.initialize()
            
            # 메인 루프 시작
            asyncio.create_task(self._main_loop())
            
            # 시작 알림
            await self.telegram.send_message(
                f"🚀 미러 트레이딩 시스템 시작\n"
                f"복제 비율: {self.mirror_ratio_multiplier}x\n"
                f"모니터링 주기: {self.monitor_interval}초\n"
                f"텔레그램 실시간 배율 조정: 활성화"
            )
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시스템 시작 실패: {e}")
            self.is_running = False

    async def _main_loop(self):
        """미러 트레이딩 메인 루프"""
        try:
            while self.is_running:
                try:
                    # 시세 업데이트
                    await self._update_prices()
                    
                    # 예약 주문 모니터링
                    await self.position_manager.monitor_plan_orders_cycle()
                    
                    # 배율 동기화
                    self.position_manager.mirror_ratio_multiplier = self.mirror_ratio_multiplier
                    
                    await asyncio.sleep(self.monitor_interval)
                    
                except Exception as e:
                    self.logger.error(f"미러 트레이딩 메인 루프 오류: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            self.logger.error(f"미러 트레이딩 메인 루프 치명적 오류: {e}")
            self.is_running = False

    async def _update_prices(self):
        """시세 정보 업데이트"""
        try:
            current_time = datetime.now()
            
            if (current_time - self.last_price_update).total_seconds() < self.price_update_interval:
                return
            
            # 비트겟 시세
            bitget_ticker = await self.bitget.get_ticker('BTCUSDT')
            bitget_price = float(bitget_ticker.get('last', 0)) if bitget_ticker else 0
            
            # 게이트 시세
            gate_ticker = await self.gate.get_ticker('BTC_USDT')
            gate_price = float(gate_ticker.get('last', 0)) if gate_ticker else 0
            
            if bitget_price > 0 and gate_price > 0:
                price_diff_percent = abs(bitget_price - gate_price) / bitget_price * 100
                
                # 포지션 매니저에 시세 업데이트
                self.position_manager.update_prices(bitget_price, gate_price, price_diff_percent)
                
                self.last_price_update = current_time
                
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    async def update_ratio_multiplier(self, new_ratio: float, user_info: str = "Unknown") -> Dict:
        """🔥🔥🔥 복제 비율 실시간 업데이트"""
        try:
            old_ratio = self.mirror_ratio_multiplier
            
            # 유효성 검증
            if new_ratio < 0.1:
                return {
                    'success': False,
                    'error': f'복제 비율이 너무 낮습니다 (최소: 0.1배)',
                    'old_ratio': old_ratio,
                    'requested_ratio': new_ratio
                }
            
            if new_ratio > 10.0:
                return {
                    'success': False,
                    'error': f'복제 비율이 너무 높습니다 (최대: 10.0배)',
                    'old_ratio': old_ratio,
                    'requested_ratio': new_ratio
                }
            
            # 복제 비율 업데이트
            self.mirror_ratio_multiplier = new_ratio
            
            # 포지션 매니저에도 동기화
            if hasattr(self, 'position_manager') and self.position_manager:
                self.position_manager.mirror_ratio_multiplier = new_ratio
            
            # 변경 내역 기록
            change_record = {
                'timestamp': datetime.now().isoformat(),
                'old_ratio': old_ratio,
                'new_ratio': new_ratio,
                'user': user_info,
                'difference': new_ratio - old_ratio
            }
            
            self.ratio_change_history.append(change_record)
            self.daily_stats['ratio_adjustments'] += 1
            
            # 변경률 계산
            change_percent = ((new_ratio - old_ratio) / old_ratio * 100) if old_ratio > 0 else 0
            
            self.logger.info(f"🎯 복제 비율 실시간 업데이트: {old_ratio}x → {new_ratio}x ({change_percent:+.1f}%) by {user_info}")
            
            return {
                'success': True,
                'old_ratio': old_ratio,
                'new_ratio': new_ratio,
                'change_percent': change_percent,
                'user': user_info,
                'timestamp': change_record['timestamp'],
                'description': self._get_ratio_description(new_ratio)
            }
            
        except Exception as e:
            self.logger.error(f"복제 비율 업데이트 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'old_ratio': self.mirror_ratio_multiplier,
                'requested_ratio': new_ratio
            }

    def _get_ratio_description(self, ratio: float) -> str:
        """복제 비율 설명 생성"""
        if ratio == 1.0:
            return "원본과 동일한 비율"
        elif ratio < 1.0:
            percentage = ratio * 100
            return f"원본의 {percentage:.1f}% 크기로 축소"
        else:
            return f"원본의 {ratio:.1f}배 크기로 확대"

    async def get_current_status(self) -> Dict:
        """현재 미러 트레이딩 상태 조회"""
        try:
            # 비트겟 계정 정보
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            # 포지션 정보
            bitget_positions = await self.bitget.get_positions('BTCUSDT')
            gate_positions = await self.gate.get_positions('BTC_USDT')
            
            bitget_pos_count = sum(1 for pos in bitget_positions if float(pos.get('total', 0)) > 0)
            gate_pos_count = sum(1 for pos in gate_positions if pos.get('size', 0) != 0)
            
            # 동기화 상태
            sync_status = await self.position_manager.check_sync_status()
            
            return {
                'is_running': self.is_running,
                'mirror_enabled': self.mirror_trading_enabled,
                'current_ratio': self.mirror_ratio_multiplier,
                'ratio_description': self._get_ratio_description(self.mirror_ratio_multiplier),
                'accounts': {
                    'bitget_equity': bitget_equity,
                    'gate_equity': gate_equity,
                    'equity_ratio': (gate_equity / bitget_equity * 100) if bitget_equity > 0 else 0
                },
                'positions': {
                    'bitget_count': bitget_pos_count,
                    'gate_count': gate_pos_count,
                    'is_synced': sync_status['is_synced']
                },
                'daily_stats': self.daily_stats.copy(),
                'ratio_changes_today': len(self.ratio_change_history)
            }
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 상태 조회 실패: {e}")
            return {
                'is_running': self.is_running,
                'mirror_enabled': self.mirror_trading_enabled,
                'current_ratio': self.mirror_ratio_multiplier,
                'error': str(e)
            }

    async def stop(self):
        """미러 트레이딩 시스템 중지"""
        try:
            self.is_running = False
            
            if hasattr(self, 'position_manager'):
                await self.position_manager.stop()
            
            # 종료 알림
            if self.mirror_trading_enabled:
                await self.telegram.send_message(
                    f"🛑 미러 트레이딩 시스템 종료\n"
                    f"최종 복제 비율: {self.mirror_ratio_multiplier}x\n"
                    f"오늘 배율 조정: {len(self.ratio_change_history)}회"
                )
            
            self.logger.info("✅ 미러 트레이딩 시스템 종료 완료")
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시스템 종료 실패: {e}")

    # 기존 메서드들과의 호환성을 위한 속성 접근
    @property
    def mirrored_positions(self):
        """포지션 매니저의 미러링된 포지션 반환"""
        if hasattr(self, 'position_manager'):
            return self.position_manager.mirrored_positions
        return {}
    
    @mirrored_positions.setter
    def mirrored_positions(self, value):
        """포지션 매니저의 미러링된 포지션 설정"""
        if hasattr(self, 'position_manager'):
            self.position_manager.mirrored_positions = value

    @property
    def failed_mirrors(self):
        """포지션 매니저의 실패한 미러링 반환"""
        if hasattr(self, 'position_manager'):
            return self.position_manager.failed_mirrors
        return []
    
    @failed_mirrors.setter
    def failed_mirrors(self, value):
        """포지션 매니저의 실패한 미러링 설정"""
        if hasattr(self, 'position_manager'):
            self.position_manager.failed_mirrors = value

    @property
    def daily_stats(self):
        """포지션 매니저의 일일 통계 반환"""
        if hasattr(self, 'position_manager'):
            # 기본 통계와 포지션 매니저 통계 합치기
            base_stats = {
                'total_mirrored': 0,
                'successful_mirrors': 0,
                'failed_mirrors': 0,
                'partial_closes': 0,
                'full_closes': 0,
                'total_volume': 0.0,
                'plan_order_mirrors': 0,
                'plan_order_cancels': 0,
                'ratio_adjustments': len(self.ratio_change_history),
                'errors': []
            }
            base_stats.update(self.position_manager.daily_stats)
            return base_stats
        return {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'ratio_adjustments': len(self.ratio_change_history),
            'errors': []
        }
    
    @daily_stats.setter
    def daily_stats(self, value):
        """포지션 매니저의 일일 통계 설정"""
        if hasattr(self, 'position_manager'):
            self.position_manager.daily_stats.update(value)
