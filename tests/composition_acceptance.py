"""Native end-to-end acceptance of an app containing only one cell and no POA process."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.polycell import package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ts-http-port', default='8102')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise ValueError('use a new acceptance output directory')
    started = time.monotonic()
    source, app = out / 'package', out / 'app'
    package.export('shipping.cost', source)
    package.assemble([source], app)
    # A required string may legally be empty; the UI used to silently omit it.
    contract_path = app / 'contracts/cells/shipping.cost.cell.yaml'
    contract = yaml.safe_load(contract_path.read_text())
    contract['examples'].insert(0, {'name': 'empty_country', 'input': {'weight_kg': 1, 'country': ''},
                                    'output': {'result': 29.99}})
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False))
    for path in ('.venv', 'hosts/ts/node_modules', 'db/pglite/node_modules'):
        (app / path).symlink_to(ROOT / path, target_is_directory=True)
    shutil.copytree(ROOT / 'hosts/rust/target', app / 'hosts/rust/target')
    command = ['make', '-C', str(app), 'check', 'dev', 'parity', 'testql', 'test',
               'integration', 'chrome', 'cdp', 'TS_HTTP_PORT=' + args.ts_http_port]
    try:
        with (out / 'test.log').open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600)
            if result.returncode:
                subprocess.run(['make', '-C', str(app), 'diag'], stdout=log, stderr=subprocess.STDOUT, timeout=30)
                raise RuntimeError(f'composed application failed: {out / "test.log"}')
    finally:
        subprocess.run(['make', '-C', str(app), 'stop'], check=True, timeout=20)
    report = json.loads((app / 'artifacts/twin/cdp-report.json').read_text())
    assert report['ok'] and len(report['results']) == 1, report
    assert not any(r['consoleErrors'] or r['networkErrors'] for r in report['results']), report
    output = {'ok': True, 'cells': 1, 'processes': 0,
              'cases': len(json.loads((app / 'tests/generated/cases.json').read_text())),
              'browser_steps': sum(len(r['steps']) for r in report['results']),
              'elapsed_s': round(time.monotonic() - started, 3), 'empty_required_string': 'PASS'}
    (out / 'report.json').write_bytes(package.json_bytes(output))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
