// Postgres bez demona: PGlite (Postgres skompilowany do WASM) w jednym procesie Node,
// dane w katalogu (jak plik SQLite), wystawiony protokołem wire Postgresa dla dowolnego klienta.
// Uwaga: PGlite = jedno połączenie naraz -> gateway używa jednego połączenia (lock).
import { PGlite } from "@electric-sql/pglite";
import { PGLiteSocketServer } from "@electric-sql/pglite-socket";

const dataDir = process.env.PGLITE_DATA ?? "./.run/pglite";
const port = Number(process.env.PGPORT ?? 5432);
const db = await PGlite.create(dataDir === "memory" ? undefined : dataDir);
const server = new PGLiteSocketServer({ db, port, host: process.env.PGHOST ?? "0.0.0.0" });
await server.start();
console.log(JSON.stringify({ svc: "db-pglite", event: "listening", port, dataDir }));
const stop = async () => { await server.stop(); await db.close(); process.exit(0); };
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
