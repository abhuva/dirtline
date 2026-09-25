# Walkable town vertical slice

`town-exterior-source.png`, `garage-interior-source.png`, and
`player-overhead-source.png` are original source art generated for Dustline from
the user's top-down town references. They are not loaded by the ROM directly.

`tools/town_assets.py` fits each source to a 256×256 native map, quantizes it to
15 opaque GBA colours plus the transparent palette entry. The player sheet is
cropped into twelve 16x32 foot-anchored frames and quantized to its own shared
15-colour sprite palette. `tools/generate_assets.py` writes the disposable
Butano BMP/JSON inputs under `graphics/`.

The first slice deliberately shares one exterior and garage across all six
outposts. Collision and interaction rectangles live in `src/town_scene.cpp`.
The exterior uses axis-aligned building footprints around a broad central street,
with a south overworld gate, a west-facing dispatch window, a mirrored eastern
race office, and a north garage
door. The interior uses matching rectangular fixture footprints, a south return
door, and an interactive mechanic counter.

Run `./build.ps1` after changing either source image or the generator. The
controller-only flow is verified by `tools/test_town_scene.py` and `./test.ps1`.
