"""Shared map catalog validation and loopback persistence regression test."""
import copy
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import serve_map_editor
from compile_recipe import ROOT, validate_library


library = json.loads((ROOT / 'maps/map-library.json').read_text())
enabled = validate_library(copy.deepcopy(library))
assert len(enabled) == sum(entry['includeInGame'] for entry in library['maps'])

draft = {
    'id': 'empty-draft',
    'includeInGame': False,
    'recipe': {'version': 3, 'name': 'Empty draft', 'seed': 42, 'nodes': []},
}
with_draft = copy.deepcopy(library)
with_draft['maps'].append(copy.deepcopy(draft))
validate_library(with_draft)
with_draft['maps'][-1]['includeInGame'] = True
try:
    validate_library(with_draft)
    raise AssertionError('Enabled empty draft passed validation')
except ValueError as error:
    assert 'graph is empty' in str(error)

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / 'map-library.json'
    path.write_text(json.dumps(library, indent=2) + '\n')
    serve_map_editor.LIBRARY_PATH = path
    server = ThreadingHTTPServer(('127.0.0.1', 0), serve_map_editor.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/api/library'
    try:
        envelope = json.loads(urlopen(url).read())
        updated = copy.deepcopy(envelope['library'])
        updated['maps'].append(draft)
        body = json.dumps({'revision': envelope['revision'], 'library': updated}).encode()
        try:
            result = json.loads(urlopen(Request(url, data=body, method='PUT', headers={'Content-Type': 'application/json'})).read())
        except HTTPError as error:
            raise AssertionError(error.read().decode()) from error
        assert result['library']['maps'][-1]['id'] == 'empty-draft'
        assert json.loads(path.read_text()) == updated
        try:
            urlopen(Request(url, data=body, method='PUT', headers={'Content-Type': 'application/json'}))
            raise AssertionError('Stale library revision overwrote the file')
        except HTTPError as error:
            assert error.code == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

print(f'PASS shared map library: {len(enabled)} compiled maps, draft persistence, atomic API and conflict guard.')
