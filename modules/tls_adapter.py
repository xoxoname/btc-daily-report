import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl._create_unverified_context()
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)