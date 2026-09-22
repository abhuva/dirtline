// DOM integration check. Install test dependency: npm install --prefix build/map-editor-ui --no-save --package-lock=false jsdom@26.1.0
import {JSDOM} from '../build/map-editor-ui/node_modules/jsdom/lib/api.js';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {compile,makeNode,presets} from './map_editor/recipe.mjs';
const read = path => readFile(new URL('../'+path,import.meta.url),'utf8');
const art=JSON.parse(await read('tools/map_editor/generated/art.json'));
const schema=JSON.parse(await read('tools/map_editor/schema.json'));
const original=JSON.parse(await read('maps/recipes/wasteland.json'));
const dom=new JSDOM(await read('tools/map_editor/index.html'),{url:'http://localhost:8765',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
// jsdom has no native PointerEvent handler properties; bridge to its event dispatcher.
Object.defineProperty(w.HTMLElement.prototype,'onpointerdown',{set(fn){if(this._pointerDown)this.removeEventListener('pointerdown',this._pointerDown);this._pointerDown=fn;this.addEventListener('pointerdown',fn);},get(){return this._pointerDown;}});
Object.assign(w,{structuredClone,compile,makeNode,presets,Worker:class {constructor(){w.testWorker=this;}postMessage(data){w.lastProgram=data;}},fetch:async url=>({json:async()=>structuredClone(String(url).includes('schema')?schema:String(url).includes('art.json')?art:original)})});
w.HTMLElement.prototype.scrollTo=()=>{};
w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
w.HTMLAnchorElement.prototype.click=function(){};
w.Blob=Blob;w.URL.createObjectURL=blob=>{w.lastBlob=blob;return 'blob:test';};w.URL.revokeObjectURL=()=>{};
w.document.addEventListener('click',e=>{if(e.target.tagName==='A')e.preventDefault();});
w.HTMLCanvasElement.prototype.getContext=()=>({fillRect(){},drawImage(){},fillText(){},strokeRect(){},beginPath(){},arc(){},fill(){},stroke(){},putImageData(){},createImageData:(width,height)=>({data:new Uint8ClampedArray(width*height*4)})});
await w.eval('(async()=>{'+(await read('tools/map_editor/app.mjs')).replace(/^import .*;\r?\n/,'')+'})()');
const $=id=>w.document.getElementById(id);
const node=id=>JSON.parse(w.localStorage.getItem('dustline.recipe.v1')).nodes.find(n=>n.id===id);
const port=(id,input)=>w.document.querySelector(`.port[data-node-id="${id}"]${input?`[data-port="${input}"]`:'.out'}`);
const click=e=>{assert.ok(e);e.click();};
const key=(key,extra={})=>w.dispatchEvent(new w.KeyboardEvent('keydown',{key,bubbles:true,...extra}));


const wait=()=>new Promise(resolve=>setTimeout(resolve,100));
const select=id=>w.document.querySelector(`.node[data-node-id="${id}"] .node-heading`).dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
const edit=(name,value)=>{const input=w.document.querySelector(`[aria-label="${name}"]`);assert.ok(input,name);input.value=String(value);input.dispatchEvent(new w.Event('change'));};
w.testWorker.onmessage({data:{ready:true}});
$('preset').value='4';$('preset').dispatchEvent(new w.Event('change'));await wait();
let recipe=JSON.parse(w.localStorage.getItem('dustline.recipe.v1'));
assert.equal(recipe.version,2);assert.equal(recipe.materialOutput,6);assert.equal(recipe.output,3);
assert.equal(w.lastProgram.textures,true);assert.equal(w.lastProgram.materialProgram.at(-1)[0],15);
select(5);click($('pin-settings'));select(3);edit('Low material',255);await wait();
assert.equal(Number(w.document.querySelector('.node.selected').dataset.nodeId),3);
assert.equal(w.lastProgram.materialProgram[1][8],255);
// Both roots and categorical IDs survive JSON export/import.
click($('export'));const exported=JSON.parse(await w.lastBlob.text());assert.equal(exported.materialOutput,6);assert.equal(exported.nodes.find(n=>n.id===5).p[3],255);
Object.defineProperty($('import-file'),'files',{configurable:true,value:[{size:1000,text:async()=>JSON.stringify(exported)}]});
await $('import-file').onchange();await wait();assert.equal(w.lastProgram.materialProgram[1][8],255);
// Render action sends both outputs and displays its asynchronous full-resolution result.
click($('render-map'));assert.equal(w.lastProgram.render,true);assert.equal(w.lastProgram.materialProgram.at(-1)[0],15);assert.ok($('render-dialog').open);
w.testWorker.onmessage({data:{render:true,id:w.lastProgram.id,blob:new Blob(['png']),seed:exported.seed}});
assert.equal($('save-render').disabled,false);assert.match($('render-status').textContent,/8192/);
$('render-zoom').value='1';$('render-zoom').dispatchEvent(new w.Event('change'));assert.equal($('render-image').style.width,'8192px');click($('close-render'));
// Simulate a generated material result, including reserved-ID warning/legend.
select(6);await wait();
w.testWorker.onmessage({data:{id:w.lastProgram.id,ms:1,outputs:[{meta:new Uint32Array([0,3,2,0,123,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]),cells:new Uint8Array(4096).fill(255),seed:42,unknown:[255]}]}});
assert.match($('notice').textContent,/Unassigned material IDs: 255/);assert.match($('legend').textContent,/Sand.*Gravel/);
// Deleting the material root restores the explicit legacy fallback and undo restores both roots.
click($('delete'));recipe=JSON.parse(w.localStorage.getItem('dustline.recipe.v1'));assert.equal(recipe.version,1);assert.equal(recipe.materialOutput,undefined);
click($('undo'));recipe=JSON.parse(w.localStorage.getItem('dustline.recipe.v1'));assert.equal(recipe.version,2);assert.equal(recipe.materialOutput,6);
// Changing outputs never replaces the wall/floor root with a material root.
select(6);click($('set-output'));recipe=JSON.parse(w.localStorage.getItem('dustline.recipe.v1'));assert.equal(recipe.output,3);assert.equal(recipe.materialOutput,6);
console.log('PASS material editor DOM: independent roots, pinned edits, JSON roundtrip, full-render request/zoom, warnings/legend, deletion/undo.');
$('preset').value='5';$('preset').dispatchEvent(new w.Event('change'));await wait();
recipe=JSON.parse(w.localStorage.getItem('dustline.recipe.v1'));
assert.equal(recipe.nodes.find(n=>n.id===recipe.output).type,'roads');
assert.equal(w.lastProgram.program.at(-1)[0],17);assert.equal(w.lastProgram.materialProgram.at(-1)[0],15);
edit('Road width (pixels)',256);edit('Road material',1);await wait();
assert.deepEqual(Array.from(w.lastProgram.program.at(-1).slice(5,8)),[256,1,0]);
select(3);click($('set-output'));await wait();assert.equal(w.lastProgram.program.at(-1)[0],11);
select(7);click($('set-output'));await wait();assert.equal(w.lastProgram.program.at(-1)[0],17);
click($('render-map'));assert.equal(w.lastProgram.render,true);assert.equal(w.lastProgram.program.at(-1)[0],17);
click($('close-render'));click($('export'));const roadExport=JSON.parse(await w.lastBlob.text());
assert.equal(roadExport.output,7);assert.equal(roadExport.materialOutput,6);
// Retired min/max exports import as one width, rounded to an 8px tile.
const oldRoads=structuredClone(roadExport);oldRoads.nodes.find(n=>n.type==='roads').p=[153,1,170];
Object.defineProperty($('import-file'),'files',{configurable:true,value:[{size:1000,text:async()=>JSON.stringify(oldRoads)}]});
await $('import-file').onchange();await wait();
assert.deepEqual(Array.from(w.lastProgram.program.at(-1).slice(5,8)),[160,1,0]);
assert.equal(w.document.querySelector('[aria-label="Road width (pixels)"]').value,'160');
assert.equal(w.document.querySelector('[aria-label="Maximum width (pixels)"]'),null);
console.log('PASS road editor DOM: preset, width/material edits, output switching, full render and JSON export.');
$('preset').value='6';$('preset').dispatchEvent(new w.Event('change'));await wait();
recipe=JSON.parse(w.localStorage.getItem('dustline.recipe.v1'));
assert.equal(recipe.version,3);assert.equal(w.lastProgram.spawnProgram.at(-1)[0],18);assert.equal(w.lastProgram.decorationProgram.at(-1)[0],19);
select(recipe.spawnOutput);edit('Target count',24);await wait();
assert.equal(w.lastProgram.program.at(-1)[0],17);assert.equal(w.lastProgram.spawnProgram.at(-1)[5],24);
click($('pin-settings'));select(recipe.output);edit('Minimum spacing (pixels)',384);await wait();
assert.equal(w.lastProgram.spawnProgram.at(-1)[6],384);click($('pin-settings'));
select(recipe.decorationOutput);edit('Density %',80);edit('Dry grass weight',0);await wait();
assert.equal(w.lastProgram.decorationProgram.at(-1)[5],80);assert.equal(w.lastProgram.decorationProgram.at(-1)[6],0);
$('show-spawns').checked=false;$('show-spawns').dispatchEvent(new w.Event('change'));await wait();assert.equal(w.lastProgram.showSpawns,false);
click($('export'));const populated=JSON.parse(await w.lastBlob.text());assert.ok(populated.spawnOutput && populated.decorationOutput);
click($('set-output'));assert.equal(JSON.parse(w.localStorage.getItem('dustline.recipe.v1')).output,populated.output);
click($('delete'));await wait();assert.equal(JSON.parse(w.localStorage.getItem('dustline.recipe.v1')).decorationOutput,undefined);
click($('undo'));await wait();assert.equal(w.lastProgram.decorationProgram.at(-1)[5],80);
console.log('PASS placement editor DOM: independent outputs, pinned spawn controls, density/type weights, marker toggle, export and deletion/undo.');
dom.window.close();
