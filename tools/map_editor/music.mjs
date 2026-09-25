const $=id=>document.getElementById(id);
const sectionIds=['cruise','drive','danger','combat'];
const scales={minor_pentatonic:[0,3,5,7,10],natural_minor:[0,2,3,5,7,8,10],dorian:[0,2,3,5,7,9,10]};
const names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
let music,revision,currentSection='cruise',pendingSection=null,audioContext,timer=null,step=0;
const clone=value=>JSON.parse(JSON.stringify(value));

async function requestJson(url,options={}){
  const response=await fetch(url,options);let result;
  try{result=await response.json();}
  catch{
    throw new Error('The running workshop server is outdated. Stop it, run ./map-editor.ps1 -NoBuild again, then reload this page.');
  }
  if(!response.ok)throw new Error(result.error||`Workshop request failed (${response.status})`);
  return result;
}

function noteFor(track,value){
  const scale=scales[music.scale],octave=Math.floor(value/scale.length),index=((value%scale.length)+scale.length)%scale.length;
  return music.root+track.octave*12+octave*12+scale[index];
}
function noteName(note){return `${names[(note%12+12)%12]}${Math.floor(note/12)-1}`;}
function setStatus(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function bind(id,key,convert=value=>value){
  const input=$(id);input.value=music[key];input.oninput=()=>{music[key]=convert(input.value);if(key==='root'||key==='scale')renderGrid();if(key==='variation')$('variation-value').textContent=`${music.variation}%`;};
}
function renderSettings(){
  $('root').replaceChildren(...Array.from({length:25},(_,index)=>{const note=24+index,o=document.createElement('option');o.value=note;o.textContent=noteName(note);return o;}));
  bind('title','title');bind('bpm','bpm',Number);bind('seed','seed',Number);bind('root','root',Number);bind('scale','scale');bind('variation','variation',Number);
  $('variation-value').textContent=`${music.variation}%`;
  $('volumes').replaceChildren(...music.tracks.map(track=>{
    const row=document.createElement('div');row.className='volume';
    const label=document.createElement('span');label.textContent=track.label;
    const input=document.createElement('input');input.type='range';input.min=0;input.max=64;input.value=track.volume;input.setAttribute('aria-label',`${track.label} volume`);
    const value=document.createElement('output');value.textContent=track.volume;
    input.oninput=()=>{track.volume=Number(input.value);value.textContent=input.value;};row.append(label,input,value);return row;
  }));
}
function renderSections(){
  $('sections').replaceChildren(...sectionIds.map(id=>{const button=document.createElement('button');button.textContent=music.sections[id].label;button.dataset.section=id;
    button.classList.toggle('active',id===currentSection);button.classList.toggle('pending',id===pendingSection);
    button.onclick=()=>{if(timer&&step!==0){pendingSection=id;renderSections();}else{currentSection=id;pendingSection=null;step=0;renderSections();renderGrid();}};return button;}));
}
function renderGrid(){
  const patterns=music.sections[currentSection].patterns;
  $('grid').replaceChildren(...music.tracks.map((track,trackIndex)=>{
    const row=document.createElement('div');row.className='track-row';const label=document.createElement('div');label.className='track-label';label.textContent=`${trackIndex+1} · ${track.label}`;
    const steps=document.createElement('div');steps.className='steps';
    patterns[track.id].forEach((value,index)=>{const cell=document.createElement('button');cell.className='step';cell.dataset.step=index;cell.dataset.track=trackIndex;
      cell.classList.toggle('on',value!==null);cell.classList.toggle('current',timer!==null&&index===step);
      cell.textContent=value===null?'·':track.kind==='drum'?'×':noteName(noteFor(track,value));
      cell.onclick=()=>{const values=patterns[track.id];if(track.kind==='drum')values[index]=values[index]===null?1:null;else values[index]=values[index]===null?0:(values[index]+1)%(scales[music.scale].length*2);renderGrid();};
      cell.oncontextmenu=event=>{event.preventDefault();patterns[track.id][index]=null;renderGrid();};steps.append(cell);});row.append(label,steps);return row;
  }));
}
function noise(duration,volume,highpass=0){
  const length=Math.max(1,Math.floor(audioContext.sampleRate*duration)),buffer=audioContext.createBuffer(1,length,audioContext.sampleRate),data=buffer.getChannelData(0);
  for(let i=0;i<length;i++)data[i]=(Math.random()*2-1)*(1-i/length);const source=audioContext.createBufferSource();source.buffer=buffer;
  const gain=audioContext.createGain();gain.gain.value=volume;let node=source;if(highpass){const filter=audioContext.createBiquadFilter();filter.type='highpass';filter.frequency.value=highpass;source.connect(filter);node=filter;}node.connect(gain).connect(audioContext.destination);source.start();
}
function playVoice(trackIndex,value){
  const track=music.tracks[trackIndex],volume=track.volume/64*.16;if(track.kind==='drum'){
    if(track.id==='kick'){const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.frequency.setValueAtTime(95,audioContext.currentTime);oscillator.frequency.exponentialRampToValueAtTime(38,audioContext.currentTime+.16);gain.gain.setValueAtTime(volume*2,audioContext.currentTime);gain.gain.exponentialRampToValueAtTime(.001,audioContext.currentTime+.19);oscillator.connect(gain).connect(audioContext.destination);oscillator.start();oscillator.stop(audioContext.currentTime+.2);}
    else if(track.id==='hat')noise(.055,volume,3500);else if(track.id==='snare')noise(.13,volume,900);else noise(.1,volume,1800);return;
  }
  const note=noteFor(track,value),oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.type=track.id==='bass'||track.id==='lead'?'triangle':'sine';oscillator.frequency.value=440*2**((note-69)/12);
  const atmospheric=track.id==='chord'||track.id==='drive',duration=atmospheric?1.8:track.id==='lead'?.72:.3;
  if(atmospheric){gain.gain.setValueAtTime(.001,audioContext.currentTime);gain.gain.exponentialRampToValueAtTime(volume,audioContext.currentTime+.18);gain.gain.exponentialRampToValueAtTime(.001,audioContext.currentTime+duration);}
  else{gain.gain.setValueAtTime(volume,audioContext.currentTime);gain.gain.exponentialRampToValueAtTime(.001,audioContext.currentTime+duration);}
  oscillator.connect(gain).connect(audioContext.destination);oscillator.start();oscillator.stop(audioContext.currentTime+duration+.01);
}
function tick(){
  document.querySelectorAll('.step.current').forEach(cell=>cell.classList.remove('current'));document.querySelectorAll(`.step[data-step="${step}"]`).forEach(cell=>cell.classList.add('current'));
  const patterns=music.sections[currentSection].patterns;music.tracks.forEach((track,index)=>{const value=patterns[track.id][step];if(value!==null)playVoice(index,value);});
  $('now').textContent=`${music.sections[currentSection].label.toUpperCase()} · ${String(step+1).padStart(2,'0')}/16`;
  step=(step+1)%16;if(step===0&&pendingSection){currentSection=pendingSection;pendingSection=null;renderSections();renderGrid();}
}
async function play(){
  if(timer)return;audioContext??=new AudioContext();await audioContext.resume();step=0;timer=setInterval(tick,60000/music.bpm/4);tick();$('play').disabled=true;
}
function stop(){if(timer){clearInterval(timer);timer=null;}step=0;pendingSection=null;$('play').disabled=false;$('now').textContent='Stopped';if(music){renderSections();renderGrid();}}
async function save(){
  stop();$('save').disabled=true;setStatus('Generating MOD, section table and reference WAV…');
  try{const result=await requestJson('/api/music',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,music})});revision=result.revision;music=result.music;$('reference').src=`${result.preview}?revision=${revision}`;setStatus('Saved. Run ./build.ps1 to include this version in the ROM.');}
  catch(error){setStatus(error.message,true);}finally{$('save').disabled=false;}
}
function download(){const blob=new Blob([JSON.stringify(music,null,2)+'\n'],{type:'application/json'}),link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='dustline-drive.json';link.click();URL.revokeObjectURL(link.href);}
async function initialize(){
  try{const result=await requestJson('/api/music');music=clone(result.music);revision=result.revision;$('reference').src=`${result.preview}?revision=${revision}`;renderSettings();renderSections();renderGrid();
    $('beats').replaceChildren(...Array.from({length:16},(_,index)=>{const span=document.createElement('span');span.textContent=index%4===0?index/4+1:'·';return span;}));setStatus('Ready. Browser playback follows unsaved edits immediately.');}
  catch(error){setStatus(error.message,true);}
}
$('play').onclick=play;$('stop').onclick=stop;$('save').onclick=save;$('download').onclick=download;window.addEventListener('beforeunload',stop);initialize();
