"""Loopback-only static editor server; never writes repository files."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.mjs': 'text/javascript', '.wasm': 'application/wasm'}

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
