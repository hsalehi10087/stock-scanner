// بک‌تست تشخیص رژیم بازار (صعودی / نزولی / رنج) روی tsetmc — با browser_evaluate روی https://www.tsetmc.com/ اجرا شود (حدود ۲ تا ۴ دقیقه).
// چهار روش را «خارج از نمونه» (OOS) مقایسه می‌کند: A=ADX+DI، B=چینش میانگین‌ها، K=K-Means (آموزش روی ۶۰٪ اول زمان)، H=مدل مارکوف پنهان (HMM، فیلتر علّی).
// هر روش فقط از داده‌ی تا همان روز استفاده می‌کند (بدون نگاه به آینده). معیار: بازده ۲۰ روز بعدِ هر برچسب.
// خروجی: رشته‌ی JSON (آمار هر روش). وضعیت در window.RG می‌ماند تا regime_today.js از آن استفاده کند.
async () => {
 const H_DAYS=20, STEP=5, MINROWS=400;
 const MW='https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false';
 const RG = window.RG = {status:'load'};
 // ---------- داده ----------
 const mw=(await (await fetch(MW)).json()).marketwatch;
 const stocks=mw.filter(x=>/^IRO1/.test(x.insID||'')&&!/ح$/.test(x.lva||'')&&!(x.lvc||'').includes('اختيار'));
 const D=[];let idx=0;
 const worker=async()=>{while(idx<stocks.length){const s=stocks[idx++];try{
  const j=await (await fetch(`https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/${s.insCode}/520`)).json();
  const a=(j.closingPriceDaily||[]).filter(x=>x.zTotTran>0||x.pClosing>0).reverse();if(a.length<MINROWS)continue;
  const n=a.length,raw=a.map(x=>x.pClosing),f=new Array(n).fill(1);let fac=1;
  for(let i=n-1;i>=1;i--){const py=a[i].priceYesterday,pc=raw[i-1];if(pc>0&&py>0&&Math.abs(py/pc-1)>0.005)fac*=py/pc;f[i-1]=fac;}
  const c=raw.map((x,i)=>x*f[i]),h=a.map((x,i)=>(x.priceMax>0?x.priceMax:x.pClosing)*f[i]),l=a.map((x,i)=>(x.priceMin>0?x.priceMin:x.pClosing)*f[i]);
  const val=a.map(x=>x.pClosing*x.qTotTran5J);const tv=val.slice(-20).sort((p,q)=>p-q)[10];if(!(tv>=5e9))continue;
  D.push({code:s.insCode,sym:s.lva,c,h,l,dates:a.map(x=>x.dEven),last:raw[n-1],tv});
 }catch(e){}}};
 await Promise.all(Array.from({length:6},worker));
 RG.D=D;RG.status='feat';
 if(D.length<30) return JSON.stringify({error:'few_stocks',n:D.length});
 // ---------- ویژگی‌ها (فقط از داده‌ی تا همان روز) ----------
 const nan=NaN;
 function feats(s){const {c,h,l}=s,n=c.length;const ret=new Array(n).fill(nan),pre=[0];
  for(let i=1;i<n;i++)ret[i]=c[i]/c[i-1]-1;
  for(let i=0;i<n;i++)pre.push(pre[i]+c[i]);
  const sma=(i,k)=>i>=k-1?(pre[i+1]-pre[i+1-k])/k:nan;
  const vol=new Array(n).fill(nan);for(let i=21;i<n;i++){let m=0;for(let k=i-19;k<=i;k++)m+=ret[k];m/=20;let v=0;for(let k=i-19;k<=i;k++)v+=(ret[k]-m)**2;vol[i]=Math.sqrt(v/19);}
  // ADX (Wilder 14)
  const adx=new Array(n).fill(nan),pdi=new Array(n).fill(nan),mdi=new Array(n).fill(nan);const P=14;
  let trS=0,pS=0,mS=0,dxA=[],adxPrev=nan;
  for(let i=1;i<n;i++){const up=h[i]-h[i-1],dn=l[i-1]-l[i];const pd=(up>dn&&up>0)?up:0,md=(dn>up&&dn>0)?dn:0;
   const tr=Math.max(h[i]-l[i],Math.abs(h[i]-c[i-1]),Math.abs(l[i]-c[i-1]));
   if(i<=P){trS+=tr;pS+=pd;mS+=md;}else{trS=trS-trS/P+tr;pS=pS-pS/P+pd;mS=mS-mS/P+md;}
   if(i>=P){const pi=100*pS/trS,mi=100*mS/trS;pdi[i]=pi;mdi[i]=mi;const dx=100*Math.abs(pi-mi)/((pi+mi)||1);
    if(i<2*P){dxA.push(dx);}else if(i===2*P){dxA.push(dx);adxPrev=dxA.reduce((p,q)=>p+q,0)/dxA.length;adx[i]=adxPrev;}else{adxPrev=(adxPrev*(P-1)+dx)/P;adx[i]=adxPrev;}}}
  const o={ret,vol,adx,pdi,mdi,sma50:new Array(n).fill(nan),sma200:new Array(n).fill(nan),r20:new Array(n).fill(nan),r5:new Array(n).fill(nan),slope:new Array(n).fill(nan),d200:new Array(n).fill(nan),d50:new Array(n).fill(nan)};
  for(let i=0;i<n;i++){o.sma50[i]=sma(i,50);o.sma200[i]=sma(i,200);if(i>=20)o.r20[i]=c[i]/c[i-20]-1;if(i>=5)o.r5[i]=c[i]/c[i-5]-1;}
  for(let i=0;i<n;i++){if(i>=60)o.slope[i]=o.sma50[i]/o.sma50[i-10]-1;o.d200[i]=c[i]/o.sma200[i]-1;o.d50[i]=c[i]/o.sma50[i]-1;}
  o.start=Math.max(2*P+1,210);return o;}
 for(const s of D)s.F=feats(s);
 // تاریخ جداکننده‌ی آموزش/آزمون: ۶۰٪ زمانیِ بلندترین سری
 const ref=D.reduce((p,q)=>q.dates.length>p.dates.length?q:p);const cutoff=ref.dates[Math.floor(ref.dates.length*0.6)];
 RG.cutoff=cutoff;
 // ---------- روش A و B (قانونی) ----------
 const labA=(F,i)=>{if(!(F.adx[i]>=0))return null;if(F.adx[i]>22&&F.pdi[i]>F.mdi[i]&&F.d50[i]>0)return 1;if(F.adx[i]>22&&F.mdi[i]>F.pdi[i]&&F.d50[i]<0)return -1;return 0;};
 const labB=(F,i)=>{if(!(F.sma200[i]>0)||!(F.slope[i]===F.slope[i]))return null;const c50=F.d50[i]>0;if(c50&&F.sma50[i]>F.sma200[i]&&F.slope[i]>0)return 1;if(!c50&&F.sma50[i]<F.sma200[i]&&F.slope[i]<0)return -1;return 0;};
 // ---------- K-Means ----------
 let seed=12345;const rnd=()=>{seed=(seed*1664525+1013904223)%4294967296;return seed/4294967296;};
 const fv=(F,i)=>[F.r20[i],F.vol[i],F.adx[i],F.slope[i],F.d200[i],F.d50[i]];
 const okv=v=>v.every(x=>x===x&&isFinite(x));
 const trainX=[];for(const s of D){const F=s.F;for(let i=F.start;i<s.c.length;i+=3){if(s.dates[i]>=cutoff)break;const v=fv(F,i);if(okv(v))trainX.push(v);}}
 const dim=6,mu=new Array(dim).fill(0),sd=new Array(dim).fill(0);
 for(const v of trainX)for(let d=0;d<dim;d++)mu[d]+=v[d]/trainX.length;
 for(const v of trainX)for(let d=0;d<dim;d++)sd[d]+=(v[d]-mu[d])**2/trainX.length;for(let d=0;d<dim;d++)sd[d]=Math.sqrt(sd[d])||1;
 const Z=trainX.map(v=>v.map((x,d)=>(x-mu[d])/sd[d]));
 const K=5;let cent=[Z[Math.floor(rnd()*Z.length)]];
 while(cent.length<K){const dd=Z.map(z=>Math.min(...cent.map(c=>c.reduce((p,q,d)=>p+(q-z[d])**2,0))));const tot=dd.reduce((p,q)=>p+q,0);let r=rnd()*tot,k=0;while(k<dd.length-1&&(r-=dd[k])>0)k++;cent.push(Z[k]);}
 for(let it=0;it<40;it++){const sum=cent.map(()=>new Array(dim).fill(0)),cnt=new Array(K).fill(0);
  for(const z of Z){let b=0,bd=Infinity;for(let k=0;k<K;k++){const dd=cent[k].reduce((p,q,d)=>p+(q-z[d])**2,0);if(dd<bd){bd=dd;b=k;}}cnt[b]++;for(let d=0;d<dim;d++)sum[b][d]+=z[d];}
  cent=cent.map((c,k)=>cnt[k]?sum[k].map(x=>x/cnt[k]):c);}
 // برچسب خوشه‌ها فقط از میانگین «بازده ۲۰ روزه‌ی گذشته» (بدون آینده)
 const order=[...Array(K).keys()].sort((p,q)=>cent[p][0]-cent[q][0]);const kmap={};kmap[order[0]]=-1;kmap[order[K-1]]=1;for(let k=1;k<K-1;k++)kmap[order[k]]=0;
 const labK=(F,i)=>{const v=fv(F,i);if(!okv(v))return null;const z=v.map((x,d)=>(x-mu[d])/sd[d]);let b=0,bd=Infinity;for(let k=0;k<K;k++){const dd=cent[k].reduce((p,q,d)=>p+(q-z[d])**2,0);if(dd<bd){bd=dd;b=k;}}return kmap[b];};
 // ---------- HMM گاوسی ۳ حالته (مشاهده: بازده ۵ روزه، لگاریتم نوسان ۲۰ روزه) ----------
 const S=3,OD=2;
 const obsOf=(F,i)=>{const r=F.r5[i],v=F.vol[i];return(r===r&&v>0)?[r*10,Math.log(v)]:null;}; // مقیاس‌دهی ساده
 const seqs=[];let cnt0=0;for(const s of D){if(cnt0++%2)continue;const F=s.F;const q=[];for(let i=F.start;i<s.c.length;i++){if(s.dates[i]>=cutoff)break;const o=obsOf(F,i);if(o)q.push(o);}if(q.length>60)seqs.push(q);}
 const allO=seqs.flat();const om=[0,0],os=[0,0];for(const o of allO)for(let d=0;d<OD;d++)om[d]+=o[d]/allO.length;for(const o of allO)for(let d=0;d<OD;d++)os[d]+=(o[d]-om[d])**2/allO.length;for(let d=0;d<OD;d++)os[d]=Math.sqrt(os[d])||1;
 const nrm=o=>o.map((x,d)=>(x-om[d])/os[d]);
 const sq=seqs.map(q=>q.map(nrm));
 let pi0=[1/3,1/3,1/3],A=[[.9,.05,.05],[.05,.9,.05],[.05,.05,.9]];
 const srt=allO.map(nrm).sort((p,q)=>p[0]-q[0]);let mean=[0,1,2].map(k=>{const sl=srt.slice(Math.floor(srt.length*k/3),Math.floor(srt.length*(k+1)/3));return [0,1].map(d=>sl.reduce((p,q)=>p+q[d],0)/sl.length);});
 let vr=[0,1,2].map(()=>[1,1]);
 const lg=(o,k)=>{let p=1;for(let d=0;d<OD;d++){p*=Math.exp(-0.5*(o[d]-mean[k][d])**2/vr[k][d])/Math.sqrt(2*Math.PI*vr[k][d]);}return Math.max(p,1e-300);};
 for(let it=0;it<15;it++){const nG=[0,0,0],sG=[[0,0],[0,0],[0,0]],sV=[[0,0],[0,0],[0,0]],xi=[[0,0,0],[0,0,0],[0,0,0]],g0=[0,0,0];
  for(const q of sq){const T=q.length;const al=[],sc=[];const B=q.map(o=>[0,1,2].map(k=>lg(o,k)));
   let a=[0,1,2].map(k=>pi0[k]*B[0][k]);let c=a.reduce((p,x)=>p+x,0);a=a.map(x=>x/c);al.push(a);sc.push(c);
   for(let t=1;t<T;t++){a=[0,1,2].map(k=>B[t][k]*[0,1,2].reduce((p,j)=>p+al[t-1][j]*A[j][k],0));c=a.reduce((p,x)=>p+x,0)||1e-300;a=a.map(x=>x/c);al.push(a);sc.push(c);}
   const be=new Array(T);be[T-1]=[1,1,1];for(let t=T-2;t>=0;t--){be[t]=[0,1,2].map(j=>[0,1,2].reduce((p,k)=>p+A[j][k]*B[t+1][k]*be[t+1][k],0)/sc[t+1]);}
   for(let t=0;t<T;t++){const g=[0,1,2].map(k=>al[t][k]*be[t][k]);const gs=g.reduce((p,x)=>p+x,0)||1;for(let k=0;k<3;k++){const gk=g[k]/gs;nG[k]+=gk;for(let d=0;d<OD;d++){sG[k][d]+=gk*q[t][d];sV[k][d]+=gk*q[t][d]**2;}if(t===0)g0[k]+=gk;}
    if(t<T-1)for(let j=0;j<3;j++)for(let k=0;k<3;k++)xi[j][k]+=al[t][j]*A[j][k]*B[t+1][k]*be[t+1][k]/sc[t+1];}}
  mean=[0,1,2].map(k=>[0,1].map(d=>sG[k][d]/(nG[k]||1)));vr=[0,1,2].map(k=>[0,1].map(d=>Math.max(sV[k][d]/(nG[k]||1)-mean[k][d]**2,0.01)));
  A=[0,1,2].map(j=>{const sm=xi[j].reduce((p,x)=>p+x,0)||1;return xi[j].map(x=>x/sm);});const g0s=g0.reduce((p,x)=>p+x,0)||1;pi0=g0.map(x=>x/g0s);}
 const hOrder=[0,1,2].sort((p,q)=>mean[p][0]-mean[q][0]);const hmap={};hmap[hOrder[0]]=-1;hmap[hOrder[1]]=0;hmap[hOrder[2]]=1;
 RG.hmm={mean,vr,A,hmap};
 function hmmFilter(s){const F=s.F,n=s.c.length;const lab=new Array(n).fill(null),prob=new Array(n).fill(null);let a=null;
  for(let i=F.start;i<n;i++){const o0=obsOf(F,i);if(!o0)continue;const o=nrm(o0);const B=[0,1,2].map(k=>lg(o,k));
   a=a?[0,1,2].map(k=>B[k]*[0,1,2].reduce((p,j)=>p+a[j]*A[j][k],0)):[0,1,2].map(k=>pi0[k]*B[k]);const c=a.reduce((p,x)=>p+x,0)||1e-300;a=a.map(x=>x/c);
   let b=0;for(let k=1;k<3;k++)if(a[k]>a[b])b=k;lab[i]=hmap[b];prob[i]=a[b];}return {lab,prob};}
 // ---------- برچسب‌ها ----------
 for(const s of D){const F=s.F,n=s.c.length;const L={A:[],B:[],K:[],H:[],V:[]};const hf=hmmFilter(s);L.H=hf.lab;RG.hprob=RG.hprob||{};
  for(let i=0;i<n;i++){L.A[i]=i>=F.start?labA(F,i):null;L.B[i]=i>=F.start?labB(F,i):null;L.K[i]=i>=F.start?labK(F,i):null;
   const vs=[L.A[i],L.B[i],L.K[i],L.H[i]];L.V[i]=vs.every(x=>x!==null&&x!==undefined)?(vs.reduce((p,q)=>p+q,0)>=3?1:(vs.reduce((p,q)=>p+q,0)<=-3?-1:0)):null;}
  s.L=L;s.hp=hf.prob;}
 // ---------- ارزیابی خارج از نمونه ----------
 const names={A:'ADX+DI',B:'چینش میانگین‌ها',K:'K-Means',H:'HMM',V:'رأی‌گیری ۴ روش (≥۳)'};
 const stat=a=>{if(!a.length)return {n:0};const m=a.reduce((p,q)=>p+q,0)/a.length;const v=a.reduce((p,q)=>p+(q-m)**2,0)/Math.max(1,a.length-1);const so=[...a].sort((p,q)=>p-q);return {n:a.length,mean:+(m*100).toFixed(2),med:+(so[Math.floor(so.length/2)]*100).toFixed(2),hit:+(100*a.filter(x=>x>0).length/a.length).toFixed(1),sd:Math.sqrt(v)};};
 const res={cutoff,stocks:D.length,methods:{}};let uncond=[];
 const mids=[];for(const s of D){for(let i=s.F.start;i+H_DAYS<s.c.length;i+=STEP)if(s.dates[i]>=cutoff)mids.push(s.dates[i]);}mids.sort();const midDate=mids[Math.floor(mids.length/2)];
 for(const key of Object.keys(names)){const by={'1':[],'-1':[],'0':[]},byH1={'1':[],'-1':[]},byH2={'1':[],'-1':[]};let sw=0,days=0;
  for(const s of D){const L=s.L[key],c=s.c;for(let i=s.F.start;i+H_DAYS<c.length;i+=STEP){if(s.dates[i]<cutoff)continue;const lb=L[i];if(lb===null||lb===undefined)continue;const fr=c[i+H_DAYS]/c[i]-1;by[lb].push(fr);if(key==='A')uncond.push(fr);(s.dates[i]<midDate?byH1:byH2)[lb]&&(s.dates[i]<midDate?byH1:byH2)[lb].push(fr);}
   for(let i=s.F.start+1;i<c.length;i++){if(s.dates[i]<cutoff)continue;if(L[i]!==null&&L[i-1]!==null&&L[i]!==undefined&&L[i-1]!==undefined){days++;if(L[i]!==L[i-1])sw++;}}}
  const su=stat(by['1']),sd_=stat(by['-1']),sr=stat(by['0']);
  const spread=(su.n&&sd_.n)?+(su.mean-sd_.mean).toFixed(2):null;
  const se=(su.n&&sd_.n)?Math.sqrt((su.sd*100)**2/su.n+(sd_.sd*100)**2/sd_.n)*2:null; // ×۲ چون پنجره‌ها هم‌پوشانی دارند
  const sp=(a,b)=>{const x=stat(a),y=stat(b);return(x.n&&y.n)?+(x.mean-y.mean).toFixed(2):null;};
  const f=o=>{const {sd,...r}=o;return r;};
  res.methods[key]={name:names[key],up:f(su),down:f(sd_),range:f(sr),spread,t:se?+(spread/se).toFixed(2):null,spreadFirstHalf:sp(byH1['1'],byH1['-1']),spreadSecondHalf:sp(byH2['1'],byH2['-1']),switchesPer100d:days?+(100*sw/days).toFixed(1):null};}
 res.uncond=f_(stat(uncond));function f_(o){const {sd,...r}=o;return r;}
 res.hmm={A:RG.hmm.A.map(r=>r.map(x=>+x.toFixed(3))),stateMeanRet5d_z:RG.hmm.mean.map(m=>+m[0].toFixed(2))};
 RG.status='done';RG.names=names;RG.labelFns={labA,labB};
 return JSON.stringify(res);
}
