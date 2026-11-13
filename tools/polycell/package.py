"""One implementation file plus data artifacts, portable as a Git repository/bundle.

Verification checks integrity and contract shape; qualification executes against an
explicit trusted oracle in a container. Neither a manifest nor a receipt is a signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from standard.conformance import HEADER, IMPURE, interface_hash

EXT = {"python": "py", "ts": "ts", "rust": "rs"}
ARTIFACTS = {"contract.cell.yaml", "cases.json", "types.txt", "prompt.md", "input.schema.json", "output.schema.json"}
RUNTIME_DIRS = ("tools", "standard", "integrations", "hosts", "proto", "gateway", "db", "docker", "twin")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def verify(directory: Path) -> dict:
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("package must be a real directory")
    entries = {p.name: p for p in directory.iterdir() if p.name != ".git"}
    if any(p.is_symlink() or not p.is_file() or p.stat().st_size > 2_000_000 for p in entries.values()):
        raise ValueError("only bounded regular files are allowed in a package")
    manifest = json.loads(entries["package.json"].read_text())
    schema = json.loads((ROOT / "standard/polycell-package.schema.v1.json").read_text())
    Draft202012Validator(schema).validate(manifest)
    source = "cell." + EXT[manifest["owner"]]
    required = ARTIFACTS | {source, "README.md"}
    if manifest["implementation"] != source or set(manifest["files"]) not in (required, required | {"provider.json"}):
        raise ValueError("exactly one implementation and the declared data artifacts are required")
    if set(entries) != set(manifest["files"]) | {"package.json"}:
        raise ValueError("unlisted or missing package file")
    for name, expected in manifest["files"].items():
        if digest(entries[name].read_bytes()) != expected:
            raise ValueError(f"digest mismatch: {name}")
    contract = yaml.safe_load(entries["contract.cell.yaml"].read_text())
    Draft202012Validator(json.loads((ROOT / "standard/polycell-cell.schema.v1.json").read_text())).validate(contract)
    if any(manifest[key] != contract[key] for key in ("urn", "name", "owner")):
        raise ValueError("package identity does not match contract")
    if contract.get("effects") != ["pure"] or contract.get("impl", "cell") != "cell":
        raise ValueError("v1 packages require a pure, non-legacy cell")
    if interface_hash(contract) != manifest["contract"]:
        raise ValueError("contract hash mismatch")
    text = entries[source].read_text()
    header = HEADER.search("\n".join(text.splitlines()[:5]))
    if not header or header["urn"] != manifest["urn"] or header["hash"] != manifest["contract"]:
        raise ValueError("implementation has a stale/missing contract header")
    if IMPURE[EXT[manifest["owner"]]].search(text):
        raise ValueError("known I/O pattern inside a pure cell")
    cases = json.loads(entries["cases.json"].read_text())
    if not isinstance(cases, list) or not cases:
        raise ValueError("package requires at least one behavior case")
    for case in cases:
        for kind in ("input", "output"):
            Draft202012Validator(json.loads(entries[f"{kind}.schema.json"].read_text())).validate(case[kind])
    return manifest


def write_package(out: Path, identity: dict, files: dict[str, bytes]) -> dict:
    out = Path(out)
    if out.exists():
        raise ValueError(f"destination already exists: {out}")
    manifest = {**identity, "files": {k: digest(v) for k, v in sorted(files.items())}}
    out.mkdir(parents=True)
    try:
        for name, value in files.items():
            if Path(name).name != name:
                raise ValueError("non-flat package file")
            (out / name).write_bytes(value)
        (out / "package.json").write_bytes(json_bytes(manifest))
        verify(out)
    except Exception:
        shutil.rmtree(out)
        raise
    return manifest


def export(name: str, out: Path) -> dict:
    from tools.polycell import prompt
    from tools.polycell.model import load_cells
    cell = next(c for c in load_cells() if c.name == name)
    cases = [c for c in json.loads((ROOT / "tests/generated/cases.json").read_text()) if c["urn"] == cell.urn]
    types = {"python": "python/polycell_types.py", "ts": "ts/types.ts", "rust": "rust/types.rs"}
    files = {
        "cell." + EXT[cell.owner]: cell.cell_path.read_bytes(),
        "contract.cell.yaml": cell.path.read_bytes(),
        "cases.json": json_bytes(cases),
        "types.txt": (ROOT / "gen" / types[cell.owner]).read_bytes(),
        "prompt.md": prompt.build(name).encode(),
        "README.md": (f"# {cell.urn}\n\nOne editable implementation: cell.{EXT[cell.owner]}.\n"
                      "The remaining files are contract, test, type, prompt and integrity artifacts.\n"
                      "Execution requires the shared Polycell runtime; this is not a standalone application.\n"
                      "Regenerate the complete implementation; qualify against the trusted baseline before assembly.\n").encode(),
    }
    for kind in ("input", "output"):
        files[f"{kind}.schema.json"] = (ROOT / f"gen/jsonschema/{name}.{kind}.json").read_bytes()
    return write_package(out, {"schema": "wellmanifest.polycell.package/v1", "urn": cell.urn, "name": name,
                              "owner": cell.owner, "implementation": "cell." + EXT[cell.owner],
                              "contract": cell.interface_hash, "runtime": "wellmanifest.polycell/v1"}, files)


def replace(base: Path, source: str, out: Path, metrics: dict | None = None) -> dict:
    manifest = verify(base)
    files = {name: (base / name).read_bytes() for name in manifest["files"] if name != "provider.json"}
    files[manifest["implementation"]] = source.encode()
    if metrics is not None:
        files["provider.json"] = json_bytes(metrics)
    return write_package(out, {k: v for k, v in manifest.items() if k != "files"}, files)


def check_oracle(candidate: Path, oracle: Path) -> dict:
    current, trusted = verify(candidate), verify(oracle)
    for key in ("urn", "name", "owner", "contract", "implementation"):
        if current[key] != trusted[key]:
            raise ValueError("candidate must retain the trusted interface")
    for name in ARTIFACTS:
        if current["files"][name] != trusted["files"][name]:
            raise ValueError(f"candidate changed trusted artifact: {name}")
    return current


def git_snapshot(directory: Path, bundle: Path | None = None) -> str:
    verify(directory)
    if (directory / ".git").exists():
        raise ValueError("refusing to rewrite an existing Git repository")
    if bundle and (bundle.exists() or bundle.resolve().is_relative_to(directory.resolve())):
        raise ValueError("bundle must be a new path outside the package")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(directory), *args], stderr=subprocess.STDOUT, text=True).strip()
    git("init", "-b", "main")
    git("add", ".")
    git("-c", "user.name=Polycell package", "-c", "user.email=polycell@localhost", "commit", "-m", "Snapshot single-cell package")
    if bundle:
        bundle.parent.mkdir(parents=True, exist_ok=True)
        git("bundle", "create", str(bundle.resolve()), "main")
    return git("rev-parse", "HEAD")


def assemble(packages: list[Path], out: Path, runtime: Path = ROOT, warm: bool = False, record_git: bool = True) -> dict:
    manifests = [verify(p) for p in packages]
    for key in ("urn", "name"):
        if len({m[key] for m in manifests}) != len(manifests):
            raise ValueError(f"duplicate {key}; parallel majors with the same name are not supported yet")
    stems = [m["name"].replace(".", "_") for m in manifests]
    if len(set(stems)) != len(stems):
        raise ValueError("implementation filename collision")
    if out.exists():
        raise ValueError("assembly destination must be new")
    out.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "target")
    for name in RUNTIME_DIRS:
        if (runtime / name).exists():
            shutil.copytree(runtime / name, out / name, ignore=ignore)
    for name in ("Makefile", "requirements.txt", ".gitignore", ".dockerignore", ".nvmrc", "compose.yml", "AGENTS.md"):
        if (runtime / name).exists():
            shutil.copy2(runtime / name, out / name)
    for part in ("contracts/cells", "contracts/processes", "tests/golden", "cells/python", "cells/ts", "cells/rust"):
        (out / part).mkdir(parents=True)
    for path in (runtime / "tests").glob("*.py"):
        shutil.copyfile(path, out / "tests" / path.name)
    lock = {"schema": "wellmanifest.polycell.cellset/v1", "packages": [], "processes": []}
    for package, manifest in zip(packages, manifests):
        name, owner = manifest["name"], manifest["owner"]
        shutil.copyfile(package / "contract.cell.yaml", out / f"contracts/cells/{name}.cell.yaml")
        shutil.copyfile(package / manifest["implementation"], out / f"cells/{owner}/{name.replace('.', '_')}.{EXT[owner]}")
        cases = json.loads((package / "cases.json").read_text())
        contract = yaml.safe_load((package / "contract.cell.yaml").read_text())
        examples = {name + ":" + c["name"] for c in contract.get("examples", [])}
        (out / f"tests/golden/{name}.jsonl").write_text("".join(json.dumps({k: c[k] for k in ("input", "output")}) + "\n"
                                                                    for c in cases if c.get("name") not in examples))
        commit = None
        if record_git and (package / ".git").exists():
            if subprocess.check_output(["git", "-C", str(package), "status", "--porcelain"]):
                raise ValueError("Git package must be committed before assembly")
            commit = subprocess.check_output(["git", "-C", str(package), "rev-parse", "HEAD"], text=True).strip()
        lock["packages"].append({"urn": manifest["urn"], "manifest_sha256": digest((package / "package.json").read_bytes()), "git_commit": commit})
    urns = {m["urn"] for m in manifests}
    for path in (runtime / "contracts/processes").glob("*.process.yaml"):
        process = yaml.safe_load(path.read_text())
        if {step["capability_ref"] for step in process["steps"]} <= urns:
            shutil.copyfile(path, out / "contracts/processes" / path.name)
            lock["processes"].append({"process_ref": process["process_ref"], "sha256": digest(path.read_bytes())})
    (out / "cellset.lock.json").write_bytes(json_bytes(lock))
    if warm:
        for path in ("hosts/ts/node_modules", "hosts/rust/target"):
            if (runtime / path).exists():
                shutil.copytree(runtime / path, out / path)
        if (runtime / "gen/python/polycell").exists():
            shutil.copytree(runtime / "gen/python/polycell", out / "gen/python/polycell")
    return lock


def qualify(candidate: Path, oracle: Path, image: str, timeout: int = 180) -> dict:
    manifest = check_oracle(candidate, oracle)
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True).strip()
    import uuid
    container = "polycell-check-" + uuid.uuid4().hex[:12]
    command = ["docker", "run", "--rm", "--name", container, "--network", "none", "--read-only",
               "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--pids-limit", "128", "--cpus", "2", "--memory", "3g", "--tmpfs", "/tmp:rw,exec,size=1536m",
               "-v", f"{ROOT / 'tools'}:/harness/tools:ro", "-v", f"{ROOT / 'standard'}:/harness/standard:ro",
               "-v", f"{candidate.resolve()}:/candidate:ro",
               "-v", f"{oracle.resolve()}:/oracle:ro", image_id, "python", "/harness/tools/polycell/package_worker.py"]
    # Files bound container logs on disk instead of retaining arbitrary candidate output in RAM.
    import tempfile
    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=log, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ValueError("qualification deadline exceeded") from None
        finally:
            subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        log.seek(0, 2)
        size = log.tell()
        log.seek(max(0, size - 100_000))
        lines = log.read().decode(errors="replace").splitlines()
    if result.returncode:
        raise ValueError("qualification failed: " + "\n".join(lines[-20:]))
    receipt = json.loads(lines[-1])
    if not receipt.get("ok") or receipt.get("urn") != manifest["urn"]:
        raise ValueError("invalid qualification receipt")
    receipt["candidate_sha256"] = digest((candidate / "package.json").read_bytes())
    receipt["oracle_sha256"] = digest((oracle / "package.json").read_bytes())
    receipt["image"] = image_id
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("cell"); e.add_argument("--out", type=Path, required=True)
    e.add_argument("--git", action="store_true"); e.add_argument("--bundle", type=Path)
    v = sub.add_parser("verify"); v.add_argument("package", type=Path)
    a = sub.add_parser("assemble"); a.add_argument("packages", type=Path, nargs="+"); a.add_argument("--out", type=Path, required=True)
    q = sub.add_parser("qualify"); q.add_argument("package", type=Path); q.add_argument("--oracle", type=Path, required=True)
    q.add_argument("--image", default="polycell/package-worker:dev"); q.add_argument("--receipt", type=Path)
    args = p.parse_args()
    if args.cmd == "export":
        result = export(args.cell, args.out)
        if args.git or args.bundle:
            result = {"manifest": result, "git_commit": git_snapshot(args.out, args.bundle)}
    elif args.cmd == "verify": result = verify(args.package)
    elif args.cmd == "assemble":
        result = assemble(args.packages, args.out)
        subprocess.run([sys.executable, str(args.out / "tools/polycell/gen.py")], check=True)
    else:
        result = qualify(args.package, args.oracle, args.image)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(json_bytes(result))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
