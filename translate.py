"""Free English -> Persian translation (Google Translate public endpoint, no key). Falls back to the original text."""
import requests

URL = "https://translate.googleapis.com/translate_a/single"


def _one(text, tl="fa"):
    r = requests.post(URL, params={"client": "gtx", "sl": "auto", "tl": tl, "dt": "t"},
                      data={"q": text}, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    return "".join(seg[0] for seg in r.json()[0] if seg and seg[0])


def fa_list(texts, tl="fa"):
    """Translate a list of short texts; keeps order and length; returns originals on failure."""
    texts = [str(t) for t in texts]
    if not texts:
        return []
    out = list(texts)
    # batch with newlines, chunk to stay under the endpoint limit
    batches, cur = [], []
    for i, t in enumerate(texts):
        if cur and sum(len(texts[j]) + 1 for j in cur) + len(t) > 4000:
            batches.append(cur)
            cur = []
        cur.append(i)
    if cur:
        batches.append(cur)
    for idx in batches:
        src = "\n".join(texts[i].replace("\n", " ") for i in idx)
        try:
            parts = _one(src, tl).split("\n")
            if len(parts) == len(idx):
                for i, p in zip(idx, parts):
                    out[i] = p.strip() or texts[i]
                continue
        except Exception as e:
            print("translate batch failed:", str(e)[:100])
        for i in idx:  # fallback: one by one
            try:
                out[i] = _one(texts[i], tl).strip() or texts[i]
            except Exception:
                pass
    return out
