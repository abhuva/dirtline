// DOM integration check. Uses the same optional jsdom install as test_map_editor_ui.mjs.
import {JSDOM} from '../build/map-editor-ui/node_modules/jsdom/lib/api.js';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';

const read=path=>readFile(new URL('../'+path,import.meta.url),'utf8');
let source=JSON.parse(await read('music/dustline-drive.json')),revision='test-revision',saved=null;
const dom=new JSDOM(await read('tools/map_editor/music.html'),{url:'http://127.0.0.1:8765/music.html',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
class Parameter {setValueAtTime(){} exponentialRampToValueAtTime(){}}
class AudioNode {constructor(){this.frequency=new Parameter();this.gain=new Parameter();}connect(){return this;}start(){}stop(){}}
class AudioContext {
  constructor(){this.sampleRate=16000;this.currentTime=0;this.destination=new AudioNode();}
  resume(){return Promise.resolve();}createOscillator(){return new AudioNode();}createGain(){return new AudioNode();}
  createBiquadFilter(){const node=new AudioNode();node.type='';return node;}
  createBuffer(_channels,length){const data=new Float32Array(length);return {getChannelData:()=>data};}
  createBufferSource(){const node=new AudioNode();node.buffer=null;return node;}
}
Object.assign(w,{AudioContext,structuredClone,fetch:async(_url,options={})=>{
  if(options.method==='PUT'){
    const request=JSON.parse(options.body);assert.equal(request.revision,revision);saved=request.music;revision+='x';source=structuredClone(saved);
    return {ok:true,status:200,json:async()=>({revision,music:structuredClone(source),preview:'/generated/music-preview.wav'})};
  }
  return {ok:true,status:200,json:async()=>({revision,music:structuredClone(source),preview:'/generated/music-preview.wav'})};
}});
w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};
await w.eval('(async()=>{'+await read('tools/map_editor/music.mjs')+'})()');
await new Promise(resolve=>setTimeout(resolve,20));
const $=id=>w.document.getElementById(id);
assert.equal(w.document.querySelectorAll('#sections button').length,4);
assert.equal(w.document.querySelectorAll('.track-row').length,8);
assert.equal(w.document.querySelectorAll('.step').length,128);
assert.equal(w.document.querySelectorAll('.volume').length,8);
assert.equal($('title').value,'Dustline Horizon');
const bassStep=w.document.querySelector('.step[data-track="3"][data-step="1"]');
assert.equal(bassStep.classList.contains('on'),false);bassStep.click();assert.equal(w.document.querySelector('.step[data-track="3"][data-step="1"]').classList.contains('on'),true);
w.document.querySelector('[data-section="combat"]').click();assert.equal(w.document.querySelector('[data-section="combat"]').classList.contains('active'),true);
await $('play').onclick();assert.match($('now').textContent,new RegExp(source.sections.combat.label.toUpperCase()));$('stop').click();assert.equal($('now').textContent,'Stopped');
$('bpm').value='132';$('bpm').dispatchEvent(new w.Event('input'));await $('save').onclick();
assert.equal(saved.bpm,132);assert.match($('status').textContent,/Saved/);
console.log('PASS music workshop DOM: settings, 8x16 composer, section switching, preview transport and repository save.');
dom.window.close();
