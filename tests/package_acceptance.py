"""Optional integration: real Git bundles and Forge-bounded Docker qualification."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.polycell import package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, help='Optional shipping.cost proposal, qualified against the exported baseline')
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('use a new acceptance output directory')
    args.out.mkdir(parents=True)
    report = {'schema': 'wellmanifest.polycell.package-acceptance/v1', 'packages': [], 'ok': False}
    started = time.monotonic()
    clones = []
    for name in ('customer.validate', 'notify.render', 'pricing.quote', 'shipping.cost'):
        original = args.out / 'exports' / name
        package.export(name, original)
        if name == 'shipping.cost' and args.candidate:
            receipt = package.qualify(args.candidate, original, 'polycell/package-worker:dev')
            report['generated_candidate'] = receipt
            candidate = args.out / 'candidate'
            shutil.copytree(args.candidate, candidate, ignore=shutil.ignore_patterns('.git'))
            original = candidate
        bundle = args.out / 'bundles' / (name + '.bundle')
        commit = package.git_snapshot(original, bundle)
        clone = args.out / 'clones' / name
        subprocess.run(['git', 'clone', '--quiet', str(bundle.resolve()), str(clone)], check=True)
        receipt = package.qualify(clone, original, 'polycell/package-worker:dev')
        receipt.update(git_commit=commit, bundle_bytes=bundle.stat().st_size)
        report['packages'].append(receipt)
        clones.append(clone)
    oracle = args.out / 'exports/shipping.cost'
    manifest = package.verify(oracle)
    code = (f'# polycell: urn={manifest["urn"]} contract={manifest["contract"]}\n'
            'from polycell_types import ShippingCostInput, ShippingCostOutput\n\n'
            'def run(input: ShippingCostInput) -> ShippingCostOutput:\n'
            '    return {"result": 0.0}\n')
    bad = args.out / 'bad-candidate'
    package.replace(oracle, code, bad)
    try:
        package.qualify(bad, oracle, 'polycell/package-worker:dev')
    except ValueError as error:
        if 'behavior mismatch' not in str(error):
            raise
        report['bad_candidate_rejected'] = True
    else:
        raise AssertionError('wrong implementation was accepted')
    app = args.out / 'app'
    lock = package.assemble(clones, app, generate=True)
    report.update(ok=True, elapsed_s=round(time.monotonic() - started, 3), cellset=lock)
    (args.out / 'report.json').write_bytes(package.json_bytes(report))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
