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

💎 **통합 자산 현황**
{asset_summary}

━━━━━━━━━━━━━━━━━━━

📊 **거래소별 포지션**
{positions_text}

━━━━━━━━━━━━━━━━━━━

📈 **수익 상세**
{profit_table}

━━━━━━━━━━━━━━━━━━━

🧠 **멘탈 케어**
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
            
            # 초기 자산 계산
            initial_capital = 4000
            total_equity = account_info.get('total_equity', initial_capital)
            cumulative_profit = total_equity - initial_capital
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            
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
            # Gate.io 클라이언트가 없거나 비활성화된 경우
            if not self.gateio_client:
                return self._get_empty_exchange_data('Gate.io')
            
            # Gate.io 계정 정보 조회
            futures_account = await self.gateio_client.get_futures_account()
            total_equity = float(futures_account.get('total', 0))
            
            # Gate.io 포지션 조회
            positions = await self.gateio_client.get_positions('usdt')
            active_position = None
            
            for pos in positions:
                if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                    active_position = pos
                    break
            
            # 포지션 정보 포맷
            position_info = {'has_position': False}
            if active_position:
                size = float(active_position.get('size', 0))
                entry_price = float(active_position.get('entry_price', 0))
                mark_price = float(active_position.get('mark_price', 0))
                unrealized_pnl = float(active_position.get('unrealised_pnl', 0))
                
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
            
            # Gate.io는 간단한 수익 계산 (실제로는 API 통해 조회 필요)
            # 여기서는 예시값 사용
            initial_capital_gateio = 3200  # Gate.io 초기 자산
            cumulative_profit = total_equity - initial_capital_gateio
            
            return {
                'exchange': 'Gate.io',
                'position_info': position_info,
                'account_info': {
                    'total_equity': total_equity,
                    'unrealized_pnl': position_info.get('unrealized_pnl', 0) if position_info['has_position'] else 0
                },
                'today_pnl': 100.0,  # 예시값 (실제로는 계산 필요)
                'weekly_profit': {'total': 400.0, 'average': 57.14},  # 예시값
                'cumulative_profit': cumulative_profit,
                'cumulative_roi': (cumulative_profit / initial_capital_gateio * 100) if initial_capital_gateio > 0 else 0,
                'total_equity': total_equity,
                'initial_capital': initial_capital_gateio
            }
            
        except Exception as e:
            self.logger.error(f"Gate.io 데이터 조회 실패: {e}")
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
            'initial_capital': 0
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
        
        # 누적 수익
        cumulative_profit = bitget_data['cumulative_profit'] + gateio_data['cumulative_profit']
        initial_capital_total = bitget_data['initial_capital'] + gateio_data['initial_capital']
        cumulative_roi = (cumulative_profit / initial_capital_total * 100) if initial_capital_total > 0 else 0
        
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
            'gateio_equity': gateio_data['total_equity']
        }
    
    def _format_asset_summary(self, combined_data: dict) -> str:
        """통합 자산 현황 포맷"""
        total_equity = combined_data['total_equity']
        bitget_equity = combined_data['bitget_equity']
        gateio_equity = combined_data['gateio_equity']
        
        lines = [
            f"• **총 자산**: ${total_equity:,.2f} (약 {total_equity * 1350 / 10000:.0f}만원)"
        ]
        
        # 거래소별 자산 (Gate.io가 있는 경우만)
        if gateio_equity > 0:
            lines.append(f"  ├ Bitget: ${bitget_equity:,.2f} ({bitget_equity * 1350 / 10000:.0f}만원)")
            lines.append(f"  └ Gate.io: ${gateio_equity:,.2f} ({gateio_equity * 1350 / 10000:.0f}만원)")
        
        # 금일 수익
        lines.append(f"• **금일 수익**: {self._format_currency(combined_data['today_total'], False)} ({combined_data['today_roi']:+.1f}%)")
        
        # 7일 수익
        lines.append(f"• **7일 수익**: {self._format_currency(combined_data['weekly_total'], False)} ({combined_data['weekly_roi']:+.1f}%)")
        
        return '\n'.join(lines)
    
    async def _format_positions_by_exchange(self, bitget_data: dict, gateio_data: dict) -> str:
        """거래소별 포지션 포맷"""
        lines = []
        
        # Bitget 포지션
        bitget_pos = bitget_data['position_info']
        if bitget_pos.get('has_position'):
            lines.append("【**Bitget**】")
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
            
            lines.append(f"• 종목: BTCUSDT / {side}")
            lines.append(f"• 진입: ${entry:,.2f} / 현재: ${current:,.0f} {change_emoji} ({pnl_rate:+.1f}%)")
            lines.append(f"• 실제 투입: ${actual_investment:.2f} ({actual_investment * 1350 / 10000:.1f}만원)")
            lines.append(f"• 청산가: ${liquidation_price:,.2f} ({liq_text})")
            lines.append(f"• 미실현: {self._format_currency(unrealized_pnl)}")
            lines.append(f"• 금일 실현: {self._format_currency(today_realized)}")
        else:
            lines.append("【**Bitget**】포지션 없음")
        
        # Gate.io 포지션
        if gateio_data['total_equity'] > 0:
            lines.append("")  # 구분선
            gateio_pos = gateio_data['position_info']
            if gateio_pos.get('has_position'):
                lines.append("【**Gate.io**】")
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
                
                lines.append(f"• 종목: BTC_USDT / {side}")
                lines.append(f"• 진입: ${entry:,.2f} / 현재: ${current:,.0f} {change_emoji} ({pnl_rate:+.1f}%)")
                lines.append(f"• 실제 투입: ${actual_investment:.2f} ({actual_investment * 1350 / 10000:.1f}만원)")
                lines.append(f"• 계약 수: {int(contract_size)}계약 ({btc_size:.4f} BTC)")
                lines.append(f"• 미실현: {self._format_currency(unrealized_pnl)}")
                lines.append(f"• 금일 실현: {self._format_currency(today_realized)}")
            else:
                lines.append("【**Gate.io**】포지션 없음")
        
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
            f"**Bitget**\n"
            f"  금일: {self._format_currency(bitget_data['today_pnl'])} ({bitget_today_roi:+.1f}%)\n"
            f"  7일: {self._format_currency(bitget_data['weekly_profit']['total'])} ({bitget_weekly_roi:+.1f}%)\n"
            f"  누적: {self._format_currency(bitget_data['cumulative_profit'])} ({bitget_data['cumulative_roi']:+.1f}%)"
        )
        
        # Gate.io 행 (있는 경우만)
        if gateio_data['total_equity'] > 0:
            lines.append("")
            lines.append(
                f"**Gate.io**\n"
                f"  금일: {self._format_currency(gateio_data['today_pnl'])} ({gateio_today_roi:+.1f}%)\n"
                f"  7일: {self._format_currency(gateio_data['weekly_profit']['total'])} ({gateio_weekly_roi:+.1f}%)\n"
                f"  누적: {self._format_currency(gateio_data['cumulative_profit'])} ({gateio_data['cumulative_roi']:+.1f}%)"
            )
            lines.append("")
        
        # 합계 행
        lines.append(
            f"**통합 합계**\n"
            f"  금일: {self._format_currency(combined_data['today_total'])} ({combined_data['today_roi']:+.1f}%)\n"
            f"  7일: {self._format_currency(combined_data['weekly_total'])} ({combined_data['weekly_roi']:+.1f}%)\n"
            f"  누적: {self._format_currency(combined_data['cumulative_profit'])} ({combined_data['cumulative_roi']:+.1f}%)"
        )
        
        return '\n'.join(lines)
    
    async def _generate_combined_mental_care(self, combined_data: dict) -> str:
        """통합 멘탈 케어 생성"""
        if not self.openai_client:
            return "시장은 예측 불가능하지만, 준비된 마음은 기회를 놓치지 않습니다. 오늘도 차분하게 접근하세요. 📊"
        
        try:
            # 상황 요약
            situation_summary = f"""
현재 트레이더 상황:
- 총 자산: ${combined_data['total_equity']:,.0f} (두 거래소 합산)
- 금일 수익: ${combined_data['today_total']:+,.0f} ({combined_data['today_roi']:+.1f}%)
- 7일 수익: ${combined_data['weekly_total']:+,.0f} ({combined_data['weekly_roi']:+.1f}%)
- 누적 수익: ${combined_data['cumulative_profit']:+,.0f} ({combined_data['cumulative_roi']:+.1f}%)
"""
            
            prompt = f"""당신은 전문 트레이딩 심리 코치입니다. 
다음 트레이더의 상황을 분석하고, 맞춤형 멘탈 케어 메시지를 작성하세요.

{situation_summary}

요구사항:
1. 두 거래소를 운영하는 트레이더임을 고려
2. 구체적인 숫자를 언급하며 개인화된 메시지
3. 분산 투자의 장점이나 리스크 관리 언급
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
            if combined_data['cumulative_roi'] > 50:
                return f"두 거래소에서 총 ${int(combined_data['cumulative_profit'])}의 수익, 훌륭한 분산 투자입니다. 🎯"
            else:
                return f"총 자산 ${int(combined_data['total_equity'])}을 안정적으로 운용중입니다. 꾸준함이 성공의 열쇠입니다. 💪"
