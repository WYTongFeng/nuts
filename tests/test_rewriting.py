import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import rewriting
import server


class LocalIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = []
        class Ollama(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send({'models': [{'name': 'local-editor:7b'}, {'name': 'reviewer:4b'}, {'name': 'remote:cloud'},
                                      {'name': 'alias', 'remote_model': 'remote'}]})
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                cls.calls.append(payload)
                if self.path == '/api/show':
                    self.send({'thinking': {'values': [False, True]}})
                    return
                if 'format' in payload:
                    self.send({'message': {'content': json.dumps({'meaning_preserved': True, 'added_claims': [], 'missing_claims': [], 'changed_claims': []})}, 'done_reason': 'stop'})
                    return
                self.send({'message': {'content': 'The API improves clarity.'}, 'done_reason': 'stop'})
            def send(self, data):
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        cls.ollama = ThreadingHTTPServer(('127.0.0.1', 0), Ollama)
        cls.app = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.patch = patch.object(rewriting, 'BASE', f'http://127.0.0.1:{cls.ollama.server_port}')
        cls.patch.start()
        cls.base = f'http://127.0.0.1:{cls.app.server_port}'
        for svc in (cls.ollama, cls.app):
            threading.Thread(target=svc.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for svc in (cls.app, cls.ollama):
            svc.shutdown()
            svc.server_close()
        cls.patch.stop()

    def setUp(self):
        rewriting._active_model = None
        rewriting._model_info.clear()
        self.calls.clear()

    def post(self, body, path='/api/rewrite', origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=raw, headers=headers)
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.load(res)
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.load(err)

    def payload(self):
        return {'text': 'The API has good clarity.', 'style': 'natural',
                'model': 'local-editor:7b', 'terms': ['API', 'Java']}

    def test_rewrite_round_trip(self):
        code, data = self.post(self.payload())
        self.assertEqual(code, 200)
        self.assertEqual(data['text'], 'The API improves clarity.')
        self.assertEqual(data['missing_terms'], [])
        self.assertFalse(self.calls[-1]['stream'])
        self.assertEqual(self.calls[-1]['keep_alive'], '5m')
        self.assertFalse(self.calls[-1]['think'])
        self.assertIn('The API has good clarity.', self.calls[-1]['messages'][-1]['content'])

    def test_audited_candidate_round_trip(self):
        code, data = self.post({**self.payload(), 'audit': True, 'attempt': 2, 'strength': 'deep', 'voice': 'My own prose.'})
        self.assertEqual(code, 200)
        self.assertTrue(data['eligible'])
        self.assertEqual(data['strategy'], '保留作者语气')
        self.assertIsNone(data['local_score']['score'])

    def test_missing_protected_terms_reported(self):
        data = self.payload()
        data['text'] += ' Java works.'
        self.assertEqual(self.post(data)[1]['missing_terms'], ['Java'])

    def test_status_excludes_remote_models(self):
        with urllib.request.urlopen(self.base + '/api/status') as res:
            self.assertEqual(json.load(res)['models'], ['local-editor:7b', 'reviewer:4b'])

    def test_validation(self):
        for body in (b'{broken', [], {'text': 42}, {'text': 'a'*20001},
                     {'text': 'word '*2001}, {**self.payload(), 'style': 'bad'},
                     {**self.payload(), 'terms': 'API'}, {**self.payload(), 'attempt': True},
                     {**self.payload(), 'attempt': 3}, {**self.payload(), 'audit': 'yes'},
                     {**self.payload(), 'voice': 'x' * 3001}, {**self.payload(), 'style': []}, {**self.payload(), 'text': ''}):
            with self.subTest(body=str(body)[:80]):
                self.assertEqual(self.post(body)[0], 400)

    def test_unknown_model_rejected(self):
        self.assertEqual(self.post({**self.payload(), 'model': 'remote:cloud'})[0], 400)

    def test_cross_origin_rejected(self):
        self.assertEqual(self.post(self.payload(), origin='https://example.com')[0], 403)

    def test_busy_returns_conflict(self):
        with server.MODEL_LOCK:
            self.assertEqual(self.post(self.payload())[0], 409)

    def test_offline_model_service(self):
        with patch.object(rewriting, 'request', side_effect=OSError('offline')):
            self.assertEqual(rewriting.status(), {'available': False, 'models': []})
            self.assertEqual(self.post(self.payload())[0], 400)

    def test_generation_timeout_returns_recoverable_error(self):
        with patch.object(rewriting, 'rewrite', side_effect=TimeoutError):
            self.assertEqual(self.post(self.payload())[0], 503)
        self.assertFalse(server.MODEL_LOCK.locked())

    def test_distinct_reviewer_and_model_lifecycle(self):
        code, candidate = self.post(self.payload())
        self.assertEqual(code, 200)
        self.assertFalse(candidate['eligible'])
        self.assertEqual(candidate['runtime']['context'], 4096)
        code, audit = self.post({**self.payload(), 'model': 'reviewer:4b',
                                'output': candidate['text']}, '/api/review')
        self.assertEqual(code, 200)
        self.assertTrue(audit['eligible'])
        self.assertEqual(audit['review']['model'], 'reviewer:4b')
        unload = next(i for i, p in enumerate(self.calls) if p.get('keep_alive') == 0)
        review = next(i for i, p in enumerate(self.calls) if 'format' in p)
        self.assertLess(unload, review)
        self.assertEqual(self.calls[unload]['model'], 'local-editor:7b')
        self.assertEqual(self.post({}, '/api/release')[0], 200)
        self.assertIsNone(rewriting._active_model)

    def test_same_model_stays_warm(self):
        self.post(self.payload())
        self.post(self.payload())
        self.assertFalse(any(p.get('keep_alive') == 0 for p in self.calls))

    def test_invalid_review_and_profile(self):
        for output in ('', 12, 'x' * 28001):
            self.assertEqual(self.post({**self.payload(), 'output': output}, '/api/review')[0], 400)
        self.assertEqual(self.post({**self.payload(), 'profile': 'bad'})[0], 400)
        self.assertEqual(self.post({**self.payload(), 'output': 'Valid text', 'model': 'remote:cloud'}, '/api/review')[0], 400)

    def test_review_failure_never_eligible(self):
        with patch.object(rewriting, 'chat', side_effect=TimeoutError):
            code, data = self.post({**self.payload(), 'output': 'The API improves clarity.'}, '/api/review')
        self.assertEqual(code, 200)
        self.assertFalse(data['eligible'])
        self.assertEqual(data['review']['status'], 'unavailable')

    def test_quality_failure_skips_review(self):
        with patch.object(rewriting, 'review') as review:
            code, data = self.post({**self.payload(), 'text': 'The API costs 300 dollars.',
                                   'output': 'The API costs 900 dollars.'}, '/api/review')
        self.assertEqual(code, 200)
        self.assertFalse(data['eligible'])
        review.assert_not_called()

    def test_review_cannot_override_computed_status(self):
        forged = json.dumps({'meaning_preserved': False, 'added_claims': [],
                             'missing_claims': [], 'changed_claims': [], 'status': 'passed'})
        with patch.object(rewriting, 'chat', return_value=forged):
            code, data = self.post({**self.payload(), 'output': 'The API improves clarity.'}, '/api/review')
        self.assertEqual(code, 200)
        self.assertFalse(data['eligible'])
        self.assertEqual(data['review']['status'], 'unavailable')

    def test_context_budget_and_limit(self):
        self.assertEqual(rewriting.runtime_options([{'content': 'a' * 7000}], 1024, 'rtx3060')['num_ctx'], 8192)
        with self.assertRaises(ValueError):
            rewriting.runtime_options([{'content': 'a' * 20000}], 1024, 'rtx3060')
        self.assertEqual(rewriting.runtime_options([{'content': 'short'}], 512, 'context8k')['num_ctx'], 8192)

    def test_truncation_is_not_accepted(self):
        with patch.object(rewriting, 'status', return_value={'models': ['local-editor:7b']}), patch.object(rewriting, 'request', return_value={'message': {'content': 'partial'}, 'done_reason': 'length'}):
            with self.assertRaises(ValueError):
                rewriting.rewrite('Original text', 'natural', 'local-editor:7b', [])


if __name__ == '__main__':
    unittest.main()
