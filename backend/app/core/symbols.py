import re

SYMBOL_PATH_PATTERN = r"^[A-Za-z0-9]{2,10}-[A-Za-z0-9]{2,10}$"
_SYMBOL_RE = re.compile(SYMBOL_PATH_PATTERN)


def normalize_symbol(slug: str) -> str:
    """'btc-usdt' (URL form) -> 'BTC/USDT' (exchange form)."""
    if not _SYMBOL_RE.match(slug):
        raise ValueError(f"Invalid symbol: {slug!r}")
    return slug.upper().replace("-", "/")
