"""Native/WASM recipe parity and legacy-map regression fixtures."""
import hashlib
import pathlib
import subprocess
import sys
import json
import struct
from compile_recipe import compile_recipe

ROOT = pathlib.Path(__file__).resolve().parents[1]


def legacy_digest(executable):
    digest = hashlib.sha256()
    output = ROOT / 'build/legacy-seed.bin'
    for i in range(128):
        seed = 0xC0FFEE if i == 0 else (i * 2654435761) & 0xffffffff
        subprocess.run([str(executable), str(seed), str(output)], check=True)
        digest.update(output.read_bytes())
    return digest.hexdigest()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        print(legacy_digest(ROOT / sys.argv[1]))
    else:
        folder = ROOT / 'build/map-recipe-tests'
        fixtures = json.loads((folder / 'manifest.json').read_text())
        digest = hashlib.sha256()
        for i, fixture in enumerate(fixtures):
            recipe = fixture['recipe']
            if recipe.get('materialOutput') == fixture['target']:
                assert compile_recipe(recipe, recipe['materialOutput']) == fixture['program']
            if fixture['target'] == recipe['output'] and next(n for n in recipe['nodes'] if n['id'] == recipe['output'])['type'] == 'world':
                assert compile_recipe(recipe) == fixture['program']
            output = folder / f'{i}.result'
            subprocess.run([str(ROOT / 'build/map_recipe_bridge'), str(folder / f'{i}.program'), str(fixture['seed']), str(output)], check=True)
            raw = output.read_bytes()
            meta = struct.unpack_from('<20I', raw)
            if meta[1] == 2:
                towns = list(zip(meta[8::2], meta[9::2]))
                assert len(set(towns)) == 6, f'Overlapping outposts in fixture {i}'
                assert all(abs(a[0]-b[0])+abs(a[1]-b[1]) >= 1024 for k,a in enumerate(towns) for b in towns[:k]), f'Outpost separation in fixture {i}'
            if fixture['tag'] == 'legacy':
                digest.update(struct.pack('<8I', 64, 64, fixture['seed'], meta[4], meta[5], meta[3], meta[6], meta[7]))
                digest.update(raw[32:])
        assert digest.hexdigest() == 'aefef27a6792c67ad4d86a418dd93195d271494f251cc0a2af6f77d231ce61a6', 'Original 128-seed layouts or placements changed'
        # Embed expected native bytes in a separate diagnostic ROM. The GBA
        # compares every byte, without injecting or modifying emulator memory.
        header = '#pragma once\nstruct fixture { const mapgen::node* program; const uint8_t* expected; int count; uint32_t seed; };\n'
        for i, fixture in enumerate(fixtures):
            header += f'const mapgen::node program_{i}[]={{\n'
            for n in fixture['program']:
                header += '{mapgen::op('+str(n[0])+'),'+','.join(map(str,n[1:5]))+'u,{'+','.join(map(str,n[5:]))+'}},\n'
            header += '};\n'
            header += f'const uint8_t expected_{i}[]={{'+','.join(map(str,(folder/f'{i}.result').read_bytes()))+'};\n'
        header += f'constexpr int fixture_count={len(fixtures)};\nconst fixture fixtures[]={{\n'
        header += '\n'.join(f'{{program_{i},expected_{i},{len(f["program"])},{f["seed"]}u}},' for i,f in enumerate(fixtures))
        header += '\n};\n'
        render_cases=json.loads((folder/'render-manifest.json').read_text())
        header += 'struct render_fixture { const mapgen::node* world; const mapgen::node* materials; int world_count,material_count; uint32_t seed,expected; };\n'
        for i,f in enumerate(render_cases):
            material_path=str(folder/f'{f["name"]}.materials') if f['materials'] else '-'
            subprocess.run([str(ROOT/'build/map_recipe_bridge'),str(folder/f'{f["name"]}.world'),str(f['seed']),str(folder/f'{f["name"]}.render'),material_path],check=True)
            assert compile_recipe(f['recipe'])==f['world']
            if f['materials']: assert compile_recipe(f['recipe'],f['recipe']['materialOutput'])==f['materials']
            for key in ('world','materials'):
                header+=f'const mapgen::node render_{key}_{i}[]={{\n'
                for n in f[key] or [[12,-1,-1,-1,0,0]]:
                    header+='{mapgen::op('+str(n[0])+'),'+','.join(map(str,n[1:5]))+'u,{'+','.join(map(str,n[5:]))+'}},\n'
                header+='};\n'
        header+=f'constexpr int render_fixture_count={len(render_cases)};\nconst render_fixture render_fixtures[]={{\n'
        for i,f in enumerate(render_cases):
            signature=struct.unpack('<I',(folder/f'{f["name"]}.render').read_bytes()[-4:])[0]
            header+=f'{{render_world_{i},render_materials_{i},{len(f["world"])},{len(f["materials"])},{f["seed"]}u,{signature}u}},\n'
        (folder/'fixtures.h').write_text(header+'};\n')
        print(f'PASS native recipe fixtures: {len(fixtures)} cases; 128 original seed maps and placements byte-identical')
