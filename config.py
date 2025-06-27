import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        self.logger = logging.getLogger('config')
        
        # 환경변수 키 이름 유지 (사용자 요구사항)
        self._load_environment_variables()
        self._validate_required_config()
        self._setup_trading_config()
        
        self.logger.info("✅ 설정 로드 완료")
        self.logger.info(f"Symbol: {self.symbol}")
        self.logger.info(f"Mirror Trading Mode: {self.mirror_trading_mode}")
        self.logger.info(f"Enable Mirror Trading: {self.enable_mirror_trading}")

    def _load_environment_variables(self):
        """환경변수 로드 - 키 이름 변경 금지"""
        
        # API 키들 (키 이름 유지)
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_KEY', '')
        self.bitget_apikey = os.getenv('BITGET_APIKEY', '')
        self.bitget_apisecret = os.getenv('BITGET_APISECRET', '')
        self.bitget_passphrase = os.getenv('BITGET_PASSPHRASE', '')
        self.coingecko_api_key = os.getenv('COINGECKO_API_KEY', '')
        self.cryptocompare_api_key = os.getenv('CRYPTOCOMPARE_API_KEY', '')
        self.gate_api_key = os.getenv('GATE_API_KEY', '')
        self.gate_api_secret = os.getenv('GATE_API_SECRET', '')
        self.newsapi_key = os.getenv('NEWSAPI_KEY', '')
        self.sdata_key = os.getenv('SDATA_KEY', '')
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # 클라이언트에서 참조하는 속성명으로 추가 할당
        self.bitget_api_key = self.bitget_apikey  # bitget_client.py에서 참조
        self.bitget_api_secret = self.bitget_apisecret  # bitget_client.py에서 참조
        self.bitget_base_url = "https://api.bitget.com"  # bitget_client.py에서 참조
        self.GATE_API_KEY = self.gate_api_key  # gateio_client.py에서 참조
        self.GATE_API_SECRET = self.gate_api_secret  # gateio_client.py에서 참조
        
        # 미러 트레이딩 설정 (키 이름 유지)
        self.enable_mirror_trading = os.getenv('ENABLE_MIRROR_TRADING', '').lower()
        self.mirror_trading_mode = os.getenv('MIRROR_TRADING_MODE', 'O')  # 기본값 O (활성화)
        self.mirror_check_interval = int(os.getenv('MIRROR_CHECK_INTERVAL', '60'))
        
        # 로깅
        self.logger.info("🔥 환경변수 로드 완료:")
        self.logger.info(f"  - ALPHA_VANTAGE_KEY: {'설정됨' if self.alpha_vantage_key else '미설정'}")
        self.logger.info(f"  - BITGET_APIKEY: {'설정됨' if self.bitget_apikey else '미설정'}")
        self.logger.info(f"  - BITGET_APISECRET: {'설정됨' if self.bitget_apisecret else '미설정'}")
        self.logger.info(f"  - BITGET_PASSPHRASE: {'설정됨' if self.bitget_passphrase else '미설정'}")
        self.logger.info(f"  - COINGECKO_API_KEY: {'설정됨' if self.coingecko_api_key else '미설정'}")
        self.logger.info(f"  - CRYPTOCOMPARE_API_KEY: {'설정됨' if self.cryptocompare_api_key else '미설정'}")
        self.logger.info(f"  - ENABLE_MIRROR_TRADING: '{self.enable_mirror_trading}'")
        self.logger.info(f"  - GATE_API_KEY: {'설정됨' if self.gate_api_key else '미설정'}")
        self.logger.info(f"  - GATE_API_SECRET: {'설정됨' if self.gate_api_secret else '미설정'}")
        self.logger.info(f"  - MIRROR_CHECK_INTERVAL: {self.mirror_check_interval}")
        self.logger.info(f"  - MIRROR_TRADING_MODE: '{self.mirror_trading_mode}'")
        self.logger.info(f"  - NEWSAPI_KEY: {'설정됨' if self.newsapi_key else '미설정'}")
        self.logger.info(f"  - SDATA_KEY: {'설정됨' if self.sdata_key else '미설정'}")
        self.logger.info(f"  - OPENAI_API_KEY: {'설정됨' if self.openai_api_key else '미설정'}")
        self.logger.info(f"  - TELEGRAM_BOT_TOKEN: {'설정됨' if self.telegram_bot_token else '미설정'}")
        self.logger.info(f"  - TELEGRAM_CHAT_ID: {'설정됨' if self.telegram_chat_id else '미설정'}")

    def _validate_required_config(self):
        """필수 설정 검증"""
        required_configs = []
        
        # Bitget API 필수
        if not self.bitget_apikey:
            required_configs.append('BITGET_APIKEY')
        if not self.bitget_apisecret:
            required_configs.append('BITGET_APISECRET')
        if not self.bitget_passphrase:
            required_configs.append('BITGET_PASSPHRASE')
        
        # Telegram 필수
        if not self.telegram_bot_token:
            required_configs.append('TELEGRAM_BOT_TOKEN')
        if not self.telegram_chat_id:
            required_configs.append('TELEGRAM_CHAT_ID')
        
        if required_configs:
            error_msg = f"필수 환경변수가 설정되지 않았습니다: {', '.join(required_configs)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 미러 트레이딩 조건 검증 (경고만, 에러 아님)
        if self._is_mirror_trading_enabled():
            if not self.gate_api_key or not self.gate_api_secret:
                self.logger.warning("⚠️ 미러 트레이딩이 활성화되었지만 Gate.io API 키가 설정되지 않았습니다")
                self.logger.warning("미러 트레이딩을 사용하려면 GATE_API_KEY와 GATE_API_SECRET를 설정해주세요")

    def _is_mirror_trading_enabled(self) -> bool:
        """미러 트레이딩 활성화 여부 확인"""
        # ENABLE_MIRROR_TRADING이 우선
        if self.enable_mirror_trading in ['true', '1', 'yes', 'on']:
            return True
        elif self.enable_mirror_trading in ['false', '0', 'no', 'off']:
            return False
        
        # ENABLE_MIRROR_TRADING이 없으면 MIRROR_TRADING_MODE 확인
        return self._parse_mirror_trading_mode(self.mirror_trading_mode)

    def _parse_mirror_trading_mode(self, mode_str: str) -> bool:
        """미러링 모드 파싱"""
        if isinstance(mode_str, bool):
            return mode_str
        
        mode_str_original = str(mode_str).strip()
        mode_str_upper = mode_str_original.upper()
        
        # 영어 O, X 우선 처리
        if mode_str_upper == 'O':
            return True
        elif mode_str_upper == 'X':
            return False
        elif mode_str_upper in ['ON', 'OPEN', 'TRUE', 'Y', 'YES']:
            return True
        elif mode_str_upper in ['OFF', 'CLOSE', 'FALSE', 'N', 'NO'] or mode_str_original == '0':
            return False
        elif mode_str_original == '1':
            return True
        else:
            self.logger.warning(f"⚠️ 알 수 없는 미러링 모드: '{mode_str_original}', 기본값(활성화) 사용")
            return True

    def _setup_trading_config(self):
        """거래 관련 설정"""
        self.symbol = "BTCUSDT"
        self.gate_contract = "BTC_USDT"
        
        # 거래 설정
        self.max_position_size = 1.0
        self.min_position_size = 0.00001
        self.max_leverage = 50
        self.default_leverage = 20
        
        # 리스크 관리
        self.stop_loss_percent = 2.0
        self.take_profit_percent = 4.0
        self.max_daily_loss = 5.0
        
        # 시세 및 동기화 설정
        self.price_sync_threshold = 1000.0  # 매우 관대하게 설정
        self.position_sync_interval = 30
        self.order_sync_interval = 45
        
        # API 호출 제한
        self.api_rate_limit = 10
        self.api_retry_count = 3
        self.api_timeout = 30

    @property
    def bitget_credentials(self) -> Dict[str, str]:
        """Bitget API 인증 정보"""
        return {
            'api_key': self.bitget_apikey,
            'secret_key': self.bitget_apisecret,
            'passphrase': self.bitget_passphrase
        }

    @property
    def gate_credentials(self) -> Dict[str, str]:
        """Gate.io API 인증 정보"""
        return {
            'api_key': self.gate_api_key,
            'secret_key': self.gate_api_secret
        }

    @property
    def telegram_credentials(self) -> Dict[str, str]:
        """Telegram 인증 정보"""
        return {
            'bot_token': self.telegram_bot_token,
            'chat_id': self.telegram_chat_id
        }

    def get_api_key(self, service: str) -> Optional[str]:
        """서비스별 API 키 조회"""
        service_keys = {
            'alpha_vantage': self.alpha_vantage_key,
            'bitget': self.bitget_apikey,
            'coingecko': self.coingecko_api_key,
            'cryptocompare': self.cryptocompare_api_key,
            'gate': self.gate_api_key,
            'newsapi': self.newsapi_key,
            'sdata': self.sdata_key,
            'openai': self.openai_api_key,
            'telegram': self.telegram_bot_token
        }
        
        return service_keys.get(service.lower())

    def is_api_available(self, service: str) -> bool:
        """서비스별 API 사용 가능 여부"""
        api_key = self.get_api_key(service)
        return bool(api_key and len(api_key.strip()) > 0)

    def get_mirror_trading_config(self) -> Dict[str, Any]:
        """미러 트레이딩 설정 조회"""
        return {
            'enabled': self._is_mirror_trading_enabled(),
            'mode': self.mirror_trading_mode,
            'check_interval': self.mirror_check_interval,
            'gate_api_available': self.is_api_available('gate'),
            'symbol': self.symbol,
            'gate_contract': self.gate_contract,
            'price_sync_threshold': self.price_sync_threshold,
            'position_sync_interval': self.position_sync_interval,
            'order_sync_interval': self.order_sync_interval
        }

    def get_trading_limits(self) -> Dict[str, float]:
        """거래 제한 설정"""
        return {
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'max_leverage': self.max_leverage,
            'default_leverage': self.default_leverage,
            'stop_loss_percent': self.stop_loss_percent,
            'take_profit_percent': self.take_profit_percent,
            'max_daily_loss': self.max_daily_loss
        }

    def get_api_settings(self) -> Dict[str, int]:
        """API 설정"""
        return {
            'rate_limit': self.api_rate_limit,
            'retry_count': self.api_retry_count,
            'timeout': self.api_timeout
        }

    def validate_credentials(self, service: str) -> bool:
        """인증 정보 유효성 검증"""
        try:
            if service.lower() == 'bitget':
                creds = self.bitget_credentials
                return all(creds.values())
            
            elif service.lower() == 'gate':
                creds = self.gate_credentials
                return all(creds.values())
            
            elif service.lower() == 'telegram':
                creds = self.telegram_credentials
                return all(creds.values())
            
            else:
                api_key = self.get_api_key(service)
                return bool(api_key)
                
        except Exception as e:
            self.logger.error(f"인증 정보 검증 실패 ({service}): {e}")
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """설정 요약 정보"""
        return {
            'symbol': self.symbol,
            'gate_contract': self.gate_contract,
            'mirror_trading_enabled': self._is_mirror_trading_enabled(),
            'mirror_trading_mode': self.mirror_trading_mode,
            'available_apis': {
                'alpha_vantage': self.is_api_available('alpha_vantage'),
                'bitget': self.is_api_available('bitget'),
                'coingecko': self.is_api_available('coingecko'),
                'cryptocompare': self.is_api_available('cryptocompare'),
                'gate': self.is_api_available('gate'),
                'newsapi': self.is_api_available('newsapi'),
                'sdata': self.is_api_available('sdata'),
                'openai': self.is_api_available('openai'),
                'telegram': self.is_api_available('telegram')
            },
            'credentials_valid': {
                'bitget': self.validate_credentials('bitget'),
                'gate': self.validate_credentials('gate'),
                'telegram': self.validate_credentials('telegram')
            },
            'trading_limits': self.get_trading_limits(),
            'api_settings': self.get_api_settings()
        }

    def update_mirror_trading_mode(self, new_mode: str) -> bool:
        """미러 트레이딩 모드 업데이트 (런타임)"""
        try:
            old_mode = self.mirror_trading_mode
            old_enabled = self._is_mirror_trading_enabled()
            
            self.mirror_trading_mode = new_mode
            new_enabled = self._is_mirror_trading_enabled()
            
            self.logger.info(f"🔄 미러 트레이딩 모드 업데이트:")
            self.logger.info(f"  - 이전: '{old_mode}' ({'활성화' if old_enabled else '비활성화'})")
            self.logger.info(f"  - 현재: '{new_mode}' ({'활성화' if new_enabled else '비활성화'})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 모드 업데이트 실패: {e}")
            return False

    def __str__(self) -> str:
        """설정 정보 문자열"""
        config_summary = self.get_config_summary()
        
        return f"""Config Summary:
Symbol: {config_summary['symbol']}
Gate Contract: {config_summary['gate_contract']}
Mirror Trading: {'Enabled' if config_summary['mirror_trading_enabled'] else 'Disabled'}
Mirror Mode: {config_summary['mirror_trading_mode']}

Available APIs: {sum(config_summary['available_apis'].values())}/{len(config_summary['available_apis'])}
Valid Credentials: {sum(config_summary['credentials_valid'].values())}/{len(config_summary['credentials_valid'])}

Trading Limits: {config_summary['trading_limits']}
API Settings: {config_summary['api_settings']}"""
