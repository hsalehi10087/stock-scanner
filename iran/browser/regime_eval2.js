// ارزیابی دقیق‌تر رژیم‌ها (بعد از regime_backtest.js روی همان صفحه اجرا شود؛ از window.RG استفاده می‌کند، دادهٔ جدید نمی‌گیرد).
// اصلاحات: ۱) فقط سهمی که ۲۰ روز گذشته «زنده» بوده (حداکثر ۴ روز بدون تغییر قیمت؛ علّی)، ۲) «بازده مازاد» = بازده سهم منهای میانگین همان روز همهٔ سهم‌ها
// (بتا و زمان‌بندی بازار حذف می‌شود)، ۳) برآورد خطا به‌صورت خوشه‌ای روی تاریخ و با اصلاح هم‌پوشانی.
() => {
 const RG=window.RG,D=RG.D,cutoff=RG.cutoff,STEP=5,keys=['A','B','K','H','V'];const out={};
 for(const H of [10,20]){
  const mk={},rows=[];
  for(const s of D){const n=s.c.length;for(let i=s.F.start;i+H<n;i+=STEP){const d=s.dates[i];if(d<cutoff)continue;let z=0;for(let k=i-19;k<=i;k++)if(s.c[k]===s.c[k-1])z++;if(z>4)continue;
   const fr=s.c[i+H]/s.c[i]-1;(mk[d]=mk[d]||[0,0]);mk[d][0]+=fr;mk[d][1]++;rows.push([s,i,d,fr]);}}
  const dates=Object.keys(mk).sort();const mid=dates[Math.floor(dates.length/2)];
  const res={};
  for(const key of keys){const g={};// g[date]={1:[..],-1:[..],0:[..]}
   for(const [s,i,d,fr] of rows){const lb=s.L[key][i];if(lb===null||lb===undefined)continue;const ex=fr-mk[d][0]/mk[d][1];((g[d]=g[d]||{'1':[],'-1':[],'0':[]})[lb]).push(ex);}
   const avg=a=>a.reduce((p,q)=>p+q,0)/a.length;
   const agg=lab=>{let all=[],n=0,pos=0;for(const d in g){const a=g[d][lab];for(const x of a){n++;if(x>0)pos++;}if(a.length)all.push(avg(a));}return {n,exMean:n?+(100*all.reduce((p,q)=>p+q,0)/all.length).toFixed(2):null,hitEx:n?+(100*pos/n).toFixed(1):null};};
   const sp=[],sp1=[],sp2=[];for(const d in g){if(g[d]['1'].length&&g[d]['-1'].length){const v=avg(g[d]['1'])-avg(g[d]['-1']);sp.push(v);(d<mid?sp1:sp2).push(v);}}
   const m=a=>a.length?avg(a):null,sd=a=>{const mm=avg(a);return Math.sqrt(a.reduce((p,q)=>p+(q-mm)**2,0)/Math.max(1,a.length-1));};
   const se=sp.length>2?sd(sp)/Math.sqrt(sp.length)*Math.sqrt(H/STEP):null;
   res[key]={up:agg('1'),down:agg('-1'),range:agg('0'),spreadPct:sp.length?+(100*m(sp)).toFixed(2):null,t:se?+(m(sp)/se).toFixed(2):null,h1:sp1.length?+(100*m(sp1)).toFixed(2):null,h2:sp2.length?+(100*m(sp2)).toFixed(2):null,dates:sp.length};}
  out['H'+H]=res;}
 return JSON.stringify(out);
}
