"""Web sources for the investors report:
  * Dataroma (83 'superinvestors', verified readable from the runner): which managers updated their 13F, what they
    bought/sold (latest quarter), and significant insider buys in superinvestor holdings.
  * Capitol Trades (US Congress trades): its site blocks the runner (HTTP 429), so we try the site's own JSON API and
    report plainly if it is blocked.
probe() keeps saving raw samples (web_sample_*) so parsers can be checked against the real pages.
"""
import datetime as dt
import html
import json
import os
import re
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept": "text/html,application/xhtml+xml,application/json", "Accept-Language": "en-US,en;q=0.9"}
DR = "https://www.dataroma.com"
MAX_FETCH = 8          # managers whose activity page is opened per day
PAGES = {
    "dataroma_home": DR + "/m/home.php",
    "capitol_bff": "https://bff.capitoltrades.com/trades?pageSize=100&page=1",
    "capitol_trades": "https://www.capitoltrades.com/trades?pageSize=96",
    "house_watcher": "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
}
CAP_HDR = dict(HDR, Origin="https://www.capitoltrades.com", Referer="https://www.capitoltrades.com/")


def _get(url, hdr=HDR, tries=2):
    for i in range(tries):
        try:
            time.sleep(0.6)
            r = requests.get(url, headers=hdr, timeout=40)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(3)
        except Exception:
            time.sleep(1)
    return None


def probe():
    out, files = {}, []
    for k, u in PAGES.items():
        try:
            r = requests.get(u, headers=CAP_HDR if "capitol" in u else HDR, timeout=40)
            out[k] = {"status": r.status_code, "bytes": len(r.content)}
            if r.status_code == 200:
                ext = "json" if "json" in r.headers.get("content-type", "") else "html"
                fn = f"web_sample_{k}.{ext}"
                open(os.path.join(HERE, fn), "w", encoding="utf-8").write(r.text[:200000])
                files.append(fn)
        except Exception as e:
            out[k] = {"error": type(e).__name__}
    json.dump(out, open(os.path.join(HERE, "web_probe.json"), "w"), indent=1)
    return files + ["web_probe.json"]


# ------------------------------------------------------------------ Dataroma
def dr_updates(text):
    """[(code, name, date)] newest first, from the home page's 'Portfolio Updates' list."""
    out = []
    for code, name, d in re.findall(r'holdings\.php\?m=([A-Za-z0-9_]+)">(.*?)<span class="portb">\s*Updated (\d+ \w+ \d{4})', text, flags=re.S):
        try:
            date = dt.datetime.strptime(d, "%d %b %Y").date()
        except ValueError:
            continue
        out.append((code, html.unescape(re.sub(r"<[^>]+>", "", name)).strip(), date))
    return sorted(out, key=lambda x: x[2], reverse=True)


def dr_activity(text):
    """Latest quarter of an activity page: ('Q2 2026', [(sym, action, pct_change, port_pct)])."""
    parts = re.split(r'<tr class="q_chg">', text)
    if len(parts) < 2:
        return None, []
    q = re.search(r"<b>(Q\d)</b>\s*&nbsp;?\s*<b>(\d{4})</b>", parts[1])
    label = f"{q.group(1)} {q.group(2)}" if q else "?"
    rows = []
    for sym, act, shares, pct in re.findall(
            r'<td class="stock"><a href="/m/stock\.php\?sym=([^"]+)">.*?</a></td>\s*<td class="\w+">([^<]*)</td>\s*'
            r'<td class="\w+">([^<]*)</td>\s*<td>([^<]*)</td>', parts[1], flags=re.S):
        m = re.match(r"\s*(Buy|Add|Reduce|Sell)\w*\s*([\d.,]+)?%?", act)
        if not m:
            continue
        try:
            port = float(pct.replace(",", "")) if pct.strip() else 0.0
        except ValueError:
            port = 0.0
        ch = float(m.group(2).replace(",", "")) if m.group(2) else None
        rows.append((sym.strip(), m.group(1), ch, port))
    return label, rows


def dr_insiders(text):
    """[(date, sym, value_usd, price)] significant insider buys listed on the home page."""
    seg = text.split("Latest significant", 1)
    if len(seg) < 2:
        return []
    seg = seg[1].split("</table>", 1)[0]
    out = []
    for d, sym, amt, pr in re.findall(r'<tr>\s*<td>([^<]+)</td>\s*<td class="st"><a href="/m/stock\.php\?sym=([^"]+)">[^<]*</a>[^<]*</td>\s*'
                                      r'<td class="amt">([^<]*)</td>\s*<td class="pr">([^<]*)</td>', seg):
        try:
            out.append((d.strip(), sym.strip(), float(amt.replace(",", "")), float(pr.replace(",", "") or 0)))
        except ValueError:
            continue
    return out


def pre(lines):
    return "<b><pre>" + html.escape("\n".join(lines)) + "</pre></b>"


def fmt_activity(rows, top=7):
    # biggest portfolio impact first
    rows = sorted(rows, key=lambda r: -abs(r[3]))[:top]
    t = [f"{'Stock':<7}{'Move':<8}{'Chg%':>7}{'Port%':>7}", "-" * 29]
    for sym, act, ch, port in rows:
        word = {"Buy": "NEW", "Add": "Add", "Reduce": "Trim", "Sell": "SOLD"}[act]
        icon = "+" if act in ("Buy", "Add") else "-"
        chs = f"{ch:.0f}" if ch is not None else "-"
        t.append(f"{sym[:6]:<7}{icon + word:<8}{chs:>7}{port:>7.2f}")
    return pre(t)


def dataroma_blocks(state, today, first_run, errors):
    r = _get(DR + "/m/home.php")
    if r is None:
        errors.append("Dataroma: صفحه’ی اصلی خوانده نشد")
        return []
    text = r.text
    ups = dr_updates(text)
    if not ups:
        errors.append("Dataroma: فهرست به‌روزرسانی‌ها پیدا نشد (ساختار صفحه عوض شده؟)")
    seen = state.setdefault("dr_seen", {})
    first_dr = not seen
    todo = []
    for code, name, d in ups:
        if seen.get(code) != d.isoformat():
            if not first_dr or len(todo) < 5:      # baseline: show only the 5 freshest
                todo.append((code, name, d))
            seen[code] = d.isoformat()
    blocks = []
    head = ("📌 <b>آخرین فایل‌های ۱۳F — Dataroma</b> (۵ مورد تازه‌تر؛ از فردا فقط موارد جدید)" if first_dr
            else f"📌 <b>سرمایه‌گذارانی که امروز پرتفویشان به‌روز شد (Dataroma)</b>")
    parts = []
    for code, name, d in todo[:MAX_FETCH]:
        rr = _get(DR + f"/m/m_activity.php?m={code}")
        if rr is None:
            errors.append(f"Dataroma: فعالیت {name} خوانده نشد")
            continue
        label, rows = dr_activity(rr.text)
        if not rows:
            parts.append(f"<b>{html.escape(name)}</b> — {label or ''} (ثبت {d}): تغییری ثبت نشده")
            continue
        parts.append(f"<b>{html.escape(name)}</b> — فصل {label} (ثبت {d})\n" + fmt_activity(rows))
    if len(todo) > MAX_FETCH:
        parts.append("و همچنین: " + "، ".join(html.escape(n) for _, n, _ in todo[MAX_FETCH:MAX_FETCH + 15]))
    if parts:
        blocks.append(head + "\nMove: NEW خرید جدید · Add افزایش · Trim کاهش · SOLD فروش کامل · "
                      "Chg% تغییر تعداد سهم · Port% اثر روی سبد (درصد)\n" + "\n\n".join(parts))
    # insider buys
    ins = dr_insiders(text)
    ins_seen = set(state.get("dr_ins_seen", []))
    agg = {}
    for d, sym, amt, pr in ins:
        k = f"{d}|{sym}"
        a = agg.setdefault(k, [d, sym, 0.0, pr])
        a[2] += amt
    new = [v for k, v in agg.items() if f"{k}|{int(v[2])}" not in ins_seen]
    state["dr_ins_seen"] = [f"{k}|{int(v[2])}" for k, v in agg.items()][-300:]
    if new:
        new = sorted(new, key=lambda v: -v[2])[:8]
        t = [f"{'Filed':<7}{'Stock':<7}{'Value$':>10}{'Price':>8}", "-" * 32]
        for d, sym, amt, pr in new:
            t.append(f"{d:<7}{sym[:6]:<7}{amt:>10,.0f}{pr:>8.2f}")
        blocks.append("🧑‍💼 <b>خرید مهم مدیران در سهام‌های سرمایه‌گذاران بزرگ (Dataroma)</b>\n" + pre(t))
    return blocks


# ------------------------------------------------------------------ Capitol Trades (Congress)
CONG_TICKERS = ("NVDA AAPL MSFT GOOGL AMZN META TSLA AVGO AMD PLTR NFLX ORCL CRM INTC MU QCOM JPM V COST LLY UNH XOM "
                "SMCI ARM COIN MSTR BA DIS UBER TSM ASML").split()


def finnhub_key():
    k = os.environ.get("FINNHUB_KEY")
    if k:
        return k.strip()
    try:
        for line in open(os.path.join(HERE, "config.txt"), encoding="utf-8"):
            if line.startswith("FINNHUB_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def congress_blocks(state, today, errors):
    """US Congress trades from Finnhub /stock/congressional-trading, for a list of popular tickers."""
    key = finnhub_key()
    if not key:
        errors.append("Finnhub: کلید در config.txt نیست")
        return []
    rows, bad = [], None
    frm = (today - dt.timedelta(days=60)).isoformat()
    for tk in CONG_TICKERS:
        try:
            time.sleep(0.4)
            r = requests.get("https://finnhub.io/api/v1/stock/congressional-trading",
                             params={"symbol": tk, "from": frm, "to": today.isoformat(), "token": key}, timeout=30)
        except Exception:
            continue
        if r.status_code in (401, 403):
            bad = r.status_code
            break
        if r.status_code != 200:
            continue
        try:
            for x in r.json().get("data", []):
                rows.append({"id": f"{x.get('name')}|{x.get('symbol') or tk}|{x.get('transactionDate')}|{x.get('transactionType')}|{x.get('amountFrom')}",
                             "pub": str(x.get("filingDate", ""))[:10], "sym": (x.get("symbol") or tk)[:6],
                             "type": "Buy" if "purch" in str(x.get("transactionType", "")).lower() else ("Sell" if "sale" in str(x.get("transactionType", "")).lower() else "Other"),
                             "who": str(x.get("name", "?")).split()[-1][:11], "mid": ((x.get("amountFrom") or 0) + (x.get("amountTo") or 0)) / 2})
        except Exception:
            continue
    if bad:
        errors.append(f"Finnhub: کلید یا پلن اجازه‌ی داده‌ی کنگره را نمی‌دهد (خطای {bad})")
        return []
    if not rows:
        return []
    seen = set(state.get("cap_seen", []))
    first = "cap_seen" not in state
    state["cap_seen"] = (list(seen) + [x["id"] for x in rows])[-1500:]
    new = rows if first else [x for x in rows if x["id"] not in seen]
    new = sorted(new, key=lambda x: (x["pub"], x["mid"]), reverse=True)[:12]
    if not new:
        return []
    t = [f"{'Filed':<6}{'Stock':<7}{'Type':<5}{'Politician':<12}{'Size
    if r is None:
        errors.append("Capitol Trades: سایت از سرور ما جلوگیری می‌کند؛ معاملات کنگره امروز نیامد")
        return []
    try:
        data = r.json().get("data", [])
    except Exception:
        errors.append("Capitol Trades: پاسخ قابل‌خواندن نبود")
        return []
    rows = []
    for x in data:
        try:
            pol = x.get("politician", {}) or {}
            iss = x.get("issuer", {}) or {}
            sym = (iss.get("issuerTicker") or "").split(":")[0] or (iss.get("issuerName") or "?")[:6]
            size = x.get("value")
            rows.append({"id": str(x.get("_txId") or f"{pol.get('lastName')}{sym}{x.get('txDate')}{size}"),
                         "pub": str(x.get("pubDate", ""))[:10], "tx": str(x.get("txDate", ""))[:10],
                         "who": f"{(pol.get('lastName') or '?')[:9]} {(pol.get('party') or '?')[:1].upper()}",
                         "sym": sym[:6], "type": str(x.get("txType", "?")), "usd": size or 0})
        except Exception:
            continue
    if not rows:
        errors.append("Capitol Trades: فهرست خالی بود (ساختار عوض شده؟)")
        return []
    seen = set(state.get("cap_seen", []))
    first = "cap_seen" not in state
    state["cap_seen"] = (list(seen) + [x["id"] for x in rows])[-600:]
    new = rows if first else [x for x in rows if x["id"] not in seen]
    new = sorted(new, key=lambda x: (x["pub"], x["usd"]), reverse=True)[:12]
    if not new:
        return []
    t = [f"{'Pub':<6}{'Stock':<7}{'Type':<5}{'Politician':<12}{'Size$':>7}", "-" * 37]
    for x in new:
        usd = f"{x['usd'] / 1000:.0f}K" if x["usd"] else "-"
        t.append(f"{x['pub'][5:]:<6}{x['sym']:<7}{x['type'][:4]:<5}{x['who']:<12}{usd:>7}")
    return ["🏛 <b>معاملات سیاستمداران آمریکا (Capitol Trades)</b> — " + ("آخرین‌ها" if first else "موارد تازه") +
            "\n<i>اعلام این معاملات تا ۴۵ روز دیرتر از انجامشان است؛ Size$ میانه‌ی بازه‌ی اعلام‌شده است.</i>\n" + pre(t)]


def run(state, today, first_run):
    errors, blocks = [], []
    try:
        blocks += dataroma_blocks(state, today, first_run, errors)
    except Exception as e:
        errors.append(f"Dataroma: خطا ({type(e).__name__})")
    try:
        blocks += congress_blocks(state, today, errors)
    except Exception as e:
        errors.append(f"Capitol Trades: خطا ({type(e).__name__})")
    return blocks, errors
:>6}", "-" * 36]
    for x in new:
        usd = f"{x['mid'] / 1000:.0f}K" if x["mid"] else "-"
        t.append(f"{x['pub'][5:]:<6}{x['sym']:<7}{x['type']:<5}{x['who']:<12}{usd:>6}")
    return ["🏛 <b>معاملات سیاستمداران آمریکا (Finnhub)</b> — " + ("آخرین‌ها" if first else "موارد تازه") +
            "\n<i>اعلام این معاملات تا ۴۵ روز دیرتر از انجامشان است؛ Size$ میانه‌ی بازه‌ی اعلام‌شده است. فقط ۳۰ سهم پرطرفدار بررسی می‌شود.</i>\n" + pre(t)]


def _congress_old(state, today, errors):
    r = _get(PAGES["capitol_bff"], CAP_HDR)
    if r is None:
        errors.append("Capitol Trades: سایت از سرور ما جلوگیری می‌کند؛ معاملات کنگره امروز نیامد")
        return []
    try:
        data = r.json().get("data", [])
    except Exception:
        errors.append("Capitol Trades: پاسخ قابل‌خواندن نبود")
        return []
    rows = []
    for x in data:
        try:
            pol = x.get("politician", {}) or {}
            iss = x.get("issuer", {}) or {}
            sym = (iss.get("issuerTicker") or "").split(":")[0] or (iss.get("issuerName") or "?")[:6]
            size = x.get("value")
            rows.append({"id": str(x.get("_txId") or f"{pol.get('lastName')}{sym}{x.get('txDate')}{size}"),
                         "pub": str(x.get("pubDate", ""))[:10], "tx": str(x.get("txDate", ""))[:10],
                         "who": f"{(pol.get('lastName') or '?')[:9]} {(pol.get('party') or '?')[:1].upper()}",
                         "sym": sym[:6], "type": str(x.get("txType", "?")), "usd": size or 0})
        except Exception:
            continue
    if not rows:
        errors.append("Capitol Trades: فهرست خالی بود (ساختار عوض شده؟)")
        return []
    seen = set(state.get("cap_seen", []))
    first = "cap_seen" not in state
    state["cap_seen"] = (list(seen) + [x["id"] for x in rows])[-600:]
    new = rows if first else [x for x in rows if x["id"] not in seen]
    new = sorted(new, key=lambda x: (x["pub"], x["usd"]), reverse=True)[:12]
    if not new:
        return []
    t = [f"{'Pub':<6}{'Stock':<7}{'Type':<5}{'Politician':<12}{'Size$':>7}", "-" * 37]
    for x in new:
        usd = f"{x['usd'] / 1000:.0f}K" if x["usd"] else "-"
        t.append(f"{x['pub'][5:]:<6}{x['sym']:<7}{x['type'][:4]:<5}{x['who']:<12}{usd:>7}")
    return ["🏛 <b>معاملات سیاستمداران آمریکا (Capitol Trades)</b> — " + ("آخرین‌ها" if first else "موارد تازه") +
            "\n<i>اعلام این معاملات تا ۴۵ روز دیرتر از انجامشان است؛ Size$ میانه‌ی بازه‌ی اعلام‌شده است.</i>\n" + pre(t)]


def run(state, today, first_run):
    errors, blocks = [], []
    try:
        blocks += dataroma_blocks(state, today, first_run, errors)
    except Exception as e:
        errors.append(f"Dataroma: خطا ({type(e).__name__})")
    try:
        blocks += congress_blocks(state, today, errors)
    except Exception as e:
        errors.append(f"Capitol Trades: خطا ({type(e).__name__})")
    return blocks, errors
