import os
from typing import Optional

class Config:
    """🔥🔥🔥 환경변수 설정 클래스 - Render 환경변수와 완전 호환"""
    
    def __init__(self):
        # 🔥🔥🔥 Render 환경변수 그대로 사용 (변경 금지)
        
        # Alpha Vantage API
        self.ALPHA_VANTAGE_KEY: Optional[str] = os.getenv('ALPHA_VANTAGE_KEY')
        
        # Bitget API 설정
        self.BITGET_APIKEY: Optional[str] = os.getenv('BITGET_APIKEY')
        self.BITGET_APISECRET: Optional[str] = os.getenv('BITGET_APISECRET')
        self.BITGET_PASSPHRASE: Optional[str] = os.getenv('BITGET_PASSPHRASE')
        
        # CoinGecko API
        self.COINGECKO_API_KEY: Optional[str] = os.getenv('COINGECKO_API_KEY')
        
        # CryptoCompare API
        self.CRYPTOCOMPARE_API_KEY: Optional[str] = os.getenv('CRYPTOCOMPARE_API_KEY')
        
        # 미러 트레이딩 활성화 설정
        self.ENABLE_MIRROR_TRADING: str = os.getenv('ENABLE_MIRROR_TRADING', 'false')
        
        # Gate.io API 설정
        self.GATE_API_KEY: Optional[str] = os.getenv('GATE_API_KEY')
        self.GATE_API_SECRET: Optional[str] = os.getenv('GATE_API_SECRET')
        
        # 미러 체크 간격 (초)
        self.MIRROR_CHECK_INTERVAL: int = int(os.getenv('MIRROR_CHECK_INTERVAL', '2'))
        
        # 미러 트레이딩 모드
        self.MIRROR_TRADING_MODE: str = os.getenv('MIRROR_TRADING_MODE', 'auto')
        
        # NewsAPI 설정
        self.NEWSAPI_KEY: Optional[str] = os.getenv('NEWSAPI_KEY')
        
        # SDATA API 설정
        self.SDATA_KEY: Optional[str] = os.getenv('SDATA_KEY')
        
        # OpenAI API 설정
        self.OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
        
        # Telegram Bot 설정
        self.TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')
        
        # 🔥🔥🔥 미러 트레이딩 고급 설정
        self.MIRROR_MAX_POSITION_SIZE: float = float(os.getenv('MIRROR_MAX_POSITION_SIZE', '1000.0'))
        self.MIRROR_RISK_LIMIT_PERCENT: float = float(os.getenv('MIRROR_RISK_LIMIT_PERCENT', '2.0'))
        self.MIRROR_SLIPPAGE_TOLERANCE: float = float(os.getenv('MIRROR_SLIPPAGE_TOLERANCE', '0.05'))
        
        # 🔥🔥🔥 시세 동기화 설정
        self.PRICE_SYNC_THRESHOLD: float = float(os.getenv('PRICE_SYNC_THRESHOLD', '1000.0'))
        self.PRICE_SYNC_ENABLED: bool = os.getenv('PRICE_SYNC_ENABLED', 'true').lower() == 'true'
        
        # 🔥🔥🔥 알림 설정
        self.ALERT_PRICE_DIFF_THRESHOLD: float = float(os.getenv('ALERT_PRICE_DIFF_THRESHOLD', '100.0'))
        self.ALERT_VOLUME_SPIKE_THRESHOLD: float = float(os.getenv('ALERT_VOLUME_SPIKE_THRESHOLD', '3.0'))
        
        # 🔥🔥🔥 로깅 설정
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_TO_FILE: bool = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        
        # 🔥🔥🔥 데이터베이스 설정 (선택사항)
        self.DATABASE_URL: Optional[str] = os.getenv('DATABASE_URL')
        
        # 🔥🔥🔥 Redis 설정 (선택사항)
        self.REDIS_URL: Optional[str] = os.getenv('REDIS_URL')
        
        # 검증 수행
        self._validate_config()
    
    def _validate_config(self):
        """🔥🔥🔥 설정 검증"""
        
        # 필수 환경변수 검증
        required_for_basic = [
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        missing_basic = [var for var in required_for_basic if not getattr(self, var)]
        if missing_basic:
            raise ValueError(f"기본 기능을 위한 필수 환경변수가 누락되었습니다: {missing_basic}")
        
        # 미러 트레이딩이 활성화된 경우 추가 검증
        if self.ENABLE_MIRROR_TRADING.lower() in ['true', '1', 'yes', 'on']:
            required_for_mirror = [
                'BITGET_APIKEY',
                'BITGET_APISECRET', 
                'BITGET_PASSPHRASE',
                'GATE_API_KEY',
                'GATE_API_SECRET'
            ]
            
            missing_mirror = [var for var in required_for_mirror if not getattr(self, var)]
            if missing_mirror:
                print(f"⚠️ 미러 트레이딩 필수 환경변수 누락: {missing_mirror}")
                print("미러 트레이딩이 비활성화됩니다.")
                self.ENABLE_MIRROR_TRADING = 'false'
        
        # API 키 검증 (선택사항)
        api_keys = [
            'ALPHA_VANTAGE_KEY',
            'COINGECKO_API_KEY', 
            'CRYPTOCOMPARE_API_KEY',
            'NEWSAPI_KEY',
            'SDATA_KEY',
            'OPENAI_API_KEY'
        ]
        
        missing_apis = [var for var in api_keys if not getattr(self, var)]
        if missing_apis:
            print(f"ℹ️ 선택적 API 키 누락: {missing_apis}")
            print("해당 기능들이 제한될 수 있습니다.")
    
    def is_mirror_trading_enabled(self) -> bool:
        """미러 트레이딩 활성화 여부 확인"""
        return self.ENABLE_MIRROR_TRADING.lower() in ['true', '1', 'yes', 'on']
    
    def get_api_endpoints(self) -> dict:
        """API 엔드포인트 설정"""
        return {
            'bitget': {
                'base_url': 'https://api.bitget.com',
                'ws_url': 'wss://ws.bitget.com/spot/v1/stream'
            },
            'gate': {
                'base_url': 'https://api.gateio.ws',
                'ws_url': 'wss://api.gateio.ws/ws/v4/'
            },
            'coingecko': {
                'base_url': 'https://api.coingecko.com/api/v3'
            },
            'newsapi': {
                'base_url': 'https://newsapi.org/v2'
            }
        }
    
    def get_trading_symbols(self) -> dict:
        """거래 심볼 설정"""
        return {
            'bitget': 'BTCUSDT',
            'gate': 'BTC_USDT',
            'coingecko': 'bitcoin'
        }
    
    def get_mirror_settings(self) -> dict:
        """미러 트레이딩 설정"""
        return {
            'enabled': self.is_mirror_trading_enabled(),
            'check_interval': self.MIRROR_CHECK_INTERVAL,
            'trading_mode': self.MIRROR_TRADING_MODE,
            'max_position_size': self.MIRROR_MAX_POSITION_SIZE,
            'risk_limit_percent': self.MIRROR_RISK_LIMIT_PERCENT,
            'slippage_tolerance': self.MIRROR_SLIPPAGE_TOLERANCE,
            'price_sync_threshold': self.PRICE_SYNC_THRESHOLD,
            'price_sync_enabled': self.PRICE_SYNC_ENABLED
        }
    
    def get_alert_settings(self) -> dict:
        """알림 설정"""
        return {
            'price_diff_threshold': self.ALERT_PRICE_DIFF_THRESHOLD,
            'volume_spike_threshold': self.ALERT_VOLUME_SPIKE_THRESHOLD
        }
    
    def get_logging_config(self) -> dict:
        """로깅 설정"""
        return {
            'level': self.LOG_LEVEL,
            'to_file': self.LOG_TO_FILE,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    
    def __str__(self) -> str:
        """설정 요약 출력 (민감한 정보 제외)"""
        return f"""🔥🔥🔥 시스템 설정 요약:

📊 기본 기능:
- Telegram Bot: {'✅' if self.TELEGRAM_BOT_TOKEN else '❌'}
- OpenAI API: {'✅' if self.OPENAI_API_KEY else '❌'}

🔄 미러 트레이딩:
- 활성화: {'✅' if self.is_mirror_trading_enabled() else '❌'}
- Bitget API: {'✅' if self.BITGET_APIKEY else '❌'}
- Gate.io API: {'✅' if self.GATE_API_KEY else '❌'}
- 체크 간격: {self.MIRROR_CHECK_INTERVAL}초
- 거래 모드: {self.MIRROR_TRADING_MODE}

📈 데이터 소스:
- Alpha Vantage: {'✅' if self.ALPHA_VANTAGE_KEY else '❌'}
- CoinGecko: {'✅' if self.COINGECKO_API_KEY else '❌'}
- CryptoCompare: {'✅' if self.CRYPTOCOMPARE_API_KEY else '❌'}
- NewsAPI: {'✅' if self.NEWSAPI_KEY else '❌'}
- SDATA: {'✅' if self.SDATA_KEY else '❌'}

⚙️ 고급 설정:
- 최대 포지션 크기: ${self.MIRROR_MAX_POSITION_SIZE:,.0f}
- 위험 한도: {self.MIRROR_RISK_LIMIT_PERCENT}%
- 슬리피지 허용: {self.MIRROR_SLIPPAGE_TOLERANCE}%
- 시세 동기화 임계값: ${self.PRICE_SYNC_THRESHOLD:,.0f}
- 로그 레벨: {self.LOG_LEVEL}"""
    
    def validate_environment(self) -> tuple[bool, list[str]]:
        """환경 검증 및 결과 반환"""
        errors = []
        
        # 기본 검증
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        
        if not self.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        
        # 미러 트레이딩 검증
        if self.is_mirror_trading_enabled():
            if not self.BITGET_APIKEY:
                errors.append("미러 트레이딩을 위해 BITGET_APIKEY가 필요합니다.")
            
            if not self.BITGET_APISECRET:
                errors.append("미러 트레이딩을 위해 BITGET_APISECRET이 필요합니다.")
            
            if not self.BITGET_PASSPHRASE:
                errors.append("미러 트레이딩을 위해 BITGET_PASSPHRASE가 필요합니다.")
            
            if not self.GATE_API_KEY:
                errors.append("미러 트레이딩을 위해 GATE_API_KEY가 필요합니다.")
            
            if not self.GATE_API_SECRET:
                errors.append("미러 트레이딩을 위해 GATE_API_SECRET이 필요합니다.")
        
        return len(errors) == 0, errors
