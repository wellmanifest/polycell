"""Klienci transportu do hostów komórek: http | grpc | stdio. Wszystkie zwracają ten sam envelope.

Adresy hostów (env):  HOST_<LANG>_HTTP, HOST_<LANG>_GRPC, HOST_<LANG>_STDIO (komenda)
"""
from __future__ import annotations

import atexit
import json
import math
import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("POLYCELL_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "gen" / "python"))

DEFAULTS = {
    "python": {"http": "http://127.0.0.1:8101", "grpc": "127.0.0.1:9101",
               "stdio": f"{sys.executable} {ROOT}/hosts/python/host.py --stdio"},
    "ts": {"http": "http://127.0.0.1:8102", "grpc": "127.0.0.1:9102",
           "stdio": f"node --experimental-strip-types --no-warnings {ROOT}/hosts/ts/host.ts --stdio"},
    "rust": {"http": "http://127.0.0.1:8103", "grpc": "127.0.0.1:9103",
             "stdio": f"{ROOT}/hosts/rust/target/release/host --stdio"},
}
TRANSPORTS = ("http", "grpc", "stdio")
STDIO_TIMEOUT = 10.0


def addr(lang: str, transport: str) -> str:
    return os.environ.get(f"HOST_{lang.upper()}_{transport.upper()}", DEFAULTS[lang][transport])


def call_http(lang: str, urn: str, data: dict, trace_id: str) -> dict:
    req = urllib.request.Request(addr(lang, "http") + "/v1/invoke",
                                 data=json.dumps({"urn": urn, "input": data, "trace_id": trace_id}).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


_grpc_stubs: dict[str, object] = {}


def call_grpc(lang: str, urn: str, data: dict, trace_id: str) -> dict:
    import grpc
    from polycell.v1 import cellhost_pb2 as pb, cellhost_pb2_grpc as rpc
    target = addr(lang, "grpc")
    if target not in _grpc_stubs:
        _grpc_stubs[target] = rpc.CellHostStub(grpc.insecure_channel(target))
    r = _grpc_stubs[target].Invoke(pb.InvokeRequest(urn=urn, json_input=json.dumps(data), trace_id=trace_id), timeout=10)
    return {"urn": r.urn, "ok": r.ok, "output": json.loads(r.json_output) if r.json_output else None,
            "error": r.error, "lang": r.lang, "duration_ms": r.duration_ms, "contract": r.contract}


class _Stdio:
    """Długo żyjący proces hosta w trybie --stdio (np. jako narzędzie CLI / sidecar bez sieci)."""

    def __init__(self, cmd: str):
        self.p = subprocess.Popen(shlex.split(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                  start_new_session=os.name == "posix")
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.requests = queue.Queue(maxsize=1)
        self._close_lock = threading.Lock()
        self.worker = threading.Thread(target=self._serve, name="polycell-stdio", daemon=True)
        self.worker.start()

    def _serve(self):
        try:
            while not self.closed.is_set():
                request = self.requests.get()
                if request is None:
                    break
                payload, done, result = request
                try:
                    if self.closed.is_set():
                        raise EOFError("stdio host is closed")
                    self.p.stdin.write(payload)
                    self.p.stdin.flush()
                    line = self.p.stdout.readline()
                    if not line:
                        raise EOFError("stdio host closed stdout")
                    result["response"] = json.loads(line)
                except Exception as error:  # noqa: BLE001 - delivered to the calling thread
                    result["error"] = error
                    self.close()
                finally:
                    done.set()
        finally:
            for stream in (self.p.stdin, self.p.stdout):
                try:
                    stream.close()
                except OSError:
                    pass

    def close(self):
        with self._close_lock:
            if not self.closed.is_set():
                self.closed.set()
                if self.p.poll() is None:
                    try:
                        if os.name == "posix":
                            os.killpg(self.p.pid, signal.SIGKILL)
                        else:
                            self.p.kill()
                    except ProcessLookupError:
                        pass
                try:
                    self.p.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    self.requests.put_nowait(None)
                except queue.Full:
                    pass
        if threading.current_thread() is not self.worker:
            self.worker.join(timeout=1)

    def call(self, urn, data, trace_id, timeout=STDIO_TIMEOUT):
        deadline = time.monotonic() + timeout
        if not self.lock.acquire(timeout=max(0, deadline - time.monotonic())):
            raise TimeoutError("stdio request timed out waiting for host")
        try:
            if self.closed.is_set():
                raise EOFError("stdio host is closed")
            payload = json.dumps({"urn": urn, "input": data, "trace_id": trace_id}) + "\n"
            done, result = threading.Event(), {}
            self.requests.put_nowait((payload, done, result))
            if not done.wait(timeout=max(0, deadline - time.monotonic())):
                self.close()
                raise TimeoutError("stdio request timed out")
            if "error" in result:
                self.close()
                raise result["error"]
            return result["response"]
        finally:
            self.lock.release()


_stdio: dict[str, _Stdio] = {}
_stdio_lock = threading.Lock()


@atexit.register
def _close_stdio():
    with _stdio_lock:
        clients = list(_stdio.values())
        _stdio.clear()
    for client in clients:
        client.close()


def call_stdio(lang: str, urn: str, data: dict, trace_id: str) -> dict:
    cmd = addr(lang, "stdio")
    previous = None
    with _stdio_lock:
        client = _stdio.get(cmd)
        if client is None or client.closed.is_set() or client.p.poll() is not None:
            previous, client = client, _Stdio(cmd)
            _stdio[cmd] = client
    if previous is not None:
        previous.close()
    try:
        return client.call(urn, data, trace_id, timeout=STDIO_TIMEOUT)
    finally:
        if client.closed.is_set():
            with _stdio_lock:
                if _stdio.get(cmd) is client:
                    del _stdio[cmd]


def _validate_response(response, lang: str, urn: str) -> dict:
    """Validate the common wire envelope before trusting any host metadata."""
    def invalid(reason):
        raise ValueError(f"invalid host response: {reason}")

    if not isinstance(response, dict):
        invalid("expected object")
    required = {"urn", "ok", "output", "error", "lang", "duration_ms", "contract"}
    if missing := required - response.keys():
        invalid("missing fields: " + ", ".join(sorted(missing)))
    if type(response["ok"]) is not bool:
        invalid("ok must be boolean")
    if response["urn"] != urn:
        invalid("urn mismatch")
    if response["lang"] != lang:
        invalid("lang mismatch")
    for field in ("error", "contract"):
        if not isinstance(response[field], str):
            invalid(f"{field} must be string")
    duration = response["duration_ms"]
    if (type(duration) not in (int, float) or duration < 0
            or (isinstance(duration, float) and not math.isfinite(duration))):
        invalid("duration_ms must be finite and nonnegative")
    if response["ok"] != (response["error"] == ""):
        invalid("ok and error disagree")
    try:
        json.dumps(response, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        invalid("expected finite JSON values")
    return dict(response)


def call(lang: str, transport: str, urn: str, data: dict, trace_id: str = "") -> dict:
    t0 = time.perf_counter()
    try:
        if transport not in TRANSPORTS:
            raise ValueError(f"unsupported transport: {transport}")
        fn = {"http": call_http, "grpc": call_grpc, "stdio": call_stdio}[transport]
        r = _validate_response(fn(lang, urn, data, trace_id), lang, urn)
    except Exception as e:  # noqa: BLE001
        r = {"urn": urn, "ok": False, "output": None, "error": f"transport {transport}: {e}", "lang": lang}
    r["transport"] = transport
    r["rtt_ms"] = round((time.perf_counter() - t0) * 1000, 3)  # pełny round-trip przez protokół
    return r
