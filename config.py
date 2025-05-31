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
        
        # Gate.io API 설정
        self.GATE_API_KEY = os.getenv('GATE_API_KEY')
        self.GATE_API_SECRET = os.getenv('GATE_API_SECRET')
        
        # Bitget 추가 설정
        self.bitget_base_url = "https://api.bitget.com"
        self.bitget_api_key = self.BITGET_API_KEY
        self.bitget_api_secret = self.BITGET_SECRET_KEY
        self.bitget_passphrase = self.BITGET_PASSPHRASE
        self.symbol = "BTCUSDT"
        
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
        
        # 설정 검증
        self._validate_config()
    
    def _validate_config(self):
        """필수 설정 검증"""
        # 미러 트레이딩 모드 체크
        mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'true').lower() == 'true'
        
        required_configs = {
            'TELEGRAM_TOKEN': self.TELEGRAM_TOKEN,
            'TELEGRAM_CHAT_ID': self.TELEGRAM_CHAT_ID,
            'BITGET_API_KEY': self.BITGET_API_KEY,
            'BITGET_SECRET_KEY': self.BITGET_SECRET_KEY,
            'BITGET_PASSPHRASE': self.BITGET_PASSPHRASE
        }
        
        # 미러 트레이딩 모드일 때만 Gate.io API 필수
        if mirror_mode:
            required_configs.update({
                'GATE_API_KEY': self.GATE_API_KEY,
                'GATE_API_SECRET': self.GATE_API_SECRET
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
        
        if mirror_mode:
            print(f"  • Gate.io API: 설정됨")
            print(f"\n🔄 미러 트레이딩: 활성화")
        else:
            print(f"\n📊 분석 전용 모드: 활성화")
        
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
        
        # Gate.io가 선택사항일 때
        if not mirror_mode and self.GATE_API_KEY:
            optional_apis['Gate.io API'] = self.GATE_API_KEY
        
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
        
        if mirror_mode:
            print("\n💡 미러 트레이딩 설정:")
            print("  • 기준 거래소: Bitget")
            print("  • 미러 거래소: Gate.io")
            print("  • 미러링 방식: 마진 비율 기반")
            print("  • 기존 포지션: 복제 제외")
        
        print("\n💡 추가 API 설정 방법:")
        print("  .env 파일에 다음 형식으로 추가:")
        print("  COINGECKO_API_KEY=your_key_here")
        print("  CRYPTOCOMPARE_API_KEY=your_key_here")
        print("  GLASSNODE_API_KEY=your_key_here")
        
        if not mirror_mode:
            print("\n💡 미러 트레이딩 활성화:")
            print("  .env 파일에 추가:")
            print("  MIRROR_TRADING_MODE=true")
            print("  GATE_API_KEY=your_gate_key")
            print("  GATE_API_SECRET=your_gate_secret")
        
        print("━" * 50 + "\n")
