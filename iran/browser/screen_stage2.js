async () => {
 const t=IR.tech;let i=0;
 const w=async()=>{while(i<t.length){const x=t[i++];try{const j=await (await fetch(`https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/${x.code}`)).json();const ii=j.instrumentInfo||j;
  const eps=parseFloat(ii.eps&&ii.eps.estimatedEPS);x.feps=isNaN(eps)?null:eps;x.spe=ii.eps&&ii.eps.sectorPE;x.psr=ii.eps&&ii.eps.psr;x.sector=ii.sector&&ii.sector.lSecVal;x.flow=ii.flow;
  x.fpe=(x.feps&&x.feps>0)?x.last/x.feps:null;}catch(e){x.fErr=String(e);}}};
 await Promise.all(Array.from({length:6},w));
 const ok=t.filter(x=>x.fpe!==null&&x.spe&&x.fpe<=x.spe*1.0);
 IR.final=ok;
 return {tech:t.length,withEps:t.filter(x=>x.fpe!==null).length,passed:ok.length,
  top:ok.slice(0,15).map(x=>[x.sym,x.last,x.st.join('+'),Math.round(x.rank*100),+x.fpe.toFixed(1),x.spe,x.cp,x.cps])};
}
