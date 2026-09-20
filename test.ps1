$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path 'dustline.elf')) { throw 'Run ./build.ps1 first.' }
$mount = "type=bind,source=$PSScriptRoot,target=/work"
docker run --rm --mount $mount dustline-build:1 gcc -shared -fPIC -O2 tools/emulator_bridge.c -o build/emulator_bridge.so -lmgba
if ($LASTEXITCODE -ne 0) { throw 'Could not compile headless mGBA adapter.' }
docker run --rm --mount $mount dustline-build:1 python3 tools/test_rom.py
if ($LASTEXITCODE -ne 0) { throw 'ROM verification failed; see artifacts/test-results.json and captures.' }
