# V0.7 Historical Data Engine — Real A-Share Pilot

This is working historical database code, not a mockup. Current persistent **V0.7 pilot targets 100 real A-share stocks**, not the full 5000+ market. The October 15 verification imported 99/100 stocks, with 94 valid symbols evaluated by four experimental strategies. The original 2-stock smoke task remains manual-only.

## Code and commands

- data_engine/akshare_adapter.py: AKShare stock_zh_a_hist, unadjusted completed daily candles; pre-15:15 China partial same-day bars excluded.
- data_engine/validator.py: OHLCV, dates, duplicate, finite values and code checks.
- data_engine/storage.py: atomic compressed Parquet write, validated read and safe file handling.
- data_engine/history_downloader.py: retry, eight-calendar-day overlap, date dedupe, no-loss on network failure.
- data_engine/provider.py: HistoryProvider.get_history(code, days=250).
- scripts/update_history_store.py: real command-line downloader with a JSON health report.

Install: python -m pip install -r requirements-history.txt
Run: python -m scripts.update_history_store --codes 600519,000001 --start 20240101 --limit 2
Unit tests: python -m pytest tests/test_data_engine.py tests/test_history_cli.py -v

## Working GitHub services

- source main branch — source and workflows
- history branch — history/600519.parquet, history/000001.parquet and data_health.json
- data branch — market.json and signal_ledger.json from the existing V0.6 system
- Actions data-engine-test.yml — regression tests
- Actions history-smoke.yml — real 2-stock AKShare smoke, downloads remain short-lived artifact
- Actions history-daily.yml — scheduled approximately weekdays 17:20 Beijing, restoring previous Parquet then incrementally updating and publishing to history branch

## Audit evidence (Beijing 2026-10-15)

- Unit tests: https://github.com/Veraleehappiness/ashare-radar/actions/runs/38666218728 (17 passed)
- Real download: https://github.com/Veraleehappiness/ashare-radar/actions/runs/38666248033 (two symbols, 671 completed daily rows each, 2024-01-02 through 2026-10-14, total 5.38s)
- Initial persistent history: https://github.com/Veraleehappiness/ashare-radar/actions/runs/38666268296 (passed)
- Audit: https://github.com/Veraleehappiness/ashare-radar/blob/history/data_health.json

## Limits and protections

- The full-market snapshot job uses another endpoint and may fail independently; V0.7 does not fix that endpoint.
- Two samples cannot establish reliability at scale; do not mark 5,000 stocks imported.
- Historical raw unadjusted OHLCV is not an executable-return series. Dividends, splits, corporate actions, delistings and exchange trading restrictions must be modeled separately.
- Never treat intraday partial daily candles as finalized close or report strategy profitability from these tests.
- Public GitHub history branch is a transitional small pilot store. A scaled 5,000-stock system needs partitioning and suitable database/object storage, and review of data redistribution rights.


## 100-stock acceptance: 2026-10-15 Beijing time

- [100-stock actual Actions execution](https://github.com/Veraleehappiness/ashare-radar/actions/runs/38696025427): passed overall threshold (99/100 successful updates; one failure 920438), 22,776 newly added daily bars across this incremental run. Latest completed session 2026-10-14.
- [100-stock health JSON](https://github.com/Veraleehappiness/ashare-radar/blob/history/data_health_100.json) records all failures and exact per-stock providers.
- [100-stock actual strategy JSON](https://github.com/Veraleehappiness/ashare-radar/blob/history/strategy_100.json): 94/100 stocks eligible for evaluation, 5 experimental hypotheses triggered (1 breakout, 3 trend pullbacks, 1 short rebound, 0 bottom reversals). **These are not returns or investment advice.**
- Five parallel 20-stock shards in `.github/workflows/history-100.yml`; fixed pool and Parquet stored on `history` branch. New signal panel in existing Netlify front-end (Strategies page) fetches data independently from the older market snapshot `data` branch.
- Legacy full-market quotes still require independent availability of Eastmoney or Sina. History 100 success does not prove real-time full-market quotes have recovered; the site will flag stale market snapshot appropriately.
