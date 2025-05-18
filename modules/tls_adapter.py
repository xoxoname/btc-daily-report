import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount("https://", TLSAdapter())
