// رژیم امروز هر سهم (صعودی / رنج / نزولی) — روی https://www.tsetmc.com/ با browser_evaluate اجرا شود (حدود ۱ تا ۲ دقیقه).
// روش برنده‌ی بک‌تست (regime_backtest.js + regime_eval2.js): «اجماع K-Means و چینش میانگین‌ها».
//   • چینش میانگین‌ها (B): صعودی = قیمت>SMA50>SMA200 و شیب SMA50 مثبت؛ نزولی = قیمت<SMA50<SMA200 و شیب منفی؛ وگرنه رنج.
//   • K-Means (K): ۵ خوشه روی [بازده ۲۰ روزه، نوسان ۲۰ روزه، ADX، شیب SMA50، فاصله از SMA200، فاصله از SMA50]؛ خوشه با بیشترین بازده=صعودی، کمترین=نزولی.
//   • رژیم نهایی: اگر هر دو یکی بگویند همان؛ وگرنه رنج/مختلط.
// فقط از داده‌ی تا همان روز استفاده می‌شود. خروجی: JSON فشرده {date,n,breadth,up:[نماد],down:[اجماع نزولی],weak:[فقط یکی از دو روش نزولی؛ by=K یا B]}.
async () => {
 const MW='https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false';
 const mw=(await (await fetch(MW)).json()).marketwatch;
 const stocks=mw.filter(x=>/^IRO1/.test(x.insID||'')&&!/ح$/.test(x.lva||'')&&!(x.lvc||'').includes('اختيار'));
 const D=[];let idx=0;
 const worker=async()=>{while(idx<stocks.length){const s=stocks[idx++];try{
  const j=await (await fetch(`https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/${s.insCode}/520`)).json();
  const a=(j.closingPriceDaily||[]).filter(x=>x.zTotTran>0||x.pClosing>0).reverse();if(a.length<400)continue;
  const n=a.length,raw=a.map(x=>x.pClosing),f=new Array(n).fill(1);let fac=1;
  for(let i=n-1;i>=1;i--){const py=a[i].priceYesterday,pc=raw[i-1];if(pc>0&&py>0&&Math.abs(py/pc-1)>0.005)fac*=py/pc;f[i-1]=fac;}
  const c=raw.map((x,i)=>x*f[i]),h=a.map((x,i)=>(x.priceMax>0?x.priceMax:x.pClosing)*f[i]),l=a.map((x,i)=>(x.priceMin>0?x.priceMin:x.pClosing)*f[i]);
  const val=a.map(x=>x.pClosing*x.qTotTran5J);const tv=val.slice(-20).sort((p,q)=>p-q)[10];if(!(tv>=5e9))continue;
  let z=0;for(let k=n-20;k<n;k++)if(c[k]===c[k-1])z++;
  D.push({code:s.insCode,sym:s.lva,c,h,l,dates:a.map(x=>x.dEven),last:raw[n-1],tv,frozen:z>4});
 }catch(e){}}};
 await Promise.all(Array.from({length:6},worker));
 if(D.length<30) return JSON.stringify({error:'few_stocks',n:D.length});
 const nan=NaN;
 function feats(s){const {c,h,l}=s,n=c.length;const ret=new Array(n).fill(nan),pre=[0];
  for(let i=1;i<n;i++)ret[i]=c[i]/c[i-1]-1;
  for(let i=0;i<n;i++)pre.push(pre[i]+c[i]);
  const sma=(i,k)=>i>=k-1?(pre[i+1]-pre[i+1-k])/k:nan;
  const vol=new Array(n).fill(nan);for(let i=21;i<n;i++){let m=0;for(let k=i-19;k<=i;k++)m+=ret[k];m/=20;let v=0;for(let k=i-19;k<=i;k++)v+=(ret[k]-m)**2;vol[i]=Math.sqrt(v/19);}
  const adx=new Array(n).fill(nan);const P=14;let trS=0,pS=0,mS=0,dxA=[],adxPrev=nan;
  for(let i=1;i<n;i++){const up=h[i]-h[i-1],dn=l[i-1]-l[i];const pd=(up>dn&&up>0)?up:0,md=(dn>up&&dn>0)?dn:0;
   const tr=Math.max(h[i]-l[i],Math.abs(h[i]-c[i-1]),Math.abs(l[i]-c[i-1]));
   if(i<=P){trS+=tr;pS+=pd;mS+=md;}else{trS=trS-trS/P+tr;pS=pS-pS/P+pd;mS=mS-mS/P+md;}
   if(i>=P){const pi=100*pS/trS,mi=100*mS/trS;const dx=100*Math.abs(pi-mi)/((pi+mi)||1);
    if(i<2*P){dxA.push(dx);}else if(i===2*P){dxA.push(dx);adxPrev=dxA.reduce((p,q)=>p+q,0)/dxA.length;adx[i]=adxPrev;}else{adxPrev=(adxPrev*(P-1)+dx)/P;adx[i]=adxPrev;}}}
  const o={vol,adx,sma50:new Array(n).fill(nan),sma200:new Array(n).fill(nan),r20:new Array(n).fill(nan),slope:new Array(n).fill(nan),d200:new Array(n).fill(nan),d50:new Array(n).fill(nan)};
  for(let i=0;i<n;i++){o.sma50[i]=sma(i,50);o.sma200[i]=sma(i,200);if(i>=20)o.r20[i]=c[i]/c[i-20]-1;}
  for(let i=0;i<n;i++){if(i>=60)o.slope[i]=o.sma50[i]/o.sma50[i-10]-1;o.d200[i]=c[i]/o.sma200[i]-1;o.d50[i]=c[i]/o.sma50[i]-1;}
  o.start=210;return o;}
 for(const s of D)s.F=feats(s);
 const labB=(F,i)=>{if(!(F.sma200[i]>0)||!(F.slope[i]===F.slope[i]))return null;const c50=F.d50[i]>0;if(c50&&F.sma50[i]>F.sma200[i]&&F.slope[i]>0)return 1;if(!c50&&F.sma50[i]<F.sma200[i]&&F.slope[i]<0)return -1;return 0;};
 // آموزش K-Means: همه‌ی روزها تا ۶۰ روز کاری پیش از آخرین روز (برچسب امروز با داده‌ای که شامل ۲۰ روز آینده‌ی خودش نباشد آموزش دیده)
 const fv=(F,i)=>[F.r20[i],F.vol[i],F.adx[i],F.slope[i],F.d200[i],F.d50[i]];
 const okv=v=>v.every(x=>x===x&&isFinite(x));
 let seed=12345;const rnd=()=>{seed=(seed*1664525+1013904223)%4294967296;return seed/4294967296;};
 const trainX=[];for(const s of D){const F=s.F,n=s.c.length;for(let i=F.start;i<n-60;i+=3){const v=fv(F,i);if(okv(v))trainX.push(v);}}
 const dim=6,mu=new Array(dim).fill(0),sd=new Array(dim).fill(0);
 for(const v of trainX)for(let d=0;d<dim;d++)mu[d]+=v[d]/trainX.length;
 for(const v of trainX)for(let d=0;d<dim;d++)sd[d]+=(v[d]-mu[d])**2/trainX.length;for(let d=0;d<dim;d++)sd[d]=Math.sqrt(sd[d])||1;
 const Z=trainX.map(v=>v.map((x,d)=>(x-mu[d])/sd[d]));
 const K=5;let cent=[Z[Math.floor(rnd()*Z.length)]];
 while(cent.length<K){const dd=Z.map(z=>Math.min(...cent.map(c=>c.reduce((p,q,d)=>p+(q-z[d])**2,0))));const tot=dd.reduce((p,q)=>p+q,0);let r=rnd()*tot,k=0;while(k<dd.length-1&&(r-=dd[k])>0)k++;cent.push(Z[k]);}
 for(let it=0;it<40;it++){const sum=cent.map(()=>new Array(dim).fill(0)),cnt=new Array(K).fill(0);
  for(const z of Z){let b=0,bd=Infinity;for(let k=0;k<K;k++){const dd=cent[k].reduce((p,q,d)=>p+(q-z[d])**2,0);if(dd<bd){bd=dd;b=k;}}cnt[b]++;for(let d=0;d<dim;d++)sum[b][d]+=z[d];}
  cent=cent.map((c,k)=>cnt[k]?sum[k].map(x=>x/cnt[k]):c);}
 const order=[...Array(K).keys()].sort((p,q)=>cent[p][0]-cent[q][0]);const kmap={};kmap[order[0]]=-1;kmap[order[K-1]]=1;for(let k=1;k<K-1;k++)kmap[order[k]]=0;
 const labK=(F,i)=>{const v=fv(F,i);if(!okv(v))return null;const z=v.map((x,d)=>(x-mu[d])/sd[d]);let b=0,bd=Infinity;for(let k=0;k<K;k++){const dd=cent[k].reduce((p,q,d)=>p+(q-z[d])**2,0);if(dd<bd){bd=dd;b=k;}}return kmap[b];};
 const up=[],down=[],weak=[];let nu=0,nd=0,nr=0,date=0;
 for(const s of D){const n=s.c.length,i=n-1,F=s.F;if(s.frozen)continue;const b=labB(F,i),k=labK(F,i);if(b===null||k===null)continue;if(s.dates[i]>date)date=s.dates[i];
  const lab=(b===k)?b:0;const row=()=>({sym:s.sym,code:s.code,last:s.last,r20:+(F.r20[i]*100).toFixed(1),d50:+(F.d50[i]*100).toFixed(1),d200:+(F.d200[i]*100).toFixed(1),adx:Math.round(F.adx[i]),tv:Math.round(s.tv/1e9)});
  if(lab===1){nu++;up.push(s.sym);}else if(lab===-1){nd++;down.push(row());}else{nr++;if(b===-1||k===-1){const r=row();r.by=(b===-1&&k===-1)?'BK':(k===-1?'K':'B');weak.push(r);}}}
 weak.sort((p,q)=>q.tv-p.tv);
 down.sort((p,q)=>q.tv-p.tv);
 return JSON.stringify({date,n:nu+nd+nr,breadth:{up:nu,range:nr,down:nd},up,down:down.slice(0,25),downTotal:nd,weak:weak.slice(0,25),weakTotal:weak.length});
}
