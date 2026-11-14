"""Untrusted host replies must satisfy the same envelope on every transport."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import time
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
                    client.close()

    def test_stdio_timeout_stops_process_and_persists_failure(self):
        host = self.directory / 'silent.py'
        host.write_text('import sys,time\nfor line in sys.stdin:\n time.sleep(60)\n')
        command = shlex.join([sys.executable, str(host)])
        with patch.dict(os.environ, {'HOST_PYTHON_STDIO': command}), patch.dict(
                transport._stdio, {}, clear=True), patch.object(transport, 'STDIO_TIMEOUT', 0.15):
            try:
                request = urllib.request.Request(self.base + '/api/process/envelope?transport=stdio',
                    data=b'{"weight_kg":1}', headers={'content-type': 'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(request, timeout=5)
                with failure.exception as response:
                    self.assertEqual(422, response.code)
                    result = json.load(response)
                self.assertIs(result['ok'], False)
                self.assertIn('timed out', result['error'])
                self.assertEqual(['first'], [step['id'] for step in result['receipt']['steps']])
                trace = result['receipt']['trace_id']
                rows = self.database.query('select * from wm_invocations where trace_id=?', (trace,))
                self.assertEqual(1, len(rows))
                self.assertFalse(rows[0]['ok'])
                saved = self.database.query('select * from wm_process_runs where trace_id=?', (trace,))
                self.assertEqual(1, len(saved))
                self.assertFalse(saved[0]['ok'])
                self.assertEqual(result['receipt'], json.loads(saved[0]['receipt']))
                self.assertEqual([], self.database.query('select * from wire_successes where trace_id=?', (trace,)))
                self.assertEqual({}, transport._stdio)
            finally:
                for client in list(transport._stdio.values()):
                    client.close()


class StdioDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.clients = []
        self.spawn_delay = 0
        original = transport._Stdio
        def spawn(command):
            time.sleep(self.spawn_delay)
            script = Path(shlex.split(command)[-1])
            ready = script.with_suffix('.ready')
            ready.unlink(missing_ok=True)
            client = original(command)
            self.clients.append(client)
            deadline = time.monotonic() + 3
            while not ready.exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError('fixture host did not start')
                time.sleep(0.005)
            return client
        self.enterContext(patch.object(transport, '_Stdio', side_effect=spawn))
        self.enterContext(patch.dict(transport._stdio, {}, clear=True))
        self.enterContext(patch.object(transport, 'STDIO_TIMEOUT', 1.0, create=True))
        self.addCleanup(self.close_clients)

    def close_clients(self):
        for client in self.clients:
            if hasattr(client, 'close'):
                client.close()
            else:  # Cleanup also bounds the old implementation during regression reproduction.
                client.p.kill()
                client.p.wait(timeout=3)
                for stream in (client.p.stdin, client.p.stdout):
                    try:
                        stream.close()
                    except OSError:
                        pass

    def host(self, body):
        script = self.directory / f'host{len(list(self.directory.glob("*.py")))}.py'
        script.write_text('import json,os,sys,time\nfrom pathlib import Path\n'
            'Path(__file__).with_suffix(".ready").write_text(str(os.getpid()))\n'
            'def reply(request):\n'
            ' return {"urn":request["urn"],"ok":True,"output":request["input"],"error":"",'
            '"lang":"python","contract":"fixture","duration_ms":0}\n' + body)
        command = shlex.join([sys.executable, str(script)])
        self.enterContext(patch.dict(os.environ, {'HOST_PYTHON_STDIO': command}))
        return script

    def call(self, data):
        result = []
        thread = threading.Thread(target=lambda: result.append(transport.call('python', 'stdio', 'urn:wm:probe', data)))
        thread.start()
        thread.join(timeout=2.5)
        completed = not thread.is_alive()
        if not completed:
            self.close_clients()
            thread.join(timeout=3)
        self.assertTrue(completed, 'stdio request exceeded the watchdog')
        self.assertEqual(1, len(result))
        return result[0]

    def test_silent_partial_and_blocked_write_requests_have_deadlines(self):
        for body, data in [('for line in sys.stdin:\n time.sleep(60)\n', {}),
                           ('for line in sys.stdin:\n sys.stdout.write("{");sys.stdout.flush();time.sleep(60)\n', {}),
                           ('time.sleep(60)\n', {'large': 'x' * 262144})]:
            with self.subTest(body=body), patch.object(transport, 'STDIO_TIMEOUT', 0.15, create=True):
                self.host(body)
                result = self.call(data)
                self.assertIs(result['ok'], False)
                self.assertIn('timed out', result['error'])
                self.assertEqual({}, transport._stdio)
                self.assertIsNotNone(self.clients[-1].p.poll())

    def restarting_host(self, failure):
        flag = self.directory / 'attempts'
        self.host(f'flag=Path({str(flag)!r})\n'
            'attempt=int(flag.read_text())+1 if flag.exists() else 1\nflag.write_text(str(attempt))\n'
            'for line in sys.stdin:\n request=json.loads(line)\n'
            f' if attempt==1:\n  {failure}\n'
            ' print(json.dumps(reply(request)),flush=True)\n')
        return flag

    def assert_restart(self, failure, timed_out=False):
        attempts = self.restarting_host(failure)
        with patch.object(transport, 'STDIO_TIMEOUT', 0.15, create=True):
            failed = self.call({'value': 1})
        self.assertIs(failed['ok'], False)
        if timed_out:
            self.assertIn('timed out', failed['error'])
        self.assertEqual('1', attempts.read_text(), 'failed requests must never be replayed')
        self.assertEqual({}, transport._stdio)
        old = self.clients[-1]
        self.assertIsNotNone(old.p.poll())
        recovered = self.call({'value': 2})
        self.assertIs(recovered['ok'], True, recovered)
        self.assertEqual({'value': 2}, recovered['output'])
        self.assertEqual('2', attempts.read_text())
        self.assertNotEqual(old.p.pid, self.clients[-1].p.pid)

    def test_timeout_retires_host_and_later_call_recovers_without_replay(self):
        self.assert_restart('time.sleep(60)', timed_out=True)

    def test_eof_retires_host_and_later_call_recovers(self):
        self.assert_restart('sys.exit(0)')

    def test_malformed_json_retires_host_and_later_call_recovers(self):
        self.assert_restart('print("not-json",flush=True);time.sleep(60)')

    def test_queued_timeout_preserves_an_inflight_request(self):
        self.host('for line in sys.stdin:\n request=json.loads(line)\n'
                  ' Path(__file__).with_suffix(".active").write_text("active")\n'
                  ' while not Path(__file__).with_suffix(".release").exists():\n  time.sleep(0.005)\n'
                  ' print(json.dumps(reply(request)),flush=True)\n')
        command = os.environ['HOST_PYTHON_STDIO']
        client = transport._Stdio(command)
        result = []
        def first():
            try:
                result.append(client.call('urn:wm:probe', {'value': 1}, '', timeout=5))
            except Exception as error:
                result.append(error)
        thread = threading.Thread(target=first)
        thread.start()
        active = Path(shlex.split(command)[-1]).with_suffix('.active')
        deadline = time.monotonic() + 2
        while not active.exists() and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.005)
        try:
            self.assertTrue(active.exists(), result)
            with self.assertRaises(TimeoutError):
                client.call('urn:wm:probe', {'value': 2}, '', timeout=0.05)
        finally:
            active.with_suffix('.release').touch()
            thread.join(timeout=3)
        self.assertEqual({'value': 1}, result[0]['output'])
        self.assertIsNone(client.p.poll())
        self.assertEqual({'value': 3}, client.call('urn:wm:probe', {'value': 3}, '', timeout=2)['output'])

    def test_concurrent_first_callers_share_one_host(self):
        self.host('for line in sys.stdin:\n print(json.dumps(reply(json.loads(line))),flush=True)\n')
        self.spawn_delay = 0.03
        barrier = threading.Barrier(6)
        def invoke(number):
            barrier.wait(timeout=3)
            return transport.call('python', 'stdio', 'urn:wm:probe', {'number': number})
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(invoke, range(6)))
        self.assertEqual(1, len(self.clients))
        self.assertEqual([{'number': n} for n in range(6)], [r['output'] for r in results])

    def test_repeated_calls_reuse_and_close_the_worker(self):
        self.host('for line in sys.stdin:\n print(json.dumps(reply(json.loads(line))),flush=True)\n')
        for number in range(3):
            self.assertEqual({'number': number}, self.call({'number': number})['output'])
        self.assertEqual(1, len(self.clients))
        client = self.clients[0]
        client.close()
        self.assertFalse(client.worker.is_alive())
        self.assertIsNotNone(client.p.poll())
        self.assertTrue(client.p.stdin.closed and client.p.stdout.closed)

    @unittest.skipUnless(os.name == 'posix', 'signal zero is a nondestructive process probe on POSIX')
    def test_normal_interpreter_shutdown_reaps_cached_host(self):
        self.host('for line in sys.stdin:\n print(json.dumps(reply(json.loads(line))),flush=True)\n')
        result = subprocess.run([sys.executable, '-c',
            'import json;from gateway import transport;'
            'result=transport.call("python","stdio","urn:wm:probe",{"value":1});'
            'client=transport._stdio[transport.addr("python","stdio")];'
            'print(json.dumps({"result":result,"pid":client.p.pid}),flush=True)'],
            cwd=transport.ROOT, capture_output=True, text=True, timeout=5, check=True)
        observed = json.loads(result.stdout)
        self.assertIs(observed['result']['ok'], True)
        with self.assertRaises(ProcessLookupError):
            os.kill(observed['pid'], 0)


if __name__ == '__main__':
    unittest.main()
