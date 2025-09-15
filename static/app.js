// Clean, corrected implementation
const qs = s => document.querySelector(s);
const logEl = document.getElementById('debug');
function log(line){
  const ts = new Date().toISOString().split('T')[1].replace('Z','');
  if(logEl){ logEl.textContent += `[${ts}] ${line}\n`; logEl.scrollTop = logEl.scrollHeight; }
}
async function apiAsk(params){
  const r = await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});
  if(!r.ok) throw new Error(r.status+' '+r.statusText); return r.json();
}
async function apiAskStream(params, onEvent){
  let r;
  try {
    r = await fetch('/ask/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});
  } catch(e){
    throw new Error('stream fetch failed:'+e);
  }
  if(r.status === 404){
    // server 可能尚未更新或未重启，触发上层降级
    const err = new Error('STREAM_ENDPOINT_NOT_FOUND');
    err.code = 404; // @ts-ignore
    throw err;
  }
  if(!r.ok) throw new Error(r.status+' '+r.statusText);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer='';
  while(true){
    const {done,value} = await reader.read();
    if(done) break;
    buffer += decoder.decode(value,{stream:true});
    let idx;
    while((idx = buffer.indexOf('\n\n'))>=0){
      const raw = buffer.slice(0,idx).trim();
      buffer = buffer.slice(idx+2);
      if(!raw.startsWith('data:')) continue;
      const dataStr = raw.slice(5).trim();
      if(dataStr==='[DONE]') break;
      try{ const obj = JSON.parse(dataStr); onEvent(obj); }catch(e){ log('parse err '+e); }
    }
  }
}
async function apiIngest(){
  const r = await fetch('/ingest',{method:'POST'}); if(!r.ok) throw new Error(r.status+' '+r.statusText); return r.json();
}
function renderContexts(list){
  const wrap = document.getElementById('contexts'); if(!wrap) return; wrap.innerHTML='';
  list.forEach((c,i)=>{
    const dt = document.createElement('details'); dt.className='ctx-item'; dt.open = i<2;
    const sm = document.createElement('summary'); sm.innerHTML = `<b>#${i+1}</b> score=${(c.score||0).toFixed(3)} <span class='small'>${c.source}</span>`; dt.appendChild(sm);
    if(c.content){ const pre=document.createElement('pre'); pre.textContent=c.content; dt.appendChild(pre); }
    wrap.appendChild(dt);
  });
}
function applyTheme(mode){ document.documentElement.dataset.theme = mode; localStorage.setItem('theme', mode); }
function initTheme(){ applyTheme(localStorage.getItem('theme') || 'light'); }
function mdToHtml(md){
  let h = md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  h = h.replace(/^###\s+(.*)$/gm,'<h3>$1</h3>').replace(/^##\s+(.*)$/gm,'<h2>$1</h2>').replace(/^#\s+(.*)$/gm,'<h1>$1</h1>');
  h = h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>').replace(/`([^`]+)`/g,'<code>$1</code>');
  h = h.replace(/^(?:- |\* )(.*)$/gm,'<li>$1</li>').replace(/(<li>.*<\/li>\n?)+/g,m=>'<ul>'+m.replace(/\n/g,'')+'</ul>');
  return h.split(/\n{2,}/).map(p=>/^<h[1-3]>/.test(p)||/^<ul>/.test(p)?p:`<p>${p}</p>`).join('\n');
}
export function initApp(){
  initTheme();
  const askBtn = document.getElementById('askBtn');
  const ingestBtn = document.getElementById('ingestBtn');
  const answerEl = document.getElementById('answer');
  const askStatus = document.getElementById('askStatus');
  const ingestStatus = document.getElementById('ingestStatus');
  document.getElementById('themeToggle')?.addEventListener('click', ()=>{
    applyTheme(document.documentElement.dataset.theme==='light'?'dark':'light');
  });
  async function doAsk(stream=true){
    const q = document.getElementById('question').value.trim(); if(!q) return;
    const top_k = parseInt(document.getElementById('topk').value,10) || 6;
    const bm25_weight = parseFloat(document.getElementById('bm25').value) || 0.35;
    const include_content = document.getElementById('includeContent').checked;
    askBtn.disabled = true; askStatus.textContent='请求中...'; answerEl.innerHTML=''; renderContexts([]);
    const params = {question:q, top_k, bm25_weight, include_content};
    if(!stream){
      try { const data = await apiAsk(params); answerEl.innerHTML = mdToHtml(data.answer||'(无回答)'); renderContexts(data.contexts||[]); log('ASK ok'); }
      catch(e){ answerEl.textContent='错误: '+e; log('ASK error '+e); }
      finally{ askBtn.disabled=false; askStatus.textContent=''; }
      return;
    }
    let md='';
    try {
        await apiAskStream(params, ev=>{
            if(ev.type==='contexts'){ renderContexts(ev.data||[]); }
            else if(ev.type==='chunk'){ md += ev.data; answerEl.innerHTML = mdToHtml(md); }
            else if(ev.type==='end'){ log('stream end'); }
        });
      } catch(e){
          if(e && e.message === 'STREAM_ENDPOINT_NOT_FOUND'){
            log('stream endpoint 404, fallback normal ask');
            try { const data = await apiAsk(params); answerEl.innerHTML = mdToHtml(data.answer||'(无回答)'); renderContexts(data.contexts||[]); }
            catch(e2){ answerEl.textContent='错误: '+e2; }
          } else {
            answerEl.textContent='错误: '+e; log('ASK stream error '+e);
          }
      }
    finally { askBtn.disabled=false; askStatus.textContent=''; }
  }
  askBtn?.addEventListener('click', ()=>doAsk(true));
  document.getElementById('question')?.addEventListener('keydown', e=>{ if(e.key==='Enter' && (e.metaKey||e.ctrlKey)) doAsk(true); });
  ingestBtn?.addEventListener('click', async ()=>{
    ingestBtn.disabled=true; ingestStatus.textContent='运行中...';
    try { const r = await apiIngest(); ingestStatus.textContent='完成 added='+r.added; log('INGEST raw='+r.raw_items+' chunks='+r.chunks+' added='+r.added); }
    catch(e){ ingestStatus.textContent='失败'; log('INGEST error '+e); }
    finally { ingestBtn.disabled=false; }
  });
}
