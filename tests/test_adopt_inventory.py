from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools" / "polycell"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import adopt  # noqa: E402


def _write_py(path: Path, fn_name: str = "classify_blocker") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"def {fn_name}(item, rules):\n"
        "    if not item:\n"
        "        return 'invalid'\n"
        "    return rules.get(item, 'known')\n",
        encoding="utf-8",
    )


class AdoptInventoryExclusionTests(unittest.TestCase):
    def test_inventory_src_excludes_worktrees_governance_venv_build_and_gen(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write_py(tmp_path / "pkg" / "flowguard.py", "classify_blocker")
            _write_py(tmp_path / "pkg" / "contest_helper.py", "evaluate_contest")

            # Non-domain paths present in Wellmanifest v5 / Polycell checkouts that must never be indexed:
            for excluded in (
                tmp_path / ".worktrees" / "ticket-001--demo" / "pkg" / "flowguard.py",
                tmp_path / "worktrees" / "legacy" / "pkg" / "flowguard.py",
                tmp_path / ".governance" / "work_start_check.py",
                tmp_path / ".venv" / "lib" / "python3.13" / "site-packages" / "dep.py",
                tmp_path / "venv" / "lib" / "dep.py",
                tmp_path / "build" / "lib" / "pkg" / "flowguard.py",
                tmp_path / "dist" / "artifact.py",
                tmp_path / "gen" / "python" / "cells.py",
                tmp_path / ".run" / "scratch.py",
                tmp_path / "pkg.egg-info" / "entry.py",
                tmp_path / "tests" / "helper.py",
                tmp_path / "pkg" / "test_flowguard.py",
            ):
                _write_py(excluded, "classify_blocker")

            inv = adopt.inventory_src(tmp_path)
            seen_files = [c["file"] for c in inv["candidates"]]

            # "contest_helper.py" contains substring "test_" mid-word and must NOT be skipped.
            self.assertEqual(seen_files, ["pkg/contest_helper.py", "pkg/flowguard.py"])
            self.assertEqual(inv["functions_seen"], 2)

    def test_inventory_map_excludes_worktrees_governance_build_and_gen(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            map_file = tmp_path / "map.toon.yaml"
            map_file.write_text(
                "# demo map\n"
                "M[6]:\n"
                "  src/flowguard.py,120\n"
                "  .governance/branch_lifecycle_check.py,200\n"
                "  .worktrees/ticket-010--fix/src/flowguard.py,120\n"
                "  build/lib/flowguard.py,120\n"
                "  gen/types.py,80\n"
                "  .venv/lib/site.py,300\n"
                "D:\n"
                "  src/flowguard.py:\n"
                "    classify_blocker(item;rules)\n"
                "  .governance/branch_lifecycle_check.py:\n"
                "    evaluate(snapshot;focus_branch)\n"
                "  .worktrees/ticket-010--fix/src/flowguard.py:\n"
                "    classify_blocker(item;rules)\n"
                "  build/lib/flowguard.py:\n"
                "    classify_blocker(item;rules)\n"
                "  gen/types.py:\n"
                "    validate_payload(data)\n"
                "  .venv/lib/site.py:\n"
                "    resolve_paths(prefix)\n",
                encoding="utf-8",
            )

            inv = adopt.inventory_map(map_file)
            self.assertEqual([c["file"] for c in inv["candidates"]], ["src/flowguard.py"])
            self.assertEqual(inv["functions_seen"], 1)


if __name__ == "__main__":
    unittest.main()
