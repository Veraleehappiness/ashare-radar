REQUIRED_COLUMNS = [
    "date", "open", "high", "low", "close", "volume"
]


def validate_history(df):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    if (df["high"] < df["close"]).any():
        raise ValueError("invalid high/close relationship")

    if (df["low"] > df["close"]).any():
        raise ValueError("invalid low/close relationship")

    if df["date"].duplicated().any():
        raise ValueError("duplicate dates")

    return True
