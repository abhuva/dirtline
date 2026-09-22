"""Loopback-only map workshop server with one bounded library write API."""
import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from compile_recipe import LIBRARY_PATH, library_revision, validate_library

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.mjs': 'text/javascript', '.wasm': 'application/wasm'}

    def _json(self, status, value):
        data = json.dumps(value).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlsplit(self.path).path == '/api/library':
            try:
                data = LIBRARY_PATH.read_bytes()
                self._json(200, {'revision': library_revision(data), 'library': json.loads(data)})
            except Exception as error:
                self._json(500, {'error': str(error)})
            return
        super().do_GET()

    def do_PUT(self):
        if urlsplit(self.path).path != '/api/library':
            self._json(404, {'error': 'Unknown endpoint'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 1024 * 1024:
                raise ValueError('Map library request must be between 1 byte and 1 MiB')
            request = json.loads(self.rfile.read(length))
            current = LIBRARY_PATH.read_bytes()
            if request.get('revision') != library_revision(current):
                self._json(409, {'error': 'The map library changed on disk. Reload before saving.'})
                return
            library = request.get('library')
            validate_library(library)
            encoded = (json.dumps(library, indent=2) + '\n').encode('utf8')
            temporary = LIBRARY_PATH.with_suffix('.json.tmp')
            temporary.write_bytes(encoded)
            os.replace(temporary, LIBRARY_PATH)
            self._json(200, {'revision': library_revision(encoded), 'library': library})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {'error': str(error)})
        except Exception as error:
            self._json(500, {'error': str(error)})

    def translate_path(self, path):
        path = unquote(urlsplit(path).path)
        base = ROOT / ('maps/recipes' if path.startswith('/recipes/') else 'tools/map_editor')
        relative = path[len('/recipes/'):] if path.startswith('/recipes/') else path.lstrip('/')
        candidate = (base / relative).resolve()
        if not candidate.is_relative_to(base.resolve()):
            return str(base / '__not_found__')
        return str(candidate)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    print(f'Dustline Map Workshop: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler)).serve_forever()
