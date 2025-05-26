import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    def __init__(self):
        # Telegram 설정
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        # Bitget API 설정
        self.BITGET_API_KEY = os.getenv('BITGET_APIKEY')
        self.BITGET_SECRET_KEY = os.getenv('BITGET_APISECRET')
        self.BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
        
        # Bitget 추가 설정
        self.bitget_base_url = "https://api.bitget.com"
        self.bitget_api_key = self.BITGET_API_KEY
        self.bitget_api_secret = self.BITGET_SECRET_KEY
        self.bitget_passphrase = self.BITGET_PASSPHRASE
        self.symbol = "BTCUSDT"
        
        # 뉴스 API 설정들 (3개 모두)
        self.NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
        self.NEWSDATA_KEY = os.getenv('NEWSDATA_KEY')
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
        
        # OpenAI 설정
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        
        # 설정 검증
        self._validate_config()
    
    def _validate_config(self):
        """필수 설정 검증"""
        required_configs = {
            'TELEGRAM_TOKEN': self.TELEGRAM_TOKEN,
            'TELEGRAM_CHAT_ID': self.TELEGRAM_CHAT_ID,
            'BITGET_API_KEY': self.BITGET_API_KEY,
            'BITGET_SECRET_KEY': self.BITGET_SECRET_KEY,
            'BITGET_PASSPHRASE': self.BITGET_PASSPHRASE
        }
        
        missing_configs = []
        for config_name, config_value in required_configs.items():
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            raise ValueError(f"다음 환경변수가 설정되지 않았습니다: {', '.join(missing_configs)}")
        
        # 선택사항들 상태 로그
        optional_configs = {
            'OPENAI_API_KEY': self.OPENAI_API_KEY,
            'NEWSAPI_KEY': self.NEWSAPI_KEY,
            'NEWSDATA_KEY': self.NEWSDATA_KEY,
            'ALPHA_VANTAGE_KEY': self.ALPHA_VANTAGE_KEY
        }
        
        available_apis = []
        missing_apis = []
        
        for config_name, config_value in optional_configs.items():
            if config_value:
                available_apis.append(config_name)
            else:
                missing_apis.append(config_name)
        
        print(f"✅ 사용 가능한 API: {', '.join(available_apis) if available_apis else '없음'}")
        if missing_apis:
            print(f"⚠️  설정되지 않은 API: {', '.join(missing_apis)} (관련 기능 제한)")
