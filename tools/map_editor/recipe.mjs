export const MAX_NODES = 32;
export function compile(recipe, schema, target = recipe.output, validateAll = true) {
  const fail = message => { throw new Error(message); };
  const integer = (value, lo, hi, name) => {
    if (!Number.isInteger(value) || value < lo || value > hi) fail(`${name}: expected ${lo}–${hi}.`);
  };
  if (![1,2,3].includes(recipe.version) || !Array.isArray(recipe.nodes)) fail('Unsupported recipe format.');
  integer(recipe.seed, 0, 0xffffffff, 'Seed');
  if (!recipe.nodes.length || recipe.nodes.length > MAX_NODES) fail('Use between 1 and 32 nodes.');
  const ops = new Map(schema.operations.map((op, index) => [op.id, { ...op, index }]));
  const nodes = new Map();
  for (const node of recipe.nodes) {
    integer(node.id, 1, 0x7fffffff, 'Node ID');
    if (nodes.has(node.id)) fail('Node IDs must be unique.');
    const op = ops.get(node.type);
    if (!op) fail(`Unknown operation: ${node.type}`);
    integer(node.stream ?? 0, 0, 0xffffffff, 'Random stream');
    // Import the retired min/max format at its midpoint, rounded to an 8px tile.
    if(node.type==='roads' && Array.isArray(node.p) && node.p.length===3) {
      integer(node.p[0],8,256,'Minimum road width');integer(node.p[2],node.p[0],256,'Maximum road width');
      node.p=[node.p[0]===node.p[2]?node.p[0]:Math.floor((node.p[0]+node.p[2]+8)/16)*8,node.p[1]];
    }
    if (!Array.isArray(node.p) || node.p.length !== op.parameters.length) fail(`Invalid parameters on node ${node.id}.`);
    op.parameters.forEach((p, i) => {
      integer(node.p[i], p[2], p[3], p[0]);
      if (p[4] === 'neighbours' && ![4, 8].includes(node.p[i])) fail('Choose 4 or 8 neighbours.');
    });
    if(node.type==='material_bands' && (node.p[0]>node.p[1] || node.p[1]>node.p[2])) fail('Material boundaries must be in ascending order.');
    nodes.set(node.id, node);
  }
  if(recipe.version===2 && nodes.get(recipe.materialOutput)?.type!=='materials') fail('Choose a Ground materials output.');
  if(recipe.version===1 && recipe.materialOutput!=null) fail('Material outputs require recipe version 2.');
  for(const [key,type] of [['materialOutput','materials'],['spawnOutput','spawns'],['decorationOutput','decoration']])
    if(recipe[key]!=null && nodes.get(recipe[key])?.type!==type)fail(`Invalid ${key}.`);
  if(recipe.version<3 && (recipe.spawnOutput!=null || recipe.decorationOutput!=null))fail('Placement outputs require recipe version 3.');
  const ordered = [], done = new Set(), visiting = new Set();
  function visit(id) {
    const node = nodes.get(id);
    if (!node) fail('Connect all required inputs and choose an output.');
    if (visiting.has(id)) fail('This connection creates a cycle.');
    if (done.has(id)) return;
    visiting.add(id);
    const op = ops.get(node.type), inputs = node.inputs ?? {};
    if (Object.keys(inputs).some(port => !(port in op.inputs))) fail(`Unknown input on node ${id}.`);
    for (const [port, expected] of Object.entries(op.inputs)) {
      const source = inputs[port];
      if (source == null && expected.endsWith('?')) continue;
      visit(source);
      if (ops.get(nodes.get(source).type).kind !== expected.replace('?', '')) fail(`Node ${id}, ${port}: needs ${expected.replace('?', '')}.`);
    }
    visiting.delete(id); done.add(id); ordered.push(id);
  }
  if (validateAll) for (const id of nodes.keys()) visit(id);
  ordered.length = 0; done.clear(); visit(target);
  const indices = new Map(ordered.map((id, i) => [id, i]));
  const program = ordered.map(id => {
    const n = nodes.get(id);
    return [ops.get(n.type).index, ...['a', 'b', 'mask'].map(p => indices.get(n.inputs?.[p]) ?? -1),
      n.stream ?? 0, ...n.p, ...Array(8 - n.p.length).fill(0)];
  });
  const last = program.map((_, i) => i);
  program.forEach((n, i) => n.slice(1, 4).forEach(source => { if (source >= 0) last[source] = i; }));
  const peak = Math.max(...program.map((_, i) => last.slice(0, i).filter(end => end >= i).length + 1));
  if (peak > 6) fail(`This graph needs ${peak} live buffers. The GBA limit is 6; simplify its branches.`);
  return { program, peak, kind: ops.get(nodes.get(target).type).kind, ordered };
}

export function makeNode(schema, type, id, x = 40, y = 40) {
  const op = schema.operations.find(op => op.id === type);
  return { id, type, label: op.name, inputs: {}, stream: op.random ? id : 0, p: op.parameters.map(p => p[1]), x, y };
}

export function presets(schema, original) {
  const create = (name, types, configure) => {
    const nodes = types.map((type, i) => makeNode(schema, type, i + 1, 40 + (i % 3) * 235, 45 + Math.floor(i / 3) * 200));
    configure(nodes);
    return { version: 1, name, seed: original.seed, output: nodes.at(-1).id, nodes };
  };
  const result = [original,
    create('Two rules + radial mask', ['random','cellular','cellular','radial','threshold','combine','largest','world'], n => {
      n[0].stream = 0;
      n[1].inputs.a = 1; n[1].p[0] = 2;
      n[2].inputs.a = 2; n[2].p = [3, 496, 504, 2, 8];
      n[3].p = [32,32,35,0]; n[4].inputs.a = 4; n[4].p[0] = 210;
      n[5].inputs = { a: 3, b: 5 }; n[6].inputs.a = 6; n[7].inputs.a = 7;
    }),
    create('Plasma basin', ['plasma','radial','blend','threshold','cellular','world'], n => {
      n[2].inputs = {a:1,b:2}; n[2].p[0] = 105;
      n[3].inputs.a = 3; n[3].p[0] = 142;
      n[4].inputs.a = 4; n[4].p[0] = 2; n[5].inputs.a = 5;
    }),
    create('Voronoi passages', ['voronoi','threshold','noise','threshold','combine','cellular','world'], n => {
      n[0].p = [18,1,20]; n[1].inputs.a = 1; n[1].p[0] = 50;
      n[2].p = [20,2]; n[3].inputs.a = 3; n[3].p = [160,1];
      n[4].inputs = {a:2,b:4}; n[4].p[0] = 1;
      n[5].inputs.a = 5; n[5].p[0] = 2; n[6].inputs.a = 6;
    }),
    (()=>{
      const r=structuredClone(original);r.name='Natural ground';r.version=2;
      const first=Math.max(...r.nodes.map(n=>n.id))+1;
      const noise=makeNode(schema,'noise',first,40,280);noise.p=[12,3];
      const bands=makeNode(schema,'material_bands',first+1,280,280);bands.inputs.a=first;
      const output=makeNode(schema,'materials',first+2,520,280);output.inputs.a=first+1;
      r.nodes.push(noise,bands,output);r.materialOutput=output.id;return r;
    })()];
  const roads=structuredClone(result.at(-1));roads.name="Natural ground + town roads";
  const node=makeNode(schema,"roads",Math.max(...roads.nodes.map(n=>n.id))+1,760,45);
  node.inputs.a=roads.output;roads.nodes.push(node);roads.output=node.id;result.push(roads);
  const populated=structuredClone(roads);populated.name='Populated wasteland';populated.version=3;
  const first=Math.max(...populated.nodes.map(n=>n.id))+1;
  const spawn=makeNode(schema,'spawns',first,760,280),decor=makeNode(schema,'decoration',first+1,760,480);
  const density=makeNode(schema,'noise',first+2,280,480);density.p=[10,2];decor.inputs.a=density.id;
  populated.nodes.push(spawn,decor,density);populated.spawnOutput=spawn.id;populated.decorationOutput=decor.id;result.push(populated);
  return result;
}
