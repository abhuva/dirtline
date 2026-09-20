DUSTLINE - PROVING GROUNDS
Playable Game Boy Advance driving prototype / version 0.1

PLAY
----
Open dist/dustline.gba in RetroArch using the Nintendo - Game Boy Advance
(mGBA) core. Use Load Content to select the file directly; a database scan
may not recognize an original homebrew game. No base game or ROM patch is
needed. A separate GBA BIOS is optional with mGBA.

Press A at the title screen. Drive east across the starting straight and
follow the circuit. Complete the nine ordered checkpoint regions, then
cross the checkered line eastbound to record a lap. The minimap shows your
position. The lower HUD counts the checkpoint regions you have passed.

CONTROLS (GBA BUTTONS, AS MAPPED IN YOUR EMULATOR)
------------------------------------------------
A               Accelerate
B               Brake; keep holding to reverse once stopped
Left / Right    Steer relative to the car (steering reverses while backing up)
L / R           Previous / next vehicle setup; restarts the current run
Select          Reset car and current run to the start
Start           Pause / controls screen; press again to resume

Up and Down have no driving function. Reverse uses B, not Down.

TRY THIS FIRST
--------------
Build speed on the straight, release A before a bend, steer into it, and
apply throttle again as you come out. You retain momentum while coasting.
There is no tap-frequency bonus: deliberate throttle timing is the goal.
The car has separate heading and velocity, so its nose can point slightly
away from its direction of travel. Watch the skid marks during a fast turn.
If you get stuck, Select resets instantly.

Press L/R to compare:
  GRIP   - forgiving cornering grip, moderate power.
  RALLY  - default; more power and speed, looser cornering.
  HEAVY  - slower acceleration and steering, more persistent momentum.

Changing setups resets the lap and checkpoint progress so a lap cannot mix
setups. Each setup retains its own best time during the current session.
Select also preserves session bests. Closing/resetting the emulator clears
these records; cartridge save support is not implemented yet.

WHAT IS IN THIS DEMO
--------------------
- Native GBA ROM, C++ / Butano / devkitARM.
- Original 1024 x 1024 scrolling circuit: straight with cones, linked bends,
  tight hairpin, dirt section, grass runoff, and a workshop building.
- 64-direction pixel-art car with a fixed elevated view; no 3D renderer.
- Fixed-point momentum, speed-dependent steering, grip-limited sliding,
  braking, reverse, and different drag/grip on asphalt, dirt, and grass.
- Collisions with cones, tire stacks, the workshop, and the outer boundary.
  Small green shrubs are drive-through ground decoration.
- Camera look-ahead, minimap, speed display, lap timer, and session bests.
- Skid/dust particles and simple synthesized engine, tire, impact, and UI sounds.
- Title screen, pause/help screen, and instant run reset.

This is the driving foundation for an original vehicle-adventure RPG,
inspired by Racing Gears Advance's handling and Car Battler Joe's vehicle
progression. It does not reproduce either game's code, artwork, sound,
maps, names, or exact physics. No combat, enemies, quests, inventory,
persistent progression, or garage upgrades are implemented yet.

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
No remote Git repository is created and no global PATH is changed.

To force a clean rebuild:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Clean

Do not edit .tools/butano to tune the game. It is an ignored external
dependency, pinned to commit c66094ae514c74068f992a4896c5e1f234e9f6e2.
The devkitpro/devkitarm base is pinned by SHA-256 digest in tools/Dockerfile.
The compiler reports devkitARM GCC 16.1.0. Debian helper packages are obtained
from Bookworm repositories when the local image is first built; their patch
versions are not frozen, so a future rebuild is not promised byte-identical.

VERIFY
------
After building:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1

The test script runs the actual dist ROM in headless libmGBA 0.10.1, sends
normal GBA joypad input, and reads exported telemetry through ELF symbols.
It never teleports the car or writes game state to make tests pass.

It checks boot, acceleration, coasting, reverse, steering, throttle-release
behavior, pause, setup changes, boundary collisions, checkpoint gating,
and a complete controller-driven lap. It also measures the frame budget.
The recorded lap completed without collisions or missed refreshes; peak
reported CPU use during that lap was about 55% of one frame.

Evidence:
  artifacts/test-results.json  Assertions, telemetry, and tested ROM SHA-256
  artifacts/title.png         Native emulator title screenshot
  artifacts/driving.png       Native emulator driving screenshot
  artifacts/controls.png      Native emulator help screenshot
  artifacts/cornering.png     Native emulator cornering screenshot
  artifacts/dirt.png          Emulator capture at the dirt transition
  artifacts/lap-complete.png  Completed lap
  artifacts/demo.gif          Controller-driven lap capture (2x, ~10 fps)
  artifacts/track.png         Generated track overview, not an emulator capture

Screenshots also have nearest-neighbor 4x versions. Actual rendering is
240 x 160 at the GBA's approximately 59.73 Hz. The GIF is sampled, so it does
not represent the display frame rate. Speed units are an arcade display
scale, not a real-world vehicle simulation.

These checks establish a working ROM and consistent mechanics. Subjective
handling feel and audio balance still need your controller playtest. This
build has not been tested on a physical cartridge or inside your RetroArch
installation. Its native ROM was verified using the mGBA emulator core.

PROJECT MAP
-----------
AGENTS.md                  Development direction and agent instructions
Makefile                   GBA build configuration
build.ps1 / test.ps1        Build and emulator verification entry points
include/driving.h          Vehicle data, tuning presets, and physics interface
src/driving.cpp            Motion, surfaces, and collision response
src/main.cpp               Input, camera, presentation, lap rules, and audio
tools/generate_assets.py   Original procedural graphics, map data, and audio
tools/emulator_bridge.c    Thin headless mGBA adapter for integration tests
tools/test_rom.py          Joypad-driven checks and capture generation
tools/Dockerfile           Isolated compiler and test dependencies

Generated graphics/, audio/, and include/generated/ are deliberately ignored
by Git. Regenerate them through build.ps1. The asset generator is their source
of truth. Tuning acceleration, grip, top speed, and steering starts in
include/driving.h. Changing the track starts with WAYPOINTS in the generator;
rendering, surfaces, and test-driver paths share that definition.

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
