import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PositionInfo:
    symbol: str
    side: str
    size: float
    entry_price: float
    margin: float
    leverage: int
    mode: str
    tp_orders: List[Dict] = field(default_factory=list)
    sl_orders: List[Dict] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    
@dataclass
class MirrorResult:
    success: bool
    action: str
    bitget_data: Dict
    gate_data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class MirrorTradingUtils:
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # Constants
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_MARGIN = 1.0
        self.MAX_PRICE_DIFF_PERCENT = 50.0
        
        # Leverage settings
        self.DEFAULT_LEVERAGE = 30
        self.MAX_LEVERAGE = 100
        self.MIN_LEVERAGE = 1
        self.leverage_cache = {}
        
        # Ratio multiplier settings
        self.DEFAULT_RATIO_MULTIPLIER = 1.0
        self.MAX_RATIO_MULTIPLIER = 10.0
        self.MIN_RATIO_MULTIPLIER = 0.1
        self.current_ratio_multiplier = 1.0
        
        # Ratio descriptions
        self.RATIO_DESCRIPTIONS = {
            0.1: "원본의 10% 크기로 대폭 축소",
            0.2: "원본의 20% 크기로 축소",
            0.3: "원본의 30% 크기로 축소",
            0.4: "원본의 40% 크기로 축소",
            0.5: "원본의 절반 크기로 축소",
            0.6: "원본의 60% 크기로 축소",
            0.7: "원본의 70% 크기로 축소",
            0.8: "원본의 80% 크기로 축소",
            0.9: "원본의 90% 크기로 축소",
            1.0: "원본 비율 그대로 복제",
            1.1: "원본의 1.1배로 10% 확대",
            1.2: "원본의 1.2배로 20% 확대",
            1.3: "원본의 1.3배로 30% 확대",
            1.4: "원본의 1.4배로 40% 확대",
            1.5: "원본의 1.5배로 50% 확대",
            2.0: "원본의 2배로 확대",
            2.5: "원본의 2.5배로 확대",
            3.0: "원본의 3배로 확대",
            5.0: "원본의 5배로 확대",
            10.0: "원본의 10배로 최대 확대"
        }
        
        # Price validation settings
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0
        self.ALLOW_VERY_CLOSE_PRICES = True
        self.PRICE_SYNC_THRESHOLD = 1000.0
        self.PRICE_ADJUSTMENT_ENABLED = True
        self.ABNORMAL_PRICE_DIFF_THRESHOLD = 10000.0
        
        # Close order detection
        self.CLOSE_ORDER_KEYWORDS = [
            'close', 'close_long', 'close_short', 'close long', 'close short',
            'exit', 'exit_long', 'exit_short', 'exit long', 'exit short',
            'reduce'
        ]
        
        self.TP_SL_ONLY_ORDER_TYPES = [
            'profit_loss',
            'stop_loss_only', 
            'take_profit_only'
        ]
        
        self.CLOSE_ORDER_STRICT_MODE = False
        
        self.logger.info("Mirror trading utils initialized with ratio multiplier support")
    
    async def calculate_dynamic_margin_ratio_with_multiplier(self, size: float, trigger_price: float, 
                                                           bitget_order: Dict, ratio_multiplier: float = 1.0) -> Dict:
        try:
            if size is None or trigger_price is None:
                return {
                    'success': False,
                    'error': 'size or trigger_price is None'
                }
            
            # Validate ratio multiplier
            validated_ratio = self.validate_ratio_multiplier(ratio_multiplier)
            if validated_ratio != ratio_multiplier:
                self.logger.warning(f"Ratio adjusted: {ratio_multiplier} → {validated_ratio}")
                ratio_multiplier = validated_ratio
            
            self.logger.info(f"Calculating margin with ratio: size={size}, ratio={ratio_multiplier}x")
            
            # Extract leverage
            bitget_account = await self.bitget.get_account_info()
            extracted_leverage = await self.extract_bitget_leverage_enhanced(
                order_data=bitget_order,
                position_data=None,
                account_data=bitget_account
            )
            
            self.logger.info(f"Extracted leverage: {extracted_leverage}x")
            
            # Get Bitget total equity
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            if bitget_total_equity <= 0:
                return {
                    'success': False,
                    'error': 'Bitget total equity is 0 or query failed'
                }
            
            # Calculate Bitget margin usage
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / extracted_leverage
            
            # Calculate base margin ratio
            base_margin_ratio = bitget_required_margin / bitget_total_equity
            
            # Apply ratio multiplier
            adjusted_margin_ratio = base_margin_ratio * ratio_multiplier
            
            # Safety checks
            if adjusted_margin_ratio <= 0:
                return {
                    'success': False,
                    'error': f'Adjusted margin ratio is 0 or negative: {adjusted_margin_ratio:.4f}'
                }
            elif adjusted_margin_ratio > 1:
                original_ratio = adjusted_margin_ratio
                adjusted_margin_ratio = 0.95
                self.logger.warning(f"Margin ratio capped at 95%: {original_ratio:.4f} → {adjusted_margin_ratio:.4f}")
            
            # Recalculate values with adjusted margin
            adjusted_required_margin = bitget_total_equity * adjusted_margin_ratio
            adjusted_notional_value = adjusted_required_margin * extracted_leverage
            
            # Analyze ratio effect
            ratio_effect = self.analyze_ratio_multiplier_effect(ratio_multiplier, base_margin_ratio, adjusted_margin_ratio)
            
            result = {
                'success': True,
                'margin_ratio': adjusted_margin_ratio,
                'leverage': extracted_leverage,
                'required_margin': adjusted_required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': adjusted_notional_value,
                'ratio_multiplier': ratio_multiplier,
                'base_margin_ratio': base_margin_ratio,
                'base_required_margin': bitget_required_margin,
                'base_notional_value': bitget_notional_value,
                'ratio_effect': ratio_effect,
                'ratio_description': self.get_ratio_multiplier_description(ratio_multiplier)
            }
            
            self.logger.info(f"Margin calculation successful:")
            self.logger.info(f"   - Base margin ratio: {base_margin_ratio*100:.3f}%")
            self.logger.info(f"   - Ratio multiplier: {ratio_multiplier}x ({ratio_effect['description']})")
            self.logger.info(f"   - Final margin ratio: {adjusted_margin_ratio*100:.3f}%")
            self.logger.info(f"   - Leverage: {extracted_leverage}x")
            self.logger.info(f"   - Effect: {ratio_effect['impact']}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Margin calculation with ratio failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        return await self.calculate_dynamic_margin_ratio_with_multiplier(size, trigger_price, bitget_order, 1.0)
    
    def validate_ratio_multiplier(self, ratio_multiplier: float) -> float:
        try:
            if ratio_multiplier is None:
                self.logger.warning("Ratio multiplier is None, using default: 1.0")
                return self.DEFAULT_RATIO_MULTIPLIER
            
            ratio_multiplier = float(ratio_multiplier)
            
            if ratio_multiplier < self.MIN_RATIO_MULTIPLIER:
                self.logger.warning(f"Ratio too small ({ratio_multiplier}), using minimum: {self.MIN_RATIO_MULTIPLIER}")
                return self.MIN_RATIO_MULTIPLIER
            
            if ratio_multiplier > self.MAX_RATIO_MULTIPLIER:
                self.logger.warning(f"Ratio too large ({ratio_multiplier}), using maximum: {self.MAX_RATIO_MULTIPLIER}")
                return self.MAX_RATIO_MULTIPLIER
            
            # Risk warnings
            if ratio_multiplier > 5.0:
                self.logger.warning(f"Very high ratio ({ratio_multiplier}x). Risk management required.")
            elif ratio_multiplier < 0.5:
                self.logger.info(f"Conservative ratio ({ratio_multiplier}x). Safe setting.")
            
            return ratio_multiplier
            
        except (ValueError, TypeError):
            self.logger.error(f"Ratio conversion failed ({ratio_multiplier}), using default: {self.DEFAULT_RATIO_MULTIPLIER}")
            return self.DEFAULT_RATIO_MULTIPLIER
    
    def get_ratio_multiplier_description(self, ratio_multiplier: float) -> str:
        try:
            # Exact match
            if ratio_multiplier in self.RATIO_DESCRIPTIONS:
                return self.RATIO_DESCRIPTIONS[ratio_multiplier]
            
            # Find closest match
            closest_ratio = min(self.RATIO_DESCRIPTIONS.keys(), 
                               key=lambda x: abs(x - ratio_multiplier))
            
            if abs(closest_ratio - ratio_multiplier) < 0.05:
                return self.RATIO_DESCRIPTIONS[closest_ratio]
            
            # Custom description
            if ratio_multiplier == 1.0:
                return "원본 비율 그대로"
            elif ratio_multiplier < 1.0:
                percentage = ratio_multiplier * 100
                return f"원본의 {percentage:.1f}% 크기로 축소"
            else:
                return f"원본의 {ratio_multiplier:.1f}배 크기로 확대"
                
        except Exception as e:
            self.logger.error(f"Failed to generate ratio description: {e}")
            return "비율 정보 없음"
    
    def analyze_ratio_multiplier_effect(self, ratio_multiplier: float, base_ratio: float, adjusted_ratio: float) -> Dict:
        try:
            effect_analysis = {
                'multiplier': ratio_multiplier,
                'base_percentage': base_ratio * 100,
                'adjusted_percentage': adjusted_ratio * 100,
                'absolute_increase': (adjusted_ratio - base_ratio) * 100,
                'relative_increase_percent': ((adjusted_ratio / base_ratio) - 1) * 100 if base_ratio > 0 else 0,
                'description': self.get_ratio_multiplier_description(ratio_multiplier),
                'impact': '',
                'risk_level': '',
                'recommendation': ''
            }
            
            # Impact analysis
            if ratio_multiplier == 1.0:
                effect_analysis['impact'] = "원본과 동일한 리스크"
                effect_analysis['risk_level'] = "기본"
                effect_analysis['recommendation'] = "표준 미러링"
            elif ratio_multiplier < 0.5:
                effect_analysis['impact'] = f"리스크 대폭 감소 ({effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "매우 낮음"
                effect_analysis['recommendation'] = "매우 보수적 - 테스트나 안전 운영에 적합"
            elif ratio_multiplier < 1.0:
                effect_analysis['impact'] = f"리스크 감소 ({effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "낮음"
                effect_analysis['recommendation'] = "보수적 - 안정적인 운영"
            elif ratio_multiplier <= 1.5:
                effect_analysis['impact'] = f"리스크 소폭 증가 (+{effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "보통"
                effect_analysis['recommendation'] = "적극적 - 수익 확대 시도"
            elif ratio_multiplier <= 3.0:
                effect_analysis['impact'] = f"리스크 상당 증가 (+{effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "높음"
                effect_analysis['recommendation'] = "공격적 - 리스크 관리 필수"
            else:
                effect_analysis['impact'] = f"리스크 대폭 증가 (+{effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "매우 높음"
                effect_analysis['recommendation'] = "매우 공격적 - 극도로 신중한 관리 필요"
            
            return effect_analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze ratio effect: {e}")
            return {
                'multiplier': ratio_multiplier,
                'description': "분석 실패",
                'impact': "알 수 없음",
                'risk_level': "불명",
                'recommendation': "신중한 검토 필요"
            }
    
    async def extract_bitget_leverage_enhanced(self, order_data: Dict = None, position_data: Dict = None, account_data: Dict = None) -> int:
        try:
            extracted_leverage = self.DEFAULT_LEVERAGE
            source = "default"
            
            # 1. Order data
            if order_data:
                for leverage_field in ['leverage', 'marginLeverage', 'leverageRatio']:
                    order_leverage = order_data.get(leverage_field)
                    if order_leverage:
                        try:
                            lev_value = int(float(order_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"order({leverage_field})"
                                self.logger.info(f"Leverage from order: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 2. Position data
            if position_data:
                for leverage_field in ['leverage', 'marginLeverage', 'leverageRatio']:
                    pos_leverage = position_data.get(leverage_field)
                    if pos_leverage:
                        try:
                            lev_value = int(float(pos_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"position({leverage_field})"
                                self.logger.info(f"Leverage from position: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 3. Account data
            if account_data:
                for leverage_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'marginLeverage']:
                    account_leverage = account_data.get(leverage_field)
                    if account_leverage:
                        try:
                            lev_value = int(float(account_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"account({leverage_field})"
                                self.logger.info(f"Leverage from account: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 4. Real-time account query
            try:
                fresh_account = await self.bitget.get_account_info()
                for leverage_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'marginLeverage']:
                    account_leverage = fresh_account.get(leverage_field)
                    if account_leverage:
                        try:
                            lev_value = int(float(account_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"fresh_account({leverage_field})"
                                self.logger.info(f"Leverage from fresh account: {extracted_leverage}x ({source})")
                                
                                # Cache the result
                                self.leverage_cache['bitget_default'] = {
                                    'leverage': extracted_leverage,
                                    'timestamp': datetime.now(),
                                    'source': source
                                }
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            except Exception as e:
                self.logger.warning(f"Fresh account query failed: {e}")
            
            # 5. Real-time position query
            try:
                positions = await self.bitget.get_positions(self.SYMBOL)
                for position in positions:
                    if float(position.get('total', 0)) > 0:
                        pos_leverage = position.get('leverage')
                        if pos_leverage:
                            try:
                                lev_value = int(float(pos_leverage))
                                if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                    extracted_leverage = lev_value
                                    source = "live_position"
                                    self.logger.info(f"Leverage from live position: {extracted_leverage}x ({source})")
                                    return extracted_leverage
                            except (ValueError, TypeError):
                                continue
            except Exception as e:
                self.logger.warning(f"Live position query failed: {e}")
            
            # 6. Cache
            if 'bitget_default' in self.leverage_cache:
                cache_data = self.leverage_cache['bitget_default']
                cache_time = cache_data['timestamp']
                if (datetime.now() - cache_time).total_seconds() < 3600:  # 1 hour cache
                    extracted_leverage = cache_data['leverage']
                    source = f"cache({cache_data['source']})"
                    self.logger.info(f"Leverage from cache: {extracted_leverage}x ({source})")
                    return extracted_leverage
            
            # Default fallback
            self.logger.warning(f"Leverage extraction failed, using default: {extracted_leverage}x")
            return extracted_leverage
            
        except Exception as e:
            self.logger.error(f"Leverage extraction error: {e}")
            return self.DEFAULT_LEVERAGE
    
    async def determine_close_order_details_enhanced(self, bitget_order: Dict) -> Dict:
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            reduce_only = bitget_order.get('reduceOnly', False)
            order_type = bitget_order.get('orderType', bitget_order.get('planType', '')).lower()
            
            self.logger.info(f"Order analysis: side='{side}', reduce_only={reduce_only}, order_type='{order_type}'")
            
            # Enhanced close order detection
            is_close_order = False
            detection_method = "none"
            
            # 1. reduce_only flag (most reliable)
            if reduce_only is True or reduce_only == 'true' or str(reduce_only).lower() == 'true':
                is_close_order = True
                detection_method = "reduce_only_flag"
                self.logger.info(f"Close order confirmed by reduce_only=True")
            
            # 2. Explicit close keywords
            elif not is_close_order:
                for keyword in self.CLOSE_ORDER_KEYWORDS:
                    if keyword in side:
                        is_close_order = True
                        detection_method = f"side_keyword_{keyword}"
                        self.logger.info(f"Close order confirmed by side keyword: '{side}' contains '{keyword}'")
                        break
            
            # 3. TP/SL only order types
            elif not is_close_order:
                for tp_sl_type in self.TP_SL_ONLY_ORDER_TYPES:
                    if tp_sl_type in order_type:
                        is_close_order = True
                        detection_method = f"tp_sl_only_type_{tp_sl_type}"
                        self.logger.info(f"Close order confirmed by TP/SL type: '{order_type}' contains '{tp_sl_type}'")
                        break
            
            # 4. Orders with TP/SL are treated as open orders (prevent misclassification)
            if not is_close_order:
                tp_price, sl_price = await self.extract_tp_sl_from_bitget_order(bitget_order)
                
                if tp_price or sl_price:
                    is_close_order = False
                    detection_method = "tp_sl_set_but_open_order"
                    self.logger.info(f"Open order with TP/SL settings (TP={tp_price}, SL={sl_price})")
                    self.logger.info(f"       → New position creation with TP/SL")
            
            # 5. Special close patterns
            if not is_close_order:
                special_patterns = ['exit', 'liquidat']
                for pattern in special_patterns:
                    if pattern in side or pattern in order_type:
                        is_close_order = True
                        detection_method = f"special_pattern_{pattern}"
                        self.logger.info(f"Close order confirmed by special pattern: '{pattern}'")
                        break
            
            # Final confirmation
            if not is_close_order:
                detection_method = "default_open_order"
                self.logger.info(f"Confirmed as open order (new position creation)")
            
            self.logger.info(f"Close order analysis result: is_close_order={is_close_order}, method={detection_method}")
            
            # Determine order direction and position side
            order_direction = None
            position_side = None
            
            if is_close_order:
                # Close orders
                if 'close_long' in side or 'exit_long' in side:
                    order_direction = 'sell'  # Close long position by selling
                    position_side = 'long'
                elif 'close_short' in side or 'exit_short' in side:
                    order_direction = 'buy'   # Close short position by buying
                    position_side = 'short'
                elif 'sell' in side and 'buy' not in side:
                    order_direction = 'sell'
                    position_side = 'long'
                elif 'buy' in side and 'sell' not in side:
                    order_direction = 'buy'
                    position_side = 'short'
                else:
                    # Query current positions to determine direction
                    try:
                        bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                        active_positions = [pos for pos in bitget_positions if float(pos.get('total', 0)) > 0]
                        
                        if active_positions:
                            main_position = active_positions[0]
                            current_side = main_position.get('holdSide', '').lower()
                            
                            if current_side == 'long':
                                order_direction = 'sell'
                                position_side = 'long'
                                self.logger.info(f"Based on current long position: sell to close")
                            elif current_side == 'short':
                                order_direction = 'buy'
                                position_side = 'short'
                                self.logger.info(f"Based on current short position: buy to close")
                            else:
                                order_direction = 'sell'
                                position_side = 'long'
                        else:
                            order_direction = 'sell'
                            position_side = 'long'
                            self.logger.warning(f"No active position, using default: long→sell")
                            
                    except Exception as e:
                        self.logger.error(f"Position query failed, using default: {e}")
                        order_direction = 'sell'
                        position_side = 'long'
            else:
                # Open orders (including those with TP/SL settings)
                if 'buy' in side or 'long' in side:
                    order_direction = 'buy'
                    position_side = 'long'
                elif 'sell' in side or 'short' in side:
                    order_direction = 'sell'
                    position_side = 'short'
                else:
                    order_direction = 'buy'
                    position_side = 'long'
            
            result = {
                'is_close_order': is_close_order,
                'order_direction': order_direction,
                'position_side': position_side,
                'original_side': side,
                'reduce_only': reduce_only,
                'order_type': order_type,
                'detection_method': detection_method
            }
            
            self.logger.info(f"Enhanced close order analysis result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Enhanced close order details determination failed: {e}")
            return {
                'is_close_order': False,
                'order_direction': 'buy',
                'position_side': 'long',
                'original_side': side if 'side' in locals() else '',
                'reduce_only': False,
                'order_type': order_type if 'order_type' in locals() else '',
                'detection_method': 'fallback'
            }
    
    async def determine_close_order_details(self, bitget_order: Dict) -> Dict:
        return await self.determine_close_order_details_enhanced(bitget_order)
    
    async def extract_tp_sl_from_bitget_order(self, bitget_order: Dict) -> Tuple[Optional[float], Optional[float]]:
        try:
            tp_price = None
            sl_price = None
            
            # Extract TP price
            tp_fields = ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice', 'tpPrice']
            
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            self.logger.info(f"TP price extracted: {field} = {tp_price}")
                            break
                    except:
                        continue
            
            # Extract SL price
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopPrice', 'slPrice']
            
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            self.logger.info(f"SL price extracted: {field} = {sl_price}")
                            break
                    except:
                        continue
            
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"TP/SL extraction failed: {e}")
            return None, None
    
    async def extract_gate_order_details(self, gate_order: Dict) -> Optional[Dict]:
        try:
            order_id = gate_order.get('id', '') or ''
            contract = gate_order.get('contract', self.GATE_CONTRACT) or self.GATE_CONTRACT
            
            # Extract trigger info
            trigger_info = gate_order.get('trigger', {}) or {}
            trigger_price_raw = trigger_info.get('price')
            
            if trigger_price_raw is None or trigger_price_raw == '':
                self.logger.debug(f"Trigger price is None or empty: {gate_order}")
                return None
            
            try:
                trigger_price = float(trigger_price_raw)
            except (ValueError, TypeError):
                self.logger.debug(f"Trigger price conversion failed: {trigger_price_raw}")
                return None
            
            # Extract initial order info
            initial_info = gate_order.get('initial', {}) or {}
            size_raw = initial_info.get('size')
            
            # Handle missing or zero size
            size = 1  # default
            if size_raw is not None:
                try:
                    size = int(size_raw)
                except (ValueError, TypeError):
                    self.logger.debug(f"Size conversion failed, using default: {size_raw}")
                    size = 1
            else:
                self.logger.debug(f"Size is None, using default: {gate_order}")
            
            # Extract TP/SL info
            tp_price = None
            sl_price = None
            
            for tp_field in ['stop_profit_price', 'stopProfitPrice', 'takeProfitPrice']:
                tp_value = gate_order.get(tp_field)
                if tp_value and tp_value != '' and str(tp_value) != '0':
                    try:
                        tp_price = float(tp_value)
                        if tp_price > 0:
                            break
                    except (ValueError, TypeError):
                        continue
            
            for sl_field in ['stop_loss_price', 'stopLossPrice', 'stopPrice']:
                sl_value = gate_order.get(sl_field)
                if sl_value and sl_value != '' and str(sl_value) != '0':
                    try:
                        sl_price = float(sl_value)
                        if sl_price > 0:
                            break
                    except (ValueError, TypeError):
                        continue
            
            if trigger_price <= 0:
                self.logger.debug(f"Invalid trigger price: {trigger_price}")
                return None
            
            return {
                'order_id': order_id,
                'contract': contract,
                'trigger_price': trigger_price,
                'size': size,
                'abs_size': abs(size),
                'tp_price': tp_price,
                'sl_price': sl_price,
                'has_tp_sl': bool(tp_price or sl_price),
                'gate_order_raw': gate_order
            }
            
        except Exception as e:
            self.logger.error(f"Gate order details extraction failed: {e}")
            return None
    
    async def generate_multiple_order_hashes(self, order_details: Dict) -> List[str]:
        try:
            # Validate required fields
            contract = order_details.get('contract') or self.GATE_CONTRACT
            trigger_price = order_details.get('trigger_price')
            size = order_details.get('size', 0)
            abs_size = order_details.get('abs_size', abs(size) if size else 0)
            
            if trigger_price is None:
                self.logger.debug(f"Required value is None - trigger_price: {trigger_price}")
                return []
            
            try:
                trigger_price = float(trigger_price)
                size = int(size) if size is not None else 0
                abs_size = abs(size) if size != 0 else 0
            except (ValueError, TypeError) as e:
                self.logger.debug(f"Value conversion failed - trigger_price: {trigger_price}, size: {size}, error: {e}")
                return []
            
            if trigger_price <= 0:
                self.logger.debug(f"Invalid trigger price - trigger_price: {trigger_price}")
                return []
            
            hashes = []
            
            # Price-based hashes (core deduplication)
            try:
                # Basic price hashes (always generated regardless of size)
                price_only_hash = f"{contract}_price_{trigger_price:.2f}"
                hashes.append(price_only_hash)
                
                precise_price_hash = f"{contract}_price_{trigger_price:.8f}"
                hashes.append(precise_price_hash)
                
                # Rounded price hashes
                rounded_price_1 = round(trigger_price, 1)
                rounded_price_hash_1 = f"{contract}_price_{rounded_price_1:.1f}"
                hashes.append(rounded_price_hash_1)
                
                rounded_price_0 = round(trigger_price, 0)
                rounded_price_hash_0 = f"{contract}_price_{rounded_price_0:.0f}"
                hashes.append(rounded_price_hash_0)
                
            except Exception as e:
                self.logger.debug(f"Price-based hash generation failed: {e}")
            
            # Size-inclusive hashes (only when size > 0)
            if abs_size > 0:
                try:
                    # Basic hash
                    basic_hash = f"{contract}_{trigger_price:.2f}_{abs_size}"
                    hashes.append(basic_hash)
                    
                    # Exact price hash
                    exact_price_hash = f"{contract}_{trigger_price:.8f}_{abs_size}"
                    hashes.append(exact_price_hash)
                    
                    # Signed hash
                    signed_hash = f"{contract}_{trigger_price:.2f}_{size}"
                    hashes.append(signed_hash)
                    
                    # Rounded price hashes
                    rounded_price_1 = round(trigger_price, 1)
                    rounded_hash_1 = f"{contract}_{rounded_price_1:.1f}_{abs_size}"
                    hashes.append(rounded_hash_1)
                    
                    rounded_price_0 = round(trigger_price, 0)
                    rounded_hash_0 = f"{contract}_{rounded_price_0:.0f}_{abs_size}"
                    hashes.append(rounded_hash_0)
                    
                except Exception as e:
                    self.logger.debug(f"Size-inclusive hash generation failed: {e}")
            else:
                self.logger.debug(f"Size is 0, generating price-based hashes only - trigger_price: {trigger_price}")
            
            # TP/SL inclusive hashes
            try:
                if order_details.get('has_tp_sl'):
                    tp_price = order_details.get('tp_price', 0) or 0
                    sl_price = order_details.get('sl_price', 0) or 0
                    
                    # TP/SL price-based hash (size independent)
                    tp_sl_price_hash = f"{contract}_price_{trigger_price:.2f}_withTPSL"
                    hashes.append(tp_sl_price_hash)
                    
                    # TP/SL + size hash (only when size > 0)
                    if abs_size > 0:
                        tp_sl_hash = f"{contract}_{trigger_price:.2f}_{abs_size}_tp{tp_price:.2f}_sl{sl_price:.2f}"
                        hashes.append(tp_sl_hash)
                        
            except Exception as e:
                self.logger.debug(f"TP/SL hash generation failed: {e}")
            
            # Lenient price range hashes (±500 dollars)
            try:
                # 500 dollar range
                price_range_500 = round(trigger_price / 500) * 500
                range_hash_500 = f"{contract}_range500_{price_range_500:.0f}"
                hashes.append(range_hash_500)
                
                # 100 dollar range
                price_range_100 = round(trigger_price / 100) * 100
                range_hash_100 = f"{contract}_range100_{price_range_100:.0f}"
                hashes.append(range_hash_100)
                
                # Very wide price difference consideration (±200 dollars)
                for offset in [-200, -100, -50, -20, 0, 20, 50, 100, 200]:
                    adjusted_price = trigger_price + offset
                    if adjusted_price > 0:
                        offset_hash = f"{contract}_offset_{adjusted_price:.0f}"
                        hashes.append(offset_hash)
                        
            except Exception as e:
                self.logger.debug(f"Price range hash generation failed: {e}")
            
            # Remove duplicates
            unique_hashes = list(set(hashes))
            
            if unique_hashes:
                self.logger.debug(f"Generated {len(unique_hashes)} order hashes: trigger=${trigger_price:.2f}, size={size}")
            else:
                self.logger.debug(f"Hash generation failed - returning empty list")
            
            return unique_hashes
            
        except Exception as e:
            self.logger.error(f"Multiple hash generation failed: {e}")
            try:
                trigger_price = order_details.get('trigger_price')
                size = order_details.get('size', 0)
                contract = order_details.get('contract', self.GATE_CONTRACT)
                
                if trigger_price is not None:
                    trigger_price = float(trigger_price)
                    # Generate fallback hashes even with size 0
                    basic_hash = f"{contract}_{trigger_price:.2f}_fallback"
                    price_hash = f"{contract}_price_{trigger_price:.2f}"
                    return [basic_hash, price_hash]
            except Exception as fallback_error:
                self.logger.error(f"Fallback hash generation also failed: {fallback_error}")
            
            return []
    
    def generate_order_hash(self, trigger_price: float, size: int, contract: str = None) -> str:
        try:
            contract = contract or self.GATE_CONTRACT
            
            if trigger_price is None or trigger_price <= 0:
                return f"{contract}_unknown_unknown"
            
            trigger_price = float(trigger_price)
            size = int(size) if size is not None else 0
            
            # Generate price-based hash even with size 0
            if size == 0:
                return f"{contract}_price_{trigger_price:.2f}"
            else:
                return f"{contract}_{trigger_price:.2f}_{abs(size)}"
            
        except (ValueError, TypeError) as e:
            self.logger.debug(f"Hash generation conversion failed: {e}")
            return f"{contract or self.GATE_CONTRACT}_error_error"
    
    def generate_price_based_hash(self, trigger_price: float, contract: str = None) -> str:
        try:
            contract = contract or self.GATE_CONTRACT
            
            if trigger_price is None or trigger_price <= 0:
                return f"{contract}_price_invalid"
            
            trigger_price = float(trigger_price)
            return f"{contract}_price_{trigger_price:.2f}"
            
        except (ValueError, TypeError) as e:
            self.logger.debug(f"Price-based hash generation failed: {e}")
            return f"{contract or self.GATE_CONTRACT}_price_error"
    
    async def adjust_price_for_gate(self, price: float, bitget_current_price: float = 0, 
                                   gate_current_price: float = 0, price_diff_percent: float = 0) -> float:
        try:
            if price is None or price <= 0:
                return price or 0
            
            # Always proceed with processing, adjustment is optional
            if (bitget_current_price > 0 and gate_current_price > 0):
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # Very high threshold for abnormal price difference (10000+ dollars)
                if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                    self.logger.info(f"Extremely large price difference but continuing processing (${price_diff_abs:.2f})")
                    return price  # Use original price without adjustment
                
                # Always process regardless of price difference, but apply adjustment selectively
                if (self.PRICE_ADJUSTMENT_ENABLED and 
                    price_diff_abs > self.PRICE_SYNC_THRESHOLD and
                    price_diff_abs <= self.ABNORMAL_PRICE_DIFF_THRESHOLD):
                    
                    # Calculate price ratio
                    price_ratio = gate_current_price / bitget_current_price
                    adjusted_price = price * price_ratio
                    
                    # Validate adjustment magnitude (very lenient: allow up to 50% adjustment)
                    adjustment_percent = abs(adjusted_price - price) / price * 100
                    
                    if adjustment_percent <= 50.0:  # 10% → 50% much more lenient
                        self.logger.info(f"Price adjusted: ${price:.2f} → ${adjusted_price:.2f} (difference: ${price_diff_abs:.2f})")
                        return adjusted_price
                    else:
                        self.logger.info(f"Large adjustment but continuing with original price ({adjustment_percent:.1f}%)")
                        return price  # Continue processing without adjustment
                else:
                    return price
            elif bitget_current_price <= 0 or gate_current_price <= 0:
                self.logger.debug("Price query failed but continuing processing")
                return price
            
            return price
            
        except Exception as e:
            self.logger.error(f"Price adjustment failed but continuing processing: {e}")
            return price or 0
    
    async def validate_trigger_price(self, trigger_price: float, side: str, current_price: float = 0) -> Tuple[bool, str]:
        try:
            if trigger_price is None or trigger_price <= 0:
                return False, "Trigger price is None or <= 0"
            
            if current_price <= 0:
                self.logger.info("Current price query failed but allowing all trigger prices")
                return True, "Current price query failed but allowed"
            
            # Allow all price differences - no processing blocking
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            price_diff_abs = abs(trigger_price - current_price)
            
            # Extremely high threshold for abnormal price difference detection (10000 dollars)
            if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                self.logger.info(f"Very large price difference but allowing processing: ${price_diff_abs:.2f}")
                return True, f"Large price difference but allowed (${price_diff_abs:.2f})"
            
            # Allow all prices unconditionally
            return True, f"All trigger prices allowed (difference: {price_diff_percent:.4f}%)"
            
        except Exception as e:
            self.logger.error(f"Trigger price validation failed but allowing: {e}")
            return True, f"Validation error but allowing all prices: {str(e)[:100]}"
    
    async def calculate_gate_order_size_for_close_order_enhanced(self, current_gate_position_size: int, 
                                                               close_order_details: Dict, 
                                                               bitget_order: Dict) -> Tuple[int, bool]:
        try:
            position_side = close_order_details['position_side']  # 'long' or 'short'
            order_direction = close_order_details['order_direction']  # 'buy' or 'sell'
            
            self.logger.info(f"Enhanced close order size calculation: current_gate_position={current_gate_position_size}, position={position_side}, direction={order_direction}")
            
            # Allow close order creation even when current position is 0
            if current_gate_position_size == 0:
                self.logger.warning(f"Current position is 0 but forcing close order creation")
                
                # Calculate base size based on Bitget order
                bitget_size = float(bitget_order.get('size', 1))
                if bitget_size <= 0:
                    bitget_size = 1
                
                # Create close order with minimum size
                base_gate_size = max(int(bitget_size * 10000), 1)  # Convert BTC to contracts
                
                # Determine close direction based on position side
                if position_side == 'long':
                    final_gate_size = -base_gate_size  # Close long position → sell
                else:
                    final_gate_size = base_gate_size   # Close short position → buy
                
                self.logger.info(f"Forced close order creation with no position: {final_gate_size}")
                return final_gate_size, True
            
            # Verify current position direction
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_position_size)
            
            # Check position direction consistency
            if current_position_side != position_side:
                self.logger.warning(f"Position direction mismatch: current={current_position_side}, expected={position_side}")
                # Enhanced: adjust to match current position
                actual_position_side = current_position_side
            else:
                actual_position_side = position_side
            
            # Calculate partial close ratio from Bitget close order
            bitget_size = float(bitget_order.get('size', 0))
            
            # Query Bitget current position to calculate partial close ratio
            try:
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_current_position = None
                
                for pos in bitget_positions:
                    pos_side = pos.get('holdSide', '').lower()
                    if pos_side == actual_position_side and float(pos.get('total', 0)) > 0:
                        bitget_current_position = pos
                        break
                
                if bitget_current_position:
                    bitget_position_size = float(bitget_current_position.get('total', 0))
                    
                    # Calculate partial close ratio
                    if bitget_position_size > 0:
                        close_ratio = min(bitget_size / bitget_position_size, 1.0)
                        self.logger.info(f"Partial close ratio: {close_ratio*100:.1f}% (Bitget position: {bitget_position_size}, close size: {bitget_size})")
                    else:
                        close_ratio = 1.0
                        self.logger.warning(f"Bitget position size is 0, treating as full close")
                else:
                    # Can't find Bitget position, use full close
                    close_ratio = 1.0
                    self.logger.warning(f"Cannot find corresponding Bitget position, treating as full close")
                    
            except Exception as e:
                # Bitget position query failed, use full close
                close_ratio = 1.0
                self.logger.error(f"Bitget position query failed, treating as full close: {e}")
            
            # Calculate Gate close order size
            gate_close_size = int(current_position_abs_size * close_ratio)
            
            # Minimum 1 to close
            if gate_close_size == 0:
                gate_close_size = 1
            
            # Cannot exceed current position
            if gate_close_size > current_position_abs_size:
                gate_close_size = current_position_abs_size
            
            # Determine close order direction (opposite to position)
            if actual_position_side == 'long':
                # Close long position → sell (negative)
                final_gate_size = -gate_close_size
                self.logger.info(f"Long position close: {gate_close_size} → sell order (negative: {final_gate_size})")
            else:
                # Close short position → buy (positive)
                final_gate_size = gate_close_size
                self.logger.info(f"Short position close: {gate_close_size} → buy order (positive: {final_gate_size})")
            
            self.logger.info(f"Enhanced close order size calculation complete: current position={current_gate_position_size} → close size={final_gate_size} (ratio: {close_ratio*100:.1f}%)")
            
            return final_gate_size, True  # reduce_only=True
            
        except Exception as e:
            self.logger.error(f"Enhanced close order size calculation failed: {e}")
            # Even on failure, create close order with base size
            bitget_size = float(bitget_order.get('size', 1))
            base_size = max(int(bitget_size * 10000), 1)
            
            position_side = close_order_details.get('position_side', 'long')
            if position_side == 'long':
                return -base_size, True  # Close long position → sell
            else:
                return base_size, True   # Close short position → buy
    
    async def calculate_gate_order_size_for_close_order(self, current_gate_position_size: int, 
                                                       close_order_details: Dict, 
                                                       bitget_order: Dict) -> Tuple[int, bool]:
        return await self.calculate_gate_order_size_for_close_order_enhanced(
            current_gate_position_size, close_order_details, bitget_order
        )
    
    async def calculate_gate_order_size_fixed(self, side: str, base_size: int, is_close_order: bool = False) -> Tuple[int, bool]:
        try:
            side_lower = side.lower()
            reduce_only = False
            
            self.logger.info(f"Order type analysis: side='{side}', is_close_order={is_close_order}")
            
            # Close order processing - completely revised logic
            if is_close_order or 'close' in side_lower:
                reduce_only = True
                
                # Close orders: order in direction to close position
                if 'close_long' in side_lower or side_lower == 'close long':
                    # Close long position → sell order (negative)
                    gate_size = -abs(base_size)
                    self.logger.info(f"Close long: Close long position → Gate sell order (negative: {gate_size})")
                    
                elif 'close_short' in side_lower or side_lower == 'close short':
                    # Close short position → buy order (positive)
                    gate_size = abs(base_size)
                    self.logger.info(f"Close short: Close short position → Gate buy order (positive: {gate_size})")
                    
                elif 'sell' in side_lower and 'buy' not in side_lower:
                    # Close by selling → closing long position
                    gate_size = -abs(base_size)
                    self.logger.info(f"Close sell: Close long position → Gate sell order (negative: {gate_size})")
                    
                elif 'buy' in side_lower and 'sell' not in side_lower:
                    # Close by buying → closing short position
                    gate_size = abs(base_size)
                    self.logger.info(f"Close buy: Close short position → Gate buy order (positive: {gate_size})")
                    
                else:
                    # Other close orders - default to sell
                    gate_size = -abs(base_size)
                    self.logger.warning(f"Unknown close order type: {side}, treating as sell (negative: {gate_size})")
                        
            # Open order processing
            else:
                reduce_only = False
                
                if 'open_long' in side_lower or ('buy' in side_lower and 'sell' not in side_lower):
                    # Create long position → buy order (positive)
                    gate_size = abs(base_size)
                    self.logger.info(f"Open long: Create new long position → Gate buy order (positive: {gate_size})")
                    
                elif 'open_short' in side_lower or 'sell' in side_lower:
                    # Create short position → sell order (negative)
                    gate_size = -abs(base_size)
                    self.logger.info(f"Open short: Create new short position → Gate sell order (negative: {gate_size})")
                    
                else:
                    # Other open orders - maintain original size
                    gate_size = base_size
                    self.logger.warning(f"Unknown open order type: {side}, maintaining original size: {gate_size}")
            
            self.logger.info(f"Final conversion result: {side} → Gate size={gate_size}, reduce_only={reduce_only}")
            return gate_size, reduce_only
            
        except Exception as e:
            self.logger.error(f"Gate order size calculation failed: {e}")
            return base_size, False
    
    async def calculate_gate_order_size(self, side: str, base_size: int) -> int:
        try:
            is_close_order = 'close' in side.lower()
            gate_size, _ = await self.calculate_gate_order_size_fixed(side, base_size, is_close_order)
            return gate_size
        except Exception as e:
            self.logger.error(f"Gate order size calculation wrapper failed: {e}")
            return base_size
    
    async def determine_gate_trigger_type(self, trigger_price: float, current_price: float = 0) -> str:
        try:
            if current_price <= 0 or trigger_price is None:
                return "ge"
            
            if trigger_price > current_price:
                return "ge"  # greater than or equal
            else:
                return "le"  # less than or equal
                
        except Exception as e:
            self.logger.error(f"Gate.io trigger type determination failed: {e}")
            return "ge"
    
    async def get_current_gate_position_size(self, gate_mirror_client, position_side: str = None) -> Tuple[int, str]:
        try:
            gate_positions = await gate_mirror_client.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions:
                self.logger.info("No Gate positions found")
                return 0, 'none'
            
            position = gate_positions[0]
            current_size = int(position.get('size', 0))
            
            if current_size == 0:
                self.logger.info("Gate position size is 0")
                return 0, 'none'
            
            # Check position direction
            current_side = 'long' if current_size > 0 else 'short'
            
            # Verify requested direction if specified
            if position_side and current_side != position_side:
                self.logger.warning(f"Requested position direction ({position_side}) differs from current position direction ({current_side})")
                return current_size, current_side  # Return actual info
            
            self.logger.info(f"Current Gate position: {current_size} ({current_side})")
            return current_size, current_side
            
        except Exception as e:
            self.logger.error(f"Current Gate position size query failed: {e}")
            return 0, 'error'
    
    async def validate_close_order_against_position(self, close_order_details: Dict, 
                                                   current_gate_position_size: int) -> Tuple[bool, str]:
        try:
            # Allow close orders even when no position exists
            if current_gate_position_size == 0:
                return True, "No current position but forcing close order allowance (position may be created)"
            
            # Current position direction
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            
            # Expected position direction from close order
            expected_position_side = close_order_details['position_side']
            
            if current_position_side != expected_position_side:
                return True, f"Position direction mismatch but allowing adjustment to current position ({current_position_side})"
            
            return True, f"Close order valid: {current_position_side} position → {close_order_details['order_direction']} order"
            
        except Exception as e:
            self.logger.error(f"Close order validation failed but allowing: {e}")
            return True, f"Validation error but allowing close order: {str(e)}"
    
    def generate_position_id(self, pos: Dict) -> str:
        symbol = pos.get('symbol', self.SYMBOL)
        side = pos.get('holdSide', '')
        entry_price = pos.get('openPriceAvg', '')
        return f"{symbol}_{side}_{entry_price}"
    
    async def create_position_info(self, bitget_pos: Dict) -> PositionInfo:
        return PositionInfo(
            symbol=bitget_pos.get('symbol', self.SYMBOL),
            side=bitget_pos.get('holdSide', '').lower(),
            size=float(bitget_pos.get('total', 0)),
            entry_price=float(bitget_pos.get('openPriceAvg', 0)),
            margin=float(bitget_pos.get('marginSize', 0)),
            leverage=int(float(bitget_pos.get('leverage', 1))),
            mode='cross' if bitget_pos.get('marginMode') == 'crossed' else 'isolated',
            unrealized_pnl=float(bitget_pos.get('unrealizedPL', 0))
        )
    
    async def get_price_difference_info(self, bitget_price: float, gate_price: float) -> Dict:
        try:
            if bitget_price <= 0 or gate_price <= 0:
                return {
                    'price_diff_abs': 0,
                    'price_diff_percent': 0,
                    'exceeds_threshold': False,
                    'status': 'invalid_prices',
                    'is_abnormal': False,
                    'should_process': True  # Always proceed with processing
                }
            
            price_diff_abs = abs(bitget_price - gate_price)
            price_diff_percent = price_diff_abs / bitget_price * 100
            exceeds_threshold = price_diff_abs > self.PRICE_SYNC_THRESHOLD
            is_abnormal = price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD
            
            if is_abnormal:
                status = 'abnormal_difference'
            elif exceeds_threshold:
                status = 'high_difference'
            elif price_diff_abs > self.PRICE_SYNC_THRESHOLD * 0.5:
                status = 'moderate_difference'
            else:
                status = 'normal'
            
            return {
                'price_diff_abs': price_diff_abs,
                'price_diff_percent': price_diff_percent,
                'exceeds_threshold': exceeds_threshold,
                'threshold': self.PRICE_SYNC_THRESHOLD,
                'abnormal_threshold': self.ABNORMAL_PRICE_DIFF_THRESHOLD,
                'is_abnormal': is_abnormal,
                'status': status,
                'bitget_price': bitget_price,
                'gate_price': gate_price,
                'should_process': True  # Always proceed with processing
            }
            
        except Exception as e:
            self.logger.error(f"Price difference info calculation failed: {e}")
            return {
                'price_diff_abs': 0,
                'price_diff_percent': 0,
                'exceeds_threshold': False,
                'status': 'error',
                'is_abnormal': False,
                'should_process': True  # Proceed even with errors
            }
    
    async def should_delay_processing(self, bitget_price: float, gate_price: float) -> Tuple[bool, str]:
        try:
            price_info = await self.get_price_difference_info(bitget_price, gate_price)
            
            # Always proceed with processing - no delays
            return False, "All orders processed immediately regardless of price difference"
            
        except Exception as e:
            self.logger.error(f"Processing delay determination failed but proceeding: {e}")
            return False, "Determination error but proceeding"
