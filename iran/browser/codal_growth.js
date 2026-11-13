async (page) => {
  const st = JSON.parse(await page.evaluate(() => window.name));
  const syms = st.syms;
  await page.evaluate((n) => { window.__cdr = {status:'running', done:0, total:n, res:{}, err:[]}; }, syms.length);
  const parseFn = (h) => {
    const FA='۰۱۲۳۴۵۶۷۸۹';
    const norm=s=>(s==null?'':String(s)).replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/‌/g,' ').replace(/\s+/g,' ').trim();
    const ns=s=>norm(s).replace(/ /g,'');
    const en=s=>s.replace(/[۰-۹]/g,c=>FA.indexOf(c));
    const num=s=>{if(s==null)return null;let x=en(norm(s)).replace(/[,٬ ]/g,'');if(['','-','--'].includes(x))return null;let neg=false;
      if(x.startsWith('(')&&x.endsWith(')')){neg=true;x=x.slice(1,-1);}if(x.startsWith('-')){neg=true;x=x.slice(1);}
      if(!/^\d+(\.\d+)?$/.test(x))return null;const v=parseFloat(x);return neg?-v:v;};
    const growth=(c,p)=>(c==null||p==null||p<=0)?null:Math.round((c/p-1)*1000)/10;
    const doc=new DOMParser().parseFromString(h,'text/html');
    for(const tb of doc.querySelectorAll('table')){const txt=ns(tb.textContent);if(!txt.startsWith('شرح')||!txt.includes('درصدتغییر'))continue;
      const rows=[...tb.querySelectorAll('tr')].map(tr=>[...tr.children].filter(c=>/^(TD|TH)$/.test(c.tagName)).map(c=>norm(c.textContent)));
      const npRows=rows.filter(r=>r.length>=3&&/^سود\(زیان\)خالص$/.test(ns(r[0]))&&num(r[1])!=null);if(!npRows.length)continue;
      const rev=rows.filter(r=>r.length>=3&&/^(درآمدهایعملیاتی|فروشخالص|درآمدعملیاتی)/.test(ns(r[0]))&&num(r[1])!=null);
      const acc=rows.filter(r=>r.length>=2&&/^سود\(زیان\)انباشته/.test(ns(r[0]))&&num(r[1])!=null);
      const np=npRows[0];const o={np_cur:num(np[1]),np_prev:num(np[2]),codal_pct:np[np.length-1]};o.np_growth=growth(o.np_cur,o.np_prev);
      const pct=num(np[np.length-1]);o.verified=o.np_growth==null||(pct!=null&&Math.abs(o.np_growth-pct)<=Math.max(1,0.01*Math.abs(pct)));
      if(rev.length){o.rev_cur=num(rev[0][1]);o.rev_prev=num(rev[0][2]);o.rev_growth=growth(o.rev_cur,o.rev_prev);}
      if(acc.length)o.accum=num(acc[0][1]);
      return o;}
    return null;
  };
  (async () => {
    let blocked = false;
    for (const raw of syms) {
      if (blocked) break;
      const sym = raw.replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/‌/g,' ').trim();
      let rec = null, err = null;
      try {
        const out = await page.evaluate(async (sym) => {
          const u='https://search.codal.ir/api/search/v2/q?Audited=true&AuditorRef=-1&Category=1&Childs=true&CompanyState=-1&CompanyType=-1&Consolidatable=true&IsNotAudited=false&Length=-1&LetterType=6&Mains=true&NotAudited=true&NotConsolidatable=true&PageNumber=1&Publisher=false&PublisherType=1&Symbol='+encodeURIComponent(sym)+'&TracingNo=-1&search=true';
          const r=await fetch(u); const t=await r.text(); if(r.status!==200) return {status:r.status};
          try { return {status:200, j: JSON.parse(t)}; } catch(e) { return {status:200, nonjson: t.slice(0,150)}; }
        }, sym);
        if (out.status !== 200 || out.nonjson) { blocked = true; err = sym + ':' + (out.status) + (out.nonjson||''); }
        else {
          const letters = (out.j && out.j.Letters) || [];
          const fix = s => (s||'').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[‌\s]/g,'');
          const FAd='۰۱۲۳۴۵۶۷۸۹';
          const liqRe = /درحالانحلال|انحلالی|هیاتتصفیه|درخواستانحلال|تصفیهشرکت|درحالتصفیه|انحلالشرکت/;
          const liqHit = letters.find(l => fix(l.Symbol) === fix(sym) && liqRe.test(fix(l.Title||'')));
          if (liqHit) { rec = {none: 'dissolution', title: liqHit.Title}; }
          const cand = liqHit ? [] : letters.filter(l => fix(l.Symbol) === fix(sym) && l.ExcelUrl && !/\(\s*شرکت[^)]*\)\s*$/.test((l.Title||'').replace(/\s+/g,' ').trim()) && /منتهی به/.test(l.Title));
          const pend = l => { const m=(l.Title.match(/منتهی به\s*([۰-۹0-9]{4}\/[۰-۹0-9]{2}\/[۰-۹0-9]{2})/)||[])[1]||''; return m.replace(/[۰-۹]/g,c=>FAd.indexOf(c)); };
          cand.sort((a,b) => (pend(b).localeCompare(pend(a))) || ((/تلفیقی/.test(b.Title)?1:0)-(/تلفیقی/.test(a.Title)?1:0)) || ((/اصلاحیه/.test(b.Title)?1:0)-(/اصلاحیه/.test(a.Title)?1:0)) || (b.PublishDateTime||'').localeCompare(a.PublishDateTime||''));
          const l = cand[0];
          if (liqHit) { /* rec already set to dissolution above */ }
          else if (!l) rec = {none:'no_statement', n: letters.length};
          else {
            await new Promise(r => setTimeout(r, 8000));
            const r = await page.context().request.get(l.ExcelUrl, {timeout: 90000});
            if (r.status() === 429) { blocked = true; err = sym + ':excel429'; }
            const html = blocked ? '' : await r.text();
            const p = blocked ? null : await page.evaluate(parseFn, html);
            if (!blocked) rec = {title: l.Title.replace(/\s+/g,' '), period: pend(l), consolidated: /تلفیقی/.test(l.Title), audited: !/حسابرسی نشده/.test(l.Title), ...(p||{none:'no_table'})};
          }
        }
      } catch (e) { err = raw + ':' + String(e).slice(0,100); }
      await page.evaluate(([raw, rec, err]) => { const c = window.__cdr; if (rec) c.res[raw] = rec; if (err) c.err.push(err); c.done++; }, [raw, rec, err]);
      await new Promise(r => setTimeout(r, 12000));
    }
    await page.evaluate((b) => { window.__cdr.status = b ? 'blocked' : 'done'; }, blocked);
  })();
  return 'started ' + syms.length;
}