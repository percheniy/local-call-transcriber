import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from call_transcriber.server import AppServer
from call_transcriber.batch import Batch


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = AppServer(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, headers):
        return urllib.request.urlopen(urllib.request.Request(self.url + '/api/state', headers=headers))

    def test_missing_token_and_cross_origin_rejected(self):
        for headers in [{}, {'Authorization': 'Bearer '+self.server.token, 'Origin': 'https://example.com'},
                        {'Authorization': 'Bearer '+self.server.token, 'Host': 'attacker.example'}]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request(headers)
            self.assertIn(error.exception.code, [401, 403])
        with self.request({'Authorization':'Bearer '+self.server.token}) as response:
            self.assertEqual(json.load(response)['phase'], 'idle')

    def test_snapshot_bounded_for_ten_thousand_jobs(self):
        batch = Batch()
        template = dict(status='done', percent=100, relative='call.wav', id=0, error='', warnings=[])
        batch.state['jobs'] = [dict(template, id=i) for i in range(10000)]
        result = batch.view(0, 10)
        self.assertEqual(len(result['jobs']), 10)
        self.assertEqual(result['jobs'][0]['id'], 0)
        self.assertEqual(result['total'], 10000)
        self.assertEqual(len(result['recent']), 10)
        self.assertLess(len(json.dumps(result)), 25000)

    def test_index_stream_reports_nested_audio_and_existing_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'nested').mkdir()
            (root / 'call.mp3').touch()
            (root / 'nested' / 'call.WAV').touch()
            (root / 'notes.txt').touch()
            (root / 'transcription').mkdir()
            (root / 'transcription' / 'call.mp3.txt').write_text('existing')
            request = urllib.request.Request(self.url + '/api/index',
                data=json.dumps(dict(folder=str(root), parallel=2)).encode(),
                headers={'Authorization': 'Bearer ' + self.server.token, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(request) as response:
                events = [json.loads(line) for line in response]
            self.assertEqual(events[0]['stage'], 'searching')
            self.assertEqual(events[-1]['stage'], 'done')
            self.assertEqual(events[-1]['found'], 2)
            self.assertEqual(events[-1]['pending'], 1)
            self.assertEqual(events[-1]['plan']['mode'], 2)
            checked = [e for e in events if e['stage'] == 'checking']
            self.assertEqual(checked[-1]['checked'], 2)
            self.assertEqual(checked[-1]['total'], 2)

    def test_index_flushes_progress_before_scan_finishes(self):
        from unittest.mock import patch
        release = threading.Event()
        def scan(folder, progress):
            progress(dict(stage='searching', found=7, scanned=9))
            if not release.wait(3):
                raise RuntimeError('Progress was buffered')
            return []
        with patch('call_transcriber.server.discover', side_effect=scan):
            request = urllib.request.Request(self.url + '/api/index', data=b'{"folder":"test"}',
                headers={'Authorization': 'Bearer ' + self.server.token})
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    first = json.loads(response.readline())
                    self.assertEqual(first['found'], 7)
                    release.set()
                    self.assertEqual(json.loads(response.readline())['stage'], 'done')
            finally:
                release.set()


if __name__ == '__main__':
    unittest.main()
