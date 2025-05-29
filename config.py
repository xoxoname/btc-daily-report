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
        
        # Gate.io API 설정 (새로 추가)
        self.GATEIO_API_KEY = os.getenv('GATEIO_API_KEY')
        self.GATEIO_API_SECRET = os.getenv('GATEIO_API_SECRET')
        self.gateio_api_key = self.GATEIO_API_KEY
        self.gateio_api_secret = self.GATEIO_API_SECRET
        
        # 미러 트레이딩 설정
        self.ENABLE_MIRROR_TRADING = os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true'
        self.MIRROR_CHECK_INTERVAL = int(os.getenv('MIRROR_CHECK_INTERVAL', '10'))  # 초
        
        # 기존 뉴스 API (3개)
        self.NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
        self.NEWSDATA_KEY = os.getenv('NEWSDATA_KEY')
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
        
        # 추가 데이터 소스 API
        self.COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')  # 선택사항
        self.CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY')
        self.GLASSNODE_API_KEY = os.getenv('GLASSNODE_API_KEY')
        
        # OpenAI 설정
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        
        # OpenAI Rate Limit 설정
        self.OPENAI_MAX_RETRIES = int(os.getenv('OPENAI_MAX_RETRIES', '3'))
        self.OPENAI_RETRY_DELAY = int(os.getenv('OPENAI_RETRY_DELAY', '60'))  # 초
        
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
        
        # 미러 트레이딩이 활성화된 경우 Gate.io API 검증
        if self.ENABLE_MIRROR_TRADING:
            required_configs.update({
                'GATEIO_API_KEY': self.GATEIO_API_KEY,
                'GATEIO_API_SECRET': self.GATEIO_API_SECRET
            })
        
        missing_configs = []
        for config_name, config_value in required_configs.items():
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            raise ValueError(f"다음 환경변수가 설정되지 않았습니다: {', '.join(missing_configs)}")
        
        # API 상태 출력
        print("\n🔧 API 설정 상태:")
        print("━" * 50)
        
        # 필수 API
        print("✅ 필수 API:")
        print(f"  • Telegram Bot: 설정됨")
        print(f"  • Bitget API: 설정됨")
        
        # 미러 트레이딩
        if self.ENABLE_MIRROR_TRADING:
            print(f"  • Gate.io API: 설정됨")
            print(f"  • 미러 트레이딩: 활성화 (체크 간격: {self.MIRROR_CHECK_INTERVAL}초)")
        else:
            print(f"  • 미러 트레이딩: 비활성화")
        
        # 선택 API들
        optional_apis = {
            'OpenAI GPT': self.OPENAI_API_KEY,
            'NewsAPI': self.NEWSAPI_KEY,
            'NewsData': self.NEWSDATA_KEY,
            'Alpha Vantage': self.ALPHA_VANTAGE_KEY,
            'CoinGecko': self.COINGECKO_API_KEY,
            'CryptoCompare': self.CRYPTOCOMPARE_API_KEY,
            'Glassnode': self.GLASSNODE_API_KEY
        }
        
        available = []
        missing = []
        
        for api_name, api_key in optional_apis.items():
            if api_key:
                available.append(api_name)
            else:
                missing.append(api_name)
        
        if available:
            print(f"\n✅ 사용 가능한 추가 API ({len(available)}개):")
            for api in available:
                print(f"  • {api}")
        
        if missing:
            print(f"\n⚠️  미설정 API ({len(missing)}개):")
            for api in missing:
                print(f"  • {api}")
        
        print("\n💡 추가 API 설정 방법:")
        print("  .env 파일에 다음 형식으로 추가:")
        print("  COINGECKO_API_KEY=your_key_here")
        print("  CRYPTOCOMPARE_API_KEY=your_key_here")
        print("  GLASSNODE_API_KEY=your_key_here")
        print("  GATEIO_API_KEY=your_key_here")
        print("  GATEIO_API_SECRET=your_secret_here")
        print("  ENABLE_MIRROR_TRADING=true")
        print("━" * 50 + "\n")
