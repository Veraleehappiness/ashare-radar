from .config import DATABASE_DIR


def _path(code: str):
    return DATABASE_DIR / f"{code}.parquet"


def save_history(code, df):
    path = _path(code)
    df.to_parquet(path, index=False)
    return path


def load_history(code):
    path = _path(code)
    if not path.exists():
        return None
    return __import__('pandas').read_parquet(path)
