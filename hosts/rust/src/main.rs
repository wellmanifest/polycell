//! Cell host Rust: HTTP/JSON :8103, gRPC polycell.v1.CellHost :9103, stdio JSON-lines (--stdio).
//! Komórki z cells/rust/*.rs są wkompilowane przez wygenerowany gen/rust/registry.rs.
use std::time::Instant;

use axum::{routing::{get, post}, Json, Router};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

pub mod types {
    include!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../gen/rust/types.rs"));
}
pub mod registry {
    include!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../gen/rust/registry.rs"));
}
pub mod pb {
    tonic::include_proto!("polycell.v1");
}

const LANG: &str = "rust";

fn contract_of(urn: &str) -> &'static str {
    registry::CELLS.iter().find(|c| c.0 == urn).map(|c| c.1).unwrap_or("")
}

fn invoke(urn: &str, input: Value, trace_id: &str) -> Value {
    let t0 = Instant::now();
    let r = registry::dispatch(urn, input);
    let ms = (t0.elapsed().as_secs_f64() * 1e6).round() / 1e3;
    let (ok, output, error) = match r {
        Ok(v) => (true, v, String::new()),
        Err(e) => (false, Value::Null, e),
    };
    eprintln!("{}", json!({"svc": "host-rust", "event": "invoke", "urn": urn, "ok": ok, "ms": ms, "trace_id": trace_id, "error": if error.is_empty() { Value::Null } else { json!(error) }}));
    json!({"urn": urn, "ok": ok, "output": output, "error": error, "lang": LANG, "duration_ms": ms, "contract": contract_of(urn)})
}

fn cells() -> Value {
    json!({"lang": LANG, "cells": registry::CELLS.iter().map(|c| json!({"urn": c.0, "contract": c.1})).collect::<Vec<_>>() })
}

struct Grpc;

#[tonic::async_trait]
impl pb::cell_host_server::CellHost for Grpc {
    async fn invoke(&self, req: tonic::Request<pb::InvokeRequest>) -> Result<tonic::Response<pb::InvokeResponse>, tonic::Status> {
        let q = req.into_inner();
        let input: Value = serde_json::from_str(if q.json_input.is_empty() { "{}" } else { &q.json_input })
            .map_err(|e| tonic::Status::invalid_argument(e.to_string()))?;
        let r = invoke(&q.urn, input, &q.trace_id);
        Ok(tonic::Response::new(pb::InvokeResponse {
            urn: q.urn,
            ok: r["ok"].as_bool().unwrap_or(false),
            json_output: r["output"].to_string(),
            error: r["error"].as_str().unwrap_or("").into(),
            lang: LANG.into(),
            duration_ms: r["duration_ms"].as_f64().unwrap_or(0.0),
            contract: r["contract"].as_str().unwrap_or("").into(),
        }))
    }
    async fn list(&self, _r: tonic::Request<pb::ListRequest>) -> Result<tonic::Response<pb::ListResponse>, tonic::Status> {
        Ok(tonic::Response::new(pb::ListResponse {
            lang: LANG.into(),
            cells: registry::CELLS.iter().map(|c| pb::CellInfo { urn: c.0.into(), contract: c.1.into(), cell: c.2.into() }).collect(),
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    if std::env::args().any(|a| a == "--stdio") {
        let mut lines = BufReader::new(tokio::io::stdin()).lines();
        let mut out = tokio::io::stdout();
        while let Some(line) = lines.next_line().await? {
            if line.trim().is_empty() { continue; }
            let q: Value = serde_json::from_str(&line)?;
            let r = invoke(q["urn"].as_str().unwrap_or(""), q["input"].clone(), q["trace_id"].as_str().unwrap_or(""));
            out.write_all(format!("{r}\n").as_bytes()).await?;
            out.flush().await?;
        }
        return Ok(());
    }
    let http: u16 = std::env::var("HTTP_PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8103);
    let grpc: u16 = std::env::var("GRPC_PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(9103);
    let app = Router::new()
        .route("/health", get(|| async { Json(json!({"ok": true, "lang": LANG})) }))
        .route("/v1/cells", get(|| async { Json(cells()) }))
        .route("/v1/invoke", post(|Json(q): Json<Value>| async move {
            Json(invoke(q["urn"].as_str().unwrap_or(""), q["input"].clone(), q["trace_id"].as_str().unwrap_or("")))
        }));
    let grpc_srv = tonic::transport::Server::builder()
        .add_service(pb::cell_host_server::CellHostServer::new(Grpc))
        .serve(([0, 0, 0, 0], grpc).into());
    let listener = tokio::net::TcpListener::bind(("0.0.0.0", http)).await?;
    eprintln!("{}", json!({"svc": "host-rust", "event": "listening", "http": http, "grpc": grpc, "cells": cells()["cells"]}));
    let (a, b) = tokio::join!(axum::serve(listener, app), grpc_srv);
    a?;
    b?;
    Ok(())
}
