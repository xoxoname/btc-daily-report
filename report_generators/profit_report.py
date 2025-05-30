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
            
            # 거래소별 포지션
            positions_text = await self._format_positions_by_exchange(bitget_data, gateio_data)
            
            # 수익 상세 테이블
            profit_table = self._format_profit_table(bitget_data, gateio_data, combined_data)
            
            # 멘탈 케어 - 통합 데이터 기반
            mental_text = await self._generate_combined_mental_care(combined_data)
            
            report = f"""💰 /profit 명령어 – 통합 손익 정보
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

💎 <b>통합 자산 현황</b>
{asset_summary}

━━━━━━━━━━━━━━━━━━━

📊 <b>거래소별 포지션</b>
{positions_text}

━━━━━━━━━━━━━━━━━━━

📈 <b>수익 상세</b>
{profit_table}

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
                'initial_capital': initial_capital
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
                futures_account = await self.gateio_client.get_futures_account()
                total_equity = float(futures_account.get('total', 0))
                
                # 디버깅을 위한 로그
                self.logger.info(f"Gate.io 계정 정보: {futures_account}")
                self.logger.info(f"Gate.io total_equity: {total_equity}")
            except Exception as e:
                self.logger.error(f"Gate.io 계정 조회 실패: {e}")
                total_equity = 0
            
            # Gate.io 자산이 0이어도 포지션 체크는 해야 함
            # Gate.io 포지션 조회
            position_info = {'has_position': False}
            try:
                positions = await self.gateio_client.get_positions('usdt')
                
                for pos in positions:
                    if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                        size = float(pos.get('size', 0))
                        entry_price = float(pos.get('entry_price', 0))
                        mark_price = float(pos.get('mark_price', 0))
                        unrealized_pnl = float(pos.get('unrealised_pnl', 0))
                        
                        position_info = {
                            'has_position': True,
                            'side': '롱' if size > 0 else '숏',
                            'size': abs(size),
                            'entry_price': entry_price,
                            'current_price': mark_price,
                            'unrealized_pnl': unrealized_pnl,
                            'contract_size': abs(size),
                            'leverage': 10,  # Gate.io 기본 레버리지 (실제로는 조회 필요)
                            'margin': abs(size) * entry_price / 10  # 추정치
                        }
                        break
            except Exception as e:
                self.logger.error(f"Gate.io 포지션 조회 실패: {e}")
            
            # Gate.io 초기 자산도 현재 자산으로 설정
            initial_capital_gateio = total_equity if total_equity > 0 else 0
            cumulative_profit = 0
            cumulative_roi = 0
            
            return {
                'exchange': 'Gate.io',
                'position_info': position_info,
                'account_info': {
                    'total_equity': total_equity,
                    'unrealized_pnl': position_info.get('unrealized_pnl', 0) if position_info['has_position'] else 0
                },
                'today_pnl': 0.0,  # 실제로는 계산 필요
                'weekly_profit': {'total': 0.0, 'average': 0.0},  # 실제로는 계산 필요
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': cumulative_roi,
                'total_equity': total_equity,
                'initial_capital': initial_capital_gateio,
                'has_account': True  # Gate.io 계정 존재 여부
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
            'account_info': {'total_equity': 0, 'unrealized_pnl': 0},
            'today_pnl': 0,
            'weekly_profit': {'total': 0, 'average': 0},
            'cumulative_profit': 0,
            'cumulative_roi': 0,
            'total_equity': 0,
            'initial_capital': 0,
            'has_account': False
        }
    
    def _calculate_combined_data(self, bitget_data: dict, gateio_data: dict) -> dict:
        """통합 데이터 계산"""
        # 총 자산
        total_equity = bitget_data['total_equity'] + gateio_data['total_equity']
        
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
        """통합 자산 현황 포맷"""
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        lines = [
            f"• <b>총 자산</b>: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)"
        ]
        
        # 거래소별 자산 (Gate.io 계정이 있는 경우)
        if combined_data.get('gateio_has_account', False):
            lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({bitget_equity * 1350 / 10000:.0f}만원)")
            lines.append(f"  └ Gate.io: ${gateio_equity:,.2f} ({gateio_equity * 1350 / 10000:.0f}만원)")
        
        # 금일 수익
        lines.append(f"• <b>금일 수익</b>: {self._format_currency_html(combined_data['today_total'], False)} ({combined_data['today_roi']:+.1f}%)")
        
        # 7일 수익
        lines.append(f"• <b>7일 수익</b>: {self._format_currency_html(combined_data['weekly_total'], False)} ({combined_data['weekly_roi']:+.1f}%)")
        
        return '\n'.join(lines)
    
    async def _format_positions_by_exchange(self, bitget_data: dict, gateio_data: dict) -> str:
        """거래소별 포지션 포맷"""
        lines = []
        
        # Bitget 포지션
        bitget_pos = bitget_data['position_info']
        if bitget_pos.get('has_position'):
            lines.append("【<b>Bitget</b>】")
            side = bitget_pos.get('side')
            entry = bitget_pos.get('entry_price', 0)
            current = bitget_pos.get('current_price', 0)
            pnl_rate = ((current - entry) / entry * 100) if entry > 0 else 0
            if side == '숏':
                pnl_rate = -pnl_rate
            
            # 실제 투입 금액
            margin = bitget_pos.get('margin', 0)
            leverage = bitget_pos.get('leverage', 1)
            actual_investment = margin / leverage if leverage > 0 else margin
            
            # 청산가와 거리
            liquidation_price = bitget_pos.get('liquidation_price', 0)
            if liquidation_price > 0:
                if side == '롱':
                    liq_distance = ((current - liquidation_price) / current * 100)
                else:
                    liq_distance = ((liquidation_price - current) / current * 100)
                liq_text = f"{abs(liq_distance):.1f}% {'하락' if side == '롱' else '상승'} 시 청산"
            else:
                liq_text = "계산불가"
            
            # 손익
            unrealized_pnl = bitget_pos.get('unrealized_pnl', 0)
            today_realized = bitget_data.get('today_pnl', 0)
            
            change_emoji = "📈" if pnl_rate > 0 else "📉" if pnl_rate < 0 else "➖"
            
            lines.append(f"• <b>종목</b>: BTCUSDT / {side}")
            lines.append(f"• <b>진입</b>: ${entry:,.2f} / 현재: ${current:,.0f} {change_emoji} ({pnl_rate:+.1f}%)")
            lines.append(f"• <b>실제 투입</b>: ${actual_investment:.2f} ({actual_investment * 1350 / 10000:.1f}만원)")
            lines.append(f"• <b>청산가</b>: ${liquidation_price:,.2f} ({liq_text})")
            lines.append(f"• <b>미실현</b>: {self._format_currency_html(unrealized_pnl)}")
            lines.append(f"• <b>금일 실현</b>: {self._format_currency_html(today_realized)}")
        else:
            lines.append("【<b>Bitget</b>】포지션 없음")
        
        # Gate.io 포지션 (계정이 있는 경우)
        if gateio_data.get('has_account', False):
            lines.append("")  # 구분선
            gateio_pos = gateio_data['position_info']
            if gateio_pos.get('has_position'):
                lines.append("【<b>Gate.io</b>】")
                side = gateio_pos.get('side')
                entry = gateio_pos.get('entry_price', 0)
                current = gateio_pos.get('current_price', 0)
                pnl_rate = ((current - entry) / entry * 100) if entry > 0 else 0
                if side == '숏':
                    pnl_rate = -pnl_rate
                
                # 실제 투입 금액 (추정)
                contract_size = gateio_pos.get('contract_size', 0)
                btc_size = contract_size * 0.0001  # 1계약 = 0.0001 BTC
                leverage = gateio_pos.get('leverage', 10)
                actual_investment = (btc_size * entry) / leverage
                
                # 손익
                unrealized_pnl = gateio_pos.get('unrealized_pnl', 0)
                today_realized = gateio_data.get('today_pnl', 0)
                
                change_emoji = "📈" if pnl_rate > 0 else "📉" if pnl_rate < 0 else "➖"
                
                lines.append(f"• <b>종목</b>: BTC_USDT / {side}")
                lines.append(f"• <b>진입</b>: ${entry:,.2f} / 현재: ${current:,.0f} {change_emoji} ({pnl_rate:+.1f}%)")
                lines.append(f"• <b>실제 투입</b>: ${actual_investment:.2f} ({actual_investment * 1350 / 10000:.1f}만원)")
                lines.append(f"• <b>계약 수</b>: {int(contract_size)}계약 ({btc_size:.4f} BTC)")
                lines.append(f"• <b>미실현</b>: {self._format_currency_html(unrealized_pnl)}")
                lines.append(f"• <b>금일 실현</b>: {self._format_currency_html(today_realized)}")
            else:
                lines.append("【<b>Gate.io</b>】포지션 없음")
        
        return '\n'.join(lines)
    
    def _format_profit_table(self, bitget_data: dict, gateio_data: dict, combined_data: dict) -> str:
        """수익 상세 테이블 포맷"""
        # 각 거래소별 수익률 계산
        bitget_today_roi = (bitget_data['today_pnl'] / bitget_data['total_equity'] * 100) if bitget_data['total_equity'] > 0 else 0
        bitget_weekly_roi = (bitget_data['weekly_profit']['total'] / bitget_data['total_equity'] * 100) if bitget_data['total_equity'] > 0 else 0
        
        gateio_today_roi = (gateio_data['today_pnl'] / gateio_data['total_equity'] * 100) if gateio_data['total_equity'] > 0 else 0
        gateio_weekly_roi = (gateio_data['weekly_profit']['total'] / gateio_data['total_equity'] * 100) if gateio_data['total_equity'] > 0 else 0
        
        lines = []
        
        # Bitget 행
        lines.append(
            f"<b>Bitget</b>\n"
            f"  <b>금일</b>: {self._format_currency_html(bitget_data['today_pnl'])} ({bitget_today_roi:+.1f}%)\n"
            f"  <b>7일</b>: {self._format_currency_html(bitget_data['weekly_profit']['total'])} ({bitget_weekly_roi:+.1f}%)\n"
            f"  <b>누적</b>: {self._format_currency_html(bitget_data['cumulative_profit'])} ({bitget_data['cumulative_roi']:+.1f}%)"
        )
        
        # Gate.io 행 (계정이 있는 경우만)
        if gateio_data.get('has_account', False):
            lines.append("")
            lines.append(
                f"<b>Gate.io</b>\n"
                f"  <b>금일</b>: {self._format_currency_html(gateio_data['today_pnl'])} ({gateio_today_roi:+.1f}%)\n"
                f"  <b>7일</b>: {self._format_currency_html(gateio_data['weekly_profit']['total'])} ({gateio_weekly_roi:+.1f}%)\n"
                f"  <b>누적</b>: {self._format_currency_html(gateio_data['cumulative_profit'])} ({gateio_data['cumulative_roi']:+.1f}%)"
            )
            lines.append("")
        
        # 합계 행
        lines.append(
            f"<b>통합 합계</b>\n"
            f"  <b>금일</b>: {self._format_currency_html(combined_data['today_total'])} ({combined_data['today_roi']:+.1f}%)\n"
            f"  <b>7일</b>: {self._format_currency_html(combined_data['weekly_total'])} ({combined_data['weekly_roi']:+.1f}%)\n"
            f"  <b>누적</b>: {self._format_currency_html(combined_data['cumulative_profit'])} ({combined_data['cumulative_roi']:+.1f}%)"
        )
        
        return '\n'.join(lines)
    
    def _format_currency_html(self, amount: float, include_krw: bool = True) -> str:
        """HTML용 통화 포맷팅"""
        usd_text = f"${amount:+,.2f}" if amount != 0 else "$0.00"
        if include_krw and amount != 0:
            krw_amount = amount * 1350 / 10000
            return f"{usd_text} ({krw_amount:+.1f}만원)"
        return usd_text
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        """통합 멘탈 케어 생성"""
        if not self.openai_client:
            return "시장은 예측 불가능하지만, 준비된 마음은 기회를 놓치지 않습니다. 오늘도 차분하게 접근하세요. 📊"
        
        try:
            # 상황 요약
            has_gateio = combined_data.get('gateio_has_account', False)
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
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            # 폴백
            if combined_data['weekly_roi'] > 10:
                return f"최근 7일간 {combined_data['weekly_roi']:.1f}%의 훌륭한 수익률을 기록하셨네요! 현재의 페이스를 유지하며 리스크 관리에 집중하세요. 🎯"
            else:
                return f"총 자산 ${int(combined_data['total_equity'])}을 안정적으로 운용중입니다. 꾸준함이 성공의 열쇠입니다. 💪"
