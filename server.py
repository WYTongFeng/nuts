"""Nuts local web app. Run python server.py [--no-browser] [--no-preload]."""
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import rewriting

ROOT = Path(__file__).parent
PORTS = range(8000, 8011)
SHELL = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>{}</body></html>'
STATIC = { '/' + name: (name, mime) for name, mime in [
    ('nuts-core.js', 'text/javascript'), ('app.js', 'text/javascript'),
    ('app.css', 'text/css'), ('model.json', 'application/json')] }
MODEL_LOCK = threading.Lock()
# GPT-2 后台预加载：idle（没预加载）/ loading / ready / error
DETECTOR = {'state': 'idle'}
DETECTOR_READY = threading.Event()
DETECTOR_READY.set()


def preload_detector():
    """启动时在后台加载 GPT-2，第一次检测就不用等；加载期间的检测请求会等它完成。"""
    try:
        with MODEL_LOCK:
            import perplexity
            perplexity.load()
        DETECTOR['state'] = 'ready'
    except Exception:
        DETECTOR['state'] = 'error'
    finally:
        DETECTOR_READY.set()


def score(text):
    import perplexity
    return perplexity.details(text)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self._send(200, 'text/html; charset=utf-8', SHELL.format((ROOT / 'analyzer.html').read_text(encoding='utf-8')).encode())
        elif self.path == '/api/status':
            self._json(200, rewriting.status())
        elif self.path == '/api/detector':
            self._json(200, DETECTOR)
        elif self.path in STATIC:
            name, mime = STATIC[self.path]
            self._send(200, mime + '; charset=utf-8', (ROOT / name).read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path not in ('/api/score', '/api/rewrite', '/api/review', '/api/release'):
            self.send_error(404)
            return
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            self._json(403, {'error': '只接受本地页面的请求。'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 <= length <= 60000:
                raise ValueError('请求太大。')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict) or not isinstance(data.get('text', ''), str):
                raise ValueError('text 必须是文本。')
            text = data.get('text', '')
            if len(text) > 20000 or len(text.split()) > 2000:
                raise ValueError('第一版每次最多处理 2,000 个词、20,000 个字符。')
            if self.path == '/api/score' and not text.strip():
                self._json(200, {'metrics': {}, 'sentences': []})
                return
            if self.path in ('/api/rewrite', '/api/review'):
                profile = data.get('profile', 'rtx3060')
                if profile not in ('rtx3060', 'context8k'):
                    raise ValueError('请选择有效的运行配置。')
                if self.path == '/api/review':
                    output = data.get('output')
                    if not isinstance(output, str) or not output.strip() or len(output) > 28000:
                        raise ValueError('复核文本为空或过长。')
                if not text.strip():
                    raise ValueError('请先输入英文。')
                terms = data.get('terms', [])
                if not isinstance(terms, list) or len(terms) > 50 or any(not isinstance(t, str) or len(t) > 100 for t in terms):
                    raise ValueError('保留术语格式无效。')
                attempt, strength, voice, audit = data.get('attempt', 0), data.get('strength', 'balanced'), data.get('voice', ''), data.get('audit', False)
                if type(attempt) is not int or not 0 <= attempt < 3 or not isinstance(strength, str) or strength not in rewriting.STRENGTHS or not isinstance(voice, str) or len(voice) > 3000 or type(audit) is not bool:
                    raise ValueError('候选序号、改写强度或写作样本格式无效。')
                if not isinstance(data.get('style'), str) or data.get('style') not in rewriting.STYLES or not isinstance(data.get('model'), str):
                    raise ValueError('请选择润色风格和本地模型。')
        except (ValueError, TypeError) as e:
            self._json(400, {'error': str(e)})
            return
        if self.path == '/api/score':
            # 预加载还没完成时先等它，而不是回“正在处理其他请求”
            DETECTOR_READY.wait(timeout=600)
        if not MODEL_LOCK.acquire(blocking=False):
            self._json(409, {'error': '模型正在处理其他请求，请稍后重试。'})
            return
        try:
            if self.path == '/api/score':
                rewriting.release()
                overall, sentences = score(text)
                DETECTOR['state'] = 'ready'
                result = {'metrics': overall, 'sentences': sentences}
            elif self.path == '/api/release':
                rewriting.release()
                result = {'released': True}
            else:
                # Free GPT-2 CUDA allocations before Ollama needs the GPU.
                if 'perplexity' in sys.modules:
                    sys.modules['perplexity'].release_gpu()
                if self.path == '/api/review':
                    result = rewriting.audit_candidate(text, output, data['model'], terms, data['style'], profile)
                else:
                    result = rewriting.rewrite(text, data['style'], data['model'], terms, attempt=attempt, strength=strength, voice=voice, audit=audit, profile=profile)
            self._json(200, result)
        except ValueError as e:
            self._json(400, {'error': str(e)})
        except Exception:
            self._json(503, {'error': '本地模型调用失败或超时。检测请检查 Python 依赖和 GPT-2 下载；润色请检查 Ollama 和模型。'})
        finally:
            MODEL_LOCK.release()

    def _json(self, code, data):
        self._send(code, 'application/json; charset=utf-8', json.dumps(data, ensure_ascii=False).encode())

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


def start_server():
    for port in PORTS:
        try:
            return ThreadingHTTPServer(('127.0.0.1', port), Handler), port
        except OSError:
            continue
    sys.exit('8000–8010 端口都被占用。')


def main():
    server, port = start_server()
    if '--no-preload' not in sys.argv:
        DETECTOR['state'] = 'loading'
        DETECTOR_READY.clear()
        threading.Thread(target=preload_detector, daemon=True).start()
    url = f'http://localhost:{port}'
    print(f'Nuts 已启动：{url}（Ctrl+C 停止）', flush=True)
    if '--no-browser' not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
