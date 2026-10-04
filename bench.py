"""Benchmark helpers: how much did the market index itself move over the same period?"""
import pandas as pd

INDEX = {"US": "^GSPC", "JP": "^N225", "IN": "^NSEI", "TW": "^TWII", "CN": "000300.SS"}
SERIES = {}


def load(download_all):
    """Download the index series; returns {market: Series} (also kept in SERIES)."""
    data = download_all(list(INDEX.values()))
    for m, sym in INDEX.items():
        s = data.get(sym)
        if s is None:
            continue
        s = s.copy()
        idx = pd.to_datetime(s.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        s.index = idx.normalize()
        SERIES[m] = s[~s.index.duplicated(keep="last")].astype(float).sort_index()
    return SERIES


def ret(*args):
    """Index % change from the last close on/before d0 to the last close on/before d1; None if unknown.
    Call as ret(series_dict, market, d0, d1) or ret(market, d0, d1)."""
    if isinstance(args[0], dict):
        series, market, d0, d1 = args
    else:
        series, (market, d0, d1) = SERIES, args
    s = series.get(market)
    if s is None or len(s) < 2:
        return None
    try:
        a, b = s.asof(pd.Timestamp(d0)), s.asof(pd.Timestamp(d1))
    except Exception:
        return None
    if a != a or b != b or not a:
        return None
    return float((b / a - 1) * 100)
