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
        result = batch.view(500, 100)
        self.assertEqual(len(result['jobs']), 100)
        self.assertEqual(result['jobs'][0]['id'], 500)
        self.assertEqual(result['total'], 10000)
        self.assertEqual(len(result['recent']), 4)
        self.assertLess(len(json.dumps(result)), 25000)


if __name__ == '__main__':
    unittest.main()
