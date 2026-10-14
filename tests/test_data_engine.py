import pandas as pd

from data_engine.validator import validate_history
from data_engine.storage import save_history, load_history



def sample_history():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "open": [10, 11],
            "high": [12, 13],
            "low": [9, 10],
            "close": [11, 12],
            "volume": [1000, 1200],
            "amount": [10000, 14000],
        }
    )


def test_validator_pass():
    df = sample_history()
    assert validate_history(df) is True


def test_storage_roundtrip(tmp_path, monkeypatch):
    import data_engine.storage as storage

    monkeypatch.setattr(storage, "DATABASE_DIR", tmp_path)

    df = sample_history()
    save_history("TEST001", df)

    result = load_history("TEST001")

    assert len(result) == 2
    assert "close" in result.columns
