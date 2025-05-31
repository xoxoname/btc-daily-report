# report_generators/profit_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback

class ProfitReportGenerator(BaseReportGenerator):
    """수익 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.gateio_client = None  # Gate.io 클라이언트 추가
    
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
            recent_flow = self._format_recent_flow(combined_data)
            
            # 멘탈 케어 - 통합 데이터 기반
            mental_text = await self._generate_combined_mental_care(combined_data)
            
            report = f"""💰 /profit 명령어 – 통합 손익 정보
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📌 <b>통합 자산 현황</b>
{asset_summary}

━━━━━━━━━━━━━━━━━━━

📌 <b>보유 포지션 정보</b>
{positions_text}

━━━━━━━━━━━━━━━━━━━

💸 <b>손익 정보</b>
{profit_detail}

━━━━━━━━━━━━━━━━━━━

💼 <b>자산 정보</b>
{asset_detail}

━━━━━━━━━━━━━━━━━━━

📊 <b>누적 성과</b>
{cumulative_text}

━━━━━━━━━━━━━━━━━━━

📈 <b>최근 수익 흐름</b>
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
        """Bitget 데이터 조회"""
        try:
            # 기존 코드 재사용
            market_data = await self._get_market_data()
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            today_pnl = await self._get_today_realized_pnl()
            weekly_profit = await self._get_weekly_profit()
            
            # 7일 수익 데이터 사용
            cumulative_profit = weekly_profit.get('total', 0)
            total_equity = account_info.get('total_equity', 0)
            
            # 누적 수익률 계산 (7일 수익 기준)
            if total_equity > cumulative_profit:
                cumulative_roi = (cumulative_profit / (total_equity - cumulative_profit)) * 100
            else:
                cumulative_roi = 0
            
            return {
                'exchange': 'Bitget',
                'market_data': market_data,
                'position_info': position_info,
                'account_info': account_info,
                'today_pnl': today_pnl,
                'weekly_profit': weekly_profit,
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': total_equity - cumulative_profit,
                'available': account_info.get('available', 0),
                'used_margin': account_info.get('used_margin', 0)
            }
        except Exception as e:
            self.logger.error(f"Bitget 데이터 조회 실패: {e}")
            return self._get_empty_exchange_data('Bitget')
    
    async def _get_gateio_data(self) -> dict:
        """Gate.io 데이터 조회"""
        try:
            # Gate.io 클라이언트가 없는 경우
            if not self.gateio_client:
                self.logger.info("Gate.io 클라이언트가 설정되지 않음")
                return self._get_empty_exchange_data('Gate.io')
            
            # Gate.io 계정 정보 조회
            try:
                account_response = await self.gateio_client.get_account_balance()
                self.logger.info(f"Gate.io 계정 응답: {account_response}")
                
                total_equity = float(account_response.get('total', 0))
                available = float(account_response.get('available', 0))
                
                # 미실현 손익
                unrealized_pnl = float(account_response.get('unrealised_pnl', 0))
                
            except Exception as e:
                self.logger.error(f"Gate.io 계정 조회 실패: {e}")
                total_equity = 0
                available = 0
                unrealized_pnl = 0
            
            # Gate.io 포지션 조회
            position_info = {'has_position': False}
            try:
                positions = await self.gateio_client.get_positions('BTC_USDT')
                self.logger.info(f"Gate.io 포지션 정보: {positions}")
                
                for pos in positions:
                    if float(pos.get('size', 0)) != 0:
                        size = float(pos.get('size', 0))
                        entry_price = float(pos.get('entry_price', 0))
                        mark_price = float(pos.get('mark_price', 0))
                        pos_unrealized_pnl = float(pos.get('unrealised_pnl', 0))
                        leverage = float(pos.get('leverage', 10))
                        
                        # 실제 투입금액 계산
                        # 1계약 = 0.0001 BTC
                        btc_size = abs(size) * 0.0001
                        margin_used = btc_size * entry_price / leverage
                        
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
                            'pnl_rate': (pos_unrealized_pnl / margin_used) * 100 if margin_used > 0 else 0,
                            'contract_size': abs(size),
                            'leverage': leverage,
                            'margin': margin_used,
                            'liquidation_price': float(pos.get('liq_price', 0))
                        }
                        break
            except Exception as e:
                self.logger.error(f"Gate.io 포지션 조회 실패: {e}")
            
            # 사용 증거금 계산
            used_margin = position_info.get('margin', 0) if position_info['has_position'] else 0
            
            # Gate.io 7일 손익 (향후 구현)
            weekly_profit = {'total': 0.0, 'average': 0.0}
            cumulative_profit = 0
            cumulative_roi = 0
            
            # 오늘 실현 손익 계산 (향후 구현)
            today_pnl = 0.0
            
            return {
                'exchange': 'Gate.io',
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
                'initial_capital': total_equity,
                'available': available,
                'used_margin': used_margin,
                'has_account': total_equity > 0  # Gate.io 계정 존재 여부
            }
            
        except Exception as e:
            self.logger.error(f"Gate.io 데이터 조회 실패: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return self._get_empty_exchange_data('Gate.io')
    
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
        
        # 누적 수익 (전체 기간 - 현재는 7일 데이터만 있음)
        cumulative_profit = bitget_data['cumulative_profit'] + gateio_data['cumulative_profit']
        
        # 금일 수익률
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        # 7일 수익률
        if total_equity > weekly_total:
            weekly_roi = (weekly_total / (total_equity - weekly_total)) * 100
        else:
            weekly_roi = 0
        
        # 누적 수익률
        if total_equity > cumulative_profit:
            cumulative_roi = (cumulative_profit / (total_equity - cumulative_profit)) * 100
        else:
            cumulative_roi = 0
        
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
            'gateio_has_account': gateio_data.get('has_account', False)
        }
    
    def _format_asset_summary(self, combined_data: dict) -> str:
        """통합 자산 현황 요약"""
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        lines = []
        
        # Gate.io 계정이 있는 경우
        if combined_data.get('gateio_has_account', False) and gateio_equity > 0:
            lines.append(f"• <b>총 자산</b>: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)")
            lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({bitget_equity / total_equity * 100:.1f}%)")
            lines.append(f"  └ Gate.io: ${gateio_equity:,.2f} ({gateio_equity / total_equity * 100:.1f}%)")
        else:
            lines.append(f"• <b>총 자산</b>: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)")
            lines.append(f"  └ Bitget: ${bitget_equity:,.2f} (100.0%)")
        
        return '\n'.join(lines)
    
    async def _format_positions_detail(self, bitget_data: dict, gateio_data: dict) -> str:
        """거래소별 포지션 상세 정보"""
        lines = []
        has_any_position = False
        
        # Bitget 포지션
        bitget_pos = bitget_data['position_info']
        if bitget_pos.get('has_position'):
            has_any_position = True
            lines.append("━━━ <b>Bitget</b> ━━━")
            lines.append(f"• 종목: BTCUSDT")
            lines.append(f"• 방향: {bitget_pos.get('side')}")
            lines.append(f"• 진입가: ${bitget_pos.get('entry_price', 0):,.2f}")
            lines.append(f"• 현재가: ${bitget_pos.get('current_price', 0):,.2f}")
            lines.append(f"• 투입 금액: ${bitget_pos.get('margin', 0):.2f} (약 {bitget_pos.get('margin', 0) * 1350 / 10000:.1f}만원)")
            
            # 청산가
            liquidation_price = bitget_pos.get('liquidation_price', 0)
            if liquidation_price > 0:
                current = bitget_pos.get('current_price', 0)
                side = bitget_pos.get('side')
                if side == '롱':
                    liq_distance = ((current - liquidation_price) / current * 100)
                    lines.append(f"• 청산가: ${liquidation_price:,.2f} ({abs(liq_distance):.1f}% 하락 시)")
                else:
                    liq_distance = ((liquidation_price - current) / current * 100)
                    lines.append(f"• 청산가: ${liquidation_price:,.2f} ({abs(liq_distance):.1f}% 상승 시)")
        
        # Gate.io 포지션
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            gateio_pos = gateio_data['position_info']
            if gateio_pos.get('has_position'):
                has_any_position = True
                if lines:
                    lines.append("")
                lines.append("━━━ <b>Gate.io</b> ━━━")
                lines.append(f"• 종목: BTC_USDT")
                lines.append(f"• 방향: {gateio_pos.get('side')}")
                lines.append(f"• 진입가: ${gateio_pos.get('entry_price', 0):,.2f}")
                lines.append(f"• 현재가: ${gateio_pos.get('current_price', 0):,.2f}")
                lines.append(f"• 투입 금액: ${gateio_pos.get('margin', 0):.2f} (약 {gateio_pos.get('margin', 0) * 1350 / 10000:.1f}만원)")
                lines.append(f"• 계약: {int(gateio_pos.get('contract_size', 0))}계약 ({gateio_pos.get('btc_size', 0):.4f} BTC)")
                
                # 청산가
                liquidation_price = gateio_pos.get('liquidation_price', 0)
                if liquidation_price > 0:
                    current = gateio_pos.get('current_price', 0)
                    side = gateio_pos.get('side')
                    if side == '롱':
                        liq_distance = ((current - liquidation_price) / current * 100)
                        lines.append(f"• 청산가: ${liquidation_price:,.2f} ({abs(liq_distance):.1f}% 하락 시)")
                    else:
                        liq_distance = ((liquidation_price - current) / current * 100)
                        lines.append(f"• 청산가: ${liquidation_price:,.2f} ({abs(liq_distance):.1f}% 상승 시)")
        
        if not has_any_position:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_profit_detail(self, bitget_data: dict, gateio_data: dict, combined_data: dict) -> str:
        """손익 정보 - 통합 요약 + 거래소별 상세"""
        lines = []
        
        # 통합 손익 요약
        lines.append("━━━ <b>통합 손익</b> ━━━")
        lines.append(f"• 금일 총 수익: {self._format_currency_html(combined_data['today_total'])}")
        lines.append(f"• 금일 수익률: {combined_data['today_roi']:+.1f}%")
        
        # Bitget 상세
        lines.append("")
        lines.append("━━━ <b>Bitget</b> ━━━")
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0)
        bitget_today_pnl = bitget_data['today_pnl']
        lines.append(f"• 미실현: {self._format_currency_html(bitget_unrealized, False)}")
        lines.append(f"• 실현: {self._format_currency_html(bitget_today_pnl, False)}")
        
        # Gate.io 상세
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            lines.append("")
            lines.append("━━━ <b>Gate.io</b> ━━━")
            gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0)
            gateio_today_pnl = gateio_data['today_pnl']
            lines.append(f"• 미실현: {self._format_currency_html(gateio_unrealized, False)}")
            lines.append(f"• 실현: {self._format_currency_html(gateio_today_pnl, False)}")
        
        return '\n'.join(lines)
    
    def _format_asset_detail(self, combined_data: dict, bitget_data: dict, gateio_data: dict) -> str:
        """자산 정보 - 통합 + 거래소별 가용/증거금"""
        lines = []
        
        # 통합 자산
        lines.append("━━━ <b>통합 자산</b> ━━━")
        lines.append(f"• 총 자산: ${combined_data['total_equity']:,.2f}")
        lines.append(f"• 가용 자산: ${combined_data['total_available']:,.2f}")
        lines.append(f"• 사용 증거금: ${combined_data['total_used_margin']:,.2f}")
        lines.append(f"• 가용 비율: {combined_data['total_available'] / combined_data['total_equity'] * 100:.1f}%")
        
        # Bitget 상세
        lines.append("")
        lines.append("━━━ <b>Bitget</b> ━━━")
        lines.append(f"• 자산: ${bitget_data['total_equity']:,.2f}")
        lines.append(f"• 가용: ${bitget_data['available']:,.2f}")
        lines.append(f"• 증거금: ${bitget_data['used_margin']:,.2f}")
        
        # Gate.io 상세
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            lines.append("")
            lines.append("━━━ <b>Gate.io</b> ━━━")
            lines.append(f"• 자산: ${gateio_data['total_equity']:,.2f}")
            lines.append(f"• 가용: ${gateio_data['available']:,.2f}")
            lines.append(f"• 증거금: ${gateio_data['used_margin']:,.2f}")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance(self, combined_data: dict, bitget_data: dict, gateio_data: dict) -> str:
        """누적 성과 - 전체 기간 (현재는 7일 데이터만)"""
        # 통합 누적 수익
        total_cumulative = combined_data['cumulative_profit']
        total_cumulative_roi = combined_data['cumulative_roi']
        
        lines = []
        lines.append(f"• <b>전체 누적 수익</b>: {self._format_currency_html(total_cumulative)}")
        lines.append(f"• <b>전체 누적 수익률</b>: {total_cumulative_roi:+.1f}%")
        
        # 거래소별 상세
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            lines.append("")
            lines.append(f"  ├ Bitget: {self._format_currency_html(bitget_data['cumulative_profit'], False)}")
            lines.append(f"  └ Gate.io: {self._format_currency_html(gateio_data['cumulative_profit'], False)}")
        
        return '\n'.join(lines)
    
    def _format_recent_flow(self, combined_data: dict) -> str:
        """최근 수익 흐름 - 통합"""
        lines = []
        
        # 통합 7일 수익
        lines.append(f"• <b>7일 수익</b>: {self._format_currency_html(combined_data['weekly_total'])}")
        lines.append(f"• <b>일평균</b>: {self._format_currency_html(combined_data['weekly_avg'])}/일")
        lines.append(f"• <b>7일 수익률</b>: {combined_data['weekly_roi']:+.1f}%")
        
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
            krw_amount = abs(amount) * 1350 / 10000
            if amount > 0:
                return f"{usd_text} (약 +{krw_amount:.1f}만원)"
            else:
                return f"{usd_text} (약 -{krw_amount:.1f}만원)"
        return usd_text
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        """통합 멘탈 케어 생성"""
        if not self.openai_client:
            # GPT가 없을 때 기본 메시지
            if combined_data['weekly_roi'] > 10:
                return f'"최근 7일간 {combined_data["weekly_roi"]:.1f}%의 훌륭한 수익률을 기록하셨네요! 현재의 페이스를 유지하며 리스크 관리에 집중하세요. 🎯"'
            elif combined_data['today_roi'] > 0:
                return f'"오늘 ${combined_data["today_total"]:.0f}을 벌어들였군요! 꾸준한 수익이 복리의 힘을 만듭니다. 감정적 거래를 피하고 시스템을 따르세요. 💪"'
            else:
                return f'"총 자산 ${int(combined_data["total_equity"])}을 안정적으로 운용중입니다. 손실은 성장의 일부입니다. 차분한 마음으로 다음 기회를 준비하세요. 🧘‍♂️"'
        
        try:
            # 상황 요약
            has_gateio = combined_data.get('gateio_has_account', False) and combined_data.get('gateio_equity', 0) > 0
            
            situation_summary = f"""
현재 트레이더 상황:
- 총 자산: ${combined_data['total_equity']:,.0f}
- 금일 수익: ${combined_data['today_total']:+,.0f} ({combined_data['today_roi']:+.1f}%)
- 7일 수익: ${combined_data['weekly_total']:+,.0f} ({combined_data['weekly_roi']:+.1f}%)
- 사용 증거금: ${combined_data['total_used_margin']:,.0f}
- 가용 자산: ${combined_data['total_available']:,.0f}
"""
            
            prompt = f"""당신은 전문 트레이딩 심리 코치입니다. 
다음 트레이더의 상황을 분석하고, 맞춤형 멘탈 케어 메시지를 작성하세요.

{situation_summary}

요구사항:
1. 구체적인 숫자(자산, 수익)를 언급하며 개인화된 메시지
2. 현재 수익 상황에 맞는 조언 (수익 중이면 과욕 경계, 손실 중이면 회복 시도 차단)
3. 2-3문장으로 간결하게
4. 따뜻하지만 전문적인 톤
5. 이모티콘 1개 포함
6. "반갑습니다", "Bitget에서의", "화이팅하세요" 같은 표현 금지
7. 통합 자산과 전체 수익을 기준으로 분석"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 트레이더의 현재 상황에 맞는 심리적 조언을 제공하는 전문가입니다. 인사말이나 격려보다는 구체적인 상황 분석과 행동 지침을 제공하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            gpt_message = response.choices[0].message.content.strip()
            
            # GPT 응답에서 금지 표현 제거
            forbidden_phrases = ["반갑습니다", "Bitget에서의", "화이팅하세요", "화이팅", "안녕하세요"]
            for phrase in forbidden_phrases:
                gpt_message = gpt_message.replace(phrase, "")
            
            gpt_message = gpt_message.strip()
            
            # 따옴표로 감싸기
            if not gpt_message.startswith('"'):
                gpt_message = f'"{gpt_message}"'
            
            return gpt_message
            
        except Exception as e:
            self.logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            # 폴백 메시지
            if combined_data['weekly_roi'] > 10:
                return f'"최근 7일간 {combined_data["weekly_roi"]:.1f}%의 훌륭한 수익률을 기록하셨네요! 현재의 페이스를 유지하며 리스크 관리에 집중하세요. 🎯"'
            elif combined_data['today_roi'] > 0:
                return f'"오늘 ${combined_data["today_total"]:.0f}을 벌어들였군요! 꾸준한 수익이 복리의 힘을 만듭니다. 감정적 거래를 피하고 시스템을 따르세요. 💪"'
            else:
                return f'"총 자산 ${int(combined_data["total_equity"])}을 안정적으로 운용중입니다. 손실은 성장의 일부입니다. 차분한 마음으로 다음 기회를 준비하세요. 🧘‍♂️"'
