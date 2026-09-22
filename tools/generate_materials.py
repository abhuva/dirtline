"""Generate the shared material-ID catalog; art swatches remain in wasteland_assets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate():
    catalog = json.loads((ROOT / 'maps/materials.json').read_text())
    entries = {entry['id']: entry for entry in catalog['materials']}
    assert len(entries) == len(catalog['materials']) and catalog['fallback'] in entries
    for key, entry in entries.items():
        assert type(key) is int and 0 <= key <= 255
        assert type(entry['texture']) is int and 0 <= entry['texture'] < 4
        assert entry['surface'] in (1, 2)
    fallback = entries[catalog['fallback']]
    header = '#pragma once\n#include <cstdint>\nnamespace ground_materials {\n'
    for name, values in (
        ('textures', [entries.get(i, fallback)['texture'] for i in range(256)]),
        ('surfaces', [entries.get(i, fallback)['surface'] for i in range(256)]),
        ('registered', [int(i in entries) for i in range(256)]),
    ):
        header += f'inline constexpr uint8_t {name}[256]={{'+','.join(map(str, values))+'};\n'
    output = ROOT / 'include/generated/ground_materials.h'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header+'}\n')
    return catalog


if __name__ == '__main__':
    generate()
