"""Install pinned Forge/SubLLM provider wheels without mutating their checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def provider_paths(root: Path) -> tuple[Path, Path]:
    venv = root / ".subactor/cache/forge-provider"
    legacy = root / ".run/forge-provider"
    for path in (root / ".subactor", venv.parent, venv, legacy.parent):
        if path.is_symlink():
            raise ValueError(f"provider path must not be a symlink: {path}")
        if path.exists() and not path.is_dir():
            raise ValueError(f"provider path must be a directory: {path}")
    if legacy.is_symlink():
        if legacy.resolve() != venv.resolve():
            raise ValueError(f"provider compatibility symlink has a foreign target: {legacy}")
    elif legacy.exists():
        raise ValueError(
            f"legacy provider exists at {legacy}; migrate it to {venv} and replace "
            "it with a symlink after verifying no process is using it")
    return venv, legacy


def install(root: Path, forge_root: Path) -> Path:
    venv, legacy = provider_paths(root)
    lock = json.loads((root / "integrations/forge.lock.json").read_text())
    wheels = []
    for rel, expected in lock["wheels"].items():
        path = forge_root / rel
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"wheel digest mismatch: {rel}")
        wheels.append(str(path.resolve()))
    venv.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = str(venv / "bin/python")
    subprocess.run([python, "-m", "pip", "install", "jsonschema==4.26.0", "PyYAML==6.0.3"], check=True)
    subprocess.run([python, "-m", "pip", "install", "--no-deps", *wheels], check=True)
    # Publish the documented path only after the pinned installation succeeds.
    provider_paths(root)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    if not legacy.is_symlink():
        legacy.symlink_to(os.path.relpath(venv, legacy.parent), target_is_directory=True)
    return venv / "bin/python"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge-root", type=Path, required=True)
    args = parser.parse_args()
    print(install(ROOT, args.forge_root))


if __name__ == "__main__":
    main()
