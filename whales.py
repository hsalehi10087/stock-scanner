"""
🐋 Famous investors' portfolios (SEC 13F) + insider trades (SEC Form 4) of well-known companies.
Free public data from SEC EDGAR. Limits: a 13F is filed 45 days AFTER each quarter ends and shows only US-listed
long positions (not the investor's trades today); Form 4 shows insiders' trades within 2 business days.
State: whales_state.json (which filings were already reported, Form 4 already shown) and
       whales_cache.json (latest summary per investor, so each day only a few requests are needed).
"""
import datetime as dt
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "whales_state.json")
CACHE = os.path.join(HERE, "whales_cache.json")
UA = {"User-Agent": "StockScannerPersonal hs10087@gmail.com", "Accept-Encoding": "gzip, deflate"}

# (label, CIK, word that must appear in the SEC name - protects against a wrong CIK)
FILERS = [
    ("وارن بافت · Berkshire", 1067983, "berkshire"),
    ("بیل اکمن · Pershing Square", 1336528, "pershing"),
    ("مایکل بری · Scion", 1649339, "scion"),
    ("ری دالیو · Bridgewater", 1350694, "bridgewater"),
    ("استنلی دراکنمیلر · Duquesne", 1536411, "duquesne"),
    ("جرج سوروس · Soros Fund", 1029160, "soros"),
    ("دیوید تپر · Appaloosa", 1656456, "appaloosa"),
    ("کارل آیکان · Icahn", 921669, "icahn"),
    ("دن لوب · Third Point", 1040273, "third point"),
    ("ست کلارمن · Baupost", 1061768, "baupost"),
    ("کتی وود · ARK", 1697748, "ark investment"),
    ("چیس کلمن · Tiger Global", 1167483, "tiger global"),
    ("فیلیپ لافون · Coatue", 1135730, "coatue"),
    ("لی لو · Himalaya", 1709323, "himalaya"),
    ("مونیش پابرای · Dalal Street", 1549575, "dalal"),
    ("دیوید آینهورن · Greenlight", 1079114, "greenlight"),
    ("کریس هون · TCI", 1647251, "tci"),
]
# companies whose insider (Form 4) trades are followed: (ticker, CIK)
ISSUERS = [("NVDA", 1045810), ("META", 1326801), ("TSLA", 1318605), ("AMZN", 1018724), ("AAPL", 320193),
           ("MSFT", 789019), ("GOOGL", 1652044), ("PLTR", 1321655), ("AVGO", 1730168), ("JPM", 19617)]
MIN_INSIDER_USD = 500_000
TOP_N = 60            # positions kept per investor in the cache


def _get(url, tries=3):
    for i in range(tries):
        try:
            time.sleep(0.15)
            r = requests.get(url, headers=UA, timeout=40)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429):
                time.sleep(2 + 2 * i)
        except Exception:
            time.sleep(1 + i)
    return None


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def submissions(cik):
    r = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if r is None:
        return None
    try:
        return r.json()
    except Exception:
        return None


def filings_of(sub, forms):
    rec = sub.get("filings", {}).get("recent", {})
    out = []
    for i, f in enumerate(rec.get("form", [])):
        if f in forms:
            out.append({"form": f, "acc": rec["accessionNumber"][i], "filed": rec["filingDate"][i],
                        "period": rec.get("reportDate", [""] * (i + 1))[i], "doc": rec.get("primaryDocument", [""] * (i + 1))[i]})
    return out


def parse_infotable(content):
    root = ET.fromstring(content)
    pos = {}
    for el in root.iter():
        if _local(el.tag) != "infoTable":
            continue
        d = {}
        for ch in el.iter():
            d[_local(ch.tag)] = (ch.text or "").strip()
        try:
            value = float(d.get("value", "0") or 0)
            shares = float(d.get("sshPrnamt", "0") or 0)
        except ValueError:
            continue
        key = (d.get("cusip", "") or d.get("nameOfIssuer", "")) + ("|" + d["putCall"].upper() if d.get("putCall") else "")
        cur = pos.setdefault(key, {"name": d.get("nameOfIssuer", "?"), "value": 0.0, "shares": 0.0,
                                   "pc": d.get("putCall", "").upper()})
        cur["value"] += value
        cur["shares"] += shares
    return pos


def holdings(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    r = _get(base + "/index.json")
    if r is None:
        return None
    try:
        names = [x["name"] for x in r.json()["directory"]["item"]]
    except Exception:
        return None
    xmls = [n for n in names if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
    xmls.sort(key=lambda n: ("info" not in n.lower(), n))
    for n in xmls:
        rr = _get(f"{base}/{n}")
        if rr is None:
            continue
        try:
            pos = parse_infotable(rr.content)
        except Exception:
            continue
        if pos:
            return pos
    return None


def short_name(n):
    orig = re.sub(r"[.,]", "", n.upper())
    n = re.sub(r"\b(INC|CORP|CORPORATION|CO|LTD|PLC|HOLDINGS|HLDGS|GROUP|CL [A-C]|CLASS [A-C]|COM|NEW|SHS|ORD|NV|SA|LP)\b", "", orig)
    n = re.sub(r"\s+", " ", n).strip().title()[:22]
    return n or orig.title()[:22]


def summarize(pos):
    total = sum(p["value"] for p in pos.values()) or 1.0
    rows = sorted(pos.items(), key=lambda kv: -kv[1]["value"])[:TOP_N]
    return {"total": total, "n": len(pos),
            "top": [{"k": k, "name": p["name"], "w": round(p["value"] / total * 100, 2), "shares": p["shares"],
                     "pc": p["pc"]} for k, p in rows]}


def diff(cur, prev):
    """Changes between two holdings dicts, as weights of the current portfolio."""
    tc = sum(p["value"] for p in cur.values()) or 1.0
    tp = sum(p["value"] for p in prev.values()) or 1.0
    new, gone, up, down = [], [], [], []
    for k, p in cur.items():
        w = p["value"] / tc * 100
        if k not in prev:
            if w >= 0.5:
                new.append((w, p["name"], p["pc"]))
            continue
        a, b = prev[k]["shares"], p["shares"]
        if a > 0:
            ch = (b / a - 1) * 100
            if ch >= 25 and w >= 0.5:
                up.append((w, p["name"], ch, p["pc"]))
            elif ch <= -25 and prev[k]["value"] / tp * 100 >= 0.5:
                down.append((w, p["name"], ch, p["pc"]))
    for k, p in prev.items():
        w = p["value"] / tp * 100
        if k not in cur and w >= 0.5:
            gone.append((w, p["name"], p["pc"]))
    key = lambda x: -x[0]
    return {"new": sorted(new, key=key)[:6], "gone": sorted(gone, key=key)[:6],
            "up": sorted(up, key=key)[:6], "down": sorted(down, key=key)[:6]}


def tag_pc(pc):
    return " (Put)" if pc == "PUT" else (" (Call)" if pc == "CALL" else "")


def pre(lines):
    return "<b><pre>" + html.escape("\n".join(lines)) + "</pre></b>"


def fmt_diff(d):
    """Changes as a small table: Move / Stock / Chg% / Wt% (weight in the portfolio; for SOLD the old weight)."""
    rows = []
    for w, n, pc in d["new"]:
        rows.append(("NEW", short_name(n) + tag_pc(pc), "-", w))
    for w, n, ch, pc in d["up"]:
        rows.append(("ADD", short_name(n) + tag_pc(pc), f"+{ch:.0f}", w))
    for w, n, ch, pc in d["down"]:
        rows.append(("CUT", short_name(n) + tag_pc(pc), f"{ch:.0f}", w))
    for w, n, pc in d["gone"]:
        rows.append(("SOLD", short_name(n) + tag_pc(pc), "-100", w))
    if not rows:
        return "تغییر قابل‌توجهی نبود (کمتر از ۲۵٪ تغییر سهم یا زیر ۰٫۵٪ سبد)."
    t = [f"{'Move':<6}{'Stock':<15}{'Chg%':>5}{'Wt%':>5}", "-" * 31]
    for mv, nm, ch, w in rows:
        t.append(f"{mv:<6}{nm[:14]:<15}{ch:>5}{w:>5.1f}")
    return pre(t)


def fmt_top(top, k=6):
    t = [f"{'Top holdings':<20}{'Wt%':>6}", "-" * 26]
    for x in top[:k]:
        t.append(f"{(short_name(x['name']) + tag_pc(x['pc']))[:19]:<20}{x['w']:>6.1f}")
    return pre(t)


def refresh_investor(label, cik, word, cache, state, first_run):
    """Checks one investor; returns (new_filing_lines or None, error or None)."""
    sub = submissions(cik)
    if not sub:
        return None, f"{label}: دریافت نشد"
    if word not in str(sub.get("name", "")).lower():
        return None, f"{label}: نام ثبت‌شده در SEC ({sub.get('name')}) با انتظار نمی‌خواند؛ کنار گذاشته شد"
    fl = filings_of(sub, ("13F-HR",))
    if not fl:
        return None, f"{label}: فایل ۱۳F پیدا نشد"
    latest = fl[0]
    ent = cache.get(str(cik))
    if ent and ent.get("acc") == latest["acc"]:
        return None, None
    cur = holdings(cik, latest["acc"])
    if not cur:
        return None, f"{label}: جدول سهام فایل {latest['acc']} خوانده نشد"
    prev = holdings(cik, fl[1]["acc"]) if len(fl) > 1 else None
    entry = {"label": label, "name": sub.get("name"), "acc": latest["acc"], "filed": latest["filed"],
             "period": latest["period"], "prev_period": fl[1]["period"] if len(fl) > 1 else "",
             "summary": summarize(cur), "diff": diff(cur, prev) if prev else None}
    cache[str(cik)] = entry
    if first_run or not ent:
        return None, None
    return entry, None


def period_label(p):
    try:
        y, m, _ = p.split("-")
        return f"{y}-Q{(int(m) - 1) // 3 + 1}"
    except Exception:
        return p


def next_deadline(today):
    for y in (today.year, today.year + 1):
        for m, d in ((2, 14), (5, 15), (8, 14), (11, 14)):
            x = dt.date(y, m, d)
            if x >= today:
                return x
    return None


# ------------------------------------------------------------------ Form 4
def parse_form4(content):
    root = ET.fromstring(content)
    owner, role = "?", []
    out = []
    for el in root.iter():
        t = _local(el.tag)
        if t == "rptOwnerName" and el.text:
            owner = el.text.strip().title()
        elif t == "officerTitle" and el.text:
            role.append(el.text.strip())
        elif t == "isDirector" and (el.text or "").strip() in ("1", "true"):
            role.append("Director")
        elif t == "isTenPercentOwner" and (el.text or "").strip() in ("1", "true"):
            role.append("10% owner")
    for tr in root.iter():
        if _local(tr.tag) != "nonDerivativeTransaction":
            continue
        g = {}
        for ch in tr.iter():
            if ch.text and ch.text.strip():
                g.setdefault(_local(ch.tag), ch.text.strip())
        # tags like 'value' repeat, so read specific parents
        def val(parent):
            for p in tr.iter():
                if _local(p.tag) == parent:
                    for c in p:
                        if _local(c.tag) == "value" and c.text:
                            return c.text.strip()
            return None
        code = g.get("transactionCode")
        try:
            sh = float(val("transactionShares") or 0)
            px = float(val("transactionPricePerShare") or 0)
        except ValueError:
            continue
        out.append({"code": code, "shares": sh, "price": px, "ad": val("transactionAcquiredDisposedCode"),
                    "date": val("transactionDate") or ""})
    return owner, ", ".join(dict.fromkeys(role)), out


def insider_trades(state, today):
    seen = set(state.get("form4_seen", []))
    first = "form4_seen" not in state
    lines, new_seen = [], []
    for tk, cik in ISSUERS:
        sub = submissions(cik)
        if not sub:
            continue
        for f in filings_of(sub, ("4",)):
            if f["acc"] in seen:
                continue
            try:
                age = (today - dt.date.fromisoformat(f["filed"])).days
            except ValueError:
                continue
            if age > 4:
                continue
            new_seen.append(f["acc"])
            if first:
                continue
            doc = f["doc"].split("/", 1)[-1] if f["doc"].startswith("xsl") else f["doc"]
            r = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['acc'].replace('-', '')}/{doc}")
            if r is None:
                continue
            try:
                owner, role, trs = parse_form4(r.content)
            except Exception:
                continue
            tot = {"P": [0.0, 0.0], "S": [0.0, 0.0]}
            for t in trs:
                if t["code"] in tot:
                    tot[t["code"]][0] += t["shares"]
                    tot[t["code"]][1] += t["shares"] * t["price"]
            for code, (sh, usd) in tot.items():
                if usd >= MIN_INSIDER_USD:
                    lines.append((usd, {"date": f["filed"][5:], "sym": tk, "act": "BUY" if code == "P" else "SELL",
                                        "who": owner.split()[0][:9] if owner else "?", "usd": usd}))
    state["form4_seen"] = (list(seen) + new_seen)[-400:]
    return [x for _, x in sorted(lines, key=lambda x: -x[0])[:10]], first


# ------------------------------------------------------------------ main entry
def run(today=None):
    """Returns (telegram_blocks, summary_lines, files_changed)."""
    today = today or dt.date.today()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    first_run = not cache
    new_filings, errors = [], []
    for label, cik, word in FILERS:
        try:
            ent, err = refresh_investor(label, cik, word, cache, state, first_run)
        except Exception as e:
            ent, err = None, f"{label}: خطا ({type(e).__name__})"
        if ent:
            new_filings.append(ent)
        if err:
            errors.append(err)
    ins_rows, ins_first = [], False
    try:
        ins_rows, ins_first = insider_trades(state, today)
    except Exception as e:
        errors.append(f"معاملات داخلی: خطا ({type(e).__name__})")
    web_blocks = []
    try:
        import whales_web
        web_blocks, web_err = whales_web.run(state, today, first_run)
        errors += web_err
    except Exception as e:
        errors.append(f"منابع وب: خطا ({type(e).__name__})")
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    json.dump(state, open(STATE, "w"), ensure_ascii=False)
    if not cache:
        return [f"🐋 <b>سرمایه‌گذاران بزرگ</b> — {today}\nامروز داده‌ای از SEC دریافت نشد."] + web_blocks, [], False

    name_fa = lambda lab: html.escape(lab.split(" · ")[0])
    blocks = [f"🐋 <b>گزارش سرمایه‌گذاران بزرگ</b> — {today}\n"
              "<i>منبع: SEC و Dataroma. فایل ۱۳F فصلی است و ۴۵ روز دیرتر می‌آید؛ معاملات مدیران روزانه است.</i>"]
    hl = []
    if first_run:
        for label, cik, _ in FILERS:
            e = cache.get(str(cik))
            if e:
                blocks.append(f"<b>{name_fa(label)}</b> — {period_label(e['period'])}، {e['summary']['n']} سهم\n" + fmt_top(e["summary"]["top"], 5))
    for e in new_filings:
        blocks.append(f"📄 <b>فایل جدید: {name_fa(e['label'])}</b> — فصل {period_label(e['period'])} (ثبت {e['filed']})\n"
                      + (fmt_diff(e["diff"]) if e["diff"] else "فصل قبلی برای مقایسه نبود.")
                      + "\n" + fmt_top(e["summary"]["top"], 5)
                      + "\n<i>Move: NEW خرید جدید · ADD افزایش · CUT کاهش · SOLD فروش کامل · Chg% تغییر تعداد سهم · Wt% وزن در سبد</i>")
    if new_filings:
        hl.append("• فایل جدید ۱۳F: " + "، ".join(e["label"].split(" · ")[0] for e in new_filings) + ".")
    else:
        blocks.append("📄 امروز فایل ۱۳F جدیدی از سرمایه‌گذاران SEC-محور ثبت نشد.")
    if ins_rows:
        t = [f"{'Date':<6}{'Stock':<6}{'Act':<5}{'Insider':<10}{'$M':>5}", "-" * 32]
        for x in ins_rows:
            t.append(f"{x['date']:<6}{x['sym']:<6}{x['act']:<5}{x['who']:<10}{x['usd'] / 1e6:>5.1f}")
        blocks.append("🧑‍💼 <b>معاملات مدیران بزرگ‌ترین شرکت‌ها (فرم ۴، بالای ۵۰۰ هزار دلار)</b>\n" + pre(t))
        hl.append(f"• {len(ins_rows)} معامله‌ی مهم مدیران.")
    elif ins_first:
        blocks.append("🧑‍💼 پیگیری معاملات مدیران ۱۰ شرکت بزرگ از امروز شروع شد؛ موارد جدید از فردا می‌آید.")
    else:
        blocks.append("🧑‍💼 معامله‌ی مهم (بالای ۵۰۰ هزار دلار) از مدیران شرکت‌های دنبال‌شده نبود.")
    keys = [str(c) for _, c, _ in FILERS if str(c) in cache]
    if keys and not first_run and not new_filings:
        e = cache[keys[today.toordinal() % len(keys)]]
        sp = f"🔦 <b>تمرکز امروز: {name_fa(e['label'])}</b> — فصل {period_label(e['period'])}، {e['summary']['n']} سهم\n" + fmt_top(e["summary"]["top"], 8)
        if e.get("diff"):
            sp += "\nتغییرات نسبت به فصل قبل:\n" + fmt_diff(e["diff"])
        blocks.append(sp)
    blocks += web_blocks
    foot = []
    nd = next_deadline(today)
    if nd:
        foot.append(f"⏳ مهلت ۱۳F فصل بعد: {nd}")
    if errors:
        foot.append("⚠️ " + "؛ ".join(errors[:4]))
    foot.append("اطلاعات عمومی است و توصیه‌ی خرید یا فروش نیست.")
    blocks.append("<i>" + html.escape("\n".join(foot)) + "</i>")
    return blocks, hl, True
