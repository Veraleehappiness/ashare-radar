from .akshare_adapter import get_daily_history
from .validator import validate_history
from .storage import save_history
from .config import DEFAULT_START_DATE


def download_stock_history(code):
    df = get_daily_history(code, DEFAULT_START_DATE)
    validate_history(df)
    return save_history(code, df)
