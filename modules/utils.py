def format_currency(value: float) -> str:
    return f"{value:,.2f} USD"

def to_krw(value: float, exchange_rate: float = 1380.0) -> str:
    return f"{int(value * exchange_rate):,}원"
