# Lakeside Commons

A 16384 x 16384 free-driving test assembled from a reusable art kit. The original
circuit is still available from the title screen. This is an authored layout,
not a randomly regenerated world.

The area is sixteen times the previous 4096-square version, at unchanged car scale.
Sixteen copies of that layout are joined by roads through their internal borders.
Existing graphics are reused; no new artwork was added.
There are 9,296 placements of existing props, 1,397 distinct graphics tiles,
and 101 distinct chunks serving 4,096 world chunk positions.
`world-2048.tmj` and `world-4096.tmj` preserve earlier layouts. Builds use only `world.tmj`.
`tools/expand_world_16k.py` performed this explicit one-time migration; builds
never run it or overwrite your authored layout. The spawn remains (512,1536).
Drive east to reach the eastern district, or follow the main roads south.

## Edit the world

Open `world.tmj` in Tiled. No editor installation is required to build the ROM.

- `Ground`: 16 x 16 tiles. Paint or copy stamps using `terrain.tsj`.
- `Objects`: reusable trees, rocks, fences and buildings from `props.tsj`.
  Place tile objects at native size, snapped to 16 pixels. Their anchor is bottom-left.
- Move the point named `start` to set the car's spawn; the car initially faces east.
- Keep the `verification_route` polyline unobstructed. Emulator tests drive it
  using ordinary controls; edit it when you substantially change the road layout.
- Add rectangle objects with type `solid` for extra invisible blockers.
- Terrain tile property `surface`: 0 grass, 1 road/gravel, 2 dirt, 3 impassable.
- Prop tile collision rectangles are editable in Tiled's tile collision editor.
  The `solid` property enables/disables those rectangles. Bushes have none.

Save, then run `./build.ps1` and `./test.ps1` from the repository root.
Builds preserve `world.tmj`, `terrain.tsj`, and `props.tsj`; they are seeded only
if missing. Their JSON can also be edited directly. The PNG files other than
`source-kit.png` are derived outputs and are regenerated.

The initial terrain sheet contains texture variants and N/E/S/W edge combinations;
it does not yet configure Tiled's Terrain Brush/Wang sets. Use existing road
stamps, or choose the matching edge tiles manually. Transparent prop artwork
is composited offline, so a forest does not consume one hardware sprite per tree.

## Art provenance and build pipeline

`source-kit.png` was made with the built-in image-generation tool, using
`../map2/background.png` as a style reference. `art-prompt.txt` records the full
prompt. Neither the reference nor the generated source is modified by builds.
The source sheet has material swatches and isolated props with alpha.

`tools/generate_assets.py` invokes `tools/open_world.py` to crop the sheet,
nearest-sample game-size assets, threshold prop alpha, and quantize to the
circuit's shared RGB5 background palette. Runtime uses the packed results:

1. Deduplicated 8 x 8 graphics tiles.
2. 16 x 16 metatiles: four graphic IDs and sixteen 4-pixel surface subcells.
3. 256 x 256 world chunks: 16 x 16 metatile IDs, independently LZ77-compressed.
4. A small chunk-ID grid describing the complete world.

Only camera-near graphics enter the 30 KiB content-shared terrain tile cache. The complete
world and collision definitions stay in ROM; nine decoded chunks occupy a fixed
4,652-byte RAM cache shared by rendering and collision. Expanding reused grass
adds placement data, not a fresh screen-sized image. Collision/visual combinations
are also deduplicated. `artifacts/open_world/report.json` records exact budgets;
`overview-small.png` shows the complete current world. `collision.png` and
`surfaces.png` use one pixel per 4 world pixels. `reference-atlas.png` and
`reference-layout.json` preserve full-resolution reference pixels without a giant
image. The old `overview.png` is historical 4096-square output, not regenerated.

The importer composes only distinct source chunks, reusing exact ground/object
combinations. It never assembles a full-world RGB image. A scanline flood checks
connectivity over the complete 4px collision grid. The new compiler was verified
against every pixel of the earlier 4096 map before expanding the layout.

The importer checks every legal camera-tile origin using a 31 x 21 tile window.
It evaluates each distinct 2x2 chunk neighbourhood once, with special clamped
edge cases, and proves coverage of all repeated locations; this is not sampling.
109,607 representative views in 123 neighbourhoods cover all 4,096,551 legal
tile-aligned camera origins; host tests also exercise 10,000 random jumps.
It rounds the maximum number of distinct visible tiles up to a 2 KiB VRAM block.
For this layout: 476 distinct tiles at the busiest view, 480 allocated slots.
Identical tiles share slots, retaining off-screen graphics until their slots
are needed. Artwork and palettes are unchanged. A more varied edited scene may
need a larger reservation; the build regenerates the capacity automatically.
The runtime protects the complete next view before eviction. Its cache loop
runs as ARM code in fast internal RAM; reset/map-switch jumps use a brief hidden
loading phase. Working-RAM bookkeeping grows by about 5 KiB, distinct from the
14 KiB saved in background VRAM. Sprite graphics allocations are unchanged.

Compression is now active in the ROM. `artifacts/open_world/compression.json`
records actual encoded sizes. The 4,096 chunk positions require an 8 KiB ID grid;
repeated chunks are stored once before compression.
Layout storage is 28,880 bytes instead of 59,904 after deduplication: 51.8% saved.
All world assets together occupy 137,736 ROM bytes (134.5 KiB), including a
6,464-byte packed radar surface table. Its 16px samples are read directly from
ROM, so zooming the radar out does not evict nearby decoded terrain chunks.
Offsets/flags, an end sentinel, alignment and the chunk-ID grid are included.
Each decoded chunk is 512 bytes. A 3x3 modulo-addressed cache reuses loaded data;
first access decodes a missing chunk, scene selection invalidates all slots.
The importer/runtime also support raw fallback for incompressible chunks.
Read-only telemetry counts actual decompressions since scene selection. The
compact driving HUD now shows only speed and ground, with a circular local radar.
Graphics in VRAM remain unpacked. The old `compression-estimate.json` describes
the earlier offline experiment only, not the currently compiled map.

## Deliberate prototype limits

- One biome and one flattened scenery layer; no foreground canopy/roof occlusion.
  Tree/building collision rectangles are conservative to keep cars from drawing
  over their artwork. They are not yet small trunk-only footprints.
- The garage is a landmark with a solid footprint, not an interactive interior.
- No NPC/traffic simulation, quests, save system or animated water.
- Road/shore edges are visibly grid-based. More diagonal and curved transition
  art can improve them without changing world storage.
- No automatic editor edge repainting yet; properties determine physics, not color.
- Supported input: finite orthogonal 16-pixel maps, dimensions in multiples of
  16 cells (256 pixels), 256..16384 pixels per axis; one Ground layer plus object
  layers. The current stress-test layout uses the maximum accepted dimensions.
- No rotated/flipped/scaled props or tiles, extra tile layers, layer offsets,
  partial opacity, or polygon collisions. Unsupported inputs fail the build.
- Both scenes share one 256-color background palette; car/effect palettes are separate.

Import validation checks spawn clearance, the route's car footprint, asset ID
limits and connectivity of traversable cells. Runtime/emulator testing is still
needed after layout edits; import validation alone does not test handling.
