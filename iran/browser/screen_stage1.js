() => {
const IR = window.IR = {status:'init', done:0, total:0, err:[], res:null};
const sma=(a,n,end)=>{let s=0;for(let i=end-n+1;i<=end;i++)s+=a[i];return s/n;};
const std=a=>{const m=a.reduce((x,y)=>x+y,0)/a.length;return Math.sqrt(a.reduce((x,y)=>x+(y-m)**2,0)/a.length);};
const maxOf=(a,i,j)=>{let m=-Infinity;for(let k=i;k<j;k++)if(a[k]>m)m=a[k];return m;};
const minOf=(a,i,j)=>{let m=Infinity;for(let k=i;k<j;k++)if(a[k]<m)m=a[k];return m;};
function peaks(v,prom){const out=[];for(let i=1;i<v.length-1;i++){if(v[i]>v[i-1]&&v[i]>=v[i+1]){let lm=v[i],j=i-1;while(j>=0&&v[j]<=v[i]){lm=Math.min(lm,v[j]);j--;}let rm=v[i];j=i+1;while(j<v.length&&v[j]<=v[i]){rm=Math.min(rm,v[j]);j++;}
 const lb=(i-1>=0)?minOf(v,Math.max(0,(function(){let k=i-1;while(k>=0&&v[k]<=v[i])k--;return k<0?0:k;})()),i):v[i];
 const pr=v[i]-Math.max(lb,(function(){let k=i+1;while(k<v.length&&v[k]<=v[i])k++;return minOf(v,i+1,Math.min(v.length,k+1));})());
 if(pr>=prom)out.push(i);}}return out;}
const near=(a,b,t=0.04)=>Math.abs(a-b)/Math.max(a,b)<=t;
function detectPatterns(close){ // close: oldest->newest daily, adjusted
 const w=[];for(let i=close.length-1;i>=0;i-=5)w.push(close[i]);w.reverse();
 const out={patterns:[],score:0,trend:'unknown'};if(w.length<60)return out;
 const v=w,last=v[v.length-1];const med=[...v].sort((a,b)=>a-b)[Math.floor(v.length/2)];
 const hi=peaks(v,0.06*med),lo=peaks(v.map(x=>-x),0.06*med);let score=0;
 const ma40=sma(v,40,v.length-1),ma40b=sma(v,40,v.length-9);const slope=ma40/ma40b-1;
 if(last>ma40&&slope>0.01){out.trend='up';score+=1}else if(last<ma40&&slope<-0.01){out.trend='down';score-=1}else out.trend='range';
 const add=(n,k,p)=>{out.patterns.push({name:n,kind:k});score+=p;};
 if(lo.length>=2){const a=lo[lo.length-2],b=lo[lo.length-1];const mid=hi.filter(h=>h>a&&h<b);
  if(mid.length&&near(v[a],v[b])&&b-a>=8&&b-a<=80&&last>=Math.min(v[a],v[b])*0.97){const neck=Math.max(...mid.map(h=>v[h]));
   if(neck/Math.max(v[a],v[b])-1>=0.08&&v.length-b<=26){const br=last>neck;add('کف دوقلو'+(br?' (شکست خط گردن)':' (در انتظار شکست)'),'bullish',br?1.5:0.5);}}}
 if(hi.length>=2){const a=hi[hi.length-2],b=hi[hi.length-1];const mid=lo.filter(l=>l>a&&l<b);
  if(mid.length&&near(v[a],v[b])&&b-a>=8&&b-a<=80&&last<=Math.max(v[a],v[b])*1.03){const neck=Math.min(...mid.map(l=>v[l]));
   if(1-neck/Math.min(v[a],v[b])>=0.08&&v.length-b<=26){const br=last<neck;add('سقف دوقلو'+(br?' (شکست حمایت)':' (هشدار)'),'bearish',br?-1.5:-0.5);}}}
 if(hi.length>=3){const [l,h,r]=hi.slice(-3);if(v[h]>v[l]*1.05&&v[h]>v[r]*1.05&&near(v[l],v[r],0.08)&&v.length-r<=26){const tr=lo.filter(x=>x>l&&x<r);
  if(tr.length){const neck=Math.min(...tr.map(x=>v[x]));const br=last<neck;add('سرووشانه'+(br?' (شکست)':''),'bearish',br?-2:-1);}}}
 if(lo.length>=3){const [l,h,r]=lo.slice(-3);if(v[h]<v[l]*0.95&&v[h]<v[r]*0.95&&near(v[l],v[r],0.08)&&v.length-r<=26){const pk=hi.filter(x=>x>l&&x<r);
  if(pk.length){const neck=Math.max(...pk.map(x=>v[x]));const br=last>neck;add('سرووشانه معکوس'+(br?' (شکست)':''),'bullish',br?2:1);}}}
 if(v.length>=60){const lo_i=Math.max(0,v.length-110);let bi=lo_i,bm=-Infinity;for(let k=lo_i;k<v.length-8;k++)if(v[k]>bm){bm=v[k];bi=k;}
  const seg=v.slice(bi);if(seg.length>=26&&seg.length<=110){const mn=Math.min(...seg);const depth=1-mn/v[bi];const bpos=seg.indexOf(mn)/seg.length;const handle=1-last/Math.max(...v.slice(-12));
   if(depth>=0.15&&depth<=0.5&&bpos>=0.25&&bpos<=0.75&&last>=v[bi]*0.92&&handle<=0.15)add('فنجان‌ودسته'+(last>v[bi]?' (شکست سقف)':' (نزدیک سقف)'),'bullish',last>v[bi]?1.5:1);}}
 if(hi.length>=2&&lo.length>=2){const h1=hi[hi.length-2],h2=hi[hi.length-1],l1=lo[lo.length-2],l2=lo[lo.length-1];
  if(near(v[h1],v[h2],0.03)&&v[l2]>v[l1]*1.03&&v.length-Math.max(h2,l2)<=12&&last>=Math.max(v[h1],v[h2])*0.95)add('مثلث صعودی','bullish',1);}
 if(v.length>105&&last>=maxOf(v,v.length-105,v.length-1))add('شکست سقف ۲ ساله','bullish',1);
 else if(v.length>53&&last>=maxOf(v,v.length-53,v.length-1))add('شکست سقف ۵۲ هفته','bullish',0.7);
 if(v.length>53&&last<=minOf(v,v.length-53,v.length)*1.03)add('نزدیک کف ۵۲ هفته','bearish',-1);
 out.score=Math.max(-3,Math.min(3,score));return out;}
function setups(c,vol){ if(c.length<260)return []; const n=c.length-1;const r=[];for(let i=1;i<=n;i++)r.push(c[i]/c[i-1]-1);
 const s50=sma(c,50,n),s150=sma(c,150,n),s200=sma(c,200,n),s200b=sma(c,200,n-21);const hi52=maxOf(c,n-251,n+1),lo52=minOf(c,n-251,n+1),p=c[n];
 const v50=sma(vol,50,n-1);const out=[];
 const trend=p>s50&&s50>s150&&s150>s200&&s200>s200b&&p>=1.3*lo52&&p>=0.75*hi52;
 if(p>maxOf(c,n-50,n)&&v50>0&&vol[n]>=1.5*v50)out.push('breakout');
 if(trend)out.push('trend');
 const sd20=std(r.slice(-20)),sd60=std(r.slice(-60));
 if(sd60>0&&sd20<0.6*sd60&&p>=0.9*hi52&&sma(vol,20,n)<sma(vol,50,n))out.push('vcp');
 if(trend&&Math.abs(p/s50-1)<=0.03&&v50>0&&sma(vol,5,n)<0.8*v50)out.push('pullback');
 return out;}
function adjust(rows){ // rows newest-first -> oldest-first adjusted closes, volumes, values
 const a=rows.filter(x=>x.zTotTran>0||x.pClosing>0).slice().reverse();const c=a.map(x=>x.pClosing);const vol=a.map(x=>x.qTotTran5J);const val=a.map(x=>x.pClosing*x.qTotTran5J);const dates=a.map(x=>x.dEven);
 for(let i=a.length-1;i>=1;i--){const f=a[i].priceYesterday/c[i-1]; /* note: c[i-1] may already be adjusted */ }
 // backward adjustment using raw closes
 const raw=a.map(x=>x.pClosing);const adj=raw.slice();let factor=1;
 for(let i=a.length-1;i>=1;i--){const py=a[i].priceYesterday,pc=raw[i-1];if(pc>0&&py>0&&Math.abs(py/pc-1)>0.005)factor*=py/pc;adj[i-1]=raw[i-1]*factor;}
 return {c:adj,vol,val,dates,raw};}
IR.detect=detectPatterns;IR.setups=setups;IR.adjust=adjust;
IR.run=async()=>{try{IR.status='list';
 const r=await fetch('https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false');
 const mw=(await r.json()).marketwatch;IR.all=mw.length;
 const stocks=mw.filter(x=>/^IRO1/.test(x.insID||'')&&!/ح$/.test(x.lva||'')&&!(x.lvc||'').includes('اختيار'));
 IR.total=stocks.length;IR.status='history';IR.cache={};
 let idx=0;const worker=async()=>{while(idx<stocks.length){const s=stocks[idx++];try{
  const rr=await fetch(`https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/${s.insCode}/520`);const j=await rr.json();const rows=j.closingPriceDaily||[];
  if(rows.length>=260){const A=adjust(rows);IR.cache[s.insCode]={sym:s.lva,name:s.lvc,eps:s.eps,pe:s.pe,A};}
 }catch(e){IR.err.push(s.lva+':'+e);}IR.done++;}};
 await Promise.all(Array.from({length:6},worker));IR.status='analyze';
 const list=[];for(const [code,o] of Object.entries(IR.cache)){const {c,vol,val}=o.A;const n=c.length-1;
  const tv=val.slice(-20).sort((a,b)=>a-b)[10];const traded=o.A.raw.slice(-20).length;if(!(tv>=5e9))continue; // median daily value >= 5 billion rial
  const r6=c[n]/c[n-126]-1;list.push({code,sym:o.sym,name:o.name,pe:o.pe,eps:o.eps,r6,last:o.A.raw[n],tv,date:o.A.dates[n]});}
 const sorted=[...list].sort((a,b)=>a.r6-b.r6);sorted.forEach((x,i)=>x.rank=i/(sorted.length-1));
 const out=[];for(const x of list){const A=IR.cache[x.code].A;const st=setups(A.c,A.vol);const cp=detectPatterns(A.c);if(cp.score<=-1)continue;if(cp.score>=1.5)st.push('longpat');
  if(st.length>=2||(st.length>=1&&x.rank>=0.8))out.push({...x,st,cp:cp.patterns.map(p=>p.name).join('، ')||cp.trend,cps:cp.score});}
 IR.liquid=list.length;IR.tech=out.sort((a,b)=>b.st.length-a.st.length||b.rank-a.rank);IR.status='tech_done';
 }catch(e){IR.status='error:'+e;}};
IR.run();return 'started';}
