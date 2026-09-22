import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {compile,makeNode} from './map_editor/recipe.mjs';
import {renderOverview,renderFullPng} from './map_editor/render.mjs';
import createEngine from './map_editor/generated/engine.mjs';
const root=new URL('../',import.meta.url),dir=new URL('build/placement-tests/',root);
await mkdir(dir,{recursive:true});
const schema=JSON.parse(await readFile(new URL('tools/map_editor/schema.json',root)));
const active=JSON.parse(await readFile(new URL('maps/wasteland.json',root)));
const art=JSON.parse(await readFile(new URL('tools/map_editor/generated/art.json',root)));
const engine=await createEngine();
function run(program,seed){engine.HEAPU32.set(new Uint32Array(program.flat()),engine._recipe_input()>>>2);assert.equal(engine._recipe_run(program.length,seed),0);}
const report=[];
for(const mode of ['active','masked','zero']) {
  const r=structuredClone(active);
  if(mode!=='active'){
    const id=Math.max(...r.nodes.map(n=>n.id))+1,field=makeNode(schema,mode==='zero'?'field_fill':'noise',id);
    if(mode==='zero')field.p=[0];
    r.nodes.push(field);r.nodes.find(n=>n.id===r.spawnOutput).inputs.a=id;r.nodes.find(n=>n.id===r.decorationOutput).inputs.a=id;
    r.nodes.find(n=>n.id===r.spawnOutput).p=[24,256,0];
  }
  const programs=[r.output,r.materialOutput,r.spawnOutput,r.decorationOutput].map(id=>compile(r,schema,id).program);
  for(let i=0;i<4;++i)await writeFile(new URL(`${mode}-${i}.program`,dir),new Uint32Array(programs[i].flat()));
  const args=['run','--rm','--mount',`type=bind,source=${process.cwd()},target=/work`,'dustline-build:1','./build/map_recipe_bridge',
    `build/placement-tests/${mode}-0.program`,String(r.seed),`build/placement-tests/${mode}.bin`,...Array.from({length:3},(_,i)=>`build/placement-tests/${mode}-${i+1}.program`)];
  execFileSync('docker',args,{stdio:'pipe'});
  const native=await readFile(new URL(`${mode}.bin`,dir));
  run(programs[0],r.seed);run(programs[1],r.seed);assert.equal(engine._recipe_apply_materials(),0);
  run(programs[2],r.seed);assert.equal(engine._recipe_apply_spawns(),0);
  run(programs[3],r.seed);assert.equal(engine._recipe_apply_decoration(),0);
  const dp=engine._recipe_decorations(),decoration=engine.HEAPU8.slice(dp,dp+1048576);
  const count=engine._recipe_spawn_count(),sp=engine._recipe_spawns()>>>1,spawns=engine.HEAPU16.slice(sp,sp+count*2);
  const offset=8272+1048576*2+4;
  assert.deepEqual(Buffer.from(decoration),native.subarray(offset,offset+1048576),`${mode} decoration tiles`);
  assert.equal(count,native.readUInt32LE(offset+1048576));
  assert.deepEqual(Buffer.from(spawns.buffer),native.subarray(offset+1048576+4),`${mode} spawn coordinates`);
  const patches=decoration.reduce((n,v)=>n+(v>0&&(v-1)%4===0),0);
  if(mode==='zero'){assert.equal(count,0);assert.equal(patches,0);}
  else {assert.ok(count>0);assert.ok(patches>100);if(mode==='masked')assert.equal(count,24);}
  if(mode==='active') {
    const tp=engine._recipe_tiles()>>>1,tiles=engine.HEAPU16.slice(tp,tp+1048576);
    const png=await renderFullPng(tiles,art,()=>{},decoration,null);
    await writeFile(new URL('artifacts/map_editor/populated-full-map.png',root),Buffer.from(await png.arrayBuffer()));
    const marked=await renderFullPng(tiles,art,()=>{},decoration,spawns);
    await writeFile(new URL('artifacts/map_editor/populated-spawns.png',root),Buffer.from(await marked.arrayBuffer()));
    const preview=renderOverview(tiles,art,4,decoration,null);
    await writeFile(new URL('populated-overview.rgba',dir),preview.pixels);
  }
  report.push({mode,spawns:count,patches,nativeWasmParity:true});
}
await writeFile(new URL('artifacts/map_editor/placement-results.json',root),JSON.stringify(report,null,2)+'\n');
console.log('PASS placement native/WASM parity, masked counts, zero fields, full textured decoration render and spawn overlay',report);
