"""Nuts 网页版的本地服务器：提供 analyzer.html，并用 GPT-2 计算困惑度。

用法:
    .venv/bin/python server.py              # 自动在浏览器打开
    .venv/bin/python server.py --no-browser
"""
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import perplexity

ROOT = Path(__file__).parent
PORTS = range(8000, 8011)  # 8000 被占用时依次往后试
# analyzer.html 按 Artifact 的格式只写了页面内容，本地访问时补上文档外壳
SHELL = (
    '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    "</head><body>{}</body></html>"
)
STATIC = {
    "/nuts-core.js": ("nuts-core.js", "text/javascript; charset=utf-8"),
    "/model.json": ("model.json", "application/json"),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 每次请求都重新读文件，改了页面刷新就能看到
        if self.path == "/":
            page = SHELL.format((ROOT / "analyzer.html").read_text(encoding="utf-8"))
            self._send(200, "text/html; charset=utf-8", page.encode())
        elif self.path in STATIC:
            name, content_type = STATIC[self.path]
            self._send(200, content_type, (ROOT / name).read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/score":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        text = json.loads(body or b"{}").get("text", "")
        try:
            overall, sentences = perplexity.details(text) if text.strip() else ({}, [])
            status, result = 200, {"metrics": overall, "sentences": sentences}
        except Exception as e:
            status, result = 500, {"error": str(e)}
        self._send(status, "application/json", json.dumps(result, ensure_ascii=False).encode())

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 不逐条打印请求
        pass


def start_server():
    for port in PORTS:
        try:
            return HTTPServer(("127.0.0.1", port), Handler), port
        except OSError:
            continue
    sys.exit(f"端口 {PORTS.start}-{PORTS.stop - 1} 都被占用了，先关掉之前开的 server.py 再试")


def main():
    server, port = start_server()
    perplexity.load()  # 先加载模型，第一次分析就不用等
    url = f"http://localhost:{port}"
    print(f"Nuts 已启动：{url}（按 Ctrl+C 停止）")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
