"""Forge/SubLLM proposal adapter for a single Polycell implementation file.

This uses Forge's provider and bounded process API, not its graph-specific
Manager evaluator. Polycell's independent package oracle accepts behavior.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.polycell.package import check_oracle, digest, new_directory, qualify, replace, snapshot, verify

HARNESS = "# Polycell adapter envelope; preserve exactly.\n"
KERNEL = "fn main() {}\n"


class ProposalRejected(ValueError):
    """A received model answer violated the requested file or contract identity."""


def request(package: Path, objective: str) -> dict:
    manifest = verify(package)
    target = "generated/" + manifest["implementation"]
    prompt = (
        "Generate one pure Polycell cell. Keep harness_py and kernel_rs byte-for-byte equal to the baseline. "
        f"Put the ENTIRE implementation in files with exactly one key: {target}. "
        "Do not add helpers, tests, dependencies, Markdown fences or patches. "
        "The JSON envelope required by the system replaces the Markdown output-format instruction in the cell prompt. "
        "Preserve the exact first-line header and all example/golden behavior. "
        "Use a short, straightforward implementation. "
        "Each files value must be a string containing source code, not a JSON object or lambda. "
        f"Exact JSON control values: harness_py = {json.dumps(HARNESS)}; kernel_rs = {json.dumps(KERNEL)}. "
        "Preserve their terminal newline characters.\n\n" + (package / "prompt.md").read_text()
        + "\nAcceptance cases (input -> expected output):\n" + (package / "cases.json").read_text()
        + "\nRegeneration objective and latest qualification feedback:\n" + objective
    )
    return {"prompt": prompt, "baseline": {"harness.py": HARNESS, "kernel.rs": KERNEL}}


def extract(bundle: dict, manifest: dict) -> str:
    if bundle["harness_py"] != HARNESS or bundle["kernel_rs"] != KERNEL:
        raise ValueError("model changed the Forge envelope sentinels")
    target = "generated/" + manifest["implementation"]
    if set(bundle["files"]) != {target}:
        raise ValueError("model must return exactly one complete cell file")
    return bundle["files"][target]


def stamp_header(code: str, manifest: dict) -> str:
    """Controller owns identity metadata; never repair or patch the function body.

    Missing headers and a misspelled marker are normalized. A conflicting URN
    or interface hash is rejected rather than relabeling a different contract.
    """
    lines = code.splitlines(keepends=True)
    marker = re.compile(r"^\s*(?:#|//)\s*\w+:\s*urn=(\S+)\s+contract=(\S+)\s*$")
    for line in lines[:5]:
        match = marker.match(line)
        if match and (match[1], match[2]) != (manifest["urn"], manifest["contract"]):
            raise ValueError("model proposed a different contract identity")
    if lines and marker.match(lines[0]):
        lines = lines[1:]
    prefix = "#" if manifest["owner"] == "python" else "//"
    return f"{prefix} polycell: urn={manifest['urn']} contract={manifest['contract']}\n" + "".join(lines)


def worker():
    from forge_base.providers import ProviderError
    from forge_base.subllm_adapter import SubLLMConfig, SubLLMProvider
    data = json.load(sys.stdin)
    provider = SubLLMProvider(SubLLMConfig.from_env())
    try:
        bundle = provider.propose(data["prompt"], data["baseline"])
    except ProviderError as error:
        print(json.dumps({"error": str(error), "metrics": provider.last_metrics}))
        return
    print(json.dumps({"bundle": bundle, "metrics": provider.last_metrics}))


def propose(package: Path, out: Path, audit: Path, model: str, base_url: str,
            objective: str, timeout: float = 180, reasoning_effort: str | None = None) -> dict:
    from forge_base.sandbox import run_bounded
    from subllm.local_runtime import render_profiles
    manifest = verify(package)
    if out.exists() or audit.exists():
        raise ValueError("proposal and audit destinations must be new")
    profiles = render_profiles(base_url=base_url, model=model, routes=("heyasa/command",))
    audit = audit.absolute()
    audit.mkdir(parents=True, mode=0o700)
    policy = audit / "subllm.toml"
    policy_text = profiles["subllm.toml"]
    if reasoning_effort is not None:
        if reasoning_effort not in {"none", "low", "medium", "high"}:
            raise ValueError("invalid reasoning effort")
        policy_text += '\n[custom_providers.local-development.model_parameters]\nreasoning_effort = ' + json.dumps(reasoning_effort) + '\n'
    policy.write_text(policy_text)
    # Explicit local-only environment: no ambient keys, fallback, proxy or shared audit DB.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "USER") if key in os.environ}
    env.update({"SUBLLM_POLICY_FILE": str(policy), "SUBLLM_USAGE_DB": str(audit / "usage.sqlite3"),
                "SUBLLM_ARCHIVE_DIR": str(audit / "archive"), "SUBLLM_CREDENTIAL_SOURCE": "process",
                "SUBLLM_USE_LOCAL_POSTGRES": "0", "FORGE_SUBLLM_APPLICATION": "heyasa",
                "FORGE_SUBLLM_FUNCTION": "command", "FORGE_ALLOW_REMOTE": "0",
                "FORGE_PROVIDER_TIMEOUT": str(timeout * 0.9), "PYTHONDONTWRITEBYTECODE": "1"})
    raw = run_bounded([sys.executable, str(Path(__file__).resolve()), "--worker"],
                      json.dumps(request(package, objective)).encode(), cwd=ROOT, env=env, timeout=timeout, limit=4_000_000)
    answer = json.loads(raw)
    (audit / "metrics.json").write_text(json.dumps(answer["metrics"], indent=2) + "\n")
    if "error" in answer:
        raise ValueError(answer["error"])
    (audit / "bundle.json").write_text(json.dumps(answer["bundle"], indent=2) + "\n")
    try:
        raw_code = extract(answer["bundle"], manifest)
        code = stamp_header(raw_code, manifest)
    except ValueError as error:
        raise ProposalRejected(str(error)) from error
    answer["metrics"]["header_normalized"] = code != raw_code
    replace(package, code, out, answer["metrics"])
    return {"package": str(out), "metrics": answer["metrics"], "qualification": "required"}


def regenerate(package: Path, out: Path, audit: Path, model: str, base_url: str,
               objective: str, oracle: Path, image: str, attempts: int = 3,
               timeout: float = 180, reasoning_effort: str | None = None) -> dict:
    """Regenerate whole files using bounded feedback; publish only qualified code."""
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("attempts must be between 1 and 3")
    package, oracle, out, audit = (p.absolute() for p in (package, oracle, out, audit))
    if os.path.lexists(out) or os.path.lexists(audit):
        raise ValueError("proposal and audit destinations must be new")
    for target in (out.resolve(), audit.resolve()):
        for source in (package.resolve(), oracle.resolve()):
            if target.is_relative_to(source) or source.is_relative_to(target):
                raise ValueError("output and audit must be outside the source packages")
    if out.resolve().is_relative_to(audit.resolve()) or audit.resolve().is_relative_to(out.resolve()):
        raise ValueError("output and audit destinations must be disjoint")
    check_oracle(package, oracle)
    audit.mkdir(parents=True, mode=0o700)
    baseline, trusted = audit / "baseline", audit / "oracle"
    snapshot(package, baseline)
    snapshot(oracle, trusted)
    report = {"schema": "wellmanifest.polycell.regeneration/v1", "ok": False, "attempts": []}

    def record():
        staged = audit / "report.tmp"
        staged.write_text(json.dumps(report, indent=2) + "\n")
        staged.replace(audit / "report.json")

    feedback = ""
    for number in range(1, attempts + 1):
        directory = audit / f"attempt-{number:03}"
        directory.mkdir()
        candidate = directory / "candidate"
        entry = {"number": number, "candidate": str(candidate), "stage": "proposal"}
        report["attempts"].append(entry)
        record()
        try:
            propose(baseline, candidate, directory / "provider", model, base_url,
                    objective + feedback, timeout, reasoning_effort)
        except ProposalRejected as error:
            entry.update(stage="proposal_rejected", error=str(error)[-4000:])
            record()
            feedback = ("\nThe previous complete proposal failed file or contract validation. "
                        "Regenerate the ENTIRE file and preserve the unchanged contract and all cases. "
                        "Diagnostic:\n" + entry["error"])
            continue
        except (ValueError, RuntimeError, OSError) as error:
            entry["error"] = str(error)[-4000:]
            record()
            raise ValueError(f"generation failed; see {audit / 'report.json'}") from error
        entry["stage"] = "qualification"
        record()
        try:
            receipt = qualify(candidate, trusted, image)
        except ValueError as error:
            entry["error"] = str(error)[-4000:]
            record()
            feedback = ("\nThe previous complete implementation failed independent qualification. "
                        "Regenerate the ENTIRE file and preserve the unchanged contract and all cases. "
                        "Diagnostic:\n" + entry["error"])
            continue
        # Bind publication to exactly the candidate that the evaluator accepted.
        with new_directory(out) as staged:
            snapshot(candidate, staged)
            if receipt["candidate_sha256"] != digest((staged / "package.json").read_bytes()):
                raise ValueError("candidate changed after qualification")
        entry.update(stage="accepted", qualification=receipt)
        report["ok"] = True
        record()
        return {"package": str(out), "qualification": receipt, "attempts": number, "audit": str(audit)}
    raise ValueError(f"no qualified candidate after {attempts} attempts; see {audit / 'report.json'}")


def replay(package: Path, out: Path, audit: Path) -> dict:
    """Explicitly re-evaluate one archived native response; never count a new call."""
    from forge_base.providers import validate_bundle
    from subllm.interaction_store import InteractionStore
    manifest = verify(package)
    audit = audit.resolve()
    metrics = json.loads((audit / "metrics.json").read_text())
    request_id = metrics["request_id"]
    with sqlite3.connect((audit / "usage.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("select * from attempts where request_id = ? and status = 'success'",
                          (hashlib.sha256(request_id.encode()).hexdigest()[:24],)).fetchall()
    if len(rows) != 1 or not rows[0]["archive_id"]:
        raise ValueError("replay requires exactly one archived successful native attempt")
    row = rows[0]
    saved = InteractionStore(audit / "archive").get_interaction(row["archive_id"], row["archive_day"])
    original = json.loads(saved["request"]["messages"][1]["content"])
    if saved["correlation_id"] != request_id or (package / "prompt.md").read_text() not in original["objective"]:
        raise ValueError("archive does not bind this package context")
    if original["baseline"] != {"harness.py": HARNESS, "kernel.rs": KERNEL}:
        raise ValueError("archive has a different Forge baseline")
    code = extract(validate_bundle(json.loads(saved["response"]["content"])), manifest)
    stamped = stamp_header(code, manifest)
    metrics = {**metrics, "header_normalized": stamped != code, "replay": True, "new_inference_calls": 0}
    replace(package, stamped, out, metrics)
    return {"package": str(out), "metrics": metrics, "qualification": "required"}


def main():
    if sys.argv[1:] == ["--worker"]:
        return worker()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--replay-audit", type=Path, help="Explicit archived-response replay, without a model call")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--objective", default="Regenerate the complete function from its contract and examples.")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high"])
    parser.add_argument("--oracle", type=Path, help="Trusted package enabling qualification and bounded regeneration")
    parser.add_argument("--image", help="Qualification worker image (required with --oracle)")
    parser.add_argument("--attempts", type=int, default=3, help="Maximum whole-file proposals with --oracle (1..3)")
    args = parser.parse_args()
    if args.replay_audit:
        if args.oracle or args.image:
            parser.error("replay is separate from qualified regeneration")
        if args.audit or args.model:
            parser.error("replay is separate from a new model/audit request")
        print(json.dumps(replay(args.package, args.out, args.replay_audit), indent=2))
        return
    if not args.audit or not args.model:
        parser.error("new inference requires --audit and --model")
    if bool(args.oracle) != bool(args.image):
        parser.error("--oracle and --image must be provided together")
    if args.oracle:
        result = regenerate(args.package, args.out, args.audit, args.model, args.base_url,
                            args.objective, args.oracle, args.image, args.attempts, args.timeout, args.reasoning_effort)
        print(json.dumps(result, indent=2))
        return
    print(json.dumps(propose(args.package, args.out, args.audit, args.model, args.base_url, args.objective, args.timeout, args.reasoning_effort), indent=2))


if __name__ == "__main__":
    main()
