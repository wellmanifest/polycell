"""Live contract-driven checks: installed cells/processes, persistence and MCP."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

from gateway import core


def request(base, path, data=None):
    req = Request(base + path, data=None if data is None else json.dumps(data).encode(),
                  headers={'content-type': 'application/json'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def check_process(result, example):
    if not result.get('ok'):
        raise AssertionError(result)
    for field, expected in example.get('expect', {}).items():
        actual = core._get(result['output'], '$.' + field)
        if not core._eq(actual, expected):
            raise AssertionError(f'process output {field}: {actual!r} != {expected!r}')
    if 'output' in example and not core._eq(result['output'], example['output']):
        raise AssertionError('process output mismatch')


def check_mcp(base, cases):
    messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
    checks = []
    for urn, case in cases.items():
        name = core.CELLS[urn]['name'].replace('.', '_')
        messages.append({'jsonrpc': '2.0', 'id': len(messages) + 1, 'method': 'tools/call',
                         'params': {'name': name, 'arguments': case['input']}})
        checks.append(('cell', case))
    for name, process in core.PROCESSES.items():
        for example in process.get('examples', []):
            messages.append({'jsonrpc': '2.0', 'id': len(messages) + 1, 'method': 'tools/call',
                             'params': {'name': 'process_' + name, 'arguments': example['input']}})
            checks.append(('process', example))
    result = subprocess.run([sys.executable, '-m', 'gateway.mcp'],
                            input=''.join(json.dumps(m) + '\n' for m in messages), text=True,
                            capture_output=True, cwd=core.ROOT, timeout=30 + 20 * len(checks), check=True,
                            env={**os.environ, 'WM_GATEWAY_URL': base})
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert [r['id'] for r in replies] == [m['id'] for m in messages], replies
    names = {cell['name'].replace('.', '_') for cell in core.CELLS.values()}
    names |= {'process_' + name for name in core.PROCESSES}
    assert {tool['name'] for tool in replies[1]['result']['tools']} == names
    for reply, (kind, expected) in zip(replies[2:], checks):
        assert reply['result']['isError'] is False, reply
        value = json.loads(reply['result']['content'][0]['text'])
        if kind == 'process':
            check_process(value, expected)
        else:
            assert value['ok'] and core._eq(value['output'], expected['output']), value
    print(f'MCP: {len(names)} tools, {len(checks)} calls PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-only', action='store_true')
    args = parser.parse_args()
    base = os.environ.get('APP_URL', 'http://127.0.0.1:8080').rstrip('/')
    cases = {}
    for case in json.loads((core.ROOT / 'tests/generated/cases.json').read_text()):
        cases.setdefault(case['urn'], case)
    assert set(cases) == set(core.CELLS), 'every installed cell requires a behavior case'
    remote = request(base, '/api/cells')
    assert remote['cells'] == core.CELLS, 'gateway is serving a different application'
    if not args.mcp_only:
        for transport in os.environ.get('TEST_TRANSPORTS', 'http,grpc,stdio').split(','):
            for urn, case in cases.items():
                result = request(base, '/api/invoke', {'urn': urn, 'input': case['input'], 'transport': transport})
                assert result['ok'] and core._eq(result['output'], case['output']), result
                assert result['contract'] == core.CELLS[urn]['contract'], result
                rows = request(base, '/api/invocations?limit=100')
                assert any(row['trace_id'] == result['trace_id'] and row['ok'] for row in rows), result
            for name, process in core.PROCESSES.items():
                for example in process.get('examples', []):
                    result = request(base, f'/api/process/{quote(name)}?transport={transport}', example['input'])
                    check_process(result, example)
                    rows = request(base, '/api/invocations?limit=100')
                    persisted = [row for row in rows if row['trace_id'] == result['receipt']['trace_id']]
                    assert len(persisted) == len(result['receipt']['steps']), result
            print(f'Application + persistence ({transport}): {len(cases)} cells, {len(core.PROCESSES)} processes PASS')
        assert request(base, '/api/logs?tail=5'), 'missing logs'
    check_mcp(base, cases)


if __name__ == '__main__':
    main()
