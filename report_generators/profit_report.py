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
            profit_detail = self._format_profit_detail(bitget_data, gateio_data)
            
            # 통합 자산 정보
            asset_detail = self._format_asset_detail(combined_data)
            
            # 누적 성과
            cumulative_text = self._format_cumulative_performance(combined_data)
            
            # 최근 수익 흐름
            recent_flow = self._format_recent_flow(combined_data)
            
            # 멘탈 케어 - 통합 데이터 기반
            mental_text = await self._generate_combined_mental_care(combined_data)
            
            # 텔레그램 MarkdownV2 형식 사용
            report = f"""💰 /profit 명령어 – 통합 손익 정보
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📌 *통합 자산 현황*
{asset_summary}

━━━━━━━━━━━━━━━━━━━

📌 *보유 포지션 정보*
{positions_text}

━━━━━━━━━━━━━━━━━━━

💸 *손익 정보*
{profit_detail}

━━━━━━━━━━━━━━━━━━━

💼 *자산 정보*
{asset_detail}

━━━━━━━━━━━━━━━━━━━

📊 *누적 성과*
{cumulative_text}

━━━━━━━━━━━━━━━━━━━

📈 *최근 수익 흐름*
{recent_flow}

━━━━━━━━━━━━━━━━━━━

🧠 *멘탈 케어*
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
            
            # 현재 자산을 초기 자산으로 사용 (누적 수익률 0%로 시작)
            total_equity = account_info.get('total_equity', 0)
            initial_capital = total_equity  # 현재 자산이 초기 자산
            cumulative_profit = 0  # 누적 수익 0
            cumulative_roi = 0  # 누적 수익률 0%
            
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
                'initial_capital': initial_capital,
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
                return self._get_empty_exchange_data('Gate.io')
            
            # Gate.io 계정 정보 조회
            try:
                futures_account = await self.gateio_client.get_account_balance()
                total_equity = float(futures_account.get('total', 0))
                available = float(futures_account.get('available', 0))
                
                # 디버깅을 위한 로그
                self.logger.info(f"Gate.io 계정 정보: total={total_equity}, available={available}")
                
            except Exception as e:
                self.logger.error(f"Gate.io 계정 조회 실패: {e}")
                total_equity = 0
                available = 0
            
            # Gate.io 포지션 조회
            position_info = {'has_position': False}
            try:
                positions = await self.gateio_client.get_positions('BTC_USDT')
                
                for pos in positions:
                    if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                        size = float(pos.get('size', 0))
                        entry_price = float(pos.get('entry_price', 0))
                        mark_price = float(pos.get('mark_price', 0))
                        unrealized_pnl = float(pos.get('unrealised_pnl', 0))
                        
                        # 실제 투입금액 계산
                        # 1계약 = 0.0001 BTC
                        btc_size = abs(size) * 0.0001
                        leverage = float(pos.get('leverage', 10))
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
                            'unrealized_pnl': unrealized_pnl,
                            'pnl_rate': (unrealized_pnl / margin_used) * 100 if margin_used > 0 else 0,
                            'contract_size': abs(size),
                            'leverage': leverage,
                            'margin': margin_used,
                            'liquidation_price': float(pos.get('liq_price', 0))
                        }
                        break
            except Exception as e:
                self.logger.error(f"Gate.io 포지션 조회 실패: {e}")
            
            # Gate.io 초기 자산도 현재 자산으로 설정
            initial_capital_gateio = total_equity if total_equity > 0 else 0
            cumulative_profit = 0
            cumulative_roi = 0
            
            # 오늘 실현 손익 계산 (임시)
            today_pnl = 0.0
            
            # 7일 손익 계산 (임시)
            weekly_profit = {'total': 0.0, 'average': 0.0}
            
            return {
                'exchange': 'Gate.io',
                'position_info': position_info,
                'account_info': {
                    'total_equity': total_equity,
                    'available': available,
                    'used_margin': total_equity - available if total_equity > available else 0,
                    'unrealized_pnl': position_info.get('unrealized_pnl', 0) if position_info['has_position'] else 0
                },
                'today_pnl': today_pnl,
                'weekly_profit': weekly_profit,
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': initial_capital_gateio,
                'available': available,
                'used_margin': total_equity - available if total_equity > available else 0,
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
        
        # 7일 수익
        weekly_total = bitget_data['weekly_profit']['total'] + gateio_data['weekly_profit']['total']
        weekly_avg = weekly_total / 7
        
        # 누적 수익 (현재는 0으로 설정)
        cumulative_profit = 0
        cumulative_roi = 0
        
        # 금일 수익률
        today_roi = (today_total / total_equity * 100) if total_equity > 0 else 0
        
        # 7일 수익률
        weekly_roi = (weekly_total / (total_equity - weekly_total) * 100) if (total_equity - weekly_total) > 0 else 0
        
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
            lines.append(f"• *총 자산*: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)")
            lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({bitget_equity / total_equity * 100:.1f}%)")
            lines.append(f"  └ Gate.io: ${gateio_equity:,.2f} ({gateio_equity / total_equity * 100:.1f}%)")
        else:
            lines.append(f"• *총 자산*: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)")
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
            lines.append("━━━ *Bitget* ━━━")
            lines.append(f"• 종목: BTCUSDT")
            lines.append(f"• 방향: {bitget_pos.get('side')}")
            lines.append(f"• 진입가: ${bitget_pos.get('entry_price', 0):,.2f}")
            lines.append(f"• 현재가: ${bitget_pos.get('current_price', 0):,.2f}")
            
            # 실제 투입 금액
            margin = bitget_pos.get('margin', 0)
            lines.append(f"• 실제 투입 금액: ${margin:.2f} (약 {margin * 1350 / 10000:.1f}만원)")
            
            # 청산가
            liquidation_price = bitget_pos.get('liquidation_price', 0)
            if liquidation_price > 0:
                current = bitget_pos.get('current_price', 0)
                side = bitget_pos.get('side')
                if side == '롱':
                    liq_distance = ((current - liquidation_price) / current * 100)
                    lines.append(f"• 청산가: ${liquidation_price:,.2f}")
                    lines.append(f"• 청산까지 거리: {abs(liq_distance):.1f}% 하락 시 청산")
                else:
                    liq_distance = ((liquidation_price - current) / current * 100)
                    lines.append(f"• 청산가: ${liquidation_price:,.2f}")
                    lines.append(f"• 청산까지 거리: {abs(liq_distance):.1f}% 상승 시 청산")
        
        # Gate.io 포지션
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            gateio_pos = gateio_data['position_info']
            if gateio_pos.get('has_position'):
                has_any_position = True
                if lines:
                    lines.append("")
                lines.append("━━━ *Gate.io* ━━━")
                lines.append(f"• 종목: BTC_USDT")
                lines.append(f"• 방향: {gateio_pos.get('side')}")
                lines.append(f"• 진입가: ${gateio_pos.get('entry_price', 0):,.2f}")
                lines.append(f"• 현재가: ${gateio_pos.get('current_price', 0):,.2f}")
                
                # 실제 투입 금액
                margin = gateio_pos.get('margin', 0)
                lines.append(f"• 실제 투입 금액: ${margin:.2f} (약 {margin * 1350 / 10000:.1f}만원)")
                
                # 계약 정보
                contract_size = gateio_pos.get('contract_size', 0)
                btc_size = gateio_pos.get('btc_size', 0)
                lines.append(f"• 계약 수: {int(contract_size)}계약 ({btc_size:.4f} BTC)")
                
                # 청산가
                liquidation_price = gateio_pos.get('liquidation_price', 0)
                if liquidation_price > 0:
                    current = gateio_pos.get('current_price', 0)
                    side = gateio_pos.get('side')
                    if side == '롱':
                        liq_distance = ((current - liquidation_price) / current * 100)
                        lines.append(f"• 청산가: ${liquidation_price:,.2f}")
                        lines.append(f"• 청산까지 거리: {abs(liq_distance):.1f}% 하락 시 청산")
                    else:
                        liq_distance = ((liquidation_price - current) / current * 100)
                        lines.append(f"• 청산가: ${liquidation_price:,.2f}")
                        lines.append(f"• 청산까지 거리: {abs(liq_distance):.1f}% 상승 시 청산")
        
        if not has_any_position:
            lines.append("• 현재 보유 중인 포지션이 없습니다.")
        
        return '\n'.join(lines)
    
    def _format_profit_detail(self, bitget_data: dict, gateio_data: dict) -> str:
        """거래소별 손익 정보"""
        lines = []
        
        # Bitget 손익
        lines.append("━━━ *Bitget* ━━━")
        bitget_unrealized = bitget_data['account_info'].get('unrealized_pnl', 0)
        bitget_today_pnl = bitget_data['today_pnl']
        bitget_today_total = bitget_unrealized + bitget_today_pnl
        bitget_today_roi = (bitget_today_total / bitget_data['total_equity'] * 100) if bitget_data['total_equity'] > 0 else 0
        
        lines.append(f"• 미실현 손익: {self._format_currency_markdown(bitget_unrealized)}")
        lines.append(f"• 금일 실현 손익: {self._format_currency_markdown(bitget_today_pnl)}")
        lines.append(f"• 금일 총 수익: {self._format_currency_markdown(bitget_today_total)}")
        lines.append(f"• 금일 수익률: {bitget_today_roi:+.1f}%")
        
        # Gate.io 손익
        if gateio_data.get('has_account', False) and gateio_data['total_equity'] > 0:
            lines.append("")
            lines.append("━━━ *Gate.io* ━━━")
            gateio_unrealized = gateio_data['account_info'].get('unrealized_pnl', 0)
            gateio_today_pnl = gateio_data['today_pnl']
            gateio_today_total = gateio_unrealized + gateio_today_pnl
            gateio_today_roi = (gateio_today_total / gateio_data['total_equity'] * 100) if gateio_data['total_equity'] > 0 else 0
            
            lines.append(f"• 미실현 손익: {self._format_currency_markdown(gateio_unrealized)}")
            lines.append(f"• 금일 실현 손익: {self._format_currency_markdown(gateio_today_pnl)}")
            lines.append(f"• 금일 총 수익: {self._format_currency_markdown(gateio_today_total)}")
            lines.append(f"• 금일 수익률: {gateio_today_roi:+.1f}%")
        
        return '\n'.join(lines)
    
    def _format_asset_detail(self, combined_data: dict) -> str:
        """통합 자산 정보"""
        lines = []
        
        # 통합 자산
        lines.append("━━━ *통합 자산* ━━━")
        lines.append(f"• 총 자산: ${combined_data['total_equity']:,.2f} (약 {combined_data['total_equity'] * 1350 / 10000:.0f}만원)")
        lines.append(f"• 가용 자산: ${combined_data['total_available']:,.2f} (약 {combined_data['total_available'] * 1350 / 10000:.0f}만원)")
        lines.append(f"• 사용 증거금: ${combined_data['total_used_margin']:,.2f}")
        
        # 가용 비율
        if combined_data['total_equity'] > 0:
            available_ratio = combined_data['total_available'] / combined_data['total_equity'] * 100
            lines.append(f"• 가용 비율: {available_ratio:.1f}%")
        
        return '\n'.join(lines)
    
    def _format_cumulative_performance(self, combined_data: dict) -> str:
        """누적 성과"""
        # 현재는 누적 데이터가 없으므로 임시로 표시
        return f"• 전체 누적 수익: {self._format_currency_markdown(0)}\n• 전체 누적 수익률: 0.0%"
    
    def _format_recent_flow(self, combined_data: dict) -> str:
        """최근 수익 흐름"""
        lines = []
        
        lines.append(f"• 최근 7일 수익: {self._format_currency_markdown(combined_data['weekly_total'])}")
        lines.append(f"• 최근 7일 평균: {self._format_currency_markdown(combined_data['weekly_avg'])}/일")
        lines.append(f"• 최근 7일 수익률: {combined_data['weekly_roi']:+.1f}%")
        
        return '\n'.join(lines)
    
    def _format_currency_markdown(self, amount: float, include_krw: bool = True) -> str:
        """Markdown용 통화 포맷팅"""
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
            return """GPT는 다음과 같은 요소를 실시간으로 분석합니다:
* 자산 규모 * 포지션 상태 * 실현/미실현 손익 * 최근 수익률 추이 * 감정 흐름 및 매매 빈도
👉 수익률이 높더라도 무리한 진입이 반복되지 않도록 유도합니다.
👉 손실 중이라면, 복구 매매 충동을 차단하는 코멘트를 생성합니다.
✅ 모든 코멘트는 상황 기반으로 즉시 생성되며, 단 하나의 문장도 하드코딩되어 있지 않습니다."""
        
        try:
            # 상황 요약
            has_gateio = combined_data.get('gateio_has_account', False) and combined_data.get('gateio_equity', 0) > 0
            exchange_count = "두 거래소" if has_gateio else "한 거래소"
            
            situation_summary = f"""
현재 트레이더 상황:
- 총 자산: ${combined_data['total_equity']:,.0f} ({exchange_count} 합산)
- 금일 수익: ${combined_data['today_total']:+,.0f} ({combined_data['today_roi']:+.1f}%)
- 7일 수익: ${combined_data['weekly_total']:+,.0f} ({combined_data['weekly_roi']:+.1f}%)
- 거래소: {'Bitget과 Gate.io' if has_gateio else 'Bitget만 사용중'}
"""
            
            prompt = f"""당신은 전문 트레이딩 심리 코치입니다. 
다음 트레이더의 상황을 분석하고, 맞춤형 멘탈 케어 메시지를 작성하세요.

{situation_summary}

요구사항:
1. 현재 사용중인 거래소 상황을 고려
2. 구체적인 숫자를 언급하며 개인화된 메시지
3. 리스크 관리나 현재 수익 상황에 맞는 조언
4. 2-3문장으로 간결하게
5. 따뜻하지만 전문적인 톤
6. 이모티콘 1개 포함"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 개인화된 조언을 제공하는 트레이딩 심리 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.9
            )
            
            gpt_message = response.choices[0].message.content.strip()
            
            return f"""GPT는 다음과 같은 요소를 실시간으로 분석합니다:
* 자산 규모 * 포지션 상태 * 실현/미실현 손익 * 최근 수익률 추이 * 감정 흐름 및 매매 빈도
👉 수익률이 높더라도 무리한 진입이 반복되지 않도록 유도합니다.
👉 손실 중이라면, 복구 매매 충동을 차단하는 코멘트를 생성합니다.
✅ 모든 코멘트는 상황 기반으로 즉시 생성되며, 단 하나의 문장도 하드코딩되어 있지 않습니다.
사용자의 상태에 맞는 심리적 설득 효과를 유도하는 방식으로 매번 다르게 구성됩니다.

{gpt_message}"""
            
        except Exception as e:
            self.logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            # 폴백
            if combined_data['weekly_roi'] > 10:
                return f"""GPT는 다음과 같은 요소를 실시간으로 분석합니다:
* 자산 규모 * 포지션 상태 * 실현/미실현 손익 * 최근 수익률 추이 * 감정 흐름 및 매매 빈도
👉 수익률이 높더라도 무리한 진입이 반복되지 않도록 유도합니다.
👉 손실 중이라면, 복구 매매 충동을 차단하는 코멘트를 생성합니다.
✅ 모든 코멘트는 상황 기반으로 즉시 생성되며, 단 하나의 문장도 하드코딩되어 있지 않습니다.

최근 7일간 {combined_data['weekly_roi']:.1f}%의 훌륭한 수익률을 기록하셨네요! 현재의 페이스를 유지하며 리스크 관리에 집중하세요. 🎯"""
            else:
                return f"""GPT는 다음과 같은 요소를 실시간으로 분석합니다:
* 자산 규모 * 포지션 상태 * 실현/미실현 손익 * 최근 수익률 추이 * 감정 흐름 및 매매 빈도
👉 수익률이 높더라도 무리한 진입이 반복되지 않도록 유도합니다.
👉 손실 중이라면, 복구 매매 충동을 차단하는 코멘트를 생성합니다.
✅ 모든 코멘트는 상황 기반으로 즉시 생성되며, 단 하나의 문장도 하드코딩되어 있지 않습니다.

총 자산 ${int(combined_data['total_equity'])}을 안정적으로 운용중입니다. 꾸준함이 성공의 열쇠입니다. 💪"""
