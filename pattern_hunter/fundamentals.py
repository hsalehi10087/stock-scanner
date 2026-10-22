"""الگویاب — صافی بنیادی: آیا سهم پیشنهادی با «صورت‌های مالی سالم»، «کن‌اسلیم» یا «روش وارن بافت» همخوانی دارد؟

داده از Yahoo (yfinance): get_info، صورت سود و زیان سالانه و فصلی، جریان نقد و ترازنامه.
معیار ناموجود (داده نبود) «نامعلوم» حساب می‌شود و امتیاز نمی‌گیرد.
قبولی هر روش:
  صورت مالی سالم: هر ۵ معیار (رشد فروش ≥۱۰٪، سود سال آخر مثبت و بیشتر از سال قبل، جریان نقد عملیاتی مثبت،
                  نسبت جاری ≥ ۱٫۲، بدهی به حقوق صاحبان سهام < ۱)
  کن‌اسلیم: C و A الزامی، و دست‌کم ۵ از ۷ (C سود فصلی ≥۲۵٪، A سود سالانه ≥۲۵٪، N نزدیک سقف ۵۲ هفته (≤۱۵٪)،
                  S حجم رو به افزایش، L قدرت نسبی ۶ ماهه ≥ ۲۰٪ بالاتر از شاخص، I سهم نهادی ≥ ۲۰٪، M شاخص بالای میانگین ۲۰۰ روزه)
  وارن بافت: ROE ≥ ۱۵٪ و سود مثبت ۴ سال پیاپی الزامی، و دست‌کم ۴ از ۵ (به‌علاوه‌ی بدهی به حقوق < ۰٫۵،
                  حاشیه‌ی سود خالص ≥ ۱۰٪، جریان نقد آزاد مثبت)
"""
import math


def _row(df, names):
    if df is None or getattr(df, 'empty', True):
        return None
    for n in names:
        if n in df.index:
            s = df.loc[n].dropna()
            if len(s):
                return s.sort_index(ascending=False)   # جدیدترین اول
    return None


def _g(a, b):
    return (a - b) / abs(b) if b not in (None, 0) and a is not None and not (isinstance(b, float) and math.isnan(b)) else None


def check(ticker, feat, market_up):
    import yfinance as yf
    tk = yf.Ticker(ticker)
    try:
        i = tk.get_info() or {}
    except Exception:
        i = {}
    try:
        inc, qinc = tk.income_stmt, tk.quarterly_income_stmt
        cf, bs = tk.cashflow, tk.balance_sheet
    except Exception:
        inc = qinc = cf = bs = None
    ni = _row(inc, ['Net Income', 'Net Income Common Stockholders'])
    qni = _row(qinc, ['Net Income', 'Net Income Common Stockholders'])
    rev = _row(inc, ['Total Revenue', 'Operating Revenue'])
    ocf = _row(cf, ['Operating Cash Flow', 'Cash Flow From Continuing Operating Activities'])
    eq = _row(bs, ['Stockholders Equity', 'Common Stock Equity'])
    debt = _row(bs, ['Total Debt'])
    de = i.get('debtToEquity')
    de = de / 100 if de is not None else (float(debt.iloc[0]) / float(eq.iloc[0]) if debt is not None and eq is not None and float(eq.iloc[0]) > 0 else None)
    roe = i.get('returnOnEquity')
    if roe is None and ni is not None and eq is not None and float(eq.iloc[0]) > 0:
        roe = float(ni.iloc[0]) / float(eq.iloc[0])
    q_g = i.get('earningsQuarterlyGrowth')
    if q_g is None and qni is not None and len(qni) >= 5 and float(qni.iloc[4]) > 0:
        q_g = _g(float(qni.iloc[0]), float(qni.iloc[4]))
    a_g = _g(float(ni.iloc[0]), float(ni.iloc[1])) if ni is not None and len(ni) >= 2 and float(ni.iloc[1]) > 0 else None
    rev_g = i.get('revenueGrowth')
    if rev_g is None and rev is not None and len(rev) >= 2:
        rev_g = _g(float(rev.iloc[0]), float(rev.iloc[1]))
    pm = i.get('profitMargins')
    fcf = i.get('freeCashflow')
    cr = i.get('currentRatio')
    inst = i.get('heldPercentInstitutions')

    def b(x, cond):
        return None if x is None else bool(cond(x))
    health = {'رشد فروش ≥۱۰٪': b(rev_g, lambda x: x >= 0.10),
              'سود مثبت و رو به رشد': None if ni is None or len(ni) < 2 else bool(float(ni.iloc[0]) > 0 and float(ni.iloc[0]) > float(ni.iloc[1])),
              'جریان نقد عملیاتی مثبت': None if ocf is None else bool(float(ocf.iloc[0]) > 0),
              'نسبت جاری ≥۱٫۲': b(cr, lambda x: x >= 1.2),
              'بدهی به حقوق <۱': b(de, lambda x: x < 1.0)}
    canslim = {'C': b(q_g, lambda x: x >= 0.25), 'A': b(a_g, lambda x: x >= 0.25),
               'N': b(feat.get('from_hi'), lambda x: x >= -0.15), 'S': b(feat.get('volu_ratio'), lambda x: x >= 1.2),
               'L': b(feat.get('rs6m'), lambda x: x >= 0.20), 'I': b(inst, lambda x: x >= 0.20), 'M': bool(market_up)}
    pos4 = None if ni is None or len(ni) < 4 else bool((ni.iloc[:4].astype(float) > 0).all())
    buffett = {'ROE ≥۱۵٪': b(roe, lambda x: x >= 0.15), 'سود مثبت ۴ سال': pos4, 'بدهی به حقوق <۰٫۵': b(de, lambda x: x < 0.5),
               'حاشیه‌ی سود ≥۱۰٪': b(pm, lambda x: x >= 0.10), 'جریان نقد آزاد مثبت': b(fcf, lambda x: x > 0)}
    n = lambda d: sum(1 for v in d.values() if v)
    passed = []
    if all(v is True for v in health.values()):
        passed.append('صورت مالی')
    if canslim['C'] and canslim['A'] and n(canslim) >= 5:
        passed.append('کن‌اسلیم')
    if buffett['ROE ≥۱۵٪'] and buffett['سود مثبت ۴ سال'] and n(buffett) >= 4:
        passed.append('بافت')
    return {'passed': passed, 'health': f'{n(health)}/5', 'canslim': f'{n(canslim)}/7', 'buffett': f'{n(buffett)}/5',
            'detail': {'health': health, 'canslim': canslim, 'buffett': buffett},
            'numbers': {'rev_growth': rev_g, 'q_earn_growth': q_g, 'annual_earn_growth': a_g, 'roe': roe, 'de': de,
                        'profit_margin': pm, 'fcf': fcf, 'current_ratio': cr}}
