"""Probe: can the GitHub runner read Dataroma and Capitol Trades? Saves raw samples so parsers can be written
against the real HTML (web_probe.json = status codes; web_sample_*.html = first 300KB of each page)."""
import json
import os

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
PAGES = {
    "dataroma_home": "https://www.dataroma.com/m/home.php",
    "dataroma_managers": "https://www.dataroma.com/m/managers.php",
    "dataroma_activity_brk": "https://www.dataroma.com/m/m_activity.php?m=BRK",
    "dataroma_holdings_brk": "https://www.dataroma.com/m/holdings.php?m=BRK",
    "capitol_trades": "https://www.capitoltrades.com/trades?pageSize=96",
}


def probe():
    out, files = {}, []
    for k, u in PAGES.items():
        try:
            r = requests.get(u, headers=HDR, timeout=40)
            out[k] = {"status": r.status_code, "bytes": len(r.content), "tables": r.text.lower().count("<table")}
            if r.status_code == 200:
                fn = f"web_sample_{k}.html"
                open(os.path.join(HERE, fn), "w", encoding="utf-8").write(r.text[:300000])
                files.append(fn)
        except Exception as e:
            out[k] = {"error": type(e).__name__}
    json.dump(out, open(os.path.join(HERE, "web_probe.json"), "w"), indent=1)
    return files + ["web_probe.json"]
