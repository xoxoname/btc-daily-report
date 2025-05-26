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
        
        # News API 설정
        self.NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
        
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
        
        # OpenAI는 선택사항이므로 경고만 출력
        if not self.OPENAI_API_KEY:
            print("경고: OPENAI_API_KEY가 설정되지 않았습니다. AI 분석 기능이 제한됩니다.")
        
        if not self.NEWSAPI_KEY:
            print("경고: NEWSAPI_KEY가 설정되지 않았습니다. 뉴스 모니터링이 제한됩니다.")
