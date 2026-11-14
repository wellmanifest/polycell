"""Untrusted host replies must satisfy the same envelope on every transport."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from gateway import core, transport
from gateway.app import H
from gateway.db import DB


class HostEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.urn = core.BY_NAME['shipping.cost']
        self.meta = core.CELLS[self.urn]
        self.reply = {'urn': self.urn, 'ok': True, 'output': {'result': 9.99}, 'error': '',
                      'lang': 'python', 'contract': self.meta['contract'], 'duration_ms': 0.1}

    def call(self, protocol, reply):
        with patch.object(transport, 'call_' + protocol, return_value=deepcopy(reply)):
            return transport.call('python', protocol, self.urn, {}, 'trace')

    def assert_rejected(self, reply):
        for protocol in transport.TRANSPORTS:
            with self.subTest(protocol=protocol, reply=reply):
                result = self.call(protocol, reply)
                self.assertIs(result['ok'], False)
                self.assertEqual(self.urn, result['urn'])
                self.assertEqual('python', result['lang'])
                self.assertIsNone(result['output'])
                self.assertIn('invalid host response', result['error'])
                self.assertEqual(protocol, result['transport'])
                self.assertGreaterEqual(result['rtt_ms'], 0)
                json.dumps(result, allow_nan=False)

    def test_valid_success_and_failure_keep_their_envelopes(self):
        failure = dict(self.reply, ok=False, output=None, error='not hosted here', contract='')
        for reply in (self.reply, failure, dict(self.reply, output=None)):
            for protocol in transport.TRANSPORTS:
                with self.subTest(protocol=protocol, ok=reply['ok']):
                    result = self.call(protocol, reply)
                    self.assertEqual(reply, {key: result[key] for key in reply})

    def test_nonobject_response_is_a_structured_failure(self):
        for value in (None, [], ['reply'], 'reply', True, 1):
            self.assert_rejected(value)

    def test_status_is_a_boolean_including_false_values(self):
        for value in ('true', 'false', 1, 0, None, [], {}):
            self.assert_rejected(dict(self.reply, ok=value))

    def test_response_urn_and_language_must_match_the_request(self):
        for ok in (True, False):
            reply = dict(self.reply, ok=ok, error='' if ok else 'host error')
            for field, value in [('urn', 'urn:wm:cell:wrong:shipping.cost:v1'),
                                 ('urn', None), ('lang', 'rust'), ('lang', None)]:
                self.assert_rejected(dict(reply, **{field: value}))

    def test_all_wire_fields_are_required(self):
        for field in self.reply:
            reply = dict(self.reply)
            del reply[field]
            self.assert_rejected(reply)

    def test_error_contract_and_duration_have_protocol_types(self):
        for field, values in [('error', [None, False, [], {}]), ('contract', [None, True, 1, []]),
                              ('duration_ms', [None, True, False, '0.1', [], -0.1])]:
            for value in values:
                self.assert_rejected(dict(self.reply, **{field: value}))

    def test_status_and_error_must_be_consistent(self):
        self.assert_rejected(dict(self.reply, error='failed but marked successful'))
        self.assert_rejected(dict(self.reply, ok=False, error=''))

    def test_nonfinite_values_cannot_cross_the_transport_boundary(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            self.assert_rejected(dict(self.reply, duration_ms=value))
            self.assert_rejected(dict(self.reply, output={'nested': [value]}))
        self.assert_rejected(dict(self.reply, output=object()))

    def test_transport_annotations_do_not_mutate_the_host_reply(self):
        reply = dict(self.reply)
        with patch.object(transport, 'call_http', return_value=reply):
            result = transport.call('python', 'http', self.urn, {}, 'trace')
        self.assertEqual(self.reply, reply)
        self.assertIsNot(reply, result)

    def test_gateway_rejects_wrong_identity_and_status_with_failed_persistence(self):
        for reply in ([], dict(self.reply, ok='true'), dict(self.reply, urn='wrong'),
                      dict(self.reply, lang='rust'), dict(self.reply, error='ambiguous')):
            for protocol in transport.TRANSPORTS:
                with self.subTest(protocol=protocol, reply=reply), patch.object(
                        transport, 'call_' + protocol, return_value=deepcopy(reply)), patch.object(core, 'db') as database:
                    result = core.invoke('shipping.cost', {'weight_kg': 2, 'country': 'PL'}, protocol)
                    self.assertIs(result['ok'], False)
                    self.assertEqual(self.urn, result['urn'])
                    self.assertIn('invalid host response', result['error'])
                    database.return_value.insert.assert_called_once()
                    table, row = database.return_value.insert.call_args.args[:2]
                    self.assertEqual('wm_invocations', table)
                    self.assertIs(row['ok'], False)
                    self.assertEqual('python', row['lang'])

    def test_bad_host_response_stops_process_and_persists_cause(self):
        process = {'schema': 'poa.process/v1', 'process_ref': 'poa://test/process/envelope/v1',
                   'steps': [{'id': 'first', 'capability_ref': self.urn, 'input': {'weight_kg': 2, 'country': 'PL'}},
                             {'id': 'next', 'capability_ref': self.urn, 'input': {'weight_kg': 3, 'country': 'PL'}}],
                   'output': {'cost': '$.steps.next.result'}}
        for protocol in transport.TRANSPORTS:
            with self.subTest(protocol=protocol), patch.dict(core.PROCESSES, {'envelope': process}), patch.object(
                    transport, 'call_' + protocol, return_value=dict(self.reply, ok='true')) as host, patch.object(core, 'db') as database:
                result = core.run_process('envelope', {}, protocol)
                self.assertIs(result['ok'], False)
                self.assertEqual(['first'], [step['id'] for step in result['receipt']['steps']])
                self.assertEqual(result['error'], result['receipt']['error'])
                host.assert_called_once()
                table, row = database.return_value.insert.call_args.args[:2]
                self.assertEqual('wm_process_runs', table)
                self.assertIs(row['ok'], False)


class WireEnvelopeTests(unittest.TestCase):
    """Exercise actual codecs, HTTP gateway, process stop and database writes."""
    def setUp(self):
        self.urn = core.BY_NAME['shipping.cost']
        self.meta = dict(core.CELLS[self.urn], persist='wire_successes')
        self.enterContext(patch.dict(core.CELLS, {self.urn: self.meta}))
        good = {'urn': self.urn, 'ok': True, 'output': {'result': 9.99}, 'error': '',
                'lang': 'python', 'contract': self.meta['contract'], 'duration_ms': 0.1}
        self.replies = [good, dict(good, ok=False, output=None, error='business rejection'), [],
                        dict(good, ok='true'), dict(good, urn='wrong'), dict(good, lang='rust'),
                        {k: v for k, v in good.items() if k != 'output'}, dict(good, error=None),
                        dict(good, contract=[]), dict(good, duration_ms=-1), dict(good, duration_ms=True),
                        dict(good, duration_ms=float('nan')), dict(good, output={'result': float('inf')}),
                        dict(good, error='inconsistent success'), dict(good, ok=False)]
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.directory = Path(directory)
        self.database = DB('sqlite:///' + str(self.directory / 'wire.db'))
        self.addCleanup(self.database.conn.close)
        self.database.conn.execute('create table wire_successes '
                                   '(trace_id text, in_weight_kg real, in_country text, out_result real)')
        self.enterContext(patch.object(core, '_db', self.database))
        self.base = self.serve(H)
        process = {'schema': 'poa.process/v1', 'process_ref': 'poa://test/process/envelope/v1',
                   'steps': [{'id': 'first', 'capability_ref': self.urn,
                              'input': {'weight_kg': '$.weight_kg', 'country': 'PL'}},
                             {'id': 'next', 'capability_ref': self.urn,
                              'input': {'weight_kg': 0, 'country': 'PL'}}],
                   'output': {'cost': '$.steps.next.result'}}
        self.enterContext(patch.dict(core.PROCESSES, {'envelope': process}))

    def serve(self, handler):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.addCleanup(stop)
        return f'http://127.0.0.1:{server.server_port}'

    def exercise(self, protocol, modes):
        for mode in modes:
            for process in (False, True):
                with self.subTest(protocol=protocol, mode=mode, process=process):
                    path = '/api/process/envelope' if process else '/api/cells/shipping.cost'
                    request = urllib.request.Request(self.base + path + '?transport=' + protocol,
                        data=json.dumps({'weight_kg': mode, 'country': 'PL'}).encode(),
                        headers={'content-type': 'application/json'})
                    try:
                        response = urllib.request.urlopen(request, timeout=15)
                    except urllib.error.HTTPError as error:
                        response = error
                    with response:
                        status, result = response.status, json.load(response)
                    self.assertEqual(200 if mode == 0 else 422, status, result)
                    self.assertIs(result['ok'], mode == 0)
                    trace = result['receipt']['trace_id'] if process else result['trace_id']
                    rows = self.database.query('select * from wm_invocations where trace_id=?', (trace,))
                    self.assertEqual(2 if process and mode == 0 else 1, len(rows), rows)
                    self.assertTrue(all(row['urn'] == self.urn and row['lang'] == 'python' for row in rows))
                    self.assertTrue(all(bool(row['ok']) == (mode == 0) for row in rows))
                    if mode != 0:
                        self.assertIn('business rejection' if mode == 1 else 'invalid host response', result['error'])
                    if process:
                        saved = self.database.query('select * from wm_process_runs where trace_id=?', (trace,))
                        self.assertEqual(1, len(saved))
                        self.assertEqual(result['receipt'], json.loads(saved[0]['receipt']))
                        self.assertEqual(2 if mode == 0 else 1, len(result['receipt']['steps']))
                        self.assertEqual(mode == 0, bool(saved[0]['ok']))
                    rows = self.database.query('select * from wire_successes where trace_id=?', (trace,))
                    self.assertEqual((2 if process else 1) if mode == 0 else 0, len(rows), rows)

    def test_http_wire_replies_through_gateway_and_process_database(self):
        replies = self.replies
        class Host(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['content-length'])))
                body = json.dumps(replies[request['input']['weight_kg']]).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        with patch.dict(os.environ, {'HOST_PYTHON_HTTP': self.serve(Host)}):
            self.exercise('http', range(len(self.replies)))

    def test_grpc_wire_replies_through_gateway_and_process_database(self):
        import grpc
        from polycell.v1 import cellhost_pb2 as pb, cellhost_pb2_grpc as rpc
        replies = self.replies
        class Host(rpc.CellHostServicer):
            def Invoke(self, request, context):
                reply = replies[json.loads(request.json_input)['weight_kg']]
                return pb.InvokeResponse(urn=reply['urn'], ok=reply['ok'], json_output=json.dumps(reply['output']),
                    error=reply['error'], lang=reply['lang'], duration_ms=reply['duration_ms'], contract=reply['contract'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            server = grpc.server(pool)
            rpc.add_CellHostServicer_to_server(Host(), server)
            port = server.add_insecure_port('127.0.0.1:0')
            server.start()
            try:
                with patch.dict(os.environ, {'HOST_PYTHON_GRPC': f'127.0.0.1:{port}'}), patch.dict(transport._grpc_stubs, {}, clear=True):
                    self.exercise('grpc', (0, 1, 4, 5, 9, 11, 12, 13, 14))
            finally:
                server.stop(0).wait(timeout=3)

    def test_stdio_wire_replies_through_gateway_and_process_database(self):
        host = self.directory / 'host.py'
        cases = self.directory / 'responses.json'
        cases.write_text(json.dumps(self.replies))
        host.write_text('import json,sys\nreplies=json.load(open(sys.argv[1]))\n'
                        'for line in sys.stdin:\n'
                        ' request=json.loads(line)\n'
                        ' print(json.dumps(replies[request["input"]["weight_kg"]]),flush=True)\n')
        command = shlex.join([sys.executable, str(host), str(cases)])
        with patch.dict(os.environ, {'HOST_PYTHON_STDIO': command}), patch.dict(transport._stdio, {}, clear=True):
            try:
                self.exercise('stdio', range(len(self.replies)))
            finally:
                for client in transport._stdio.values():
                    client.p.terminate()
                    client.p.wait(timeout=3)
                    client.p.stdin.close()
                    client.p.stdout.close()


if __name__ == '__main__':
    unittest.main()
