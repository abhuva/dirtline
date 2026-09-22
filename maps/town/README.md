# Walkable town vertical slice

`town-exterior-source.png` and `garage-interior-source.png` are original source
art generated for Dustline from the user's desert settlement style reference.
They are not loaded by the ROM directly.

`tools/town_assets.py` fits each source to a 256×256 native map, quantizes it to
15 opaque GBA colours plus the transparent palette entry, and generates the
walking player sprite. `tools/generate_assets.py` writes the disposable Butano
BMP/JSON inputs under `graphics/`.

The first slice deliberately shares one exterior and garage across all six
outposts. Collision and interaction rectangles live in `src/town_scene.cpp`.
The exterior has a south overworld gate and a north garage door. The interior
has a south return door and an interactive mechanic counter.

Run `./build.ps1` after changing either source image or the generator. The
controller-only flow is verified by `tools/test_town_scene.py` and `./test.ps1`.
