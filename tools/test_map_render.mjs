import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import createEngine from './map_editor/generated/engine.mjs';
import {renderOverview,renderFullPng} from './map_editor/render.mjs';
const root=new URL('../',import.meta.url),folder=new URL('build/map-recipe-tests/',root);
const cases=JSON.parse(await readFile(new URL('render-manifest.json',folder),'utf8'));
const art=JSON.parse(await readFile(new URL('tools/map_editor/generated/art.json',root),'utf8'));
const engine=await createEngine();
await mkdir(new URL('artifacts/map_editor/',root),{recursive:true});
function run(program,seed){engine.HEAPU32.set(new Uint32Array(program.flat()),engine._recipe_input()>>>2);assert.equal(engine._recipe_run(program.length,seed),0);}
for(const f of cases){
  run(f.world,f.seed);
  if(f.materials.length){run(f.materials,f.seed);assert.equal(engine._recipe_apply_materials(),0);}
  const native=await readFile(new URL(`${f.name}.render`,folder));
  const ground=engine._recipe_ground(),ptr=engine._recipe_tiles(),tileMap=engine.HEAPU16.slice(ptr>>>1,(ptr>>>1)+1024*1024);
  assert.deepEqual(Buffer.from(engine.HEAPU8.slice(ground,ground+4096)),native.subarray(4176,8272),`${f.name} ground IDs`);
  assert.deepEqual(Buffer.from(tileMap.buffer),native.subarray(8272,-4),`${f.name} every rendered tile`);
  assert.equal(engine._recipe_render_signature()>>>0,native.readUInt32LE(native.length-4),`${f.name} tiles and grip`);
  if(['original','natural','roads','roads-wide','active'].includes(f.name)){
    const png=await renderFullPng(tileMap,art);
    await writeFile(new URL(`artifacts/map_editor/${f.name}-full-map.png`,root),Buffer.from(await png.arrayBuffer()));
    const preview=renderOverview(tileMap,art);
    await writeFile(new URL(`${f.name}-overview.rgba`,folder),preview.pixels);
  }
}
await writeFile(new URL('artifacts/map_editor/render-results.json',root),JSON.stringify({cases:cases.length,tilesPerCase:1048576,nativeWasmTileParity:true,groundIdParity:true,surfaceParity:true,fullPngSize:[8192,8192]},null,2)+'\n');
console.log(`PASS ${cases.length} native/WASM full tile maps, ground IDs and surface signatures; exported original and natural 8192-square PNGs.`);
