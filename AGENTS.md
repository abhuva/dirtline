# Working on Dustline

This repository is an original Game Boy Advance driving/RPG prototype. The
deliverable is a real `.gba` ROM, playable with RetroArch's mGBA core.

## Direction

- First make driving satisfying: momentum, readable grip, throttle release,
  controlled slides, and distinct vehicle setups.
- Inspirations are Racing Gears Advance's handling and Car Battler Joe's
  progression. Use original code, art, audio, names, and world design.
- Keep a fixed elevated 2D view. Do not add Mode 7 or a 3D renderer.
- Add RPG systems only after the driving has been playtested.

## Engineering

- C++ and Butano, built with devkitARM. Pin external dependencies.
- `src/` contains runtime code; `include/` contains interfaces and tuning.
- `tools/generate_assets.py` is the source of procedural pixel art, track data,
  and synthesized sound. Generated files live in `graphics/`, `audio/`, and
  `include/generated/`; regenerate rather than hand-edit those outputs.
- Keep physics independent of presentation. Use fixed point on the GBA.
- The simulation runs at one step per GBA frame, approximately 59.73 Hz.
- Windows paths may contain spaces. The Docker build mounts the project at
  `/work`; do not move the user's checkout or alter global PATH settings.
- Run `./build.ps1` after code or asset changes. Never call a compile a playtest.
- For handling or gameplay changes, run `./test.ps1` and inspect emulator
  captures. Record remaining subjective playtesting needs honestly.
- Keep `readme.txt` accurate, including controls, build instructions, limitations,
  and the location of the playable ROM.
- Do not commit `.tools/`, `build/`, emulator saves, or local logs. Release ROMs
  and test screenshots belong in `dist/` and `artifacts/` respectively.
- Preserve user work and never publish a remote repository without instruction.
