"""Install pinned Forge/SubLLM provider wheels without mutating their checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge-root", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((ROOT / "integrations/forge.lock.json").read_text())
    wheels = []
    for rel, expected in lock["wheels"].items():
        path = args.forge_root / rel
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"wheel digest mismatch: {rel}")
        wheels.append(str(path.resolve()))
    venv = ROOT / ".run/forge-provider"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = str(venv / "bin/python")
    subprocess.run([python, "-m", "pip", "install", "jsonschema==4.26.0", "PyYAML==6.0.3"], check=True)
    subprocess.run([python, "-m", "pip", "install", "--no-deps", *wheels], check=True)
    print(python)


if __name__ == "__main__":
    main()
