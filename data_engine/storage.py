"""Validated atomic Parquet storage; every code lives in its own local file."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pandas as pd
from .config import DATABASE_DIR
from .validator import normalize_history, validate_code


def history_path(code: str, root: Path | str | None = None) -> Path:
    return Path(root) / f"{validate_code(code)}.parquet" if root is not None else DATABASE_DIR / f"{validate_code(code)}.parquet"


def save_history(code: str, df: pd.DataFrame, root: Path | str | None = None) -> Path:
    data = normalize_history(df)
    path = history_path(code, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{code}.", suffix=".parquet", dir=path.parent)
    os.close(handle)
    try:
        data.to_parquet(temporary, engine="pyarrow", index=False, compression="zstd")
        # Validate before replacing the last known-good file.
        probe = pd.read_parquet(temporary, engine="pyarrow")
        if len(probe) != len(data):
            raise IOError("写入 Parquet 后行数不一致")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def load_history(code: str, root: Path | str | None = None) -> pd.DataFrame | None:
    path = history_path(code, root)
    if not path.is_file():
        return None
    try:
        return normalize_history(pd.read_parquet(path, engine="pyarrow"))
    except Exception as exc:
        raise RuntimeError(f"历史数据库文件损坏: {code}") from exc


def last_saved_date(code: str, root: Path | str | None = None):
    frame = load_history(code, root)
    return frame.date.iloc[-1].date() if frame is not None else None
