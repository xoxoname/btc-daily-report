def format_currency(value):
    try:
        return "{:,.2f}".format(float(value))
    except Exception:
        return str(value)
