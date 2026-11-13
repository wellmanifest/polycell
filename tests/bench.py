"""Benchmark protokołów: ta sama komórka (każdy język) przez http / grpc / stdio. p50/p95 round-trip."""
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway import transport  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
cases = {c["owner"]: c for c in json.loads(Path("tests/generated/cases.json").read_text())}
print(f"{'lang':7} {'transport':9} {'p50 ms':>8} {'p95 ms':>8} {'req/s':>8}")
for lang, c in cases.items():
    for tr in transport.TRANSPORTS:
        transport.call(lang, tr, c["urn"], c["input"])  # rozgrzewka / połączenie
        lat = []
        t0 = time.perf_counter()
        for _ in range(N):
            t = time.perf_counter()
            r = transport.call(lang, tr, c["urn"], c["input"])
            lat.append((time.perf_counter() - t) * 1000)
            assert r["ok"], r
        total = time.perf_counter() - t0
        lat.sort()
        print(f"{lang:7} {tr:9} {statistics.median(lat):8.3f} {lat[int(N * .95)]:8.3f} {N / total:8.0f}")
