"""Tests for Polycell /v1/poa/registry endpoint, CLI export, and URTLog sync."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from gateway import core, poa_registry
from gateway.app import H


class PolycellPoaRegistryTests(unittest.TestCase):
    def test_poa_registry_payload_covers_cells_processes_and_queries(self) -> None:
        payload = poa_registry.poa_registry()
        self.assertEqual(payload["schema"], "polycell.poa-registry/v1")
        self.assertEqual(payload["systems"], ["polycell"])
        self.assertEqual(payload["total"], len(payload["operations"]))
        by_uri = {op["uri"]: op for op in payload["operations"]}

        expected_cells = {
            "customer.validate": ("urn:wm:cell:shop:customer.validate:v1", ["db:write"], "proc"),
            "notify.render": ("urn:wm:cell:shop:notify.render:v1", ["pure"], "query"),
            "pricing.quote": ("urn:wm:cell:shop:pricing.quote:v1", ["db:write"], "proc"),
            "shipping.cost": ("urn:wm:cell:shop:shipping.cost:v1", ["pure"], "query"),
        }
        for name, (urn, effects, kind) in expected_cells.items():
            uri = f"proc://wellmanifest/polycell/cell/{name}/v1"
            self.assertIn(uri, by_uri)
            op = by_uri[uri]
            self.assertEqual(op["urn"], urn)
            self.assertEqual(op["effects"], effects)
            self.assertEqual(op["kind"], kind)
            self.assertEqual(op["system"], "polycell")

        checkout = by_uri["proc://wellmanifest/polycell/process/checkout/v1"]
        self.assertIn("poa://shop.local/process/checkout/v1", checkout["aliases"])
        self.assertEqual(checkout["kind"], "proc")
        self.assertIn("local_write", checkout["effects"])

        parity = by_uri["proc://wellmanifest/polycell/parity/v1"]
        self.assertEqual(parity["authority"], "none")
        self.assertEqual(parity["effects"], ["pure"])
        self.assertIn("proc://wellmanifest/polycell/poa-registry/v1", by_uri)

    def test_http_endpoint_serves_poa_registry(self) -> None:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/v1/poa/registry", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=2)
        self.assertEqual(body["schema"], "polycell.poa-registry/v1")
        self.assertEqual(body["total"], len(core.CELLS) + len(core.PROCESSES) + 2)

    def test_cli_poa_registry_outputs_json(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "gateway.cli", "poa-registry"],
            cwd=str(core.ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        body = json.loads(proc.stdout)
        self.assertEqual(body["schema"], "polycell.poa-registry/v1")
        self.assertGreaterEqual(body["total"], 7)

    @unittest.skipIf(importlib.util.find_spec("urtlog") is None, "uritime-urtlog optional package not installed")
    def test_real_urtlog_unified_registry_imports_polycell_poa(self) -> None:
        from urtlog import AccessContext
        from urtlog.registry import UnifiedRegistry

        payload = poa_registry.poa_registry()
        with tempfile.TemporaryDirectory() as td:
            unified = UnifiedRegistry(td)
            try:
                imported = unified.import_poa_registry(payload)
                self.assertEqual(imported, payload["total"])
                ctx = AccessContext("tom", roles=frozenset({"admin"}), max_sensitivity="secret")
                uris = {row["address"] for row in unified.search(ctx, kind="uri", system="polycell")}
                urns = {row["address"] for row in unified.search(ctx, kind="urn", system="polycell")}
                self.assertIn("proc://wellmanifest/polycell/cell/pricing.quote/v1", uris)
                self.assertIn("proc://wellmanifest/polycell/process/checkout/v1", uris)
                self.assertIn("urn:wm:cell:shop:pricing.quote:v1", urns)
                self.assertIn("urn:wm:cell:shop:customer.validate:v1", urns)
            finally:
                unified.close()


if __name__ == "__main__":
    unittest.main()
