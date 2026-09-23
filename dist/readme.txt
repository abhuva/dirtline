DUSTLINE - PROCEDURAL WASTELANDS
Playable Game Boy Advance driving/combat prototype / version 0.14

PLAY
----
Open dist/dustline.gba in RetroArch using the Nintendo - Game Boy Advance
(mGBA) core. Use Load Content to select the file directly; a database scan
may not recognize an original homebrew game. No base game or ROM patch is
needed. A separate GBA BIOS is optional with mGBA.

Choose a map with Left/Right, then press A. Every title entry comes from
maps/map-library.json and has a saved seed. The ROM currently includes eight
8192 x 8192 procedural maps. There is no runtime random-map choice. Recipes can
use cellular automata, masks, smoothing and largest-component flood fill so
disconnected floor is filled and all six outposts are reachable.
The loading screen shows aggregate progress through the selected map's world,
material, spawn and decoration node graphs, followed by encounter and scene setup.
Select opens settings without resetting the car. Vehicle setups are fitted by the
mechanic inside town.
While driving, L cycles weapons and R fires the selected weapon.
Drive east from spawn to try the nearby first outpost (256px away).
Approaching an outpost stops the car and asks whether to enter. Use a direction
to select Yes/No, then A to confirm; B cancels. No is selected initially.
Yes unloads the overworld graphics and opens a walkable desert settlement. Walk
around the central rocks to the garage at the north edge, face its open door and
press A. Inside, walk to the mechanic and press A to fit a vehicle setup. Leave
through the garage door, then use the settlement's south gate to return to the
exact saved coordinates, stopped, on the same map. Leave the entrance vicinity
before its prompt can reopen.
The settlement marker remains visible above the bottom-aligned entry question.
All six outposts currently share this first town and garage layout. There are no
additional interiors, shop transactions, dialogue trees or persistent saves yet.

BASIC COMBAT TEST
Red/orange versions of the existing car spawn throughout procedural maps.
Each reachable 512px sector gets an encounter anchor where clearance permits,
plus two nearby starter opponents. The active exported recipe has 163 anchors; other seeds
vary. A shared pool limits the entire simulation to FIVE active enemies.
Anchors activate within 560px (about 2.3 screen widths); cars despawn beyond
800px from the player. This wider removal radius avoids boundary flicker.
New cars spawn outside the viewport, with clearance from existing cars. Initial
scene loading may place the starter pair in view. Nearby eligible points get
priority when a slot is free; the pool never grows to accommodate more points.
Destroyed encounters wait 1,800 driving frames (about 30 seconds) before becoming
eligible again, then return with three HP. A visible anchor waits until it is
off-screen. Despawned survivors retain their remaining HP, but restart at their
anchor when reactivated. Anchors cannot produce duplicates while their car lives.
L cycles GUN, SAW, SIDES, SEEK and TRAP once per press. Hold R to use the selected
weapon. The top status line shows its name and a small original pixel icon.
The default forward gun fires about six shots per second with 120px muzzle
travel; side guns fire both +/-90-degree directions every 16 driving frames.
Each bullet removes one of the enemy's three HP pips.
The chainsaw is a 10px-radius circle 24px ahead of the car, dealing two HP every
eight frames on contact (enemy bodies have an 11px hit radius). Release R to stop.
Homing missiles launch 18px ahead, coast for eight ticks, then acquire the
closest living enemy. They refresh direction every six ticks, travel 4px/frame,
deal three HP, and expire after 150 ticks. At most two exist; shots are spaced
36 ticks apart. Targets use encounter identity and are reacquired after loss.
Traps drop 22px behind, arm after 18 ticks, and stay stationary for up to 900
ticks. Enemy contact detonates a 32px-radius, three-HP blast. The owner's car
does not trigger it. Six traps maximum; one drop per 45 ticks. A full pool
refuses another drop. Traps flash when armed and show a blast when triggered.
Weapons respect walls/buildings. Each weapon retains its own cooldown when
switched; deployed attacks keep working. Pause/settings freeze all simulation.
Town entry clears deployed attacks while preserving the selected weapon and
encounter damage. A new run starts with the gun and empty weapon pools.
The player starts with 100 health and a 20-point rechargeable shield. Enemy
bullets deal one point, consuming shield before health. After three seconds
without damage, shield returns at four points per second. Entering an outpost
fully restores both. At zero health, A revives in place with full health and
shield, clears deployed projectiles and grants two seconds of protection.
Ramming changes motion, not health, for now.
Cars have heading-aligned 22x14px rectangular contact bodies. Impacts transfer
velocity according to relative closing speed and mass, with mild bounce and
tangential friction. Light cars are shoved more than heavy ones; engine speed
limits do not instantly erase an impact's extra speed. Three bounded contact
passes separate groups of cars, checking terrain before every correction.
Terrain driving still uses the established forgiving circular footprint. This
is arcade contact response, not a full chassis/inertia/angular-impact model.
Bullets cannot pass through walls/buildings.
Enemy fire ignores other enemies. Ammunition is unlimited.

Enemies detect/pursue within 480px (two screen widths). Their gun now matches
the player's: 120px muzzle range, 6px/frame bullets, one shot per ten frames.
They only fire with the player inside a roughly +/-9-degree forward cone,
within gun reach and with a clear terrain line of sight. There is no auto-aim.
They use the same driving physics, but a weaker 750kg RAIDER setup: 0.032
acceleration, 2.25 maximum engine speed, 0.100 grip and 2.15 steering. Normal
AI cruising targets 1.4px/frame. Sensors check predicted positions of the player
and other live cars as well as terrain. Near the player they make short flanking
legs and repeated attack runs instead of parking; outside pursuit range they
patrol near their original positions. Rear sensing protects reverse recoveries.
This is local obstacle avoidance, not maze-wide pathfinding: awkward corners
can still confuse them. Brief braking stops and occasional contacts are normal.

Select settings, Start pause, and town prompts freeze combat. Entering town
unloads its sprites and clears bullets in flight, but preserves enemy HP/deaths
and positions, including anchor ownership and cooldowns. Cooldowns only advance
while driving, not in menus or town. Returning does not reset encounters; starting
a new map resets all of them. No encounter state is saved across a reboot.
All driving scenes use a single 12px-high HUD strip: speed and detected ground.
The former lower control strip and second HUD row now show terrain. Setup names,
seed, timers and lap counts are not displayed while driving. The wasteland uses
a static 64x64 source image clipped by a circular mask, with transparent corners
and a thin rim. Each source pixel is one logical cell. Walls are
bright, floor dark, roads grey and towns gold dots. The yellow player marker
stays centered at every zoom; the image follows the player. Areas beyond the map
edges appear white like walls. Town dots outside the circle are clipped. Select
opens settings; Left/Right choose 1x (widest), 2x, 4x or 8x (closest).
Zoom copies and crops the same source pixels, so driving cannot change gaps into
walls through terrain resampling. The source uses 4 KiB and is built once per
scene. All crops update only when the player
crosses a displayed pixel. Road width and ground materials do not change this
simplified image. Small red dots track living active enemies every frame; dots
outside the circle, destroyed enemies and inactive spawn points are hidden.

In settings, Left/Right choose 1x, 2x, 4x or 8x, then A, B, Select or Start
returns. Driving pauses and preserves position and velocity. The zoom preference
persists across catalog maps and town visits until reboot.

CONTROLS (GBA BUTTONS, AS MAPPED IN YOUR EMULATOR)
------------------------------------------------
Title Left/Right Select the previous / next map
Title A          Start the selected map
A               Accelerate
B               Brake; keep holding to reverse once stopped
Left / Right    Steer relative to the car (steering reverses while backing up)
Town D-pad      Walk in four directions
Town A          Enter/leave doors and interact with the mechanic
Garage Left/Right Choose a vehicle setup while speaking to the mechanic
Garage A / B    Fit the selected setup / close the setup menu
L in wasteland  Cycle GUN / SAW / SIDES / SEEK / TRAP (one weapon at a time)
R in wasteland  Hold to use the selected weapon; no vehicle setup change
Select          Open settings while driving or in town (pauses driving)
Left / Right    In settings: choose minimap zoom
A/B/Select/Start In settings: apply and return
Start           Pause / controls screen; press again to resume
Select in pause Return to map selection

Up and Down have no driving function. Reverse uses B, not Down.

PROGRESSION DIRECTION
---------------------
Each town should offer a Garage for fitting, buying/selling and printing parts.
Owned blueprints are permanent unlocks available in every garage, allowing
onward travel without a mandatory central hub. Reactor/solar upgrades could
govern sustainable power output and recharge, avoiding a fuel-empty dead end.
The proposed eventual loadout is main + secondary offensive weapons and a
separate special slot (initially traps). This prototype deliberately exposes
one selected weapon at a time for individual handling/balance experiments;
there are no shop transactions, multi-slot equipment or energy economy yet.
The GBA has no X/Y buttons, so special-weapon controls need a native-button
mapping when the multi-slot loadout is added.

TRY THIS FIRST
--------------
Build speed on the straight, release A before a bend, steer into it, and
apply throttle again as you come out. You retain momentum while coasting.
There is no tap-frequency bonus: deliberate throttle timing is the goal.
The car has separate heading and velocity, so its nose can point slightly
away from its direction of travel. Watch the skid marks during a fast turn.
To restart a run, press Start, then Select, and choose a map again. Its saved
seed reproduces the same layout; there is no driving-position reset key.

Enter a wasteland town, walk into the garage and speak to the mechanic to compare:
  GRIP   - 950kg; forgiving cornering grip, moderate power.
  RALLY  - 1100kg; default, more power and speed, looser cornering.
  HEAVY  - 2200kg; slower acceleration/steering, greater resistance to shoves.
The town menu displays mass. These are relative arcade handling values, not
a real-world vehicle model; no enemy tank art or dedicated tank setup yet.

Changing setups in town does not reset position or regenerate the world.
The selected setup carries across catalog maps. Closing or resetting the
emulator clears the session; cartridge save support is not implemented yet.

WHAT IS IN THIS DEMO
--------------------
- Native GBA ROM, C++ / Butano / devkitARM.
- Eight catalog-selected 8k procedural maps with fixed seeds, connected floor,
  canyon walls, six settlement icons, live minimaps and a town/garage scene loop.
- Five pooled enemy drivers, world-wide spawn points, cooldowns and despawning.
- Forward guns, three-hit enemies, player health and a rechargeable shield.
- 64-direction pixel-art car with a fixed elevated view; no 3D renderer.
- Fixed-point momentum, speed-dependent steering, grip-limited sliding,
  braking, reverse, and slower curb shoulders. The handling presets are unchanged.
- Terrain collisions keep the car out of canyon walls and town buildings.
- Camera look-ahead and a zoomable circular overview with live enemy dots.
- Skid/dust particles and simple synthesized engine, tire, impact, and UI sounds.
- Title screen, pause/help screen, and paused minimap settings menu.
- Local browser workshop backed by the same shared map catalog compiled into the ROM.

This is the driving foundation for an original vehicle-adventure RPG,
inspired by Racing Gears Advance's handling and Car Battler Joe's vehicle
progression. It does not reproduce either game's code, artwork, sound,
maps, names, or exact physics. No quests, inventory, persistent progression,
or garage upgrades are implemented yet.

BUILD ON WINDOWS
----------------
Prerequisites: Git and running Docker Desktop using Linux containers.
PowerShell is sufficient; no global GBA compiler or Python install needed.

From this repository:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1

The script downloads Butano 21.8.0 at the pinned commit, builds a local
Docker image with the pinned devkitARM base, generates assets, and compiles
the ROM. The compiler and asset tools run inside the container, with the
checkout mounted at /work to avoid Windows path-with-spaces problems.

Output:
  dist/dustline.gba      Playable ROM
  dist/readme.txt        This document
  dist/licenses/        Upstream runtime/dependency license notices
  dustline.elf           Local debugging symbols (not committed)
  build/                Intermediate compiler/asset outputs (not committed)

The first build needs internet access and downloads sizeable dependencies.
Later builds reuse .tools/butano and the local dustline-build:1 Docker image.
The project is hosted at https://github.com/abhuva/dirtline; pushes to main are
built automatically and published at https://github.com/abhuva/dirtline/releases/latest.
The local build script does not change global PATH settings.

To force a clean rebuild:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Clean

Do not edit .tools/butano to tune the game. It is an ignored external
dependency, pinned to commit c66094ae514c74068f992a4896c5e1f234e9f6e2.
The devkitpro/devkitarm base is pinned by SHA-256 digest in tools/Dockerfile.
The compiler reports devkitARM GCC 16.1.0. Debian helper packages are obtained
from Bookworm repositories when the local image is first built; their patch
versions are not frozen, so a future rebuild is not promised byte-identical.

WEB MAP WORKSHOP
----------------
Run ./build.ps1 once to generate the game art, then ./map-editor.ps1 and open
http://127.0.0.1:8765.
Requires Docker Desktop and Python 3; the optional parity test also uses Node.js.
The script compiles the shared C++ generator to WebAssembly using Emscripten
4.0.15, pinned by Docker digest. There are no frontend packages, CDN requests,
or external accounts. Everything runs locally, including generation in a worker.
After the first build, ./map-editor.ps1 -NoBuild starts immediately. Rebuild
without -NoBuild after changing C++ generator code. -BuildOnly builds the engine
without starting the server; -Port chooses a different loopback port.

The editor provides a draggable node graph with typed input/output connections,
live intermediate previews, undo/redo, shared-library persistence, JSON import/
export, PNG captures, before/after comparison, floor-region overlays, exact
refined collision, game textures, and a nine-seed preview grid. Changing settings keeps the seed;
the refresh button chooses a new seed. Click a seed thumbnail to explore it.
The Map selector loads entries from maps/map-library.json. New starts a blank
draft, Save updates its catalog entry, and Save As creates a separate entry.
Drafts may be incomplete while Include in game is off. Enabling that checkbox
requires a complete valid graph; enabled entries appear on the ROM title screen
after the next build. Delete map removes the selected catalog entry. The local
server uses revision checks and atomic file replacement to prevent stale tabs
from silently overwriting newer saves. Unsaved edits are recovered per map in
the browser when the catalog revision still matches. Ctrl+S also saves.
Drag between output and input ports in either direction to connect them; dropping
onto an occupied input replaces its connection. Outputs can feed multiple inputs.
Click the x beside a connected input to disconnect it. Escape or dropping on
empty space cancels a drag. Clicking output then input and the Node Settings
selectors also support connecting/replacing; reset a selector to clear its input.
Connection edits support undo/redo. Drag node headers to move nodes.
To tune one node while watching another, select the node to edit and click
Pin settings, then select a downstream node for its preview. The pinned controls
keep editing the named node and the preview updates live. Unpin settings restores
selection-following controls. Duplicate/Delete act on the node in Node Settings.
The temporary cellular iteration slider also works through downstream previews.
Pins clear when their node is removed or a different recipe is loaded.
The desktop workshop fits the browser window with a single compact toolbar and
graph heading. Drag empty graph space to pan without bounds and use the mouse
wheel to zoom around the pointer. The graph has no scrollbars. The preview scales
to the space available. Small windows or large text may require scrolling inside a panel.
The built-in Guide describes mask semantics and the individual controls.

Game textures previews the actual terrain art using the same C++ tile selector
as the ROM: rounded walls, cliff faces, ground patches and settlement stamps.
Full map render opens an 8192x8192 render with Fit/25%/50%/100% zoom and Save full
PNG. Cars, enemies, radar and HUD are not part of the terrain render. The small
live preview is downsampled; the full PNG contains every original 8px tile.
Full renders include temporary iteration-preview settings; JSON exports do not.
PNG rows are compressed incrementally to avoid a giant RGBA export buffer.

Enemy spawns and decoration (version 3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Choose the Populated wasteland preset or add Enemy spawns and Decoration nodes.
They are independent final outputs applied to the selected wall/floor world.
New nodes become their respective output automatically; Use as spawn/decoration
output selects another branch. JSON stores spawnOutput and decorationOutput.
The Wasteland catalog entry includes both outputs. Older recipes retain legacy
encounters and no decoration. Ground output remains optional in version 3.

Enemy spawns has Target count (0-258), Minimum spacing (0-1024 world pixels),
Starter encounters, and an optional 0-255 field on input A. Zero forbids a
location; positive values are relative weights for selection without replacement.
Generation chooses from the existing reachable sector anchors and respects town
clearance. Count is a target: the preview reports the actual number available
after terrain, field and spacing restrictions. Starter encounters explicitly
requests the two original near-start anchors; they count toward the target and
respect both the field and spacing. Five active enemy cars remains the limit.
The Spawns checkbox controls location markers in previews and full PNG exports.
These markers are editor overlays; the in-game red dots remain live enemy cars.

Decoration has Density %, four relative type weights (dry grass, low shrub,
pebbles, dry twigs), Keep roads clear, and an optional 0-255 density field on A.
Effective density is Density % multiplied by the field / 255. The weights choose
the mix among placed patches; they need not sum to 100. All-zero weights or zero
density places nothing. Constant field makes a uniform value; Mask to field
converts a binary selection into 0/255. Noise, radial and other fields work too.
Each 32px cell has one hashed candidate, with an 8px-aligned random offset and
16px artwork. Independent hashes control presence, position and type. Weight
changes preserve positions; the same seed/stream reconstructs them after travel
or town visits. Walls, settlement stamps and optionally roads exclude patches.
They have no collision, grip changes, animation or saved state. Breakables are
not implemented in this pass.

Browser, native preview and GBA use the same placement code. Game textures and
full PNGs include the transparent artwork. The runtime streams it below cars on
a separate background layer, using no object-sprite slots. It visits newly
exposed 32px cells and caches visible results; it never scans the whole world
while driving. Placement checks cover masks, count/spacing, deterministic types,
native/WASM parity, PNG pixels and emulator rendering.

Version 2 recipes have two independent outputs: output (Playable world) and
materialOutput (Ground materials). Each output is a 64x64 byte array. Material
IDs cover 128x128 world pixels and are categorical: 0 sand, 1 gravel, 2 hardpan,
3 asphalt. IDs 0-255 are stored unchanged. Unassigned IDs are flagged in the
editor and use the catalog's fallback art and driving surface (currently sand).
The catalog lives in maps/materials.json; texture indexes reference the current
four ground swatches. Additional IDs can map to these swatches; adding new art
also requires extending the swatch extraction in tools/wasteland_assets.py.

Start with the Natural ground preset (also maps/recipes/natural-ground.json).
Its Value noise -> Stepped LUT -> Ground materials branch turns the input into
value bands, then interprets those values as material IDs. Position 0 is fixed;
its output is editable. Click the LUT histogram to add up to 255 movable points.
Select a point to edit its preview color and value/ID or delete it. Each point changes the output from its position
onward. Constant field creates a uniform base. Paint field value replaces
values wherever its mask is 1; chain these nodes for more material areas.
Select a Ground materials node and choose Use as ground output. The Playable
world node remains the wall/floor output. Pin material settings while previewing
Final world / Game textures to tune areas live. Material edges follow the 64x64
cells; no blending is applied. Wall and settlement artwork retain their own
textures, including the sand already drawn into the settlement stamps.

Town roads
~~~~~~~~~~
Use the Natural ground + town roads preset, or connect Playable world -> Town
roads and select the latter as the wall/floor output. Ground materials remain
independent. Pin the road settings while previewing Final world / Game textures.
The node runs one breadth-first search from the starting town, then follows the
same parent tree from every other town. Equal-cost cardinal steps give shortest
valid routes; ties use stable N/E/S/W ordering. There are no terrain preferences.
Connections use N/E/S/W bits in one byte per logical cell.
Roads do not change walls, placements or ground IDs. The material overlay changes
both ground art and grip; it supports the same 0-255 IDs and fallback catalog.
Road width is a single value from 8-256 world pixels, sampled at the game's
8px tile resolution. Width variation is disabled to keep GBA runtime cost low.
Old min/max exports import at the midpoint, rounded to an 8px tile (equal limits
retain their original value). The active export uses 160px instead of 153-170.
Wide roads extend into neighbouring cells, with walls and settlement artwork
retaining priority. Narrow passages can therefore clip the requested width.
Axis-aligned segments have rounded joins. Their anchors sit south of the town buildings;
north approaches at town cells are excluded, with routes using their open plazas.
The paths are shortest on this valid road graph. They are not diagonal paths or
smoothed splines. Rebuild to use exported road settings in the game.

The Town roads catalog entry demonstrates constant-width roads and ground settings.
Run ./build.ps1 after saving to include it in the ROM.
Current full terrain previews are artifacts/map_editor/roads-full-map.png and
active-full-map.png. Road storage in the shared source is 4,104 bytes;
the generation workspace is 45,136 bytes and reuses the existing flood queue.
Road search runs only while generating the map. Tile/grip lookup checks four
surrounding anchors with integer arithmetic; there is no width noise,
interpolation or runtime width grid. See artifacts/test-results.json for
measured GBA frame timing. Default recipes without this node retain
their existing appearance and allocate no persistent road grid.

Version 1 recipes keep the original 512px patch rules and sand around outposts.
Assigning a ground output switches to version 2 and makes its IDs authoritative
for floor art and grip, including ground around settlements. The Ground materials
inspector offers Use original ground rules to switch back. Deleting the active
ground output also restores those legacy rules; Undo restores the output.
Sand/gravel use dirt grip and drag; hardpan/asphalt use road handling.

Operations: random fill; arbitrary cellular birth/survival rules, 4/8 neighbours,
0-32 iterations, optional update mask and border; radial field; threshold;
wall-mask union/intersection/subtraction/XOR; weighted field blend with optional
mask; invert; largest four-connected floor; integer value noise with octaves;
diamond-square plasma; squared Voronoi nearest-site / F2-F1 distance; and a
Playable world finalizer. Source nodes have stable independent random streams.
The CA iteration preview is temporary and does not alter the exported recipe.
The finalizer enforces a two-cell solid border, retains connected floor, reports
fallback clearing use, and carves the original spawn and six outpost approaches.

To use a recipe in the ROM:
  1. Create or load a map in the workshop and choose its final outputs.
  2. Turn on Include in game and press Save or Save As.
  3. Run ./build.ps1, then ./test.ps1 and playtest the resulting ROM.
The local server writes maps/map-library.json. The asset generator compiles every
enabled entry into include/generated/wasteland_recipe.h.
Do not hand-edit the generated header. The ROM executes the recipe at runtime;
no layout bitmap is baked into it. Each entry always uses its saved seed. The
default Wasteland entry has seed 12648431, fixed road width 160px, an independent
ground-material branch, spawn points and decoration. Standalone JSON import and
export remain available for exchange and backups; they do not change the shared
catalog until saved through the workshop.
Graph positions and labels are editor-only; unconnected branches are not exported.

Both recipe versions are bounded: 64x64 logical cells, 32 total nodes, six live
4 KiB grids per output. The two programs run sequentially in the same workspace. The executor reuses buffers after their last consumer. CPU cost depends
on the operations and iteration counts. Browser timing is not a GBA estimate.
Arbitrary recipes still need clearance, settlement-spacing and driving playtests;
the editor renders terrain but does not simulate vehicles or gameplay.
The existing gameplay routes assume the original layout, so a substantially
different exported recipe may require new controller-driven test routes.

Run ./test-map-editor.ps1 -NoGba to rebuild and test just the dev tool (native
and WebAssembly checks, with no GBA compilation or emulator run).
Run ./test-map-editor.ps1 for native/WebAssembly/GBA parity. It compiles a separate
diagnostic ROM in build/, runs it in mGBA, and compares every result byte for 339
cases, including every preset stage, extreme seeds, masks, and 128 historical
maps with their placements. It also checks graph validation, buffer liveness,
rules, flood-fill ties and fallback behavior. Seven rendered maps are compared
against native output across all 1,048,576 tile references; sampled tile/surface
signatures also run on GBA. Full PNG files are decoded and their source pixels
checked. It does not change dist/dustline.gba.
For the DOM integration checks (no browser rendering), install the pinned test
helper and run:
  npm install --prefix build/map-editor-ui --no-save --package-lock=false jsdom@26.1.0
  node tools/test_map_editor_ui.mjs
To test the Natural ground catalog entry:
  docker run --rm --mount "type=bind,source=$PWD,target=/work" dustline-build:1 python3 tools/test_material_rom.py
Run ./test-map-editor.ps1 first for its render fixtures; ./test.ps1 supplies the
emulator bridge. For Town roads, run the same Docker command with
tools/test_road_rom.py. It also checks driving across the road
overlay and the additional grid allocation/release.
The separate material-ROM smoke test checks terrain pixels, grip, restart,
scene release and a short controller-driven route; subjective handling still
needs human playtesting.
Reports and editor screenshots live in artifacts/map_editor/. Generated editor
engine files live in tools/map_editor/generated/ and are ignored by Git.

VERIFY
------
After building:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1

The test script runs the actual dist ROM in headless libmGBA 0.10.1, sends
normal GBA joypad input, and reads exported telemetry through ELF symbols.
It never teleports the car or writes game state to make tests pass.

It checks title catalog enumeration, every enabled map's fixed seed, repeatable
generation, acceleration, camera look-ahead, pause and frame budget. Exact
results and peak timings are recorded in artifacts/test-results.json, excluding
car, UI and particles from terrain pixel comparisons.
The procedural generator has a 128-seed host sweep: determinism, independent
four-connected flood-fill verification, placement separation, car clearance,
and traversable coarse-cell links. ROM tests compare the GBA's seed/signature
with that same host generator, exercise Yes/No and repeated town visits, exact
return coordinates, held-button protection, catalog switching, canyon collisions
and rendered pixels. Loading is separate from driving-frame profiling.
Tests also check the visible town artwork above its prompt, every overview
cell, town dots, player-marker alignment, one-upload stability while driving,
newly exposed HUD space, and town-only setup controls. Settings tests cover the
four image zooms, frozen motion, held-button
protection, town/map persistence, unchanged driving VRAM and frame timing.
Combat tests check three-hit destruction, enemy movement/firing, health and shield,
terrain impacts, bounded projectiles, menu freezing and town persistence.
Traffic tests leave the player idle for 25 seconds, verify ongoing enemy motion,
vehicle sensing, forward-only fire and separation, then ram using joypad input.
Host tests exercise the exact rectangle/impulse math with 25 mass combinations:
momentum, energy loss, glancing hits, separation and terrain-pinned contacts.
The same 128-seed sweep verifies unique, reachable encounter anchors and sector
coverage. Spawning tests kill a car, wait through its cooldown, then drive out
of the district and back using joypad input. They check five-slot ownership,
despawning, off-screen activation, expired-kill respawn and damaged-survivor HP.
See the current results JSON for exact check counts and frame timings;
these are measured routes, not worst-case guarantees for every seed/system.

Evidence:
  artifacts/test-results.json  Assertions, telemetry, and tested ROM SHA-256
  artifacts/title.png         Native emulator title screenshot
  artifacts/driving.png       Native emulator driving screenshot
  artifacts/controls.png      Native emulator help screenshot
  artifacts/cornering.png     Native emulator cornering screenshot
  artifacts/wasteland/       Catalog snapshot, overview, tiles, emulator captures,
                              generated seed fixtures and art budget report
  artifacts/settings/        Settings menu and all four minimap zoom captures
  artifacts/combat/          Enemy/gunfire captures, route GIF and combat results
  artifacts/spawning/        Cooldown, streaming and damaged-survivor captures
  artifacts/traffic/         Anti-idle manoeuvres GIF, ram capture and results

Screenshots also have nearest-neighbor 4x versions. Actual rendering is
240 x 160 at the GBA's approximately 59.73 Hz. The GIF is sampled, so it does
not represent the display frame rate. Speed units are an arcade display
scale, not a real-world vehicle simulation.

These checks establish a working ROM and consistent mechanics. Subjective
handling feel and audio balance still need your controller playtest. This
build has not been tested on a physical cartridge or inside your RetroArch
installation. Its native ROM was verified using the mGBA emulator core.

PROCEDURAL WASTELAND PIPELINE
-----------------------------
See maps/overworld/README.md for generation rules and art provenance.
maps/overworld/wasteland-kit-muted.png and wasteland-details-muted.png are the
current environment sources, generated with the built-in image tool from the
supplied muted wasteland style reference. muted-art-prompts.txt records both
prompts. The build extracts, downsamples, quantizes and deduplicates the art
through tools/wasteland_assets.py and tools/generate_assets.py. The earlier
source kit and maps/open_world/wasteland.png are preserved.
Four ground materials and both wall textures repeat at 32px. Town stamps are
64px; grass, scrub, rocks and twigs use transparent 16px patches. The editor's
Game textures / Full map render views use the same artwork as the ROM.
artifacts/wasteland/muted-art-proof.png shows 3x3 texture repeats and all four
details composited over each ground material. Alpha is binary on the GBA.

The on-GBA generator operates on a 64 x 64 byte grid, one cell per 128 world
pixels. It seeds 47% walls, applies five 4/5-neighbour smoothing passes, keeps
the largest four-connected floor region, then adds connected spawn/outpost
clearings. Convex wall corners round inward on the same 8px grid used for
graphics and collision. All coarse floor remains open; passages are at least
128px wide before the car footprint. Sand/gravel are slower dirt; hardpan and
rare asphalt patches use road grip. Surface boundaries are deliberately simple
patches, not an authored road network. Town icons have small solid footprints
north of their accessible entrances. Future required objects must be placed
in this retained floor region and checked against those footprints.

Persistent layout is 4,168 bytes, plus 4,096 bytes for a version 2 ground output
and 4,104 bytes when Town roads is enabled. The bounded recipe workspace is
45,136 bytes (six grid buffers, 12,288 bytes of scratch, a staging layout and
road grid) and is freed before scene graphics load. There is no full 8k bitmap in RAM/ROM.
Terrain pixels and collision are evaluated from the coarse layout as needed.
180 unique 8px artwork tiles fit a 192-slot reservation: 12 KiB terrain VRAM,
18 KiB including the streamed map and driving HUD. The modal adds 4 KiB; the
decoration layer adds 6 KiB of background VRAM and about 4.5 KiB of streaming RAM.
The complete wasteland tile set uploads during scene loading and stays resident.
Driving updates only newly exposed tile-map rows/columns, with no artwork
eviction or whole-view cache pinning.
Wasteland HUD, pause, town screens and decoration now use 4bpp. Decoration pixel
data shrinks from 1,088 to 544 bytes; its allocated VRAM still rounds up to a
2 KiB block, so normal driving remains at 24 KiB total background allocation.
UI pixel storage is also halved (maps remain 16-bit). Lossless RGB5 palette
compaction fits the muted terrain palette into 80 entries, leaving separate
16-colour banks for UI and scenery. Terrain stays 8bpp: 91/180 current tiles
need more than 15 opaque colours.
Its density/settings occupy 4,120 bytes, and saved spawn coordinates use 1,036
bytes. The temporary spawn weight field is freed after generation. Decoration
art has 17 transparent 8px tiles with its own muted 16-colour palette bank. The
blank town uses only 4 KiB total background VRAM. The zoomable 64x64 overview uses
2 KiB of sprite VRAM, 2 KiB of staging RAM, a 4 KiB source image and a dedicated
16-color palette. Five enemy dots share one 32-byte tile and the existing sprite
palette; the circle masks take 4 KiB of ROM. Combat uses five
existing directional car frames, a shared enemy palette, small HP/effect sprites,
and fixed pools of 24 bullets, two missiles and six traps. Its simulation state
is 4,716 bytes in a single
boot-time EWRAM allocation (not on the small internal stack), with separate
small sprite handles; there is no per-frame allocation or unbounded projectile
list. All AI and weapon simulation is fixed-point and separate from presentation.
Diagnostic telemetry lives in EWRAM to preserve the small internal stack.
This includes a 3,100-byte bounded encounter table (capacity 258; 12 bytes per
anchor plus a count). Inactive anchors run no physics or AI. Nearby anchors are
scanned every eight driving frames and at most one car is activated per scan.
Wasteland overview generation reads only wall cells and road-connection bits;
there are no terrain/material samples while driving. Zoomed crops reuse packed
rows and precomputed circle masks, updating only on display-pixel crossings.
Town entry releases the terrain renderer and radar, retaining only the run
layout, car/camera state and shared UI/car/particle resources. Returning rebuilds
graphics from that same layout; it does not reroll the world. Selecting a new
catalog entry releases the previous layout and regenerates from the saved seed.

This is a first reusable art pass: texture repetition, coarse map-scale shapes,
simple material boundaries and conservative town hitboxes remain visible.
The layout is connected, but route variety, travel times, wall readability and
cornering comfort need human controller testing. No world/seed persistence yet.

PROJECT FILES
-------------
AGENTS.md                  Development direction and agent instructions
Makefile                   GBA build configuration
build.ps1 / test.ps1        Build and emulator verification entry points
include/driving.h          Vehicle data, tuning presets, and physics interface
src/driving.bn_iwram.cpp   Motion, surfaces, and collision response (ARM hot loop)
src/main.cpp               Input, camera, presentation, lap rules, and audio
tools/generate_assets.py   Original procedural graphics, map data, and audio
src/world_map.cpp          Selected scene, ROM tile lookup and surface queries
src/terrain_streamer.bn_iwram.cpp  Terrain tile cache and VBlank uploads
maps/map-library.json      Shared editor and ROM map catalog
tools/compile_recipe.py    Catalog validation and generated C++ recipe compiler
tools/serve_map_editor.py  Loopback editor server and atomic catalog save API
tools/emulator_bridge.c    Thin headless mGBA adapter for integration tests
tools/test_rom.py          Joypad-driven checks and capture generation
include/cave_layout.h      Shared integer cellular automaton and flood fill
src/wasteland.cpp          Runtime procedural tiles and surface queries
src/local_minimap.bn_iwram.cpp Zoomable wasteland image / enemy dots / local radar
tools/wasteland_assets.py  Reference-derived tile kit compiler and budget report
tools/town_assets.py       Native town backgrounds and walking sprite generation
include/town_scene.h       Walkable town/interior state and interaction interface
src/town_scene.cpp         Town movement, collision, doors and mechanic menu
tools/test_town_scene.py   Controller-driven town/garage vertical-slice test
tools/test_cave_layout.cpp Host seed sweep, clearance checks and seed export
tools/test_wasteland.py    Procedural graphics and town lifecycle ROM tests
tools/test_settings.py     Paused settings, zoom levels and persistence ROM tests
include/combat.h           Combat limits, enemy/bullet state and weapon tuning
src/combat.cpp             Fixed-point enemy driving, weapons and damage
src/combat_view.cpp        Existing car art, HP pips, bullets and destruction FX
tools/test_combat.py       Joypad-driven combat and scene-lifecycle checks
include/enemy_spawns.h     Seeded reachable encounter anchors and compact state
tools/test_spawning.py     Cooldown, off-screen spawning and out/back streaming tests
include/vehicle_contact.h  Shared fixed-point rectangular contact/impulse solver
tools/test_vehicle_contact.cpp Host contact and mass-response tests
tools/test_traffic.py      Anti-idle AI, car sensing, front guns and ram ROM tests
tools/Dockerfile           Isolated compiler and test dependencies

Generated graphics/, audio/, and include/generated/ are deliberately ignored
by Git. Regenerate them through build.ps1. The asset generator is their source
of truth. Tuning acceleration, grip, top speed, and steering starts in
include/driving.h.

CREDITS / THIRD-PARTY SOFTWARE
-----------------------------
Game-specific code, pixel artwork, font, layout, and synthesized sounds were
created for this project. There are no extracted commercial-game assets.

Butano by Gustavo Valiente and contributors:
  https://github.com/GValiente/butano
devkitARM / devkitPro:
  https://devkitpro.org/
mGBA by endrift and contributors (test tooling):
  https://mgba.io/
Pillow (asset generation and screenshots):
  https://python-pillow.org/

dist/licenses contains Butano's upstream dependency notices. Some notices
cover optional backends not enabled by this build. Game-specific code has
not been assigned a public redistribution license; choose one before a
public source release if desired.
