"""
Invite-link subscribers for the Telegram reports.

How it works: the bot has a secret invite link  https://t.me/<bot>?start=<INVITE_CODE>.  Whoever taps it and presses
Start sends "/start <code>" to the bot. Every time the scanner runs, it reads those messages (getUpdates), adds the
sender to subscribers.csv and replies with a welcome. Later reports go to the owner and to all active subscribers;
the personal messages (your watchlist, and the summary that mentions it) go to the owner only.
"/stop" from a subscriber switches the reports off for that person.
Note: Telegram keeps unread messages for only 24 hours, so a new person is registered at the next scanner run.
"""
import csv
import datetime as dt
import hmac
import json
import os

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "subscribers.csv")
DONE = os.path.join(HERE, "backtest_subs.json")
COLS = ["chat_id", "name", "username", "joined_at", "status"]
PRIVATE = {"summary", "watch", "portfolio", "aibasket", "alpaca"}          # owner only
PUBLIC_ONLY = {"summary_pub"}           # subscribers only (summary without the personal watchlist part)

WELCOME = ("سلام {name} 👋\n"
           "ثبت‌نام شدید. از این به بعد گزارش‌های روزانه‌ی بازار برایتان می‌آید: سیگنال‌ها، اقتصاد و کالاها، خبرها و "
           "آزمون زنده‌ی استراتژی‌ها.\n"
           "گزارش بعدی در اجرای بعدیِ ربات (سه‌شنبه تا شنبه، صبح) می‌رسد.\n"
           "این گزارش‌ها خودکار و آزمایشی‌اند و توصیه‌ی خرید یا فروش نیستند.\n"
           "برای قطع گزارش‌ها هر زمان /stop را بفرستید.")
ALREADY = "شما قبلاً ثبت‌نام شده‌اید و گزارش‌ها می‌آید. برای قطع گزارش‌ها /stop را بفرستید."
DENIED = "این ربات خصوصی است. برای عضویت به لینک دعوت نیاز دارید."
STOPPED = "گزارش‌ها برای شما قطع شد. هر وقت خواستید دوباره از لینک دعوت Start بزنید."


def load():
    if not os.path.exists(PATH):
        return []
    with open(PATH, encoding="utf-8", newline="") as f:
        return [{c: row.get(c, "") for c in COLS} for row in csv.DictReader(f)]


def save(rows):
    with open(PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def active_ids():
    return [r["chat_id"] for r in load() if r["status"] == "active"]


def recipients(owner, filename):
    owner = str(owner)
    subs = [c for c in active_ids() if c != owner]
    if filename in PRIVATE:
        return [owner]
    if filename in PUBLIC_ONLY:
        return subs
    return [owner] + subs


def _api(token, method, **params):
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", data=params, timeout=30)
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else {}


def _say(token, chat, text):
    try:
        _api(token, "sendMessage", chat_id=chat, text=text)
    except Exception as e:
        print("subscriber reply failed:", str(e)[:80])


def process(token, owner, code, git_save=None):
    """Read new /start and /stop messages and update subscribers.csv."""
    if not token or not code:
        return
    data = _api(token, "getUpdates", timeout=0, allowed_updates=json.dumps(["message"]))
    updates = data.get("result", []) if data.get("ok") else []
    if not updates:
        return
    rows = load()
    by_id = {r["chat_id"]: r for r in rows}
    joined = []
    for u in updates:
        msg = u.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            continue
        cid, text = str(chat.get("id")), (msg.get("text") or "").strip()
        if cid == str(owner):
            continue
        name = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) or "دوست عزیز"
        user = chat.get("username", "") or ""
        low = text.lower()
        if low.startswith("/start"):
            param = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
            if param and hmac.compare_digest(param, code):
                if cid in by_id and by_id[cid]["status"] == "active":
                    _say(token, cid, ALREADY)
                else:
                    by_id[cid] = {"chat_id": cid, "name": name, "username": user,
                                  "joined_at": dt.date.today().isoformat(), "status": "active"}
                    joined.append(by_id[cid])
                    _say(token, cid, WELCOME.format(name=name))
            elif cid in by_id and by_id[cid]["status"] == "active":
                _say(token, cid, ALREADY)
            else:
                _say(token, cid, DENIED)
        elif low.startswith("/stop"):
            if cid in by_id and by_id[cid]["status"] == "active":
                by_id[cid]["status"] = "stopped"
                _say(token, cid, STOPPED)
    _api(token, "getUpdates", offset=max(u["update_id"] for u in updates) + 1, timeout=0)   # mark as read
    save(list(by_id.values()))
    for j in joined:
        _say(token, owner, f"👤 مشترک جدید: {j['name']}" + (f" (@{j['username']})" if j["username"] else ""))
    if git_save:
        git_save(["subscribers.csv"], f"Subscribers update {dt.date.today()}")


def deactivate(chat_ids, git_save=None):
    """People who blocked the bot (HTTP 403) are switched off so we stop trying."""
    ids = {str(c) for c in chat_ids if c}
    if not ids:
        return
    rows, changed = load(), False
    for r in rows:
        if r["chat_id"] in ids and r["status"] == "active":
            r["status"] = "blocked"
            changed = True
    if changed:
        save(rows)
        if git_save:
            git_save(["subscribers.csv"], f"Subscribers: blocked {dt.date.today()}")


def touch(request_id):
    """Quick 'register now' run: the real work is done at the start of main(); this only marks the request done."""
    with open(DONE, "w", encoding="utf-8") as f:
        json.dump({"request": request_id, "date": dt.date.today().isoformat(), "active": len(active_ids())}, f)
    return True
