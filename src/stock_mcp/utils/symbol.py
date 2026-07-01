from __future__ import annotations


ETF_PREFIXES = ("15", "16", "18", "50", "51", "52", "56", "58", "59")
A_SHARE_PREFIXES = ("00", "20", "30", "60", "68")
BJ_PREFIXES = ("43", "83", "87", "88", "92")


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().lower()
    if cleaned.startswith(("sh", "sz", "bj")) and len(cleaned) >= 8:
        return cleaned

    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) != 6:
        raise ValueError(f"Unsupported symbol format: {symbol}")

    if digits.startswith(("60", "68", "50", "51", "52", "56", "58", "59")):
        prefix = "sh"
    elif digits.startswith(("00", "15", "16", "18", "20", "30")):
        prefix = "sz"
    elif digits.startswith(BJ_PREFIXES):
        prefix = "bj"
    else:
        raise ValueError(f"Unsupported symbol prefix: {symbol}")

    return f"{prefix}{digits}"


def to_digits(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    return normalized[2:]


def infer_market(symbol: str) -> str:
    digits = to_digits(symbol)
    if digits.startswith(ETF_PREFIXES):
        return "ETF"
    if digits.startswith(BJ_PREFIXES):
        return "BJ"
    if digits.startswith(A_SHARE_PREFIXES):
        return "A"
    raise ValueError(f"Unsupported market for symbol: {symbol}")
