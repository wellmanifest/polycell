"""Trusted container evaluator. Candidate code never supplies its own oracle/runner."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from forge_base.sandbox import run_bounded
from jsonschema import Draft202012Validator
from tools.polycell.package import assemble, check_oracle


def main():
    start = time.monotonic()
    candidate, oracle = Path("/candidate"), Path("/oracle")
    meta = check_oracle(candidate, oracle)
    work = Path("/tmp/project")
    assemble([candidate], work, runtime=Path("/app"), warm=meta["owner"] == "rust", record_git=False)
    env = {**os.environ, "POLYCELL_ROOT": str(work), "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
    if meta["owner"] == "ts":
        (work / "hosts/ts/node_modules").symlink_to("/app/hosts/ts/node_modules")
    run_bounded([sys.executable, str(work / "tools/polycell/gen.py")], cwd=work, env=env, timeout=20)
    run_bounded([sys.executable, str(work / "standard/conformance.py"), "--root", str(work)], cwd=work, env=env, timeout=20)
    if meta["owner"] == "rust":
        compiler = ("import subprocess; r = subprocess.run(['cargo','build','--release','--locked','--offline'], "
                    "stderr=subprocess.STDOUT); print('POLYCELL_BUILD_STATUS=' + str(r.returncode), flush=True)")
        build_log = run_bounded([sys.executable, "-c", compiler], cwd=work / "hosts/rust", env=env, timeout=120).decode()
        if not build_log.rstrip().endswith("POLYCELL_BUILD_STATUS=0"):
            raise ValueError("Rust compilation failed: " + build_log[-4000:])
    build_s = time.monotonic() - start
    commands = {
        "python": [sys.executable, str(work / "hosts/python/host.py"), "--stdio"],
        "ts": ["node", "--experimental-strip-types", "--no-warnings", str(work / "hosts/ts/host.ts"), "--stdio"],
        "rust": [str(work / "hosts/rust/target/release/host"), "--stdio"],
    }
    cases = json.loads((oracle / "cases.json").read_text())
    requests = "".join(json.dumps({"urn": meta["urn"], "input": c["input"], "trace_id": "package-test"}) + "\n" for c in cases)
    raw = run_bounded(commands[meta["owner"]], requests.encode(), cwd=work, env=env, timeout=20, limit=2_000_000)
    replies = [json.loads(line) for line in raw.splitlines()]
    if len(replies) != len(cases):
        raise ValueError("unexpected number of candidate replies")
    # Use the same tolerant numeric comparator as the gateway's transport parity.
    sys.path.insert(0, str(work))
    os.environ["POLYCELL_ROOT"] = str(work)
    from gateway.core import _eq
    output_validator = Draft202012Validator(json.loads((oracle / "output.schema.json").read_text()))
    for case, reply in zip(cases, replies):
        output_validator.validate(reply.get("output"))
        if not reply.get("ok") or reply.get("contract") != meta["contract"] or not _eq(reply.get("output"), case["output"]):
            raise ValueError(f"behavior mismatch: {case.get('name', 'case')}")
    print(json.dumps({"schema": "wellmanifest.polycell.qualification/v1", "ok": True, "urn": meta["urn"],
                      "owner": meta["owner"], "cases": len(cases), "transport": "stdio", "network": "none",
                      "build_s": round(build_s, 3), "elapsed_s": round(time.monotonic() - start, 3)}))


if __name__ == "__main__":
    main()
