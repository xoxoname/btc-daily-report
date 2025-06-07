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
        # Gate.io 초기 자본은 실제 누적 수익 기준으로 동적 계산
    
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
            
            # Gate.io 데이터 조회 (개선된 메서드 사용)
            gateio_data = await self._get_gateio_data_fixed()
            
            # Gate.io 실제 사용 여부 확인
            gateio_has_data = (gateio_data.get('has_account', False) and 
                             gateio_data.get('total_equity', 0) > 0)
            
            # 통합 데이터 계산
            combined_data = self._calculate_combined_data(bitget_data, gateio_data)
            
            # 통합 자산 현황
            asset_summary = self._format_asset_summary(combined_data, gateio_has_data)
            
            # 거래소별 포지션 정보
            positions_text = await self._format_positions_detail(bitget_data, gateio_data, gateio_has_data)
            
            # 거래소별 손익 정보
            profit_detail = self._format_profit_detail(bitget_data, gateio_data, combined_data, gateio_has_data)
            
            # 통합 자산 정보
            asset_detail = self._format_asset_detail(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 누적 성과 (전체 기간)
            cumulative_text = self._format_cumulative_performance(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 최근 수익 흐름 (통합)
            recent_flow = self._format_recent_flow(combined_data, bitget_data, gateio_data, gateio_has_data)
            
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
        """Bitget 데이터 조회 - 수정된 7일 손익 조회"""
        try:
            # 기존 코드 재사용
            market_data = await self._get_market_data()
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            
            # 🔥🔥 오늘 실현손익 조회 - 거래 내역 기반
            today_pnl = await self._get_today_realized_pnl_from_fills()
            
            # 🔥🔥 수정된 7일 손익 조회 - 더 정확한 방법
            self.logger.info("=== Bitget 7일 손익 조회 시작 (수정된 방법) ===")
            weekly_profit = await self._get_weekly_profit_improved()
            
            # 결과 로깅
            source = weekly_profit.get('source', 'unknown')
            total_pnl = weekly_profit.get('total_pnl', 0)
            
            self.logger.info(f"Bitget 7일 손익 최종 결과:")
            self.logger.info(f"  - 총 손익: ${total_pnl:.2f}")
            self.logger.info(f"  - 데이터 소스: {source}")
            self.logger.info(f"  - 거래 건수: {weekly_profit.get('trade_count', 0)}")
            
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
    
    async def _get_today_realized_pnl_from_fills(self) -> float:
        """오늘 실현손익 - 거래 내역에서 정확히 추출"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # UTC로 변환하여 타임스탬프 생성
            start_time_utc = today_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            self.logger.info(f"오늘 실현손익 조회:")
            self.logger.info(f"  - KST 시작: {today_start.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"  - KST 종료: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 거래 내역 조회
            fills = await self.bitget_client.get_trade_fills(
                symbol=self.config.symbol,
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=100
            )
            
            self.logger.info(f"조회된 오늘 거래 내역: {len(fills)}건")
            
            total_pnl = 0.0
            trade_count = 0
            
            for fill in fills:
                try:
                    # 실현 손익 추출
                    profit = 0.0
                    profit_fields = ['profit', 'realizedPL', 'realizedPnl', 'pnl', 'realizedProfit']
                    
                    for field in profit_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                profit = float(fill[field])
                                if profit != 0:
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 수수료 추출
                    fee = 0.0
                    fee_fields = ['fee', 'fees', 'totalFee', 'feeAmount']
                    for field in fee_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                fee = abs(float(fill[field]))
                                if fee > 0:
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 순 실현손익 = 실현손익 - 수수료
                    net_profit = profit - fee
                    
                    if profit != 0 or fee != 0:
                        total_pnl += net_profit
                        trade_count += 1
                        
                        fill_time = fill.get('cTime', 0)
                        time_str = datetime.fromtimestamp(int(fill_time)/1000, tz=kst).strftime('%H:%M:%S') if fill_time else 'N/A'
                        
                        self.logger.debug(f"거래 ({time_str}): 실현손익 ${profit:.4f} - 수수료 ${fee:.4f} = 순손익 ${net_profit:.4f}")
                
                except Exception as fill_error:
                    self.logger.warning(f"거래 내역 파싱 오류: {fill_error}")
                    continue
            
            self.logger.info(f"오늘 실현손익 최종: ${total_pnl:.4f} ({trade_count}건)")
            return total_pnl
            
        except Exception as e:
            self.logger.error(f"오늘 실현손익 조회 실패: {e}")
            return 0.0
    
    async def _get_weekly_profit_improved(self) -> dict:
        """🔥 수정된 7일 손익 조회 - 더 정확한 방법"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            seven_days_ago = now - timedelta(days=7)
            
            self.logger.info(f"7일 손익 조회 기간: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')}")
            
            # 방법 1: 최근 7일간 거래 내역에서 계산
            start_timestamp = int(seven_days_ago.timestamp() * 1000)
            end_timestamp = int(now.timestamp() * 1000)
            
            # 더 많은 거래 내역 조회 (한 번에 500건)
            all_fills = []
            try:
                # 최근 7일 거래 내역 - 페이징으로 모든 데이터 조회
                current_end = end_timestamp
                page = 0
                
                while page < 20:  # 최대 20페이지
                    fills = await self.bitget_client.get_trade_fills(
                        symbol=self.config.symbol,
                        start_time=start_timestamp,
                        end_time=current_end,
                        limit=500
                    )
                    
                    if not fills:
                        break
                    
                    all_fills.extend(fills)
                    self.logger.info(f"7일 거래내역 페이지 {page + 1}: {len(fills)}건 조회 (누적 {len(all_fills)}건)")
                    
                    if len(fills) < 500:
                        break
                    
                    # 다음 페이지를 위해 마지막 거래 시간을 새로운 end_time으로 설정
                    last_fill = fills[-1]
                    last_time = last_fill.get('cTime', last_fill.get('createTime'))
                    if last_time:
                        current_end = int(last_time) - 1
                    else:
                        break
                    
                    page += 1
                
                self.logger.info(f"총 7일 거래 내역: {len(all_fills)}건")
                
            except Exception as e:
                self.logger.error(f"거래 내역 조회 실패: {e}")
                all_fills = []
            
            # 거래 내역에서 손익 계산
            if all_fills:
                total_pnl = 0.0
                daily_pnl = {}
                trade_count = 0
                
                for fill in all_fills:
                    try:
                        # 시간 추출
                        fill_time = fill.get('cTime', fill.get('createTime', 0))
                        if not fill_time:
                            continue
                        
                        fill_date_kst = datetime.fromtimestamp(int(fill_time) / 1000, tz=kst)
                        fill_date_str = fill_date_kst.strftime('%Y-%m-%d')
                        
                        # 7일 범위 내 체크
                        if fill_date_kst < seven_days_ago:
                            continue
                        
                        # 실현 손익 추출
                        profit = 0.0
                        for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl', 'realizedProfit']:
                            if profit_field in fill and fill[profit_field] is not None:
                                try:
                                    profit = float(fill[profit_field])
                                    if profit != 0:
                                        break
                                except:
                                    continue
                        
                        # 수수료 추출
                        fee = 0.0
                        for fee_field in ['fee', 'fees', 'totalFee', 'feeAmount']:
                            if fee_field in fill and fill[fee_field] is not None:
                                try:
                                    fee = abs(float(fill[fee_field]))
                                    if fee > 0:
                                        break
                                except:
                                    continue
                        
                        # 순 손익
                        net_pnl = profit - fee
                        
                        if fill_date_str not in daily_pnl:
                            daily_pnl[fill_date_str] = 0
                        
                        daily_pnl[fill_date_str] += net_pnl
                        total_pnl += net_pnl
                        trade_count += 1
                        
                        if profit != 0 or fee != 0:
                            self.logger.debug(f"7일 거래: {fill_date_str} - ${net_pnl:.2f} (profit: ${profit:.2f}, fee: ${fee:.2f})")
                        
                    except Exception as e:
                        self.logger.warning(f"거래 내역 파싱 오류: {e}")
                        continue
                
                # 일별 손익 로깅
                for date_str, pnl in sorted(daily_pnl.items()):
                    self.logger.info(f"📊 {date_str}: ${pnl:.2f}")
                
                return {
                    'total_pnl': total_pnl,
                    'daily_pnl': daily_pnl,
                    'average_daily': total_pnl / 7,
                    'trade_count': trade_count,
                    'source': 'trade_fills_improved',
                    'confidence': 'high'
                }
            
            # 방법 2: achievedProfits 조회 (포지션 기반)
            try:
                self.logger.info("거래 내역 조회 실패, achievedProfits 시도")
                
                positions = await self.bitget_client.get_positions(self.config.symbol)
                achieved_profits = 0
                
                for pos in positions:
                    achieved = float(pos.get('achievedProfits', 0))
                    if achieved != 0:
                        achieved_profits = achieved
                        break
                
                if achieved_profits > 0:
                    self.logger.info(f"achievedProfits에서 조회: ${achieved_profits:.2f}")
                    
                    return {
                        'total_pnl': achieved_profits,
                        'daily_pnl': {},
                        'average_daily': achieved_profits / 7,
                        'trade_count': 0,
                        'source': 'achieved_profits_fallback',
                        'confidence': 'medium'
                    }
            
            except Exception as e:
                self.logger.error(f"achievedProfits 조회 실패: {e}")
            
            # 방법 3: 기본값 반환
            self.logger.warning("모든 7일 손익 조회 방법 실패, 기본값 반환")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'source': 'fallback_zero',
                'confidence': 'low'
            }
            
        except Exception as e:
            self.logger.error(f"7일 손익 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'source': 'error',
                'confidence': 'low'
            }
    
    async def _get_gateio_data_fixed(self) -> dict:
        """🔥🔥 Gate.io 데이터 조회 - 공식 API 문서 기반 수정"""
        try:
            # Gate.io 클라이언트가 없는 경우
            if not self.gateio_client:
                self.logger.info("Gate.io 클라이언트가 설정되지 않음")
                return self._get_empty_exchange_data('Gate')
            
            self.logger.info("🔍 Gate.io 데이터 조회 시작 (공식 API 문서 기반)...")
            
            # Gate 계정 정보 조회
            total_equity = 0
            available = 0
            unrealized_pnl = 0
            
            try:
                self.logger.info("Gate.io 계정 정보 조회 중...")
                account_response = await self.gateio_client.get_account_balance()
                self.logger.info(f"Gate 계정 응답: {account_response}")
                
                if account_response:
                    total_equity = float(account_response.get('total', 0))
                    available = float(account_response.get('available', 0))
                    unrealized_pnl = float(account_response.get('unrealised_pnl', 0))
                    
                    self.logger.info(f"Gate.io 계정 정보 성공: total=${total_equity:.2f}, available=${available:.2f}")
                else:
                    self.logger.warning("Gate.io 계정 응답이 빈 값")
                
            except Exception as e:
                self.logger.error(f"Gate 계정 조회 실패: {e}")
                self.logger.error(f"Gate 계정 오류 상세: {traceback.format_exc()}")
                # 계정 조회 실패해도 계속 진행
            
            # Gate 포지션 조회
            position_info = {'has_position': False}
            
            try:
                self.logger.info("Gate.io 포지션 조회 중...")
                positions = await self.gateio_client.get_positions('BTC_USDT')
                self.logger.info(f"Gate 포지션 응답: {positions}")
                
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
                            
                            # 청산가
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
                                'roe': roe,
                                'contract_size': abs(size),
                                'leverage': leverage,
                                'margin': margin_used,
                                'liquidation_price': liquidation_price
                            }
                            
                            self.logger.info(f"Gate.io 포지션 정보 성공: {position_info['side']} ${entry_price:.2f}")
                            break
                else:
                    self.logger.info("Gate.io 포지션 없음")
                    
            except Exception as e:
                self.logger.error(f"Gate 포지션 조회 실패: {e}")
                self.logger.error(f"Gate 포지션 오류 상세: {traceback.format_exc()}")
            
            # 🔥🔥 Gate.io 공식 API 문서 기반 수익 조회 - 완전 수정
            today_pnl = 0
            weekly_profit = {'total': 0, 'average': 0}
            cumulative_profit = 0
            initial_capital = 0
            
            try:
                self.logger.info("🔍 Gate.io 공식 API 기반 수익 조회 시작...")
                
                # 🔥🔥 방법 1: account_book API 사용 (공식 문서 기준)
                today_pnl = await self._get_gate_today_pnl_from_account_book()
                self.logger.info(f"Gate.io 오늘 실현손익 (account_book): ${today_pnl:.4f}")
                
                # 🔥🔥 방법 2: account_book으로 7일 수익 조회
                weekly_profit_result = await self._get_gate_weekly_profit_from_account_book()
                weekly_profit = {
                    'total': weekly_profit_result.get('total_pnl', 0),
                    'average': weekly_profit_result.get('average_daily', 0),
                    'source': weekly_profit_result.get('source', 'gate_account_book_api')
                }
                self.logger.info(f"Gate.io 7일 손익 (account_book): ${weekly_profit['total']:.4f}")
                
                # 🔥🔥 방법 3: 포지션의 history_pnl로 누적 수익 조회
                cumulative_profit = await self._get_gate_cumulative_profit_from_positions()
                
                # 초기 자본 동적 계산 (현재 잔고 - 누적 수익)
                initial_capital = total_equity - cumulative_profit
                
                # 초기 자본이 음수가 되지 않도록 보정
                if initial_capital < 0:
                    initial_capital = total_equity * 0.8  # 현재 잔고의 80%로 추정
                    cumulative_profit = total_equity - initial_capital
                
                self.logger.info(f"Gate.io 수익 계산 (공식 API):")
                self.logger.info(f"  - 현재 잔고: ${total_equity:.2f}")
                self.logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
                self.logger.info(f"  - 계산된 초기 자본: ${initial_capital:.2f}")
                
            except Exception as e:
                self.logger.error(f"Gate.io 공식 API 수익 조회 실패: {e}")
                # 기본값 설정
                initial_capital = total_equity * 0.8 if total_equity > 0 else 700  # 기본값
                cumulative_profit = total_equity - initial_capital if total_equity > 0 else 0
            
            # 사용 증거금 계산
            used_margin = 0
            if position_info['has_position']:
                used_margin = position_info.get('margin', 0)
            else:
                used_margin = total_equity - available
            
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            
            # 계정이 실제로 있는지 확인
            has_account = total_equity > 0
            
            self.logger.info(f"Gate.io 데이터 구성 완료 (공식 API):")
            self.logger.info(f"  - 계정 존재: {has_account}")
            self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
            self.logger.info(f"  - 오늘 실현손익: ${today_pnl:.4f}")
            self.logger.info(f"  - 7일 손익: ${weekly_profit['total']:.4f}")
            self.logger.info(f"  - 누적 수익: ${cumulative_profit:.2f} ({cumulative_roi:+.1f}%)")
            self.logger.info(f"  - 초기 자본: ${initial_capital:.2f}")
            self.logger.info(f"  - 포지션: {'있음' if position_info['has_position'] else '없음'}")
            self.logger.info(f"  - 사용 증거금: ${used_margin:.2f}")
            
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
                'initial_capital': initial_capital,  # 동적으로 계산된 초기 자본
                'available': available,
                'used_margin': used_margin,
                'has_account': has_account,  # Gate 계정 존재 여부
                'actual_profit': cumulative_profit
            }
            
        except Exception as e:
            self.logger.error(f"Gate 데이터 조회 실패: {e}")
            self.logger.error(f"Gate 데이터 오류 상세: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Gate')
    
    async def _get_gate_today_pnl_from_account_book(self) -> float:
        """🔥🔥 Gate.io 공식 account_book API로 오늘 실현손익 조회"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # UTC로 변환하여 초 단위 타임스탬프 생성 (Gate.io는 초 단위)
            start_time_utc = today_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp())  # 초 단위
            end_timestamp = int(end_time_utc.timestamp())     # 초 단위
            
            self.logger.info(f"Gate.io 오늘 실현손익 조회 (account_book):")
            self.logger.info(f"  - KST 시작: {today_start.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"  - KST 종료: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"  - UTC 타임스탬프: {start_timestamp} ~ {end_timestamp}")
            
            # Gate.io account_book API 호출 (pnl 타입만)
            # GET /futures/usdt/account_book?type=pnl&from={start}&to={end}
            
            total_pnl = 0.0
            
            try:
                # 직접 API 호출 (gateio_client에 메서드가 있다고 가정)
                if hasattr(self.gateio_client, 'get_account_book'):
                    account_records = await self.gateio_client.get_account_book(
                        start_time=start_timestamp * 1000,  # 밀리초로 변환
                        end_time=end_timestamp * 1000,      # 밀리초로 변환
                        limit=100,
                        type_filter='pnl'  # PnL 타입만 필터링
                    )
                else:
                    # 대체 방법: 직접 API 엔드포인트 호출
                    endpoint = "/api/v4/futures/usdt/account_book"
                    params = {
                        'from': start_timestamp,
                        'to': end_timestamp,
                        'type': 'pnl',
                        'limit': 100
                    }
                    
                    # gateio_client의 _request 메서드 활용
                    account_records = await self.gateio_client._request('GET', endpoint, params=params)
                
                self.logger.info(f"Gate.io account_book PnL 기록: {len(account_records) if account_records else 0}건")
                
                if account_records:
                    for record in account_records:
                        try:
                            change = float(record.get('change', 0))
                            record_type = record.get('type', '')
                            record_time = int(record.get('time', 0))
                            
                            if record_type == 'pnl' and change != 0:
                                total_pnl += change
                                
                                # 시간 변환하여 로깅
                                time_kst = datetime.fromtimestamp(record_time, tz=kst)
                                self.logger.debug(f"Gate PnL 기록 ({time_kst.strftime('%H:%M:%S')}): ${change:.4f}")
                        
                        except Exception as parse_error:
                            self.logger.warning(f"Gate PnL 기록 파싱 오류: {parse_error}")
                            continue
                
            except Exception as api_error:
                self.logger.error(f"Gate.io account_book API 호출 실패: {api_error}")
                
                # 대체 방법: positions에서 realised_pnl 조회
                try:
                    positions = await self.gateio_client.get_positions('BTC_USDT')
                    for pos in positions:
                        realised_pnl = float(pos.get('realised_pnl', 0))
                        if realised_pnl != 0:
                            total_pnl = realised_pnl  # 오늘만이 아닌 전체 실현손익
                            self.logger.info(f"대체: 포지션 realised_pnl 사용: ${total_pnl:.4f}")
                            break
                except Exception as pos_error:
                    self.logger.error(f"대체 포지션 조회도 실패: {pos_error}")
            
            self.logger.info(f"Gate.io 오늘 실현손익 최종: ${total_pnl:.4f}")
            return total_pnl
            
        except Exception as e:
            self.logger.error(f"Gate.io 오늘 실현손익 조회 실패: {e}")
            return 0.0
    
    async def _get_gate_weekly_profit_from_account_book(self) -> dict:
        """🔥🔥 Gate.io 공식 account_book API로 7일 수익 조회"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            seven_days_ago = now - timedelta(days=7)
            
            # UTC로 변환하여 초 단위 타임스탬프 생성 (Gate.io는 초 단위)
            start_timestamp = int(seven_days_ago.timestamp())
            end_timestamp = int(now.timestamp())
            
            self.logger.info(f"Gate.io 7일 손익 조회 (account_book):")
            self.logger.info(f"  - 기간: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')}")
            self.logger.info(f"  - UTC 타임스탬프: {start_timestamp} ~ {end_timestamp}")
            
            total_pnl = 0.0
            daily_pnl = {}
            
            try:
                # Gate.io account_book API 호출 (pnl 타입만)
                if hasattr(self.gateio_client, 'get_account_book'):
                    account_records = await self.gateio_client.get_account_book(
                        start_time=start_timestamp * 1000,  # 밀리초로 변환
                        end_time=end_timestamp * 1000,      # 밀리초로 변환
                        limit=500,
                        type_filter='pnl'  # PnL 타입만 필터링
                    )
                else:
                    # 직접 API 엔드포인트 호출
                    endpoint = "/api/v4/futures/usdt/account_book"
                    params = {
                        'from': start_timestamp,
                        'to': end_timestamp,
                        'type': 'pnl',
                        'limit': 500
                    }
                    
                    account_records = await self.gateio_client._request('GET', endpoint, params=params)
                
                self.logger.info(f"Gate.io 7일 account_book PnL 기록: {len(account_records) if account_records else 0}건")
                
                if account_records:
                    for record in account_records:
                        try:
                            change = float(record.get('change', 0))
                            record_type = record.get('type', '')
                            record_time = int(record.get('time', 0))
                            
                            if record_type == 'pnl' and change != 0:
                                # 날짜별로 분류
                                record_date_kst = datetime.fromtimestamp(record_time, tz=kst)
                                record_date_str = record_date_kst.strftime('%Y-%m-%d')
                                
                                if record_date_str not in daily_pnl:
                                    daily_pnl[record_date_str] = 0
                                
                                daily_pnl[record_date_str] += change
                                total_pnl += change
                                
                                self.logger.debug(f"Gate 7일 PnL ({record_date_str}): ${change:.4f}")
                        
                        except Exception as parse_error:
                            self.logger.warning(f"Gate 7일 PnL 기록 파싱 오류: {parse_error}")
                            continue
                    
                    # 일별 손익 로깅
                    for date_str, pnl in sorted(daily_pnl.items()):
                        self.logger.info(f"📊 Gate {date_str}: ${pnl:.2f}")
                    
                    return {
                        'total_pnl': total_pnl,
                        'daily_pnl': daily_pnl,
                        'average_daily': total_pnl / 7,
                        'source': 'gate_account_book_api_official',
                        'confidence': 'high'
                    }
                
            except Exception as api_error:
                self.logger.error(f"Gate.io 7일 account_book API 호출 실패: {api_error}")
            
            # 기본값 반환
            self.logger.warning("Gate.io 7일 손익 조회 실패, 기본값 반환")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'source': 'gate_account_book_failed',
                'confidence': 'low'
            }
            
        except Exception as e:
            self.logger.error(f"Gate.io 7일 손익 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'source': 'gate_error',
                'confidence': 'low'
            }
    
    async def _get_gate_cumulative_profit_from_positions(self) -> float:
        """🔥🔥 Gate.io 포지션의 history_pnl로 누적 수익 조회"""
        try:
            self.logger.info("Gate.io 누적 수익 조회 (포지션 history_pnl)...")
            
            positions = await self.gateio_client.get_positions('BTC_USDT')
            
            total_history_pnl = 0.0
            
            if positions:
                for pos in positions:
                    # Gate.io 포지션 응답에서 history_pnl 또는 total_pnl 필드 확인
                    history_pnl = float(pos.get('history_pnl', 0))
                    realised_pnl = float(pos.get('realised_pnl', 0))
                    
                    # history_pnl이 있으면 사용, 없으면 realised_pnl 사용
                    if history_pnl != 0:
                        total_history_pnl = history_pnl
                        self.logger.info(f"Gate.io history_pnl 발견: ${history_pnl:.4f}")
                        break
                    elif realised_pnl != 0:
                        total_history_pnl = realised_pnl
                        self.logger.info(f"Gate.io realised_pnl 사용: ${realised_pnl:.4f}")
                        break
            
            # 추가: account_book에서 전체 pnl 누적 조회 (더 정확한 방법)
            if total_history_pnl == 0:
                try:
                    self.logger.info("포지션에서 history_pnl 없음, account_book에서 전체 누적 조회...")
                    
                    # 30일 전부터 현재까지 모든 pnl 기록 조회
                    now = datetime.now()
                    thirty_days_ago = now - timedelta(days=30)
                    
                    start_timestamp = int(thirty_days_ago.timestamp())
                    end_timestamp = int(now.timestamp())
                    
                    if hasattr(self.gateio_client, 'get_account_book'):
                        all_records = await self.gateio_client.get_account_book(
                            start_time=start_timestamp * 1000,
                            end_time=end_timestamp * 1000,
                            limit=1000,
                            type_filter='pnl'
                        )
                    else:
                        endpoint = "/api/v4/futures/usdt/account_book"
                        params = {
                            'from': start_timestamp,
                            'to': end_timestamp,
                            'type': 'pnl',
                            'limit': 1000
                        }
                        all_records = await self.gateio_client._request('GET', endpoint, params=params)
                    
                    cumulative_from_records = 0.0
                    if all_records:
                        for record in all_records:
                            change = float(record.get('change', 0))
                            if record.get('type') == 'pnl':
                                cumulative_from_records += change
                        
                        total_history_pnl = cumulative_from_records
                        self.logger.info(f"Gate.io 30일 account_book 누적: ${cumulative_from_records:.4f}")
                
                except Exception as record_error:
                    self.logger.error(f"account_book 누적 조회 실패: {record_error}")
            
            self.logger.info(f"Gate.io 누적 수익 최종: ${total_history_pnl:.4f}")
            return total_history_pnl
            
        except Exception as e:
            self.logger.error(f"Gate.io 누적 수익 조회 실패: {e}")
            return 0.0
    
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
                    self.logger.info(f"Bitget 포지션 데이터: {position}")
                    
                    hold_side = position.get('holdSide', '')
                    side = '롱' if hold_side == 'long' else '숏'
                    
                    # 필요한 값들 추출
                    entry_price = float(position.get('openPriceAvg', 0))
                    mark_price = float(position.get('markPrice', 0))
                    margin_mode = position.get('marginMode', '')
                    
                    # 증거금 추출
                    margin = 0
                    margin_fields = ['margin', 'initialMargin', 'im', 'holdMargin']
                    for field in margin_fields:
                        if field in position and position[field]:
                            try:
                                margin = float(position[field])
                                if margin > 0:
                                    self.logger.info(f"증거금 필드 발견: {field} = {margin}")
                                    break
                            except:
                                continue
                    
                    # margin이 0인 경우 계산
                    if margin == 0:
                        leverage = float(position.get('leverage', 10))
                        position_value = total_size * mark_price
                        margin = position_value / leverage
                        self.logger.info(f"증거금 계산: 포지션가치({position_value}) / 레버리지({leverage}) = {margin}")
                    
                    # 미실현 손익
                    unrealized_pnl = float(position.get('unrealizedPL', 0))
                    
                    # ROE 계산
                    roe = (unrealized_pnl / margin) * 100 if margin > 0 else 0
                    
                    # 청산가 추출 - 더 정확한 방법
                    liquidation_price = 0
                    liq_fields = ['liquidationPrice', 'liqPrice', 'estimatedLiqPrice']
                    for field in liq_fields:
                        if field in position and position[field]:
                            try:
                                raw_liq_price = float(position[field])
                                if raw_liq_price > 0 and raw_liq_price < mark_price * 3:  # 합리적인 범위
                                    liquidation_price = raw_liq_price
                                    self.logger.info(f"청산가 발견: {field} = {liquidation_price}")
                                    break
                            except:
                                continue
                    
                    # 청산가가 없거나 비합리적이면 계산
                    if liquidation_price <= 0:
                        leverage = float(position.get('leverage', 10))
                        if side == '롱':
                            liquidation_price = entry_price * (1 - 0.9/leverage)  # 90% 안전마진
                        else:
                            liquidation_price = entry_price * (1 + 0.9/leverage)
                        
                        self.logger.info(f"청산가 계산: ${liquidation_price:.2f} (레버리지 {leverage}x 기반)")
                    
                    leverage = float(position.get('leverage', 10))
                    
                    self.logger.info(f"Bitget 포지션 정보:")
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
                        'roe': roe,
                        'liquidation_price': liquidation_price,
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
        total_initial = self.BITGET_INITIAL_CAPITAL + gateio_data.get('initial_capital', 0)
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
    
    def _format_asset_summary(self, combined_data: dict, gateio_has_data: bool) -> str:
        """통합 자산 현황 요약 - 굵게 표시"""
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        lines = []
        
        # Gate 계정이 있고 데이터가 있는 경우
        if gateio_has_data and gateio_equity > 0:
            lines.append(f"• <b>총 자산: ${total_equity:,.2f}</b> ({int(total_equity * 1350 / 10000)}만원)")
            lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({int(bitget_equity * 1350 / 10000)}만원/{bitget_equity / total_equity * 100:.0f}%)")
            lines.append(f"  └ Gate: ${gateio_equity:,.2f} ({int(gateio_equity * 1350 / 10000)}만원/{gateio_equity / total_equity * 100:.0f}%)")
        else:
            lines.append(f"• <b>총 자산: ${total_equity:,.2f}</b> ({int(total_equity * 1350 / 10000)}만원)")
            lines.append(f"  └ Bitget: ${bitget_equity:,.2f} ({int(bitget_equity * 1350 / 10000)}만원/100%)")
        
        return '\n'.join(lines)
    
    async def _format_positions_detail(self, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """거래소별 포지션 상세 정보 - 청산가 굵게 표시"""
        lines = []
        has_any_position = False
        
        # Bitget 포지션
        bitget_pos = bitget_data['position_info']
        if bitget_pos.get('has_position'):
            has_any_position = True
            lines.append("━━━ <b>Bitget</b> ━━━")
            
            roe = bitget_pos.get('roe', 0)
            roe_sign = "+" if roe >= 0 else ""
            
            lines.append(f"• BTC {bitget_pos.get('side')} | 진입: ${bitget_pos.get('entry_price', 0):,.2f} ({roe_sign}{roe:.1f}%)")
            lines.append(f"• 현재가: ${bitget_pos.get('current_price', 0):,.2f} | 증거금: ${bitget_pos.get('margin', 0):.2f}")
            
            # 청산가 - 굵게 표시
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
        
        # Gate 포지션 - 데이터가 있는 경우만
        if gateio_has_data and gateio_data['total_equity'] > 0:
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
                
                # 청산가 - 굵게 표시
                liquidation_price = gateio_pos.get('liquidation_price', 0)
                if liquidation_price > 0:
                    current = gateio_pos.get('current_price', 0)
                    side = gateio_pos.get('side')
                    if side == '롱':
                        liq_distance = ((current - liquidation_price) / current * 100)
                    else:
                        liq_distance = ((liquidation_price - current) / current * 100)
                    lines.append(f"• <b>청산가: ${liquidation_price:,.2f}</b> ({abs(liq_distance):.0f}% 거리)")
        
        if not has_any_position:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_profit_detail(self, bitget_data: dict, gateio_data: dict, combined_data: dict, gateio_has_data: bool) -> str:
        """손익 정보 - 통합 요약 + 거래소별 상세 (굵게 표시)"""
        lines = []
        
        # 통합 손익 요약 - 굵게 표시
        lines.append(f"• <b>수익: {self._format_currency_compact(combined_data['today_total'], combined_data['today_roi'])}</b>")
        
        # Bitget 상세
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0)
        bitget_today_pnl = bitget_data['today_pnl']
        lines.append(f"  ├ Bitget: 미실현 {self._format_currency_html(bitget_unrealized, False)} | 실현 {self._format_currency_html(bitget_today_pnl, False)}")
        
        # Gate 상세 - 데이터가 있는 경우만
        if gateio_has_data and gateio_data['total_equity'] > 0:
            gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0)
            gateio_today_pnl = gateio_data['today_pnl']
            lines.append(f"  └ Gate: 미실현 {self._format_currency_html(gateio_unrealized, False)} | 실현 {self._format_currency_html(gateio_today_pnl, False)}")
        
        return '\n'.join(lines)
    
    def _format_asset_detail(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """자산 정보 - 통합 + 거래소별 가용/증거금 (굵게 표시)"""
        lines = []
        
        # 통합 자산 - 굵게 표시
        lines.append(f"• <b>가용/증거금: ${combined_data['total_available']:,.0f} / ${combined_data['total_used_margin']:,.0f}</b> ({combined_data['total_available'] / combined_data['total_equity'] * 100:.0f}% 가용)")
        
        # Bitget 상세
        lines.append(f"  ├ Bitget: ${bitget_data['available']:,.0f} / ${bitget_data['used_margin']:,.0f}")
        
        # Gate 상세 - 데이터가 있는 경우만
        if gateio_has_data and gateio_data['total_equity'] > 0:
            lines.append(f"  └ Gate: ${gateio_data['available']:,.0f} / ${gateio_data['used_margin']:,.0f}")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """누적 성과 - 전체 기간 (굵게 표시)"""
        lines = []
        
        # 통합 누적 수익 - 굵게 표시
        total_cumulative = combined_data['cumulative_profit']
        total_cumulative_roi = combined_data['cumulative_roi']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(total_cumulative, total_cumulative_roi)}</b>")
        
        # 거래소별 상세
        if gateio_has_data and gateio_data['total_equity'] > 0:
            lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)} ({bitget_data['cumulative_roi']:+.0f}%)")
            
            gate_roi = gateio_data['cumulative_roi']
            lines.append(f"  └ Gate: {self._format_currency_html(gateio_data['cumulative_profit'], False)} ({gate_roi:+.0f}%)")
        else:
            lines.append(f"  └ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)} ({bitget_data['cumulative_roi']:+.0f}%)")
        
        return '\n'.join(lines)
    
    def _format_recent_flow(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """최근 수익 흐름 - 통합 + 데이터 소스 표시 (굵게 표시)"""
        lines = []
        
        # 통합 7일 수익 - 굵게 표시
        lines.append(f"• <b>7일 수익: {self._format_currency_compact(combined_data['weekly_total'], combined_data['weekly_roi'])}</b>")
        
        # 거래소별 7일 수익 + 데이터 소스
        if gateio_has_data and gateio_data['total_equity'] > 0:
            bitget_weekly = bitget_data['weekly_profit']['total']
            gate_weekly = gateio_data['weekly_profit']['total']
            
            # Bitget 데이터 소스 표시
            source = bitget_data['weekly_profit'].get('source', 'unknown')
            source_text = self._get_source_text(source)
            
            lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_weekly, False)}{source_text}")
            
            # Gate.io 데이터 소스 표시
            gate_source = gateio_data['weekly_profit'].get('source', 'unknown')
            gate_source_text = self._get_source_text(gate_source)
            lines.append(f"  └ Gate: {self._format_currency_html(gate_weekly, False)}{gate_source_text}")
        else:
            # Bitget만 있는 경우
            bitget_weekly = bitget_data['weekly_profit']['total']
            source = bitget_data['weekly_profit'].get('source', 'unknown')
            source_text = self._get_source_text(source)
            
            lines.append(f"  └ Bitget: {self._format_currency_html(bitget_weekly, False)}{source_text}")
        
        # 일평균 - 굵게 표시
        lines.append(f"• <b>일평균: {self._format_currency_compact_daily(combined_data['weekly_avg'])}</b>")
        
        return '\n'.join(lines)
    
    def _get_source_text(self, source: str) -> str:
        """데이터 소스 텍스트 변환"""
        if 'achieved_profits' in source:
            return " (포지션수익)"
        elif 'trade_fills' in source:
            return " (거래내역)"
        elif 'improved' in source:
            return " (향상된방식)"
        elif 'gate_account_book_api' in source:
            return " (공식API)"
        elif 'gate_pnl' in source:
            return " (PnL기록)"
        elif 'gate_all' in source:
            return " (계정변동)"
        elif 'gate_trades' in source:
            return " (거래수수료)"
        elif 'gate_api' in source:
            return " (API개선)"
        elif 'fallback' in source:
            return " (대체방식)"
        elif 'error' in source or 'zero' in source:
            return " (오류/기본값)"
        else:
            return " (기타)"
    
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
        """컴팩트한 통화+수익률 포맷"""
        sign = "+" if amount >= 0 else ""
        krw = int(abs(amount) * 1350 / 10000)
        return f"{sign}${abs(amount):,.2f} ({sign}{krw}만원/{sign}{roi:.1f}%)"
    
    def _format_currency_compact_daily(self, amount: float) -> str:
        """일평균용 컴팩트 포맷"""
        sign = "+" if amount >= 0 else ""
        krw = int(abs(amount) * 1350 / 10000)
        return f"{sign}${abs(amount):,.2f} ({sign}{krw}만원/일)"
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        """통합 멘탈 케어 생성 - 개선된 버전"""
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
                account_info, position_info, combined_data['today_pnl'], weekly_profit
            )
            
            return mental_text
            
        except Exception as e:
            self.logger.error(f"통합 멘탈 케어 생성 실패: {e}")
            return "시장은 변동성이 클 수 있지만, 꾸준한 전략과 리스크 관리로 좋은 결과를 얻을 수 있습니다. 감정에 휘둘리지 말고 차분하게 대응하세요 💪"
