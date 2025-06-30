from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback
import asyncio
from datetime import datetime, timedelta
import pytz

class ProfitReportGenerator(BaseReportGenerator):
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.gateio_client = None
        
        # 2025년 5월 1일부터 집계 시작 (참고용)
        self.PROFIT_START_DATE = datetime(2025, 5, 1, tzinfo=pytz.timezone('Asia/Seoul'))
    
    def set_gateio_client(self, gateio_client):
        self.gateio_client = gateio_client
        self.logger.info("✅ Gate.io 클라이언트 설정 완료")
        
    async def generate_report(self) -> str:
        try:
            current_time = self._get_current_time_kst()
            
            # Bitget 데이터 조회 - 개선된 API 연결 체크
            bitget_data = await self._get_bitget_data_robust()
            
            # Gate.io 데이터 조회 - 개선된 API 연결 체크
            gateio_data = await self._get_gateio_data_robust()
            
            # 데이터 유효성 검증
            bitget_healthy = self._validate_bitget_data(bitget_data)
            gateio_healthy = self._validate_gateio_data(gateio_data)
            
            # 통합 데이터 계산 - 순수 수익 기반
            combined_data = self._calculate_combined_data_pure_profit(bitget_data, gateio_data, bitget_healthy, gateio_healthy)
            
            # 리포트 구성
            asset_summary = self._format_asset_summary_robust(combined_data, bitget_healthy, gateio_healthy)
            positions_text = await self._format_positions_detail_robust(bitget_data, gateio_data, bitget_healthy, gateio_healthy)
            profit_detail = self._format_profit_detail_robust(bitget_data, gateio_data, combined_data, bitget_healthy, gateio_healthy)
            asset_detail = self._format_asset_detail_robust(combined_data, bitget_data, gateio_data, bitget_healthy, gateio_healthy)
            cumulative_text = self._format_cumulative_performance_robust(combined_data, bitget_data, gateio_data, bitget_healthy, gateio_healthy)
            seven_day_text = self._format_7day_profit_robust(combined_data, bitget_data, gateio_data, bitget_healthy, gateio_healthy)
            
            # 멘탈 케어
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

📊 <b>누적 성과 (순수익 기준)</b>
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
    
    async def _get_bitget_data_robust(self) -> dict:
        try:
            self.logger.info("🔍 Bitget 데이터 조회 시작 (순수 수익 계산)")
            
            # API 연결 상태 사전 체크
            if not self.bitget_client:
                self.logger.error("❌ Bitget 클라이언트가 없음")
                return self._get_empty_bitget_data()
            
            if not self.bitget_client.api_keys_validated:
                self.logger.warning("⚠️ Bitget API 키 검증되지 않음")
                await self.bitget_client._validate_api_keys()
            
            # 단계별 데이터 수집 (각각 독립적으로 처리)
            market_data = {}
            account_info = {}
            position_info = {'has_position': False}
            today_pnl = 0.0
            weekly_profit = {'total_pnl': 0, 'average_daily': 0, 'actual_days': 7}
            cumulative_data = {'total_profit': 0, 'roi': 0}
            used_margin = 0.0
            
            # 1. 시장 데이터 (티커/펀딩비)
            try:
                market_data = await self._get_market_data_safe()
            except Exception as e:
                self.logger.warning(f"⚠️ 시장 데이터 조회 실패: {e}")
                market_data = {'current_price': 0, 'funding_rate': 0}
            
            # 2. 계정 정보 (재시도 로직 포함)
            for attempt in range(3):
                try:
                    account_info = await self.bitget_client.get_account_info()
                    if account_info and float(account_info.get('usdtEquity', 0)) > 0:
                        self.logger.info(f"✅ Bitget 계정 정보 조회 성공 (시도 {attempt + 1})")
                        break
                    elif attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    else:
                        self.logger.error("❌ Bitget 계정 정보가 비어있음")
                        account_info = {}
                except Exception as e:
                    self.logger.warning(f"⚠️ Bitget 계정 조회 실패 (시도 {attempt + 1}): {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    else:
                        account_info = {}
            
            # 3. 포지션 정보
            try:
                positions = await self.bitget_client.get_positions(self.config.symbol)
                used_margin = await self.bitget_client.get_accurate_used_margin()
                
                if positions:
                    for pos in positions:
                        total_size = float(pos.get('total', 0))
                        if total_size > 0:
                            hold_side = pos.get('holdSide', '')
                            side = '롱' if hold_side == 'long' else '숏'
                            
                            position_info = {
                                'has_position': True,
                                'symbol': self.config.symbol,
                                'side': side,
                                'side_en': hold_side,
                                'size': total_size,
                                'entry_price': float(pos.get('openPriceAvg', 0)),
                                'current_price': float(pos.get('markPrice', 0)),
                                'margin': float(pos.get('marginSize', 0)),
                                'unrealized_pnl': float(pos.get('unrealizedPL', 0)),
                                'roe': 0,  # 나중에 계산
                                'liquidation_price': float(pos.get('liquidationPrice', 0)),
                                'leverage': float(pos.get('leverage', 30))
                            }
                            
                            # ROE 계산
                            if position_info['margin'] > 0:
                                position_info['roe'] = (position_info['unrealized_pnl'] / position_info['margin']) * 100
                            
                            break
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget 포지션 조회 실패: {e}")
                position_info = {'has_position': False}
                used_margin = 0.0
            
            # 4. 오늘 PnL
            try:
                today_pnl = await self.bitget_client.get_today_position_pnl()
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget 오늘 PnL 조회 실패: {e}")
                today_pnl = 0.0
            
            # 5. 7일 PnL
            try:
                weekly_profit = await self.bitget_client.get_7day_position_pnl()
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget 7일 PnL 조회 실패: {e}")
                weekly_profit = {'total_pnl': 0, 'average_daily': 0, 'actual_days': 7}
            
            # 6. 누적 손익 - Position PnL 기반으로 계산
            try:
                cumulative_data = await self._get_cumulative_profit_position_based('bitget')
            except Exception as e:
                self.logger.warning(f"⚠️ Bitget 누적 손익 조회 실패: {e}")
                cumulative_data = {'total_profit': 0, 'roi': 0}
            
            # 자산 정보 추출
            total_equity = float(account_info.get('usdtEquity', 0))
            available = float(account_info.get('available', 0))
            unrealized_pl = float(account_info.get('unrealizedPL', 0))
            
            # API 건강성 체크
            api_healthy = (total_equity > 0 or position_info.get('has_position', False))
            
            result = {
                'exchange': 'Bitget',
                'market_data': market_data,
                'position_info': position_info,
                'account_info': account_info,
                'today_pnl': today_pnl,
                'weekly_profit': {
                    'total': weekly_profit.get('total_pnl', 0),
                    'average': weekly_profit.get('average_daily', 0),
                    'actual_days': weekly_profit.get('actual_days', 7),
                    'source': weekly_profit.get('source', 'bitget_v2_api')
                },
                'cumulative_profit': cumulative_data.get('total_profit', 0),
                'cumulative_roi': cumulative_data.get('roi', 0),
                'total_equity': total_equity,
                'available': available,
                'used_margin': used_margin,
                'unrealized_pl': unrealized_pl,
                'cumulative_data': cumulative_data,
                'api_healthy': api_healthy
            }
            
            self.logger.info(f"✅ Bitget 데이터 조회 완료:")
            self.logger.info(f"  - API 건강성: {api_healthy}")
            self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
            self.logger.info(f"  - 사용 증거금: ${used_margin:.2f}")
            self.logger.info(f"  - 누적 순수익: ${cumulative_data.get('total_profit', 0):.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Bitget 데이터 조회 실패: {e}")
            return self._get_empty_bitget_data()
    
    async def _get_gateio_data_robust(self) -> dict:
        try:
            if not self.gateio_client:
                self.logger.info("Gate.io 클라이언트가 설정되지 않음")
                return self._get_empty_gateio_data()
            
            self.logger.info("🔍 Gate.io 데이터 조회 시작 (순수 수익 계산)")
            
            # 계정 정보 조회 (재시도 로직)
            account_response = {}
            for attempt in range(3):
                try:
                    account_response = await self.gateio_client.get_account_balance()
                    if account_response and float(account_response.get('total', 0)) > 0:
                        self.logger.info(f"✅ Gate.io 계정 조회 성공 (시도 {attempt + 1})")
                        break
                    elif attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    else:
                        self.logger.info("Gate.io 계정이 비어있거나 없음")
                        account_response = {}
                except Exception as e:
                    self.logger.warning(f"⚠️ Gate.io 계정 조회 실패 (시도 {attempt + 1}): {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    else:
                        account_response = {}
            
            total_equity = float(account_response.get('total', 0))
            available = float(account_response.get('available', 0))
            unrealized_pnl = float(account_response.get('unrealised_pnl', 0))
            
            # 포지션 조회
            position_info = {'has_position': False}
            used_margin = 0
            
            if total_equity > 0:
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
                                liquidation_price = float(pos.get('liq_price', 0))
                                
                                # 포지션별 증거금 계산
                                if entry_price > 0 and mark_price > 0:
                                    btc_size = abs(size) * 0.0001
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
                                break
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ Gate.io 포지션 조회 실패: {e}")
            
            # Position PnL 기반 손익 계산 - 강화된 재시도 로직
            today_position_pnl = 0.0
            weekly_profit = {'total_pnl': 0, 'average_daily': 0, 'actual_days': 7.0}
            
            if total_equity > 0:
                try:
                    # 오늘 PnL 조회 - 재시도 로직 추가
                    for attempt in range(2):
                        try:
                            today_position_pnl = await self.gateio_client.get_today_position_pnl()
                            if today_position_pnl != 0:
                                break
                            elif attempt == 0:
                                await asyncio.sleep(1)
                        except Exception as e:
                            self.logger.warning(f"Gate.io 오늘 PnL 조회 시도 {attempt + 1} 실패: {e}")
                            if attempt == 0:
                                await asyncio.sleep(1)
                    
                    # 7일 PnL 조회 - 다중 방식 시도
                    weekly_profit = await self._get_gateio_7day_profit_multiple_methods()
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Gate.io Position PnL 계산 실패: {e}")
            
            # 누적 수익 계산 - Position PnL 기반
            cumulative_data = await self._get_cumulative_profit_position_based('gateio')
            
            has_account = total_equity > 0
            
            result = {
                'exchange': 'Gate',
                'position_info': position_info,
                'account_info': account_response,
                'today_pnl': today_position_pnl,
                'weekly_profit': weekly_profit,
                'cumulative_profit': cumulative_data.get('total_profit', 0),
                'cumulative_roi': cumulative_data.get('roi', 0),
                'total_equity': total_equity,
                'available': available,
                'used_margin': used_margin,
                'unrealized_pnl': unrealized_pnl,
                'has_account': has_account,
                'actual_profit': cumulative_data.get('total_profit', 0)
            }
            
            self.logger.info(f"✅ Gate.io 데이터 조회 완료:")
            self.logger.info(f"  - 계정 존재: {has_account}")
            self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
            self.logger.info(f"  - 7일 PnL: ${weekly_profit['total_pnl']:.2f} (거래: {weekly_profit.get('trade_count', 0)}건)")
            self.logger.info(f"  - 누적 순수익: ${cumulative_data.get('total_profit', 0):.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Gate.io 데이터 조회 실패: {e}")
            return self._get_empty_gateio_data()
    
    async def _get_gateio_7day_profit_multiple_methods(self) -> dict:
        """Gate.io 7일 수익 다중 방식 시도"""
        try:
            self.logger.info("🔍 Gate.io 7일 수익 다중 방식 조회 시작")
            
            # 방법 1: 기존 7일 PnL 조회 (재시도 강화)
            for attempt in range(3):
                try:
                    weekly_result = await self.gateio_client.get_7day_position_pnl()
                    
                    if weekly_result and weekly_result.get('trade_count', 0) > 0:
                        self.logger.info(f"✅ 방법1 성공 (시도 {attempt + 1}): ${weekly_result.get('total_pnl', 0):.2f}")
                        return {
                            'total_pnl': weekly_result.get('total_pnl', 0),
                            'average_daily': weekly_result.get('average_daily', 0),
                            'actual_days': weekly_result.get('actual_days', 7.0),
                            'trade_count': weekly_result.get('trade_count', 0),
                            'source': f"method1_attempt{attempt+1}",
                            'confidence': 'high'
                        }
                    elif attempt < 2:
                        self.logger.warning(f"방법1 시도 {attempt + 1} 실패 - 재시도")
                        await asyncio.sleep(3)
                        continue
                        
                except Exception as e:
                    self.logger.warning(f"방법1 시도 {attempt + 1} 오류: {e}")
                    if attempt < 2:
                        await asyncio.sleep(3)
                        continue
            
            # 방법 2: 더 넓은 범위로 거래 내역 조회 (14일)
            try:
                self.logger.info("🔍 방법2: 14일 범위로 거래 내역 조회")
                
                now = datetime.now()
                fourteen_days_ago = now - timedelta(days=14)
                start_ts = int(fourteen_days_ago.timestamp())
                end_ts = int(now.timestamp())
                
                trades_14days = await self.gateio_client.get_my_trades(
                    contract="BTC_USDT",
                    start_time=start_ts,
                    end_time=end_ts,
                    limit=1000
                )
                
                if trades_14days and len(trades_14days) > 0:
                    # 최근 7일간의 거래만 필터링
                    seven_days_ago = now - timedelta(days=7)
                    seven_days_ts = int(seven_days_ago.timestamp())
                    
                    recent_trades = []
                    for trade in trades_14days:
                        trade_time = int(trade.get('create_time', 0))
                        if trade_time >= seven_days_ts:
                            recent_trades.append(trade)
                    
                    if recent_trades:
                        # PnL 계산
                        total_pnl = 0.0
                        for trade in recent_trades:
                            pnl = float(trade.get('point', 0))
                            total_pnl += pnl
                        
                        avg_daily = total_pnl / 7
                        
                        self.logger.info(f"✅ 방법2 성공: ${total_pnl:.2f} (14일 중 7일 필터링, {len(recent_trades)}건)")
                        return {
                            'total_pnl': total_pnl,
                            'average_daily': avg_daily,
                            'actual_days': 7.0,
                            'trade_count': len(recent_trades),
                            'source': 'method2_14day_filtered',
                            'confidence': 'medium'
                        }
                        
            except Exception as e:
                self.logger.warning(f"방법2 실패: {e}")
            
            # 방법 3: 30일 범위로 조회 후 7일 필터링
            try:
                self.logger.info("🔍 방법3: 30일 범위로 거래 내역 조회")
                
                now = datetime.now()
                thirty_days_ago = now - timedelta(days=30)
                start_ts = int(thirty_days_ago.timestamp())
                end_ts = int(now.timestamp())
                
                trades_30days = await self.gateio_client.get_my_trades(
                    contract="BTC_USDT",
                    start_time=start_ts,
                    end_time=end_ts,
                    limit=2000
                )
                
                if trades_30days and len(trades_30days) > 0:
                    # 최근 7일간의 거래만 필터링
                    seven_days_ago = now - timedelta(days=7)
                    seven_days_ts = int(seven_days_ago.timestamp())
                    
                    recent_trades = []
                    for trade in trades_30days:
                        trade_time = int(trade.get('create_time', 0))
                        if trade_time >= seven_days_ts:
                            recent_trades.append(trade)
                    
                    if recent_trades:
                        # PnL 계산
                        total_pnl = 0.0
                        for trade in recent_trades:
                            pnl = float(trade.get('point', 0))
                            total_pnl += pnl
                        
                        avg_daily = total_pnl / 7
                        
                        self.logger.info(f"✅ 방법3 성공: ${total_pnl:.2f} (30일 중 7일 필터링, {len(recent_trades)}건)")
                        return {
                            'total_pnl': total_pnl,
                            'average_daily': avg_daily,
                            'actual_days': 7.0,
                            'trade_count': len(recent_trades),
                            'source': 'method3_30day_filtered',
                            'confidence': 'medium'
                        }
                        
            except Exception as e:
                self.logger.warning(f"방법3 실패: {e}")
            
            # 모든 방법 실패 시 기본값
            self.logger.warning("❌ Gate.io 7일 수익 조회 모든 방법 실패")
            return {
                'total_pnl': 0,
                'average_daily': 0,
                'actual_days': 7.0,
                'trade_count': 0,
                'source': 'all_methods_failed',
                'confidence': 'low'
            }
            
        except Exception as e:
            self.logger.error(f"Gate.io 7일 수익 다중 방식 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'average_daily': 0,
                'actual_days': 7.0,
                'trade_count': 0,
                'source': 'error',
                'confidence': 'low'
            }
    
    async def _get_cumulative_profit_position_based(self, exchange: str) -> dict:
        """Position PnL 기반 누적 수익 계산 (입금 제외)"""
        try:
            self.logger.info(f"🔍 {exchange} 누적 순수익 계산 시작 (Position PnL 기반)")
            
            # 30일간의 긴 기간으로 Position PnL 조회
            now = datetime.now()
            start_date = now - timedelta(days=30)
            
            start_timestamp = int(start_date.timestamp() * 1000)  # 밀리초
            end_timestamp = int(now.timestamp() * 1000)  # 밀리초
            
            if exchange == 'bitget':
                result = await self.bitget_client.get_position_pnl_based_profit(
                    start_timestamp, end_timestamp, self.config.symbol
                )
                
                total_profit = result.get('net_profit', 0)  # 수수료 제외한 순수익
                current_equity = 0
                
                try:
                    account_info = await self.bitget_client.get_account_info()
                    current_equity = float(account_info.get('usdtEquity', 0))
                except:
                    current_equity = 0
                
                # 대략적인 ROI 계산 (현재 자산 기준)
                roi = (total_profit / max(current_equity - total_profit, 1000)) * 100 if current_equity > 0 else 0
                
                self.logger.info(f"✅ Bitget 30일 순수익: ${total_profit:.2f}")
                
                return {
                    'total_profit': total_profit,
                    'roi': roi,
                    'source': 'position_pnl_30days',
                    'period_days': 30,
                    'confidence': 'high'
                }
                
            elif exchange == 'gateio' and self.gateio_client:
                # Gate.io의 경우 초 단위로 변환
                start_timestamp_sec = int(start_date.timestamp())
                end_timestamp_sec = int(now.timestamp())
                
                result = await self.gateio_client.get_position_pnl_based_profit(
                    start_timestamp_sec, end_timestamp_sec, 'BTC_USDT'
                )
                
                total_profit = result.get('net_profit', 0)  # 수수료 제외한 순수익
                current_equity = 0
                
                try:
                    account_info = await self.gateio_client.get_account_balance()
                    current_equity = float(account_info.get('total', 0))
                except:
                    current_equity = 0
                
                # 대략적인 ROI 계산
                roi = (total_profit / max(current_equity - total_profit, 750)) * 100 if current_equity > 0 else 0
                
                self.logger.info(f"✅ Gate.io 30일 순수익: ${total_profit:.2f}")
                
                return {
                    'total_profit': total_profit,
                    'roi': roi,
                    'source': 'position_pnl_30days',
                    'period_days': 30,
                    'confidence': 'high'
                }
            
            # 기본값
            return {
                'total_profit': 0,
                'roi': 0,
                'source': 'fallback_zero',
                'confidence': 'low'
            }
            
        except Exception as e:
            self.logger.error(f"{exchange} 누적 순수익 계산 실패: {e}")
            return {
                'total_profit': 0,
                'roi': 0,
                'source': 'error',
                'confidence': 'low'
            }
    
    def _validate_bitget_data(self, data: dict) -> bool:
        if not data or data.get('exchange') != 'Bitget':
            return False
        
        # 기본 연결성 체크
        api_healthy = data.get('api_healthy', False)
        total_equity = data.get('total_equity', 0)
        
        # 자산이 있거나 포지션이 있으면 유효한 것으로 간주
        has_position = data.get('position_info', {}).get('has_position', False)
        
        valid = api_healthy and (total_equity > 0 or has_position)
        
        self.logger.info(f"Bitget 데이터 검증: {valid} (자산: ${total_equity:.2f}, 포지션: {has_position})")
        return valid
    
    def _validate_gateio_data(self, data: dict) -> bool:
        if not data or data.get('exchange') != 'Gate':
            return False
        
        has_account = data.get('has_account', False)
        total_equity = data.get('total_equity', 0)
        
        valid = has_account and total_equity > 0
        
        self.logger.info(f"Gate.io 데이터 검증: {valid} (자산: ${total_equity:.2f})")
        return valid
    
    def _calculate_combined_data_pure_profit(self, bitget_data: dict, gateio_data: dict, 
                                           bitget_healthy: bool, gateio_healthy: bool) -> dict:
        
        self.logger.info(f"🔍 순수 수익 기반 통합 계산:")
        self.logger.info(f"  - Bitget 상태: {'정상' if bitget_healthy else '오류'}")
        self.logger.info(f"  - Gate.io 상태: {'정상' if gateio_healthy else '없음'}")
        
        # 총 자산 계산
        bitget_equity = bitget_data['total_equity'] if bitget_healthy else 0
        gateio_equity = gateio_data['total_equity'] if gateio_healthy else 0
        total_equity = bitget_equity + gateio_equity
        
        # 자산 비중 계산
        if total_equity > 0:
            bitget_weight = bitget_equity / total_equity
            gateio_weight = gateio_equity / total_equity
        else:
            bitget_weight = 1.0 if bitget_healthy else 0.0
            gateio_weight = 1.0 if gateio_healthy and not bitget_healthy else 0.0
        
        # 가용 자산 계산
        bitget_available = bitget_data['available'] if bitget_healthy else 0
        gateio_available = gateio_data['available'] if gateio_healthy else 0
        total_available = bitget_available + gateio_available
        
        # 사용 증거금 계산
        bitget_used_margin = bitget_data['used_margin'] if bitget_healthy else 0
        gateio_used_margin = gateio_data['used_margin'] if gateio_healthy else 0
        total_used_margin = bitget_used_margin + gateio_used_margin
        
        # 미실현 손익 계산
        bitget_unrealized = bitget_data.get('unrealized_pl', 0) if bitget_healthy else 0
        gateio_unrealized = gateio_data.get('unrealized_pnl', 0) if gateio_healthy else 0
        today_unrealized = bitget_unrealized + gateio_unrealized
        
        # Position PnL 기반 금일 손익
        bitget_today_pnl = bitget_data['today_pnl'] if bitget_healthy else 0
        gateio_today_pnl = gateio_data['today_pnl'] if gateio_healthy else 0
        today_position_pnl = bitget_today_pnl + gateio_today_pnl
        today_total = today_position_pnl + today_unrealized
        
        # 금일 수익률 - 전체 자산 기준으로 계산
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        # 7일 Position PnL
        bitget_weekly = bitget_data['weekly_profit']['total'] if bitget_healthy else 0
        gateio_weekly = gateio_data['weekly_profit']['total_pnl'] if gateio_healthy else 0
        weekly_total = bitget_weekly + gateio_weekly
        
        # 7일 수익률 - 현실적인 계산 방식
        if total_equity > 0 and weekly_total != 0:
            initial_7d_equity = total_equity - weekly_total
            if initial_7d_equity > 0:
                weekly_roi = (weekly_total / initial_7d_equity * 100)
            else:
                weekly_roi = (weekly_total / total_equity * 100)
        else:
            weekly_roi = 0
        
        # 수익률 상한선 적용 (비현실적인 수익률 방지)
        if abs(weekly_roi) > 200:
            self.logger.warning(f"⚠️ 7일 수익률이 비현실적: {weekly_roi:.1f}%, 계산 재조정")
            weekly_roi = (weekly_total / total_equity * 100) if total_equity > 0 else 0
            weekly_roi = min(abs(weekly_roi), 50) * (1 if weekly_roi >= 0 else -1)
        
        # 실제 일수 계산
        bitget_days = bitget_data['weekly_profit'].get('actual_days', 7) if bitget_healthy else 7
        gateio_days = gateio_data['weekly_profit'].get('actual_days', 7) if gateio_healthy else 7
        actual_days = max(bitget_days, gateio_days)
        
        weekly_avg = weekly_total / actual_days if actual_days > 0 else 0
        
        # 누적 수익 (Position PnL 기반)
        bitget_cumulative = bitget_data['cumulative_profit'] if bitget_healthy else 0
        gateio_cumulative = gateio_data['cumulative_profit'] if gateio_healthy else 0
        cumulative_profit = bitget_cumulative + gateio_cumulative
        
        # 누적 수익률 - 추정 초기 자본 대비
        estimated_initial_capital = max(total_equity - cumulative_profit, 1000)
        cumulative_roi = (cumulative_profit / estimated_initial_capital * 100) if estimated_initial_capital > 0 else 0
        
        self.logger.info(f"순수 수익 계산 결과:")
        self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
        self.logger.info(f"  - Bitget 비중: {bitget_weight:.1%}, Gate 비중: {gateio_weight:.1%}")
        self.logger.info(f"  - 금일 수익률: {today_roi:.1f}%")
        self.logger.info(f"  - 7일 수익률: {weekly_roi:.1f}%")
        self.logger.info(f"  - 누적 순수익: ${cumulative_profit:.2f}")
        self.logger.info(f"  - 7일 총 수익: Bitget ${bitget_weekly:.2f} + Gate ${gateio_weekly:.2f} = ${weekly_total:.2f}")
        
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
            'bitget_weight': bitget_weight,
            'gateio_weight': gateio_weight,
            'estimated_initial_capital': estimated_initial_capital,
            # 개별 거래소 손익
            'bitget_today_realized': bitget_today_pnl,
            'bitget_today_unrealized': bitget_unrealized,
            'gateio_today_realized': gateio_today_pnl,
            'gateio_today_unrealized': gateio_unrealized,
            # 상태
            'bitget_healthy': bitget_healthy,
            'gateio_healthy': gateio_healthy
        }
    
    def _format_asset_summary_robust(self, combined_data: dict, bitget_healthy: bool, gateio_healthy: bool) -> str:
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        lines = []
        
        if total_equity > 0:
            lines.append(f"• <b>총 자산: ${total_equity:,.2f}</b> ({int(total_equity * 1350 / 10000)}만원)")
            
            if gateio_healthy and gateio_equity > 0:
                # 두 거래소 모두 있는 경우
                bitget_pct = combined_data['bitget_weight'] * 100
                gateio_pct = combined_data['gateio_weight'] * 100
                
                if bitget_healthy:
                    lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({bitget_pct:.0f}%)")
                else:
                    lines.append(f"  ├ Bitget: API 오류")
                
                lines.append(f"  └ Gate: ${gateio_equity:,.2f} ({gateio_pct:.0f}%)")
            else:
                # Bitget만 있는 경우
                if bitget_healthy:
                    lines.append(f"  └ Bitget: ${bitget_equity:,.2f} (100%)")
                else:
                    lines.append(f"  └ Bitget: API 연결 오류")
        else:
            lines.append(f"• <b>총 자산: 조회 중...</b>")
            if not bitget_healthy:
                lines.append(f"  └ Bitget: API 연결 오류")
            if gateio_healthy:
                lines.append(f"  └ Gate: ${gateio_equity:,.2f}")
        
        return '\n'.join(lines)
    
    def _format_profit_detail_robust(self, bitget_data: dict, gateio_data: dict, combined_data: dict, 
                                   bitget_healthy: bool, gateio_healthy: bool) -> str:
        lines = []
        
        today_total = combined_data['today_total']
        today_roi = combined_data['today_roi']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(today_total, today_roi)}</b>")
        
        # Bitget 상세
        if bitget_healthy:
            bitget_realized = combined_data['bitget_today_realized']
            bitget_unrealized = combined_data['bitget_today_unrealized']
            lines.append(f"  ├ Bitget: 미실현 {self._format_currency_html(bitget_unrealized, False)} | 실현 {self._format_currency_html(bitget_realized, False)}")
        else:
            lines.append(f"  ├ Bitget: API 연결 오류")
        
        # Gate 상세
        if gateio_healthy and gateio_data['total_equity'] > 0:
            gateio_realized = combined_data['gateio_today_realized']
            gateio_unrealized = combined_data['gateio_today_unrealized']
            lines.append(f"  └ Gate: 미실현 {self._format_currency_html(gateio_unrealized, False)} | 실현 {self._format_currency_html(gateio_realized, False)}")
        elif gateio_healthy:
            lines.append(f"  └ Gate: ${gateio_data['total_equity']:,.2f} 계정")
        
        return '\n'.join(lines)
    
    def _format_7day_profit_robust(self, combined_data: dict, bitget_data: dict, gateio_data: dict, 
                                 bitget_healthy: bool, gateio_healthy: bool) -> str:
        lines = []
        
        weekly_total = combined_data['weekly_total']
        weekly_roi = combined_data['weekly_roi']
        actual_days = combined_data['actual_days']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(weekly_total, weekly_roi)}</b>")
        
        # 거래소별 상세
        if gateio_healthy and gateio_data['total_equity'] > 0:
            if bitget_healthy:
                bitget_weekly = bitget_data['weekly_profit']['total']
                lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_weekly, False)}")
            else:
                lines.append(f"  ├ Bitget: API 연결 오류")
            
            gate_weekly = gateio_data['weekly_profit']['total_pnl']
            gate_source = gateio_data['weekly_profit'].get('source', 'unknown')
            gate_trade_count = gateio_data['weekly_profit'].get('trade_count', 0)
            
            # 조회 방식 표시
            if 'method1' in gate_source:
                method_indicator = "📊"
            elif 'method2' in gate_source or 'method3' in gate_source:
                method_indicator = "🔍"
            elif 'failed' in gate_source:
                method_indicator = "❌"
            else:
                method_indicator = "📊" if gate_trade_count > 0 else "🔍"
                
            lines.append(f"  └ Gate: {self._format_currency_html(gate_weekly, False)} {method_indicator}")
        else:
            if bitget_healthy:
                bitget_weekly = bitget_data['weekly_profit']['total']
                lines.append(f"  └ Bitget: {self._format_currency_html(bitget_weekly, False)}")
            else:
                lines.append(f"  └ Bitget: API 연결 오류")
        
        # 일평균
        lines.append(f"• <b>일평균: {self._format_currency_compact_daily(combined_data['weekly_avg'])}</b>")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance_robust(self, combined_data: dict, bitget_data: dict, gateio_data: dict, 
                                            bitget_healthy: bool, gateio_healthy: bool) -> str:
        lines = []
        
        total_cumulative = combined_data['cumulative_profit']
        total_cumulative_roi = combined_data['cumulative_roi']
        
        lines.append(f"• <b>순수익: {self._format_currency_compact(total_cumulative, total_cumulative_roi)}</b>")
        lines.append(f"• <b>계산 방식: Position PnL 기반 (입금 제외)</b>")
        
        # 거래소별 상세
        if gateio_healthy and gateio_data['total_equity'] > 0:
            if bitget_healthy:
                bitget_profit = bitget_data['cumulative_profit']
                bitget_roi = bitget_data['cumulative_roi']
                lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_profit, False)} ({bitget_roi:+.0f}%)")
            else:
                lines.append(f"  ├ Bitget: API 연결 오류")
            
            gate_profit = gateio_data['cumulative_profit']
            gate_roi = gateio_data['cumulative_roi']
            lines.append(f"  └ Gate: {self._format_currency_html(gate_profit, False)} ({gate_roi:+.0f}%)")
        else:
            if bitget_healthy:
                bitget_profit = bitget_data['cumulative_profit']
                bitget_roi = bitget_data['cumulative_roi']
                lines.append(f"  └ Bitget: {self._format_currency_html(bitget_profit, False)} ({bitget_roi:+.0f}%)")
            else:
                lines.append(f"  └ Bitget: API 연결 오류")
        
        return '\n'.join(lines)
    
    async def _format_positions_detail_robust(self, bitget_data: dict, gateio_data: dict, 
                                            bitget_healthy: bool, gateio_healthy: bool) -> str:
        lines = []
        has_any_position = False
        
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
                if gateio_healthy and gateio_data['total_equity'] > 0:
                    lines.append("━━━ <b>Bitget</b> ━━━")
                    lines.append("• 현재 포지션 없음")
        else:
            if gateio_healthy and gateio_data['total_equity'] > 0:
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
                if lines:
                    lines.append("")
                lines.append("━━━ <b>Gate</b> ━━━")
                lines.append("• 현재 포지션 없음")
        
        # 두 거래소 모두 포지션이 없는 경우
        if not has_any_position and not lines:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_asset_detail_robust(self, combined_data: dict, bitget_data: dict, gateio_data: dict, 
                                  bitget_healthy: bool, gateio_healthy: bool) -> str:
        lines = []
        
        total_available = combined_data['total_available']
        total_used_margin = combined_data['total_used_margin']
        total_equity = combined_data['total_equity']
        
        # 가용자산 비율 계산
        if total_equity > 0:
            available_pct = min((total_available / total_equity * 100), 100)
        else:
            available_pct = 0
        
        lines.append(f"• <b>가용/증거금: ${total_available:,.0f} / ${total_used_margin:,.0f}</b> ({available_pct:.0f}% 가용)")
        
        # Bitget 상세
        if bitget_healthy:
            bitget_available = bitget_data['available']
            bitget_used_margin = bitget_data['used_margin']
            lines.append(f"  ├ Bitget: ${bitget_available:,.0f} / ${bitget_used_margin:,.0f}")
        else:
            lines.append(f"  ├ Bitget: API 연결 오류")
        
        # Gate 상세
        if gateio_healthy and gateio_data['total_equity'] > 0:
            gate_available = gateio_data['available']
            gate_used_margin = gateio_data['used_margin']
            lines.append(f"  └ Gate: ${gate_available:,.0f} / ${gate_used_margin:,.0f}")
        elif gateio_healthy:
            lines.append(f"  └ Gate: ${gateio_data['available']:,.0f} / ${gateio_data['used_margin']:,.0f}")
        
        return '\n'.join(lines)
    
    async def _get_market_data_safe(self) -> dict:
        try:
            if not self.bitget_client:
                return {'current_price': 0, 'change_24h': 0, 'funding_rate': 0, 'volume_24h': 0}
            
            ticker_task = self.bitget_client.get_ticker(self.config.symbol)
            funding_task = self.bitget_client.get_funding_rate(self.config.symbol)
            
            try:
                ticker, funding_rate = await asyncio.gather(ticker_task, funding_task, return_exceptions=True)
                
                if isinstance(ticker, Exception):
                    ticker = {}
                if isinstance(funding_rate, Exception):
                    funding_rate = {}
                
                return {
                    'current_price': float(ticker.get('last', 0)) if ticker else 0,
                    'change_24h': float(ticker.get('changeUtc', 0)) if ticker else 0,
                    'funding_rate': float(funding_rate.get('fundingRate', 0)) if funding_rate else 0,
                    'volume_24h': float(ticker.get('baseVolume', 0)) if ticker else 0
                }
            except:
                return {'current_price': 0, 'change_24h': 0, 'funding_rate': 0, 'volume_24h': 0}
                
        except Exception as e:
            self.logger.error(f"시장 데이터 조회 실패: {e}")
            return {'current_price': 0, 'change_24h': 0, 'funding_rate': 0, 'volume_24h': 0}
    
    def _get_empty_bitget_data(self) -> dict:
        return {
            'exchange': 'Bitget',
            'position_info': {'has_position': False},
            'account_info': {'usdtEquity': 0, 'unrealizedPL': 0, 'available': 0},
            'today_pnl': 0,
            'weekly_profit': {'total': 0, 'average': 0, 'actual_days': 7},
            'cumulative_profit': 0,
            'cumulative_roi': 0,
            'total_equity': 0,
            'available': 0,
            'used_margin': 0,
            'unrealized_pl': 0,
            'api_healthy': False
        }
    
    def _get_empty_gateio_data(self) -> dict:
        return {
            'exchange': 'Gate',
            'position_info': {'has_position': False},
            'account_info': {'total': 0, 'unrealised_pnl': 0, 'available': 0},
            'today_pnl': 0,
            'weekly_profit': {'total_pnl': 0, 'average_daily': 0, 'actual_days': 7},
            'cumulative_profit': 0,
            'cumulative_roi': 0,
            'total_equity': 0,
            'available': 0,
            'used_margin': 0,
            'unrealized_pnl': 0,
            'has_account': False
        }
    
    def _format_currency_html(self, amount: float, include_krw: bool = True) -> str:
        # 비현실적인 값 안전장치
        if abs(amount) > 1000000:
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
        if abs(amount) > 1000000:
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
        if abs(amount) > 100000:
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
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        try:
            # 정확한 자산 정보로 멘탈 케어 데이터 구성
            account_info = {
                'usdtEquity': combined_data['total_equity'],  # 실제 총 자산
                'total_equity': combined_data['total_equity'],  # 백업용 필드
                'unrealizedPL': combined_data['today_unrealized'],
                'unrealized_pl': combined_data['today_unrealized']  # 백업용 필드
            }
            
            position_info = {
                'has_position': combined_data['total_used_margin'] > 0
            }
            
            weekly_profit = {
                'total': combined_data['weekly_total'],
                'total_pnl': combined_data['weekly_total'],  # 백업용 필드
                'average': combined_data['weekly_avg'],
                'average_daily': combined_data['weekly_avg']  # 백업용 필드
            }
            
            self.logger.info(f"🧠 멘탈 케어 데이터 전달:")
            self.logger.info(f"  - 총 자산: ${account_info['usdtEquity']:,.2f}")
            self.logger.info(f"  - 오늘 실현 PnL: ${combined_data['today_position_pnl']:.2f}")
            self.logger.info(f"  - 오늘 미실현 PnL: ${combined_data['today_unrealized']:.2f}")
            self.logger.info(f"  - 7일 총 수익: ${weekly_profit['total']:.2f}")
            self.logger.info(f"  - 포지션 보유: {position_info['has_position']}")
            
            mental_text = await self.mental_care.generate_profit_mental_care(
                account_info, position_info, combined_data['today_position_pnl'], weekly_profit
            )
            
            return mental_text
            
        except Exception as e:
            self.logger.error(f"통합 멘탈 케어 생성 실패: {e}")
            # 안전한 폴백 메시지 (하드코딩 방지)
            total_equity = combined_data.get('total_equity', 12000)
            krw_amount = int(total_equity * 1350 / 10000)
            return f"현재 ${total_equity:,.0f} ({krw_amount}만원) 자산을 안정적으로 관리하고 계시네요. 감정적 거래보다는 계획적인 접근이 중요해요. 리스크 관리를 철저히 하면서 꾸준히 나아가세요 💪"
