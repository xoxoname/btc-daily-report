# report_generators/profit_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback
from datetime import datetime, timedelta
import pytz

class ProfitReportGenerator(BaseReportGenerator):
    """수익 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.gateio_client = None  # Gate.io 클라이언트 추가
        
        # 2025년 5월 1일부터 집계 시작
        self.PROFIT_START_DATE = datetime(2025, 5, 1, tzinfo=pytz.timezone('Asia/Seoul'))
        
        # 초기 자산 설정 (2025년 5월 1일 기준)
        self.BITGET_INITIAL_CAPITAL = 4000.0  # 2025년 5월 1일 기준 초기 자산 $4000
    
    def set_gateio_client(self, gateio_client):
        """Gate.io 클라이언트 설정"""
        self.gateio_client = gateio_client
        self.logger.info("✅ Gate.io 클라이언트 설정 완료")
        
    async def generate_report(self) -> str:
        """💰 /profit 명령어 리포트 생성"""
        try:
            current_time = self._get_current_time_kst()
            
            # Bitget 데이터 조회 - Position PnL 기준
            bitget_data = await self._get_bitget_data_position_pnl()
            
            # Gate.io 데이터 조회 - Position PnL 기준
            gateio_data = await self._get_gateio_data_position_pnl()
            
            # Gate.io 실제 사용 여부 확인
            gateio_has_data = (gateio_data.get('has_account', False) and 
                             gateio_data.get('total_equity', 0) > 0)
            
            # 통합 데이터 계산
            combined_data = self._calculate_combined_data_position_pnl(bitget_data, gateio_data)
            
            # 통합 자산 현황
            asset_summary = self._format_asset_summary(combined_data, gateio_has_data)
            
            # 거래소별 포지션 정보
            positions_text = await self._format_positions_detail(bitget_data, gateio_data, gateio_has_data)
            
            # 거래소별 손익 정보 - Position PnL 기준 (개선된 형식)
            profit_detail = self._format_profit_detail_position_pnl_improved(bitget_data, gateio_data, combined_data, gateio_has_data)
            
            # 통합 자산 정보
            asset_detail = self._format_asset_detail(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 누적 성과 (2025년 5월부터)
            cumulative_text = self._format_cumulative_performance_position_pnl(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 7일 수익 (간소화된 형식)
            seven_day_text = self._format_7day_profit_simple(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 멘탈 케어 - 통합 데이터 기반
            mental_text = await self._generate_combined_mental_care(combined_data)
            
            report = f"""💰 <b>실시간 손익 현황 (Position PnL 기준)</b>
📅 {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📌 <b>통합 자산</b>
{asset_summary}

📌 <b>포지션</b>
{positions_text}

💸 <b>금일 손익</b>
{profit_detail}

💼 <b>자산 상세</b>
{asset_detail}

📊 <b>누적 성과 (2025.5월~)</b>
{cumulative_text}

📈 <b>7일 수익</b>
{seven_day_text}

━━━━━━━━━━━━━━━━━━━
🧠 <b>멘탈 케어</b>
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"수익 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return "❌ 수익 현황 조회 중 오류가 발생했습니다."
    
    async def _get_bitget_data_position_pnl(self) -> dict:
        """🔥🔥 Bitget Position PnL 기준 정확한 데이터 조회 - 수수료 분리 + 강화된 오류 처리"""
        try:
            self.logger.info("🔍 Bitget Position PnL 기준 정확한 데이터 조회 시작...")
            
            # 🔥🔥 단계별 데이터 조회 (오류 격리)
            market_data = {}
            position_info = {'has_position': False}
            account_info = {}
            today_position_pnl = 0.0
            weekly_position_pnl = {'total_pnl': 0, 'average_daily': 0, 'actual_days': 7}
            cumulative_data = {'total_profit': 0, 'roi': 0}
            
            # 1. 시장 데이터 조회 (실패해도 계속)
            try:
                market_data = await self._get_market_data()
                self.logger.info("✅ 시장 데이터 조회 성공")
            except Exception as e:
                self.logger.warning(f"⚠️ 시장 데이터 조회 실패: {e}")
                market_data = {}
            
            # 2. 계정 정보 조회 (가장 중요)
            try:
                account_info = await self._get_account_info()
                if account_info:
                    self.logger.info(f"✅ 계정 정보 조회 성공: ${account_info.get('total_equity', 0):.2f}")
                else:
                    self.logger.error("❌ 계정 정보 조회 실패 - 빈 응답")
                    raise Exception("계정 정보 없음")
            except Exception as e:
                self.logger.error(f"❌ 계정 정보 조회 실패: {e}")
                # 🔥🔥 계정 정보 실패시 기본값 설정
                account_info = {
                    'total_equity': 0,
                    'available': 0,
                    'used_margin': 0,
                    'unrealized_pnl': 0,
                    'margin_balance': 0,
                    'wallet_balance': 0
                }
            
            # 3. 포지션 정보 조회 (실패해도 계속)
            try:
                position_info = await self._get_position_info()
                if position_info.get('has_position'):
                    self.logger.info(f"✅ 포지션 정보 조회 성공: {position_info.get('side')} 포지션")
                else:
                    self.logger.info("ℹ️ 현재 포지션 없음")
            except Exception as e:
                self.logger.warning(f"⚠️ 포지션 정보 조회 실패: {e}")
                position_info = {'has_position': False}
            
            # 4. 오늘 Position PnL 조회 (실패해도 계속)
            try:
                today_position_pnl = await self.bitget_client.get_today_position_pnl()
                self.logger.info(f"✅ 오늘 Position PnL: ${today_position_pnl:.4f}")
            except Exception as e:
                self.logger.warning(f"⚠️ 오늘 Position PnL 조회 실패: {e}")
                today_position_pnl = 0.0
            
            # 5. 7일 Position PnL 조회 (실패해도 계속)
            try:
                weekly_position_pnl = await self.bitget_client.get_7day_position_pnl()
                self.logger.info(f"✅ 7일 Position PnL: ${weekly_position_pnl.get('total_pnl', 0):.4f}")
            except Exception as e:
                self.logger.warning(f"⚠️ 7일 Position PnL 조회 실패: {e}")
                weekly_position_pnl = {
                    'total_pnl': 0,
                    'average_daily': 0,
                    'actual_days': 7,
                    'trading_fees': 0,
                    'funding_fees': 0,
                    'net_profit': 0,
                    'source': 'error_fallback'
                }
            
            # 6. 누적 손익 조회 (실패해도 계속)
            try:
                cumulative_data = await self._get_cumulative_profit_since_may()
                self.logger.info(f"✅ 누적 수익: ${cumulative_data.get('total_profit', 0):.2f}")
            except Exception as e:
                self.logger.warning(f"⚠️ 누적 손익 조회 실패: {e}")
                cumulative_data = {'total_profit': 0, 'roi': 0}
            
            # 총 자산 확인
            total_equity = account_info.get('total_equity', 0)
            
            # 🔥🔥 사용 증거금 계산 개선 - 포지션 정보와 계정 정보 모두 확인
            used_margin = 0
            
            # 1순위: 계정 정보에서 직접 추출
            if account_info.get('used_margin', 0) > 0:
                used_margin = account_info.get('used_margin', 0)
                self.logger.info(f"Bitget 증거금 (계정정보): ${used_margin:.2f}")
            
            # 2순위: 포지션 정보에서 계산
            elif position_info.get('has_position', False):
                pos_margin = position_info.get('margin', 0)
                if pos_margin > 0:
                    used_margin = pos_margin
                    self.logger.info(f"Bitget 증거금 (포지션정보): ${used_margin:.2f}")
                else:
                    # 3순위: 포지션 크기와 가격으로 계산
                    size = position_info.get('size', 0)
                    current_price = position_info.get('current_price', 0)
                    leverage = position_info.get('leverage', 30)
                    
                    if size > 0 and current_price > 0 and leverage > 0:
                        position_value = size * current_price
                        used_margin = position_value / leverage
                        self.logger.info(f"Bitget 증거금 (계산): 사이즈={size}, 가격=${current_price:.2f}, 레버리지={leverage}x, 증거금=${used_margin:.2f}")
            
            # 4순위: 가용자산으로 역계산
            if used_margin == 0:
                available = account_info.get('available', 0)
                if available > 0 and total_equity > available:
                    used_margin = total_equity - available
                    self.logger.info(f"Bitget 증거금 (역계산): 총자산=${total_equity:.2f} - 가용=${available:.2f} = ${used_margin:.2f}")
            
            # 🔥🔥 API 연결 상태 체크
            api_healthy = total_equity > 0 or position_info.get('has_position', False)
            
            result = {
                'exchange': 'Bitget',
                'market_data': market_data,
                'position_info': position_info,
                'account_info': account_info,
                'today_pnl': today_position_pnl,  # Position PnL 기준
                'weekly_profit': {
                    'total': weekly_position_pnl.get('total_pnl', 0),  # Position PnL 기준
                    'average': weekly_position_pnl.get('average_daily', 0),
                    'actual_days': weekly_position_pnl.get('actual_days', 7),
                    'trading_fees': weekly_position_pnl.get('trading_fees', 0),
                    'funding_fees': weekly_position_pnl.get('funding_fees', 0),
                    'net_profit': weekly_position_pnl.get('net_profit', 0),
                    'source': weekly_position_pnl.get('source', 'position_pnl_based')
                },
                'cumulative_profit': cumulative_data.get('total_profit', 0),
                'cumulative_roi': cumulative_data.get('roi', 0),
                'total_equity': total_equity,
                'initial_capital': self.BITGET_INITIAL_CAPITAL,
                'available': account_info.get('available', 0),
                'used_margin': used_margin,  # 🔥🔥 개선된 증거금 계산
                'cumulative_data': cumulative_data,
                'api_healthy': api_healthy  # 🔥🔥 API 연결 상태
            }
            
            if api_healthy:
                self.logger.info(f"✅ Bitget Position PnL 기준 데이터 조회 완료:")
                self.logger.info(f"  - 오늘 Position PnL: ${today_position_pnl:.4f}")
                self.logger.info(f"  - 7일 Position PnL: ${weekly_position_pnl.get('total_pnl', 0):.4f}")
                self.logger.info(f"  - 누적 수익: ${cumulative_data.get('total_profit', 0):.2f}")
                self.logger.info(f"  - 사용 증거금: ${used_margin:.2f}")
            else:
                self.logger.warning("⚠️ Bitget API 연결 문제 - 기본값으로 설정")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Bitget Position PnL 데이터 조회 실패: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Bitget')
    
    async def _get_gateio_data_position_pnl(self) -> dict:
        """🔥🔥 Gate.io Position PnL 기준 정확한 손익 계산 - 강화된 안전장치"""
        try:
            # Gate.io 클라이언트가 없는 경우
            if not self.gateio_client:
                self.logger.info("Gate.io 클라이언트가 설정되지 않음")
                return self._get_empty_exchange_data('Gate')
            
            self.logger.info("🔍 Gate.io Position PnL 기준 정확한 손익 계산 시작...")
            
            # Gate 계정 정보 조회
            total_equity = 0
            available = 0
            unrealized_pnl = 0
            
            try:
                account_response = await self.gateio_client.get_account_balance()
                
                if account_response:
                    total_equity = float(account_response.get('total', 0))
                    available = float(account_response.get('available', 0))
                    unrealized_pnl = float(account_response.get('unrealised_pnl', 0))
                    
                    self.logger.info(f"Gate.io 계정 정보: total=${total_equity:.2f}, available=${available:.2f}, unrealized=${unrealized_pnl:.4f}")
                
            except Exception as e:
                self.logger.error(f"Gate 계정 조회 실패: {e}")
            
            # Gate 포지션 조회
            position_info = {'has_position': False}
            
            try:
                positions = await self.gateio_client.get_positions('BTC_USDT')
                
                if positions:
                    for pos in positions:
                        size = float(pos.get('size', 0))
                        if size != 0:
                            entry_price = float(pos.get('entry_price', 0))
                            mark_price = float(pos.get('mark_price', 0))
                            pos_unrealized_pnl = float(pos.get('unrealised_pnl', 0))
                            leverage = float(pos.get('leverage', 10))
                            
                            # 증거금 계산
                            btc_size = abs(size) * 0.0001  # Gate.io 계약 크기
                            position_value = btc_size * mark_price
                            margin_used = position_value / leverage
                            
                            # ROE 계산
                            roe = (pos_unrealized_pnl / margin_used) * 100 if margin_used > 0 else 0
                            
                            # 🔥🔥 청산가 안전장치 추가
                            liquidation_price = float(pos.get('liq_price', 0))
                            
                            # 청산가 검증
                            if liquidation_price > 0:
                                # 청산가가 현재가와 비교해서 말이 되는지 확인
                                price_ratio = liquidation_price / mark_price if mark_price > 0 else 0
                                
                                if size > 0:  # 롱 포지션
                                    if not (0.5 <= price_ratio <= 0.95):
                                        self.logger.warning(f"Gate.io 비현실적 청산가 감지 (롱): 현재=${mark_price:.2f}, 청산=${liquidation_price:.2f}")
                                        liquidation_price = entry_price * 0.8  # 보수적 추정
                                else:  # 숏 포지션
                                    if not (1.05 <= price_ratio <= 1.5):
                                        self.logger.warning(f"Gate.io 비현실적 청산가 감지 (숏): 현재=${mark_price:.2f}, 청산=${liquidation_price:.2f}")
                                        liquidation_price = entry_price * 1.2  # 보수적 추정
                            
                            position_info = {
                                'has_position': True,
                                'symbol': 'BTC_USDT',
                                'side': '롱' if size > 0 else '숏',
                                'side_en': 'long' if size > 0 else 'short',
                                'size': abs(size),
                                'btc_size': btc_size,
                                'entry_price': entry_price,
                                'current_price': mark_price,
                                'unrealized_pnl': pos_unrealized_pnl,
                                'roe': roe,
                                'contract_size': abs(size),
                                'leverage': leverage,
                                'margin': margin_used,
                                'liquidation_price': liquidation_price
                            }
                            break
                    
            except Exception as e:
                self.logger.error(f"Gate 포지션 조회 실패: {e}")
            
            # 🔥🔥 Position PnL 기준 손익 계산 - 강화된 안전장치
            today_position_pnl = 0.0
            weekly_profit = {'total_pnl': 0, 'average_daily': 0}
            cumulative_profit = 0.0
            initial_capital = 750  # 기본 초기 자본
            
            try:
                self.logger.info("🔍 Gate.io Position PnL 기준 손익 API 조회...")
                
                # 🔥🔥 오늘 Position PnL 조회 - 강화된 안전장치
                today_position_pnl = await self.gateio_client.get_today_position_pnl()
                
                # 🔥🔥 7일 Position PnL 조회 - 강화된 안전장치
                weekly_result = await self.gateio_client.get_7day_position_pnl()
                weekly_pnl_value = weekly_result.get('total_pnl', 0)
                
                weekly_profit = {
                    'total_pnl': weekly_pnl_value,
                    'average_daily': weekly_result.get('average_daily', 0),
                    'actual_days': weekly_result.get('actual_days', 7),
                    'trading_fees': weekly_result.get('trading_fees', 0),
                    'funding_fees': weekly_result.get('funding_fees', 0),
                    'net_profit': weekly_result.get('net_profit', 0),
                    'source': weekly_result.get('source', 'gate_position_pnl_based_enhanced_safety'),
                    'filtered_count': weekly_result.get('filtered_count', 0)
                }
                
                # 🔥🔥 누적 수익 계산 (잔고 기반 추정)
                if total_equity > 0:
                    # 현재 잔고에서 추정 초기 자본 차감
                    estimated_initial = 750
                    cumulative_profit = total_equity - estimated_initial
                    initial_capital = estimated_initial
                    
                    self.logger.info(f"✅ Gate.io Position PnL 기준 손익 계산 완료 (강화된 안전장치):")
                    self.logger.info(f"  - 오늘 Position PnL: ${today_position_pnl:.4f}")
                    self.logger.info(f"  - 7일 Position PnL: ${weekly_profit['total_pnl']:.4f}")
                    self.logger.info(f"  - 필터링된 거래: {weekly_profit.get('filtered_count', 0)}건")
                    self.logger.info(f"  - 누적 수익 (추정): ${cumulative_profit:.2f}")
                else:
                    self.logger.info("Gate.io 잔고가 0이거나 없음")
                
            except Exception as e:
                self.logger.error(f"Gate.io Position PnL 기반 손익 API 실패: {e}")
                # 오류 발생시 안전하게 0으로 처리
                today_position_pnl = 0.0
                weekly_profit = {
                    'total_pnl': 0, 
                    'average_daily': 0, 
                    'actual_days': 7, 
                    'trading_fees': 0, 
                    'funding_fees': 0, 
                    'net_profit': 0, 
                    'source': 'error_safe_fallback',
                    'filtered_count': 0
                }
            
            # 🔥🔥 사용 증거금 계산 개선 - Gate.io
            used_margin = 0
            if position_info['has_position']:
                used_margin = position_info.get('margin', 0)
                self.logger.info(f"Gate.io 증거금 (포지션): ${used_margin:.2f}")
            else:
                # 포지션이 없으면 가용자산으로 역계산
                if total_equity > 0 and available >= 0:
                    used_margin = max(0, total_equity - available)
                    self.logger.info(f"Gate.io 증거금 (역계산): ${used_margin:.2f}")
            
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            has_account = total_equity > 0
            
            self.logger.info(f"Gate.io 최종 Position PnL 기준 데이터 (강화된 안전장치):")
            self.logger.info(f"  - 계정 존재: {has_account}")
            self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
            self.logger.info(f"  - 사용 증거금: ${used_margin:.2f}")
            self.logger.info(f"  - 미실현손익: ${unrealized_pnl:.4f}")
            self.logger.info(f"  - 오늘 Position PnL: ${today_position_pnl:.4f}")
            self.logger.info(f"  - 7일 Position PnL: ${weekly_profit['total_pnl']:.4f}")
            self.logger.info(f"  - 누적 수익: ${cumulative_profit:.2f} ({cumulative_roi:+.1f}%)")
            
            return {
                'exchange': 'Gate',
                'position_info': position_info,
                'account_info': {
                    'total_equity': total_equity,
                    'available': available,
                    'used_margin': used_margin,  # 🔥🔥 개선된 증거금 계산
                    'unrealized_pnl': unrealized_pnl
                },
                'today_pnl': today_position_pnl,  # Position PnL 기준 (강화된 안전장치)
                'weekly_profit': weekly_profit,   # Position PnL 기준 (강화된 안전장치)
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': initial_capital,
                'available': available,
                'used_margin': used_margin,  # 🔥🔥 개선된 증거금 계산
                'has_account': has_account,
                'actual_profit': cumulative_profit
            }
            
        except Exception as e:
            self.logger.error(f"Gate Position PnL 기준 데이터 조회 실패: {e}")
            self.logger.error(f"Gate 데이터 오류 상세: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Gate')
    
    def _calculate_combined_data_position_pnl(self, bitget_data: dict, gateio_data: dict) -> dict:
        """Position PnL 기준 통합 데이터 계산 - 강화된 안전장치"""
        # 🔥🔥 API 연결 상태 체크
        bitget_healthy = bitget_data.get('api_healthy', True)
        gateio_healthy = gateio_data.get('has_account', False)
        
        self.logger.info(f"🔍 통합 데이터 계산:")
        self.logger.info(f"  - Bitget 상태: {'정상' if bitget_healthy else '오류'}")
        self.logger.info(f"  - Gate.io 상태: {'정상' if gateio_healthy else '없음'}")
        
        # 총 자산 (정상적인 데이터만 사용)
        bitget_equity = bitget_data['total_equity'] if bitget_healthy else 0
        gateio_equity = gateio_data['total_equity'] if gateio_healthy else 0
        total_equity = bitget_equity + gateio_equity
        
        # 가용 자산
        bitget_available = bitget_data['available'] if bitget_healthy else 0
        gateio_available = gateio_data['available'] if gateio_healthy else 0
        total_available = bitget_available + gateio_available
        
        # 🔥🔥 사용 증거금 (개선된 계산)
        bitget_used_margin = bitget_data['used_margin'] if bitget_healthy else 0
        gateio_used_margin = gateio_data['used_margin'] if gateio_healthy else 0
        total_used_margin = bitget_used_margin + gateio_used_margin
        
        # 🔥🔥 Position PnL 기준 금일 손익 계산 - 강화된 안전장치
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0) if bitget_healthy else 0
        gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0) if gateio_healthy else 0
        
        bitget_today_pnl = bitget_data['today_pnl'] if bitget_healthy else 0
        gateio_today_pnl = gateio_data['today_pnl'] if gateio_healthy else 0
        
        # 🔥🔥 개별 값 안전장치
        if abs(bitget_today_pnl) > 10000:
            self.logger.warning(f"Bitget 오늘 PnL 비현실적: ${bitget_today_pnl:.2f}, 0으로 처리")
            bitget_today_pnl = 0.0
        
        if abs(gateio_today_pnl) > 10000:
            self.logger.warning(f"Gate.io 오늘 PnL 비현실적: ${gateio_today_pnl:.2f}, 0으로 처리")
            gateio_today_pnl = 0.0
        
        today_position_pnl = bitget_today_pnl + gateio_today_pnl  # Position PnL 기준
        today_unrealized = bitget_unrealized + gateio_unrealized
        today_total = today_position_pnl + today_unrealized
        
        # 🔥🔥 7일 Position PnL (통합) - 강화된 안전장치
        bitget_weekly = bitget_data['weekly_profit']['total'] if bitget_healthy else 0
        gateio_weekly = gateio_data['weekly_profit']['total_pnl'] if gateio_healthy else 0
        
        # 🔥🔥 개별 7일 값 안전장치
        if abs(bitget_weekly) > 10000:
            self.logger.warning(f"Bitget 7일 PnL 비현실적: ${bitget_weekly:.2f}, 0으로 처리")
            bitget_weekly = 0.0
        
        if abs(gateio_weekly) > 10000:
            self.logger.warning(f"Gate.io 7일 PnL 비현실적: ${gateio_weekly:.2f}, 0으로 처리")
            gateio_weekly = 0.0
        
        weekly_total = bitget_weekly + gateio_weekly  # Position PnL 기준
        
        # 실제 일수 계산
        actual_days = 7.0
        if bitget_healthy:
            actual_days = max(actual_days, bitget_data['weekly_profit'].get('actual_days', 7))
        if gateio_healthy:
            actual_days = max(actual_days, gateio_data['weekly_profit'].get('actual_days', 7))
        
        weekly_avg = weekly_total / actual_days if actual_days > 0 else 0
        
        # 누적 수익 (2025년 5월부터)
        bitget_cumulative = bitget_data['cumulative_profit'] if bitget_healthy else 0
        gateio_cumulative = gateio_data['cumulative_profit'] if gateio_healthy else 0
        cumulative_profit = bitget_cumulative + gateio_cumulative
        
        # 수익률 계산 (분모가 0인 경우 방지)
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        initial_7d = total_equity - weekly_total
        weekly_roi = (weekly_total / initial_7d * 100) if initial_7d > 0 else 0
        
        # 🔥🔥 초기 자본 계산 개선
        bitget_initial = self.BITGET_INITIAL_CAPITAL if bitget_healthy else 0
        gateio_initial = gateio_data.get('initial_capital', 750) if gateio_healthy else 0
        total_initial = bitget_initial + gateio_initial
        
        cumulative_roi = (cumulative_profit / total_initial * 100) if total_initial > 0 else 0
        
        # 🔥🔥 검증: 7일과 누적이 다른지 확인
        seven_vs_cumulative_diff = abs(weekly_total - cumulative_profit)
        is_properly_separated = seven_vs_cumulative_diff > 50  # $50 이상 차이나야 정상
        
        self.logger.info(f"Position PnL 기준 통합 데이터 계산 (강화된 안전장치):")
        self.logger.info(f"  - 총 자산: ${total_equity:.2f} (B:${bitget_equity:.2f} + G:${gateio_equity:.2f})")
        self.logger.info(f"  - 오늘 Position PnL: ${today_position_pnl:.4f}")
        self.logger.info(f"  - 7일  Position PnL: ${weekly_total:.4f} ({actual_days:.1f}일)")
        self.logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
        self.logger.info(f"  - 총 증거금: ${total_used_margin:.2f}")
        self.logger.info(f"  - 차이: ${seven_vs_cumulative_diff:.2f}")
        self.logger.info(f"  - 정상 분리됨: {'✅' if is_properly_separated else '⚠️'}")
        
        return {
            'total_equity': total_equity,
            'total_available': total_available,
            'total_used_margin': total_used_margin,  # 🔥🔥 개선된 증거금 계산
            'today_position_pnl': today_position_pnl,  # Position PnL 기준
            'today_unrealized': today_unrealized,
            'today_total': today_total,
            'today_roi': today_roi,
            'weekly_total': weekly_total,    # Position PnL 기준
            'weekly_avg': weekly_avg,
            'weekly_roi': weekly_roi,
            'actual_days': actual_days,      # 실제 7일 기간
            'cumulative_profit': cumulative_profit,
            'cumulative_roi': cumulative_roi,
            'bitget_equity': bitget_equity,
            'gateio_equity': gateio_equity,
            'gateio_has_account': gateio_healthy,
            'total_initial': total_initial,
            'seven_vs_cumulative_diff': seven_vs_cumulative_diff,
            'is_properly_separated': is_properly_separated,
            # 개별 거래소 미실현/실현 손익
            'bitget_today_realized': bitget_today_pnl,
            'bitget_today_unrealized': bitget_unrealized,
            'gateio_today_realized': gateio_today_pnl,
            'gateio_today_unrealized': gateio_unrealized,
            # API 연결 상태
            'bitget_healthy': bitget_healthy,
            'gateio_healthy': gateio_healthy
        }
    
    def _format_profit_detail_position_pnl_improved(self, bitget_data: dict, gateio_data: dict, combined_data: dict, gateio_has_data: bool) -> str:
        """🔥🔥 개선된 Position PnL 기준 손익 정보 - 미실현/실현 분리 표시 + API 연결 상태 고려"""
        lines = []
        
        # 🔥🔥 API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 통합 손익 요약
        today_position_pnl = combined_data['today_position_pnl']
        today_unrealized = combined_data['today_unrealized']
        today_total = combined_data['today_total']
        today_roi = combined_data['today_roi']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(today_total, today_roi)}</b>")
        
        # Bitget 상세 - 미실현/실현 분리 (API 연결 상태 고려)
        if bitget_healthy:
            bitget_realized = combined_data['bitget_today_realized']
            bitget_unrealized = combined_data['bitget_today_unrealized']
            lines.append(f"  ├ Bitget: 미실현 {self._format_currency_html(bitget_unrealized, False)} | 실현 {self._format_currency_html(bitget_realized, False)}")
        else:
            lines.append(f"  ├ Bitget: API 연결 오류")
        
        # Gate 상세 - 데이터가 있는 경우만, 미실현/실현 분리
        if gateio_healthy and gateio_data['total_equity'] > 0:
            gateio_realized = combined_data['gateio_today_realized']
            gateio_unrealized = combined_data['gateio_today_unrealized']
            lines.append(f"  └ Gate: 미실현 {self._format_currency_html(gateio_unrealized, False)} | 실현 {self._format_currency_html(gateio_realized, False)}")
        elif gateio_has_data:
            lines.append(f"  └ Gate: ${gateio_data['total_equity']:,.2f} 계정")
        
        return '\n'.join(lines)
    
    def _format_7day_profit_simple(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """🔥🔥 간소화된 7일 수익 표시 + API 연결 상태 고려"""
        lines = []
        
        # 🔥🔥 API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 실제 기간 표시
        actual_days = combined_data.get('actual_days', 7.0)
        
        # 통합 7일 Position PnL
        lines.append(f"• <b>수익: {self._format_currency_compact(combined_data['weekly_total'], combined_data['weekly_roi'])}</b>")
        
        # 거래소별 7일 Position PnL
        if gateio_healthy and gateio_data['total_equity'] > 0:
            if bitget_healthy:
                bitget_weekly = bitget_data['weekly_profit']['total']
                lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_weekly, False)}")
            else:
                lines.append(f"  ├ Bitget: API 연결 오류")
            
            gate_weekly = gateio_data['weekly_profit']['total_pnl']
            gate_filtered = gateio_data['weekly_profit'].get('filtered_count', 0)
            gate_display = f"{self._format_currency_html(gate_weekly, False)}"
            if gate_filtered > 0:
                gate_display += f" (필터:{gate_filtered}건)"
            lines.append(f"  └ Gate: {gate_display}")
        else:
            # Bitget만 있는 경우
            if bitget_healthy:
                bitget_weekly = bitget_data['weekly_profit']['total']
                lines.append(f"  └ Bitget: {self._format_currency_html(bitget_weekly, False)}")
            else:
                lines.append(f"  └ Bitget: API 연결 오류")
        
        # 일평균 (실제 일수 기준)
        lines.append(f"• <b>일평균: {self._format_currency_compact_daily(combined_data['weekly_avg'])}</b>")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance_position_pnl(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """Position PnL 기준 누적 성과 - 2025년 5월부터 + API 연결 상태 고려"""
        lines = []
        
        # 🔥🔥 API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 통합 누적 수익
        total_cumulative = combined_data['cumulative_profit']
        total_cumulative_roi = combined_data['cumulative_roi']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(total_cumulative, total_cumulative_roi)}</b>")
        
        # 거래소별 상세
        if gateio_healthy and gateio_data['total_equity'] > 0:
            if bitget_healthy:
                lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)} ({bitget_data['cumulative_roi']:+.0f}%)")
            else:
                lines.append(f"  ├ Bitget: API 연결 오류")
            
            gate_roi = gateio_data['cumulative_roi']
            lines.append(f"  └ Gate: {self._format_currency_html(gateio_data['cumulative_profit'], False)} ({gate_roi:+.0f}%)")
        else:
            if bitget_healthy:
                lines.append(f"  └ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)} ({bitget_data['cumulative_roi']:+.0f}%)")
            else:
                lines.append(f"  └ Bitget: API 연결 오류")
        
        # 🔥🔥 검증 정보 추가 (개발용)
        if not combined_data.get('is_properly_separated', True):
            lines.append(f"  ⚠️ 7일({combined_data['weekly_total']:.0f})과 누적({total_cumulative:.0f}) 수익이 비슷함")
        
        return '\n'.join(lines)
    
    def _format_currency_html(self, amount: float, include_krw: bool = True) -> str:
        """HTML용 통화 포맷팅 - 안전장치 포함"""
        # 🔥🔥 비현실적인 값 안전장치
        if abs(amount) > 1000000:  # 100만 달러 이상은 오류로 간주
            return "$0.00"
        
        if amount > 0:
            usd_text = f"+${amount:.2f}"
        elif amount < 0:
            usd_text = f"-${abs(amount):.2f}"
        else:
            usd_text = "$0.00"
            
        if include_krw and amount != 0:
            krw_amount = int(abs(amount) * 1350 / 10000)
            if amount > 0:
                return f"{usd_text} (+{krw_amount}만원)"
            else:
                return f"{usd_text} (-{krw_amount}만원)"
        return usd_text
    
    def _format_currency_compact(self, amount: float, roi: float) -> str:
        """컴팩트한 통화+수익률 포맷 - 안전장치 포함"""
        # 🔥🔥 비현실적인 값 안전장치
        if abs(amount) > 1000000:  # 100만 달러 이상은 오류로 간주
            return "+$0.00 (+0만원/+0.0%)"
        
        if amount >= 0:
            sign = "+"
            krw = int(amount * 1350 / 10000)
            return f"{sign}${amount:.2f} ({sign}{krw}만원/{sign}{roi:.1f}%)"
        else:
            sign = "-"
            krw = int(abs(amount) * 1350 / 10000)
            return f"{sign}${abs(amount):.2f} ({sign}{krw}만원/{sign}{abs(roi):.1f}%)"
    
    def _format_currency_compact_daily(self, amount: float) -> str:
        """일평균용 컴팩트 포맷 - 안전장치 포함"""
        # 🔥🔥 비현실적인 값 안전장치
        if abs(amount) > 100000:  # 10만 달러 이상은 오류로 간주
            return "+$0.00 (+0만원/일)"
        
        if amount >= 0:
            sign = "+"
            krw = int(amount * 1350 / 10000)
            return f"{sign}${amount:.2f} ({sign}{krw}만원/일)"
        else:
            sign = "-"
            krw = int(abs(amount) * 1350 / 10000)
            return f"{sign}${abs(amount):.2f} ({sign}{krw}만원/일)"
    
    def _get_current_time_kst(self) -> str:
        """현재 시간을 KST로 반환"""
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        return now.strftime('%Y-%m-%d %H:%M')
    
    async def _get_market_data(self) -> dict:
        """시장 데이터 조회"""
        try:
            if not self.bitget_client:
                return {}
            
            ticker = await self.bitget_client.get_ticker(self.config.symbol)
            funding_rate = await self.bitget_client.get_funding_rate(self.config.symbol)
            
            return {
                'current_price': float(ticker.get('last', 0)) if ticker else 0,
                'change_24h': float(ticker.get('changeUtc', 0)) if ticker else 0,
                'funding_rate': float(funding_rate.get('fundingRate', 0)) if funding_rate else 0,
                'volume_24h': float(ticker.get('baseVolume', 0)) if ticker else 0
            }
        except Exception as e:
            self.logger.error(f"시장 데이터 조회 실패: {e}")
            return {}
    
    async def _get_account_info(self) -> dict:
        """계정 정보 조회"""
        try:
            if not self.bitget_client:
                return {}
            
            account = await self.bitget_client.get_account_info()
            
            if not account:
                return {}
            
            # 계정 정보 파싱
            total_equity = float(account.get('accountEquity', 0))
            available = float(account.get('available', 0))
            used_margin = float(account.get('usedMargin', 0))
            unrealized_pnl = float(account.get('unrealizedPL', 0))
            
            return {
                'total_equity': total_equity,
                'available': available,
                'used_margin': used_margin,
                'unrealized_pnl': unrealized_pnl,
                'margin_balance': float(account.get('marginBalance', 0)),
                'wallet_balance': float(account.get('walletBalance', 0))
            }
            
        except Exception as e:
            self.logger.error(f"계정 정보 조회 실패: {e}")
            return {}
    
    async def _get_position_info(self) -> dict:
        """포지션 정보 조회 (Bitget) - 청산가 개선"""
        try:
            positions = await self.bitget_client.get_positions(self.config.symbol)
            
            if not positions:
                return {'has_position': False}
            
            # 활성 포지션 찾기
            for position in positions:
                total_size = float(position.get('total', 0))
                if total_size > 0:
                    hold_side = position.get('holdSide', '')
                    side = '롱' if hold_side == 'long' else '숏'
                    
                    # 필요한 값들 추출
                    entry_price = float(position.get('openPriceAvg', 0))
                    mark_price = float(position.get('markPrice', 0))
                    margin_mode = position.get('marginMode', '')
                    
                    # 🔥🔥 증거금 추출 개선 - 더 정확한 계산
                    margin = 0
                    
                    # 1순위: 계정 정보에서 usedMargin 사용 (가장 정확)
                    account_info = await self._get_account_info()
                    if account_info.get('used_margin', 0) > 0:
                        margin = account_info.get('used_margin', 0)
                        self.logger.info(f"포지션 증거금 (계정정보): ${margin:.2f}")
                    else:
                        # 2순위: 포지션 필드들에서 추출
                        margin_fields = ['margin', 'initialMargin', 'im', 'holdMargin']
                        for field in margin_fields:
                            if field in position and position[field]:
                                try:
                                    field_margin = float(position[field])
                                    if field_margin > 0:
                                        margin = field_margin
                                        self.logger.info(f"포지션 증거금 ({field}): ${margin:.2f}")
                                        break
                                except:
                                    continue
                        
                        # 3순위: 계산으로 추정
                        if margin == 0:
                            leverage = float(position.get('leverage', 10))
                            position_value = total_size * mark_price
                            margin = position_value / leverage
                            self.logger.info(f"포지션 증거금 (계산): ${margin:.2f}")
                    
                    # 미실현 손익
                    unrealized_pnl = float(position.get('unrealizedPL', 0))
                    
                    # ROE 계산
                    roe = (unrealized_pnl / margin) * 100 if margin > 0 else 0
                    
                    # 🔥🔥 청산가 추출 및 검증 (개선된 로직)
                    liquidation_price = 0
                    leverage = float(position.get('leverage', 10))
                    
                    # 원본 청산가 필드들 시도
                    liq_fields = ['liquidationPrice', 'liqPrice', 'estimatedLiqPrice']
                    for field in liq_fields:
                        if field in position and position[field]:
                            try:
                                raw_liq_price = float(position[field])
                                
                                # 🔥🔥 청산가 유효성 검증
                                if self._is_liquidation_price_valid(raw_liq_price, mark_price, hold_side):
                                    liquidation_price = raw_liq_price
                                    self.logger.info(f"유효한 청산가 ({field}): ${liquidation_price:,.2f}")
                                    break
                                else:
                                    self.logger.warning(f"비현실적 청산가 무시 ({field}): ${raw_liq_price:,.2f}")
                            except (ValueError, TypeError):
                                continue
                    
                    # 🔥🔥 청산가가 없거나 비현실적이면 계산
                    if liquidation_price <= 0:
                        if hold_side == 'long':
                            liquidation_price = entry_price * (1 - 0.9/leverage)
                        else:
                            liquidation_price = entry_price * (1 + 0.9/leverage)
                        self.logger.info(f"청산가 계산: ${liquidation_price:,.2f} ({hold_side}, {leverage}x)")
                    
                    return {
                        'has_position': True,
                        'symbol': self.config.symbol,
                        'side': side,
                        'side_en': hold_side,
                        'size': total_size,
                        'entry_price': entry_price,
                        'current_price': mark_price,
                        'margin_mode': margin_mode,
                        'margin': margin,  # 🔥🔥 개선된 증거금 계산
                        'unrealized_pnl': unrealized_pnl,
                        'roe': roe,
                        'liquidation_price': liquidation_price,  # 🔥🔥 검증된 청산가
                        'leverage': leverage
                    }
            
            return {'has_position': False}
            
        except Exception as e:
            self.logger.error(f"포지션 정보 조회 실패: {e}")
            return {'has_position': False}
    
    def _is_liquidation_price_valid(self, liq_price: float, mark_price: float, hold_side: str) -> bool:
        """🔥🔥 청산가 유효성 검증"""
        try:
            if liq_price <= 0 or mark_price <= 0:
                return False
            
            # 청산가가 현재가와 비교해서 말이 되는지 확인
            price_ratio = liq_price / mark_price
            
            if hold_side == 'long':
                # 롱 포지션: 청산가는 현재가보다 낮아야 함 (50% ~ 95% 범위)
                if 0.5 <= price_ratio <= 0.95:
                    return True
                else:
                    self.logger.warning(f"롱 포지션 청산가 비정상: 현재가=${mark_price:,.2f}, 청산가=${liq_price:,.2f} (비율: {price_ratio:.2f})")
                    return False
            else:
                # 숏 포지션: 청산가는 현재가보다 높아야 함 (105% ~ 150% 범위)
                if 1.05 <= price_ratio <= 1.5:
                    return True
                else:
                    self.logger.warning(f"숏 포지션 청산가 비정상: 현재가=${mark_price:,.2f}, 청산가=${liq_price:,.2f} (비율: {price_ratio:.2f})")
                    return False
                    
        except Exception as e:
            self.logger.error(f"청산가 유효성 검증 오류: {e}")
            return False
    
    async def _get_cumulative_profit_since_may(self) -> dict:
        """2025년 5월 1일부터 누적 손익 조회"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            start_date = self.PROFIT_START_DATE
            
            # 방법 2: 현재 잔고에서 초기 자본 차감 (간단하고 정확)
            try:
                account_info = await self._get_account_info()
                current_equity = account_info.get('total_equity', 0)
                
                # 누적 수익 = 현재 잔고 - 초기 자본
                total_profit = current_equity - self.BITGET_INITIAL_CAPITAL
                roi = (total_profit / self.BITGET_INITIAL_CAPITAL) * 100 if self.BITGET_INITIAL_CAPITAL > 0 else 0
                
                period_days = (now - start_date).days
                daily_average = total_profit / max(period_days, 1)
                
                return {
                    'total_profit': total_profit,
                    'monthly_profit': {},
                    'trade_count': 0,
                    'roi': roi,
                    'source': 'balance_minus_initial_capital',
                    'period_days': period_days,
                    'daily_average': daily_average,
                    'current_equity': current_equity,
                    'initial_capital': self.BITGET_INITIAL_CAPITAL
                }
                
            except Exception as e:
                self.logger.error(f"잔고 기반 누적 수익 계산 실패: {e}")
            
            # 기본값 반환
            return {
                'total_profit': 0,
                'monthly_profit': {},
                'trade_count': 0,
                'roi': 0,
                'source': 'fallback_zero',
                'period_days': 0,
                'daily_average': 0
            }
            
        except Exception as e:
            self.logger.error(f"2025년 5월부터 누적 손익 조회 실패: {e}")
            return {
                'total_profit': 0,
                'monthly_profit': {},
                'trade_count': 0,
                'roi': 0,
                'source': 'error',
                'period_days': 0,
                'daily_average': 0
            }
    
    def _get_empty_exchange_data(self, exchange_name: str) -> dict:
        """빈 거래소 데이터"""
        return {
            'exchange': exchange_name,
            'position_info': {'has_position': False},
            'account_info': {'total_equity': 0, 'unrealized_pnl': 0, 'available': 0, 'used_margin': 0},
            'today_pnl': 0,
            'weekly_profit': {'total': 0, 'average': 0, 'total_pnl': 0, 'average_daily': 0},
            'cumulative_profit': 0,
            'cumulative_roi': 0,
            'total_equity': 0,
            'initial_capital': 0,
            'available': 0,
            'used_margin': 0,
            'has_account': False
        }
    
    def _format_asset_summary(self, combined_data: dict, gateio_has_data: bool) -> str:
        """통합 자산 현황 요약 - API 연결 상태 고려"""
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        # 🔥🔥 API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        lines = []
        
        # Gate 계정이 있고 데이터가 있는 경우
        if gateio_healthy and gateio_equity > 0:
            lines.append(f"• <b>총 자산: ${total_equity:,.2f}</b> ({int(total_equity * 1350 / 10000)}만원)")
            
            # Bitget 비율 계산 (API 상태 고려)
            if bitget_healthy and total_equity > 0:
                bitget_pct = bitget_equity / total_equity * 100
                lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({int(bitget_equity * 1350 / 10000)}만원/{bitget_pct:.0f}%)")
            else:
                lines.append(f"  ├ Bitget: API 연결 오류 (${bitget_equity:,.2f})")
            
            # Gate.io 비율 계산
            if total_equity > 0:
                gate_pct = gateio_equity / total_equity * 100
                lines.append(f"  └ Gate: ${gateio_equity:,.2f} ({int(gateio_equity * 1350 / 10000)}만원/{gate_pct:.0f}%)")
            else:
                lines.append(f"  └ Gate: ${gateio_equity:,.2f} ({int(gateio_equity * 1350 / 10000)}만원)")
        else:
            # Gate 계정이 없거나 Bitget만 있는 경우
            lines.append(f"• <b>총 자산: ${total_equity:,.2f}</b> ({int(total_equity * 1350 / 10000)}만원)")
            
            if bitget_healthy:
                lines.append(f"  └ Bitget: ${bitget_equity:,.2f} ({int(bitget_equity * 1350 / 10000)}만원/100%)")
            else:
                lines.append(f"  └ Bitget: API 연결 오류")
        
        return '\n'.join(lines)
    
    async def _format_positions_detail(self, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """거래소별 포지션 상세 정보 - API 연결 상태 고려"""
        lines = []
        has_any_position = False
        
        # 🔥🔥 API 연결 상태 확인
        bitget_healthy = bitget_data.get('api_healthy', True)
        gateio_healthy = gateio_data.get('has_account', False)
        
        # Bitget 포지션
        if bitget_healthy:
            bitget_pos = bitget_data['position_info']
            if bitget_pos.get('has_position'):
                has_any_position = True
                lines.append("━━━ <b>Bitget</b> ━━━")
                
                roe = bitget_pos.get('roe', 0)
                roe_sign = "+" if roe >= 0 else ""
                
                lines.append(f"• BTC {bitget_pos.get('side')} | 진입: ${bitget_pos.get('entry_price', 0):,.2f} ({roe_sign}{roe:.1f}%)")
                lines.append(f"• 현재가: ${bitget_pos.get('current_price', 0):,.2f} | 증거금: ${bitget_pos.get('margin', 0):.2f}")
                
                # 🔥🔥 청산가 - 개선된 표시
                liquidation_price = bitget_pos.get('liquidation_price', 0)
                if liquidation_price > 0:
                    current = bitget_pos.get('current_price', 0)
                    side = bitget_pos.get('side')
                    if side == '롱':
                        liq_distance = ((current - liquidation_price) / current * 100)
                    else:
                        liq_distance = ((liquidation_price - current) / current * 100)
                    lines.append(f"• <b>청산가: ${liquidation_price:,.2f}</b> ({abs(liq_distance):.0f}% 거리)")
                else:
                    leverage = bitget_pos.get('leverage', 30)
                    lines.append(f"• <b>청산가: {leverage}x 레버리지</b> (안전 거리 충분)")
            else:
                # 포지션이 없는 경우도 표시
                if gateio_healthy:  # Gate가 있으면 Bitget도 표시
                    lines.append("━━━ <b>Bitget</b> ━━━")
                    lines.append("• 현재 포지션 없음")
        else:
            # API 연결 오류
            lines.append("━━━ <b>Bitget</b> ━━━")
            lines.append("• ⚠️ API 연결 오류")
        
        # Gate 포지션
        if gateio_healthy and gateio_data['total_equity'] > 0:
            gateio_pos = gateio_data['position_info']
            if gateio_pos.get('has_position'):
                has_any_position = True
                if lines:
                    lines.append("")
                lines.append("━━━ <b>Gate</b> ━━━")
                
                roe = gateio_pos.get('roe', 0)
                roe_sign = "+" if roe >= 0 else ""
                
                lines.append(f"• BTC {gateio_pos.get('side')} | 진입: ${gateio_pos.get('entry_price', 0):,.2f} ({roe_sign}{roe:.1f}%)")
                lines.append(f"• 현재가: ${gateio_pos.get('current_price', 0):,.2f} | 증거금: ${gateio_pos.get('margin', 0):.2f}")
                
                # 청산가
                liquidation_price = gateio_pos.get('liquidation_price', 0)
                if liquidation_price > 0:
                    current = gateio_pos.get('current_price', 0)
                    side = gateio_pos.get('side')
                    if side == '롱':
                        liq_distance = ((current - liquidation_price) / current * 100)
                    else:
                        liq_distance = ((liquidation_price - current) / current * 100)
                    lines.append(f"• <b>청산가: ${liquidation_price:,.2f}</b> ({abs(liq_distance):.0f}% 거리)")
            else:
                # 포지션이 없는 경우
                if lines:  # Bitget 정보가 있으면 구분선 추가
                    lines.append("")
                lines.append("━━━ <b>Gate</b> ━━━")
                lines.append("• 현재 포지션 없음")
        
        # 두 거래소 모두 포지션이 없는 경우
        if not has_any_position and not lines:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_asset_detail(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """자산 정보 - 개선된 증거금 표시 + 비율 계산 수정"""
        lines = []
        
        # 🔥🔥 API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 통합 자산 (정상적인 데이터만 사용)
        total_available = combined_data['total_available']
        total_used_margin = combined_data['total_used_margin']  # 🔥🔥 개선된 증거금
        total_equity = combined_data['total_equity']
        
        # 🔥🔥 가용자산 비율 계산 수정 (분모가 0인 경우 방지)
        if total_equity > 0:
            available_pct = (total_available / total_equity * 100)
        else:
            available_pct = 0
        
        # 비율이 비현실적인 경우 (100% 초과) 수정
        if available_pct > 100:
            self.logger.warning(f"⚠️ 가용자산 비율 이상: {available_pct:.0f}%, 100%로 제한")
            available_pct = 100
        
        lines.append(f"• <b>가용/증거금: ${total_available:,.0f} / ${total_used_margin:,.0f}</b> ({available_pct:.0f}% 가용)")
        
        # Bitget 상세 (API 연결 상태에 따라)
        if bitget_healthy:
            bitget_available = bitget_data['available']
            bitget_used_margin = bitget_data['used_margin']  # 🔥🔥 개선된 증거금
            lines.append(f"  ├ Bitget: ${bitget_available:,.0f} / ${bitget_used_margin:,.0f}")
        else:
            lines.append(f"  ├ Bitget: API 연결 오류")
        
        # Gate 상세 (연결 상태에 따라)
        if gateio_healthy and gateio_data['total_equity'] > 0:
            gate_available = gateio_data['available']
            gate_used_margin = gateio_data['used_margin']  # 🔥🔥 개선된 증거금
            lines.append(f"  └ Gate: ${gate_available:,.0f} / ${gate_used_margin:,.0f}")
        elif gateio_has_data:
            lines.append(f"  └ Gate: ${gateio_data['available']:,.0f} / ${gateio_data['used_margin']:,.0f}")
        
        return '\n'.join(lines)
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        """통합 멘탈 케어 생성"""
        try:
            # 멘탈 케어 생성
            account_info = {
                'accountEquity': combined_data['total_equity'],
                'unrealizedPL': combined_data['today_unrealized']
            }
            
            position_info = {
                'has_position': combined_data['total_used_margin'] > 0
            }
            
            weekly_profit = {
                'total': combined_data['weekly_total'],
                'average': combined_data['weekly_avg']
            }
            
            mental_text = await self.mental_care.generate_profit_mental_care(
                account_info, position_info, combined_data['today_position_pnl'], weekly_profit
            )
            
            return mental_text
            
        except Exception as e:
            self.logger.error(f"통합 멘탈 케어 생성 실패: {e}")
            return "시장은 변동성이 클 수 있지만, 꾸준한 전략과 리스크 관리로 좋은 결과를 얻을 수 있습니다. 감정에 휘둘리지 말고 차분하게 대응하세요 💪"
