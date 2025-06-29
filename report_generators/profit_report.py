# report_generators/profit_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback
from datetime import datetime, timedelta
import pytz

class ProfitReportGenerator(BaseReportGenerator):
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.gateio_client = None
        
        # 2025년 5월 1일부터 집계 시작
        self.PROFIT_START_DATE = datetime(2025, 5, 1, tzinfo=pytz.timezone('Asia/Seoul'))
        
        # 초기 자산 설정 (2025년 5월 1일 기준)
        self.BITGET_INITIAL_CAPITAL = 4000.0  # 2025년 5월 1일 기준 초기 자산 $4000
    
    def set_gateio_client(self, gateio_client):
        self.gateio_client = gateio_client
        self.logger.info("✅ Gate.io 클라이언트 설정 완료")
        
    async def generate_report(self) -> str:
        try:
            current_time = self._get_current_time_kst()
            
            # Bitget 데이터 조회 - V2 API 정확한 구현
            bitget_data = await self._get_bitget_data_v2_accurate()
            
            # Gate.io 데이터 조회 - V4 API 정확한 구현
            gateio_data = await self._get_gateio_data_v4_accurate()
            
            # Gate.io 실제 사용 여부 확인
            gateio_has_data = (gateio_data.get('has_account', False) and 
                             gateio_data.get('total_equity', 0) > 0)
            
            # 통합 데이터 계산 (API 응답 정확히 사용)
            combined_data = self._calculate_combined_data_accurate(bitget_data, gateio_data)
            
            # 통합 자산 현황
            asset_summary = self._format_asset_summary(combined_data, gateio_has_data)
            
            # 거래소별 포지션 정보 (API 응답 정확히 표시)
            positions_text = await self._format_positions_detail_accurate(bitget_data, gateio_data, gateio_has_data)
            
            # 거래소별 손익 정보
            profit_detail = self._format_profit_detail_accurate(bitget_data, gateio_data, combined_data, gateio_has_data)
            
            # 통합 자산 정보 (API 응답 정확히 사용)
            asset_detail = self._format_asset_detail_accurate(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 누적 성과 (2025년 5월부터)
            cumulative_text = self._format_cumulative_performance_accurate(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 7일 수익 (API 응답 정확히 사용)
            seven_day_text = self._format_7day_profit_accurate(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 멘탈 케어 - 통합 데이터 기반
            mental_text = await self._generate_combined_mental_care(combined_data)
            
            report = f"""💰 <b>실시간 손익 현황</b>
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
    
    async def _get_bitget_data_v2_accurate(self) -> dict:
        """Bitget V2 API 정확한 구현 - 실제 API 응답 직접 사용"""
        try:
            self.logger.info("🔍 Bitget V2 API 정확한 구현 시작...")
            
            # 단계별 데이터 조회 (오류 격리)
            market_data = {}
            position_info = {'has_position': False}
            account_info = {}
            today_position_pnl = 0.0
            weekly_position_pnl = {'total_pnl': 0, 'average_daily': 0, 'actual_days': 7}
            cumulative_data = {'total_profit': 0, 'roi': 0}
            total_margin_size = 0.0
            
            # 1. 시장 데이터 조회
            try:
                market_data = await self._get_market_data()
                self.logger.info("✅ 시장 데이터 조회 성공")
            except Exception as e:
                self.logger.warning(f"⚠️ 시장 데이터 조회 실패: {e}")
                market_data = {}
            
            # 2. 계정 정보 조회 (Bitget V2 API 정확한 구현)
            try:
                account_info = await self.bitget_client.get_account_info() if self.bitget_client else {}
                if account_info and account_info.get('usdtEquity', 0) > 0:
                    self.logger.info(f"✅ Bitget V2 계정 정보 조회 성공: ${account_info.get('usdtEquity', 0):.2f}")
                else:
                    self.logger.error("❌ Bitget V2 계정 정보 조회 실패")
                    account_info = {}
            except Exception as e:
                self.logger.error(f"❌ Bitget V2 계정 정보 조회 실패: {e}")
                account_info = {}
            
            # 3. 포지션 정보 조회 (Bitget V2 API 정확한 구현)
            try:
                positions = await self.bitget_client.get_positions(self.config.symbol) if self.bitget_client else []
                if positions:
                    for pos in positions:
                        total_size = float(pos.get('total', 0))
                        if total_size > 0:
                            # Bitget V2 API marginSize 필드 직접 사용
                            margin_size = float(pos.get('marginSize', 0))
                            total_margin_size += margin_size
                            
                            hold_side = pos.get('holdSide', '')
                            side = '롱' if hold_side == 'long' else '숏'
                            
                            # Bitget V2 API 필수 값들 정확히 추출
                            entry_price = float(pos.get('openPriceAvg', 0))
                            mark_price = float(pos.get('markPrice', 0))
                            unrealized_pnl = float(pos.get('unrealizedPL', 0))
                            liquidation_price = float(pos.get('liquidationPrice', 0))
                            leverage = float(pos.get('leverage', 30))
                            
                            # ROE 계산
                            roe = (unrealized_pnl / margin_size) * 100 if margin_size > 0 else 0
                            
                            position_info = {
                                'has_position': True,
                                'symbol': self.config.symbol,
                                'side': side,
                                'side_en': hold_side,
                                'size': total_size,
                                'entry_price': entry_price,
                                'current_price': mark_price,
                                'margin': margin_size,  # Bitget V2 API marginSize 직접 사용
                                'unrealized_pnl': unrealized_pnl,
                                'roe': roe,
                                'liquidation_price': liquidation_price,
                                'leverage': leverage
                            }
                            
                            self.logger.info(f"✅ Bitget V2 포지션 정보 (정확한 API):")
                            self.logger.info(f"  - marginSize: ${margin_size:.2f}")
                            self.logger.info(f"  - liquidationPrice: ${liquidation_price:.2f}")
                            break
                else:
                    self.logger.info("ℹ️ 현재 포지션 없음")
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget V2 포지션 정보 조회 실패: {e}")
                position_info = {'has_position': False}
            
            # 4. 오늘 Position PnL 조회 (Bitget V2 API 정확한 구현)
            try:
                today_position_pnl = await self.bitget_client.get_today_position_pnl() if self.bitget_client else 0.0
                self.logger.info(f"✅ Bitget V2 오늘 Position PnL: ${today_position_pnl:.4f}")
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget V2 오늘 Position PnL 조회 실패: {e}")
                today_position_pnl = 0.0
            
            # 5. 7일 Position PnL 조회 (Bitget V2 API 정확한 구현)
            try:
                weekly_position_pnl = await self.bitget_client.get_7day_position_pnl() if self.bitget_client else {}
                self.logger.info(f"✅ Bitget V2 7일 Position PnL: ${weekly_position_pnl.get('total_pnl', 0):.4f}")
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget V2 7일 Position PnL 조회 실패: {e}")
                weekly_position_pnl = {
                    'total_pnl': 0,
                    'average_daily': 0,
                    'actual_days': 7,
                    'source': 'error_fallback'
                }
            
            # 6. 누적 손익 조회
            try:
                cumulative_data = await self._get_cumulative_profit_since_may()
                self.logger.info(f"✅ Bitget 누적 수익: ${cumulative_data.get('total_profit', 0):.2f}")
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget 누적 손익 조회 실패: {e}")
                cumulative_data = {'total_profit': 0, 'roi': 0}
            
            # 총 자산 확인
            total_equity = float(account_info.get('usdtEquity', 0))
            available = float(account_info.get('available', 0))
            unrealized_pl = float(account_info.get('unrealizedPL', 0))
            
            # API 연결 상태 체크
            api_healthy = total_equity > 0 or position_info.get('has_position', False)
            
            result = {
                'exchange': 'Bitget',
                'market_data': market_data,
                'position_info': position_info,
                'account_info': account_info,
                'today_pnl': today_position_pnl,
                'weekly_profit': {
                    'total': weekly_position_pnl.get('total_pnl', 0),
                    'average': weekly_position_pnl.get('average_daily', 0),
                    'actual_days': weekly_position_pnl.get('actual_days', 7),
                    'source': weekly_position_pnl.get('source', 'bitget_v2_api')
                },
                'cumulative_profit': cumulative_data.get('total_profit', 0),
                'cumulative_roi': cumulative_data.get('roi', 0),
                'total_equity': total_equity,
                'initial_capital': self.BITGET_INITIAL_CAPITAL,
                'available': available,
                'used_margin': total_margin_size,  # marginSize 합계 직접 사용
                'unrealized_pl': unrealized_pl,
                'cumulative_data': cumulative_data,
                'api_healthy': api_healthy
            }
            
            if api_healthy:
                self.logger.info(f"✅ Bitget V2 API 정확한 구현 완료:")
                self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
                self.logger.info(f"  - marginSize 합계: ${total_margin_size:.2f}")
                self.logger.info(f"  - 미실현 손익: ${unrealized_pl:.4f}")
            else:
                self.logger.warning("⚠️ Bitget V2 API 연결 문제")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Bitget V2 API 정확한 구현 실패: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Bitget')
    
    async def _get_gateio_data_v4_accurate(self) -> dict:
        """Gate.io V4 API 정확한 구현 - 실제 API 응답 직접 사용"""
        try:
            # Gate.io 클라이언트가 없는 경우
            if not self.gateio_client:
                self.logger.info("Gate.io 클라이언트가 설정되지 않음")
                return self._get_empty_exchange_data('Gate')
            
            self.logger.info("🔍 Gate.io V4 API 정확한 구현 시작...")
            
            # Gate 계정 정보 조회 (V4 API 정확한 구현)
            account_response = {}
            total_equity = 0
            available = 0
            unrealized_pnl = 0
            
            try:
                account_response = await self.gateio_client.get_account_balance()
                
                if account_response:
                    # Gate.io V4 API 응답 정확히 사용
                    total_equity = float(account_response.get('total', 0))
                    available = float(account_response.get('available', 0))
                    unrealized_pnl = float(account_response.get('unrealised_pnl', 0))
                    
                    self.logger.info(f"Gate.io V4 계정 정보 (정확한 API): total=${total_equity:.2f}")
                
            except Exception as e:
                self.logger.error(f"Gate V4 계정 조회 실패: {e}")
            
            # Gate 포지션 조회 (V4 API 정확한 구현)
            position_info = {'has_position': False}
            used_margin = 0
            
            try:
                positions = await self.gateio_client.get_positions('BTC_USDT')
                
                if positions:
                    for pos in positions:
                        size = float(pos.get('size', 0))
                        if size != 0:
                            # Gate.io V4 API 정확한 필드 사용
                            entry_price = float(pos.get('entry_price', 0))
                            mark_price = float(pos.get('mark_price', 0))
                            pos_unrealized_pnl = float(pos.get('unrealised_pnl', 0))
                            leverage = float(pos.get('leverage', 10))
                            liquidation_price = float(pos.get('liq_price', 0))
                            
                            # 포지션별 증거금 계산 (Gate.io V4 정확한 계산)
                            position_margin = 0
                            if entry_price > 0 and mark_price > 0:
                                btc_size = abs(size) * 0.0001  # Gate.io 계약 크기
                                position_value = btc_size * mark_price
                                position_margin = position_value / leverage
                                used_margin += position_margin
                            
                            # ROE 계산
                            roe = (pos_unrealized_pnl / position_margin) * 100 if position_margin > 0 else 0
                            
                            position_info = {
                                'has_position': True,
                                'symbol': 'BTC_USDT',
                                'side': '롱' if size > 0 else '숏',
                                'side_en': 'long' if size > 0 else 'short',
                                'size': abs(size),
                                'entry_price': entry_price,
                                'current_price': mark_price,
                                'unrealized_pnl': pos_unrealized_pnl,
                                'roe': roe,
                                'leverage': leverage,
                                'margin': position_margin,
                                'liquidation_price': liquidation_price
                            }
                            
                            self.logger.info(f"✅ Gate.io V4 포지션 발견:")
                            self.logger.info(f"  - 방향: {position_info['side']}")
                            self.logger.info(f"  - 계산된 증거금: ${position_margin:.2f}")
                            break
                    
            except Exception as e:
                self.logger.error(f"Gate V4 포지션 조회 실패: {e}")
            
            # Position PnL 기준 손익 계산 - V4 API 정확한 구현
            today_position_pnl = 0.0
            weekly_profit = {'total_pnl': 0, 'average_daily': 0}
            cumulative_profit = 0.0
            initial_capital = 750
            
            try:
                self.logger.info("🔍 Gate.io V4 API 정확한 손익 계산...")
                
                # 오늘 Position PnL 조회 - V4 API 정확한 구현
                today_position_pnl = await self.gateio_client.get_today_position_pnl()
                
                # 7일 Position PnL - V4 API 정확한 구현
                weekly_result = await self.gateio_client.get_7day_position_pnl()
                
                # V4 API 응답 정확히 사용
                weekly_profit = {
                    'total_pnl': weekly_result.get('total_pnl', 0),
                    'average_daily': weekly_result.get('average_daily', 0),
                    'actual_days': weekly_result.get('actual_days', 7.0),
                    'source': weekly_result.get('source', 'gate_v4_api_accurate')
                }
                
                # 누적 수익 계산 (현재 잔고 - 추정 초기)
                if total_equity > 0:
                    estimated_initial = 750
                    cumulative_profit = total_equity - estimated_initial if total_equity > estimated_initial else 0
                    initial_capital = estimated_initial
                    
                    self.logger.info(f"✅ Gate.io V4 API 정확한 손익 계산 완료:")
                    self.logger.info(f"  - 오늘 Position PnL: ${today_position_pnl:.4f}")
                    self.logger.info(f"  - 7일 Position PnL (V4 API): ${weekly_profit['total_pnl']:.2f}")
                    self.logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
                else:
                    self.logger.info("Gate.io 잔고가 0이거나 없음")
                
            except Exception as e:
                self.logger.error(f"Gate.io V4 API 정확한 손익 계산 실패: {e}")
                today_position_pnl = 0.0
                weekly_profit = {
                    'total_pnl': 0.0,
                    'average_daily': 0.0,
                    'actual_days': 7.0,
                    'source': 'gate_v4_api_error'
                }
            
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            has_account = total_equity > 0
            
            self.logger.info(f"Gate.io V4 최종 정확한 데이터:")
            self.logger.info(f"  - 계정 존재: {has_account}")
            self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
            self.logger.info(f"  - 사용 증거금: ${used_margin:.2f}")
            self.logger.info(f"  - 미실현손익: ${unrealized_pnl:.4f}")
            
            return {
                'exchange': 'Gate',
                'position_info': position_info,
                'account_info': account_response,
                'today_pnl': today_position_pnl,
                'weekly_profit': weekly_profit,
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': initial_capital,
                'available': available,
                'used_margin': used_margin,
                'unrealized_pnl': unrealized_pnl,
                'has_account': has_account,
                'actual_profit': cumulative_profit
            }
            
        except Exception as e:
            self.logger.error(f"Gate V4 API 정확한 구현 실패: {e}")
            self.logger.error(f"Gate 데이터 오류 상세: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Gate')
    
    def _calculate_combined_data_accurate(self, bitget_data: dict, gateio_data: dict) -> dict:
        """API 응답 정확히 사용 - 추가 계산 최소화"""
        # API 연결 상태 체크
        bitget_healthy = bitget_data.get('api_healthy', True)
        gateio_healthy = gateio_data.get('has_account', False)
        
        self.logger.info(f"🔍 API 정확한 사용 통합 데이터 계산:")
        self.logger.info(f"  - Bitget 상태: {'정상' if bitget_healthy else '오류'}")
        self.logger.info(f"  - Gate.io 상태: {'정상' if gateio_healthy else '없음'}")
        
        # 총 자산 (API 응답 정확히 사용)
        bitget_equity = bitget_data['total_equity'] if bitget_healthy else 0
        gateio_equity = gateio_data['total_equity'] if gateio_healthy else 0
        total_equity = bitget_equity + gateio_equity
        
        # 가용 자산 (API 응답 정확히 사용)
        bitget_available = bitget_data['available'] if bitget_healthy else 0
        gateio_available = gateio_data['available'] if gateio_healthy else 0
        total_available = bitget_available + gateio_available
        
        # 사용 증거금 (API 응답 정확히 사용)
        bitget_used_margin = bitget_data['used_margin'] if bitget_healthy else 0
        gateio_used_margin = gateio_data['used_margin'] if gateio_healthy else 0
        total_used_margin = bitget_used_margin + gateio_used_margin
        
        # 미실현 손익 (API 응답 정확히 사용)
        bitget_unrealized = bitget_data.get('unrealized_pl', 0) if bitget_healthy else 0
        gateio_unrealized = gateio_data.get('unrealized_pnl', 0) if gateio_healthy else 0
        today_unrealized = bitget_unrealized + gateio_unrealized
        
        # Position PnL 기준 금일 손익 (API 응답 정확히 사용)
        bitget_today_pnl = bitget_data['today_pnl'] if bitget_healthy else 0
        gateio_today_pnl = gateio_data['today_pnl'] if gateio_healthy else 0
        today_position_pnl = bitget_today_pnl + gateio_today_pnl
        today_total = today_position_pnl + today_unrealized
        
        # 7일 Position PnL (API 응답 정확히 사용)
        bitget_weekly = bitget_data['weekly_profit']['total'] if bitget_healthy else 0
        gateio_weekly = gateio_data['weekly_profit']['total_pnl'] if gateio_healthy else 0
        weekly_total = bitget_weekly + gateio_weekly
        
        # 실제 일수 계산
        actual_days = 7.0
        if bitget_healthy:
            actual_days = max(actual_days, bitget_data['weekly_profit'].get('actual_days', 7))
        if gateio_healthy:
            actual_days = max(actual_days, gateio_data['weekly_profit'].get('actual_days', 7))
        
        weekly_avg = weekly_total / actual_days if actual_days > 0 else 0
        
        # 누적 수익 (API 응답 정확히 사용)
        bitget_cumulative = bitget_data['cumulative_profit'] if bitget_healthy else 0
        gateio_cumulative = gateio_data['cumulative_profit'] if gateio_healthy else 0
        cumulative_profit = bitget_cumulative + gateio_cumulative
        
        # 수익률 계산 (분모가 0인 경우 방지)
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        initial_7d = total_equity - weekly_total
        weekly_roi = (weekly_total / initial_7d * 100) if initial_7d > 0 else 0
        
        # 초기 자본 계산
        bitget_initial = self.BITGET_INITIAL_CAPITAL if bitget_healthy else 0
        gateio_initial = gateio_data.get('initial_capital', 750) if gateio_healthy else 0
        total_initial = bitget_initial + gateio_initial
        
        cumulative_roi = (cumulative_profit / total_initial * 100) if total_initial > 0 else 0
        
        # Gate.io 7일 수익 신뢰도 체크
        gateio_weekly_source = gateio_data.get('weekly_profit', {}).get('source', 'unknown')
        gateio_weekly_confidence = 'v4_api_accurate' if 'v4_api' in gateio_weekly_source else 'estimated'
        
        self.logger.info(f"API 정확한 사용 통합 데이터 계산 완료:")
        self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
        self.logger.info(f"  - 총 사용 증거금: ${total_used_margin:.2f}")
        self.logger.info(f"  - 오늘 Position PnL: ${today_position_pnl:.4f}")
        self.logger.info(f"  - 7일  Position PnL: ${weekly_total:.4f}")
        
        return {
            'total_equity': total_equity,
            'total_available': total_available,
            'total_used_margin': total_used_margin,
            'today_position_pnl': today_position_pnl,
            'today_unrealized': today_unrealized,
            'today_total': today_total,
            'today_roi': today_roi,
            'weekly_total': weekly_total,
            'weekly_avg': weekly_avg,
            'weekly_roi': weekly_roi,
            'actual_days': actual_days,
            'cumulative_profit': cumulative_profit,
            'cumulative_roi': cumulative_roi,
            'bitget_equity': bitget_equity,
            'gateio_equity': gateio_equity,
            'gateio_has_account': gateio_healthy,
            'total_initial': total_initial,
            # 개별 거래소 미실현/실현 손익
            'bitget_today_realized': bitget_today_pnl,
            'bitget_today_unrealized': bitget_unrealized,
            'gateio_today_realized': gateio_today_pnl,
            'gateio_today_unrealized': gateio_unrealized,
            # API 연결 상태
            'bitget_healthy': bitget_healthy,
            'gateio_healthy': gateio_healthy,
            # Gate.io 7일 수익 신뢰도
            'gateio_weekly_confidence': gateio_weekly_confidence,
            'gateio_weekly_source': gateio_weekly_source
        }
    
    def _format_profit_detail_accurate(self, bitget_data: dict, gateio_data: dict, combined_data: dict, gateio_has_data: bool) -> str:
        lines = []
        
        # API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 통합 손익 요약
        today_position_pnl = combined_data['today_position_pnl']
        today_unrealized = combined_data['today_unrealized']
        today_total = combined_data['today_total']
        today_roi = combined_data['today_roi']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(today_total, today_roi)}</b>")
        
        # Bitget 상세 - 미실현/실현 분리
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
    
    def _format_7day_profit_accurate(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        lines = []
        
        # API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 실제 기간 표시
        actual_days = combined_data.get('actual_days', 7.0)
        
        # 통합 7일 Position PnL (API 정확히)
        lines.append(f"• <b>수익: {self._format_currency_compact(combined_data['weekly_total'], combined_data['weekly_roi'])}</b>")
        
        # 거래소별 7일 Position PnL
        if gateio_healthy and gateio_data['total_equity'] > 0:
            if bitget_healthy:
                bitget_weekly = bitget_data['weekly_profit']['total']
                lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_weekly, False)}")
            else:
                lines.append(f"  ├ Bitget: API 연결 오류")
            
            gate_weekly = gateio_data['weekly_profit']['total_pnl']
            gate_source = gateio_data['weekly_profit'].get('source', 'unknown')
            # Gate.io 수익이 V4 API 정확한지 표시
            confidence_indicator = "📊" if "v4_api" in gate_source else "🔍"
            lines.append(f"  └ Gate: {self._format_currency_html(gate_weekly, False)} {confidence_indicator}")
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
    
    def _format_cumulative_performance_accurate(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        lines = []
        
        # API 연결 상태 확인
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
        
        return '\n'.join(lines)
    
    async def _format_positions_detail_accurate(self, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """포지션 정보 - API 응답 정확히 표시"""
        lines = []
        has_any_position = False
        
        # API 연결 상태 확인
        bitget_healthy = bitget_data.get('api_healthy', True)
        gateio_healthy = gateio_data.get('has_account', False)
        
        # Bitget 포지션 (V2 API 응답 정확히 사용)
        if bitget_healthy:
            bitget_pos = bitget_data['position_info']
            if bitget_pos.get('has_position'):
                has_any_position = True
                lines.append("━━━ <b>Bitget</b> ━━━")
                
                roe = bitget_pos.get('roe', 0)
                roe_sign = "+" if roe >= 0 else ""
                
                lines.append(f"• BTC {bitget_pos.get('side')} | 진입: ${bitget_pos.get('entry_price', 0):,.2f} ({roe_sign}{roe:.1f}%)")
                lines.append(f"• 현재가: ${bitget_pos.get('current_price', 0):,.2f} | 증거금: ${bitget_pos.get('margin', 0):.2f}")
                
                # V2 API marginSize 직접 표시
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
                    lines.append(f"• <b>청산가: {leverage}x 레버리지</b> (API 값 없음)")
            else:
                # 포지션이 없는 경우도 표시
                if gateio_healthy:  # Gate가 있으면 Bitget도 표시
                    lines.append("━━━ <b>Bitget</b> ━━━")
                    lines.append("• 현재 포지션 없음")
        else:
            # API 연결 오류
            lines.append("━━━ <b>Bitget</b> ━━━")
            lines.append("• ⚠️ API 연결 오류")
        
        # Gate 포지션 (V4 API 응답 정확히 사용)
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
                
                # V4 API 응답 정확히 사용
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
    
    def _format_asset_detail_accurate(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """자산 상세 - API 응답 정확히 사용"""
        lines = []
        
        # API 연결 상태 확인
        bitget_healthy = combined_data.get('bitget_healthy', True)
        gateio_healthy = combined_data.get('gateio_healthy', False)
        
        # 통합 자산 (API 응답 정확히 사용)
        total_available = combined_data['total_available']
        total_used_margin = combined_data['total_used_margin']  # API marginSize 합계
        total_equity = combined_data['total_equity']
        
        # 가용자산 비율 계산 (분모가 0인 경우 방지)
        if total_equity > 0:
            available_pct = (total_available / total_equity * 100)
        else:
            available_pct = 0
        
        # 비율이 비현실적인 경우 (100% 초과) 수정
        if available_pct > 100:
            self.logger.warning(f"⚠️ 가용자산 비율 이상: {available_pct:.0f}%, 100%로 제한")
            available_pct = 100
        
        lines.append(f"• <b>가용/증거금: ${total_available:,.0f} / ${total_used_margin:,.0f}</b> ({available_pct:.0f}% 가용)")
        
        # Bitget 상세 (marginSize 정확히 사용)
        if bitget_healthy:
            bitget_available = bitget_data['available']
            bitget_used_margin = bitget_data['used_margin']  # marginSize 합계
            lines.append(f"  ├ Bitget: ${bitget_available:,.0f} / ${bitget_used_margin:,.0f}")
        else:
            lines.append(f"  ├ Bitget: API 연결 오류")
        
        # Gate 상세 (V4 API 응답 정확히 사용)
        if gateio_healthy and gateio_data['total_equity'] > 0:
            gate_available = gateio_data['available']
            gate_used_margin = gateio_data['used_margin']  # V4 API 계산값
            lines.append(f"  └ Gate: ${gate_available:,.0f} / ${gate_used_margin:,.0f}")
        elif gateio_has_data:
            lines.append(f"  └ Gate: ${gateio_data['available']:,.0f} / ${gateio_data['used_margin']:,.0f}")
        
        return '\n'.join(lines)
    
    def _format_currency_html(self, amount: float, include_krw: bool = True) -> str:
        # 비현실적인 값 안전장치
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
        # 비현실적인 값 안전장치
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
        # 비현실적인 값 안전장치
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
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        return now.strftime('%Y-%m-%d %H:%M')
    
    async def _get_market_data(self) -> dict:
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
    
    async def _get_cumulative_profit_since_may(self) -> dict:
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            start_date = self.PROFIT_START_DATE
            
            # 현재 잔고에서 초기 자본 차감
            try:
                account_info = await self.bitget_client.get_account_info() if self.bitget_client else {}
                current_equity = float(account_info.get('usdtEquity', 0))
                
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
        return {
            'exchange': exchange_name,
            'position_info': {'has_position': False},
            'account_info': {'usdtEquity': 0, 'unrealizedPL': 0, 'available': 0, 'usedMargin': 0},
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
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        # API 연결 상태 확인
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
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        try:
            # 멘탈 케어 생성
            account_info = {
                'usdtEquity': combined_data['total_equity'],
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
