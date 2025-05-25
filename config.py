# config.py - 설정 관리
import os
from dataclasses import dataclass

@dataclass
class Config:
    """애플리케이션 설정"""
    
    # Bitget API 설정
    bitget_api_key: str = os.getenv('BITGET_APIKEY', '')
    bitget_api_secret: str = os.getenv('BITGET_APISECRET', '')
    bitget_passphrase: str = os.getenv('BITGET_PASSPHRASE', '')
    bitget_base_url: str = 'https://api.bitget.com'
    
    # OpenAI API 설정
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    openai_model: str = 'gpt-4'
    
    # Telegram 설정
    telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_chat_id: str = os.getenv('TELEGRAM_CHAT_ID', '1038440081')
    
    # 거래 설정
    symbol: str = 'BTCUSDT'
    product_type: str = 'UMCBL'  # USDT-M 선물
    
    # 예외 감지 임계값
    price_change_threshold: float = 2.0  # 2% 변동
    volume_threshold: float = 1000  # 1000 BTC 이체
    
    # 환율 (대략적 환산용)
    usd_to_krw: float = 1350
    
    def __post_init__(self):
        """설정 검증"""
        required_vars = [
            'bitget_api_key', 'bitget_api_secret', 'bitget_passphrase',
            'openai_api_key', 'telegram_bot_token'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(self, var):
                missing_vars.append(var.upper())
        
        if missing_vars:
            raise ValueError(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    
    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return os.getenv('ENVIRONMENT', 'development') == 'production'
