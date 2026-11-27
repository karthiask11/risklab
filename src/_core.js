/* ---------- maths ---------- */
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
function cov(a,b){const ma=mean(a),mb=mean(b);let s=0;for(let i=0;i<a.length;i++)s+=(a[i]-ma)*(b[i]-mb);return s/(a.length-1)}
function align(syms,y){
  const ser=syms.map(s=>adjusted(store[s])),maps=ser.map(r=>new Map(r));
  const end=ser.map(r=>r.at(-1)[0]).reduce((a,b)=>a<b?a:b),start=subYears(end,y);
  const dates=ser[0].map(r=>r[0]).filter(d=>d>=start&&d<=end&&maps.every(m=>m.has(d)));
  const px=maps.map(m=>dates.map(d=>m.get(d)));
  return {dates,px,ret:px.map(p=>p.slice(1).map((v,i)=>v/p[i]-1)),start,end,short:dates.length>1&&dates[0]>addDays(start,10)};
}
/* each stock keeps its own history inside the period (a stock listed later is not cut out and does not cut the others) */
function alignEach(syms,y){
  const ser=syms.map(s=>adjusted(store[s]));
  const end=ser.map(r=>r.at(-1)[0]).reduce((a,b)=>a<b?a:b),start=subYears(end,y);
  const pd=[],px=[],ret=[],rd=[];
  ser.forEach(r=>{const z=r.filter(x=>x[0]>=start&&x[0]<=end);pd.push(z.map(x=>x[0]));px.push(z.map(x=>x[1]));
    ret.push(z.slice(1).map((x,i)=>x[1]/z[i][1]-1));rd.push(z.slice(1).map(x=>x[0]))});
  const li=pd.reduce((b,d,i)=>d.length>pd[b].length?i:b,0),dates=pd[li];
  const first=ser.map(r=>r[0][0]).reduce((a,b)=>a<b?a:b),from=first>start?first:start;
  const late=syms.map((s,i)=>pd[i].length&&pd[i][0]>addDays(from,10)?i:-1).filter(i=>i>=0);
  return {syms,dates,pd,px,ret,rd,start,end,late,short:dates.length>1&&dates[0]>addDays(start,10)};
}
/* covariance on the days both series have */
function pairCov(ra,da,rb,db){
  if(da===db||(da.length===db.length&&da[0]===db[0]&&da.at(-1)===db.at(-1)))return {c:cov(ra,rb),va:cov(ra,ra),vb:cov(rb,rb),n:ra.length};
  const mb=new Map(db.map((d,i)=>[d,rb[i]])),a=[],b=[];
  da.forEach((d,i)=>{if(mb.has(d)){a.push(ra[i]);b.push(mb.get(d))}});
  return a.length>2?{c:cov(a,b),va:cov(a,a),vb:cov(b,b),n:a.length}:{c:0,va:1,vb:1,n:a.length};
}
/* symmetric eigen-decomposition (Jacobi), used to keep a pairwise covariance matrix valid */
function eigSym(M){
  const n=M.length,a=M.map(r=>r.slice()),V=M.map((_,i)=>M.map((_,j)=>i===j?1:0));
  for(let sw=0;sw<60;sw++){let off=0;for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)off+=a[i][j]*a[i][j];if(off<1e-30)break;
    for(let p=0;p<n;p++)for(let q=p+1;q<n;q++){if(Math.abs(a[p][q])<1e-300)continue;
      const th=(a[q][q]-a[p][p])/(2*a[p][q]),t=Math.sign(th||1)/(Math.abs(th)+Math.sqrt(th*th+1)),c=1/Math.sqrt(t*t+1),s=t*c;
      for(let k=0;k<n;k++){const x=a[k][p],y=a[k][q];a[k][p]=c*x-s*y;a[k][q]=s*x+c*y}
      for(let k=0;k<n;k++){const x=a[p][k],y=a[q][k];a[p][k]=c*x-s*y;a[q][k]=s*x+c*y}
      for(let k=0;k<n;k++){const x=V[k][p],y=V[k][q];V[k][p]=c*x-s*y;V[k][q]=s*x+c*y}}}
  return {val:a.map((r,i)=>r[i]),V};
}
function fixCorr(R){
  const n=R.length,{val,V}=eigSym(R);if(Math.min(...val)>1e-8)return R;
  const L=val.map(x=>Math.max(x,1e-6)),B=R.map((_,i)=>R.map((_,j)=>{let s=0;for(let k=0;k<n;k++)s+=V[i][k]*L[k]*V[j][k];return s}));
  return B.map((r,i)=>r.map((x,j)=>x/Math.sqrt(B[i][i]*B[j][j])));
}
function stats(p,r,dates){
  const m=mean(r),v=cov(r,r),sd=Math.sqrt(v),days=(Date.parse(dates.at(-1))-Date.parse(dates[0]))/864e5;
  let peak=p[0],mdd=0;for(const x of p){if(x>peak)peak=x;mdd=Math.min(mdd,x/peak-1)}
  let best=-1,worst=1,bi=0,wi=0;r.forEach((x,i)=>{if(x>best){best=x;bi=i}if(x<worst){worst=x;wi=i}});
  return {first:p[0],last:p.at(-1),pr:p.at(-1)/p[0]-1,cagr:Math.pow(p.at(-1)/p[0],365.25/days)-1,m,v,sd,ar:m*TD,ak:sd*Math.sqrt(TD),best,worst,bd:dates[bi+1],wd:dates[wi+1],up:r.filter(x=>x>0).length,down:r.filter(x=>x<0).length,n:r.length,mdd,years:days/365.25};
}
function portfolio(A,w){
  const k=w.length,pd=A.pd||A.px.map(()=>A.dates),rd=A.rd||A.px.map(()=>A.dates.slice(1));
  const S=A.ret.map((r,i)=>stats(A.px[i],r,pd[i]));
  const O=A.ret.map((a,i)=>A.ret.map((b,j)=>i===j?{n:a.length}:pairCov(a,rd[i],b,rd[j])));
  let R=A.ret.map((_,i)=>A.ret.map((_,j)=>i===j?1:(O[i][j].n>=20&&O[i][j].va>0&&O[i][j].vb>0?O[i][j].c/Math.sqrt(O[i][j].va*O[i][j].vb):0)));
  const mixed=A.pd&&A.late&&A.late.length>0;if(mixed&&k>2)R=fixCorr(R);
  const sc=A.scale||R.map(()=>1);  /* scale > 1 or < 1: a short-history stock's risk blended with its sector's */
  const C=R.map((r,i)=>r.map((x,j)=>x*Math.sqrt(S[i].v*S[j].v)*sc[i]*sc[j]));
  let v=0,diag=0;const mc=w.map((_,i)=>w.reduce((s,wj,j)=>s+wj*C[i][j],0));
  for(let i=0;i<k;i++){v+=w[i]*mc[i];diag+=w[i]*w[i]*C[i][i]}
  const ret=w.reduce((s,x,i)=>s+x*S[i].ar,0),risk=Math.sqrt(v*TD),wavg=w.reduce((s,x,i)=>s+x*S[i].ak*sc[i],0);
  return {S,C,corr:R,over:O,ret,risk,v:v*TD,diag:diag*TD,covp:(v-diag)*TD,wavg,contrib:w.map((x,i)=>x*mc[i]/v)};
}

/* ---------- charts ---------- */
function axes(W,H,m,x0,x1,y0,y1,fx,fy){
  const X=v=>m.l+(v-x0)/(x1-x0)*(W-m.l-m.r),Y=v=>H-m.b-(v-y0)/(y1-y0)*(H-m.t-m.b);
  const ticks=(a,b,n)=>{const st=Math.pow(10,Math.floor(Math.log10((b-a)/n)));const s=[1,2,2.5,5,10].map(z=>z*st).find(z=>(b-a)/z<=n);const out=[];for(let v=Math.ceil(a/s)*s;v<=b+1e-12;v+=s)out.push(v);return out};
  const nt=W<520?3:6;let g="";
  for(const t of ticks(y0,y1,5))g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--rule)"/><text x="${m.l-8}" y="${Y(t)+4}" text-anchor="end">${fy(t)}</text>`;
  for(const t of ticks(x0,x1,nt))g+=`<text x="${X(t)}" y="${H-m.b+18}" text-anchor="middle">${fx(t)}</text>`;
  return {X,Y,g};
}
const pad=(a,b,f=.12)=>{const d=(b-a)||Math.abs(a)||.01;return [a-d*f,b+d*f]};
function draw(el,fn){const s=el.querySelector("svg");const go=()=>{if(s.clientWidth)s.innerHTML=fn(s.clientWidth,s.clientHeight)};go();const ro=new ResizeObserver(go);ro.observe(s)}
function scatter(W,H,pts,curve,line){
  const m={l:56,r:24,t:18,b:42},all=[...pts,...(curve||[])];
  let [x0,x1]=pad(Math.min(...all.map(p=>p.x)),Math.max(...all.map(p=>p.x)));x0=Math.max(0,x0);
  let [y0,y1]=pad(Math.min(0,...all.map(p=>p.y)),Math.max(0,...all.map(p=>p.y)));
  const a=axes(W,H,m,x0,x1,y0,y1,t=>pct(t,0),t=>pct(t,0));let g=a.g;
  g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${a.Y(0)}" y2="${a.Y(0)}" stroke="var(--mute)"/>`;
  g+=`<text x="${W-m.r}" y="${H-6}" text-anchor="end">Risk (annual SD) →</text><text x="${m.l}" y="12">↑ Annual return</text>`;
  if(line)g+=`<line x1="${a.X(Math.max(x0,line[0].x))}" y1="${a.Y(line[0].y+(line[1].y-line[0].y)*(Math.max(x0,line[0].x)-line[0].x)/(line[1].x-line[0].x))}" x2="${a.X(Math.min(x1,line[1].x))}" y2="${a.Y(line[0].y+(line[1].y-line[0].y)*(Math.min(x1,line[1].x)-line[0].x)/(line[1].x-line[0].x))}" stroke="var(--ink)" stroke-dasharray="5 5" stroke-opacity=".6"/>`;
  if(curve)g+=`<polyline fill="none" stroke="var(--teal)" stroke-width="2.5" stroke-opacity=".45" points="${curve.map(p=>a.X(p.x)+","+a.Y(p.y)).join(" ")}"/>`;
  const placed=[],free=(x0b,y0b,wb)=>!placed.some(b=>x0b<b[0]+b[2]&&b[0]<x0b+wb&&Math.abs(y0b-b[1])<15);
  const order=pts.map((p,i)=>i).sort((i,j)=>(pts[j].main?2:pts[j].label?1:0)-(pts[i].main?2:pts[i].label?1:0));
  const lab={};
  for(const i of order){const p=pts[i];if(!p.label)continue;const X=a.X(p.x),Y=a.Y(p.y),left=X>W*.7,wb=p.label.length*7.6+4;
    for(const dy of [0,16,-16,30,-30]){const lx=left?X-14-wb:X+14;if(free(lx,Y+dy,wb)){placed.push([lx,Y+dy,wb]);lab[i]=[left?X-14:X+14,Y+dy+4,left];break}}}
  pts.forEach((p,i)=>{const X=a.X(p.x),Y=a.Y(p.y);
    g+=p.main?`<circle class="ring" cx="${X}" cy="${Y}" r="11" fill="var(--teal)" fill-opacity=".18" stroke="var(--teal)" stroke-width="3"/>`
      :`<circle cx="${X}" cy="${Y}" r="${p.small?4:6}" fill="${p.min?"var(--bg)":"var(--ink)"}" stroke="var(--ink)" stroke-width="${p.min?2:0}"/>`;
    if(lab[i])g+=`<text class="lbl" x="${lab[i][0]}" y="${lab[i][1]}" text-anchor="${lab[i][2]?"end":"start"}">${esc(p.label)}</text>`});
  return g;
}
function lineChart(W,H,dates,p){
  const m={l:62,r:18,t:16,b:34},[y0,y1]=pad(Math.min(...p),Math.max(...p),.06),n=p.length-1;
  const X=i=>m.l+i/n*(W-m.l-m.r),Y=v=>H-m.b-(v-y0)/(y1-y0)*(H-m.t-m.b);
  let g="";const st=(y1-y0)/4;for(let k=0;k<=4;k++){const v=y0+st*k;g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--rule)"/><text x="${m.l-8}" y="${Y(v)+4}" text-anchor="end">${num(v,0)}</text>`}
  const nt=W<520?3:5;for(let k=0;k<nt;k++){const i=Math.round(k/(nt-1)*n);g+=`<text x="${X(i)}" y="${H-10}" text-anchor="${k===0?"start":k===nt-1?"end":"middle"}">${fmtD(dates[i]).slice(3)}</text>`}
  const pts=p.map((v,i)=>X(i)+","+Y(v)).join(" ");
  g+=`<polygon points="${m.l},${H-m.b} ${pts} ${X(n)},${H-m.b}" fill="var(--tealbg)"/><polyline points="${pts}" fill="none" stroke="var(--teal)" stroke-width="2"/>`;
  g+=`<circle cx="${X(n)}" cy="${Y(p[n])}" r="5" fill="var(--teal)"/><text class="lbl" x="${X(n)-8}" y="${Y(p[n])-10}" text-anchor="end">₹${num(p[n])}</text>`;
  return g;
}

