// پیگیری سیگنال‌های قبلی از روز سیگنال تا آخرین جلسه (قیمت تعدیل‌شده‌ی tsetmc).
// استفاده: متن __ROWS__ را با آرایه‌ی JSON سطرهای history.csv (فیلدهای ticker, date, insCode) عوض کن و با browser_evaluate اجرا کن.
async () => {
  const rows = __ROWS__;
  const adjust = (rowsIn) => {
    const a = rowsIn.filter(x => x.zTotTran > 0 || x.pClosing > 0).slice().reverse();
    const raw = a.map(x => x.pClosing), dates = a.map(x => String(x.dEven));
    const adj = raw.slice(); let factor = 1;
    for (let i = a.length - 1; i >= 1; i--) {
      const py = a[i].priceYesterday, pc = raw[i - 1];
      if (pc > 0 && py > 0 && Math.abs(py / pc - 1) > 0.005) factor *= py / pc;
      adj[i - 1] = raw[i - 1] * factor;
    }
    return {adj, dates};
  };
  const out = [];
  for (const r of rows) {
    try {
      const j = await (await fetch(`https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/${r.insCode}/520`)).json();
      const {adj, dates} = adjust(j.closingPriceDaily || []);
      const d0 = r.date.replace(/-/g, '');
      const i0 = dates.findIndex(d => d >= d0);
      if (i0 < 0 || i0 >= adj.length - 1) { out.push({ticker: r.ticker, date: r.date, ret_pct: null}); continue; }
      const base = adj[i0], now = adj[adj.length - 1];
      const seg = adj.slice(i0);
      out.push({ticker: r.ticker, date: r.date, ret_pct: +((now / base - 1) * 100).toFixed(1),
                max_pct: +((Math.max(...seg) / base - 1) * 100).toFixed(1),
                min_pct: +((Math.min(...seg) / base - 1) * 100).toFixed(1), last_date: dates[dates.length - 1]});
    } catch (e) { out.push({ticker: r.ticker, date: r.date, ret_pct: null, err: String(e).slice(0, 80)}); }
  }
  return out;
}
