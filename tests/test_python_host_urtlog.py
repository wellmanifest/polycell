from __future__ import annotations

import builtins
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HOST_DIR = Path(__file__).resolve().parents[1] / "hosts" / "python"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from urtlog_bridge import maybe_emit_polycell_invoke  # noqa: E402


class PolycellUrtLogBridgeTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "URTLOG_STATE_DIR"}
        with mock.patch.dict(os.environ, env, clear=True):
            res = maybe_emit_polycell_invoke("urn:polycell:demo:echo", {"x": 1}, {"ok": True, "output": {"x": 1}})
        self.assertEqual(res, {"emitted": False, "reason": "disabled"})

    def test_graceful_when_urtlog_missing(self) -> None:
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "urtlog.sdk" or name.startswith("urtlog"):
                raise ImportError("simulated missing uritime-urtlog")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"URTLOG_STATE_DIR": td}):
                with mock.patch.object(builtins, "__import__", side_effect=fake_import):
                    res = maybe_emit_polycell_invoke("urn:polycell:demo:echo", {"x": 1}, {"ok": True, "output": {"x": 1}})
        self.assertEqual(res, {"emitted": False, "reason": "urtlog_not_installed"})

    @unittest.skipIf(importlib.util.find_spec("urtlog") is None, "uritime-urtlog optional package not installed")
    def test_emits_span_and_registers_cell_urn(self) -> None:
        from urtlog import AccessContext, UrtClient

        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td) / "urtlog"
            with mock.patch.dict(os.environ, {"URTLOG_STATE_DIR": str(state_dir), "URTLOG_COMMISSIONED_BY": "user:tom"}):
                emitted = maybe_emit_polycell_invoke(
                    "urn:polycell:demo:echo",
                    {"value": 42},
                    {"ok": True, "output": {"value": 42}, "duration_ms": 1.2, "contract": "demo.echo/v1"},
                    trace_id="trace-poly-1",
                )
            self.assertEqual(emitted, {"emitted": True, "urn": "urn:polycell:demo:echo", "ok": True})

            ctx = AccessContext("tom", roles=frozenset({"admin"}), groups=frozenset({"ops"}), max_sensitivity="secret")
            with UrtClient(state_dir, source="polycell", repository="wellmanifest/polycell") as client:
                tree = client.store.logic_tree(ctx, op_prefix="op/urn/polycell/demo/echo/")
                self.assertGreaterEqual(tree["total_events"], 5)
                self.assertIn("in_flight:metric", tree["ascii"])
                reg = client.registry.search(ctx, kind="uri", prefix="op/urn/polycell/demo/echo/")
                self.assertEqual(len(reg), 1)


if __name__ == "__main__":
    unittest.main()
