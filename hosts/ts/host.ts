// Cell host TypeScript (Node 22+, natywne usuwanie typów - bez kroku build).
// Ładuje cells/ts/*.ts i wystawia: HTTP/JSON :8102, gRPC polycell.v1.CellHost :9102, stdio JSON-lines.
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createInterface } from "node:readline";

const ROOT = process.env.POLYCELL_ROOT ?? resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const LANG = "ts";
const INDEX: Record<string, { name: string; owner: string; contract: string }> =
  JSON.parse(readFileSync(join(ROOT, "gen/cells.index.json"), "utf8")).cells;
const mine = () => Object.keys(INDEX).filter((u) => INDEX[u].owner === LANG);

const log = (o: Record<string, unknown>) =>
  process.stderr.write(JSON.stringify({ ts: Date.now() / 1000, svc: "host-ts", ...o }) + "\n");

async function load(urn: string) {
  const file = join(ROOT, "cells/ts", INDEX[urn].name.replaceAll(".", "_") + ".ts");
  const v = statSync(file).mtimeMs; // hot-reload po podmianie pliku komórki
  return import(pathToFileURL(file).href + "?v=" + v);
}

export async function invoke(urn: string, input: unknown, trace_id = "") {
  const t0 = performance.now();
  const res: Record<string, unknown> = { urn, ok: false, output: null, error: "", lang: LANG, contract: INDEX[urn]?.contract ?? "" };
  try {
    if (!mine().includes(urn)) throw new Error(`urn not hosted here: ${urn}`);
    res.output = (await load(urn)).run(input);
    res.ok = true;
  } catch (e) {
    res.error = String(e);
  }
  res.duration_ms = Math.round((performance.now() - t0) * 1000) / 1000;
  log({ event: "invoke", urn, ok: res.ok, ms: res.duration_ms, trace_id, error: res.error || undefined });
  return res;
}

function send(r: ServerResponse, code: number, o: unknown) {
  const b = JSON.stringify(o);
  r.writeHead(code, { "content-type": "application/json", "content-length": Buffer.byteLength(b) }).end(b);
}

async function body(req: IncomingMessage): Promise<any> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  return JSON.parse(Buffer.concat(chunks).toString() || "{}");
}

async function serveGrpc(port: number) {
  try {
    const grpc = await import("@grpc/grpc-js");
    const loader = await import("@grpc/proto-loader");
    const def = loader.loadSync(join(ROOT, "proto/polycell/v1/cellhost.proto"), { keepCase: true, defaults: true });
    const pkg: any = grpc.loadPackageDefinition(def).polycell;
    const server = new grpc.Server();
    server.addService(pkg.v1.CellHost.service, {
      Invoke: async (call: any, cb: any) => {
        const r: any = await invoke(call.request.urn, JSON.parse(call.request.json_input || "{}"), call.request.trace_id);
        cb(null, { ...r, json_output: JSON.stringify(r.output) });
      },
      List: (_c: any, cb: any) => cb(null, { lang: LANG, cells: mine().map((u) => ({ urn: u, contract: INDEX[u].contract })) }),
    });
    await new Promise<void>((ok, err) =>
      server.bindAsync(`0.0.0.0:${port}`, grpc.ServerCredentials.createInsecure(), (e) => (e ? err(e) : ok())));
    return true;
  } catch (e) {
    log({ event: "grpc_disabled", reason: String(e) });
    return false;
  }
}

if (process.argv.includes("--stdio")) {
  const rl = createInterface({ input: process.stdin });
  for await (const line of rl) {
    if (!line.trim()) continue;
    const q = JSON.parse(line);
    process.stdout.write(JSON.stringify(await invoke(q.urn, q.input ?? {}, q.trace_id)) + "\n");
  }
} else {
  const httpPort = Number(process.env.HTTP_PORT ?? 8102);
  const grpcPort = Number(process.env.GRPC_PORT ?? 9102);
  const g = await serveGrpc(grpcPort);
  createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/health") return send(res, 200, { ok: true, lang: LANG });
    if (req.method === "GET" && req.url === "/v1/cells")
      return send(res, 200, { lang: LANG, cells: mine().map((u) => ({ urn: u, contract: INDEX[u].contract })) });
    if (req.method === "POST" && req.url === "/v1/invoke") {
      const q = await body(req);
      return send(res, 200, await invoke(q.urn, q.input ?? {}, q.trace_id));
    }
    send(res, 404, { error: "not found" });
  }).listen(httpPort, () => log({ event: "listening", http: httpPort, grpc: g ? grpcPort : null, cells: mine() }));
}
