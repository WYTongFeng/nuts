import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import server
except ImportError:  # 没装 torch / transformers
    server = None


@unittest.skipIf(server is None, "需要 torch 和 transformers")
class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, text):
        req = urllib.request.Request(self.base + "/api/score", data=json.dumps({"text": text}).encode(), method="POST")
        with urllib.request.urlopen(req) as res:
            return json.load(res)

    def test_page_is_a_full_document(self):
        with urllib.request.urlopen(self.base + "/") as res:
            body = res.read().decode()
        self.assertTrue(body.startswith("<!doctype html>"))
        self.assertIn("<title>Nuts</title>", body)

    def test_static_files(self):
        for path in ("/nuts-core.js", "/model.json"):
            with urllib.request.urlopen(self.base + path) as res:
                self.assertEqual(res.status, 200)

    def test_score_returns_overall_and_per_sentence(self):
        result = self.post("Online learning is useful. It also has problems.")
        self.assertEqual(set(result["metrics"]), {"ppl", "sent_ppl_std", "top10"})
        self.assertEqual(len(result["sentences"]), 2)

    def test_empty_text(self):
        self.assertEqual(self.post("  "), {"metrics": {}, "sentences": []})

    def test_detector_status(self):
        with urllib.request.urlopen(self.base + "/api/detector") as res:
            self.assertIn(json.load(res)["state"], {"idle", "loading", "ready", "error"})

    def test_preload_marks_detector_ready(self):
        server.DETECTOR["state"] = "loading"
        server.DETECTOR_READY.clear()
        server.preload_detector()
        self.assertEqual(server.DETECTOR["state"], "ready")
        self.assertTrue(server.DETECTOR_READY.is_set())

    def test_unknown_path(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.base + "/secret.txt")
        ctx.exception.close()
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
