"""
Optional Gemini helpers (free key from aistudio.google.com).
Every function returns None when no key is set or a call fails, so callers can fall back
to the rule-based / Google-Translate versions.
"""
import json
import os
import re
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]


def key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    path = os.path.join(HERE, "config.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def available():
    return bool(key())


def ask(prompt, json_mode=False, timeout=120):
    k = key()
    if not k:
        return None
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    headers = {"x-goog-api-key": k, "Content-Type": "application/json"}
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(4):
            try:
                r = requests.post(url, headers=headers, json=body, timeout=timeout)
            except Exception as e:
                print("gemini request failed:", str(e)[:100])
                break
            if r.status_code in (429, 500, 503) and attempt < 3:
                time.sleep(8 * (attempt + 1))
                continue
            if r.status_code != 200:
                print(f"gemini {model} -> HTTP {r.status_code}: {r.text[:120]}")
                break
            try:
                parts = r.json()["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    print(f"gemini ok: {model}")
                    return text
            except Exception as e:
                print("gemini parse failed:", str(e)[:100])
            break
    return None


def _json_list(text, n):
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, list) and len(data) == n else None


def translate_fa(texts, chunk=60):
    """English -> fluent simple Persian. Returns a list of the same length, or None on any failure."""
    if not available() or not texts:
        return None
    out = []
    for i in range(0, len(texts), chunk):
        part = [str(t) for t in texts[i:i + chunk]]
        prompt = ("Translate each English text in this JSON array into fluent, simple, natural Persian "
                  "(easy for a general reader; short sentences). Keep company names, tickers, numbers and "
                  "percentages unchanged. Reply ONLY with a JSON array of strings, same length and same order.\n\n"
                  + json.dumps(part, ensure_ascii=False))
        res = _json_list(ask(prompt, json_mode=True), len(part))
        if res is None:
            return None
        out += [str(x).strip() or part[j] for j, x in enumerate(res)]
    return out


def classify_tone(items, chunk=80):
    """items: list of (meaning_if_up, meaning_if_down, headline). Returns list of 'up'/'down'/'neutral' or None."""
    if not available() or not items:
        return None
    out = []
    for i in range(0, len(items), chunk):
        part = items[i:i + chunk]
        lines = [{"up_means": u, "down_means": d, "headline": h} for u, d, h in part]
        prompt = ("For each item decide what the news headline says about its topic. Answer 'up' if the headline "
                  "indicates what 'up_means' describes, 'down' if it indicates what 'down_means' describes, and "
                  "'neutral' if it is unrelated, mixed or gives no clear direction. Be strict: use 'neutral' when unsure. "
                  "Reply ONLY with a JSON array of strings, same length and same order.\n\n"
                  + json.dumps(lines, ensure_ascii=False))
        res = _json_list(ask(prompt, json_mode=True), len(part))
        if res is None:
            return None
        out += [x if x in ("up", "down", "neutral") else "neutral" for x in res]
    return out
