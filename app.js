'use strict';
const $ = id => document.getElementById(id);
const Core = window.NutsCore;
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let experiment = null, selectedCandidate = 0, stopRequested = false;
let model, mode = 'detect', busy = false, revision = 0, lastDetection = null, lastRewrite = null, undoText = null;
const sample = 'Online learning has changed how students organise their studies. Recorded lectures let students revisit difficult topics at their own pace. This can be particularly useful when a lecturer introduces several unfamiliar ideas in one session. However, studying from home also requires discipline. Notifications, household responsibilities and unreliable internet connections can interrupt a lesson. Some students find it harder to ask questions online than in a classroom. A useful course should therefore combine flexible materials with regular opportunities for discussion. Clear weekly goals and timely feedback can help students understand what to focus on next.';
function message(text, error = false) { $('message').textContent = text; $('message').classList.toggle('error', error); }
function count() { return Core.words($('input').value).length; }
function nonEnglish(text) { const letters = text.match(/\p{L}/gu) || []; return !/[a-z]/i.test(text) || (letters.length && letters.filter(c => c > '\x7f').length / letters.length > .3); }
function dirty() {
  revision++;
  $('count').textContent = `${count().toLocaleString()} / 2,000 词`;
  $('highlights').textContent = '';
  $('detection').classList.add('stale'); $('rewritten').classList.add('stale');
  if (lastDetection || lastRewrite) message('原文或设置已改变，请重新处理。已有结果对应上一次输入。');
}
function resetDisplay() {
  $('empty').hidden = false; $('detection').hidden = true; $('rewritten').hidden = true;
  $('highlights').textContent = ''; $('engine').textContent = '等待输入';
}
function switchMode(next) {
  if (busy) return;
  mode = next; revision++; resetDisplay(); message('');
  const detect = mode === 'detect';
  $('detectTab').classList.toggle('active', detect); $('rewriteTab').classList.toggle('active', !detect);
  $('detectTab').setAttribute('aria-pressed', detect); $('rewriteTab').setAttribute('aria-pressed', !detect);
  $('settings').hidden = detect; $('detectInfo').hidden = !detect;
  $('crumb').textContent = detect ? '英文检测' : '英文润色';
  $('title').textContent = detect ? '读懂文字里的 AI 痕迹。' : '让好想法，表达得更好。';
  $('subtitle').textContent = detect ? '从整篇到每一句，了解英文文本的写作特征。' : '保留你的原意，打磨英文的语气、节奏与清晰度。';
  $('privacy').textContent = detect ? '检测分数表示模型的判断倾向，不是文章中 AI 内容的比例。' : '通过本机 Ollama 润色；请核对结果中的事实、数字与引用。';
  $('run').textContent = detect ? '检测文本 ↗' : '开始润色 ↗';
  $('resultTitle').textContent = detect ? '检测结果' : '润色结果';
  $('emptyTitle').textContent = detect ? '每一段文字，都值得细读。' : '你的意思，更清楚的表达。';
  $('emptyNote').textContent = detect ? '输入至少 80 个英文词，查看检测评分与逐句分析。' : '选择本地模型与风格，生成润色版本。';
}
async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await res.json();
  if (!res.ok) { const error = new Error(data.error || '请求失败'); error.status = res.status; throw error; }
  return data;
}
async function refreshModels() {
  $('refresh').disabled = true;
  const old = $('localModel').value;
  try {
    const data = await api('/api/status');
    $('localModel').replaceChildren(...data.models.map(name => new Option(name, name)));
    if (!data.models.length) $('localModel').add(new Option('尚无可用的本地模型', ''));
    if (data.models.includes(old)) $('localModel').value = old;
    else if (data.models.includes('qwen3:4b')) $('localModel').value = 'qwen3:4b';
    else if (data.models.includes('qwen2.5:7b')) $('localModel').value = 'qwen2.5:7b';
    for (const id of ['model2','model3','reviewModel']) {
      const select=$(id), previous=select.value, initial=!select.dataset.loaded;
      select.replaceChildren(new Option(id==='reviewModel'?'使用润色模型 1':'不使用',''), ...data.models.map(name=>new Option(name,name)));
      if(data.models.includes(previous)) select.value=previous;
      else if(initial && id==='model2' && data.models.includes('gemma3:4b') && $('localModel').value!=='gemma3:4b') select.value='gemma3:4b';
      else if(initial && id==='reviewModel' && data.models.includes('qwen2.5:7b')) select.value='qwen2.5:7b';
      select.dataset.loaded='true';
    }
    if (old !== $('localModel').value) dirty();
    $('modelStatus').textContent = data.available ? (data.models.length ? '已连接本机 Ollama。首次加载模型可能需要稍等。' : 'Ollama 已连接，请先下载模型，例如在终端运行 ollama pull qwen2.5:7b。') : '尚未连接 Ollama。请在这台电脑安装并启动 Ollama，下载模型后点击“刷新连接”。';
  } catch { $('modelStatus').textContent = '连接不到本地服务，请通过启动脚本打开网站。'; }
  finally { $('refresh').disabled = false; }
}
function highlights() {
  const result = lastDetection;
  if (!$('showHighlights').checked || !result || result.text !== $('input').value || mode !== 'detect' || $('detection').classList.contains('stale')) {
    $('highlights').textContent = ''; return;
  }
  let pos = 0, html = '';
  for (const s of result.sentences) {
    html += esc(result.text.slice(pos, s.start));
    const content = esc(result.text.slice(s.start, s.end));
    html += s.level ? `<mark class="${s.level === 1 ? 'mild' : ''}">${content}</mark>` : content;
    pos = s.end;
  }
  $('highlights').innerHTML = html + esc(result.text.slice(pos)) + '\n';
  syncScroll();
}
function syncScroll() { $('highlights').scrollTop = $('input').scrollTop; $('highlights').scrollLeft = $('input').scrollLeft; }
function showDetection(text, rule, lm) {
  const variant = lm ? 'full' : 'rules', m = model.doc[variant];
  const values = Core.docValues(rule, lm?.metrics), p = Core.probability(m, values);
  const verdict = Core.docVerdict(m, p, rule.words);
  const sm = model.sentence[variant];
  const sentences = rule.sentence_details.map((s, i) => {
    const prob = Core.probability(sm, Core.sentenceValues(s, lm?.sentences[i]));
    return {...s, prob, level:s.words >= 3 ? Core.sentenceLevel(sm, prob) : 0};
  });
  lastDetection = {text, sentences};
  $('empty').hidden = true; $('detection').hidden = false; $('rewritten').hidden = true;
  $('detection').classList.remove('stale');
  $('score').textContent = `${Math.round(p * 100)}%`;
  $('ring').style.setProperty('--score', `${p * 100}%`);
  $('verdict').textContent = {likely:'很可能是 AI 生成',possible:'可能有 AI 成分',unlikely:'不太像 AI 生成'}[verdict];
  $('engine').textContent = lm ? 'GPT-2 + 规则' : '仅规则 · 降级模式';
  $('verdictNote').textContent = '这是统计模型的参考评分，不能据此确认文字来源。';
  const labels = {log_ppl:'词语可预测性',log_sent_ppl_std:'句间可预测性变化',top10:'常见预测词占比',burst:'句子长短变化',avg_word_len:'平均词长',log_phrases:'常见 AI 短语',commas_per_sentence:'逗号使用习惯'};
  const contributions = m.features.map((f,i) => ({label:labels[f],value:m.coef[i] * ((values[f] ?? m.mean[i]) - m.mean[i]) / m.scale[i]})).sort((a,b) => Math.abs(b.value)-Math.abs(a.value)).slice(0,4);
  $('reasons').innerHTML = contributions.map(c => `<li><span class="reason-dot ${c.value < 0 ? 'human' : ''}">●</span>${esc(c.label)}：${c.value >= 0 ? '偏向 AI 特征' : '偏向人类写作特征'}</li>`).join('');
  const flagged = sentences.filter(s => s.level).sort((a,b) => b.prob-a.prob).slice(0,5);
  $('sentences').replaceChildren();
  for (const s of flagged) {
    const button = document.createElement('button'); button.className = 'sentence';
    button.textContent = `${Math.round(s.prob*100)}% · ${text.slice(s.start,s.end)}`;
    button.onclick = () => { if (text !== $('input').value) return; $('input').focus(); $('input').setSelectionRange(s.start,s.end); $('input').scrollTop = s.start/Math.max(text.length,1)*$('input').scrollHeight; syncScroll(); };
    $('sentences').append(button);
  }
  if (!flagged.length) $('sentences').textContent = '未发现达到高亮阈值的句子。';
  highlights();
}
function diffText(before, after) {
  const a = before.match(/\s+|\S+/g) || [], b = after.match(/\s+|\S+/g) || [];
  if (a.length*b.length > 300000) return `<del>${esc(before)}</del>\n\n<ins>${esc(after)}</ins>`;
  const dp = Array.from({length:a.length+1},()=>new Uint16Array(b.length+1));
  for (let i=a.length-1;i>=0;i--) for(let j=b.length-1;j>=0;j--) dp[i][j]=a[i]===b[j]?1+dp[i+1][j+1]:Math.max(dp[i+1][j],dp[i][j+1]);
  let i=0,j=0,result='';
  while(i<a.length||j<b.length) {
    if(i<a.length&&j<b.length&&a[i]===b[j]) { result+=esc(a[i]);i++;j++; }
    else if(j<b.length&&(i===a.length||dp[i][j+1]>=dp[i+1][j])) result+=`<ins>${esc(b[j++])}</ins>`;
    else result+=`<del>${esc(a[i++])}</del>`;
  }
  return result;
}
const platforms = ['Turnitin','GPTZero','ZeroGPT','QuillBot'];
function candidateScore(candidate) { return candidate.local_score?.score; }
function scoreLabel(score) { return score == null ? '不评分' : score.toFixed(2)+'%'; }
function renderExperiment() {
  const baseline = experiment.candidates[0]?.original_score?.score;
  const eligible = experiment.candidates.map((c,i)=>({c,i})).filter(({c})=>c.eligible && !c.duplicate && c.text.trim()!==experiment.original.trim());
  eligible.sort((a,b)=>(candidateScore(a.c) ?? Infinity)-(candidateScore(b.c) ?? Infinity));
  const best = eligible[0];
  selectedCandidate = best && (baseline==null || (candidateScore(best.c)!=null && candidateScore(best.c)<baseline)) ? best.i+1 : 0;
  $('selectionNote').textContent = selectedCandidate ? (baseline==null ? '原文不足 80 词，不比较检测分数。默认展示首个通过自动检查的候选；外部平台表现未知。' : '默认展示通过自动检查、且 Nuts 规则参考评分较低的候选。自动检查不保证语义完全正确，外部平台表现未知。') : '暂时保留原文：没有发现同时通过自动检查且本地参考评分更低的候选。你仍可逐个查看。';
  $('empty').hidden=true; $('detection').hidden=true; $('rewritten').hidden=false; $('rewritten').classList.remove('stale');
  selectCandidate(selectedCandidate);
}
function selectCandidate(index) {
  if (!experiment) return;
  selectedCandidate=index;
  const current=index ? experiment.candidates[index-1] : null;
  const output=current?.text ?? experiment.original;
  lastRewrite={before:experiment.original,after:output};
  $('output').value=output; $('diff').innerHTML=diffText(experiment.original,output);
  $('engine').textContent=current?.model || '原文基线';
  $('candidates').replaceChildren();
  const labels=['原文',...experiment.candidates.map((c,i)=>`版本 ${i+1} · ${c.model} · ${c.strategy}${c.duplicate?'（重复）':''}`)];
  labels.forEach((label,i)=>{const button=document.createElement('button');button.textContent=label;button.setAttribute('aria-pressed',i===index);button.onclick=()=>selectCandidate(i);$('candidates').append(button);});
  const baseline=experiment.candidates[0]?.original_score?.score;
  $('qualityNote').classList.toggle('quality-flag',Boolean(current&&!current.eligible));
  if(current) {
    const semantic=current.review;
    const issues=[...current.quality.issues,...current.quality.warnings];
    if(semantic.status==='flagged') issues.push('语义复核发现疑点：'+[...semantic.added_claims,...semantic.missing_claims,...semantic.changed_claims].join('；'));
    if(semantic.status==='unavailable') issues.push(semantic.reason || '语义复核未完成');
    if(semantic.status==='skipped') issues.push('语义复核已跳过');
    $('qualityNote').textContent=`Nuts 规则参考：原文 ${scoreLabel(baseline)} → 当前 ${scoreLabel(candidateScore(current))}。${current.eligible?'自动检查未发现问题（仍需人工核对）。':'不自动推荐此版本。'} ${issues.join('；')} 生成：${current.model}（${current.runtime?.seconds ?? '—'} 秒）；复核：${semantic.model || '待复核'}（${semantic.runtime?.seconds ?? '—'} 秒）。`;
  } else $('qualityNote').textContent=`原文 Nuts 规则参考：${scoreLabel(baseline)}。切换版本查看检查结果。`;
  $('rewriteWarning').textContent='不要把本地评分当成外部平台的预测值。选择版本后，请检查原意、事实和引用。';
  renderExternal();
}
function externalKey() { return selectedCandidate ? experiment.candidates[selectedCandidate-1].id : 'original'; }
function renderExternal() {
  const key=externalKey();
  experiment.external[key] ||= {};
  $('externalRows').replaceChildren();
  for (const platform of platforms) {
    const row=document.createElement('tr'), name=document.createElement('th'); name.textContent=platform;row.append(name);
    for (const [side,label] of [['original','原文'],[key,'当前版本']]) {
      const cell=document.createElement('td'), input=document.createElement('input');
      input.type='number';input.min=0;input.max=100;input.step='any';input.placeholder='未测';input.setAttribute('aria-label',platform+' '+label+'分数');
      input.value=experiment.external[side]?.[platform]?.value ?? '';
      if(side==='original' && label==='当前版本') input.disabled=true;
      input.onchange=()=>{
        if(input.value!=='' && (!input.checkValidity() || !Number.isFinite(Number(input.value)))) {message('检测分数必须是 0–100，未测请留空。',true);return;}
        experiment.external[side] ||= {};
        if(input.value==='') delete experiment.external[side][platform];
        else experiment.external[side][platform]={value:Number(input.value),recorded_at:new Date().toISOString(),source:'user-entered, not independently verified'};
        renderExternal();
      };
      cell.append(input);row.append(cell);
    }
    $('externalRows').append(row);
  }
  const values=platforms.map(p=>experiment.external[key]?.[p]?.value);
  const known=values.filter(v=>typeof v==='number');
  $('externalSummary').textContent=known.length===4 ? (known.every(v=>v===0)?'你录入的四项结果均为 0%；仅代表这个版本的这次手工记录，未经独立验证。':`已记录 4 / 4 项；最高分 ${Math.max(...known)}%，尚未达到本次全 0 目标。`) : `已记录 ${known.length} / 4 项，未测项未知，不能判断是否达到目标。`;
}
$('exportExperiment').onclick=()=>{
  if(!experiment)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify({...experiment,selected_version:externalKey()},null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='nuts-experiment-'+experiment.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
async function run() {
  if (busy) return;
  const text = $('input').value;
  if (!text.trim()) return message('请先输入英文文本。',true);
  if (nonEnglish(text)) return message('第一版仅支持英文文本，请输入英文。',true);
  if (count()>2000 || text.split(/\s+/).filter(Boolean).length>2000) return message('每次最多处理 2,000 个词，请分段处理。',true);
  if (mode==='detect' && count()<80) return message('文本太短：至少需要 80 个英文词才能进行检测。',true);
  if (mode==='detect' && !model) return message('检测模型未加载，请刷新页面重试。',true);
  if (mode==='rewrite' && !$('localModel').value) return message('请先连接 Ollama 并下载本地模型。',true);
  const currentRevision=revision;
  const requestMode=mode;
  busy=true;
  for (const id of ['run','detectTab','rewriteTab','apply','undo']) $(id).disabled=true;
  document.querySelectorAll('#settings select, #settings input, #settings textarea, #settings button').forEach(el=>el.disabled=true);
  $('run').textContent='处理中…';
  message(mode==='detect'?'正在检测。首次使用 GPT-2 需要下载模型，可能需要几分钟。':'本地模型正在润色，可能需要几分钟，请保持页面打开。');
  try {
    if (mode==='detect') {
      const rule=Core.analyze(text,model.phrases);
      let lm=null, fallback='';
      try {
        lm=await api('/api/score',{text});
        if(lm.sentences.length!==rule.sentence_details.length) throw new Error('逐句结果不匹配');
      } catch(e) { if(e.status===409||e.status===400) throw e; fallback='GPT-2 不可用，本次使用规则模型，准确率较低。'; }
      if(currentRevision!==revision) return message('输入已改变，请重新检测。旧请求结果未应用。');
      showDetection(text,rule,lm);
      message(fallback||'检测完成。点击右侧句子可定位原文。');
    } else {
      const config = {style:$('style').value, model:$('localModel').value, strength:$('strength').value,
        voice:$('voice').value, terms:$('terms').value.split(/[,，\n]/).map(s=>s.trim()).filter(Boolean), audit:false, profile:$('profile').value, reviewer:$('reviewModel').value || $('localModel').value};
      const generation=$('generation').value;
      const generators=generation==='multi' ? [...new Set([config.model,$('model2').value,$('model3').value].filter(Boolean))] : [config.model];
      const jobs=generation==='compare' ? [0,1,2].map(attempt=>({model:config.model,attempt})) : generators.map(model=>({model,attempt:0}));
      const total=jobs.length;
      config.generators=generators; config.generation=generation;
      stopRequested = false; $('stop').hidden = false; resetDisplay(); lastRewrite=null; selectedCandidate=0;
      experiment = {id:crypto.randomUUID(), created_at:new Date().toISOString(), original:text, settings:config,
        candidates:[], failures:[], external:{original:{}}, target:0, detector_note:'Nuts rules scores are not third-party scores.'};
      let completed = 0;
      for (let attempt=0; attempt<total; attempt++) {
        if (stopRequested || currentRevision!==revision) break;
        message(`正在生成候选 ${attempt+1} / ${total} · ${jobs[attempt].model}。生成完成后统一复核。`);
        try {
          const data = await api('/api/rewrite', {...config, text, ...jobs[attempt]});
          if (currentRevision!==revision) break;
          const duplicate = experiment.candidates.some(c=>c.text===data.text);
          experiment.candidates.push({...data, id:`candidate-${attempt+1}`, duplicate});
          completed++;
          renderExperiment();
        } catch(e) {
          experiment.failures.push({attempt:attempt+1, error:e.message});
          if (e.status===409) break;
        }
      }
      for (const candidate of experiment.candidates) {
        if(stopRequested || currentRevision!==revision) break;
        if(!candidate.quality.passed) continue;
        message(`正在统一复核 ${candidate.id} · ${config.reviewer}。`);
        try {
          const audit=await api('/api/review', {...config, text, output:candidate.text, model:config.reviewer});
          Object.assign(candidate,audit);
          renderExperiment();
        } catch(e) {
          candidate.review={status:'unavailable',model:config.reviewer,reason:e.message}; candidate.eligible=false;
          experiment.failures.push({candidate:candidate.id,stage:'review',error:e.message});
          if(e.status===409) break;
        }
      }
      if (currentRevision!==revision) { $('rewritten').classList.add('stale'); return message('输入或设置已改变，请重新生成。已完成的结果对应旧输入。'); }
      if (!completed) throw new Error(experiment.failures[0]?.error || '本轮没有生成候选。');
      renderExperiment();
      message(`已完成 ${completed} 个候选${stopRequested?'（已停止后续请求，未复核版本不自动推荐）':''}${experiment.failures.length?`；部分请求失败，已保留成功结果：${experiment.failures[0].error}`:''}。外部平台分数仍需实测。`);
    }
  } catch(e) { message(e.message||'处理失败，请稍后再试。',true); }
  finally {
    if(requestMode==='rewrite') {
      try { await api('/api/release',{}); }
      catch { message($('message').textContent+' 模型释放未完成，可在终端使用 ollama stop 模型名。',true); }
    }
    busy=false; $('stop').hidden=true;
    document.querySelectorAll('#settings select, #settings input, #settings textarea, #settings button').forEach(el=>el.disabled=false); for(const id of ['run','detectTab','rewriteTab','apply','undo']) $(id).disabled=false;
    $('run').textContent=requestMode==='detect'?'检测文本 ↗':'开始润色 ↗';
  }
}
$('detectTab').onclick=()=>switchMode('detect'); $('rewriteTab').onclick=()=>switchMode('rewrite');
$('input').addEventListener('input',dirty); $('input').addEventListener('scroll',syncScroll);
for(const id of ['style','terms','localModel','strength','generation','voice','model2','model3','reviewModel','profile']) $(id).addEventListener('change',dirty);
$('terms').addEventListener('input',dirty); $('voice').addEventListener('input',dirty);
$('stop').onclick=()=>{stopRequested=true;message('当前请求完成后将停止，已完成的候选会保留。');};
$('showHighlights').onchange=highlights; $('run').onclick=run; $('refresh').onclick=refreshModels;
$('input').addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();run();}});
$('clear').onclick=()=>{$('input').value='';dirty();resetDisplay();message('');};
$('sample').onclick=()=>{$('input').value=sample;dirty();};
$('file').onchange=async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;if(file.size>60000)return message('文件太大，请选择较短的 TXT 文件。',true);try{const text=await file.text();if(text.length>20000)throw new Error('文件超过 20,000 个字符。');$('input').value=text;dirty();}catch(e){message(e.message,true);}};
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText($('output').value);message('已复制润色结果。');}catch{message('复制失败，请在结果框中全选并复制。',true);}};
$('download').onclick=()=>{const url=URL.createObjectURL(new Blob([$ ('output').value],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='nuts-polished.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('apply').onclick=()=>{if(busy||!lastRewrite)return;undoText=$('input').value;$('input').value=lastRewrite.after;dirty();$('undo').hidden=false;message('结果已用作原文。可撤销替换，或切换至英文检测。');};
$('undo').onclick=()=>{if(busy||undoText===null)return;$('input').value=undoText;undoText=null;dirty();$('undo').hidden=true;message('已恢复替换前的原文。');};
$('theme').onclick=()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark';};
(async()=>{try{model=await api('/model.json');const ev=model.evaluation.full;$('accuracy').textContent=`已有 RAID 测试集：检出率 ${(ev.possible_tpr*100).toFixed(1)}%，误判率 ${(ev.possible_fpr*100).toFixed(1)}%；非母语论文段落误判率 ${(ev.esl_possible_fpr*100).toFixed(1)}%。均按“可能”阈值统计。`;}catch{message('无法加载检测模型，请通过本地启动脚本打开。',true);$('accuracy').textContent='评测数据未加载。';}})();
refreshModels();
