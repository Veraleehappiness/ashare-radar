#!/usr/bin/env python3
"""One-time bootstrap of the existing public Netlify site into Git-managed source.

This copies only public static assets, never account data, user cookies or API keys.
It fails closed if the live site is inaccessible. Re-run manually if needed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://playful-kashata-64f33f.netlify.app/"
DATA_URL = "https://raw.githubusercontent.com/Veraleehappiness/ashare-radar/data/market.json"

def fetch(filename: str) -> bytes:
    req = urllib.request.Request(URL + filename, headers={
        "User-Agent": "AShareRadar-StaticSiteBackup/1.0",
        "Accept": "text/html,application/javascript,text/css,application/json,*/*",
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"{filename}: HTTP {response.status}")
        payload = response.read(200_000 + 1)
    if not payload or len(payload) > 200_000:
        raise RuntimeError(f"{filename}: empty or oversized response")
    return payload

def sync(destination: Path) -> str:
    sources = {name: fetch(name) for name in ("index.html", "app.js", "style.css")}
    html = sources["index.html"].decode("utf-8")
    javascript = sources["app.js"].decode("utf-8")
    css = sources["style.css"].decode("utf-8")
    if ("AShare Radar" not in html or "/app.js" not in html or "/style.css" not in html
            or "pageTitles" not in javascript or "market_data_url" not in javascript
            or len(css) < 2000):
        raise RuntimeError("Received HTML/CSS/JS does not match the known Radar static site")
    # Basic safety check; the repo is public. Never mirror embedded API secrets.
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", javascript + html):
        raise RuntimeError("Potential API token embedded in public frontend, refusing to commit")
    config = {
        "market_data_url": DATA_URL,
        "notes": "Public GitHub market-only data; personal watchlists remain device-local.",
    }
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in sources.items():
        (destination / name).write_bytes(content)
    (destination / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "_redirects").write_text("/* /index.html 200\n", encoding="utf-8")
    fallback = {
        "status": "pending", "schema": 2, "generated_at": None, "stocks": [],
        "candidates": [], "sectors": [], "histories": {}, "backtests": {},
        "coverage": {}, "quality": {}, "warnings": ["No live GitHub snapshot available"],
    }
    (destination / "data").mkdir(exist_ok=True)
    (destination / "data" / "market.json").write_text(
        json.dumps(fallback, ensure_ascii=False), encoding="utf-8"
    )
    # Fail explicitly if the live website is not yet the V0.5 user-selected version.
    detected = re.search(r"Personal Research V\d+\.\d+", html)
    version = detected.group(0) if detected else "Version unknown"
    print(f"Imported live Netlify frontend: {version}. Git repository controls future deployments.")
    return version

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default="site")
    args = parser.parse_args()
    try:
        sync(Path(args.destination))
    except (RuntimeError, ValueError, UnicodeError, urllib.error.URLError) as error:
        print("Import failed; repository files left unchanged:", error, file=sys.stderr)
        raise SystemExit(1)
