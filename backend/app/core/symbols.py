import re

SYMBOL_PATH_PATTERN = r"^[A-Za-z0-9]{1,14}-[A-Za-z0-9]{2,5}$"
# Coins whose price is pegged to a currency: a direction forecast is meaningless for them.
PEGGED_BASES = frozenset(
    "USDC FDUSD TUSD USDP DAI BUSD USDE USD1 USDS PYUSD RLUSD XUSD BFUSD RWUSD U AEUR EURI EUR GBP AUD TRY BRL".split()
)
UNIVERSAL_SYMBOL = "ALL/USDT"


def is_forecastable(symbol: str) -> bool:
    base, _, quote = symbol.partition("/")
    return quote == "USDT" and base not in PEGGED_BASES and symbol != UNIVERSAL_SYMBOL


_SYMBOL_RE = re.compile(SYMBOL_PATH_PATTERN)


def normalize_symbol(slug: str) -> str:
    """'btc-usdt' (URL form) -> 'BTC/USDT' (exchange form)."""
    if not _SYMBOL_RE.match(slug):
        raise ValueError(f"Invalid symbol: {slug!r}")
    return slug.upper().replace("-", "/")
