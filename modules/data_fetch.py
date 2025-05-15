# modules/data_fetch.py
import time
import hmac
import hashlib
import requests
import pandas as pd
from .constants import BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE

BASE_URL = "https://api.bitget.com"

def _signed_headers(path: str, method: str, body:
