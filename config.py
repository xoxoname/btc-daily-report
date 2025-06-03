import os
from typing import Optional

class Config:
    """설정 클래스"""
    
    def __init__(self):
        # Telegram 봇 설정
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        # Bitget API 설정 (환경변수명 통일)
        self.BITGET_APIKEY = os.getenv('BITGET_APIKEY')
        self.BITGET_APISECRET = os.getenv('BITGET_APISECRET')
        self.BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
        
        # Gate.io API 설정
        self.GATE_API_KEY = os.getenv('GATE_API_KEY')
        self.GATE_API_SECRET = os.getenv('GATE_API_SECRET')
        
        # AI API 설정
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
        
        # 뉴스 API 설정
        self.NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
        self.NEWSDATA_KEY = os.getenv('SDATA_KEY')  # 환경변수명과 일치
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
        
        # 암호화폐 API 설정
        self.COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')
        self.CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY')
        
        # 미러 트레이딩 설정
        self.ENABLE_MIRROR_TRADING = os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true'
        self.MIRROR_TRADING_MODE = os.getenv('MIRROR_TRADING_MODE', 'conservative').lower()
        self.MIRROR_CHECK_INTERVAL = int(os.getenv('MIRROR_CHECK_INTERVAL', '5'))
        
        # 필수 설정 검증
        self._validate_required_settings()
    
    def _validate_required_settings(self):
        """필수 설정 검증"""
        required_settings = [
            ('TELEGRAM_BOT_TOKEN', self.TELEGRAM_BOT_TOKEN),
            ('TELEGRAM_CHAT_ID', self.TELEGRAM_CHAT_ID),
        ]
        
        missing_settings = []
        for name, value in required_settings:
            if not value:
                missing_settings.append(name)
        
        if missing_settings:
            raise ValueError(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_settings)}")
    
    def has_bitget_api(self) -> bool:
        """Bitget API 설정 확인"""
        return all([
            self.BITGET_APIKEY,
            self.BITGET_APISECRET,
            self.BITGET_PASSPHRASE
        ])
    
    def has_gate_api(self) -> bool:
        """Gate.io API 설정 확인"""
        return all([
            self.GATE_API_KEY,
            self.GATE_API_SECRET
        ])
    
    def has_openai_api(self) -> bool:
        """OpenAI API 설정 확인"""
        return bool(self.OPENAI_API_KEY)
    
    def has_anthropic_api(self) -> bool:
        """Anthropic API 설정 확인"""
        return bool(self.ANTHROPIC_API_KEY)
    
    def has_newsapi(self) -> bool:
        """NewsAPI 설정 확인"""
        return bool(self.NEWSAPI_KEY)
    
    def has_newsdata(self) -> bool:
        """NewsData API 설정 확인"""
        return bool(self.NEWSDATA_KEY)
    
    def has_alpha_vantage(self) -> bool:
        """Alpha Vantage API 설정 확인"""
        return bool(self.ALPHA_VANTAGE_KEY)
    
    def has_coingecko_api(self) -> bool:
        """CoinGecko API 설정 확인"""
        return bool(self.COINGECKO_API_KEY)
    
    def has_cryptocompare_api(self) -> bool:
        """CryptoCompare API 설정 확인"""
        return bool(self.CRYPTOCOMPARE_API_KEY)
    
    def can_enable_mirror_trading(self) -> bool:
        """미러 트레이딩 활성화 가능 여부"""
        return self.ENABLE_MIRROR_TRADING and self.has_bitget_api() and self.has_gate_api()
    
    def get_api_status_summary(self) -> dict:
        """API 설정 상태 요약"""
        return {
            'telegram': bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID),
            'bitget': self.has_bitget_api(),
            'gate': self.has_gate_api(),
            'openai': self.has_openai_api(),
            'anthropic': self.has_anthropic_api(),
            'newsapi': self.has_newsapi(),
            'newsdata': self.has_newsdata(),
            'alpha_vantage': self.has_alpha_vantage(),
            'coingecko': self.has_coingecko_api(),
            'cryptocompare': self.has_cryptocompare_api(),
            'mirror_trading_enabled': self.can_enable_mirror_trading()
        }
    
    def get_missing_apis(self) -> list:
        """설정되지 않은 API 목록"""
        missing = []
        status = self.get_api_status_summary()
        
        api_names = {
            'telegram': 'Telegram Bot',
            'bitget': 'Bitget API',
            'gate': 'Gate.io API',
            'openai': 'OpenAI GPT',
            'anthropic': 'Claude (Anthropic)',
            'newsapi': 'NewsAPI',
            'newsdata': 'NewsData',
            'alpha_vantage': 'Alpha Vantage',
            'coingecko': 'CoinGecko',
            'cryptocompare': 'CryptoCompare'
        }
        
        for key, name in api_names.items():
            if not status.get(key, False):
                missing.append(name)
        
        return missing
    
    def print_status(self):
        """설정 상태 출력"""
        print("=" * 50)
        print("🚀 비트코인 예측 시스템 v2.2 - 비트코인 전용 (제한 해제)")
        print("=" * 50)
        print("🔧 API 설정 상태:")
        print("━" * 50)
        
        # 운영 모드
        if self.can_enable_mirror_trading():
            print("🔄 운영 모드: 미러 트레이딩 모드")
        else:
            print("📊 운영 모드: 분석 전용 모드")
        
        # 필수 API
        status = self.get_api_status_summary()
        required_apis = ['telegram', 'bitget', 'gate']
        
        if all(status.get(api, False) for api in required_apis):
            print("✅ 필수 API:")
            print("  • Telegram Bot: 설정됨")
            print("  • Bitget API: 설정됨")
            print("  • Gate.io API: 설정됨")
        else:
            print("❌ 필수 API 누락:")
            for api in required_apis:
                api_names = {'telegram': 'Telegram Bot', 'bitget': 'Bitget API', 'gate': 'Gate.io API'}
                if not status.get(api, False):
                    print(f"  • {api_names[api]}: 미설정")
        
        # 추가 API
        optional_apis = ['openai', 'anthropic', 'newsapi', 'newsdata', 'alpha_vantage', 'coingecko', 'cryptocompare']
        available_apis = [api for api in optional_apis if status.get(api, False)]
        missing_apis = [api for api in optional_apis if not status.get(api, False)]
        
        if available_apis:
            print(f"✅ 사용 가능한 추가 API ({len(available_apis)}개):")
            api_names = {
                'openai': 'OpenAI GPT',
                'anthropic': 'Claude (Anthropic)',
                'newsapi': 'NewsAPI',
                'newsdata': 'NewsData',
                'alpha_vantage': 'Alpha Vantage',
                'coingecko': 'CoinGecko',
                'cryptocompare': 'CryptoCompare'
            }
            for api in available_apis:
                print(f"  • {api_names[api]}")
        
        if missing_apis:
            print(f"⚠️  미설정 API ({len(missing_apis)}개):")
            api_names = {
                'openai': 'OpenAI GPT',
                'anthropic': 'Claude (Anthropic)',
                'newsapi': 'NewsAPI',
                'newsdata': 'NewsData',
                'alpha_vantage': 'Alpha Vantage',
                'coingecko': 'CoinGecko',
                'cryptocompare': 'CryptoCompare'
            }
            for api in missing_apis:
                print(f"  • {api_names[api]}")
        
        # AI 번역 설정
        if self.has_anthropic_api() and self.has_openai_api():
            print("🤖 AI 번역 설정: Claude 우선, GPT 백업")
        elif self.has_openai_api():
            print("🤖 AI 번역 설정: GPT만 사용")
        elif self.has_anthropic_api():
            print("🤖 AI 번역 설정: Claude만 사용")
        else:
            print("⚠️  AI 번역 비활성화: OpenAI 또는 Claude API 필요")
        
        # 미러 트레이딩 설정
        if self.can_enable_mirror_trading():
            print("💡 미러 트레이딩 설정:")
            print("  • 기준 거래소: Bitget")
            print("  • 미러 거래소: Gate.io")
            print("  • 미러링 방식: 마진 비율 기반")
            print("  • 기존 포지션: 복제 제외")
            print("  • 신규 진입만 미러링")
        
        # 추가 설정 안내
        if missing_apis:
            print("💡 추가 API 설정 방법:")
            print("  환경변수에 추가:")
            for api in missing_apis:
                env_names = {
                    'openai': 'OPENAI_API_KEY',
                    'anthropic': 'ANTHROPIC_API_KEY',
                    'newsapi': 'NEWSAPI_KEY',
                    'newsdata': 'SDATA_KEY',
                    'alpha_vantage': 'ALPHA_VANTAGE_KEY',
                    'coingecko': 'COINGECKO_API_KEY',
                    'cryptocompare': 'CRYPTOCOMPARE_API_KEY'
                }
                if api in env_names:
                    print(f"  • {env_names[api]}")
        
        print("━" * 50)
