# Error Catalog — wellmanifest/polycell

Consumer error catalog for `wellmanifest/polycell` conformance checks implemented in
[`standard/conformance.py`](../standard/conformance.py) and documented in
[`docs/SPEC.md`](../docs/SPEC.md).

Run [`python3 standard/conformance.py --root .`](../standard/conformance.py) to
verify all contracts, cells, processes, and generated artifacts.

| Code | Severity | Summary | Runbook |
| --- | --- | --- | --- |
| `PC001` | ERROR | Invalid cell contract (schema, URN, owner, declared effects, or unknown type) | [`PC001.md`](./PC001.md) |
| `PC002` | ERROR | Duplicate URN or conflicting type definitions with the same name | [`PC002.md`](./PC002.md) |
| `PC003` | ERROR / WARNING | Missing cell implementation (`GAP`), missing managed header, `STALE` implementation, or `STUB` (`WARNING`) | [`PC003.md`](./PC003.md) |
| `PC004` | ERROR | Orphan cell implementation file without a matching contract | [`PC004.md`](./PC004.md) |
| `PC005` | WARNING | Missing contract examples (no contract test cases) | [`PC005.md`](./PC005.md) |
| `PC006` | ERROR | Process contract violation (unknown URN, dependency ordering, transport address in definition, or mutating `query`) | [`PC006.md`](./PC006.md) |
| `PC007` | ERROR | Generated artifacts out of date or missing `gen/registry.json` | [`PC007.md`](./PC007.md) |
| `PC008` | ERROR | Prohibited I/O in a cell declared `pure` | [`PC008.md`](./PC008.md) |
| `PC009` | WARNING | Superseded legacy code still present | [`PC009.md`](./PC009.md) |
