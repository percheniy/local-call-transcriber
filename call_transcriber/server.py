"""Token-protected loopback interface; audio never leaves the local machine."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import webbrowser
from urllib.parse import parse_qs, urlsplit

from .batch import Batch, discover
from .resources import plan, snapshot
from .picker import choose_folder, mounted_folder

WEB = Path(__file__).parent / 'web'


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, folder=None, container=False):
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.batch = Batch()
        self.container = container
        self.picker_lock = threading.Lock()
        self.folder = str(Path(folder).expanduser().resolve()) if folder else ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, data, mime='application/json; charset=utf-8'):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, api=False):
        host = self.headers.get('Host', '')
        port = self.server.server_port
        if host not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            self.send(403, dict(error='Недопустимый адрес сервера.'))
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}:
            self.send(403, dict(error='Запрос с другого сайта запрещён.'))
            return False
        if api and not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            self.send(401, dict(error='Откройте ссылку, напечатанную в терминале при запуске.'))
            return False
        return True

    def do_GET(self):
        url = urlsplit(self.path)
        if not self.allowed(url.path.startswith('/api/')):
            return
        try:
            if url.path == '/api/state':
                query = parse_qs(url.query)
                offset = max(0, int(query.get('offset', ['0'])[0]))
                self.send(200, self.server.batch.view(0, 10))
            elif url.path == '/api/info':
                self.send(200, dict(folder=self.server.folder, resources=snapshot(0).public(), picker="mounted" if self.server.container else "native"))
            elif url.path == '/api/result':
                identity = int(parse_qs(url.query)['id'][0])
                if identity < 0:
                    raise ValueError('Неверная запись.')
                path = self.server.batch.result_path(identity)
                self.send(200, dict(text=Path(path).read_text(encoding='utf-8'), path=path))
            elif url.path.startswith('/fonts/') and Path(url.path).name in {p.name for p in (WEB / 'fonts').glob('*.ttf')}:
                self.send(200, (WEB / 'fonts' / Path(url.path).name).read_bytes(), 'font/ttf')
            else:
                static = {'/': ('index.html', 'text/html; charset=utf-8'),
                          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('style.css', 'text/css; charset=utf-8'),
                          '/matrix-lines.js': ('matrix-lines.js', 'text/javascript; charset=utf-8'),
                          '/matrix.js': ('matrix.js', 'text/javascript; charset=utf-8')}
                if url.path not in static:
                    self.send(404, dict(error='Не найдено'))
                    return
                name, mime = static[url.path]
                self.send(200, (WEB / name).read_bytes(), mime)
        except (OSError, ValueError, KeyError, IndexError) as error:
            self.send(400, dict(error=str(error)))

    def index_folder(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        def emit(event):
            self.wfile.write((json.dumps(event, ensure_ascii=False) + '\n').encode())
            self.wfile.flush()
        try:
            jobs = discover(data['folder'], progress=emit)
            pending = sum(job['status'] == 'pending' for job in jobs)
            emit(dict(stage='done', found=len(jobs), total=len(jobs), pending=pending,
                      plan=plan(snapshot(), pending, parallel=data.get('parallel', 'auto'))))
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as error:
            try:
                emit(dict(stage='error', error=str(error)))
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self):
        if not self.allowed(api=True):
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 16_384:
                raise ValueError('Слишком большой запрос.')
            data = json.loads(self.rfile.read(length) or b'{}')
            if self.path == '/api/index':
                self.index_folder(data)
            elif self.path == '/api/pick-folder':
                if self.server.container:
                    raise ValueError('Используйте системный выбор папки в браузере.')
                if not self.server.picker_lock.acquire(blocking=False):
                    raise ValueError('Окно выбора папки уже открыто.')
                try:
                    self.send(200, dict(folder=choose_folder()))
                finally:
                    self.server.picker_lock.release()
            elif self.path == '/api/pick-mounted':
                if not self.server.container:
                    raise ValueError('Выбор подключённой папки доступен только в контейнере.')
                self.send(200, dict(folder=mounted_folder(data['nonce'])))
            elif self.path == '/api/preview':
                jobs = discover(data['folder'])
                resources = snapshot()
                pending = sum(j['status'] == 'pending' for j in jobs)
                self.send(200, dict(total=len(jobs), plan=plan(resources, pending, parallel=data.get("parallel", "auto")), pending=pending))
            elif self.path == '/api/start':
                self.server.batch.start(data['folder'], data.get('parallel', 'auto'))
                self.send(202, self.server.batch.view(0, 10))
            elif self.path == '/api/cancel':
                self.server.batch.cancel()
                self.send(200, self.server.batch.view(0, 10))
            else:
                self.send(404, dict(error='Не найдено'))
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.send(400, dict(error=str(error)))


def main():
    parser = argparse.ArgumentParser(description='Локальная расшифровка папки звонков: GigaAM v3 + Sortformer')
    parser.add_argument('--folder', help='Начальная папка в интерфейсе')
    parser.add_argument('--port', type=int, default=0, help='0 — автоматически выбрать свободный порт')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--container', action='store_true', help='Bind inside a container; publish only to host loopback')
    args = parser.parse_args()
    server = AppServer(('0.0.0.0' if args.container else '127.0.0.1', args.port), args.folder, args.container)
    url = f'http://127.0.0.1:{server.server_port}/#{server.token}'
    print(f'Откройте интерфейс: {url}', flush=True)
    if not args.no_browser:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nОстановка…', flush=True)
    finally:
        server.batch.cancel()
        if server.batch.thread:
            server.batch.thread.join(timeout=15)
        server.server_close()


if __name__ == '__main__':
    main()
