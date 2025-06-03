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
        
        # 초기 자산 설정 (실제 초기 투자금으로 설정 필요)
        self.BITGET_INITIAL_CAPITAL = 4000.0  # 초기 자산 $4000 가정
        self.GATE_INITIAL_CAPITAL = 700.0     # Gate.io 2025년 5월 초기 자본
    
    def set_gateio_client(self, gateio_client):
        """Gate.io 클라이언트 설정"""
        self.gateio_client = gateio_client
        self.logger.info("✅ Gate.io 클라이언트 설정 완료")
        
    async def generate_report(self) -> str:
        """💰 /profit 명령어 리포트 생성"""
        try:
            current_time = self._get_current_time_kst()
            
            # Bitget 데이터 조회
            bitget_data = await self._get_bitget_data()
            
            # Gate.io 데이터 조회 (활성화된 경우)
            gateio_data = await self._get_gateio_data()
            
            # 통합 데이터 계산
            combined_data = self._calculate_combined_data(bitget_data, gateio_data)
            
            # 통합 자산 현황
            asset_summary = self._format_asset_summary(combined_data)
            
            # 거래소별 포지션 정보
            positions_text = await self._format_positions_detail(bitget_data, gateio_data)
            
            # 거래소별 손익 정보
            profit_detail = self._format_profit_detail(bitget_data, gateio_data, combined_data)
            
            # 통합 자산 정보
            asset_detail = self._format_asset_detail(combined_data, bitget_data, gateio_data)
            
            # 누적 성과 (전체 기간)
            cumulative_text = self._format_cumulative_performance(combined_data, bitget_data, gateio_data)
            
            # 최근 수익 흐름 (통합)
            recent_flow = self._format_recent_flow(combined_data, bitget_data, gateio_data)
            
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

📊 <b>누적 성과</b>
{cumulative_text}

📈 <b>최근 흐름</b>
{recent_flow}

━━━━━━━━━━━━━━━━━━━
🧠 <b>멘탈 케어</b>
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"수익 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return "❌ 수익 현황 조회 중 오류가 발생했습니다."
    
    async def _get_bitget_data(self) -> dict:
        """Bitget 데이터 조회 - 실현 손익 조회 개선"""
        try:
            # 기존 코드 재사용
            market_data = await self._get_market_data()
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            
            # 🔥🔥 개선된 오늘 실현 손익 조회 - 다중 방법 시도
            today_pnl = await self._get_today_realized_pnl_enhanced()
            
            # 개선된 7일 손익 조회 - achievedProfits vs 실제 거래내역 비교
            self.logger.info("=== Bitget 7일 손익 조회 시작 ===")
            weekly_profit = await self.bitget_client.get_simple_weekly_profit(days=7)
            
            # 결과 로깅
            source = weekly_profit.get('source', 'unknown')
            total_pnl = weekly_profit.get('total_pnl', 0)
            
            self.logger.info(f"Bitget 7일 손익 최종 결과:")
            self.logger.info(f"  - 총 손익: ${total_pnl:.2f}")
            self.logger.info(f"  - 데이터 소스: {source}")
            self.logger.info(f"  - 거래 건수: {weekly_profit.get('trade_count', 0)}")
            
            if source == 'achievedProfits':
                position_days = weekly_profit.get('position_days', 0)
                self.logger.info(f"  - achievedProfits 사용됨 (포지션 기간: {position_days}일)")
            elif source == 'achievedProfits_only':
                self.logger.info(f"  - achievedProfits만 사용됨 (거래내역 없음)")
            else:
                self.logger.info(f"  - 실제 거래내역 사용됨")
            
            # 전체 기간 손익 조회 (30일)
            all_time_profit = await self.bitget_client.get_profit_loss_history(days=30)
            
            total_equity = account_info.get('total_equity', 0)
            
            # 실제 누적 수익 계산
            cumulative_profit = total_equity - self.BITGET_INITIAL_CAPITAL
            cumulative_roi = (cumulative_profit / self.BITGET_INITIAL_CAPITAL) * 100
            
            result = {
                'exchange': 'Bitget',
                'market_data': market_data,
                'position_info': position_info,
                'account_info': account_info,
                'today_pnl': today_pnl,
                'weekly_profit': {
                    'total': weekly_profit.get('total_pnl', 0),
                    'average': weekly_profit.get('average_daily', 0),
                    'daily_pnl': weekly_profit.get('daily_pnl', {}),
                    'source': source  # 데이터 소스 추가
                },
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': self.BITGET_INITIAL_CAPITAL,
                'available': account_info.get('available', 0),
                'used_margin': account_info.get('used_margin', 0)
            }
            
            self.logger.info(f"Bitget 데이터 구성 완료:")
            self.logger.info(f"  - 7일 손익: ${result['weekly_profit']['total']:.2f} (소스: {source})")
            self.logger.info(f"  - 오늘 실현손익: ${result['today_pnl']:.2f}")
            self.logger.info(f"  - 누적 수익: ${cumulative_profit:.2f} ({cumulative_roi:+.1f}%)")
            
            return result
        except Exception as e:
            self.logger.error(f"Bitget 데이터 조회 실패: {e}")
            return self._get_empty_exchange_data('Bitget')
    
    async def _get_today_realized_pnl_enhanced(self) -> float:
        """🔥🔥 개선된 오늘 실현 손익 조회 - 다중 방법 시도"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = int(today_start.timestamp() * 1000)
            end_time = int(now.timestamp() * 1000)
            
            self.logger.info(f"🔥 개선된 오늘 실현손익 조회: {today_start.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')}")
            
            # 🔥 방법 1: Account Bills 조회 (V2 corrected)
            bills_pnl = await self._get_today_pnl_from_bills(start_time, end_time)
            self.logger.info(f"Account Bills 방식: ${bills_pnl:.2f}")
            
            # 🔥 방법 2: 거래 내역(Fills) 조회 (enhanced)
            fills_pnl = await self._get_today_pnl_from_fills(start_time, end_time)
            self.logger.info(f"Trade Fills 방식: ${fills_pnl:.2f}")
            
            # 🔥 방법 3: 기존 방식 (폴백)
            legacy_pnl = await self._get_today_realized_pnl_kst_legacy()
            self.logger.info(f"Legacy 방식: ${legacy_pnl:.2f}")
            
            # 🔥🔥 최적 값 선택
            # 1순위: Account Bills (정확함)
            if bills_pnl != 0:
                self.logger.info(f"✅ Account Bills 결과 사용: ${bills_pnl:.2f}")
                return bills_pnl
            
            # 2순위: Trade Fills (대안)
            if fills_pnl != 0:
                self.logger.info(f"✅ Trade Fills 결과 사용: ${fills_pnl:.2f}")
                return fills_pnl
            
            # 3순위: Legacy (폴백)
            if legacy_pnl != 0:
                self.logger.info(f"✅ Legacy 결과 사용: ${legacy_pnl:.2f}")
                return legacy_pnl
            
            # 모든 방법이 0인 경우
            self.logger.warning("⚠️ 모든 방법에서 오늘 실현손익이 0으로 조회됨")
            return 0.0
            
        except Exception as e:
            self.logger.error(f"오늘 실현 손익 조회 실패: {e}")
            return 0.0
    
    async def _get_today_pnl_from_bills(self, start_time: int, end_time: int) -> float:
        """🔥 Account Bills에서 오늘 실현 손익 추출"""
        try:
            # 개선된 Account Bills 조회 사용
            bills = await self.bitget_client.get_account_bills_v2_corrected(
                start_time=start_time,
                end_time=end_time,
                business_type='contract_settle',  # 실현 손익만
                limit=100
            )
            
            total_pnl = 0.0
            for bill in bills:
                amount = float(bill.get('amount', 0))
                if amount != 0:
                    total_pnl += amount
                    self.logger.debug(f"Bills PnL: ${amount:.2f}")
            
            self.logger.info(f"Account Bills 오늘 실현손익: ${total_pnl:.2f} ({len(bills)}건)")
            return total_pnl
            
        except Exception as e:
            self.logger.warning(f"Account Bills 오늘 손익 조회 실패: {e}")
            return 0.0
    
    async def _get_today_pnl_from_fills(self, start_time: int, end_time: int) -> float:
        """🔥 Trade Fills에서 오늘 실현 손익 추출"""
        try:
            # 강화된 거래 내역 조회
            fills = await self.bitget_client._get_enhanced_fills_v2(
                self.config.symbol, start_time, end_time
            )
            
            total_pnl = 0.0
            for fill in fills:
                # 손익 추출 (여러 필드 시도)
                profit = 0.0
                for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl']:
                    if profit_field in fill and fill[profit_field] is not None:
                        try:
                            profit = float(fill[profit_field])
                            if profit != 0:
                                break
                        except:
                            continue
                
                if profit != 0:
                    total_pnl += profit
                    self.logger.debug(f"Fills PnL: ${profit:.2f}")
            
            self.logger.info(f"Trade Fills 오늘 실현손익: ${total_pnl:.2f} ({len(fills)}건)")
            return total_pnl
            
        except Exception as e:
            self.logger.warning(f"Trade Fills 오늘 손익 조회 실패: {e}")
            return 0.0
    
    async def _get_today_realized_pnl_kst_legacy(self) -> float:
        """기존 방식 (폴백용)"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = int(today_start.timestamp() * 1000)
            end_time = int(now.timestamp() * 1000)
            
            # 모든 거래 조회 (페이징 처리)
            all_fills = await self.bitget_client._get_period_fills_with_paging(
                self.config.symbol,
                start_time,
                end_time
            )
            
            realized_pnl = 0
            for trade in all_fills:
                profit = float(trade.get('profit', 0))
                if profit != 0:
                    realized_pnl += profit
            
            self.logger.info(f"Legacy 방식 오늘 실현 손익: ${realized_pnl:.2f} ({len(all_fills)}건)")
            return realized_pnl
            
        except Exception as e:
            self.logger.error(f"Legacy 오늘 실현 손익 조회 실패: {e}")
            return 0.0
    
    async def _get_gateio_data(self) -> dict:
        """Gate 데이터 조회 (개선된 버전) - 증거금 정확도 향상"""
        try:
            # Gate.io 클라이언트가 없는 경우
            if not self.gateio_client:
                self.logger.info("Gate 클라이언트가 설정되지 않음")
                return self._get_empty_exchange_data('Gate')
            
            # Gate 계정 정보 조회
            try:
                account_response = await self.gateio_client.get_account_balance()
                self.logger.info(f"Gate 계정 응답: {account_response}")
                
                total_equity = float(account_response.get('total', 0))
                available = float(account_response.get('available', 0))
                
                # 미실현 손익
                unrealized_pnl = float(account_response.get('unrealised_pnl', 0))
                
            except Exception as e:
                self.logger.error(f"Gate 계정 조회 실패: {e}")
                total_equity = 0
                available = 0
                unrealized_pnl = 0
            
            # Gate 포지션 조회
            position_info = {'has_position': False}
            try:
                positions = await self.gateio_client.get_positions('BTC_USDT')
                self.logger.info(f"Gate 포지션 정보: {positions}")
                
                for pos in positions:
                    if float(pos.get('size', 0)) != 0:
                        size = float(pos.get('size', 0))
                        entry_price = float(pos.get('entry_price', 0))
                        mark_price = float(pos.get('mark_price', 0))
                        pos_unrealized_pnl = float(pos.get('unrealised_pnl', 0))
                        leverage = float(pos.get('leverage', 10))
                        
                        # 🔥🔥 개선된 증거금 계산
                        # Gate.io는 계약 크기가 0.0001 BTC
                        btc_size = abs(size) * 0.0001
                        
                        # 1. API에서 직접 제공하는 margin 확인
                        api_margin = pos.get('margin', None)
                        if api_margin is not None:
                            margin_used = float(api_margin)
                            self.logger.info(f"🔥 Gate API에서 직접 제공하는 margin: ${margin_used:.2f}")
                        else:
                            # 2. 포지션 가치 기반 계산
                            position_value = btc_size * mark_price
                            margin_used = position_value / leverage
                            self.logger.info(f"🔥 계산된 margin: 포지션가치({position_value:.2f}) / 레버리지({leverage}) = ${margin_used:.2f}")
                        
                        # 3. 계정의 used 필드도 확인
                        account_used = float(account_response.get('used', 0))
                        if account_used > 0:
                            self.logger.info(f"🔥 계정에서 사용중인 금액: ${account_used:.2f}")
                            # 계정 used가 더 정확할 수 있음
                            if abs(account_used - margin_used) < margin_used * 0.1:  # 10% 이내 차이면
                                margin_used = account_used
                                self.logger.info(f"🔥 계정 used 값 사용: ${margin_used:.2f}")
                        
                        # ROE (Return on Equity) 계산 - 증거금 대비 수익률
                        roe = (pos_unrealized_pnl / margin_used) * 100 if margin_used > 0 else 0
                        
                        # 청산가 (liquidation price)
                        liquidation_price = float(pos.get('liq_price', 0))
                        
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
                            'roe': roe,  # pnl_rate 대신 roe로 변경
                            'contract_size': abs(size),
                            'leverage': leverage,
                            'margin': margin_used,
                            'liquidation_price': liquidation_price
                        }
                        
                        self.logger.info(f"🔥 Gate 포지션 정보 완성:")
                        self.logger.info(f"  - 증거금: ${margin_used:.2f}")
                        self.logger.info(f"  - ROE: {roe:.2f}%")
                        self.logger.info(f"  - 청산가: ${liquidation_price:.2f}")
                        break
            except Exception as e:
                self.logger.error(f"Gate 포지션 조회 실패: {e}")
            
            # 🔥🔥 개선된 사용 증거금 계산
            used_margin = 0
            if position_info['has_position']:
                used_margin = position_info.get('margin', 0)
            else:
                # 포지션이 없으면 계정의 used 사용
                used_margin = float(account_response.get('used', 0))
            
            # Gate 손익 데이터 조회 (2025년 5월부터)
            gate_profit_data = await self.gateio_client.get_profit_history_since_may()
            
            # 실제 초기 자본
            actual_initial = gate_profit_data.get('initial_capital', self.GATE_INITIAL_CAPITAL)
            
            # 누적 수익 사용 (2025년 5월부터)
            cumulative_profit = gate_profit_data.get('total', 0)
            cumulative_roi = (cumulative_profit / actual_initial * 100) if actual_initial > 0 else 0
            
            # Gate 7일 손익
            weekly_profit = gate_profit_data.get('weekly', {'total': 0, 'average': 0})
            
            # 오늘 실현 손익
            today_pnl = gate_profit_data.get('today_realized', 0)
            
            # 실제 수익 (현재 잔고 - 초기 자본)
            actual_profit = gate_profit_data.get('actual_profit', 0)
            
            self.logger.info(f"Gate 손익 데이터: 누적={cumulative_profit:.2f}, 7일={weekly_profit['total']:.2f}, 오늘={today_pnl:.2f}")
            self.logger.info(f"Gate 증거금 최종: ${used_margin:.2f}")
            
            return {
                'exchange': 'Gate',
                'position_info': position_info,
                'account_info': {
                    'total_equity': total_equity,
                    'available': available,
                    'used_margin': used_margin,
                    'unrealized_pnl': unrealized_pnl
                },
                'today_pnl': today_pnl,
                'weekly_profit': weekly_profit,
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': actual_initial,
                'available': available,
                'used_margin': used_margin,
                'has_account': total_equity > 0,  # Gate 계정 존재 여부
                'actual_profit': actual_profit  # 실제 수익
            }
            
        except Exception as e:
            self.logger.error(f"Gate 데이터 조회 실패: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Gate')
    
    async def _get_position_info(self) -> dict:
        """포지션 정보 조회 (Bitget) - V2 API 필드 확인, 청산가 정보 추가"""
        try:
            positions = await self.bitget_client.get_positions(self.config.symbol)
            
            if not positions:
                return {'has_position': False}
            
            # 활성 포지션 찾기
            for position in positions:
                total_size = float(position.get('total', 0))
                if total_size > 0:
                    self.logger.info(f"Bitget 포지션 전체 데이터: {position}")
                    
                    hold_side = position.get('holdSide', '')
                    side = '롱' if hold_side == 'long' else '숏'
                    
                    # 필요한 값들 추출
                    entry_price = float(position.get('openPriceAvg', 0))
                    mark_price = float(position.get('markPrice', 0))
                    margin_mode = position.get('marginMode', '')
                    
                    # V2 API에서 증거금 관련 필드 확인
                    margin = 0
                    margin_fields = ['margin', 'initialMargin', 'im', 'holdMargin', 'marginCoin']
                    for field in margin_fields:
                        if field in position and position[field]:
                            try:
                                margin = float(position[field])
                                if margin > 0:
                                    self.logger.info(f"증거금 필드 발견: {field} = {margin}")
                                    break
                            except:
                                continue
                    
                    # 미실현 손익
                    unrealized_pnl = float(position.get('unrealizedPL', 0))
                    
                    # margin이 0인 경우 대체 계산 방법
                    if margin == 0:
                        # 레버리지 정보 확인
                        leverage = float(position.get('leverage', 10))
                        
                        # 포지션 가치 = 수량 * 현재가
                        position_value = total_size * mark_price
                        
                        # 증거금 = 포지션 가치 / 레버리지
                        margin = position_value / leverage
                        self.logger.info(f"증거금 계산: 포지션가치({position_value}) / 레버리지({leverage}) = {margin}")
                    
                    # ROE 계산 (증거금 대비 수익률)
                    roe = (unrealized_pnl / margin) * 100 if margin > 0 else 0
                    
                    # PNL 퍼센트 대체 계산
                    if roe == 0 and entry_price > 0:
                        # 가격 변화율 기반 계산
                        if side == '롱':
                            roe = ((mark_price - entry_price) / entry_price) * 100 * leverage
                        else:
                            roe = ((entry_price - mark_price) / entry_price) * 100 * leverage
                        self.logger.info(f"ROE 대체 계산: {roe:.2f}%")
                    
                    # 🔥🔥 청산가 필드 확인 및 추가
                    liquidation_price = 0
                    liq_fields = ['liquidationPrice', 'liqPrice', 'estimatedLiqPrice', 'liquidPrice']
                    for field in liq_fields:
                        if field in position and position[field]:
                            try:
                                liquidation_price = float(position[field])
                                if liquidation_price > 0:
                                    self.logger.info(f"청산가 필드 발견: {field} = {liquidation_price}")
                                    break
                            except:
                                continue
                    
                    # 레버리지 정보
                    leverage = float(position.get('leverage', 10))
                    
                    self.logger.info(f"🔥 Bitget 포지션 정보:")
                    self.logger.info(f"  - 진입가: ${entry_price:.2f}")
                    self.logger.info(f"  - 현재가: ${mark_price:.2f}")
                    self.logger.info(f"  - 청산가: ${liquidation_price:.2f}")
                    self.logger.info(f"  - 증거금: ${margin:.2f}")
                    self.logger.info(f"  - ROE: {roe:.2f}%")
                    
                    return {
                        'has_position': True,
                        'symbol': self.config.symbol,
                        'side': side,
                        'side_en': hold_side,
                        'size': total_size,
                        'entry_price': entry_price,
                        'current_price': mark_price,
                        'margin_mode': margin_mode,
                        'margin': margin,
                        'unrealized_pnl': unrealized_pnl,
                        'roe': roe,  # ROE 추가
                        'liquidation_price': liquidation_price,  # 🔥🔥 청산가 추가
                        'leverage': leverage
                    }
            
            return {'has_position': False}
            
        except Exception as e:
            self.logger.error(f"포지션 정보 조회 실패: {e}")
            return {'has_position': False}
    
    def _get_empty_exchange_data(self, exchange_name: str) -> dict:
        """빈 거래소 데이터"""
        return {
            'exchange': exchange_name,
            'position_info': {'has_position': False},
            'account_info': {'total_equity': 0, 'unrealized_pnl': 0, 'available': 0, 'used_margin': 0},
            'today_pnl': 0,
            'weekly_profit': {'total': 0, 'average': 0},
            'cumulative_profit': 0,
            'cumulative_roi': 0,
            'total_equity': 0,
            'initial_capital': 0,
            'available': 0,
            'used_margin': 0,
            'has_account': False
        }
    
    def _calculate_combined_data(self, bitget_data: dict, gateio_data: dict) -> dict:
        """통합 데이터 계산"""
        # 총 자산
        total_equity = bitget_data['total_equity'] + gateio_data['total_equity']
        
        # 가용 자산
        total_available = bitget_data['available'] + gateio_data['available']
        
        # 사용 증거금
        total_used_margin = bitget_data['used_margin'] + gateio_data['used_margin']
        
        # 금일 수익
        today_pnl = bitget_data['today_pnl'] + gateio_data['today_pnl']
        today_unrealized = (bitget_data['account_info'].get('unrealized_pnl', 0) + 
                           gateio_data['account_info'].get('unrealized_pnl', 0))
        today_total = today_pnl + today_unrealized
        
        # 7일 수익 (통합)
        weekly_total = bitget_data['weekly_profit']['total'] + gateio_data['weekly_profit']['total']
        weekly_avg = weekly_total / 7
        
        # 누적 수익 (전체 기간)
        cumulative_profit = bitget_data['cumulative_profit'] + gateio_data['cumulative_profit']
        
        # 금일 수익률
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        # 7일 수익률
        initial_7d = total_equity - weekly_total
        weekly_roi = (weekly_total / initial_7d * 100) if initial_7d > 0 else 0
        
        # 누적 수익률
        total_initial = self.BITGET_INITIAL_CAPITAL + gateio_data.get('initial_capital', self.GATE_INITIAL_CAPITAL)
        cumulative_roi = (cumulative_profit / total_initial * 100) if total_initial > 0 else 0
        
        return {
            'total_equity': total_equity,
            'total_available': total_available,
            'total_used_margin': total_used_margin,
            'today_pnl': today_pnl,
            'today_unrealized': today_unrealized,
            'today_total': today_total,
            'today_roi': today_roi,
            'weekly_total': weekly_total,
            'weekly_avg': weekly_avg,
            'weekly_roi': weekly_roi,
            'cumulative_profit': cumulative_profit,
            'cumulative_roi': cumulative_roi,
            'bitget_equity': bitget_data['total_equity'],
            'gateio_equity': gateio_data['total_equity'],
            'gateio_has_account': gateio_data.get('has_account', False),
            'total_initial': total_initial
        }
    
    def _format_asset_summary(self, combined_data: dict) -> str:
        """통합 자산 현황 요약"""
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        lines = []
        
        # Gate 계정이 있는 경우
        if combined_data.get('gateio_has_account', False) and gateio_equity > 0:
            lines.append(f"• <b>총 자산</b>: ${total_equity:,.2f} ({int(total_equity * 1350 / 10000)}만원)")
            lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({int(bitget_equity * 1350 / 10000)}만원/{bitget_equity / total_equity * 100:.0f}%)")
            lines.append(f"  └ Gate: ${gateio_equity:,.2f} ({int(gateio_equity * 1350 / 10000)}만원/{gateio_equity / total_equity * 100:.0f}%)")
        else:
            lines.append(f"• <b>총 자산</b>: ${total_equity:,.2f} ({int(total_equity * 1350 / 10000)}만원)")
            lines.append(f"  └ Bitget: ${bitget_equity:,.2f} ({int(bitget_equity * 1350 / 10000)}만원/100%)")
        
        return '\n'.join(lines)
    
    async def _format_positions_detail(self, bitget_data: dict, gateio_data: dict) -> str:
        """거래소별 포지션 상세 정보 - 청산가 추가, Gate 계약 부분 제거"""
        lines = []
        has_any_position = False
        
        # Bitget 포지션
        bitget_pos = bitget_data['position_info']
        if bitget_pos.get('has_position'):
            has_any_position = True
            lines.append("━━━ <b>Bitget</b> ━━━")
            
            # ROE (포지션 수익률) 사용
            roe = bitget_pos.get('roe', 0)
            roe_sign = "+" if roe >= 0 else ""
            
            lines.append(f"• BTC {bitget_pos.get('side')} | 진입: ${bitget_pos.get('entry_price', 0):,.2f} ({roe_sign}{roe:.1f}%)")
            lines.append(f"• 현재가: ${bitget_pos.get('current_price', 0):,.2f} | 증거금: ${bitget_pos.get('margin', 0):.2f}")
            
            # 🔥🔥 청산가 추가 (Bitget)
            liquidation_price = bitget_pos.get('liquidation_price', 0)
            if liquidation_price > 0:
                current = bitget_pos.get('current_price', 0)
                side = bitget_pos.get('side')
                if side == '롱':
                    liq_distance = ((current - liquidation_price) / current * 100)
                else:
                    liq_distance = ((liquidation_price - current) / current * 100)
                lines.append(f"• 청산가: ${liquidation_price:,.2f} ({abs(liq_distance):.0f}% 거리)")
        
        # Gate 포지션
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            gateio_pos = gateio_data['position_info']
            if gateio_pos.get('has_position'):
                has_any_position = True
                if lines:
                    lines.append("")
                lines.append("━━━ <b>Gate</b> ━━━")
                
                # ROE (포지션 수익률)
                roe = gateio_pos.get('roe', 0)
                roe_sign = "+" if roe >= 0 else ""
                
                lines.append(f"• BTC {gateio_pos.get('side')} | 진입: ${gateio_pos.get('entry_price', 0):,.2f} ({roe_sign}{roe:.1f}%)")
                lines.append(f"• 현재가: ${gateio_pos.get('current_price', 0):,.2f} | 증거금: ${gateio_pos.get('margin', 0):.2f}")
                
                # 🔥🔥 Gate 계약 부분 제거 (사용자 요청)
                # 기존: lines.append(f"• 계약: {int(gateio_pos.get('contract_size', 0))}개 ({gateio_pos.get('btc_size', 0):.4f} BTC)")
                
                # 청산가
                liquidation_price = gateio_pos.get('liquidation_price', 0)
                if liquidation_price > 0:
                    current = gateio_pos.get('current_price', 0)
                    side = gateio_pos.get('side')
                    if side == '롱':
                        liq_distance = ((current - liquidation_price) / current * 100)
                    else:
                        liq_distance = ((liquidation_price - current) / current * 100)
                    lines.append(f"• 청산가: ${liquidation_price:,.2f} ({abs(liq_distance):.0f}% 거리)")
        
        if not has_any_position:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_profit_detail(self, bitget_data: dict, gateio_data: dict, combined_data: dict) -> str:
        """손익 정보 - 통합 요약 + 거래소별 상세"""
        lines = []
        
        # 통합 손익 요약 - 소수점 1자리까지 표시
        lines.append(f"• <b>수익</b>: {self._format_currency_compact(combined_data['today_total'], combined_data['today_roi'])}")
        
        # Bitget 상세
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0)
        bitget_today_pnl = bitget_data['today_pnl']
        lines.append(f"  ├ Bitget: 미실현 {self._format_currency_html(bitget_unrealized, False)} | 실현 {self._format_currency_html(bitget_today_pnl, False)}")
        
        # Gate 상세
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0)
            gateio_today_pnl = gateio_data['today_pnl']
            lines.append(f"  └ Gate: 미실현 {self._format_currency_html(gateio_unrealized, False)} | 실현 {self._format_currency_html(gateio_today_pnl, False)}")
        
        return '\n'.join(lines)
    
    def _format_asset_detail(self, combined_data: dict, bitget_data: dict, gateio_data: dict) -> str:
        """자산 정보 - 통합 + 거래소별 가용/증거금"""
        lines = []
        
        # 통합 자산
        lines.append(f"• <b>가용/증거금</b>: ${combined_data['total_available']:,.0f} / ${combined_data['total_used_margin']:,.0f} ({combined_data['total_available'] / combined_data['total_equity'] * 100:.0f}% 가용)")
        
        # Bitget 상세
        lines.append(f"  ├ Bitget: ${bitget_data['available']:,.0f} / ${bitget_data['used_margin']:,.0f}")
        
        # Gate 상세
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            lines.append(f"  └ Gate: ${gateio_data['available']:,.0f} / ${gateio_data['used_margin']:,.0f}")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance(self, combined_data: dict, bitget_data: dict, gateio_data: dict) -> str:
        """누적 성과 - 전체 기간"""
        lines = []
        
        # 통합 누적 수익
        total_cumulative = combined_data['cumulative_profit']
        total_cumulative_roi = combined_data['cumulative_roi']
        
        lines.append(f"• <b>수익</b>: {self._format_currency_compact(total_cumulative, total_cumulative_roi)}")
        
        # 거래소별 상세
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)} ({bitget_data['cumulative_roi']:+.0f}%)")
            
            # Gate.io는 2025년 5월부터 표시
            gate_roi = gateio_data['cumulative_roi']
            lines.append(f"  └ Gate: {self._format_currency_html(gateio_data['cumulative_profit'], False)} ({gate_roi:+.0f}%)")
        else:
            lines.append(f"  └ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)} ({bitget_data['cumulative_roi']:+.0f}%)")
        
        return '\n'.join(lines)
    
    def _format_recent_flow(self, combined_data: dict, bitget_data: dict, gateio_data: dict) -> str:
        """최근 수익 흐름 - 통합 + 데이터 소스 표시"""
        lines = []
        
        # 통합 7일 수익
        lines.append(f"• <b>7일 수익</b>: {self._format_currency_compact(combined_data['weekly_total'], combined_data['weekly_roi'])}")
        
        # 거래소별 7일 수익 + 데이터 소스
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            bitget_weekly = bitget_data['weekly_profit']['total']
            gate_weekly = gateio_data['weekly_profit']['total']
            
            # Bitget 데이터 소스 표시
            source = bitget_data['weekly_profit'].get('source', 'unknown')
            source_text = ""
            if source == 'achievedProfits':
                source_text = " (포지션)"
            elif source == 'achievedProfits_only':
                source_text = " (포지션만)"
            else:
                source_text = " (거래내역)"
            
            lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_weekly, False)}{source_text}")
            lines.append(f"  └ Gate: {self._format_currency_html(gate_weekly, False)}")
        else:
            # Bitget만 있는 경우
            bitget_weekly = bitget_data['weekly_profit']['total']
            source = bitget_data['weekly_profit'].get('source', 'unknown')
            source_text = ""
            if source == 'achievedProfits':
                source_text = " (포지션 실현수익)"
            elif source == 'achievedProfits_only':
                source_text = " (포지션 실현수익만)"
            else:
                source_text = " (거래내역 계산)"
            
            lines.append(f"  └ Bitget: {self._format_currency_html(bitget_weekly, False)}{source_text}")
        
        # 일평균
        lines.append(f"• <b>일평균</b>: {self._format_currency_compact_daily(combined_data['weekly_avg'])}")
        
        return '\n'.join(lines)
    
    def _format_currency_html(self, amount: float, include_krw: bool = True) -> str:
        """HTML용 통화 포맷팅"""
        if amount > 0:
            usd_text = f"+${amount:,.2f}"
        elif amount < 0:
            usd_text = f"-${abs(amount):,.2f}"
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
        """컴팩트한 통화+수익률 포맷 - 수익률 소수점 1자리"""
        sign = "+" if amount >= 0 else ""
        krw = int(abs(amount) * 1350 / 10000)
        return f"{sign}${abs(amount):,.2f} ({sign}{krw}만원/{sign}{roi:.1f}%)"
    
    def _format_currency_compact_daily(self, amount: float) -> str:
        """일평균용 컴팩트 포맷"""
        sign = "+" if amount >= 0 else ""
        krw = int(abs(amount) * 1350 / 10000)
        return f"{sign}${abs(amount):,.2f} ({sign}{krw}만원/일)"
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        """통합 멘탈 케어 생성"""
        if not self.openai_client:
            # GPT가 없을 때 기본 메시지
            if combined_data['cumulative_roi'] > 100:
                return f'"초기 자본 대비 {int(combined_data["cumulative_roi"])}%의 놀라운 수익률입니다! 이제는 수익 보호와 안정적인 운용이 중요한 시점입니다. 과욕은 성과를 무너뜨릴 수 있습니다. 🎯"'
            elif combined_data['weekly_roi'] > 10:
                return f'"최근 7일간 {int(combined_data["weekly_roi"])}%의 훌륭한 수익률을 기록하셨네요! 현재의 페이스를 유지하며 리스크 관리에 집중하세요. 🎯"'
            elif combined_data['today_roi'] > 0:
                return f'"오늘 ${int(combined_data["today_total"])}을 벌어들였군요! 꾸준한 수익이 복리의 힘을 만듭니다. 감정적 거래를 피하고 시스템을 따르세요. 💪"'
            else:
                return f'"총 자산 ${int(combined_data["total_equity"])}을 안정적으로 운용중입니다. 손실은 성장의 일부입니다. 차분한 마음으로 다음 기회를 준비하세요. 🧘‍♂️"'
        
        try:
            # 상황 요약
            has_gateio = combined_data.get('gateio_has_account', False) and combined_data.get('gateio_equity', 0) > 0
            
            situation_summary = f"""
현재 트레이더 상황:
- 총 자산: ${combined_data['total_equity']:,.0f}
- 초기 자본: ${combined_data['total_initial']:,.0f}
- 금일 수익: ${combined_data['today_total']:+,.0f} ({combined_data['today_roi']:+.1f}%)
- 7일 수익: ${combined_data['weekly_total']:+,.0f} ({combined_data['weekly_roi']:+.1f}%)
- 누적 수익: ${combined_data['cumulative_profit']:+,.0f} ({combined_data['cumulative_roi']:+.1f}%)
- 사용 증거금: ${combined_data['total_used_margin']:,.0f}
- 가용 자산: ${combined_data['total_available']:,.0f}
- 가용 비율: {(combined_data['total_available'] / combined_data['total_equity'] * 100):.0f}%
"""
            
            prompt = f"""당신은 전문 트레이딩 심리 코치입니다. 
다음 트레이더의 상황을 분석하고, 맞춤형 멘탈 케어 메시지를 작성하세요.

{situation_summary}

요구사항:
1. 구체적인 숫자(자산, 수익률)를 언급하며 개인화된 메시지
2. 현재 수익 상황에 맞는 조언 (높은 수익률이면 과욕 경계, 손실 중이면 회복 시도 차단)
3. 2-3문장으로 간결하게
4. 따뜻하고 친근한 톤으로, 너무 딱딱하지 않게
5. 반드시 이모티콘 1개 포함 (마지막에)
6. "반갑습니다", "Bitget에서의", "화이팅하세요" 같은 표현 금지
7. 금일 수익률과 7일 수익률을 비교할 때 논리적으로 정확하게 분석
8. 가용 자산이 많은 것은 좋은 것이므로 긍정적으로 표현
9. 충동적 매매를 자제하도록 부드럽게 권유
10. 메시지를 항상 완전한 문장으로 마무리"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 트레이더의 현재 상황에 맞는 심리적 조언을 제공하는 따뜻한 멘토입니다. 논리적으로 정확하고 친근한 조언을 제공하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=350,
                temperature=0.8
            )
            
            gpt_message = response.choices[0].message.content.strip()
            
            # GPT 응답에서 금지 표현 제거
            forbidden_phrases = ["반갑습니다", "Bitget에서의", "화이팅하세요", "화이팅", "안녕하세요", "레버리지"]
            for phrase in forbidden_phrases:
                gpt_message = gpt_message.replace(phrase, "")
            
            gpt_message = gpt_message.strip()
            
            # 이모티콘이 없으면 추가
            emoji_list = ['🎯', '💪', '🚀', '✨', '🌟', '😊', '👍', '🔥', '💎', '🏆']
            has_emoji = any(emoji in gpt_message for emoji in emoji_list)
            
            if not has_emoji:
                import random
                gpt_message += f" {random.choice(emoji_list)}"
            
            # 메시지가 완전히 끝났는지 확인
            if not gpt_message.endswith(('.', '!', '?', ')', '"')) and not has_emoji:
                # 미완성 문장 처리
                if '.' in gpt_message:
                    # 마지막 완전한 문장까지만 사용
                    gpt_message = gpt_message[:gpt_message.rfind('.')+1]
                    gpt_message += " 🎯"
            
            # 따옴표로 감싸기
            if not gpt_message.startswith('"'):
                gpt_message = f'"{gpt_message}"'
            
            return gpt_message
            
        except Exception as e:
            self.logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            # 폴백 메시지
            if combined_data['cumulative_roi'] > 100:
                return f'"초기 자본 대비 {int(combined_data["cumulative_roi"])}%의 놀라운 수익률입니다! 이제는 수익 보호와 안정적인 운용이 중요한 시점입니다. 과욕은 성과를 무너뜨릴 수 있습니다. 🎯"'
            elif combined_data['weekly_roi'] > 10:
                return f'"최근 7일간 {int(combined_data["weekly_roi"])}%의 훌륭한 수익률을 기록하셨네요! 현재의 페이스를 유지하며 리스크 관리에 집중하세요. 🎯"'
            elif combined_data['today_roi'] > 0:
                return f'"오늘 ${int(combined_data["today_total"])}을 벌어들였군요! 꾸준한 수익이 복리의 힘을 만듭니다. 감정적 거래를 피하고 시스템을 따르세요. 💪"'
            else:
                return f'"총 자산 ${int(combined_data["total_equity"])}을 안정적으로 운용중입니다. 손실은 성장의 일부입니다. 차분한 마음으로 다음 기회를 준비하세요. 🧘‍♂️"'
