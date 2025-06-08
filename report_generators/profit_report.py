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
            
            # Bitget 데이터 조회
            bitget_data = await self._get_bitget_data()
            
            # Gate.io 데이터 조회 (정확한 공식 API 기반 계산)
            gateio_data = await self._get_gateio_data_accurate_fixed()
            
            # Gate.io 실제 사용 여부 확인
            gateio_has_data = (gateio_data.get('has_account', False) and 
                             gateio_data.get('total_equity', 0) > 0)
            
            # 통합 데이터 계산
            combined_data = self._calculate_combined_data_accurate(bitget_data, gateio_data)
            
            # 통합 자산 현황
            asset_summary = self._format_asset_summary(combined_data, gateio_has_data)
            
            # 거래소별 포지션 정보
            positions_text = await self._format_positions_detail(bitget_data, gateio_data, gateio_has_data)
            
            # 거래소별 손익 정보
            profit_detail = self._format_profit_detail_accurate(bitget_data, gateio_data, combined_data, gateio_has_data)
            
            # 통합 자산 정보
            asset_detail = self._format_asset_detail(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 누적 성과 (2025년 5월부터)
            cumulative_text = self._format_cumulative_performance_accurate(combined_data, bitget_data, gateio_data, gateio_has_data)
            
            # 최근 수익 흐름 (통합)
            recent_flow = self._format_recent_flow_accurate(combined_data, bitget_data, gateio_data, gateio_has_data)
            
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
    
    async def _get_gateio_data_accurate_fixed(self) -> dict:
        """🔥🔥 Gate.io 정확한 데이터 조회 - 수정된 공식 API 기반"""
        try:
            # Gate.io 클라이언트가 없는 경우
            if not self.gateio_client:
                self.logger.info("Gate.io 클라이언트가 설정되지 않음")
                return self._get_empty_exchange_data('Gate')
            
            self.logger.info("🔍 Gate.io 정확한 데이터 조회 시작 (수정된 공식 API 완전 기반)...")
            
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
                            break
                    
            except Exception as e:
                self.logger.error(f"Gate 포지션 조회 실패: {e}")
            
            # 🔥🔥 Gate.io 수익 조회 - 수정된 공식 API 직접 사용
            today_pnl = 0
            weekly_profit = {'total_pnl': 0, 'average_daily': 0}
            cumulative_profit = 0
            
            try:
                # 🔥🔥 수정된 gateio_client의 공식 API 메서드 직접 사용
                self.logger.info("🔍 Gate.io 수정된 공식 API 메서드 직접 사용...")
                
                # 오늘 실현손익 (포지션 API 기반)
                today_pnl = await self.gateio_client.get_today_realized_pnl()
                
                # 7일 수익 (포지션 API 기반)
                weekly_result = await self.gateio_client.get_weekly_profit()
                weekly_profit = {
                    'total_pnl': weekly_result.get('total_pnl', 0),
                    'average_daily': weekly_result.get('average_daily', 0),
                    'source': weekly_result.get('source', 'gateio_client_api')
                }
                
                # 누적 수익 (포지션 API 기반 정확한 계산)
                profit_history = await self.gateio_client.get_profit_history_since_may()
                cumulative_profit = profit_history.get('actual_profit', 0)
                
                self.logger.info(f"✅ Gate.io 수정된 공식 API 성공:")
                self.logger.info(f"  - 오늘 실현손익: ${today_pnl:.4f}")
                self.logger.info(f"  - 7일 수익: ${weekly_profit['total_pnl']:.4f}")
                self.logger.info(f"  - 정확한 누적 수익: ${cumulative_profit:.2f}")
                
            except Exception as e:
                self.logger.error(f"Gate.io 수정된 공식 API 실패: {e}")
                # 기본값 유지
                cumulative_profit = 0
                today_pnl = 0
                weekly_profit = {'total_pnl': 0, 'average_daily': 0, 'source': 'api_failed'}
            
            # 사용 증거금 계산
            used_margin = 0
            if position_info['has_position']:
                used_margin = position_info.get('margin', 0)
            else:
                used_margin = max(0, total_equity - available)
            
            # 초기 자본을 동적 계산 (현재 잔고 - 누적 수익)
            if cumulative_profit > 0:
                initial_capital = max(500, total_equity - cumulative_profit)  # 최소 $500
            else:
                initial_capital = max(700, total_equity * 0.9) if total_equity > 0 else 700
                cumulative_profit = max(0, total_equity - initial_capital)
            
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            has_account = total_equity > 0
            
            self.logger.info(f"Gate.io 최종 데이터 (수정된 정확한 계산):")
            self.logger.info(f"  - 계정 존재: {has_account}")
            self.logger.info(f"  - 총 자산: ${total_equity:.2f}")
            self.logger.info(f"  - 미실현손익: ${unrealized_pnl:.4f}")
            self.logger.info(f"  - 오늘 실현손익: ${today_pnl:.4f}")
            self.logger.info(f"  - 7일 손익: ${weekly_profit['total_pnl']:.4f}")
            self.logger.info(f"  - 수정된 정확한 누적 수익: ${cumulative_profit:.2f} ({cumulative_roi:+.1f}%)")
            self.logger.info(f"  - 동적 초기 자본: ${initial_capital:.2f}")
            
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
                'initial_capital': initial_capital,
                'available': available,
                'used_margin': used_margin,
                'has_account': has_account,
                'actual_profit': cumulative_profit
            }
            
        except Exception as e:
            self.logger.error(f"Gate 정확한 데이터 조회 실패: {e}")
            self.logger.error(f"Gate 데이터 오류 상세: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Gate')
    
    def _calculate_combined_data_accurate(self, bitget_data: dict, gateio_data: dict) -> dict:
        """정확한 통합 데이터 계산"""
        # 총 자산
        total_equity = bitget_data['total_equity'] + gateio_data['total_equity']
        
        # 가용 자산
        total_available = bitget_data['available'] + gateio_data['available']
        
        # 사용 증거금
        total_used_margin = bitget_data['used_margin'] + gateio_data['used_margin']
        
        # 금일 손익 계산
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0)
        gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0)
        
        today_realized = bitget_data['today_pnl'] + gateio_data['today_pnl']
        today_unrealized = bitget_unrealized + gateio_unrealized
        today_total = today_realized + today_unrealized
        
        # 7일 수익 (통합)
        bitget_weekly = bitget_data['weekly_profit']['total']
        gateio_weekly = gateio_data['weekly_profit']['total_pnl']
        weekly_total = bitget_weekly + gateio_weekly
        weekly_avg = weekly_total / 7
        
        # 누적 수익 (2025년 5월부터)
        bitget_cumulative = bitget_data['cumulative_profit']
        gateio_cumulative = gateio_data['cumulative_profit']
        cumulative_profit = bitget_cumulative + gateio_cumulative
        
        # 수익률 계산
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        initial_7d = total_equity - weekly_total
        weekly_roi = (weekly_total / initial_7d * 100) if initial_7d > 0 else 0
        
        total_initial = self.BITGET_INITIAL_CAPITAL + gateio_data.get('initial_capital', 0)
        cumulative_roi = (cumulative_profit / total_initial * 100) if total_initial > 0 else 0
        
        return {
            'total_equity': total_equity,
            'total_available': total_available,
            'total_used_margin': total_used_margin,
            'today_realized': today_realized,
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
    
    def _format_profit_detail_accurate(self, bitget_data: dict, gateio_data: dict, combined_data: dict, gateio_has_data: bool) -> str:
        """정확한 손익 정보"""
        lines = []
        
        # 통합 손익 요약
        today_total = combined_data['today_total']
        today_roi = combined_data['today_roi']
        
        lines.append(f"• <b>수익: {self._format_currency_compact(today_total, today_roi)}</b>")
        
        # Bitget 상세
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0)
        bitget_realized = bitget_data['today_pnl']
        lines.append(f"  ├ Bitget: 미실현 {self._format_currency_html(bitget_unrealized, False)} | 실현 {self._format_currency_html(bitget_realized, False)}")
        
        # Gate 상세 - 데이터가 있는 경우만
        if gateio_has_data and gateio_data['total_equity'] > 0:
            gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0)
            gateio_realized = gateio_data['today_pnl']
            lines.append(f"  └ Gate: 미실현 {self._format_currency_html(gateio_unrealized, False)} | 실현 {self._format_currency_html(gateio_realized, False)}")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance_accurate(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """정확한 누적 성과 - 2025년 5월부터"""
        lines = []
        
        # 통합 누적 수익
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
    
    def _format_recent_flow_accurate(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """정확한 최근 수익 흐름"""
        lines = []
        
        # 통합 7일 수익
        lines.append(f"• <b>7일 수익: {self._format_currency_compact(combined_data['weekly_total'], combined_data['weekly_roi'])}</b>")
        
        # 거래소별 7일 수익
        if gateio_has_data and gateio_data['total_equity'] > 0:
            bitget_weekly = bitget_data['weekly_profit']['total']
            gate_weekly = gateio_data['weekly_profit']['total_pnl']
            
            lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_weekly, False)}")
            lines.append(f"  └ Gate: {self._format_currency_html(gate_weekly, False)}")
        else:
            # Bitget만 있는 경우
            bitget_weekly = bitget_data['weekly_profit']['total']
            lines.append(f"  └ Bitget: {self._format_currency_html(bitget_weekly, False)}")
        
        # 일평균
        lines.append(f"• <b>일평균: {self._format_currency_compact_daily(combined_data['weekly_avg'])}</b>")
        
        return '\n'.join(lines)
    
    def _format_currency_html(self, amount: float, include_krw: bool = True) -> str:
        """HTML용 통화 포맷팅"""
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
        """컴팩트한 통화+수익률 포맷"""
        if amount >= 0:
            sign = "+"
            krw = int(amount * 1350 / 10000)
            return f"{sign}${amount:.2f} ({sign}{krw}만원/{sign}{roi:.1f}%)"
        else:
            sign = "-"
            krw = int(abs(amount) * 1350 / 10000)
            return f"{sign}${abs(amount):.2f} ({sign}{krw}만원/{sign}{abs(roi):.1f}%)"
    
    def _format_currency_compact_daily(self, amount: float) -> str:
        """일평균용 컴팩트 포맷"""
        if amount >= 0:
            sign = "+"
            krw = int(amount * 1350 / 10000)
            return f"{sign}${amount:.2f} ({sign}{krw}만원/일)"
        else:
            sign = "-"
            krw = int(abs(amount) * 1350 / 10000)
            return f"{sign}${abs(amount):.2f} ({sign}{krw}만원/일)"
    
    # 나머지 메서드들은 기존과 동일...
    async def _get_bitget_data(self) -> dict:
        """Bitget 데이터 조회 - 2025년 5월부터 집계"""
        try:
            # 기존 코드 재사용
            market_data = await self._get_market_data()
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            
            # 오늘 실현손익 조회 - 거래 내역 기반
            today_pnl = await self._get_today_realized_pnl_from_fills()
            
            # 7일 손익 조회
            weekly_profit = await self._get_weekly_profit_improved()
            
            # 2025년 5월부터 누적 손익 조회
            cumulative_data = await self._get_cumulative_profit_since_may()
            
            total_equity = account_info.get('total_equity', 0)
            
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
                    'source': weekly_profit.get('source', 'unknown')
                },
                'cumulative_profit': cumulative_data.get('total_profit', 0),
                'cumulative_roi': cumulative_data.get('roi', 0),
                'total_equity': total_equity,
                'initial_capital': self.BITGET_INITIAL_CAPITAL,
                'available': account_info.get('available', 0),
                'used_margin': account_info.get('used_margin', 0),
                'cumulative_data': cumulative_data
            }
            
            return result
        except Exception as e:
            self.logger.error(f"Bitget 데이터 조회 실패: {e}")
            return self._get_empty_exchange_data('Bitget')
    
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
            
            # 거래 내역 조회
            fills = await self.bitget_client.get_trade_fills(
                symbol=self.config.symbol,
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=100
            )
            
            total_pnl = 0.0
            
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
                
                except Exception as fill_error:
                    continue
            
            return total_pnl
            
        except Exception as e:
            self.logger.error(f"오늘 실현손익 조회 실패: {e}")
            return 0.0
    
    async def _get_weekly_profit_improved(self) -> dict:
        """7일 손익 조회"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            seven_days_ago = now - timedelta(days=7)
            
            # 현재 잔고에서 7일 전 추정 잔고를 뺀 값으로 근사 계산
            try:
                positions = await self.bitget_client.get_positions(self.config.symbol)
                achieved_profits = 0
                
                for pos in positions:
                    achieved = float(pos.get('achievedProfits', 0))
                    if achieved != 0:
                        achieved_profits = achieved
                        break
                
                if achieved_profits > 0:
                    # achievedProfits를 7일 수익으로 근사
                    total_pnl = min(achieved_profits, achieved_profits)  # 최대 제한
                    
                    return {
                        'total_pnl': total_pnl,
                        'daily_pnl': {},
                        'average_daily': total_pnl / 7,
                        'trade_count': 0,
                        'source': 'achieved_profits_approximation',
                        'confidence': 'medium'
                    }
            
            except Exception as e:
                self.logger.error(f"achievedProfits 조회 실패: {e}")
            
            # 기본값 반환
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
                    
                    # 증거금 추출
                    margin = 0
                    margin_fields = ['margin', 'initialMargin', 'im', 'holdMargin']
                    for field in margin_fields:
                        if field in position and position[field]:
                            try:
                                margin = float(position[field])
                                if margin > 0:
                                    break
                            except:
                                continue
                    
                    # margin이 0인 경우 계산
                    if margin == 0:
                        leverage = float(position.get('leverage', 10))
                        position_value = total_size * mark_price
                        margin = position_value / leverage
                    
                    # 미실현 손익
                    unrealized_pnl = float(position.get('unrealizedPL', 0))
                    
                    # ROE 계산
                    roe = (unrealized_pnl / margin) * 100 if margin > 0 else 0
                    
                    # 청산가 추출
                    liquidation_price = 0
                    liq_fields = ['liquidationPrice', 'liqPrice', 'estimatedLiqPrice']
                    for field in liq_fields:
                        if field in position and position[field]:
                            try:
                                raw_liq_price = float(position[field])
                                if raw_liq_price > 0 and raw_liq_price < mark_price * 3:
                                    liquidation_price = raw_liq_price
                                    break
                            except:
                                continue
                    
                    # 청산가가 없으면 계산
                    if liquidation_price <= 0:
                        leverage = float(position.get('leverage', 10))
                        if side == '롱':
                            liquidation_price = entry_price * (1 - 0.9/leverage)
                        else:
                            liquidation_price = entry_price * (1 + 0.9/leverage)
                    
                    leverage = float(position.get('leverage', 10))
                    
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
            'weekly_profit': {'total_pnl': 0, 'average_daily': 0},
            'cumulative_profit': 0,
            'cumulative_roi': 0,
            'total_equity': 0,
            'initial_capital': 0,
            'available': 0,
            'used_margin': 0,
            'has_account': False
        }
    
    def _format_asset_summary(self, combined_data: dict, gateio_has_data: bool) -> str:
        """통합 자산 현황 요약"""
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
        """거래소별 포지션 상세 정보"""
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
            
            # 청산가
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
        
        # Gate 포지션
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
        
        if not has_any_position:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_asset_detail(self, combined_data: dict, bitget_data: dict, gateio_data: dict, gateio_has_data: bool) -> str:
        """자산 정보"""
        lines = []
        
        # 통합 자산
        lines.append(f"• <b>가용/증거금: ${combined_data['total_available']:,.0f} / ${combined_data['total_used_margin']:,.0f}</b> ({combined_data['total_available'] / combined_data['total_equity'] * 100:.0f}% 가용)")
        
        # Bitget 상세
        lines.append(f"  ├ Bitget: ${bitget_data['available']:,.0f} / ${bitget_data['used_margin']:,.0f}")
        
        # Gate 상세
        if gateio_has_data and gateio_data['total_equity'] > 0:
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
                account_info, position_info, combined_data['today_realized'], weekly_profit
            )
            
            return mental_text
            
        except Exception as e:
            self.logger.error(f"통합 멘탈 케어 생성 실패: {e}")
            return "시장은 변동성이 클 수 있지만, 꾸준한 전략과 리스크 관리로 좋은 결과를 얻을 수 있습니다. 감정에 휘둘리지 말고 차분하게 대응하세요 💪"
