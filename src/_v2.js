/* ================= v2: deeper analysis (from NISM XXI-B, CFA, Palomar, Farrell, J.P. Morgan tools) =================
   Each block can be switched off by the admin (site/config.v2.<key> = false). */
const V2ON=k=>!(SITE.v2&&SITE.v2[k]===false);
const V2COL=["var(--teal)","var(--ink)","#c0841a","#7a5cc7","#2f7fd1","#c2410c","#4d7c0f","#be185d"];
function solveLin(M,b){ // Gaussian elimination with pivoting
  const n=b.length,a=M.map((r,i)=>[...r,b[i]]);
  for(let c=0;c<n;c++){let p=c;for(let r=c+1;r<n;r++)if(Math.abs(a[r][c])>Math.abs(a[p][c]))p=r;[a[c],a[p]]=[a[p],a[c]];
    const d=a[c][c]||1e-12;for(let r=0;r<n;r++)if(r!==c){const f=a[r][c]/d;for(let k=c;k<=n;k++)a[r][k]-=f*a[c][k]}}
  return a.map((r,i)=>r[n]/(r[i]||1e-12));
}
const sdOf=a=>a.length>1?Math.sqrt(cov(a,a)):NaN;
function ddOf(v){let pk=v[0],m=0;for(const x of v){if(x>pk)pk=x;m=Math.min(m,x/pk-1)}return m}
function summ(v,dates,rf){ // value path -> CAGR, vol, Sharpe, max drawdown
  const r=v.slice(1).map((x,i)=>x/v[i]-1),yrs=(Date.parse(dates.at(-1))-Date.parse(dates[0]))/864e5/365.25;
  const cagr=Math.pow(v.at(-1)/v[0],1/Math.max(yrs,1e-9))-1,vol=sdOf(r)*Math.sqrt(TD);
  return {cagr,vol,sharpe:(cagr-rf)/vol,mdd:ddOf(v),yrs,end:v.at(-1)/v[0]};
}
function multiLine(W,H,dates,series){
  const m={l:56,r:18,t:16,b:34},all=series.flatMap(s=>s.v).filter(Number.isFinite),[y0,y1]=pad(Math.min(...all),Math.max(...all),.06),n=dates.length-1;
  const X=i=>m.l+i/Math.max(1,n)*(W-m.l-m.r),Y=v=>H-m.b-(v-y0)/(y1-y0)*(H-m.t-m.b);let g="";
  const st=(y1-y0)/4;for(let k=0;k<=4;k++){const v=y0+st*k;g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--rule)"/><text x="${m.l-8}" y="${Y(v)+4}" text-anchor="end">${num(v,0)}</text>`}
  const nt=W<520?3:5;for(let k=0;k<nt;k++){const i=Math.round(k/(nt-1)*n);g+=`<text x="${X(i)}" y="${H-10}" text-anchor="${k===0?"start":k===nt-1?"end":"middle"}">${fmtD(dates[i]).slice(3)}</text>`}
  series.forEach((s,k)=>{const step=Math.max(1,Math.floor(s.v.length/600));g+=`<polyline fill="none" stroke="${V2COL[k%V2COL.length]}" stroke-width="${k===0?2.4:1.6}" points="${s.v.map((v,i)=>i%step&&i!==s.v.length-1?"":X(i)+","+Y(v)).filter(Boolean).join(" ")}"/>`});
  return g;
}
const legend=names=>`<div class="lgd">${names.map((n,k)=>`<span><i style="background:${V2COL[k%V2COL.length]}"></i>${esc(n)}</span>`).join("")}</div>`;
const v2apply=(use,w,msg)=>{state.mode="wt";use.forEach((h,i)=>{h.wt=Math.round(w[i]*1000)/10});save();document.getElementsByName("mode").forEach(r=>r.checked=r.value==="wt");renderPortfolio();toast(msg||"Weights applied")};

/* ---------- A1. against the benchmark: tracking error, information ratio, M², capture, Treynor, Jensen ---------- */
function relStats(A,w,mret,mrd,P,rf,pb){
  const ps=portSeries(A,w),mb=new Map(mrd.map((d,i)=>[d,mret[i]])),rp=[],rb=[];
  for(const [d,r] of ps)if(mb.has(d)){rp.push(r);rb.push(mb.get(d))}
  if(rp.length<60)return null;
  const act=rp.map((x,i)=>x-rb[i]),te=sdOf(act)*Math.sqrt(TD),ar=mean(act)*TD,sdb=sdOf(rb)*Math.sqrt(TD),sdp=sdOf(rp)*Math.sqrt(TD),mp=mean(rp)*TD,mbA=mean(rb)*TD;
  const ix=f=>rb.map((x,i)=>f(x)?i:-1).filter(i=>i>=0),cap=I=>I.length?mean(I.map(i=>rp[i]))/mean(I.map(i=>rb[i])):NaN;
  const shp=(mp-rf)/sdp;
  return {n:rp.length,te,ar,ir:ar/te,m2:rf+shp*sdb,mb:mbA,mp,sdb,sdp,upc:cap(ix(x=>x>0)),dnc:cap(ix(x=>x<0)),treynor:Number.isFinite(pb)?(mp-rf)/pb:NaN,jensen:Number.isFinite(pb)?mp-(rf+pb*(mbA-rf)):NaN,dr:P.wavg/P.risk,hit:act.filter(x=>x>0).length/act.length};
}
function relHTML(A,w,mret,mrd,P,rf,pb){
  if(!V2ON("rel")||!mret)return "";
  const s=relStats(A,w,mret,mrd,P,rf,pb);if(!s)return "";
  const row=(l,v,n)=>`<tr><td>${l}</td><td class="n"><b>${v}</b></td><td class="note">${n}</td></tr>`;
  return `<section style="margin-top:28px"><h2>Compared with ${BN()} ${tip("te")}</h2><div class="scroll"><table class="steps"><thead><tr><th>Measure</th><th class="n">Value</th><th>What it means</th></tr></thead><tbody>
    ${row("Active return a year",`<span class="${cls(s.ar)}">${pct(s.ar,1)}</span>`,`Your average yearly return minus ${BN()}'s (${pct(s.mp,1)} − ${pct(s.mb,1)})`)}
    ${row("Tracking error",pct(s.te,1),"How far your daily returns wander from the benchmark, per year. Index funds: under 1%; active funds: 4–8%")}
    ${row("Information ratio",fx(s.ir),"Active return ÷ tracking error. Above 0.5 is good, above 1 is rare")}
    ${row("M² (Modigliani)",`<span class="${cls(s.m2-s.mb)}">${pct(s.m2,1)}</span>`,`Your return if your portfolio had ${BN()}'s risk (${pct(s.sdb,1)}). Compare with ${pct(s.mb,1)}`)}
    ${row("Up-market capture",Number.isFinite(s.upc)?pct(s.upc,0):"–","On days the benchmark rose, you gained this much of its rise. Above 100% is good")}
    ${row("Down-market capture",Number.isFinite(s.dnc)?pct(s.dnc,0):"–","On days it fell, you lost this much of its fall. Below 100% is good")}
    ${row("Treynor ratio",Number.isFinite(s.treynor)?pct(s.treynor,1):"–","(Return − risk-free) ÷ beta: reward per unit of market risk")}
    ${row("Jensen's alpha",Number.isFinite(s.jensen)?`<span class="${cls(s.jensen)}">${pct(s.jensen,1)}</span>`:"–","Return above what CAPM expects for your beta")}
    ${row("Diversification ratio",fx(s.dr),"Weighted average stock risk ÷ portfolio risk. 1 = no benefit; higher = more risk cancelled by mixing")}
    ${row("Days you beat it",pct(s.hit,0),`Out of ${s.n} trading days`)}
  </tbody></table></div><p class="note">All from daily returns on days both you and ${BN()} traded. Formulas: TE = SD(Rp − Rb) × √252; IR = (R̄p − R̄b) ÷ TE; M² = Rf + Sharpe × σb.</p></section>`;
}

/* ---------- A2. stress tests: real Indian market falls + simple "what if the market falls" ---------- */
const SCEN=[["2018 mid & small-cap fall","2018-01-12","2018-03-23"],["IL&FS / NBFC crisis","2018-08-28","2018-10-26"],["2019 slowdown fall","2019-06-03","2019-08-22"],["COVID crash","2020-02-19","2020-03-23"],["2022 rate-hike fall","2022-01-17","2022-06-17"],["2024–25 correction","2024-09-26","2025-03-03"]];
function periodRet(sym,a,b){
  const e=store[sym];if(!e)return NaN;const s=e.tr||e;let p0=null,p1=null;
  for(const x of s){if(x[0]<=a)p0=x;if(x[0]<=b)p1=x;else break}
  return p0&&p1&&p0[0]>=addDays(a,-10)&&p1[0]>=addDays(b,-10)&&p1[0]>p0[0]?p1[1]/p0[1]-1:NaN;
}
function stressHTML(use,w,beta,val){
  if(!V2ON("stress"))return "";
  const rows=SCEN.map(([l,a,b])=>{const bn=periodRet(IDX,a,b);let s=0,est=[];
    use.forEach((h,i)=>{const r=periodRet(h.sym,a,b);if(Number.isFinite(r))s+=w[i]*r;else if(Number.isFinite(beta[i])&&Number.isFinite(bn)){s+=w[i]*beta[i]*bn;est.push(h.sym)}else s=NaN});
    return {l,a,b,p:s,bn,est}});
  const pb=w.reduce((s,x,i)=>s+x*beta[i],0),rup=x=>val>0&&Number.isFinite(x)?` <span class="note">(${rs(x*val)})</span>`:"";
  return `<section style="margin-top:28px"><h2>Stress tests ${tip("stress")}</h2><div class="scroll"><table><thead><tr><th>Scenario</th><th>Dates</th><th class="n">Your mix</th><th class="n">${BN()}</th></tr></thead><tbody>
    ${rows.map(r=>`<tr><td><b>${r.l}</b>${r.est.length?`<br><span class="note">estimated from beta: ${esc(r.est.join(", "))}</span>`:""}</td><td class="note">${fmtD(r.a)} – ${fmtD(r.b)}</td><td class="n ${cls(r.p)}"><b>${Number.isFinite(r.p)?pct(r.p,1):"–"}</b>${rup(r.p)}</td><td class="n ${cls(r.bn)}">${Number.isFinite(r.bn)?pct(r.bn,1):"–"}</td></tr>`).join("")}
    ${Number.isFinite(pb)?[-.1,-.2,-.3].map(f=>`<tr><td><b>Market falls ${pct(-f,0)}</b><br><span class="note">your beta ${pb.toFixed(2)} × fall</span></td><td class="note">what-if</td><td class="n neg"><b>${pct(pb*f,1)}</b>${rup(pb*f)}</td><td class="n neg">${pct(f,0)}</td></tr>`).join(""):""}
  </tbody></table></div><p class="note">Real scenarios apply today's weights to each stock's actual total return in those dates. A stock not listed then is estimated as beta × the benchmark's fall. The what-if rows use beta only, so they miss stock-specific shocks.</p></section>`;
}

/* ---------- B. portfolio strategies (Palomar ch. 7–16, Black-Litterman), walk-forward backtest ---------- */
function wInvVol(S){const iv=S.map((r,i)=>1/Math.sqrt(r[i])),s=iv.reduce((a,b)=>a+b,0);return iv.map(x=>x/s)}
function wRiskParity(S){
  const n=S.length;let w=wInvVol(S);
  for(let it=0;it<300;it++){const m=S.map(r=>dot(r,w)),v=dot(w,m),rc=w.map((x,i)=>Math.max(1e-12,x*m[i]/v));
    if(Math.max(...rc.map(r=>Math.abs(r-1/n)))<1e-7)break;w=w.map((x,i)=>x*Math.sqrt((1/n)/rc[i]));const s=w.reduce((a,b)=>a+b,0);w=w.map(x=>x/s)}
  return w;
}
function hrp(S){
  const n=S.length,sd=S.map((r,i)=>Math.sqrt(r[i])),D=S.map((r,i)=>r.map((c,j)=>Math.sqrt(Math.max(0,(1-c/(sd[i]*sd[j]))/2))));
  let cl=[...Array(n).keys()].map(i=>({items:[i],h:0}));
  const dist=(a,b)=>{let m=1e9;for(const i of a.items)for(const j of b.items)m=Math.min(m,D[i][j]);return m};
  while(cl.length>1){let bi=0,bj=1,bd=1e9;for(let i=0;i<cl.length;i++)for(let j=i+1;j<cl.length;j++){const d=dist(cl[i],cl[j]);if(d<bd){bd=d;bi=i;bj=j}}
    const m={items:[...cl[bi].items,...cl[bj].items],l:cl[bi],r:cl[bj],h:bd};cl=cl.filter((_,k)=>k!==bi&&k!==bj);cl.push(m)}
  const root=cl[0],w=Array(n).fill(1);
  const cv=ix=>{const iv=ix.map(i=>1/S[i][i]),s=iv.reduce((a,b)=>a+b,0),u=iv.map(x=>x/s);let v=0;ix.forEach((i,a)=>ix.forEach((j,b)=>v+=u[a]*u[b]*S[i][j]));return v};
  const bis=ix=>{if(ix.length<2)return;const h=Math.floor(ix.length/2),L=ix.slice(0,h),R=ix.slice(h),vl=cv(L),vr=cv(R),a=1-vl/(vl+vr);L.forEach(i=>w[i]*=a);R.forEach(i=>w[i]*=1-a);bis(L);bis(R)};
  bis(root.items);return {w,root};
}
function shrinkCov(S,d=.5){const n=S.length,sd=S.map((r,i)=>Math.sqrt(r[i]));let rb=0,c=0;for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){rb+=S[i][j]/(sd[i]*sd[j]);c++}rb=c?rb/c:0;
  return S.map((r,i)=>r.map((x,j)=>i===j?x:(1-d)*x+d*rb*sd[i]*sd[j]))}
function maxSharpe(mu,S,cap,rf){const F=frontier(mu,S,cap);return F.reduce((a,p)=>(p.r-rf)/p.k>(a.r-rf)/a.k?p:a,F[0]).w}
function blackLitterman(S,wm,views,conf,rf,erm,tau=.05){
  const vm=quad(wm,S),delta=Math.max(.5,(erm-rf)/vm),pi=S.map(r=>delta*dot(r,wm));
  const idx=views.map((v,i)=>Number.isFinite(v)?i:-1).filter(i=>i>=0);
  if(!idx.length)return {pi,mu:pi.map(x=>x+rf),delta};
  const om=conf==="high"?.25:conf==="low"?4:1;
  const M=idx.map(a=>idx.map(b=>tau*S[a][b]+(a===b?om*tau*S[a][a]:0))),q=idx.map(i=>views[i]-rf-pi[i]),x=solveLin(M,q);
  return {pi,mu:S.map((r,i)=>pi[i]+tau*idx.reduce((s,a,t)=>s+r[a]*x[t],0)+rf),delta};
}
function mcapW(use){const m=use.map(h=>{const f=fund(h.sym);return f&&f[4]>0?f[4]:NaN}),ok=m.every(Number.isFinite),s=ok?m.reduce((a,b)=>a+b,0):use.length;return {w:ok?m.map(x=>x/s):use.map(()=>1/use.length),ok}}
function stratDefs(n,cap,rf,wYou){
  return [["Your mix",()=>wYou.slice()],["Equal weight (1/N)",()=>Array(n).fill(1/n)],["Inverse volatility",C=>wInvVol(C)],["Minimum variance",(C,mu)=>mvOpt(mu,C,0,cap)],
    ["Risk parity",C=>wRiskParity(C)],["HRP (clusters)",C=>hrp(C).w],["Max Sharpe (shrunk)",(C,mu)=>maxSharpe(mu,shrinkCov(C),cap,rf)]];
}
function stratHTML(A,P,use,w,beta,rf){
  if(!V2ON("strat")||use.length<2)return "";
  const n=use.length,cap=Math.max(state.cap||1,1/n),S=P.C.map(r=>r.map(c=>c*TD)),mu=P.S.map(s=>s.ar),erm=state.erm??ermDefault();
  const MW=mcapW(use),V=(state.blv||{}),views=use.map(h=>{const v=parseFloat(V[h.sym]);return Number.isFinite(v)?v/100:NaN}),conf=state.blc||"mid";
  const BL=blackLitterman(S,MW.w,views,conf,rf,erm),wBL=maxSharpe(BL.mu,S,cap,rf);
  const defs=stratDefs(n,cap,rf,w),W=defs.map(([l,f])=>[l,f(S,mu)]);W.push(["Black-Litterman",wBL]);
  const H=hrp(S),ord=H.root.items.map(i=>use[i].sym);
  const stat=x=>{const k=Math.sqrt(quad(x,S)),r=dot(x,mu);return {k,r,sh:(r-rf)/k,b:dot(x,beta)}};
  const tree=(nd,d=0)=>nd.items.length===1?`<li><b>${esc(use[nd.items[0]].sym)}</b></li>`:`<li><span class="note">group (distance ${nd.h.toFixed(2)})</span><ul>${tree(nd.l,d+1)}${tree(nd.r,d+1)}</ul></li>`;
  return `<section style="margin-top:28px" id="stratSec"><h2>Strategy comparison ${tip("strat")}</h2>
  <p class="note">Seven ways to split the same money across your stocks. In-sample numbers use this period's data, so the optimised mixes always look best here. The backtest below is the honest test.</p>
  <div class="scroll"><table><thead><tr><th>Stock</th>${W.map(x=>`<th class="n">${esc(x[0])}</th>`).join("")}</tr></thead><tbody>
    ${use.map((h,i)=>`<tr><td><b>${esc(h.sym)}</b></td>${W.map(x=>`<td class="n">${pct(x[1][i],1)}</td>`).join("")}</tr>`).join("")}
    ${[["Risk a year","k",v=>pct(v,1)],["Return a year (past)","r",v=>pct(v,1)],["Sharpe","sh",fx],["Beta","b",v=>Number.isFinite(v)?v.toFixed(2):"–"]].map(([l,k,f])=>`<tr><td>${l}</td>${W.map(x=>`<td class="n"><b>${f(stat(x[1])[k])}</b></td>`).join("")}</tr>`).join("")}
    <tr><td></td>${W.map((x,k)=>k?`<td class="n"><button class="add" data-sw="${k}" type="button">Use</button></td>`:"<td></td>").join("")}</tr>
  </tbody></table></div>
  <details style="margin-top:12px"><summary>Black-Litterman: add your own views</summary>
    <p class="note">Starts from market-cap weights${MW.ok?"":" (market caps missing for some stocks, so equal weights)"} and the returns the market implies (π = δΣw, δ = ${BL.delta.toFixed(2)}). Type the yearly return you expect for any stock; leave blank for no view. Confidence decides how far the mix moves toward your views.</p>
    <div class="scroll"><table style="width:auto"><thead><tr><th>Stock</th><th class="n">Market weight</th><th class="n">Implied return π</th><th>Your view % a year</th><th class="n">Blended return</th></tr></thead><tbody>
    ${use.map((h,i)=>`<tr><td><b>${esc(h.sym)}</b></td><td class="n">${pct(MW.w[i],1)}</td><td class="n">${pct(BL.pi[i]+rf,1)}</td><td><input class="blv" data-s="${esc(h.sym)}" inputmode="decimal" style="width:6em" value="${Number.isFinite(views[i])?(views[i]*100).toFixed(1):""}"></td><td class="n"><b>${pct(BL.mu[i],1)}</b></td></tr>`).join("")}
    </tbody></table></div>
    <label style="font-size:14px">Confidence in my views <select id="blc"><option value="low" ${conf==="low"?"selected":""}>Low</option><option value="mid" ${conf==="mid"?"selected":""}>Medium</option><option value="high" ${conf==="high"?"selected":""}>High</option></select></label>
  </details>
  <details style="margin-top:8px"><summary>How HRP grouped your stocks (cluster tree)</summary><ul class="tree">${tree(H.root)}</ul><p class="note">Stocks that move together sit in the same group. HRP shares risk between groups first, then inside each group, so one crowded sector cannot take over. Order: ${esc(ord.join(" → "))}.</p></details>
  <h3 style="margin-top:18px">Walk-forward backtest</h3>
  <p class="note">Every 3 months, each strategy looks only at the past 1 year of prices, sets its weights, then holds them for the next 3 months. No peeking at the future. Uses the last 5 years of days when all your stocks traded.</p>
  <button class="btn ghost" id="btRun" type="button">Run the backtest</button><div id="btOut"></div></section>`;
}
function bindStrat(A,P,use,w,rf){
  const sec=$("#stratSec");if(!sec)return;
  const n=use.length,cap=Math.max(state.cap||1,1/n),S=P.C.map(r=>r.map(c=>c*TD)),mu=P.S.map(s=>s.ar),erm=state.erm??ermDefault();
  const MW=mcapW(use),V=state.blv||{},views=use.map(h=>{const v=parseFloat(V[h.sym]);return Number.isFinite(v)?v/100:NaN});
  const defs=stratDefs(n,cap,rf,w),all=[...defs.map(([l,f])=>[l,f(S,mu)]),["Black-Litterman",maxSharpe(blackLitterman(S,MW.w,views,state.blc||"mid",rf,erm).mu,S,cap,rf)]];
  sec.querySelectorAll("[data-sw]").forEach(b=>b.onclick=()=>{const x=all[+b.dataset.sw];v2apply(use,x[1],x[0]+" weights applied")});
  sec.querySelectorAll(".blv").forEach(i=>i.onchange=()=>{state.blv=state.blv||{};const v=i.value.trim();if(v==="")delete state.blv[i.dataset.s];else if(Number.isFinite(parseFloat(v)))state.blv[i.dataset.s]=parseFloat(v);save();renderPortfolio()});
  const bc=$("#blc");if(bc)bc.onchange=()=>{state.blc=bc.value;save();renderPortfolio()};
  $("#btRun").onclick=()=>{const o=$("#btOut");o.innerHTML=`<p class="load">Running…</p>`;setTimeout(()=>{
    const syms=use.map(h=>h.sym),need=syms.filter(s=>!store[s]);if(need.length){o.innerHTML=`<p class="note">Prices not loaded.</p>`;return}
    const B=align(syms,5),R=B.ret,T=R[0]?R[0].length:0,L=252,Hd=63;
    if(T<L+Hd){o.innerHTML=`<p class="note">Not enough shared history: the backtest needs at least 15 months when all your stocks traded (have ${T} days). A recent listing shortens it.</p>`;return}
    const out=defs.map(([l])=>({l,v:[100],to:0,re:0,w:null}));
    for(let t=L;t<T;t+=Hd){
      const win=R.map(r=>r.slice(t-L,t)),C=win.map(a=>win.map(b=>cov(a,b)*TD)),m=win.map(a=>mean(a)*TD);
      defs.forEach(([l,f],k)=>{const o=out[k],nw=f(C,m);if(o.w){o.to+=nw.reduce((a,x,i)=>a+Math.abs(x-o.w[i]),0)/2;o.re++}
        let h=nw.slice();for(let d=t;d<Math.min(t+Hd,T);d++){const g=h.reduce((a,x,i)=>a+x*(1+R[i][d]),0);h=h.map((x,i)=>x*(1+R[i][d])/g);o.v.push(o.v.at(-1)*g)}o.w=h});
    }
    const dates=B.dates.slice(L),res=out.map(o=>({...o,...summ(o.v,dates,rf)}));
    o.innerHTML=`<div class="panel" style="margin-top:10px"><div class="fig" id="btFig"><svg role="img" aria-label="Backtest growth of 100 rupees"></svg></div>${legend(res.map(r=>r.l))}
      <p class="note">Growth of ₹100 from ${fmtD(dates[0])} to ${fmtD(dates.at(-1))}, before costs and taxes.</p></div>
      <div class="scroll"><table><thead><tr><th>Strategy</th><th class="n">₹100 became</th><th class="n">CAGR</th><th class="n">Risk</th><th class="n">Sharpe</th><th class="n">Max fall</th><th class="n">Turnover a year</th></tr></thead><tbody>
      ${res.map(r=>`<tr><td><b>${esc(r.l)}</b></td><td class="n">₹${num(r.v.at(-1),0)}</td><td class="n ${cls(r.cagr)}">${pct(r.cagr,1)}</td><td class="n">${pct(r.vol,1)}</td><td class="n">${fx(r.sharpe)}</td><td class="n neg">${pct(r.mdd,1)}</td><td class="n">${pct(r.to/Math.max(r.yrs,.25),0)}</td></tr>`).join("")}
      </tbody></table></div><p class="note">Turnover = share of the portfolio traded at each rebalance, per year; higher turnover means more brokerage and tax. Black-Litterman is not in the backtest because it needs your views at each date. Past results do not predict the future.</p>`;
    draw($("#btFig"),(W,H)=>multiLine(W,H,dates,res.map(r=>({v:r.v}))));
  },30)};
}

/* ---------- C1. Brinson-Fachler attribution by sector against a Nifty 500 built from market caps ---------- */
function brinsonHTML(use,w){
  if(!V2ON("brinson")||!use.length)return "";
  const y=state.period,U=LIST.filter(x=>x.n5).map(x=>STOCKS[x.sym]).filter(x=>x&&metric(x,y)&&Number.isFinite(metric(x,y).pr));
  if(U.length<100)return "";
  const mc=U.map(x=>{const f=fund(x.sym);return f&&f[4]>0?f[4]:NaN}),cover=mc.filter(Number.isFinite).length,useMc=cover>=U.length*.6;
  const bs={};let tot=0;U.forEach((x,i)=>{const wt=useMc?(Number.isFinite(mc[i])?mc[i]:0):1;if(!wt)return;const k=x.ind||"Not classified";bs[k]=bs[k]||{w:0,r:0};bs[k].w+=wt;bs[k].r+=wt*metric(x,y).pr;tot+=wt});
  for(const k in bs){bs[k].r/=bs[k].w;bs[k].w/=tot}
  const ps={};use.forEach((h,i)=>{const x=STOCKS[h.sym],m=x&&metric(x,y);if(!m||!Number.isFinite(m.pr))return;const k=sectorOf(h.sym);ps[k]=ps[k]||{w:0,r:0};ps[k].w+=w[i];ps[k].r+=w[i]*m.pr});
  let pw=0;for(const k in ps){ps[k].r/=ps[k].w;pw+=ps[k].w}for(const k in ps)ps[k].w/=pw;
  const Rb=Object.values(bs).reduce((s,v)=>s+v.w*v.r,0),Rp=Object.values(ps).reduce((s,v)=>s+v.w*v.r,0);
  const keys=[...new Set([...Object.keys(ps),...Object.keys(bs)])],rows=keys.map(k=>{const wp=ps[k]?ps[k].w:0,wb=bs[k]?bs[k].w:0,rb=bs[k]?bs[k].r:0,rp=ps[k]?ps[k].r:rb;
    return {k,wp,wb,rp:ps[k]?rp:NaN,rb,al:(wp-wb)*(rb-Rb),se:wb*(rp-rb),in:(wp-wb)*(rp-rb)}}).filter(r=>r.wp>0||r.wb>.02).sort((a,b)=>Math.abs(b.al+b.se+b.in)-Math.abs(a.al+a.se+a.in));
  const T=rows.reduce((s,r)=>({al:s.al+r.al,se:s.se+r.se,in:s.in+r.in}),{al:0,se:0,in:0}),other=keys.length-rows.length;
  const allT={al:0,se:0,in:0};keys.forEach(k=>{const wp=ps[k]?ps[k].w:0,wb=bs[k]?bs[k].w:0,rb=bs[k]?bs[k].r:0,rp=ps[k]?ps[k].r:rb;allT.al+=(wp-wb)*(rb-Rb);allT.se+=wb*(rp-rb);allT.in+=(wp-wb)*(rp-rb)});
  return `<section style="margin-top:28px"><h2>Brinson attribution by sector ${tip("brinson")}</h2>
  <div class="figs"><div class="fig1"><div class="lab">Your return (${y}Y total)</div><div class="mid ${cls(Rp)}">${pct(Rp,1)}</div></div><div class="fig1"><div class="lab">Nifty 500 (built)</div><div class="mid ${cls(Rb)}">${pct(Rb,1)}</div></div>
  <div class="fig1"><div class="lab">Sector choice (allocation)</div><div class="mid ${cls(allT.al)}">${pct(allT.al,1)}</div></div><div class="fig1"><div class="lab">Stock choice (selection)</div><div class="mid ${cls(allT.se)}">${pct(allT.se,1)}</div></div><div class="fig1"><div class="lab">Interaction</div><div class="mid ${cls(allT.in)}">${pct(allT.in,1)}</div></div></div>
  <div class="scroll"><table><thead><tr><th>Sector</th><th class="n">Your weight</th><th class="n">Index weight</th><th class="n">Your return</th><th class="n">Index return</th><th class="n">Allocation</th><th class="n">Selection</th><th class="n">Interaction</th></tr></thead><tbody>
  ${rows.map(r=>`<tr><td>${esc(r.k)}</td><td class="n">${pct(r.wp,1)}</td><td class="n">${pct(r.wb,1)}</td><td class="n ${cls(r.rp)}">${Number.isFinite(r.rp)?pct(r.rp,1):"–"}</td><td class="n ${cls(r.rb)}">${pct(r.rb,1)}</td><td class="n ${cls(r.al)}">${pct(r.al,2)}</td><td class="n ${cls(r.se)}">${pct(r.se,2)}</td><td class="n ${cls(r.in)}">${pct(r.in,2)}</td></tr>`).join("")}
  </tbody></table></div>
  <p class="note">Brinson-Fachler: allocation = (wp − wb)(Rb,sector − Rb,total); selection = wb(Rp,sector − Rb,sector); interaction = (wp − wb)(Rp,sector − Rb,sector). The three add up to ${pct(Rp-Rb,1)}, your gap over the index. The index is rebuilt from ${U.length} Nifty 500 stocks ${useMc?"weighted by today's market cap":"equally weighted (market caps not loaded yet)"}, so it is close to, not exactly, the official index.${other?` ${other} small sectors with no holding are hidden but counted.`:""}</p></section>`;
}

/* ---------- C2. rebalancing simulator: buy-and-hold, calendar, band, CPPI ---------- */
function rebalHTML(use){
  if(!V2ON("rebal")||use.length<2)return "";
  return `<section style="margin-top:28px" id="rbSec"><h2>Rebalancing simulator ${tip("rebal")}</h2>
  <p class="note">Your target weights, run through this period's real prices with different rebalancing rules. CPPI keeps a floor: it holds stocks only up to a multiple of the cushion above the floor, and parks the rest at the risk-free rate.</p>
  <div class="ctl"><label style="font-size:14px;display:grid;gap:2px">Amount ₹<input id="rbAmt" inputmode="numeric" value="${state.rbAmt||1000000}"></label>
  <label style="font-size:14px;display:grid;gap:2px">Trading cost % of each trade<input id="rbCost" inputmode="decimal" value="${state.rbCost??0.2}"></label>
  <label style="font-size:14px;display:grid;gap:2px">CPPI floor %<input id="rbFl" inputmode="decimal" value="${state.rbFl??80}"></label>
  <label style="font-size:14px;display:grid;gap:2px">CPPI multiplier<input id="rbM" inputmode="decimal" value="${state.rbM??3}"></label></div>
  <button class="btn ghost" id="rbRun" type="button">Run the simulation</button><div id="rbOut"></div></section>`;
}
function bindRebal(use,w,rf){
  if(!$("#rbRun"))return;
  $("#rbRun").onclick=()=>{
    const amt=Math.max(1000,parseFloat($("#rbAmt").value.replace(/,/g,""))||1e6),cost=Math.max(0,parseFloat($("#rbCost").value)||0)/100,fl=Math.min(.99,Math.max(0,(parseFloat($("#rbFl").value)||80)/100)),mult=Math.max(0,parseFloat($("#rbM").value)||3);
    Object.assign(state,{rbAmt:amt,rbCost:cost*100,rbFl:fl*100,rbM:mult});save();
    const B=align(use.map(h=>h.sym),state.period),R=B.ret,T=R[0]?R[0].length:0,o=$("#rbOut");
    if(T<40){o.innerHTML=`<p class="note">Not enough days when all your stocks traded.</p>`;return}
    const run=(rule)=>{let h=w.map(x=>x*amt),v=[amt],paid=0,trades=0;
      for(let d=0;d<T;d++){h=h.map((x,i)=>x*(1+R[i][d]));let V=h.reduce((a,b)=>a+b,0);
        const drift=Math.max(...h.map((x,i)=>Math.abs(x/V-w[i])));
        if(rule.every&&(d+1)%rule.every===0||rule.band&&drift>rule.band){const tr=h.reduce((a,x,i)=>a+Math.abs(w[i]*V-x),0),c=tr*cost;V-=c;paid+=c;trades++;h=w.map(x=>x*V)}
        v.push(V)}return {v,paid,trades}};
    const cppi=()=>{let V=amt,F=amt*fl,v=[amt],paid=0;const rfd=Math.pow(1+rf,1/TD)-1;let e=Math.min(V,mult*(V-F));
      for(let d=0;d<T;d++){const rp=w.reduce((a,x,i)=>a+x*R[i][d],0);const safe=V-e;e*=1+rp;V=e+safe*(1+rfd);F*=1+rfd;const ne=Math.max(0,Math.min(V,mult*(V-F))),c=Math.abs(ne-e)*cost;V-=c;paid+=c;e=Math.max(0,Math.min(V,mult*(V-F)));v.push(V)}
      return {v,paid,trades:T}};
    const res=[["Buy and hold",run({})],["Rebalance monthly",run({every:21})],["Rebalance quarterly",run({every:63})],["Rebalance yearly",run({every:252})],["Band: when any stock drifts 5%",run({band:.05})],[`CPPI (floor ${pct(fl,0)}, ×${mult})`,cppi()]].map(([l,r])=>({l,...r,...summ(r.v,B.dates,rf)}));
    o.innerHTML=`<div class="panel" style="margin-top:10px"><div class="fig" id="rbFig"><svg role="img" aria-label="Rebalancing rules compared"></svg></div>${legend(res.map(r=>r.l))}<p class="note">${fmtD(B.dates[0])} to ${fmtD(B.dates.at(-1))}, after trading costs, before tax.</p></div>
    <div class="scroll"><table><thead><tr><th>Rule</th><th class="n">Final value</th><th class="n">CAGR</th><th class="n">Risk</th><th class="n">Max fall</th><th class="n">Rebalances</th><th class="n">Costs paid</th></tr></thead><tbody>
    ${res.map(r=>`<tr><td><b>${esc(r.l)}</b></td><td class="n">${rs(r.v.at(-1))}</td><td class="n ${cls(r.cagr)}">${pct(r.cagr,1)}</td><td class="n">${pct(r.vol,1)}</td><td class="n neg">${pct(r.mdd,1)}</td><td class="n">${r.l.startsWith("CPPI")?"daily":r.trades}</td><td class="n">${rs(r.paid)}</td></tr>`).join("")}
    </tbody></table></div><p class="note">Rebalancing sells what rose and buys what fell, which keeps risk near the target. In a strong trend, buy-and-hold often ends higher; in a choppy market, rebalancing can win. CPPI gives up some upside to protect the floor (it can still break the floor in a sudden crash).</p>`;
    draw($("#rbFig"),(W,H)=>multiLine(W,H,B.dates,res.map(r=>({v:r.v}))));
  };
}

/* ---------- C3. PMS fee calculator (fixed, performance with hurdle and high-water mark, GST) ---------- */
function feeHTML(P){
  if(!V2ON("fee"))return "";
  const F=state.fee||{};
  const g=Number.isFinite(F.g)?F.g:Math.round(Math.min(.25,Math.max(.06,P?P.ret:.12))*1000)/10;
  const inp=(id,l,v)=>`<label style="font-size:14px;display:grid;gap:2px">${l}<input id="${id}" inputmode="decimal" value="${v}"></label>`;
  return `<section style="margin-top:28px" id="feeSec"><h2>PMS fee calculator ${tip("pmsfee")}</h2>
  <p class="note">What a portfolio manager's fees do to your money. SEBI's minimum PMS ticket is ₹50 lakh. Fees here include 18% GST.</p>
  <div class="ctl">${inp("fAmt","Amount ₹",F.amt||5000000)}${inp("fYrs","Years",F.yrs||10)}${inp("fG","Gross return % a year",g)}
  <label style="font-size:14px;display:grid;gap:2px">Fee model<select id="fM"><option value="fixed" ${F.m==="fixed"?"selected":""}>Fixed fee only</option><option value="hybrid" ${!F.m||F.m==="hybrid"?"selected":""}>Fixed + performance (hybrid)</option><option value="perf" ${F.m==="perf"?"selected":""}>Performance only</option></select></label>
  ${inp("fFix","Fixed fee % a year",F.fix??(F.m==="fixed"?2.5:1.5))}${inp("fH","Hurdle % a year",F.h??10)}${inp("fS","Profit share % above hurdle",F.s??15)}${inp("fX","Exit load % (at the end)",F.x??0)}</div>
  <div id="feeOut"></div></section>`;
}
function bindFee(){
  const sec=$("#feeSec");if(!sec)return;
  const calc=()=>{const v=id=>parseFloat(String($("#"+id).value).replace(/,/g,"")),m=$("#fM").value;
    const F={amt:Math.max(1e5,v("fAmt")||5e6),yrs:Math.min(40,Math.max(1,Math.round(v("fYrs")||10))),g:Number.isFinite(v("fG"))?v("fG"):12,m,fix:Math.max(0,v("fFix")||0),h:Math.max(0,v("fH")||0),s:Math.max(0,v("fS")||0),x:Math.max(0,v("fX")||0)};
    state.fee=F;save();
    const g=F.g/100,fx_=m==="perf"?0:F.fix/100,sh=m==="fixed"?0:F.s/100,h=F.h/100,gst=.18;
    let V=F.amt,hwm=F.amt,tot=0,D=F.amt;const rows=[];
    for(let y=1;y<=F.yrs;y++){const st=V,gross=V*(1+g),fixed=fx_*(st+gross)/2*(1+gst),V1=gross-fixed,thr=hwm*(1+h),perf=sh>0&&V1>thr?sh*(V1-thr)*(1+gst):0,V2=V1-perf;
      hwm=Math.max(hwm,V2);tot+=fixed+perf;V=V2;D*=1+g;rows.push({y,st,gain:gross-st,fixed,perf,end:V2})}
    const exit=V*F.x/100;V-=exit;tot+=exit;
    const net=Math.pow(V/F.amt,1/F.yrs)-1;
    $("#feeOut").innerHTML=`<div class="figs" style="margin-top:12px"><div class="fig1"><div class="lab">With no fees</div><div class="mid">${rs(D)}</div><div class="lab">${pct(g,1)} a year</div></div>
      <div class="fig1"><div class="lab">After all fees</div><div class="mid">${rs(V)}</div><div class="lab">${pct(net,2)} a year</div></div>
      <div class="fig1"><div class="lab">Total fees paid</div><div class="mid neg">${rs(tot)}</div><div class="lab">fee drag ${pct(g-net,2)} a year</div></div>
      <div class="fig1"><div class="lab">Money lost to fees</div><div class="mid neg">${rs(D-V)}</div><div class="lab">incl. growth the fees would have earned</div></div></div>
      <details><summary>Year by year</summary><div class="scroll"><table><thead><tr><th>Year</th><th class="n">Start</th><th class="n">Gross gain</th><th class="n">Fixed fee</th><th class="n">Performance fee</th><th class="n">End</th></tr></thead><tbody>
      ${rows.map(r=>`<tr><td>${r.y}</td><td class="n">${rs(r.st)}</td><td class="n">${rs(r.gain)}</td><td class="n">${rs(r.fixed)}</td><td class="n">${rs(r.perf)}</td><td class="n">${rs(r.end)}</td></tr>`).join("")}
      ${exit>0?`<tr><td colspan="5">Exit load ${pct(F.x/100,1)}</td><td class="n neg">−${rs(exit)}</td></tr>`:""}</tbody></table></div></details>
      <p class="note">Fixed fee is charged on the year's average value. The performance fee is charged only on gains above the hurdle and above the high-water mark (the highest value already charged), so you never pay twice for the same gain. Real PMS fees are charged quarterly on daily values; this yearly model is close. Same return every year is assumed; real returns vary.</p>`};
  sec.querySelectorAll("input,select").forEach(e=>e.onchange=calc);calc();
}

/* ---------- C4. GIPS-style performance presentation (Performance page) ---------- */
function gipsHTML(R){
  if(!V2ON("gips")||!R.series||R.series.length<20)return "";
  const s=R.series,yrs={};s.forEach(x=>{yrs[x.d.slice(0,4)]=x});
  const ys=Object.keys(yrs).sort(),me={};s.forEach(x=>{me[x.d.slice(0,7)]=x});
  const months=Object.keys(me).sort().map(k=>me[k]),mr=months.slice(1).map((x,i)=>[x.d,x.cum/months[i].cum-1,x.n/months[i].n-1]);
  let prev=s[0];
  const rows=ys.map(y=>{const e=yrs[y],p=prev;prev=e;const partial=p.d.slice(0,4)===y||e.d.slice(5)<"12-24";
    const m36=mr.filter(x=>x[0]<=e.d).slice(-36),ok=m36.length>=36;
    return {y,p:e.cum/p.cum-1,b:Number.isFinite(e.n)&&Number.isFinite(p.n)?e.n/p.n-1:NaN,partial,v:e.V,sp:ok?sdOf(m36.map(x=>x[1]))*Math.sqrt(12):NaN,sb:ok?sdOf(m36.map(x=>x[2]))*Math.sqrt(12):NaN}});
  return `<section style="margin-top:28px"><h2>Performance presentation (GIPS style) ${tip("gips")}</h2>
  <div class="scroll"><table><thead><tr><th>Year</th><th class="n">Your return (TWRR)</th><th class="n">${BN()}</th><th class="n">Excess</th><th class="n">3-yr SD you</th><th class="n">3-yr SD index</th><th class="n">Year-end value</th></tr></thead><tbody>
  ${rows.map(r=>`<tr><td>${r.y}${r.partial?" <span class=\"note\">(part year)</span>":""}</td><td class="n ${cls(r.p)}">${pct(r.p,1)}</td><td class="n ${cls(r.b)}">${Number.isFinite(r.b)?pct(r.b,1):"–"}</td><td class="n ${cls(r.p-r.b)}">${Number.isFinite(r.b)?pct(r.p-r.b,1):"–"}</td><td class="n">${Number.isFinite(r.sp)?pct(r.sp,1):"–"}</td><td class="n">${Number.isFinite(r.sb)?pct(r.sb,1):"–"}</td><td class="n">${rs(r.v)}</td></tr>`).join("")}
  <tr><td><b>Since start (a year)</b></td><td class="n ${cls(R.twA)}"><b>${pct(R.twA,1)}</b></td><td class="n ${cls(R.nfA)}"><b>${pct(R.nfA,1)}</b></td><td class="n ${cls(R.twA-R.nfA)}"><b>${pct(R.twA-R.nfA,1)}</b></td><td colspan="3"></td></tr></tbody></table></div>
  <p class="note">Laid out like a GIPS composite report: time-weighted returns per calendar year after trading costs, the benchmark, and the 3-year standard deviation of monthly returns (shown once 36 months exist). One account only, so internal dispersion and composite assets are not applicable. Returns are before management fees and tax. <b>This is a learning layout, not a claim of GIPS compliance.</b></p></section>`;
}
