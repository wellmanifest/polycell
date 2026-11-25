"""Opt-in, zero-mandatory-dependency bridge emitting Polycell Python host invocations into uritime-urtlog."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class _CellInvocationFailed(Exception):
    """Signal a failed cell result to the span without exposing its error text."""


def maybe_emit_polycell_invoke(
    urn: str,
    data: dict[str, Any],
    result: dict[str, Any],
    *,
    trace_id: str = "",
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Emit a Polycell cell invocation into `uritime-urtlog` when explicitly opted in via `URTLOG_STATE_DIR`.

    Never raises or alters cell invocation results.
    """
    raw_dir = str(state_dir).strip() if state_dir is not None else os.environ.get("URTLOG_STATE_DIR", "").strip()
    if not raw_dir:
        return {"emitted": False, "reason": "disabled"}

    try:
        from urtlog.sdk import UrtClient
    except ImportError:
        return {"emitted": False, "reason": "urtlog_not_installed"}

    commissioned_by = os.environ.get("URTLOG_COMMISSIONED_BY", "").strip() or "polycell:host-python"
    recipients_raw = os.environ.get("URTLOG_RECIPIENTS", "group:ops,heyasa")
    recipients = tuple(r.strip() for r in recipients_raw.split(",") if r.strip())
    try:
        encoded_input = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        in_hash = hashlib.sha256(encoded_input).hexdigest()[:16]
        in_urn = f"urn:polycell:input:{in_hash}"
        out_urn = f"urn:polycell:output:{trace_id or in_hash}"
        with UrtClient(Path(raw_dir), source="polycell", repository="wellmanifest/polycell") as client:
            with client.span(
                urn,
                inputs={in_urn: data},
                commissioned_by=commissioned_by,
                executed_by="polycell:host-python",
                recipients=recipients,
                parent_run_id=trace_id or None,
            ) as sp:
                sp.emit_log(
                    "metric",
                    {"duration_ms": result.get("duration_ms"), "ok": bool(result.get("ok")), "contract": result.get("contract", "")},
                    summary=f"polycell invoke {urn} ok={result.get('ok')}",
                )
                if result.get("ok"):
                    sp.commit_output(out_urn, result.get("output") if result.get("output") is not None else {})
                else:
                    raise _CellInvocationFailed("cell invocation failed")
        return {"emitted": True, "urn": urn, "ok": True}
    except _CellInvocationFailed:
        return {"emitted": True, "urn": urn, "ok": False}
    except Exception as exc:  # noqa: BLE001 - optional telemetry must never disrupt cell host
        return {"emitted": False, "reason": f"emit_error:{type(exc).__name__}"}
