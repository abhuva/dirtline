"""Validation and canonicalization for per-map GBA art banks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / 'maps/art-assets.json'

DEFAULT_PROFILE = {
    'materials': [
        {'id': 0, 'asset': 'sun-sand', 'enabled': True},
        {'id': 1, 'asset': 'sun-gravel', 'enabled': True},
        {'id': 2, 'asset': 'sun-hardpan', 'enabled': True},
        {'id': 3, 'asset': 'sun-asphalt', 'enabled': True},
    ],
    'decorations': [
        {'asset': 'dry-grass', 'enabled': True},
        {'asset': 'low-shrub', 'enabled': True},
        {'asset': 'pebbles', 'enabled': True},
        {'asset': 'dry-twigs', 'enabled': True},
    ],
    'wallSet': 'sun-canyon',
    'townSet': 'frontier',
}

THEME_PROFILES = {
    'sun': DEFAULT_PROFILE,
    'rust': {
        'materials': [{'id': i, 'asset': key, 'enabled': True} for i, key in enumerate(
            ('rust-dust', 'rust-gravel', 'rust-hardpan', 'rust-asphalt'))],
        'decorations': [{'asset': key, 'enabled': True} for key in
            ('wire-grass', 'rust-scrap', 'oil-brush', 'iron-shards')],
        'wallSet': 'rust-ridge', 'townSet': 'rustworks',
    },
    'ash': {
        'materials': [{'id': i, 'asset': key, 'enabled': True} for i, key in enumerate(
            ('ash-dust', 'ash-gravel', 'ash-hardpan', 'ash-asphalt'))],
        'decorations': [{'asset': key, 'enabled': True} for key in
            ('ash-tuft', 'cinder-shrub', 'char-stones', 'dead-branches')],
        'wallSet': 'ash-cliff', 'townSet': 'ashpost',
    },
    'salt': {
        'materials': [{'id': i, 'asset': key, 'enabled': True} for i, key in enumerate(
            ('salt-crust', 'salt-shingle', 'salt-hardpan', 'salt-road'))],
        'decorations': [{'asset': key, 'enabled': True} for key in
            ('salt-grass', 'blue-shrub', 'salt-chunks', 'driftwood')],
        'wallSet': 'salt-bluff', 'townSet': 'salt-harbor',
    },
    'verdant-machine': {
        'materials': [{'id': i, 'asset': key, 'enabled': True} for i, key in enumerate(
            ('lush-grass', 'forest-moss', 'factory-yard', 'machine-road'))],
        'decorations': [{'asset': key, 'enabled': True} for key in
            ('fern-clump', 'wild-flowers', 'pipe-scrap', 'machine-vent')],
        'wallSet': 'forest-works', 'townSet': 'greenworks',
    },
}


def load_catalog():
    catalog = json.loads(CATALOG_PATH.read_text())
    if catalog.get('version') != 1:
        raise ValueError('Unsupported art asset catalog')
    for group in ('materials', 'decorations', 'wallSets', 'townSets'):
        values = catalog.get(group)
        if not isinstance(values, list) or not values:
            raise ValueError(f'Art catalog needs {group}')
        keys = [value.get('key') for value in values]
        if len(set(keys)) != len(keys) or not all(isinstance(key, str) and key for key in keys):
            raise ValueError(f'Art catalog has invalid or duplicate {group} keys')
        for value in values:
            transform=value.get('transform')
            if not isinstance(transform,list) or len(transform)!=6 or not all(type(component) in (int,float) for component in transform):
                raise ValueError(f'Art asset {value.get("key")} needs a six-value RGB transform')
    for value in catalog['materials']:
        if type(value.get('base')) is not int or not 0<=value['base']<4 or value.get('surface') not in (1,2):
            raise ValueError(f'Material asset {value.get("key")} has invalid source or surface')
    for value in catalog['decorations']:
        if type(value.get('base')) is not int or not 0<=value['base']<4:
            raise ValueError(f'Decoration asset {value.get("key")} has invalid source')
    return catalog


def default_profile():
    return json.loads(json.dumps(DEFAULT_PROFILE))


def validate_profile(profile, catalog=None):
    catalog = catalog or load_catalog()
    if profile is None:
        profile = default_profile()
    if isinstance(profile, str):
        if profile not in THEME_PROFILES:
            raise ValueError(f'Unknown art profile preset: {profile}')
        profile = json.loads(json.dumps(THEME_PROFILES[profile]))
    if not isinstance(profile, dict):
        raise ValueError('Art profile must be an object')
    material_assets = {item['key']: item for item in catalog['materials']}
    decoration_assets = {item['key']: item for item in catalog['decorations']}
    wall_sets = {item['key'] for item in catalog['wallSets']}
    town_sets = {item['key'] for item in catalog['townSets']}
    materials = profile.get('materials')
    decorations = profile.get('decorations')
    if not isinstance(materials, list) or len(materials) != 4:
        raise ValueError('Art profile needs exactly four material slots')
    if not isinstance(decorations, list) or len(decorations) != 4:
        raise ValueError('Art profile needs exactly four decoration slots')
    ids = set()
    normalized_materials = []
    for slot, binding in enumerate(materials):
        if not isinstance(binding, dict) or type(binding.get('enabled', True)) is not bool:
            raise ValueError(f'Material slot {slot + 1} is invalid')
        enabled = binding.get('enabled', True)
        asset = binding.get('asset')
        material_id = binding.get('id')
        if asset not in material_assets:
            raise ValueError(f'Unknown material asset: {asset}')
        if type(material_id) is not int or not 0 <= material_id <= 255:
            raise ValueError(f'Material slot {slot + 1} ID must be 0-255')
        if enabled and material_id in ids:
            raise ValueError(f'Duplicate enabled material ID: {material_id}')
        if enabled:
            ids.add(material_id)
        normalized_materials.append({'id': material_id, 'asset': asset, 'enabled': enabled})
    if not ids:
        raise ValueError('Enable at least one ground material')
    normalized_decorations = []
    for slot, binding in enumerate(decorations):
        if not isinstance(binding, dict) or type(binding.get('enabled', True)) is not bool:
            raise ValueError(f'Decoration slot {slot + 1} is invalid')
        asset = binding.get('asset')
        if asset not in decoration_assets:
            raise ValueError(f'Unknown decoration asset: {asset}')
        normalized_decorations.append({'asset': asset, 'enabled': binding.get('enabled', True)})
    wall_set = profile.get('wallSet')
    town_set = profile.get('townSet')
    if wall_set not in wall_sets:
        raise ValueError(f'Unknown wall set: {wall_set}')
    if town_set not in town_sets:
        raise ValueError(f'Unknown town set: {town_set}')
    return {'materials': normalized_materials, 'decorations': normalized_decorations,
            'wallSet': wall_set, 'townSet': town_set}


def profile_key(profile, catalog=None):
    normalized = validate_profile(profile, catalog)
    payload = json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def profiles_for_entries(entries, catalog=None):
    catalog = catalog or load_catalog()
    profiles, indices, keys = [], {}, []
    for entry in entries:
        profile = validate_profile(entry['recipe'].get('artProfile'), catalog)
        key = profile_key(profile, catalog)
        if key not in indices:
            indices[key] = len(profiles)
            profiles.append(profile)
        keys.append(key)
    return profiles, indices, keys
