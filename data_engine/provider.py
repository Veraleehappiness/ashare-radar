"""Read-only strategy-facing historical data provider."""
from pathlib import Path
import pandas as pd
from .storage import load_history
from .validator import validate_code


class HistoryProvider:
    def __init__(self, root: Path | str | None = None):
        self.root = root

    def get_history(self, code: str, days: int | None = 250) -> pd.DataFrame:
        validate_code(code)
        if days is not None and not 1 <= days <= 10000:
            raise ValueError("days 必须在 1..10000 之间")
        frame = load_history(code, self.root)
        if frame is None:
            raise FileNotFoundError(f"{code} 尚无已验证历史日线")
        return frame.tail(days).copy() if days is not None else frame.copy()
