import createEngine from './generated/engine.mjs';
import {renderOverview,renderFullPng} from './render.mjs';
const engine = await createEngine();
const art = await fetch('./generated/art.json').then(r=>{if(!r.ok)throw new Error('Run ./build.ps1 to generate terrain art.');return r.json();});
const registered=new Set(art.catalog.materials.map(m=>m.id));
const messages = ['OK','Invalid node count','Unknown operation','Invalid input','Wrong port type','Invalid parameter','GBA buffer budget exceeded'];
function execute(program,seed){
  engine.HEAPU32.set(new Uint32Array(program.flat()),engine._recipe_input()>>>2);
  const status=engine._recipe_run(program.length,seed>>>0);
  if(status)throw new Error(messages[status]??`Engine error ${status}`);
}
function run(program, seed, {collision=false,textures=false,materialProgram=null,spawnProgram=null,decorationProgram=null,showSpawns=true,full=false,small=false}={}) {
  execute(program,seed);
  const meta = engine.HEAPU32.slice(engine._recipe_meta() >>> 2, (engine._recipe_meta() >>> 2) + 20);
  const cells = engine.HEAPU8.slice(engine._recipe_cells(), engine._recipe_cells() + 4096);
  let refined=null,texture=null,ground=null,tileMap=null,decorations=null,spawns=null,patches=0;
  if(meta[1]===2){
    if(materialProgram){execute(materialProgram,seed);if(engine._recipe_apply_materials())throw new Error('Ground output must contain material IDs.');}
    if(spawnProgram){execute(spawnProgram,seed);if(engine._recipe_apply_spawns())throw new Error('Choose an Enemy spawns output.');}
    if(decorationProgram){execute(decorationProgram,seed);if(engine._recipe_apply_decoration())throw new Error('Choose a Decoration output.');}
    const count=engine._recipe_spawn_count(),points=engine._recipe_spawns()>>>1;
    spawns=engine.HEAPU16.slice(points,points+count*2);
    if(decorationProgram){const ptr=engine._recipe_decorations();decorations=engine.HEAPU8.slice(ptr,ptr+1024*1024);patches=decorations.reduce((n,v)=>n+(v>0 && (v-1)%4===0),0);}
    const ptr=engine._recipe_ground();ground=engine.HEAPU8.slice(ptr,ptr+4096);
    if(collision){const ptr=engine._recipe_collision();refined=engine.HEAPU8.slice(ptr,ptr+1024*1024);}
    if(textures || full){
      const ptr=engine._recipe_tiles()>>>1;tileMap=engine.HEAPU16.slice(ptr,ptr+1024*1024);
      if(textures)texture=renderOverview(tileMap,art,small?8:4,decorations,showSpawns?spawns:null);
    }
  }
  const unknown=[...new Set(meta[1]===3?cells:ground??[])].filter(id=>!registered.has(id));
  return {meta,cells,refined,texture,ground,unknown,seed,spawns,patches,requestedSpawns:spawnProgram?.at(-1)[5],decorations:full?decorations:null,tileMap:full?tileMap:null};
}
self.onmessage = async ({data}) => {
  const {id,program,seed,collision,textures,seeds,compare,materialProgram,spawnProgram,decorationProgram,histogramProgram,histogramNode,categorical,categoricalColors,showSpawns,render} = data;
  const options={materialProgram,spawnProgram,decorationProgram,showSpawns};
  try {
    if(render){
      const output=run(program,seed,{...options,full:true});
      if(!output.tileMap)throw new Error('Choose a Playable world to render.');
      const blob=await renderFullPng(output.tileMap,art,progress=>self.postMessage({id,render:true,progress}),output.decorations,showSpawns?output.spawns:null);
      self.postMessage({id,render:true,blob,seed});return;
    }
    const start = performance.now();
    const outputs = (seeds ?? [seed]).map(s => run(program,s,{...options,collision,textures,small:!!seeds}));
    const before = compare ? run(compare,seed,{...options,textures}) : null;
    let histogram=null;
    if(histogramProgram){execute(histogramProgram,seed);histogram=new Uint16Array(256);for(const value of engine.HEAPU8.slice(engine._recipe_cells(),engine._recipe_cells()+4096))++histogram[value];}
    const response={id,outputs,before,histogram,histogramNode,categorical,categoricalColors,ms:performance.now()-start};
    const transfer=outputs.flatMap(o=>[o.cells.buffer,...[o.refined,o.ground,o.texture?.pixels].filter(Boolean).map(a=>a.buffer)]);
    if(histogram)transfer.push(histogram.buffer);
    self.postMessage(response,transfer);
  } catch (error) { self.postMessage({id,render:!!render,error:error.message}); }
};
self.postMessage({ready:true});
