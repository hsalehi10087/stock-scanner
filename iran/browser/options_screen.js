// غربال «موقعیت های آپشن ایران» — روی tsetmc.com با browser_evaluate اجرا شود. خروجی: رشته‌ی JSON فشرده.
// همه‌ی قراردادهای اختیار معامله را می‌خواند، به دارایی پایه وصل می‌کند (با نام، وگرنه با کد ISIN)،
// نرخ بهره‌ی ضمنی را از برابری کال/پوت می‌گیرد و نوسان ضمنی را با نوسان واقعی ۳۰ روزه‌ی پایه مقایسه می‌کند.
async () => {
 const nz=t=>(t||'').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/‌/g,' ').replace(/\s+/g,' ').trim();
 const r0=await fetch('https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false');
 const mw=(await r0.json()).marketwatch;
 const op=mw.filter(x=>(x.lvc||'').includes('اختيار'));
 const byName={},byIsin={};
 for(const x of mw){ if(/اختيار/.test(x.lvc||''))continue; byName[nz(x.lva)]=x; const id=x.insID||'';
  if(/^IR[OT][1-7]/.test(id)&&!/ح$/.test(x.lva||'')){const k=id.slice(4,8); if(!byIsin[k]||/0001$/.test(id)) byIsin[k]=x;} }
 // تبدیل تاریخ شمسی سررسید به میلادی
 const fmt=new Intl.DateTimeFormat('en-u-ca-persian',{year:'numeric',month:'numeric',day:'numeric',timeZone:'UTC'});
 const now=new Date(Date.now()+3.5*3600e3); const today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
 const j2g={};for(let i=-10;i<700;i++){const d=new Date(today+i*864e5);const p=Object.fromEntries(fmt.formatToParts(d).map(q=>[q.type,q.value]));
  j2g[`${p.year}/${String(p.month).padStart(2,'0')}/${String(p.day).padStart(2,'0')}`]=+d;}
 const re=/^اختیار\s*([خف])\s*(.+)-(\d+)-(\d{8}|\d{2,4}\/\d{2}\/\d{2})$/;
 const cov={total:op.length,unparsed:0,noUnd:0,noDate:0,expired:0};const P=[];
 for(const x of op){const m=re.exec(nz(x.lvc)); if(!m){cov.unparsed++;continue;}
  let d=m[4]; if(/^\d{8}$/.test(d)) d=d.slice(0,4)+'/'+d.slice(4,6)+'/'+d.slice(6); else if(d.length===8) d='14'+d;
  const u=byName[m[2].trim()]||byIsin[(x.insID||'').slice(4,8)]; if(!u){cov.noUnd++;continue;}
  const ed=j2g[d]; if(!ed){cov.noDate++;continue;} const dte=Math.round((ed-today)/864e5); if(dte<1){cov.expired++;continue;}
  P.push({sym:nz(x.lva),type:m[1]==='خ'?'call':'put',und:nz(u.lva),K:+m[3],exp:d,dte,S:u.pcl,uCode:u.insCode,prem:x.pcl,ask:x.pmo,bid:x.pmd,trades:x.ztt||0,val:x.qtc||0});}
 cov.usable=P.length; cov.traded=P.filter(p=>p.trades>0).length;
 const ucodes=[...new Set(P.filter(p=>p.trades>0).map(p=>p.uCode))];
 const H={};let i=0,lastDate=0;
 const w=async()=>{while(i<ucodes.length){const c=ucodes[i++];try{
   const j=await (await fetch(`https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/${c}/120`)).json();
   const a=(j.closingPriceDaily||[]).filter(x=>x.pClosing>0&&x.priceYesterday>0).reverse();if(a.length<40)continue;
   const lr=a.map(x=>Math.log(x.pClosing/x.priceYesterday));const s=[];let cur=1;for(const x of a){cur*=x.pClosing/x.priceYesterday;s.push(cur);}
   const n=s.length;const l30=lr.slice(-30);const mm=l30.reduce((p,q)=>p+q,0)/30;
   const hv=Math.sqrt(l30.reduce((p,q)=>p+(q-mm)**2,0)/29)*Math.sqrt(250);
   const k50=Math.min(50,n);const sma50=s.slice(-k50).reduce((p,q)=>p+q,0)/k50;
   H[c]={hv,up:s[n-1]>sma50,ret20:s[n-1]/s[n-21]-1}; if(a[n-1].dEven>lastDate)lastDate=a[n-1].dEven;}catch(e){}}};
 await Promise.all(Array.from({length:6},w));
 function erf(x){const t=1/(1+0.3275911*Math.abs(x));const y=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-x*x);return x>=0?y:-y;}
 const N=x=>0.5*(1+erf(x/Math.SQRT2));
 const d1f=(S,K,T,v,r)=>(Math.log(S/K)+(r+0.5*v*v)*T)/(v*Math.sqrt(T));
 const bs=(S,K,T,v,r,ty)=>{const d1=d1f(S,K,T,v,r),d2=d1-v*Math.sqrt(T),df=Math.exp(-r*T);return ty==='call'?S*N(d1)-K*df*N(d2):K*df*N(-d2)-S*N(-d1);};
 // نرخ بهره‌ی ضمنی: میانه‌ی برابری کال/پوت در جفت‌های پرمعامله
 const mp={};for(const x of P){const k=x.uCode+'|'+x.K+'|'+x.exp;(mp[k]=mp[k]||{})[x.type]=x;}
 const rs=[];for(const k in mp){const c=mp[k].call,p=mp[k].put;if(c&&p&&c.trades>=30&&p.trades>=30&&c.dte>=14&&c.prem>0&&p.prem>0){const pv=c.S-(c.prem-p.prem);if(pv>0&&pv<c.K)rs.push(Math.log(c.K/pv)/(c.dte/365));}}
 rs.sort((a,b)=>a-b);
 if(rs.length<5) return JSON.stringify({error:'rate_pairs_too_few',pairs:rs.length,cov,date:lastDate});
 const r=rs[Math.floor(rs.length/2)];
 const out=[];let unpriced=0;
 for(const p of P){ if(p.trades<1||!(p.prem>0)||!(p.S>0))continue; const h=H[p.uCode]; if(!h)continue;
  const T=p.dte/365;let lo=0.01,hi=6;
  if(bs(p.S,p.K,T,lo,r,p.type)>p.prem||bs(p.S,p.K,T,hi,r,p.type)<p.prem){unpriced++;continue;}
  for(let k=0;k<60;k++){const mid=(lo+hi)/2;if(bs(p.S,p.K,T,mid,r,p.type)<p.prem)lo=mid;else hi=mid;}
  const iv=(lo+hi)/2;const d1=d1f(p.S,p.K,T,iv,r);const dl=p.type==='call'?N(d1):N(d1)-1;
  const be=p.type==='call'?(p.K+p.prem)/p.S-1:1-(p.K-p.prem)/p.S;
  out.push({...p,iv,hv:h.hv,ratio:iv/h.hv,dl,be,up:h.up,ret20:h.ret20,spr:(p.ask>0&&p.bid>0)?p.ask/p.bid-1:null});}
 const liq=out.filter(x=>x.dte>=14&&x.trades>=30&&x.val>=5e9&&x.spr!==null&&x.spr<=0.08);
 const f=x=>({sym:x.sym,und:x.und,K:x.K,exp:x.exp,dte:x.dte,S:x.S,prem:x.prem,trades:x.trades,iv:Math.round(x.iv*100),hv:Math.round(x.hv*100),ratio:+x.ratio.toFixed(2),be:+(x.be*100).toFixed(1),ret20:+(x.ret20*100).toFixed(1)});
 const undSet={};for(const x of out)undSet[x.und]=x.up;
 const res={date:lastDate,cov,unds:Object.keys(undSet).length,undsDown:Object.keys(undSet).filter(k=>!undSet[k]),unpriced,
  rate:Math.round(r*100),ratePairs:rs.length,rateLo:Math.round(rs[Math.floor(rs.length*0.25)]*100),rateHi:Math.round(rs[Math.floor(rs.length*0.75)]*100),
  liq:liq.length,liqCalls:liq.filter(x=>x.type==='call').length,liqPuts:liq.filter(x=>x.type==='put').length,
  calls:liq.filter(x=>x.type==='call'&&x.up&&x.dl>=0.3&&x.dl<=0.8).sort((a,b)=>a.ratio-b.ratio).slice(0,5).map(f),
  puts:liq.filter(x=>x.type==='put'&&!x.up&&x.dl<=-0.2&&x.dl>=-0.8).sort((a,b)=>a.ratio-b.ratio).slice(0,5).map(f)};
 return JSON.stringify(res);
}
