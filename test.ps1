$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path 'dustline.elf')) { throw 'Run ./build.ps1 first.' }
$mount = "type=bind,source=$PSScriptRoot,target=/work"
docker run --rm --mount $mount dustline-build:1 python3 tools/test_map_storage.py
if ($LASTEXITCODE -ne 0) { throw 'Build audit regression tests failed.' }

docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_map_recipe.cpp -o build/test_map_recipe
if ($LASTEXITCODE -ne 0) { throw 'Could not compile recipe tests.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Iinclude tools/map_recipe_bridge.cpp -o build/map_recipe_bridge
if ($LASTEXITCODE -ne 0) { throw 'Could not compile active recipe reference.' }

docker run --rm --mount $mount dustline-build:1 ./build/test_map_recipe
if ($LASTEXITCODE -ne 0) { throw 'Recipe kernel tests failed.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_placement.cpp -o build/test_placement
if ($LASTEXITCODE -ne 0) { throw 'Could not compile placement tests.' }
docker run --rm --mount $mount dustline-build:1 ./build/test_placement
if ($LASTEXITCODE -ne 0) { throw 'Placement tests failed.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_vehicle_contact.cpp -o build/test_vehicle_contact
if ($LASTEXITCODE -ne 0) { throw 'Could not compile vehicle contact tests.' }
docker run --rm --mount $mount dustline-build:1 ./build/test_vehicle_contact
if ($LASTEXITCODE -ne 0) { throw 'Vehicle contact physics tests failed.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_terrain_cache.cpp -o build/test_terrain_cache
if ($LASTEXITCODE -ne 0) { throw 'Could not compile tile cache stress test.' }
docker run --rm --mount $mount dustline-build:1 ./build/test_terrain_cache
if ($LASTEXITCODE -ne 0) { throw 'Tile cache stress test failed.' }

docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_chunk_cache.cpp -o build/test_chunk_cache
if ($LASTEXITCODE -ne 0) { throw 'Could not compile chunk compression test.' }
docker run --rm --mount $mount dustline-build:1 ./build/test_chunk_cache
if ($LASTEXITCODE -ne 0) { throw 'Chunk compression test failed.' }
docker run --rm --mount $mount dustline-build:1 gcc -shared -fPIC -O2 tools/emulator_bridge.c -o build/emulator_bridge.so -lmgba
if ($LASTEXITCODE -ne 0) { throw 'Could not compile headless mGBA adapter.' }
docker run --rm --mount $mount dustline-build:1 g++ -std=c++17 -O2 -Wall -Wextra -Iinclude tools/test_cave_layout.cpp -o build/test_cave_layout
if ($LASTEXITCODE -ne 0) { throw 'Could not compile cave generator tests.' }
docker run --rm --mount $mount dustline-build:1 ./build/test_cave_layout
if ($LASTEXITCODE -ne 0) { throw 'Cave connectivity test failed.' }
docker run --rm --mount $mount dustline-build:1 python3 tools/test_rom.py
if ($LASTEXITCODE -ne 0) { throw 'ROM verification failed; see artifacts/test-results.json and captures.' }
