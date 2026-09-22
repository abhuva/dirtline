import {compile, makeNode, LUT_MAX_POINTS, defaultLutColor} from './recipe.mjs';

const $ = id => document.getElementById(id);
const element = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const clone = value => structuredClone(value);
const schema = await fetch('./schema.json').then(r => r.json());
const materialCatalog=(await fetch('./generated/art.json').then(r=>r.json())).catalog.materials;
const libraryResponse=await fetch('/api/library');
if(!libraryResponse.ok)throw new Error(`Could not load the map library (${libraryResponse.status}).`);
const libraryEnvelope=await libraryResponse.json();
let library=libraryEnvelope.library,libraryRevision=libraryEnvelope.revision;
const ops = new Map(schema.operations.map(o => [o.id,o]));
const savedSelection=localStorage.getItem('dustline.map-selection.v1');
let currentId=library.maps.some(entry=>entry.id===savedSelection)?savedSelection:library.maps[0].id;
let currentEntry=library.maps.find(entry=>entry.id===currentId);
let recipe=clone(currentEntry.recipe),includeInGame=currentEntry.includeInGame;
let selected=recipe.output??recipe.nodes[0]?.id??null,pending=null,dirty=false;
let undo = [], redo = [], sequence = 0, ready = false, timer, lastResponse, iteration = null;
let zoom=1,panX=0,panY=0;
let pinnedSettings = null;
let lutHistogram=null,lutHistogramNode=null,lutPointSelection=null;
let renderRequest=0,renderUrl=null,renderBlob=null,renderSeed=0,renderBusy=false;
let cancelConnectionDrag = null, suppressPortClick = false;
try {
  const saved=JSON.parse(localStorage.getItem('dustline.map-draft.v1'));
  if(saved?.id===currentId&&saved.revision===libraryRevision&&saved.recipe){
    recipe=saved.recipe;includeInGame=Boolean(saved.includeInGame);selected=recipe.output??recipe.nodes[0]?.id??null;dirty=true;
  }
} catch { /* A broken draft must never prevent opening the workshop. */ }
const worker = new Worker('./worker.mjs', {type:'module'});
worker.onerror = event => message(`Engine could not load: ${event.message}. Run ./map-editor.ps1 to rebuild it.`, 'error');
worker.onmessage = ({data}) => {
  if(data.render){
    if(data.id!==renderRequest)return;
    if(data.error){renderBusy=false;$('render-status').textContent=data.error;$('render-map').disabled=false;return;}
    if(data.progress!==undefined){$('render-status').textContent=`Rendering full map: ${data.progress}%`;return;}
    if(renderUrl)URL.revokeObjectURL(renderUrl);
    renderBlob=data.blob;renderSeed=data.seed;renderUrl=URL.createObjectURL(data.blob);
    renderBusy=false;$('render-image').src=renderUrl;$('render-status').textContent=`8192 × 8192 pixels · seed ${data.seed}`;
    $('save-render').disabled=false;$('render-map').disabled=false;return;
  }
  if (data.ready) { ready = true; $('engine-status').textContent = 'ENGINE READY · SHARED C++ / WASM'; schedule(); return; }
  if (data.id !== sequence) return;
  if (data.error) { $('preview').setAttribute('aria-busy','false'); message(data.error,'error'); return; }
  $('preview').setAttribute('aria-busy','false'); $('download-png').disabled=false;
  if(Object.hasOwn(data,'histogramNode')){lutHistogram=data.histogram;lutHistogramNode=data.histogramNode;updateVisibleLut();}
  lastResponse = data; draw(data);
};
function message(text, type='') { $('notice').textContent = text; $('notice').className = type; }
function remember() { undo.push(clone(recipe)); if (undo.length > 80) undo.shift(); redo = []; }
function save() {
  dirty=true;
  try {
    localStorage.setItem('dustline.recipe.v1', JSON.stringify(recipe));
    localStorage.setItem('dustline.map-draft.v1',JSON.stringify({id:currentId,revision:libraryRevision,recipe,includeInGame}));
  } catch { /* The repository Save action remains available. */ }
  $('undo').disabled = !undo.length; $('redo').disabled = !redo.length;
  updateMapControls();
}
function change(fn, repaint=true) { remember(); fn(); iteration = null; save(); if (repaint) render(); else { renderGraph(); schedule(); } }
function restore(from, to) {
  if (!from.length) return;
  to.push(clone(recipe)); recipe = from.pop();
  if (!recipe.nodes.some(n => n.id === selected)) selected = recipe.output??recipe.nodes[0]?.id??null;
  pending = null; iteration = null; save(); render();
}
function select(id) {
  selected = id; iteration = null; $('view').value = 'selected';
  renderGraph(); renderInspector(); schedule();
}
function settingsNodeId() { return pinnedSettings ?? selected; }
function arrange() {
  const levels = new Map(), visiting = new Set(), rows = new Map();
  function level(n) {
    if (levels.has(n.id)) return levels.get(n.id);
    if (visiting.has(n.id)) return 0;
    visiting.add(n.id);
    const sources = Object.values(n.inputs).map(id => recipe.nodes.find(n => n.id === id)).filter(Boolean);
    const depth = sources.length ? 1 + Math.max(...sources.map(level)) : 0;
    visiting.delete(n.id); levels.set(n.id, depth); return depth;
  }
  for (const n of recipe.nodes) {
    const depth = level(n), row = rows.get(depth) ?? 0;
    n.x = 35 + depth*235; n.y = 45 + row*190; rows.set(depth,row+1);
  }
}
function render() {
  if(pinnedSettings!==null && !recipe.nodes.some(n=>n.id===pinnedSettings))pinnedSettings=null;
  $('recipe-name').value = recipe.name ?? 'Untitled recipe'; $('seed').value = recipe.seed;
  $('include-in-game').checked=includeInGame;updateMapControls();
  renderGraph(); renderInspector(); schedule();
}
function summary(n) {
  if (n.type === 'random') return `${n.p[0]}% walls · border ${n.p[1]}`;
  if (n.type === 'cellular') return `${n.p[0]} passes · ${n.p[4]} neighbours`;
  if (n.type === 'world') return 'Connect · clear · place';
  if (n.type === 'roads') return `${n.p[0]} px / material ${n.p[1]}`;
  if (n.type === 'largest') return '4-connected floor';
  if (n.type === 'combine') return ['A ∪ B','A ∩ B','A − B','A ⊕ B'][n.p[0]];
  if (n.type === 'field_lut') return `${n.p[0]+1} bands · ${n.p[1]} initial`;
  return ops.get(n.type).parameters.map((p,i) => n.p[i]).join(' / ') || 'Binary mask';
}
function connectionError(sourceId, targetId, port) {
  const source=recipe.nodes.find(n=>n.id===sourceId), target=recipe.nodes.find(n=>n.id===targetId);
  const expected=target && ops.get(target.type).inputs[port]?.replace('?','');
  if (!source || !expected || ops.get(source.type).kind!==expected) return `This input needs a ${expected || 'compatible output'}.`;
  const visited=new Set();
  function reachesTarget(id) {
    if(id===targetId)return true;
    if(visited.has(id))return false;
    visited.add(id);
    return Object.values(recipe.nodes.find(n=>n.id===id)?.inputs ?? {}).some(reachesTarget);
  }
  return reachesTarget(sourceId)?'This connection would create a cycle.':null;
}
function connect(sourceId, targetId, port, selectTarget=true) {
  const error=connectionError(sourceId,targetId,port);
  if(error){message(error,'error');return;}
  const target=recipe.nodes.find(n=>n.id===targetId);
  pending=null;
  if(target.inputs[port]===sourceId){if(selectTarget)select(targetId);return;}
  change(()=>{target.inputs[port]=sourceId;if(selectTarget)selected=targetId;});
}
function disconnect(targetId, port, selectTarget=true) {
  const target=recipe.nodes.find(n=>n.id===targetId);
  if(!target || target.inputs[port]===undefined)return;
  pending=null;
  change(()=>{delete target.inputs[port];if(selectTarget)selected=targetId;});
}
function wirePath(x1,y1,x2,y2) {
  const bend=Math.max(45,Math.abs(x2-x1)/2);
  return `M${x1},${y1} C${x1+bend},${y1} ${x2-bend},${y2} ${x2},${y2}`;
}
function portPointerDown(event) {
  event.stopPropagation();
  if(event.button!==0)return;
  const start=event.currentTarget, pointerId=event.pointerId;
  const origin=start.getBoundingClientRect(), startX=event.clientX, startY=event.clientY;
  let moved=false, hover=null, preview=null;
  function endpoints(other) {
    if(!other || start.classList.contains('out')===other.classList.contains('out'))return null;
    const output=start.classList.contains('out')?start:other, input=output===start?other:start;
    return [Number(output.dataset.nodeId),Number(input.dataset.nodeId),input.dataset.port];
  }
  function cleanup() {
    window.removeEventListener('pointermove',move);
    window.removeEventListener('pointerup',up);
    window.removeEventListener('pointercancel',cancel);
    window.removeEventListener('blur',cancel);
    hover?.classList.remove('drop-valid','drop-invalid'); preview?.remove();
    start.classList.remove('pending'); cancelConnectionDrag=null;
  }
  function cancel() {cleanup();pending=null;renderGraph();}
  function move(e) {
    if(e.pointerId!==pointerId)return;
    if(!moved && Math.hypot(e.clientX-startX,e.clientY-startY)<4)return;
    e.preventDefault();
    if(!moved){
      moved=true;pending=null;start.classList.add('pending');
      preview=document.createElementNS('http://www.w3.org/2000/svg','path');
      preview.classList.add('wire-preview');$('wires').append(preview);
      $('graph-hint').textContent='Drop on a matching port to connect or replace. Escape cancels.';
    }
    hover?.classList.remove('drop-valid','drop-invalid');
    hover=document.elementFromPoint(e.clientX,e.clientY)?.closest('.port');
    const pair=endpoints(hover), valid=pair && !connectionError(...pair);
    hover?.classList.add(valid?'drop-valid':'drop-invalid');
    const rect=$('graph-plane').getBoundingClientRect();
    const x1=(origin.left+origin.width/2-rect.left)/zoom, y1=(origin.top+origin.height/2-rect.top)/zoom;
    const x2=(e.clientX-rect.left)/zoom,y2=(e.clientY-rect.top)/zoom;
    preview.setAttribute('d',start.classList.contains('out')?wirePath(x1,y1,x2,y2):wirePath(x2,y2,x1,y1));
  }
  function up(e) {
    if(e.pointerId!==pointerId)return;
    const pair=endpoints(document.elementFromPoint(e.clientX,e.clientY)?.closest('.port'));
    cleanup();
    if(!moved)return; // Ordinary clicks retain the keyboard-accessible connection flow.
    suppressPortClick=true;setTimeout(()=>{suppressPortClick=false;},0);
    if(pair)connect(...pair);
    else message('Connection unchanged. Drop on an input/output port of the matching type.');
    renderGraph();
  }
  cancelConnectionDrag=cancel;
  window.addEventListener('pointermove',move,{passive:false});
  window.addEventListener('pointerup',up);
  window.addEventListener('pointercancel',cancel);
  window.addEventListener('blur',cancel);
}
window.addEventListener('click',event=>{
  if(suppressPortClick){event.preventDefault();event.stopImmediatePropagation();}
},true);
function applyGraphView() {
  $('graph-plane').style.transform=`translate(${panX}px, ${panY}px) scale(${zoom})`;
  $('graph').style.backgroundPosition=`${panX}px ${panY}px`;$('graph').style.backgroundSize=`${18*zoom}px ${18*zoom}px`;
  $('zoom-label').textContent=`${Math.round(zoom*100)}%`;
}
function renderGraph() {
  $('nodes').replaceChildren(); $('wires').replaceChildren();
  const width = Math.max($('graph').clientWidth/zoom, ...recipe.nodes.map(n => (Number(n.x)||0)+230));
  const height = Math.max($('graph').clientHeight/zoom, ...recipe.nodes.map(n => (Number(n.y)||0)+210));
  $('graph-plane').style.width = `${width}px`; $('graph-plane').style.height = `${height}px`;
  applyGraphView();
  for (const n of recipe.nodes) {
    const op = ops.get(n.type), card = element('div',`node ${op.kind}${n.id===selected?' selected':''}`);
    card.dataset.nodeId = n.id; card.style.left = `${Number(n.x)||0}px`; card.style.top = `${Number(n.y)||0}px`;
    const head = element('div','node-heading');
    head.tabIndex=0;head.setAttribute('role','button');head.setAttribute('aria-label',`Inspect ${n.label}`);
    head.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select(n.id);}};
    head.append(element('div','node-label',n.label || op.name), element('div','node-type',`${String(n.id).padStart(2,'0')} / ${op.name}`));
    const out = element('button',`port out ${op.kind}${pending===n.id?' pending':''}`);
    out.dataset.nodeId=n.id;
    out.title = `Connect ${n.label} output`; out.setAttribute('aria-label',out.title);
    out.onclick = event => { event.stopPropagation(); pending = pending===n.id?null:n.id; renderGraph(); };
    out.onpointerdown = portPointerDown; head.append(out);
    head.onpointerdown = event => {
      if (event.button !== 0) return;
      event.preventDefault();
      const startX=event.clientX,startY=event.clientY,originalX=Number(n.x)||0,originalY=Number(n.y)||0;
      let moved=false;
      const move = e => {
        if (!moved && Math.abs(e.clientX-startX)+Math.abs(e.clientY-startY)<4) return;
        if (!moved) { remember(); moved=true; }
        n.x=Math.max(0,originalX+(e.clientX-startX)/zoom); n.y=Math.max(0,originalY+(e.clientY-startY)/zoom);
        renderGraph();
      };
      const up = () => {
        window.removeEventListener('pointermove',move); window.removeEventListener('pointerup',up);
        if (moved) save(); else select(n.id);
      };
      window.addEventListener('pointermove',move); window.addEventListener('pointerup',up,{once:true});
    };
    card.append(head);
    Object.entries(op.inputs).forEach(([port,expected], index) => {
      const row=element('div','node-port',`${port==='mask'?'Mask':port.toUpperCase()}${expected.endsWith('?')?' · optional':''}`);
      const button=element('button',`port ${expected.replace('?','')}${n.inputs[port]!==undefined?' connected':''}`);
      button.dataset.nodeId=n.id;button.dataset.port=port;button.onpointerdown=portPointerDown;
      button.title=`Connect ${n.label} input ${port}`; button.setAttribute('aria-label',button.title);
      button.onclick=() => {
        if (pending===null) { select(n.id); message('Choose an output dot first, or use the input selector below.'); return; }
        connect(pending,n.id,port);
      };
      row.append(button); card.append(row);
      const source=recipe.nodes.find(s=>s.id===n.inputs[port]);
      if (source) {
        const remove=element('button','disconnect','×');
        remove.title=`Disconnect ${n.label} input ${port}`;remove.setAttribute('aria-label',remove.title);
        remove.onclick=()=>disconnect(n.id,port);row.append(remove);
        const x1=(Number(source.x)||0)+190,y1=(Number(source.y)||0)+33;
        const x2=Number(n.x)||0,y2=(Number(n.y)||0)+75+index*24;
        const path=document.createElementNS('http://www.w3.org/2000/svg','path');
        const bend=Math.max(45,Math.abs(x2-x1)/2);
        path.setAttribute('d',`M${x1},${y1} C${x1+bend},${y1} ${x2-bend},${y2} ${x2},${y2}`);
        path.setAttribute('fill','none'); path.setAttribute('stroke',expected.startsWith('field')?'#7d97bb':expected.startsWith('material')?'#d8a576':'#899e62'); path.setAttribute('stroke-width','2');
        $('wires').append(path);
      }
    });
    const foot=element('div','node-summary',summary(n)); foot.onclick=()=>select(n.id); card.append(foot);
    if(n.id===recipe.output) card.append(element('div','node-output','ROM OUTPUT'));
    if(n.id===recipe.materialOutput) card.append(element('div','node-output','GROUND OUTPUT'));
    if(n.id===recipe.spawnOutput)card.append(element('div','node-output','SPAWN OUTPUT'));
    if(n.id===recipe.decorationOutput)card.append(element('div','node-output','DECORATION OUTPUT'));
    if(n.id===pinnedSettings) card.append(element('div','node-pinned-label','PINNED'));
    $('nodes').append(card);
  }
  $('graph-hint').textContent=pending===null?'Drag empty space to pan · wheel to zoom · drag ports to connect.':'Choose any matching input to connect or replace. Escape cancels.';
}
function setting(parent,label,control,full=false) {
  const row=element('label',`setting${full?' full':''}`); row.append(element('span','',label),control); parent.append(row); return row;
}
function lutPoints(n) {
  return Array.from({length:n.p[0]},(_,slot)=>({slot,position:n.p[2+slot*2],output:n.p[3+slot*2],color:n.colors[slot+1]}));
}
function lutEntryAt(n,position) {
  let entry={output:n.p[1],color:n.colors[0]};
  for(const point of lutPoints(n).sort((a,b)=>a.position-b.position))if(point.position<=position)entry=point;
  return entry;
}
function setLutPoints(n,points) {
  n.p=[points.length,n.p[1],...points.flatMap(point=>[point.position,point.output])];
  n.colors=[n.colors[0],...points.map(point=>point.color)];
}
function freeLutPosition(n,wanted,ignore=-1) {
  const occupied=new Set(lutPoints(n).filter(p=>p.slot!==ignore).map(p=>p.position));
  wanted=Math.max(1,Math.min(255,Math.round(wanted)));
  if(!occupied.has(wanted))return wanted;
  for(let distance=1;distance<255;++distance)for(const candidate of [wanted+distance,wanted-distance])
    if(candidate>=1 && candidate<=255 && !occupied.has(candidate))return candidate;
  return null;
}
function lutPreviewColors(n) {
  const colors=Array(256).fill(null),entries=[{output:n.p[1],color:n.colors[0]},...lutPoints(n).sort((a,b)=>a.position-b.position)];
  for(const entry of entries)colors[entry.output]=entry.color;
  return colors;
}
function readableText(color) {
  const rgb=[1,3,5].map(at=>parseInt(color.slice(at,at+2),16));
  return rgb[0]*299+rgb[1]*587+rgb[2]*114>145000?'#172419':'#f2f5e8';
}
function svgNode(tag,attributes={}) {
  const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const [name,value] of Object.entries(attributes))node.setAttribute(name,value);
  return node;
}
function renderLutDiagram(n,chart) {
  const points=lutPoints(n).sort((a,b)=>a.position-b.position),entries=[{position:0,output:n.p[1],color:n.colors[0]},...points];
  const bands=chart.querySelector('.lut-bands');bands.replaceChildren();
  entries.forEach((entry,index)=>{
    const end=entries[index+1]?.position??256;
    bands.append(svgNode('rect',{x:entry.position,y:0,width:end-entry.position,height:100,fill:entry.color}));
  });
  const histogram=lutHistogramNode===n.id?lutHistogram:null,max=histogram?Math.max(1,...histogram):1;
  let path='M0 96';
  for(let value=0;value<256;++value){const y=96-(histogram?.[value]??0)/max*82;path+=`L${value} ${y}L${value+1} ${y}`;}
  path+='L256 96Z';chart.querySelector('.lut-histogram').setAttribute('d',path);
  chart.querySelector('.lut-frequency').textContent=histogram?`${max} max / 4096 cells`:'Connect an input to see its distribution';
  const fixed=chart.querySelector('.lut-fixed');fixed.textContent=n.p[1];fixed.style.setProperty('--point-color',n.colors[0]);fixed.style.color=readableText(n.colors[0]);
  for(const handle of chart.querySelectorAll('.lut-point')) {
    const point=lutPoints(n).find(p=>p.slot===Number(handle.dataset.slot));
    if(point){handle.style.left=`${point.position/255*100}%`;handle.textContent=point.output;handle.title=`Input ${point.position} and above outputs ${point.output}`;handle.style.setProperty('--point-color',point.color);handle.style.color=readableText(point.color);}
  }
  const popup=chart.querySelector('.lut-popover');
  if(popup){const slot=Number(popup.dataset.slot),position=slot<0?0:n.p[2+slot*2];popup.style.left=`${Math.max(18,Math.min(82,position/255*100))}%`;}
}
function updateVisibleLut() {
  const chart=document.querySelector('.lut-chart'),n=recipe.nodes.find(n=>n.id===settingsNodeId());
  if(chart && n?.type==='field_lut')renderLutDiagram(n,chart);
}
function deleteLutPoint(n,slot) {
  const points=lutPoints(n).filter(point=>point.slot!==slot).map(({position,output,color})=>({position,output,color}));
  setLutPoints(n,points);lutPointSelection=null;
}
function addLutPoint(n,position) {
  if(n.p[0]>=LUT_MAX_POINTS)return false;
  position=freeLutPosition(n,position);
  if(position===null)return false;
  const points=lutPoints(n).map(({position,output,color})=>({position,output,color}));
  const source=lutEntryAt(n,position);points.push({position,output:source.output,color:source.color});setLutPoints(n,points);
  lutPointSelection={nodeId:n.id,slot:points.length-1};
  return true;
}
function renderLutPopup(n,chart) {
  if(lutPointSelection?.nodeId!==n.id)return;
  const slot=lutPointSelection.slot,fixed=slot===-1,point=fixed?{position:0,output:n.p[1],color:n.colors[0]}:lutPoints(n).find(point=>point.slot===slot);
  if(!point){lutPointSelection=null;return;}
  const popup=element('div','lut-popover');popup.dataset.slot=slot;popup.onclick=event=>event.stopPropagation();popup.onpointerdown=event=>event.stopPropagation();
  const heading=element('div','lut-popup-heading');heading.append(element('strong','',fixed?'Input 0 · fixed':`Input ${point.position}`));
  const close=element('button','lut-popup-close','×');close.setAttribute('aria-label','Close point editor');close.onclick=()=>{lutPointSelection=null;renderInspector();};heading.append(close);popup.append(heading);
  if(!fixed){
    const position=element('input');position.type='number';position.min=1;position.max=255;position.value=point.position;position.setAttribute('aria-label','Point position');
    position.onchange=()=>{const value=Number(position.value);if(position.validity.valid&&position.value!==''&&!lutPoints(n).some(p=>p.slot!==slot&&p.position===value))change(()=>{n.p[2+slot*2]=value;});else position.value=n.p[2+slot*2];};
    setting(popup,'Input position',position);
  }
  const output=element('input');output.type='number';output.min=0;output.max=255;output.value=point.output;output.setAttribute('aria-label',fixed?'Initial output value':'Point output value');
  output.onchange=()=>{if(output.validity.valid&&output.value!=='')change(()=>{if(fixed)n.p[1]=Number(output.value);else n.p[3+slot*2]=Number(output.value);});else output.value=fixed?n.p[1]:n.p[3+slot*2];};
  setting(popup,'Value / ID',output);
  const color=element('input');color.type='color';color.value=point.color;color.setAttribute('aria-label','Point color');color.onchange=()=>change(()=>{n.colors[slot+1]=color.value;});
  setting(popup,'Preview color',color);
  if(!fixed){const remove=element('button','lut-popup-delete','Delete point');remove.setAttribute('aria-label','Delete LUT point');remove.onclick=()=>change(()=>deleteLutPoint(n,slot));popup.append(remove);}
  chart.append(popup);
}
function renderLutEditor(settings,n) {
  const editor=element('div','lut-editor setting full');
  const header=element('div','lut-header');header.append(element('span','','INPUT DISTRIBUTION / STEPPED OUTPUT'),element('span','lut-count',`${n.p[0]+1} points`));editor.append(header);
  const chart=element('div','lut-chart');chart.setAttribute('aria-label','Input value histogram. Click to add a LUT point.');
  const svg=svgNode('svg',{viewBox:'0 0 256 100',preserveAspectRatio:'none','aria-hidden':'true'});
  svg.append(svgNode('g',{class:'lut-bands'}),svgNode('path',{class:'lut-histogram'}),svgNode('line',{class:'lut-axis',x1:0,y1:96,x2:256,y2:96}));chart.append(svg);
  const fixed=element('button',`lut-fixed${lutPointSelection?.nodeId===n.id&&lutPointSelection.slot===-1?' selected':''}`);fixed.style.left='0%';fixed.title='Position 0 is fixed';fixed.setAttribute('aria-label',`Fixed LUT point at 0, output ${n.p[1]}`);fixed.onclick=event=>{event.stopPropagation();lutPointSelection={nodeId:n.id,slot:-1};renderInspector();};chart.append(fixed);
  for(const point of lutPoints(n)) {
    const handle=element('button',`lut-point${lutPointSelection?.nodeId===n.id&&lutPointSelection.slot===point.slot?' selected':''}`);
    handle.dataset.slot=point.slot;handle.setAttribute('aria-label',`LUT point at ${point.position}, output ${point.output}`);
    handle.onpointerdown=event=>{
      if(event.button!==0)return;event.preventDefault();event.stopPropagation();
      const slot=Number(handle.dataset.slot),startX=event.clientX;let remembered=false,moved=false;
      lutPointSelection={nodeId:n.id,slot};
      const move=e=>{
        if(Math.abs(e.clientX-startX)>=2)moved=true;if(!moved)return;
        if(!remembered){remember();remembered=true;}
        const rect=chart.getBoundingClientRect(),position=freeLutPosition(n,(e.clientX-rect.left)/rect.width*255,slot);
        if(position!==null)n.p[2+slot*2]=position;iteration=null;save();renderLutDiagram(n,chart);schedule();
      };
      const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);renderGraph();renderInspector();};
      window.addEventListener('pointermove',move);window.addEventListener('pointerup',up,{once:true});
    };
    handle.onclick=event=>{event.stopPropagation();lutPointSelection={nodeId:n.id,slot:point.slot};renderInspector();};
    handle.onkeydown=event=>{
      if(event.key==='Delete'||event.key==='Backspace'){event.preventDefault();change(()=>deleteLutPoint(n,point.slot));return;}
      if(!['ArrowLeft','ArrowRight'].includes(event.key))return;
      event.preventDefault();const delta=(event.key==='ArrowLeft'?-1:1)*(event.shiftKey?8:1);
      change(()=>{n.p[2+point.slot*2]=freeLutPosition(n,n.p[2+point.slot*2]+delta,point.slot);});
    };
    chart.append(handle);
  }
  chart.onclick=event=>{
    if(n.p[0]>=LUT_MAX_POINTS||event.target.closest('.lut-point,.lut-fixed,.lut-popover'))return;
    const rect=chart.getBoundingClientRect();change(()=>addLutPoint(n,(event.clientX-rect.left)/rect.width*255));
  };
  chart.append(element('span','lut-zero','0'),element('span','lut-max','255'),element('span','lut-frequency'));
  renderLutPopup(n,chart);
  editor.append(chart,element('p','setting-help','Click empty graph space to add a point. Select a point to edit its preview color and value/ID. Drag movable points through one another to reorder them; position 0 stays fixed.'));
  settings.append(editor);renderLutDiagram(n,chart);
}
function renderInspector() {
  const root=$('inspector'); root.replaceChildren();
  const n=recipe.nodes.find(n=>n.id===settingsNodeId());
  const pinned=pinnedSettings!==null;
  $('pin-settings').textContent=pinned?'Unpin settings':'Pin settings';
  $('pin-settings').setAttribute('aria-pressed',String(pinned));
  $('pin-settings').disabled=!n;
  $('pin-settings').title=pinned?'Let settings follow the selected node':'Keep these controls while selecting another node to preview';
  $('inspector-node-name').textContent=n?`${pinned?'Pinned: ':''}${n.label}`:'';
  $('delete').disabled=!n || recipe.nodes.length===1;
  $('duplicate').disabled=!n || recipe.nodes.length>=32;
  $('delete').title=n?`Delete ${n.label}`:'';
  $('duplicate').title=n?`Duplicate ${n.label}`:'';
  const selectedType=recipe.nodes.find(n=>n.id===selected)?.type;
  $('set-output').disabled=!['world','roads','materials','spawns','decoration'].includes(selectedType);
  $('set-output').textContent=selectedType==='spawns'?'Use as spawn output':selectedType==='decoration'?'Use as decoration output':selectedType==='materials'?'Use as ground output':'Use as wall/floor output';
  if (!n) return;
  const op=ops.get(n.type),settings=element('div','settings'),lutTop=n.type==='field_lut'?element('div','lut-node-row'):settings;
  if(n.type==='field_lut')settings.append(lutTop);
  const label=element('input'); label.value=n.label; label.maxLength=80;
  label.onchange=()=>change(()=>{n.label=label.value;}); setting(lutTop,'Node label',label,n.type!=='field_lut');
  for(const [port,expected] of Object.entries(op.inputs)) {
    const input=element('select'); input.setAttribute('aria-label',`Input ${port}`);
    const empty=element('option','',expected.endsWith('?')?'None · apply everywhere':'Choose a source…'); empty.value=''; input.append(empty);
    recipe.nodes.filter(source=>source.id!==n.id && ops.get(source.type).kind===expected.replace('?','')).forEach(source=>{
      const option=element('option','',`${source.id} · ${source.label}`); option.value=source.id; input.append(option);
    });
    input.value=n.inputs[port]??'';
    input.onchange=()=>{if(input.value)connect(Number(input.value),n.id,port,false);else disconnect(n.id,port,false);input.value=n.inputs[port]??'';};
    setting(lutTop,`${port==='mask'?'Apply within mask':`Input ${port.toUpperCase()}`} · ${expected}`,input);
  }
  const parameterOrder=op.parameters.map((_,i)=>i);
  if(n.type==='field_lut')renderLutEditor(settings,n);
  else parameterOrder.forEach(index=>{
    const param=op.parameters[index];
    const [name,,min,max,mode]=param;
    if(mode==='rule') {
      const row=element('div','rule-buttons');
      for(let bit=0;bit<=8;++bit) {
        const button=element('button',n.p[index]&(1<<bit)?'active':'',String(bit));
        button.setAttribute('aria-label',`${name}: ${bit}`); button.setAttribute('aria-pressed',String(Boolean(n.p[index]&(1<<bit))));
        button.onclick=()=>change(()=>{n.p[index]^=1<<bit;}); row.append(button);
      }
      setting(settings,name,row,true);
    } else if(mode==='material') {
      const input=element('input');input.type='number';input.min=0;input.max=255;input.step=1;input.value=n.p[index];
      input.setAttribute('aria-label',name);input.setAttribute('list','material-ids');
      input.onchange=()=>{if(input.value!=='' && input.validity.valid)change(()=>{n.p[index]=Number(input.value);});else input.value=n.p[index];};
      const row=setting(settings,name,input);row.append(element('span','material-name',materialCatalog.find(m=>m.id===n.p[index])?.name??'Unassigned ID · renders as sand'));
    } else if(mode) {
      const choices={toggle:[[0,'No'],[1,'Yes']],neighbours:[[4,'4 · cardinal'],[8,'8 · surrounding']],combine:[[0,'Union · A OR B'],[1,'Intersection · A AND B'],[2,'Subtract · A minus B'],[3,'Exclusive OR']],voronoi:[[0,'Nearest site (squared)'],[1,'F2 − F1 (squared)']]};
      const input=element('select'); input.setAttribute('aria-label',name);
      choices[mode].forEach(([value,text])=>{const o=element('option','',text);o.value=value;input.append(o);});
      input.value=n.p[index]; input.onchange=()=>change(()=>{n.p[index]=Number(input.value);}); setting(settings,name,input);
    } else {
      const row=element('div','range-row'), slider=element('input'), number=element('input');
      slider.type='range'; number.type='number';
      for(const input of [slider,number]) {input.min=min;input.max=max;input.step=1;input.value=n.p[index];input.setAttribute('aria-label',name+(input===slider?' slider':''));}
      let remembered=false;
      slider.onpointerdown=()=>{remember();remembered=true;};
      slider.oninput=()=>{
        if(!remembered) remember();
        n.p[index]=Number(slider.value); number.value=slider.value; iteration=null; save(); renderGraph(); schedule();
      };
      slider.onchange=()=>{remembered=false;};
      number.onchange=()=>{ const value=Number(number.value); if(!number.validity.valid || number.value===''){number.value=n.p[index];return;} change(()=>{n.p[index]=value;}); };
      row.append(slider,number); setting(settings,name,row);
    }
  });
  if(op.random) {
    const input=element('input'); input.type='number'; input.min=0;input.max=4294967295;input.step=1;input.value=n.stream;
    input.onchange=()=>{ if(input.validity.valid && input.value!=='') change(()=>{n.stream=Number(input.value);});else input.value=n.stream;};
    setting(settings,'Random stream · 0 preserves the original seed',input,true);
  }
  if(n.type==='cellular') {
    const range=element('input');range.type='range';range.min=0;range.max=n.p[0];range.value=iteration??n.p[0];
    range.setAttribute('aria-label','Preview through iteration');
    const row=setting(settings,`Preview through iteration ${iteration??n.p[0]} / ${n.p[0]} · preview only`,range,true);
    range.oninput=()=>{iteration=Number(range.value); row.firstChild.textContent=`Preview through iteration ${iteration} / ${n.p[0]} · preview only`;if(pinnedSettings===null)$('view').value='selected';schedule();};
    settings.append(element('p','setting-help','Rule counts exclude the center. The optional mask limits updates; the forced solid border always wins.'));
  }
  if(n.type==='roads') settings.append(element('p','setting-help','One breadth-first search connects all towns to the starting town along shortest floor paths. Road width is constant, in world pixels (up to 256), rendered on the 8-pixel tile grid. Wide roads are clipped by walls and settlement artwork.'));
  if(n.type==='world') settings.append(element('p','setting-help','Enforces a 2-cell border, retains connected floor, creates a fallback clearing when needed, then carves the spawn and six outposts. Compare with its input to inspect these changes.'));
  if(n.type==='largest') settings.append(element('p','setting-help','Retains the largest four-connected floor component. Equal sizes choose the first in row-major order. An all-wall input stays all walls; final world placement handles fallback.'));
  if(n.type==='field_paint')settings.append(element('p','setting-help','Replace the field value wherever the mask is 1. All other cells keep their input value.'));
  if(n.type==='materials'){
    settings.append(element('p','setting-help','Interpret each input field value as a ground material ID for one 128 × 128 world-pixel cell. This output controls ground art and grip independently of wall/floor.'));
    const legacy=element('button','','Use original ground rules');legacy.onclick=()=>change(()=>{delete recipe.materialOutput;if(recipe.version<3)recipe.version=1;});settings.append(legacy);
  }
  if(n.type==='spawns')settings.append(element('p','placement-help','Applied to the final world. Input A: 0 forbids spawning; higher values increase relative likelihood. Count is limited by valid anchors and spacing. Starter encounters count toward the target and respect the field.'));
  if(n.type==='decoration')settings.append(element('p','placement-help','Applied to the final world. Input A multiplies density (0 = none, 255 = full). Four type weights are normalized automatically; all zero disables decoration. Positions stay fixed when type weights change.'));
  root.append(settings);
}
function schedule() {
  clearTimeout(timer); ++sequence; $('preview').setAttribute('aria-busy','true');
  $('download-png').disabled=true; $('export').disabled=true;
  $('render-map').disabled=true;
  message(ready?'Generating…':'Loading the shared generation engine…');
  timer=setTimeout(generate,70);
}
function generate() {
  if(!ready) return;
  try {
    let final=null;
    try {final=compile(recipe,schema,recipe.output,false);} catch { /* Independent stages can still be previewed. */ }
    const view=$('view').value, target=['selected','compare'].includes(view)?selected:recipe.output;
    const previewRecipe=clone(recipe), node=previewRecipe.nodes.find(n=>n.id===target);
    const iterationNode=previewRecipe.nodes.find(n=>n.id===settingsNodeId()),settingsNode=iterationNode;
    if(iteration!==null && iterationNode?.type==='cellular') iterationNode.p[0]=iteration;
    let compiled=compile(previewRecipe,schema,target,false);
    const placement=['spawns','decoration'].includes(compiled.kind);
    const spawnTarget=node.type==='spawns'?node.id:recipe.spawnOutput,decorTarget=node.type==='decoration'?node.id:recipe.decorationOutput;
    let spawnProgram=null,decorationProgram=null;
    if(compiled.kind==='world' || placement){
      if(spawnTarget!=null)spawnProgram=compile(previewRecipe,schema,spawnTarget,false).program;
      if(decorTarget!=null)decorationProgram=compile(previewRecipe,schema,decorTarget,false).program;
      if(placement)compiled=compile(previewRecipe,schema,recipe.output,false);
    }
    let materialProgram=null,materialError='';
    if(recipe.materialOutput!=null){try{materialProgram=compile(previewRecipe,schema,recipe.materialOutput,false).program;}catch(error){materialError=error.message;}}
    const histogramProgram=settingsNode?.type==='field_lut'&&settingsNode.inputs?.a!=null?compile(previewRecipe,schema,settingsNode.inputs.a,false).program:null;
    if(compiled.kind==='world' && materialError)throw new Error(materialError);
    let exportError='';
    try { const all=compile(recipe,schema); if(all.kind!=='world') exportError='Choose a Playable world node as the ROM output.'; } catch(error) {exportError=error.message;}
    $('export').disabled=Boolean(exportError); $('export').title=exportError||'Download the procedural recipe';
    $('recipe-status').textContent=(final?`${recipe.nodes.length} NODES · WALL/FLOOR + ${materialProgram?'GROUND IDS':'ORIGINAL GROUND'} · v${recipe.version}`:`${recipe.nodes.length} NODES · OUTPUT NEEDS A CONNECTION`)+` · ${dirty?'UNSAVED':'SAVED'}`;
    $('render-map').disabled=renderBusy || Boolean(exportError) || !final;
    $('preview-title').textContent=view==='seeds'?'Nine possibilities':node.label;
    $('preview-label').textContent=view==='seeds'?'CLICK A SEED TO EXPLORE':compiled.kind==='field'?'FIELD · 0—255':compiled.kind==='material'?'GROUND MATERIAL IDS · 0—255':$('layer').value==='textures'?'GAME TEXTURES · 8192 × 8192':'64 × 64 / 8192 px';
    const compare=!placement && view==='compare' && node.inputs?.a ? compile(previewRecipe,schema,node.inputs.a,false).program : null;
    const seeds=view==='seeds'?Array.from({length:9},(_,i)=>(recipe.seed+i)>>>0):null;
    message(exportError || 'Generating…',exportError?'warning':'');
    const categoricalColors=node?.type==='field_lut'?lutPreviewColors(node):null;
    worker.postMessage({id:sequence,program:compiled.program,materialProgram,spawnProgram,decorationProgram,histogramProgram,histogramNode:histogramProgram?settingsNode.id:null,categorical:!!categoricalColors,categoricalColors,showSpawns:$('show-spawns').checked,seed:recipe.seed,collision:$('layer').value==='collision' && !seeds,textures:$('layer').value==='textures',seeds,compare});
  } catch(error) {
    $('export').disabled=true; $('preview').setAttribute('aria-busy','false');
    $('preview-label').textContent='INVALID GRAPH · PREVIOUS PREVIEW'; message(error.message,'error');
  }
}
function regions(cells) {
  const labels=new Int32Array(4096),sizes=[]; let label=0;
  for(let i=0;i<4096;++i) if(!cells[i] && !labels[i]) {
    ++label; const queue=[i];labels[i]=label;
    for(let head=0;head<queue.length;++head) {
      const at=queue[head],x=at%64,y=at>>6;
      for(const next of [x?at-1:-1,x<63?at+1:-1,y?at-64:-1,y<63?at+64:-1])
        if(next>=0 && !cells[next] && !labels[next]) {labels[next]=label;queue.push(next);}
    }
    sizes.push(queue.length);
  }
  return {labels,count:label,largest:Math.max(0,...sizes)};
}
function paint(output,regionView=false,refined=true,categoricalColors=null) {
  if(output.texture){const canvas=document.createElement('canvas');canvas.width=canvas.height=output.texture.side;const ctx=canvas.getContext('2d');const pixels=ctx.createImageData(canvas.width,canvas.height);pixels.data.set(output.texture.pixels);ctx.putImageData(pixels,0,0);return canvas;}
  const source=refined && output.refined?output.refined:output.cells, side=source.length===4096?64:1024;
  const canvas=document.createElement('canvas');canvas.width=canvas.height=side;
  const ctx=canvas.getContext('2d'), pixels=ctx.createImageData(side,side), field=output.meta[1]===1;
  const labels=regionView && !field && side===64?regions(output.cells).labels:null;
  const palette=[[215,184,126],[129,175,148],[153,156,209],[213,144,110],[194,191,127],[142,191,206]];
  for(let i=0;i<source.length;++i) {
    let color;
    if(output.meta[1]===3){const hex=materialCatalog.find(m=>m.id===source[i])?.color??'#f04fbc';color=[1,3,5].map(at=>parseInt(hex.slice(at,at+2),16));}
    else if(field && categoricalColors){const hex=categoricalColors[source[i]]??defaultLutColor(source[i]);color=[1,3,5].map(at=>parseInt(hex.slice(at,at+2),16));}
    else if(field) {const t=source[i]/255;color=[31+t*203,55+t*168,48+t*119];}
    else color=source[i]?[37,66,55]:labels?palette[(labels[i]-1)%palette.length]:[215,184,126];
    pixels.data.set([...color,255],i*4);
  }
  ctx.putImageData(pixels,0,0);return canvas;
}
function markers(ctx,output,x,y,size) {
  if(output.meta[1]!==2) return;
  if($('show-spawns').checked && output.spawns){
    ctx.fillStyle='#f04040';
    for(let i=0;i<output.spawns.length;i+=2)ctx.fillRect(x+output.spawns[i]/8192*size-1,y+output.spawns[i+1]/8192*size-1,3,3);
  }
  for(let i=0;i<7;++i) {
    const px=output.meta[6+i*2]/8192*size+x,py=output.meta[7+i*2]/8192*size+y;
    ctx.fillStyle=i?'#effbc6':'#f7814e';ctx.strokeStyle='#253b2b';ctx.lineWidth=1.5;
    if(i) {ctx.fillRect(px-3.5,py-3.5,7,7);ctx.strokeRect(px-3.5,py-3.5,7,7);}
    else {ctx.beginPath();ctx.arc(px,py,5,0,Math.PI*2);ctx.fill();ctx.stroke();}
  }
}
function draw(data) {
  const canvas=$('preview'),ctx=canvas.getContext('2d'),layer=$('layer').value;
  ctx.imageSmoothingEnabled=false;ctx.fillStyle='#111c17';ctx.fillRect(0,0,640,640);
  const first=data.outputs[0],grid=data.outputs.length>1;
  const categoricalColors=data.categorical?data.categoricalColors??[]:null;
  const legend=categoricalColors?[...new Set(first.cells)].sort((a,b)=>a-b).map(value=>[`Output ${value}`,categoricalColors[value]??defaultLutColor(value)]):
    first.meta[1]===3 || first.texture ? materialCatalog.map(m=>[m.name,m.color]) : [['Floor','#d8b77b'],['Wall','#28483d'],['Spawn','#f08b5b'],['Outpost','#e7f6bc']];
  if(first.spawns && $('show-spawns').checked)legend.push(['Enemy spawns','#f04040']);
  $('legend').replaceChildren(...legend.map(([name,color])=>{const item=element('span'),swatch=element('i');swatch.style.background=color;item.append(swatch,document.createTextNode(name));return item;}));
  if(grid) {
    data.outputs.forEach((output,i)=>{
      const x=(i%3)*216,y=Math.floor(i/3)*216;
      ctx.drawImage(paint(output,layer==='regions',false,categoricalColors),x,y,208,186);
      ctx.fillStyle='#ccd8bc';ctx.font='13px Consolas,monospace';ctx.fillText(String(output.seed),x+5,y+204);
    });
  } else if(data.before) {
    const before=paint(data.before,layer==='regions',false),after=paint(first,layer==='regions',true,categoricalColors);
    ctx.drawImage(before,0,0,before.width/2,before.height,0,0,320,640);
    ctx.drawImage(after,after.width/2,0,after.width/2,after.height,320,0,320,640);
    ctx.fillStyle='#e6efcc';ctx.fillRect(319,0,2,640);
    ctx.fillStyle='#10251de8';ctx.fillRect(8,8,180,28);ctx.fillRect(328,8,180,28);
    ctx.fillStyle='#e3eccd';ctx.font='14px Consolas';ctx.fillText('INPUT / BEFORE',18,27);ctx.fillText('OUTPUT / AFTER',338,27);
  } else {ctx.drawImage(paint(first,layer==='regions',true,categoricalColors),0,0,640,640);if(!first.texture)markers(ctx,first,0,0,640);}
  const isField=first.meta[1]===1,stats=regions(first.cells);
  let changed=0;if(data.before) first.cells.forEach((v,i)=>{changed+=v!==data.before.cells[i];});
  const min=Math.min(...first.cells),max=Math.max(...first.cells);
  const items=[
    [isField?'Value range':'Floor coverage',isField?`${min}—${max}`:`${(first.meta[5]/4096*100).toFixed(1)}%`,''],
    [isField?'Output':'Floor regions',isField?'Field':String(stats.count),!isField?`${stats.largest} largest`:'0—255'],
    ['Live buffers',`${first.meta[2]} / 6`,`${first.meta[2]*4} KiB grids`],
    [data.before?'Changed cells':'Browser generation',data.before?String(changed):data.ms.toFixed(1),data.before?'of 4096':'ms']
  ];
  if(first.meta[1]===3){items[0]=['Material IDs',String(new Set(first.cells).size),'distinct'];items[1]=['ID range',`${min}—${max}`,''];}
  if(first.spawns){items[0]=['Spawn locations',String(first.spawns.length/2),first.requestedSpawns==null?'legacy':`/ ${first.requestedSpawns} requested`];items[1]=['Decoration patches',String(first.patches??0),'cosmetic'];}
  $('metrics').replaceChildren(...items.map(([name,value,unit])=>{
    const metric=element('div','metric');metric.append(element('span','',name));
    const strong=element('strong','',value);strong.append(element('small','',unit));metric.append(strong);return metric;
  }));
  const fallback=data.outputs.filter(o=>o.meta[3]).length;
  let text=`Signature ${first.meta[4].toString(16).padStart(8,'0')} · seed ${first.seed}.`;
  if(fallback) text+=` Fallback clearing used${grid?` in ${fallback} of 9 seeds`:''}.`;
  else if(first.meta[1]===2) text+=' Connected floor; spawn and outposts placed.';
  if(layer==='collision' && first.meta[1]!==2) text+=' Refined collision is available on Playable world outputs.';
  if($('view').value==='compare' && !data.before) text+=' This source node has no input to compare.';
  if(layer==='textures' && first.meta[1]!==2)text+=' Select a Playable world output for the textured map.';
  const unknown=[...new Set(data.outputs.flatMap(o=>o.unknown??[]))];
  if(first.requestedSpawns!=null && first.spawns.length/2<first.requestedSpawns)text+=` Placed ${first.spawns.length/2}/${first.requestedSpawns} spawns: floor, probability field or spacing limits available anchors.`;
  if(unknown.length)text+=` Unassigned material IDs: ${unknown.join(', ')}. IDs are preserved; game art and grip fall back to sand.`;
  try {const valid=compile(recipe,schema);if(valid.kind!=='world')text+=' Choose a Playable world output to export.';}catch(error){text+=` Export unavailable: ${error.message}`;}
  message(text,fallback||unknown.length?'warning':'');
}

function renderMapOptions(){
  const options=library.maps.map(entry=>{
    const option=element('option','',`${entry.recipe.name}${entry.includeInGame?'':' · DRAFT'}`);option.value=entry.id;return option;
  });
  if(currentId===null){const option=element('option','','NEW MAP · UNSAVED');option.value='';options.push(option);}
  $('preset').replaceChildren(...options);$('preset').value=currentId??'';
}
function updateMapControls(){
  renderMapOptions();
  $('save-map').disabled=!dirty;
  $('save-map').textContent=dirty?'Save *':'Save';
  $('delete-map').disabled=currentId===null||library.maps.length<=1;
  $('recipe-status').classList.toggle('dirty',dirty);
}
function resetEditorState(){
  selected=recipe.output??recipe.nodes[0]?.id??null;pending=null;pinnedSettings=null;lutPointSelection=null;
  undo=[];redo=[];iteration=null;panX=panY=0;zoom=1;$('view').value='final';
  $('undo').disabled=true;$('redo').disabled=true;
}
function discardAllowed(){return !dirty||window.confirm('Discard unsaved changes to this map?');}
function loadMap(id){
  const entry=library.maps.find(entry=>entry.id===id);if(!entry)return;
  currentId=id;currentEntry=entry;recipe=clone(entry.recipe);includeInGame=entry.includeInGame;dirty=false;
  localStorage.setItem('dustline.map-selection.v1',id);localStorage.setItem('dustline.recipe.v1',JSON.stringify(recipe));localStorage.removeItem('dustline.map-draft.v1');
  resetEditorState();render();message(`Loaded ${recipe.name}.`);
}
function slug(name){
  const base=name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40)||'map';
  let id=base,suffix=2;while(library.maps.some(entry=>entry.id===id))id=`${base.slice(0,43-String(suffix).length)}-${suffix++}`;return id;
}
async function writeLibrary(next,nextId,success){
  try{
    const response=await fetch('/api/library',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:libraryRevision,library:next})});
    const result=await response.json();if(!response.ok)throw new Error(result.error||`Save failed (${response.status}).`);
    library=result.library;libraryRevision=result.revision;currentId=nextId;currentEntry=library.maps.find(entry=>entry.id===currentId);
    recipe=clone(currentEntry.recipe);includeInGame=currentEntry.includeInGame;dirty=false;
    localStorage.setItem('dustline.map-selection.v1',currentId);localStorage.setItem('dustline.recipe.v1',JSON.stringify(recipe));localStorage.removeItem('dustline.map-draft.v1');
    resetEditorState();render();message(success);
  }catch(error){message(error.message,'error');updateMapControls();}
}
async function saveMap(asCopy=false){
  let name=String(recipe.name??'').trim();
  if(asCopy){name=window.prompt('Name for the copied map',`${name||'Untitled map'} copy`)?.trim();if(!name)return;}
  recipe.name=name;
  if(includeInGame){
    try{const result=compile(recipe,schema);if(result.kind!=='world')throw new Error('Choose a Playable world output.');
      for(const key of ['materialOutput','spawnOutput','decorationOutput'])if(recipe[key]!=null)compile(recipe,schema,recipe[key]);
    }catch(error){message(`Cannot include this map in the game: ${error.message}`,'error');return;}
  }
  const next=clone(library);let id=currentId;
  if(asCopy||id===null){id=slug(name);next.maps.push({id,includeInGame,recipe:clone(recipe)});}
  else {const index=next.maps.findIndex(entry=>entry.id===id);next.maps[index]={id,includeInGame,recipe:clone(recipe)};}
  await writeLibrary(next,id,`${name} saved to maps/map-library.json.`);
}
$('preset').onchange=()=>{const id=$('preset').value;if(discardAllowed())loadMap(id);else $('preset').value=currentId??'';};
$('new-map').onclick=()=>{
  if(!discardAllowed())return;
  const name=window.prompt('Name for the new map','Untitled map')?.trim();if(!name)return;
  currentId=null;recipe={version:3,name,seed:crypto.getRandomValues(new Uint32Array(1))[0],nodes:[]};includeInGame=false;dirty=true;
  resetEditorState();save();render();message('New draft. Add nodes, then Save to add it to the shared library.');
};
$('save-map').onclick=()=>saveMap(false);$('save-as').onclick=()=>saveMap(true);
$('include-in-game').onchange=()=>{includeInGame=$('include-in-game').checked;save();message(includeInGame?'This map will appear in the next ROM build.':'Saved as an editor draft; it will not appear in the ROM.');};
$('delete-map').onclick=async()=>{
  if(currentId===null||!window.confirm(`Delete ${recipe.name} from the shared map library?`))return;
  const index=library.maps.findIndex(entry=>entry.id===currentId),next=clone(library);next.maps.splice(index,1);
  const replacement=next.maps[Math.min(index,next.maps.length-1)].id;
  await writeLibrary(next,replacement,`${recipe.name} deleted from the shared library.`);
};
document.querySelector('.section-label span').textContent=schema.operations.length;
materialCatalog.forEach(m=>{const option=element('option','',m.name);option.value=m.id;$('material-ids').append(option);});
schema.operations.forEach(op=>{
  const button=element('button',op.kind);button.append(element('span','',op.kind==='field'?'≈':op.id==='world'?'↗':'+'),document.createTextNode(op.name));
  button.onclick=()=>{
    if(recipe.nodes.length>=32){message('This recipe already has 32 nodes.','error');return;}
    change(()=>{
      const id=Math.max(0,...recipe.nodes.map(n=>n.id))+1,n=makeNode(schema,op.id,id,35+recipe.nodes.length%3*220,45+Math.floor(recipe.nodes.length/3)*190);
      for(const [port,expected] of Object.entries(op.inputs)) {
        if(expected.endsWith('?'))continue;
        const matches=recipe.nodes.filter(s=>ops.get(s.type).kind===expected);
        const source=matches.find(s=>s.id===selected)??matches.at(-1);if(source)n.inputs[port]=source.id;
      }
      recipe.nodes.push(n);selected=id;$('view').value='selected';
      if(op.kind==='world')recipe.output=id;
      if(op.id==='materials'){recipe.version=Math.max(2,recipe.version);recipe.materialOutput=id;}
      if(op.id==='spawns'){recipe.version=3;recipe.spawnOutput=id;}
      if(op.id==='decoration'){recipe.version=3;recipe.decorationOutput=id;}
    });
    const added=recipe.nodes.at(-1);panX=$('graph').clientWidth/2-((Number(added.x)||0)+95)*zoom;panY=$('graph').clientHeight/2-((Number(added.y)||0)+70)*zoom;renderGraph();
  };
  $('library').append(button);
});
$('undo').onclick=()=>restore(undo,redo);$('redo').onclick=()=>restore(redo,undo);
$('arrange').onclick=()=>{change(arrange);fitGraph();};
function setZoom(value,anchorX=$('graph').clientWidth/2,anchorY=$('graph').clientHeight/2){
  const next=Math.max(.25,Math.min(1.5,value));if(next===zoom)return;
  const worldX=(anchorX-panX)/zoom,worldY=(anchorY-panY)/zoom;
  panX=anchorX-worldX*next;panY=anchorY-worldY*next;zoom=next;renderGraph();
}
$('zoom-in').onclick=()=>setZoom(zoom+.1);$('zoom-out').onclick=()=>setZoom(zoom-.1);
function fitGraph(){
  if(!recipe.nodes.length){zoom=1;panX=panY=0;renderGraph();return;}
  const minX=Math.min(...recipe.nodes.map(n=>Number(n.x)||0)),minY=Math.min(...recipe.nodes.map(n=>Number(n.y)||0));
  const maxX=Math.max(...recipe.nodes.map(n=>(Number(n.x)||0)+230)),maxY=Math.max(...recipe.nodes.map(n=>(Number(n.y)||0)+210));
  const width=maxX-minX,height=maxY-minY,padding=16;
  zoom=Math.max(.25,Math.min(1,($('graph').clientWidth-padding*2)/width,($('graph').clientHeight-padding*2)/height));
  panX=($('graph').clientWidth-width*zoom)/2-minX*zoom;panY=($('graph').clientHeight-height*zoom)/2-minY*zoom;renderGraph();
}
$('fit-graph').onclick=fitGraph;
$('graph').addEventListener('wheel',event=>{
  event.preventDefault();const rect=$('graph').getBoundingClientRect();
  setZoom(zoom*(event.deltaY<0?1.1:1/1.1),event.clientX-rect.left,event.clientY-rect.top);
},{passive:false});
$('graph').addEventListener('pointerdown',event=>{
  if(event.button!==0||event.target.closest('.node'))return;
  event.preventDefault();const pointerId=event.pointerId,startX=event.clientX,startY=event.clientY,originX=panX,originY=panY;
  $('graph').classList.add('panning');
  const move=e=>{if(e.pointerId!==pointerId)return;panX=originX+e.clientX-startX;panY=originY+e.clientY-startY;applyGraphView();};
  const end=e=>{if(e.pointerId!==pointerId)return;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',end);$('graph').classList.remove('panning');};
  window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);window.addEventListener('pointercancel',end);
});
$('recipe-name').onchange=()=>change(()=>{recipe.name=$('recipe-name').value.trim();},false);
$('seed').onchange=()=>{const input=$('seed');if(!input.validity.valid||input.value===''){input.value=recipe.seed;return;}change(()=>{recipe.seed=Number(input.value);},false);};
$('random-seed').onclick=()=>change(()=>{recipe.seed=crypto.getRandomValues(new Uint32Array(1))[0];});
$('view').onchange=schedule;$('layer').onchange=schedule;$('show-spawns').onchange=schedule;
$('pin-settings').onclick=()=>{pinnedSettings=pinnedSettings===null?selected:null;iteration=null;renderGraph();renderInspector();schedule();};
$('duplicate').onclick=()=>change(()=>{
  const n=clone(recipe.nodes.find(n=>n.id===settingsNodeId()));n.id=Math.max(...recipe.nodes.map(n=>n.id))+1;n.label+=' copy';n.x+=30;n.y+=160;
  if(ops.get(n.type).random)n.stream=n.id;recipe.nodes.push(n);
  if(pinnedSettings!==null)pinnedSettings=n.id;else {selected=n.id;$('view').value='selected';}
});
$('delete').onclick=()=>change(()=>{
  const removed=settingsNodeId();
  recipe.nodes=recipe.nodes.filter(n=>n.id!==removed);
  for(const n of recipe.nodes)for(const port of Object.keys(n.inputs))if(n.inputs[port]===removed)delete n.inputs[port];
  if(recipe.output===removed)recipe.output=recipe.nodes.findLast(n=>['world','roads'].includes(n.type))?.id??recipe.nodes.at(-1).id;
  if(recipe.materialOutput===removed){delete recipe.materialOutput;if(recipe.version<3)recipe.version=1;}
  for(const key of ['spawnOutput','decorationOutput'])if(recipe[key]===removed)delete recipe[key];
  if(selected===removed)selected=recipe.output;
  pending=null;
});
$('set-output').onclick=()=>change(()=>{const type=recipe.nodes.find(n=>n.id===selected).type;
  if(type==='materials'){recipe.materialOutput=selected;recipe.version=Math.max(2,recipe.version);}
  else if(type==='spawns'){recipe.spawnOutput=selected;recipe.version=3;}
  else if(type==='decoration'){recipe.decorationOutput=selected;recipe.version=3;}
  else recipe.output=selected;$('view').value='final';});
function download(blob,name){const url=URL.createObjectURL(blob),a=element('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export').onclick=()=>{
  try{const compiled=compile(recipe,schema);if(compiled.kind!=='world')throw new Error('Select a Playable world output.');
    for(const key of ['materialOutput','spawnOutput','decorationOutput'])if(recipe[key]!=null)compile(recipe,schema,recipe[key]);
    download(new Blob([JSON.stringify(recipe,null,2)+'\n'],{type:'application/json'}),`${currentId??slug(recipe.name)}.json`);
    message('Standalone recipe exported for backup or sharing. Save writes directly to the shared map library.');
  }catch(error){message(error.message,'error');}
};
$('import').onclick=()=>$('import-file').click();
$('import-file').onchange=async()=>{
  const file=$('import-file').files[0];if(!file)return;
  try{
    if(file.size>256*1024)throw new Error('Recipe file is too large (limit 256 KiB).');
    const imported=JSON.parse(await file.text());compile(imported,schema);
    for(const n of imported.nodes){n.x=Math.max(0,Math.min(10000,Number(n.x)||0));n.y=Math.max(0,Math.min(10000,Number(n.y)||0));n.inputs??={};n.label=String(n.label??ops.get(n.type).name).slice(0,80);}
    if(!discardAllowed())return;
    currentId=null;recipe=imported;includeInGame=false;dirty=true;resetEditorState();save();render();
    message('Imported as a new draft. Use Save to add it to the shared library.');
  }catch(error){message(`Import failed: ${error.message}`,'error');}
  $('import-file').value='';
};
$('download-png').onclick=()=>$('preview').toBlob(blob=>download(blob,`dustline-${recipe.seed}.png`));
$('render-map').onclick=()=>{
  try {
    const previewRecipe=clone(recipe),iterationNode=previewRecipe.nodes.find(n=>n.id===settingsNodeId());
    if(iteration!==null && iterationNode?.type==='cellular')iterationNode.p[0]=iteration;
    const world=compile(previewRecipe,schema),materialProgram=recipe.materialOutput==null?null:compile(previewRecipe,schema,recipe.materialOutput).program;
    if(world.kind!=='world')throw new Error('Choose a Playable world output.');
    renderRequest++;renderBusy=true;renderBlob=null;$('save-render').disabled=true;$('render-map').disabled=true;
    $('render-image').removeAttribute('src');$('render-status').textContent='Rendering full map…';$('render-dialog').showModal();
    const spawnProgram=recipe.spawnOutput==null?null:compile(previewRecipe,schema,recipe.spawnOutput).program;
    const decorationProgram=recipe.decorationOutput==null?null:compile(previewRecipe,schema,recipe.decorationOutput).program;
    worker.postMessage({id:renderRequest,render:true,program:world.program,materialProgram,spawnProgram,decorationProgram,showSpawns:$('show-spawns').checked,seed:recipe.seed});
  }catch(error){message(error.message,'error');}
};
$('close-render').onclick=()=>$('render-dialog').close();
$('save-render').onclick=()=>{if(renderBlob)download(renderBlob,`dustline-world-${renderSeed}-8192.png`);};
$('render-zoom').onchange=()=>{$('render-image').style.width=$('render-zoom').value==='fit'?'':`${8192*Number($('render-zoom').value)}px`;$('render-image').classList.toggle('actual-size',$('render-zoom').value!=='fit');};
$('preview').onclick=event=>{
  if($('view').value!=='seeds'||!lastResponse)return;
  const rect=$('preview').getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width,y=(event.clientY-rect.top)/rect.height;
  const output=lastResponse.outputs[Math.min(2,Math.floor(y*3))*3+Math.min(2,Math.floor(x*3))];
  if(output)change(()=>{recipe.seed=output.seed;$('view').value='final';});
};
$('help').onclick=()=>$('guide').showModal();$('close-guide').onclick=()=>$('guide').close();
window.addEventListener('keydown',event=>{
  if(event.key==='Escape'){if(cancelConnectionDrag)cancelConnectionDrag();else {pending=null;renderGraph();}}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?restore(redo,undo):restore(undo,redo);}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();saveMap(false);}
});
localStorage.setItem('dustline.recipe.v1',JSON.stringify(recipe));render();
