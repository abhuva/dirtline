param([switch]$NoBuild, [switch]$NoGba)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $NoBuild) { & ./map-editor.ps1 -BuildOnly }
$mount = "type=bind,source=$PSScriptRoot,target=/work"
New-Item -ItemType Directory -Force build | Out-Null
node tools/test_map_editor.mjs --prepare
if ($LASTEXITCODE -ne 0) { throw 'Editor graph/compiler checks failed.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_map_recipe.cpp -o build/test_map_recipe
if ($LASTEXITCODE -ne 0) { throw 'Recipe test compilation failed.' }
docker run --rm --mount $mount dustline-build:1 ./build/test_map_recipe
if ($LASTEXITCODE -ne 0) { throw 'Recipe kernel checks failed.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/map_recipe_bridge.cpp -o build/map_recipe_bridge
if ($LASTEXITCODE -ne 0) { throw 'Native recipe bridge compilation failed.' }
docker run --rm --mount $mount dustline-build:1 python3 tools/test_map_recipe.py
if ($LASTEXITCODE -ne 0) { throw 'Native recipe fixtures or historical baseline failed.' }
node tools/test_map_editor.mjs
if ($LASTEXITCODE -ne 0) { throw 'Native / WebAssembly parity failed.' }
node tools/test_map_render.mjs
if ($LASTEXITCODE -ne 0) { throw 'Native / WebAssembly tile rendering failed.' }
docker run --rm --mount $mount dustline-build:1 python3 tools/test_map_render.py
if ($LASTEXITCODE -ne 0) { throw 'Full-map PNG verification failed.' }
node tools/test_placement.mjs
if ($LASTEXITCODE -ne 0) { throw 'Placement preview parity failed.' }
docker run --rm --mount $mount dustline-build:1 python3 tools/test_placement_render.py
if ($LASTEXITCODE -ne 0) { throw 'Placement PNG verification failed.' }
if ($NoGba) { Write-Host 'Dev-tool checks complete. GBA build and emulator checks skipped.'; return }

docker run --rm --mount $mount dustline-build:1 /opt/devkitpro/devkitARM/bin/arm-none-eabi-g++ tools/map_recipe_bridge.cpp -Iinclude -Ibuild/map-recipe-tests -DMAP_RECIPE_GBA_PROBE -std=c++17 -O2 -mthumb -mthumb-interwork -fno-exceptions -fno-rtti '-specs=gba.specs' -o build/map_recipe_probe.elf
if ($LASTEXITCODE -ne 0) { throw 'GBA recipe probe compilation failed.' }
docker run --rm --mount $mount dustline-build:1 /opt/devkitpro/devkitARM/bin/arm-none-eabi-objcopy -O binary build/map_recipe_probe.elf build/map_recipe_probe.gba
if ($LASTEXITCODE -ne 0) { throw 'GBA recipe probe conversion failed.' }
docker run --rm --mount $mount dustline-build:1 /opt/devkitpro/tools/bin/gbafix build/map_recipe_probe.gba
if ($LASTEXITCODE -ne 0) { throw 'GBA recipe probe header fix failed.' }
docker run --rm --mount $mount dustline-build:1 gcc -shared -fPIC -O2 tools/emulator_bridge.c -o build/map_recipe_emulator_bridge.so -lmgba
if ($LASTEXITCODE -ne 0) { throw 'mGBA bridge compilation failed.' }
docker run --rm --mount $mount dustline-build:1 python3 tools/test_map_recipe_gba.py
if ($LASTEXITCODE -ne 0) { throw 'GBA / native recipe parity failed.' }
