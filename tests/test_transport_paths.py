"""Relocated applications must launch hosts with literal filesystem paths."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

from gateway import transport
from tools.polycell import package


@contextmanager
def relocated_transport(root, executable=None):
    # A fresh module models a new gateway starting inside the relocated app.
    with patch.dict(os.environ, {"POLYCELL_ROOT": str(root)}), \
         patch.object(sys, "path", sys.path.copy()), \
         patch.object(sys, "executable", executable or sys.executable):
        for language in ("PYTHON", "TS", "RUST"):
            os.environ.pop(f"HOST_{language}_STDIO", None)
        spec = importlib.util.spec_from_file_location("relocated_transport", transport.__file__)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            yield module
        finally:
            module._close_stdio()


class StdioPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cell_package = self.root / "package"
        package.export("shipping.cost", self.cell_package)

    def assemble(self, name):
        app = self.root / name
        package.assemble([self.cell_package], app, generate=True)
        return app

    def check_shipping(self, module, app):
        cases = json.loads((app / "tests/generated/cases.json").read_text())
        self.assertTrue(cases)
        for index, case in enumerate(cases):
            response = module.call("python", "stdio", case["urn"], case["input"], f"relocated-{index}")
            self.assertTrue(response["ok"], response)
            self.assertEqual(case["output"], response["output"])
        self.assertEqual(1, len(module._stdio), "host must be reused across calls")

    def test_relocated_application_uses_default_python_host(self):
        for name in ("application with spaces", "O'Brien \"quoted\" żółć"):
            with self.subTest(name=name):
                app = self.assemble(name)
                with relocated_transport(app) as module:
                    self.check_shipping(module, app)

    @unittest.skipUnless(os.name == "posix", "interpreter symlink fixture requires POSIX")
    def test_interpreter_path_is_one_argument(self):
        app = self.assemble("application")
        executable = self.root / "Python's binaries" / "python interpreter"
        executable.parent.mkdir()
        executable.symlink_to(sys.executable)
        with relocated_transport(app, str(executable)) as module:
            self.check_shipping(module, app)

    def test_explicit_command_preserves_literal_arguments_without_shell_expansion(self):
        app = self.root / "unused app's directory"
        host = self.root / "custom host's.py"
        host.write_text('import json, sys\n'
                        'for line in sys.stdin:\n'
                        ' request = json.loads(line)\n'
                        ' print(json.dumps({"urn": request["urn"], "ok": True, "error": "",\n'
                        '  "output": {"arguments": sys.argv[1:], "input": request["input"]},\n'
                        '  "lang": "python", "duration_ms": 0, "contract": "custom"}), flush=True)\n')
        arguments = ['argument with "quotes" and spaces', '$UNCHANGED;literal']
        command = shlex.join([sys.executable, str(host), *arguments])
        with relocated_transport(app) as module, \
             patch.dict(os.environ, {"HOST_PYTHON_STDIO": command}):
            response = module.call("python", "stdio", "urn:wm:cell:test:custom:v1", {"value": 7})
            self.assertTrue(response["ok"], response)
            self.assertEqual({"arguments": arguments, "input": {"value": 7}}, response["output"])


if __name__ == "__main__":
    unittest.main()
