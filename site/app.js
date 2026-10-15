/* AShare Radar: static Netlify front end. Never embeds a paid API key, personal data, or pretend quotes. */
'use strict';
const emptyMarket={status:'pending',schema:2,generated_at:null,quote_collected_at:null,stocks:[],candidates:[],sectors:[],histories:{},backtests:{},coverage:{},quality:{},warnings:[]};
const KEY_WATCH='ashare-radar-watch-v2', KEY_SIM='ashare-radar-paper-v2';
const pageTitles={overview:'市场总览',screener:'全市场选股',strategies:'量化策略库',research:'研究引擎',tracking:'信号追踪',watchlist:'我的自选',backtest:'策略回测',simulator:'模拟账户',quality:'数据质量',assistant:'ChatGPT 研究'};
const state={page:'overview',market:emptyMarket,watch:loadJson(KEY_WATCH,[]),paper:loadJson(KEY_SIM,{initial:100000,cash:100000,trades:[]}),
  search:'',filter:'all',selected:null,backtest:null,stockLimit:60,tab:'candidates',historyPilot:null,historyHealth:null};
function loadJson(key,fallback){try{const x=JSON.parse(localStorage.getItem(key));return x===null?fallback:x}catch{return fallback}}
function save(key,val){try{localStorage.setItem(key,JSON.stringify(val))}catch{toast('浏览器存储不可用，修改无法保存')}}
const $=s=>document.querySelector(s);
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function n(v,d=2){if(v===null||v===undefined||v===''||!Number.isFinite(Number(v)))return '—';return Number(v).toLocaleString('zh-CN',{maximumFractionDigits:d,minimumFractionDigits:0})}
function cash(v){return '¥'+n(v,2)}
function percent(v){return v===null||v===undefined||!Number.isFinite(Number(v))?'—':`${v>=0?'+':''}${n(v,2)}%`}
function changeClass(v){return Number(v)>=0?'pos':'neg'}
function stamp(v){if(!v)return '尚无有效数据';const d=new Date(v);return Number.isNaN(d.getTime())?'时间未知':new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(d)+'（北京时间）'}
function dateCN(v){if(!v)return '—';const d=new Date(v);return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'medium'}).format(d)}
function dayCN(v=new Date()){const p=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(v);const m=Object.fromEntries(p.map(x=>[x.type,x.value]));return `${m.year}-${m.month}-${m.day}`}
function ageHours(){const d=Date.parse(state.market.generated_at||'');return Number.isFinite(d)?(Date.now()-d)/36e5:Infinity}
function stale(){return ageHours()>72}
function ok(){return state.market.status==='ok' && !!state.market.generated_at && state.market.stocks.length>0}
function statusBadge(){return ok()?stale()?'<span class="tag warn">数据超过72小时</span>':'<span class="tag">已连接历史行情快照</span>':'<span class="tag warn">等待首次真实行情更新</span>'}
function c(){return state.market.coverage||{}}
function quote(code){return (state.market.stocks||[]).find(s=>s.code===code)}
function sym(code){return /^\d{6}$/.test(code)}
function notifyNav(){document.querySelectorAll('[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===state.page));$('#breadcrumb').textContent=pageTitles[state.page];$('#sideStatus').textContent=ok()?(stale()?'历史数据已过期':'快照已保存'):'等待行情接入';}
function setPage(page){state.page=page;notifyNav();render();window.scrollTo({top:0,behavior:'smooth'})}
function toast(msg){const el=$('#toast');el.textContent=msg;el.classList.add('show');clearTimeout(window.toastTimeout);window.toastTimeout=setTimeout(()=>el.classList.remove('show'),3000)}
function title(eyebrow,name,sub,button=''){return `<div class="page-title"><div><p class="eyebrow">${eyebrow}</p><h1>${name}</h1><div class="sub">${sub}</div></div>${button?`<div class="right-actions">${button}</div>`:''}</div>`}
function panel(title,body,link=''){return `<section class="card panel-pad"><div class="panel-hd"><h3>${title}</h3>${link||''}</div>${body}</section>`}
function empty(head,desc){return `<div class="empty"><div class="empty-icon">◎</div><strong>${head}</strong><p>${desc}</p></div>`}
function marketWarning(){return `<div class="info-banner ${stale()?'warn':''}">${!ok()?'<b>尚未连接真实市场数据。</b> 请先通过 GitHub Actions 执行一次采集；本站绝不生成虚构行情。':stale()?`<b>历史数据较旧。</b> 上次采集 ${stamp(state.market.generated_at)}，请勿把它用于盘中决策。`:`当前为 <b>定时采集的网页行情快照</b>，并非交易所实时推送。上次采集：${stamp(state.market.quote_collected_at)}。`}</div>`}
function metric(label,value,note,cls=''){return `<div class="card metric"><div class="label">${label}<span class="marker">↗</span></div><div class="value ${cls}">${value}</div><div class="note">${note}</div></div>`}
function stockRows(list,limit=20){if(!list?.length)return `<tr><td colspan="7" style="text-align:center;color:#8fa2b0;padding:26px">暂无真实股票数据</td></tr>`;return list.slice(0,limit).map((s,i)=>`<tr class="stock-row" data-stock="${esc(s.code)}"><td class="mono muted">${String(i+1).padStart(2,'0')}</td><td><div class="name">${esc(s.name)}</div><div class="code">${esc(s.code)}</div></td><td class="num">${cash(s.price)}</td><td class="num ${changeClass(s.change_pct)}">${percent(s.change_pct)}</td><td class="num">${s.score===undefined?'—':n(s.score,1)}</td><td>${s.signal?`<span class="pill">${esc(s.signal)}</span>`:'<span class="pill secondary">行情观察</span>'}</td><td><button class="btn sm ghost" data-add="${esc(s.code)}" aria-label="添加自选">☆</button></td></tr>`).join('')}
function table(list,limit=20){return `<div class="table-wrap"><table><thead><tr><th>#</th><th>股票</th><th>最新快照价</th><th>涨跌幅</th><th>技术分</th><th>信号</th><th>自选</th></tr></thead><tbody>${stockRows(list,limit)}</tbody></table></div>`}
function researchPrompt(code){
  const item=quote(code), cand=(state.market.candidates||[]).find(x=>x.code===code);
  const hist=(state.market.histories||{})[code];
  const details=[];
  details.push('请充当审慎的A股投资研究助手，以下内容来自我的个人研究平台的历史/定时行情快照，而不是交易所实时数据。');
  details.push('请先核实行情最新日期、重大公告、行业变化，再作判断。若数据不可用或来源不明，请直接说未知，不得编造实时价格、资金流、新闻或收益预测。');
  details.push('研究对象：'+(item?.name||'名称待核实')+'（'+code+'）');
  details.push('本地快照状态：'+(ok()?'已加载':'无真实市场数据')+'；可能过期：'+(stale()?'是':'否'));
  details.push('快照来源：'+(state.market.quote_provider||'未标明')+'；采集时间：'+(state.market.quote_collected_at||state.market.generated_at||'未知'));
  details.push('快照行情：'+(item?`价格 ${item.price??'未知'} 元；涨跌幅 ${item.change_pct??'未知'}%；成交额 ${item.amount??'未知'}`:'没有该股票的报价，必须自行核查'));
  details.push('技术信号：'+(cand?.signal||'未确认，不能当作买入信号'));
  details.push('历史日线：'+(hist?`最后一根 ${hist.last_bar||'未知'}，来源 ${hist.source||'未知'}`:'未获取'));
  details.push('策略触发理由：'+(cand?.reasons?.length?cand.reasons.join('；'):'没有完成规则确认'));
  details.push('请按以下结构回答：1. 已确认事实及其来源/日期；2. 技术趋势、量价与板块环境；3. 催化剂与反证；4. 关键观察/策略失效条件；5. 如需进一步分析应补充哪些数据。');
  details.push('不要把单次回测或AI评分当成未来收益保证；不做自动下单。');
  return details.join('\n\n');
}
function aiPage(){
 const choices=[...new Set([...state.watch,...(state.market.candidates||[]).slice(0,12).map(s=>s.code)])].filter(sym);
 const code=state.selected||choices[0]||'';
 return `${title('AI RESEARCH / PERSONAL','用你的 ChatGPT 研究股票','不需要在网站输入 ChatGPT 密码或 API Key；只有主动复制并粘贴后，你选择的信息才会进入 ChatGPT。')}
 <div class="info-banner warn">此功能<b>不是账号 API 直连</b>，不会读取你的 ChatGPT 历史对话或记忆。点击按钮后会复制本页研究提示词并打开 chatgpt.com，需要在 ChatGPT 中按 Ctrl+V / 粘贴。</div>
 <section class="card panel-pad"><div class="panel-hd"><h3>股票研究提示词</h3><span class="tag">零额外 API 费用</span></div>
 <div class="form-row"><input class="input" id="aiCode" inputmode="numeric" maxlength="6" placeholder="输入6位A股代码，如000725" value="${esc(code)}"/><button class="btn primary" id="generateAIPrompt">生成提示词</button></div>
 <p class="hint">候选代码：${choices.length?choices.slice(0,8).map(x=>`<button class="btn sm ghost" data-aicode="${x}">${x}</button>`).join(' '):'可直接输入股票代码'}</p>
 <textarea id="aiPrompt" class="input ai-textarea" readonly aria-label="待复制的股票研究提示词">${esc(code&&sym(code)?researchPrompt(code):'请输入有效的6位股票代码，点击生成提示词。')}</textarea>
 <div class="right-actions" style="margin-top:12px;flex-wrap:wrap"><button class="btn primary" id="copyAIPrompt">复制提示词</button><a class="btn ghost" href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">打开 ChatGPT ↗</a></div>
 <p class="hint">为保障隐私，模拟交易持仓不会自动加入提示词。不要粘贴账号密码、验证码或 API 密钥。</p></section>`;
}
function overview(){const d=state.market,co=c();const candidates=d.candidates||[],sectors=d.sectors||[];const wins=(d.stocks||[]).filter(s=>Number(s.change_pct)>0).length,loses=(d.stocks||[]).filter(s=>Number(s.change_pct)<0).length;
const charts=sectors.length?`<div class="sector-list">${sectors.slice(0,7).map((s,i)=>`<div class="sector-item"><div class="sector-name"><span>${esc(s.name)}</span><span>${percent(s.change_pct)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(3,Math.min(100,Math.abs(Number(s.change_pct)||0)*14))}%"></div></div></div>`).join('')}</div>`:empty('板块数据暂不可用','板块接口未获取成功或尚未运行采集。不会臆测资金流向。');
return `${title('INTELLIGENCE OVERVIEW','你的 A 股研究中心','从市场数据到交易信号，所有结论都有来源与时间。',`<button class="btn ghost" id="reload">↻ 重新读取数据</button>`)}
${marketWarning()}<div class="card hero"><div><p class="eyebrow">SYSTEM / FOCUS</p><h2>寻找有依据的机会，<em>而不是猜测涨跌。</em></h2><p>全市场快照预筛选，候选股历史 K 线验证。所有评分为可解释规则排序，不代表未来上涨概率。</p>${statusBadge()}</div><div class="hero-right"><div class="radar-ring"></div><small>DATA-FIRST INVESTING</small></div></div>
<div class="metrics">${metric('全市场有效快照',n(co.market_count,0),'只代表当次接口采集覆盖','cyan')}${metric('历史日线核验',n(co.history_succeeded,0)+' / '+n(co.history_attempted,0),'实际完成 K 线校验的数量')}${metric('策略触发',n(co.signal_count,0),'有限候选池的真实硬筛信号','green')}${metric('市场涨 / 跌',ok()?`${n(wins,0)} / ${n(loses,0)}`:'—','同一次行情快照，不是盘中实时')}
</div><div class="grid12">${panel('候选股 · 优先观察',candidates.length?table(candidates,7):empty('暂时没有确认信号','可能尚未采集、历史数据不足，或没有候选股满足硬性策略条件。'),`<button class="panel-link" data-page="screener">查看全部 →</button>`)}${panel('行业表现 · 当次快照',charts)}</div>
${panel('系统数据说明',`<div class="audit"><span class="bullet"></span><span>行情：${esc(d.quote_provider||'尚未接入')}；采集时间：${stamp(d.generated_at)}。</span></div><div class="divider"></div><div class="audit"><span class="bullet"></span><span>${esc(co.scope||'运行策略前无法确认数据覆盖。')}</span></div><div class="page-foot">当前版本不提供真正的盘中秒级预警或自动买卖。免费静态站点仅展示最近一次定时计算结果。</div>`)}`}
function filteredStocks(){const d=state.market,src=state.tab==='candidates'?d.candidates:d.stocks;let xs=(src||[]).filter(s=>{
const str=(s.code+' '+s.name).toLowerCase();if(state.search && !str.includes(state.search.toLowerCase()))return false;
if(state.filter==='up')return Number(s.change_pct)>0;
if(state.filter==='down')return Number(s.change_pct)<0;
return true;
});if(state.tab==='market'){xs.sort((a,b)=>(Number(b.amount)||0)-(Number(a.amount)||0))}return xs}
function screener(){const co=c();const rows=filteredStocks();return `${title('MARKET SCANNER','全市场选股','全市场仅完成行情快照预筛，历史技术分析仅覆盖部分候选股票。')}${marketWarning()}
<div class="card stats-strip"><span>行情样本<b>${n(co.market_count,0)}</b></span><span>历史核验<b>${n(co.history_succeeded,0)}</b></span><span>确认信号<b>${n(co.signal_count,0)}</b></span><span>规则<b>底部反转 / 放量突破 / 趋势修复</b></span></div>
<div class="controls"><button class="btn ${state.tab==='candidates'?'primary':'ghost'}" data-tab="candidates">策略候选</button><button class="btn ${state.tab==='market'?'primary':'ghost'}" data-tab="market">全市场快照</button><input id="query" class="input search" placeholder="搜索股票名称或代码" value="${esc(state.search)}"/><select id="filter" class="input"><option value="all" ${state.filter==='all'?'selected':''}>全部涨跌</option><option value="up" ${state.filter==='up'?'selected':''}>上涨</option><option value="down" ${state.filter==='down'?'selected':''}>下跌</option></select></div>
<div class="card panel-pad"><div class="panel-hd"><h3>${state.tab==='candidates'?'通过技术规则的股票':'行情快照 · 按成交额排序'}</h3><small id="countText">共 ${rows.length} 条</small></div><div id="stockTable">${table(rows,state.tab==='market'?state.stockLimit:20)}</div>${state.tab==='market'&&rows.length>state.stockLimit?`<button class="btn ghost" id="showMore" style="margin-top:15px">显示更多</button>`:''}</div>
<div id="detail">${detailHTML(state.selected)}</div><p class="page-foot">注意：全市场快照列表不代表全市场历史技术面扫描；列表没有技术分时是正常的。公开行情中的资金流入指标也不能等同于机构真实净买入。</p>`}
function chartSvg(arr,key='close',fill=false){if(!Array.isArray(arr)||arr.length<2)return empty('暂无有效历史曲线','只有成功采集到完整的历史数据才能显示图表。');let y=arr.map(x=>Number(x[key])).filter(Number.isFinite);if(y.length<2)return empty('无法绘图','价格数据无效');let mi=Math.min(...y),ma=Math.max(...y);if(mi===ma){mi-=1;ma+=1}const w=730,h=210,x0=15,x1=w-15,top=18,bot=h-32;const pts=arr.map((row,i)=>{const val=Number(row[key]);return Number.isFinite(val)?`${x0+(i/(arr.length-1))*(x1-x0)},${bot-((val-mi)/(ma-mi))*(bot-top)}`:null}).filter(Boolean).join(' ');return `<svg class="chart-svg" role="img" aria-label="历史走势线图" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="15" y1="${top}" x2="${x1}" y2="${top}" stroke="#263a4d" stroke-dasharray="3,6"/><line x1="15" y1="${(top+bot)/2}" x2="${x1}" y2="${(top+bot)/2}" stroke="#263a4d" stroke-dasharray="3,6"/><line x1="15" y1="${bot}" x2="${x1}" y2="${bot}" stroke="#263a4d" stroke-dasharray="3,6"/>${fill?`<polygon points="${x0},${bot} ${pts} ${x1},${bot}" fill="#b7ef6310"/>`:''}<polyline points="${pts}" fill="none" stroke="#b7ef63" stroke-width="2.2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/><text x="18" y="${top+12}">${n(ma,2)}</text><text x="18" y="${bot-8}">${n(mi,2)}</text></svg>`}
function detailHTML(code){if(!code)return '';const q=quote(code),his=state.market.histories[code],cand=state.market.candidates.find(x=>x.code===code);if(!q)return '';return `<div class="card panel-pad detail"><div class="detail-header"><div><p class="eyebrow">RESEARCH DETAIL / ${esc(code)}</p><h3>${esc(q.name)} <span class="code">${esc(code)}</span></h3></div><button class="btn sm ghost" id="closeDetail">关闭</button></div><div class="stats-strip"><span>行情价<b>${cash(q.price)}</b></span><span>涨跌幅<b class="${changeClass(q.change_pct)}">${percent(q.change_pct)}</b></span><span>技术分<b>${cand?n(cand.score,1):'未触发'}</b></span><span>日线时间<b>${his?esc(his.last_bar):'未采集'}</b></span></div>
<div class="chart-box">${his?chartSvg(his.bars,'close',true):empty('没有这只股票的完整日线','定时采集只针对部分候选股票，不代表历史数据不存在。')}</div><p class="hint">${his?`来源：${esc(his.source)}，不复权价格；本图仅作历史走势参考。`:'仅有行情快照，无法生成可靠的技术信号。'}</p><div class="divider"></div><h3>规则信号解释 ${cand?`<span class="tag">${esc(cand.signal)}</span>`:'<span class="tag gray">暂无信号</span>'}</h3><div class="rule-list">${cand?cand.reasons.map(r=>`<div class="rule">• ${esc(r)}</div>`).join(''):empty('尚无可解释的完整技术信号','没有依据的情况下不提供 AI 猜测或操作建议。')}</div><div class="right-actions" style="margin-top:18px"><button class="btn primary" data-add="${esc(code)}">☆ 加入自选</button><button class="btn ghost" data-backtest="${esc(code)}">查看研究回测</button><button class="btn ghost" data-chatgpt="${esc(code)}">与 ChatGPT 分析 ↗</button></div></div>`}
function watchlist(){const stocks=state.watch.map(code=>quote(code)||{code,name:'行情尚未缓存',price:null,change_pct:null});return `${title('WATCHLIST','我的自选股','仅保存在当前浏览器，不发布到网站，也不会自动同步手机。')}${marketWarning()}<div class="two-cols"><section class="card panel-pad"><div class="panel-hd"><h3>添加观察股票</h3></div><form id="addWatch"><label class="label-field" for="watchCode">输入 6 位 A 股代码</label><div class="form-row"><input class="input" id="watchCode" placeholder="例如 000725" inputmode="numeric" maxlength="6" required/><button class="btn primary" type="submit">添加</button></div></form><p class="hint">即使当前没有该股票的快照，也可以先存入代码。浏览器清理缓存可能删除自选记录。</p></section>${panel('我的观察列表',state.watch.length?`<div class="watch-tags">${state.watch.map(code=>`<span class="watch-tag">${esc(code)} <button title="从自选移除" data-remove="${esc(code)}">×</button></span>`).join('')}</div><small class="muted">点击下方股票查看本次行情快照</small>`:empty('观察池为空','添加自己关注的 A 股代码即可开始。'))}</div><div class="card panel-pad" style="margin-top:19px"><div class="panel-hd"><h3>自选行情 · 本次快照</h3><small>${state.watch.length} 只股票</small></div>${table(stocks,500)}</div>${detailHTML(state.selected)}`}
function backtest(){const keys=Object.keys(state.market.backtests||{}).sort();if(!keys.includes(state.backtest))state.backtest=keys[0]||null;const d=state.market.backtests[state.backtest],q=state.backtest?quote(state.backtest):null,m=d?.metrics;return `${title('STRATEGY LAB','策略回测实验室','仅单股 MA10/30 示范回测，不是完整 A 股量化回测，不能据此宣称策略盈利。')}${marketWarning()}<div class="info-banner warn"><b>重大限制：</b>不包含退市幸存者偏差、历史 ST 标记、分红送转、真实涨跌停成交与停牌完整模型；使用不复权数据。不能用此结果作为实盘依据。</div><div class="controls"><select id="backSelect" class="input" style="min-width:235px">${keys.length?keys.map(code=>`<option value="${esc(code)}" ${code===state.backtest?'selected':''}>${esc(code)} · ${esc(quote(code)?.name||'股票')}</option>`).join(''):'<option>无回测数据</option>'}</select></div>${!m?empty('等待历史数据与研究回测','GitHub Actions 成功采集历史K线后，展示样本内研究绩效。'): `<div class="metrics">${metric('累计收益',percent(m.total_return_pct),'示范模型扣估算交易成本',Number(m.total_return_pct)>=0?'green':'')}${metric('最大回撤',percent(m.max_drawdown_pct),'相对历史峰值的最大下行')}${metric('夏普比率',m.sharpe===null?'—':n(m.sharpe,2),'仅用于样本内研究')}${metric('成交笔数',n(m.trade_count,0),'非全市场组合回测')}</div>${panel(`${esc(q?.name||state.backtest)} · 单股资产净值`, `<div class="chart-box">${chartSvg(d.curve,'equity',true)}</div><div class="legend"><span><i class="dot"></i>模拟账户权益（元）</span><span>交易日 ${n(m.days,0)} 天</span></div><p class="hint">${esc(d.note||'')}</p>`)}`}`}
function computeLots(){const lots={},fees=[];for(const t of state.paper.trades||[]){let xs=lots[t.code]||(lots[t.code]=[]);if(t.side==='BUY'){xs.push({qty:t.qty,price:t.price,date:t.date})}else{let left=t.qty;for(const lot of xs){const use=Math.min(lot.qty,left);lot.qty-=use;left-=use;if(!left)break}if(left>0)throw new Error('模拟账本存在无法交割的卖出交易')}}return lots}
function positions(){let lots;try{lots=computeLots()}catch{toast('模拟交易账本不合法');return []}return Object.entries(lots).map(([code,xs])=>{let alive=xs.filter(x=>x.qty>0),qty=alive.reduce((s,x)=>s+x.qty,0),cost=alive.reduce((s,x)=>s+x.qty*x.price,0)/Math.max(1,qty),available=alive.filter(x=>x.date<dayCN()).reduce((s,x)=>s+x.qty,0),q=quote(code);return {code,qty,cost,available,q,marketValue:q&&q.price?qty*q.price:0}}).filter(x=>x.qty>0)}
function equity(){const pos=positions(); if(pos.some(p=>!p.q || !Number.isFinite(Number(p.q.price)) || Number(p.q.price)<=0) || (pos.length>0 && stale()))return null;return state.paper.cash+pos.reduce((s,p)=>s+p.marketValue,0)}
function simulator(){const pos=positions(),p=state.paper;return `${title('PAPER TRADING','我的模拟账户','使用定时快照价虚拟记账；这不是券商模拟撮合系统，也不代表实际可成交。',`<button class="btn ghost" id="exportPaper">导出备份</button>`)}
<div class="info-banner warn">个人交易记录只存于当前浏览器。手机与电脑不会自动同步。任何交易均为<b>按缓存价格人工虚拟记账</b>，不能当作真实市场成交。</div><div class="metrics">${metric('模拟总资产',equity()===null?'—':cash(equity()),'行情缺失或过期时不估算持仓市值','green')}${metric('可用现金',cash(p.cash),'资金模拟账户')}${metric('持仓数量',n(pos.length,0),'仅当前浏览器')}${metric('虚拟总收益',equity()===null?'—':percent((equity()/p.initial-1)*100),'不代表实际交易绩效')}</div>
<div class="two-cols"><section class="card panel-pad"><div class="panel-hd"><h3>新增模拟委托</h3></div><form id="paperForm"><div class="form-grid"><div><label class="label-field">方向</label><select class="input" name="side" style="width:100%"><option value="BUY">模拟买入</option><option value="SELL">模拟卖出</option></select></div><div><label class="label-field">股票代码</label><input name="code" class="input" inputmode="numeric" maxlength="6" placeholder="000725" required style="width:100%"/></div><div><label class="label-field">股票数量（100股整手）</label><input class="input" name="qty" type="number" min="100" step="100" value="100" required style="width:100%"/></div><div><label class="label-field">委托价格（元）</label><input class="input" name="price" type="number" min="0.01" step="0.01" placeholder="人工填写" required style="width:100%"/></div><div class="full"><button class="btn primary" type="submit" style="width:100%">确认模拟记账</button></div></div></form><p class="hint">默认资金 ¥100,000；费用估算：最低佣金 ¥5，万三佣金，卖出印花税 0.05%。卖出实行按日期 T+1，按 FIFO 从可卖批次扣减。</p></section>
${panel('当前持仓',pos.length?`<div class="table-wrap"><table><thead><tr><th>代码</th><th>总股数</th><th>今日可卖</th><th>均价</th></tr></thead><tbody>${pos.map(x=>`<tr><td class="code">${esc(x.code)}</td><td class="num">${n(x.qty,0)}</td><td class="num">${n(x.available,0)}</td><td class="num">${cash(x.cost)}</td></tr>`).join('')}</tbody></table></div>`:empty('尚无模拟持仓','在左侧建立模拟交易，记录不会发送到云端。'))}</div>
<div style="margin-top:19px">${panel('最近模拟交易',p.trades.length?`<div class="table-wrap"><table><thead><tr><th>日期</th><th>方向</th><th>代码</th><th>数量</th><th>价格</th><th>费用</th></tr></thead><tbody>${p.trades.slice(-15).reverse().map(t=>`<tr><td class="code">${esc(t.date)}</td><td class="${t.side==='BUY'?'neg':'pos'}">${t.side==='BUY'?'买入':'卖出'}</td><td class="code">${esc(t.code)}</td><td class="num">${n(t.qty,0)}</td><td class="num">${cash(t.price)}</td><td class="num">${cash(t.fee)}</td></tr>`).join('')}</tbody></table></div>`:empty('暂无交易日志','提交模拟买卖后在这里查看记录。'),`<button class="btn sm ghost" id="resetPaper">重置账户</button>`)}</div>`}
function quality(){const d=state.market,co=c(),q=d.quality||{},warnings=d.warnings||[];return `${title('DATA OBSERVABILITY','行情质量与系统状态','知道数据来自哪里、覆盖多少股票、更新于什么时候，比漂亮的分数更重要。',`<button class="btn primary" id="reload">↻ 重新加载快照</button>`)}${marketWarning()}<div class="metrics">${metric('有效快照行数',n(q.rows||co.market_count,0),'最低质量门槛 ≥1200')}${metric('有效价格占比',q.valid_price_ratio==null?'—':n(q.valid_price_ratio,1)+'%','仅统计有效快照')}${metric('重复股票代码',q.duplicate_codes==null?'—':n(q.duplicate_codes,0),'数据唯一性指标')}${metric('量比缺失率',q.missing_volume_ratio_pct==null?'—':n(q.missing_volume_ratio_pct,1)+'%','无法计算时不插入虚构数值')}</div>
<div class="two-cols">${panel('数据来源与时间',`<div class="rule-list"><div class="rule"><b>全市场：</b>${esc(d.quote_provider||'未接入')}</div><div class="rule"><b>行情类别：</b>${esc(d.quote_kind||'未标注')}</div><div class="rule"><b>采集时间：</b>${stamp(d.generated_at)}</div><div class="rule"><b>历史 K 线：</b>${esc(d.history_kind||'未标注')}</div><div class="rule"><b>实际历史核验：</b>${n(co.history_succeeded,0)}/${n(co.history_attempted,0)} 只股票</div></div>`)}${panel('执行异常与限制',warnings.length?`<div class="rule-list">${warnings.slice(0,9).map(e=>`<div class="rule">${esc(e)}</div>`).join('')}</div><p class="hint">仅显示前 9 条，完整异常记录在 JSON 内。</p>`:empty('无记录的异常','这不代表数据正确；跨源质量核对仍须独立验证。'))}</div>
<div style="margin-top:19px">${panel('部署维护说明',`<div class="rule-list"><div class="rule"><b>Netlify：</b>仅托管静态网页。免费信用额度方案支持 Private（仅所有者 Netlify 登录）。必须在控制台确认生产环境权限已开启。</div><div class="rule"><b>GitHub Actions：</b>周一至周五北京时间 16:45 和 19:20 计划运行；只更新 data 分支的纯行情 JSON，不触发 Netlify 主站生产部署。GitHub 定时可能延迟，非自动识别交易日。</div><div class="rule"><b>隐私：</b>自选股与模拟交易保存在浏览器 localStorage；清除浏览器存储会丢失，手机/电脑不自动共享。</div><div class="rule"><b>AI：</b>付费 AI 自动报告未开启。本版本只有程序计算的可解释技术信号，不会假装运行了语言模型。</div><div class="rule"><b>安全：</b>为了让免费静态站读取最新数据，如使用公开 GitHub 仓库，原始数据可被他人访问；绝不能往仓库加入私人持仓、券商密码、AI Key 或飞书 Webhook。</div></div><p class="page-foot">显示问题？按 README 按钮手动触发一次 GitHub Actions，先确认 config.json 已填写 GitHub 公开 data 分支原始 JSON 链接，再核实工作流具有 contents:write 权限。</p>`)}</div>`}
function historicalPilotPanel(){
  const p=state.historyPilot, h=state.historyHealth;
  if(!p || !h){
    return panel('100只历史数据库 · 四策略研究',empty('历史策略数据未发布或无法连接','100只样本正在进行真实入库；没有结果时不展示模拟信号。'));
  }
  const scanned=n(p.evaluated||0,0), total=n(p.attempted||100,0);
  const counts=p.signal_count_by_strategy||{};
  const rules=Array.isArray(p.strategy_definitions)?p.strategy_definitions:[];
  const badges=rules.map(r=>'<span class="tag gray">'+esc(r.name)+'：'+n(counts[r.id]||0,0)+'</span>').join(' ');
  const results=Array.isArray(p.signals)?p.signals:[];
  const latest=results.slice(0,40).map(r=>'<div class="rule"><b>'+esc(r.name)+' ('+esc(r.code)+')</b> · '+esc(r.strategy_name)+'<div class="hint">完成日K线 '+esc(r.signal_date)+' · 收盘参考 '+cash(r.reference_close)+' · 非交易建议</div></div>').join('');
  const status=p.status==='complete'?'样本检查完成':'部分股票数据不足、失败或过期';
  const info='<div class="info-banner warn"><b>100只样本研究，非A股全市场扫描。</b> '+esc(status)+'；最新数据处理时间 '+stamp(p.generated_at)+'；历史数据成功更新 '+n(h.succeeded,0)+'/100，只对'+scanned+'/'+total+'只股票执行四策略。收盘后信号不能视为当日收盘可交易。</div>';
  return '<div style="margin-top:20px">'+panel('100只真实历史股票 · 四套策略（Parquet）',
    '<div class="right-actions" style="margin-bottom:14px;justify-content:flex-start">'+badges+'</div>'+
    info+'<div class="hint" style="margin-top:15px">本次触发 '+n(p.signal_count,0)+' 条研究信号；质量报告 '+n(h.succeeded,0)+'/100只成功，'+n(h.failed,0)+'只失败。'+
    '<a href="https://github.com/Veraleehappiness/ashare-radar/blob/history/data_health_100.json" target="_blank" rel="noopener noreferrer">查看可审计结果 ↗</a></div>'+
    (latest?'<div class="rule-list" style="margin-top:14px">'+latest+'</div>':empty('100只样本暂无策略触发','没有信号并不等于没有研究机会；未检查股票不计入扫描。'))
  )+'</div>';
}
function strategies(){
  const lib=state.market.strategy_library||{};
  const rules=Array.isArray(lib.rules)?lib.rules:[];
  const signals=Array.isArray(lib.signals)?lib.signals:[];
  const active=rules.filter(r=>r.state==='experimental');
  const ruleHtml=rules.length?`<div class='rule-list'>${rules.map(r=>`<div class='rule'><b>${esc(r.name)}</b> <span class='muted'>${r.state==='experimental'?'研究规则·已编码':'数据待接入'}</span><div class='hint'>${esc(r.horizon)} · ${esc(r.entry)}</div><div class='hint'>${esc(r.evidence)}</div></div>`).join('')}</div>`:empty('策略库尚无数据','等待包含 strategy_library 的 GitHub 行情任务成功发布。');
  const signalHtml=signals.length?`<div class='rule-list'>${signals.slice(0,60).map(p=>`<div class='rule'><b>${esc(p.name)} (${esc(p.code)})</b> · ${esc(p.strategy_name)}<div class='hint'>${esc(p.signal_date)} · 研究参考收盘价 ${cash(p.reference_close)} · 20日量比 ${n(p.metrics?.volume_ratio20,2)} · 非买入指令</div></div>`).join('')}</div>`:empty('当前没有符合规则的信号','不得以演示数据补造信号；也不代表所有A股均经过深度扫描。');
  const count=lib.evaluated_stocks===undefined?'—':n(lib.evaluated_stocks,0);
  const stats=`<div class='metrics'>${metric('内置规则',rules.length?n(rules.length,0):'—','包含等待数据源的研究方向')}${metric('已编码规则',rules.length?n(active.length,0):'—','不等于已验证盈利')}${metric('K线核验股票',count,'当前只覆盖初筛股票')}${metric('今日触发',lib.signal_count==null?'—':n(lib.signal_count,0),'仅真实交易数据')}</div>`;
  return title('QUANT STRATEGY LAB','量化策略库','可复现规则和真实信号，独立于交易指令。')+marketWarning()+historicalPilotPanel()+stats+`<div class='info-banner warn' style='margin-top:18px'>策略均为研究假设，尚无样本外净收益证明。信号在收盘后才确定，不能按该收盘价假定成交。覆盖范围：${esc(lib.scope||'尚无已验证策略结果')}。</div><div style='margin-top:18px'>${panel('规则及数据要求',ruleHtml)}</div><div style='margin-top:18px'>${panel('实际触发信号',signalHtml)}</div>`;
}
function research(){
  const d=state.market, a=d.alphasift||{}, bk=d.research_backtests||{}, studies=d.backtests||{};
  const pickRows=(Array.isArray(a.picks)?a.picks:[]).slice(0,20);
  const picks=pickRows.length?`<div class='rule-list'>${pickRows.map((p,i)=>`<div class='rule'><b>${i+1}. ${esc(p.name||'股票')} · ${esc(p.code)}</b><div class='hint'>AlphaSift分数：${n(p.final_score,2)} · 策略：${esc(a.strategy||'未知')} · 独立行情来源：${esc(a.snapshot_source||'未说明')}</div></div>`).join('')}</div>`:empty('没有通过验证的 AlphaSift 候选','状态：'+esc(a.status||'未接入')+'；接口失败时不显示假结果。');
  const resultRows=Object.values(studies).filter(x=>x&&x.engine==='AKQuant');
  const reports=resultRows.length?`<div class='rule-list'>${resultRows.map(v=>{const m=v.metrics||{};return `<div class='rule'><b>${esc(v.name)} · ${esc(v.symbol)}</b><div class='hint'>样本：${esc(v.sample_start)} 至 ${esc(v.sample_end)} · 扣费模拟收益 ${percent(m.total_return_pct)} · 回撤 ${n(m.max_drawdown_pct,3)}% · 夏普 ${n(m.sharpe,2)} · 交易记录 ${n(m.trade_count,0)}</div><div class='hint'>${esc(v.scope||'限定样本研究')}；此样本策略无法代表全市场，不构成未来盈利证明。</div></div>`}).join('')}</div>`:empty('AKQuant 尚无有效结果','最新状态：'+esc(bk.status||'未接入')+'；不以虚拟收益填充。');
  return title('OPEN SOURCE RESEARCH','量化研究引擎','透明展示 AlphaSift 及 AKQuant 的真实运行输出。')+marketWarning()+`<div class='metrics'>${metric('AlphaSift',esc(a.status||'未接入'),'独立量化筛选引擎')}${metric('独立候选',pickRows.length?n(pickRows.length,0):'—','不与本地候选混作同源')}${metric('AKQuant',esc(bk.status||'未接入'),'仅特定样本实验')}${metric('回测样本',n(resultRows.length,0),'尚非全市场组合回测')}</div><div style='margin-top:18px'>${panel('AlphaSift 实际筛选结果',picks)}</div><div style='margin-top:18px'>${panel('AKQuant 有限样本历史回测',reports)}</div><p class='page-foot'>研究代码和数据可能有数据版本、历史成本及样本偏差。不能将回测当作必然可实现收益。</p>`;
}
function tracking(){
  const t=state.market.signal_tracking||{}, horizons=t.horizons||{};
  const steps=[1,5,10,20].map(nobs=>{const z=horizons[String(nobs)]||{};return `<div class='rule'><b>后续成功采集 ${nobs} 次</b><div class='hint'>成熟样本 ${n(z.matured_signals||0,0)} · 平均变化 ${z.mean_sampled_change_pct==null?'—':percent(z.mean_sampled_change_pct)} · 上涨比例 ${z.positive_ratio_pct==null?'—':n(z.positive_ratio_pct,2)+'%'}</div></div>`}).join('');
  const tip=(t.status==='ok')?'记录已接入；零成熟样本说明尚未积累到观察期限。':'追踪状态：'+esc(t.status||'未接入')+'；不可填造样本。';
  return title('FORWARD OBSERVATION','前瞻信号追踪','记录股票被筛选后的真实价格变化，不用未来数据回写历史信号。')+marketWarning()+`<div class='metrics'>${metric('累计追踪',t.tracked_total==null?'—':n(t.tracked_total,0),'公开策略信号记录')}${metric('本次新增',t.added_today==null?'—':n(t.added_today,0),'收盘快照通过校验后入账')}${metric('观察日期',esc(t.market_session||'—'),'交易日一致性检验')}${metric('成熟样本',n(Object.values(horizons).reduce((a,h)=>a+Number(h.matured_signals||0),0),0),'不同观察窗口不可简单累加成独立股票')}</div><div class='info-banner warn' style='margin-top:18px'>${tip} 观察窗口按成功采集次数计算，不一定等于真实交易日；未计入复权、滑点、佣金和停牌等实际交易条件。</div><div style='margin-top:18px'>${panel('不同观察窗口 · 真实样本',`<div class='rule-list'>${steps}</div>`)}</div>`;
}
function render(){notifyNav();const renderers={overview,screener,strategies,research,tracking,watchlist,backtest,simulator,quality,assistant:aiPage};$('#content').innerHTML=(renderers[state.page]||overview)()}
function addWatch(code){if(!sym(code)){toast('请输入六位股票代码');return}if(!state.watch.includes(code))state.watch.push(code);save(KEY_WATCH,state.watch);toast(`已添加 ${code} · 当前设备本地存储`);render()}
function simulate(form){const fd=new FormData(form),side=fd.get('side'),code=String(fd.get('code')||'').trim(),qty=Number(fd.get('qty')),price=Number(fd.get('price'));
if(!sym(code)||!Number.isInteger(qty)||qty<100||qty%100!==0||!Number.isFinite(price)||price<=0){toast('请核对代码、价格及100股整手数量');return}
const fee=Math.max(5,qty*price*.0003)+(side==='SELL'?qty*price*.0005:0),gross=qty*price;
if(side==='BUY' && state.paper.cash<gross+fee){toast('模拟资金不足');return}
if(side==='SELL' && (positions().find(x=>x.code===code)?.available||0)<qty){toast('违反 T+1 或模拟持仓不足，无法卖出');return}
state.paper.cash+=side==='SELL'?gross-fee:-gross-fee;
state.paper.trades.push({date:dayCN(),code,side,qty,price,fee:Math.round(fee*100)/100});save(KEY_SIM,state.paper);toast('已记录虚拟交易 · 不是实际成交');render()}
function backup(){const o={saved_at:new Date().toISOString(),watchlist:state.watch,simulator:state.paper};const blob=new Blob([JSON.stringify(o,null,2)],{type:'application/json'});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='ashare-private-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),300)}
async function copyPrompt(){
 const el=$('#aiPrompt');if(!el)return;
 el.focus();el.select();
 try{await navigator.clipboard.writeText(el.value);toast('提示词已复制，前往 ChatGPT 粘贴即可');}
 catch(e){toast('自动复制被浏览器限制，请按 Ctrl+C 或长按复制');}
}
function selectSymbol(code){state.selected=code;render();setTimeout(()=>$('#detail')?.scrollIntoView({behavior:'smooth',block:'start'}),20)}
async function fetchPilotData(){
  try{
    const response=await fetch('/config.json?t='+Date.now(),{cache:'no-store'});
    const config=response.ok?await response.json():{};
    const load=async (address)=>{
      if(!address||!/^https:\/\//.test(address))return null;
      const request=await fetch(address+(address.includes('?')?'&':'?')+'t='+Date.now(),{cache:'no-store'});
      if(!request.ok)throw Error('HTTP '+request.status);
      return request.json();
    };
    const [result,health]=await Promise.all([load(config.history_strategy_url),load(config.history_health_url)]);
    if(!result||!health||result.schema!==1||health.schema!==1)throw Error('100股票审计版本不兼容');
    state.historyPilot=result;
    state.historyHealth=health;
    if(state.page==='strategies'||state.page==='quality')render();
  }catch(err){
    state.historyPilot=null;
    state.historyHealth=null;
    if(state.page==='strategies'||state.page==='quality')render();
    console.warn('100-stock history feed unavailable:',err.message);
  }
}
async function fetchData(){try{const settingsResponse=await fetch('/config.json?t='+Date.now(),{cache:'no-store'});const settings=settingsResponse.ok?await settingsResponse.json():{};const source=(settings.market_data_url&&/^https:\/\//.test(settings.market_data_url))?settings.market_data_url:'/data/market.json';const r=await fetch(source+(source.includes('?')?'&':'?')+'t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(d.schema!==2 || !Array.isArray(d.stocks) || !Array.isArray(d.candidates))throw Error('数据版本或格式不兼容');state.market=d;render();}catch(err){state.market={...emptyMarket,warnings:['静态 JSON 请求失败：'+err.message]};render();toast('暂时无法加载行情数据')}}
function handlerClick(e){const page=e.target.closest('[data-page]');if(page){setPage(page.dataset.page);return}const add=e.target.closest('[data-add]');if(add){e.stopPropagation();addWatch(add.dataset.add);return}const del=e.target.closest('[data-remove]');if(del){state.watch=state.watch.filter(c=>c!==del.dataset.remove);save(KEY_WATCH,state.watch);render();return}
const aiButton=e.target.closest('[data-chatgpt]');if(aiButton){state.selected=aiButton.dataset.chatgpt;setPage('assistant');return}
 const codeButton=e.target.closest('[data-aicode]');if(codeButton){state.selected=codeButton.dataset.aicode;render();return}
 if(e.target.closest('#generateAIPrompt')){const code=String($('#aiCode')?.value||'').trim();if(!sym(code)){toast('请输入有效的六位 A 股代码');return}state.selected=code;render();toast('研究提示词已生成');return}
 if(e.target.closest('#copyAIPrompt')){copyPrompt();return}
 const stock=e.target.closest('[data-stock]');if(stock){selectSymbol(stock.dataset.stock);return}const bt=e.target.closest('[data-backtest]');if(bt){state.backtest=bt.dataset.backtest;setPage('backtest');return}const tab=e.target.closest('[data-tab]');if(tab){state.tab=tab.dataset.tab;state.stockLimit=60;render();return}
if(e.target.closest('#closeDetail')){state.selected=null;render();return}if(e.target.closest('#reload')){toast('重新加载定时研究数据');fetchData();fetchPilotData();return}if(e.target.closest('#showMore')){state.stockLimit+=60;render();return}if(e.target.closest('#exportPaper')){backup();return}
if(e.target.closest('#resetPaper')){if(window.confirm('这将清空当前浏览器的模拟交易记录，并重置为10万元虚拟本金，确定继续吗？')){state.paper={initial:100000,cash:100000,trades:[]};save(KEY_SIM,state.paper);render()}return}}
function setup(){document.addEventListener('click',handlerClick);
document.addEventListener('submit',e=>{if(e.target.id==='addWatch'){e.preventDefault();const code=$('#watchCode').value.trim();addWatch(code)}if(e.target.id==='paperForm'){e.preventDefault();simulate(e.target)}});
document.addEventListener('input',e=>{if(e.target.id==='query'){state.search=e.target.value;const el=$('#stockTable');if(el)el.innerHTML=table(filteredStocks(),state.tab==='market'?state.stockLimit:20);const count=$('#countText');if(count)count.textContent='共 '+filteredStocks().length+' 条'}});
document.addEventListener('change',e=>{if(e.target.id==='filter'){state.filter=e.target.value;render()}if(e.target.id==='backSelect'){state.backtest=e.target.value;render()}});
function clock(){const txt=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());$('#topTime').textContent='北京时间 '+txt}clock();setInterval(clock,60000);fetchData();fetchPilotData()}
setup();
