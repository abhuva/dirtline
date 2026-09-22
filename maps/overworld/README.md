# Procedural overworld

Every enabled entry in `maps/map-library.json` is an 8,192 x 8,192 map with a
saved seed. The same catalog supplies the browser workshop and the ROM title
screen. There is no runtime random-map option. Returning from a town preserves
the current generated layout. Seeds remain available in test telemetry, not the
minimal driving HUD. No cartridge save or seed-entry UI exists yet.

## Generation and collision

`include/cave_layout.h` is the source shared by GBA runtime and host tests:

- 64 x 64 logical cells, each 128 world pixels; 47% initial wall probability.
- Five passes of the common 4/5-neighbour cave rule: an existing wall survives
  with four wall neighbours; floor becomes wall with five. Equivalently, count
  all nine cells including the center and keep a wall if at least five are walls.
- A two-cell solid outer border and four-direction flood fill. Only the largest
  connected floor component survives. A pathological result below 256 cells gets
  a central fallback clearing. The current 128-seed sweep uses no fallbacks.
- Spawn near the component center, a connected first-outpost approach 256px
  east, then five spread-out destinations scored to prefer narrow branch ends.
  Destinations are not guaranteed to be graph-theoretic dead ends. Each gets a
  connected 3 x 3-cell clearing. They are map icons, not full city layouts.
- Convex exposed wall corners round inward with a 48px radius, quantized to
  8px cells shared by renderer and collision. Coarse floor is never narrowed.
- Legacy material patches are seed-derived at 512px scale: sand, gravel, hardpan and
  occasional asphalt remnants. No new road grid is imposed on the cave layout.
- Town art is a 64px stamp immediately north of its entrance; its solid footprint
  ends 8px short of the entrance for car clearance. A 64px entrance radius prompts
  the player. After cancel/return, leave the 160px vicinity to rearm it.

The cave-rule background is documented by
[RogueBasin](https://www.roguebasin.com/index.php/Cellular_Automata_Method_for_Generating_Random_Cave-Like_Levels).
Our implementation, deterministic PRNG, placement and runtime integration are
project code. Future required objects should use retained connected floor and
verify their full footprint/approach against walls and existing props.

## Artwork

The current art follows the user's supplied muted wasteland sheet: dusty brown
soil, grey gravel, cracked hardpan, charcoal asphalt, layered rock and olive
vegetation. These are newly generated assets made with the built-in image tool.
`muted-art-prompts.txt` records both prompts:

- `wasteland-kit-muted.png`: a 4 x 2 atlas containing four floor swatches,
  plateau top/cliff face and two transparent settlement icons.
- `wasteland-details-muted.png`: four isolated transparent patches, in order
  dry grass, low scrub, rocks and dead brush.

The earlier `wasteland-kit.png`, `art-prompt.txt` and original reference
`../open_world/wasteland.png` are preserved as previous art sources.

`tools/wasteland_assets.py`, invoked by `tools/generate_assets.py`, extracts and
reduces the swatches to 32px textures and the icons to 64px background stamps,
preserves their alpha when compositing onto sand, quantizes to RGB5, reserves UI
and scenery palette slots and deduplicates 8px graphics. Decoration imports use
an alpha cutoff of 192, nearest-neighbour resizing inside 16px, and a dedicated
15-opaque-colour palette plus transparent index zero. Ground and walls repeat
at 32px; the existing rounded collision/rendering geometry is unchanged.
Do not hand-edit generated headers or BMPs. Run `./build.ps1` after source changes.
`tools/test_wasteland_art.py` checks terrain opacity, repeat-boundary contrast,
detail alpha and matching GBA/editor pixels. Its `artifacts/wasteland/muted-art-proof.png`
shows 3 x 3 repeats and details on every ground material for visual inspection.

The graphics budget is bounded for **every seed** by the whole art vocabulary:
180 unique tiles, rounded to 192 cache slots (12 KiB). No seed-specific camera
capacity guess is needed. Including HUD/map and decoration is 24 KiB background
VRAM while driving, 28 KiB during the question, 4 KiB in the blank town. The
terrain palette uses 80 entries; UI and scenery have separate 4bpp banks. All
wasteland art uploads once during scene loading; stable tile IDs allow driving
to update only entering rows/columns without cache eviction or whole-view pinning.
The live minimap costs 2 KiB sprite VRAM plus about 2 KiB staging RAM and a 4 KiB source image. Five
enemy sprites share a 32-byte tile; circle masks use 4 KiB ROM. Layout is 4,168 RAM bytes, with 12,288 scratch bytes only
during generation. The renderer uses 13,948 bytes of RAM including its cache.

## Town lifecycle and verification

The nearby town is intentionally easy to try: accelerate east from spawn.
The marker is now lower and the question is bottom-aligned so it remains visible.
Direction selects Yes/No, A confirms, B cancels. Yes destroys the terrain/HUD/
minimap graphics and the renderer, flushes retained display references, and
loads a blank town background. Its single return option uses A or Start.
The run layout, car position/heading and camera survive; velocity is stopped.
L/R select vehicle setup only on this town screen, without resetting position.
Return recreates the scene with the same seed and exact saved position. Held
confirmation buttons cannot immediately accelerate or re-open the prompt.

Driving scenes use a single 12px top strip showing speed and ground.
The second HUD line and entire bottom control strip are removed. Lap/seed/setup
details no longer obscure the world.

The wasteland minimap uses a static north-up 64x64 source image clipped to the circular radar mask. Each source pixel is
one logical cell: bright walls, dark floor, grey road-connection cells, and gold
town dots. Transparent corners reveal the scene. Town dots are clipped to the circle; the
player marker stays centered at every zoom. The source is generated
once per scene (4 KiB). All four zooms crop this image around the player, updating
only on display-pixel crossings. Pixels beyond the map edges show white wall. No
terrain queries are needed while driving. Live red 2x2 dots show active living
enemies inside the circle and disappear on death or despawn. Wall corner
rounding, ground textures and varying road thickness do not alter this overview.
Select opens zoom settings; Left/Right choose 1x/2x/4x/8x, then A/B/Select returns.

`./test.ps1` runs the 128-seed host connectivity/clearance sweep, every enabled
catalog map and joypad-only procedural scene tests.
`artifacts/wasteland/` contains an overview, native emulator captures,
compiled tile preview, host-generated seed fixtures and budget report.
`artifacts/test-results.json` records the tested ROM hash and emulator assertions.

Still prototype: repeated texture tiles, simple surface transitions, no authored
town interiors, no persistence or town NPCs. Connectivity is not the same
as enjoyable pacing; map scale, passage width and visual clarity need playtesting.

## Material recipes and preview

Version 2 editor recipes add a separate 64x64 Ground materials output. IDs are
bytes, interpreted through `maps/materials.json`, and determine both ground art
and driving surface. The ROM stores that grid in an additional 4 KiB allocation.
The shared selector in `include/wasteland_tiles.h` supplies both game rendering
and the browser's Game textures / Full map render views. Legacy recipes retain
their original patches. See the WEB MAP WORKSHOP section in `readme.txt`.

## Procedural town roads

The optional Town roads node follows the Playable world node. One breadth-first
search from town zero supplies shortest paths for all towns, avoiding walls and
buildings. The separate connection grid overlays a chosen ground material at
8-256px width, using the same geometry for tile rendering and grip. A single
constant width keeps lookup cheap; width variation is disabled.
Wide roads extend across cell boundaries and are clipped by walls/building art. It does not
modify the categorical ground grid or wall/floor map. Select this node as the
wall/floor output; `maps/recipes/town-roads.json` is a ready-made example.

The Wasteland catalog entry includes wide roads, its material branch, spawn and
decoration outputs, and seed 12648431. Save catalog changes in the browser and
rebuild to expose enabled maps on the title screen. See artifacts/test-results.json
for current emulator results.

## Spawn and cosmetic outputs

Version 3 recipes can select `spawnOutput` (Enemy spawns) and
`decorationOutput` (Decoration). Each takes an optional 0-255 field on A and is
applied to the final world. The active recipe selects both; the editor's
Populated wasteland preset demonstrates a noise-driven decoration field.

Spawns select a target count from valid sector anchors with weighted sampling,
minimum spacing, and optional starter encounters. Zero weights exclude anchors.
The preview reports achieved/requested counts and offers a Spawns overlay toggle.
Runtime stores compact coordinates, then uses the existing five-car encounter
pool and HP/cooldown persistence.

Decoration density and four relative type weights place 16px dry grass, scrub,
pebbles and twigs on a hashed 32px grid. Type changes retain positions. Patches
exclude walls/buildings and, by default, roads. The transparent background layer
costs 6 KiB VRAM, about 4.5 KiB staging/cache RAM and a 4,120-byte density/config
allocation. It uses no object sprites and changes neither collision nor grip.
Generation and rendering are shared by the editor, native tests and GBA.
