# polycell — kontrakty → generowane interfejsy, logika jako wymienne pliki (Python · TypeScript · Rust)

> Propozycja standardu **`wellmanifest/polycell`** + działająca aplikacja przykładowa.
> Cel: w świecie kodu generowanego przez AI **nigdy nie refaktoryzować warstwy komunikacji** —
> interfejsy są generowane albo niezmienne, a logikę **regeneruje się całymi plikami**.

## Problem i odpowiedź w jednym akapicie

Generowanie nowego kodu jest tanie, a zmiana istniejącego — droga, bo każda zmiana danych rozlewa się na
serwer, klienta, typy, walidację, bazę i testy. Polycell rozcina to na trzy warstwy o różnej „prędkości zmian”:

| Warstwa | Jak powstaje | Jak się zmienia |
|---|---|---|
| **Transport** `proto/polycell/v1/cellhost.proto` (gRPC), `POST /v1/invoke` (HTTP), JSON-lines (stdio) | napisany raz | **nigdy** |
| **Interfejsy danych**: proto typowane, typy TS/Py/Rust, JSON Schema, OpenAPI, narzędzia MCP, SQL, rejestr API, testy, menu UI | `make gen` z kontraktu YAML | regeneracja (sekundy, deterministycznie) |
| **Logika**: `cells/<lang>/<nazwa>.<ext>` — jedna czysta funkcja `run(input) -> output` na plik | LLM z `make prompt CELL=…` | **regeneracja całego pliku**, nie łatanie |

Hosty (Python, TS, Rust) są generyczne — ładują komórki i wystawiają je trzema protokołami. Gateway robi REST,
UI, NL→API, MCP, procesy POA, walidację kontraktu i zapis każdego wywołania do Postgresa.

```mermaid
flowchart LR
  C[contracts/*.cell.yaml<br/>contracts/*.process.yaml] -->|make gen| G[gen/: proto · typy · JSON Schema<br/>OpenAPI · MCP · SQL · registry.json · testy]
  C -->|make prompt| L[LLM] -->|cały plik| CELLS[cells/python · cells/ts · cells/rust]
  subgraph Hosty — niezmienne
    HP[host-python] & HT[host-ts] & HR[host-rust]
  end
  CELLS --> HP & HT & HR
  UI[UI / CLI / MCP / NL / REST] --> GW[gateway<br/>walidacja · POA · trace]
  GW -- gRPC / HTTP / stdio<br/>polycell.v1.CellHost --> HP & HT & HR
  GW --> DB[(Postgres: PGlite / embedded / serwer<br/>wm_invocations + projekcje)]
  TW[digital twin: Chrome CDP · testql · logi docker] --> GW
```

## Szybki start

```bash
nvm use             # Node 22 (minimum 22.18); Python >=3.11, Rust i Chrome w PATH
make install        # tworzy .venv, instaluje pip + npm + cargo
make dev            # PGlite + 3 hosty + gateway, bez Dockera -> http://127.0.0.1:8080
make twin           # + Chrome CDP, parity, scenariusze testql i UI
# albo w Dockerze:
make up             # db, host-python, host-ts, host-rust, gateway
make docker-twin    # + chrome (CDP :9222), dozzle (logi :8888), testql, scenariusze UI
make help           # wszystkie komendy
```

Tryb Docker wymaga Docker Compose >=2.36 oraz buildx; Makefile włącza Compose Bake.
Obraz gatewaya zawiera trzy środowiska językowe, także do wywołań stdio.

## Weryfikacja 2026-11-13 (Linux, Python 3.13 / Node 22 / Rust 1.97)

Aktualny zakres, poprawki i ograniczenia opisuje [raport testów](docs/TESTING.md).
Do testów lokalnych użyto `TS_HTTP_PORT=18102`, ponieważ port 8102 zajmowała inna aplikacja.
Tę samą wartość należy przekazać do `make dev`, `make parity` i `make bench`.

- **Parytet protokołów**: 15 przypadków (przykłady + golden), rozdzielonych między 3 języki, × 3 protokoły {HTTP/JSON, gRPC/protobuf, stdio JSON-lines} = 45 wywołań — wszystkie zgodne z oczekiwaniem (`make parity`).
- **Proces POA** `poa://shop.local/process/checkout/v1`: Python (walidacja) → Rust (wycena) → TS (powiadomienie), z `plan_hash` i `poa.receipt/v1`.
- **MCP** (JSON-RPC stdio): `initialize`, `tools/list`, `tools/call` (`make mcp-test`).
- **Postgres bez demona**: PGlite (WASM) przez `@electric-sql/pglite-socket`, gateway przez psycopg; zapis envelope i projekcji.
- **Rejestr** `gen/registry.json` waliduje się względem oficjalnej schemy `wellmanifest.api-registry/v1` z `wellmanifest/nl-api-llm`.
- **Digital twin**: scenariusz UI przez Chrome DevTools Protocol (paleta NL, proces, przełączanie transportu, walidacja) — PASS, zrzuty w `artifacts/twin/`.
- **Scenariusze TestTOON** (`tests/generated/*.testql.toon.yaml`) — 5/5 PASS.
- **Docker**: obrazy zbudowane, `make docker-twin` — TestQL i CDP PASS; parytet oraz integracja HTTP/gRPC/stdio także PASS.
- **Regresje gatewaya i paczek**: `make test` — 39 testów (walidacja, błędy HTTP, Git, zgodność testów z kontraktem, składanie aplikacji i tożsamość kwalifikowanego kodu).
- **Integracja**: `make integration` — checkout przez trzy protokoły, trzy zapisane wywołania na proces, guard, logi i MCP.
- **Adopcja legacy**: przechodzą istniejące golden cases; `prune` wykrywa 3 odwołania do starej funkcji. Pełnego cyklu wrap/switch/usunięcie nie powtarzano podczas tej weryfikacji.

Pomiar round-trip (sekwencyjnie, 1 klient, localhost, `make bench N=300`):

| host | HTTP p50 | gRPC p50 | stdio p50 |
|---|---|---|---|
| python | 2.367 ms | 0.943 ms | 0.102 ms |
| ts | 1.098 ms | 1.307 ms | 0.250 ms |
| rust | 0.730 ms | 0.457 ms | 0.096 ms |

Pomiar obejmuje wykonanie komórki i round-trip; nie izoluje narzutu samego transportu.
Wykonano go na obciążonej maszynie podczas budowania obrazów. Wyniki zależą od środowiska;
nie stanowią gwarancji wydajności ani podstawy do uniwersalnego rankingu protokołów.

## Odpowiedzi na pytania projektowe

**SOA i POA z URI/URN, gRPC, protobuf — czy to się łączy?** Tak, i warstwy się nie dublują:
komórka = usługa (SOA) adresowana **URN** `urn:wm:cell:<ns>:<nazwa>:v<major>`; proces = kompozycja URN-ów (**POA**, `poa://…`),
bez adresów i protokołów w definicji — wiązanie URN → host/transport robi planner w gateway. Transport to protobuf/gRPC
z kopertą JSON (stabilna na zawsze); dla klientów chcących ścisłego typowania generowany jest `gen/proto/shop/cells.proto`
z wiadomościami per komórka. Wersja główna w URN = równoległe wersje bez łamania klientów.

**Jak zrzucać dane z requestów różnych API do DB?** Każde wywołanie dowolnym protokołem przechodzi przez jedną kopertę
(`trace_id, urn, transport, lang, ok, input, output, error, duration_ms, contract`) zapisywaną w `wm_invocations` (jsonb).
Komórka z `persist: {table: …}` dostaje dodatkowo wygenerowaną tabelę-projekcję z kolumnami `in_*`/`out_*`.
Schemat SQL jest generowany z kontraktu, więc dane i API nie rozjeżdżają się.

**Postgres „jak SQLite”, bez demona.** Trzy tryby, jedna zmienna `WM_DB`:
- `postgresql://…` do **PGlite** (Postgres skompilowany do WASM, jeden proces Node, dane w katalogu) — domyślny w `make dev` i w Dockerze. Ograniczenie: **jedno połączenie** — gateway trzyma jedno połączenie z lockiem; narzędzia (MCP, golden) idą przez gateway.
- `embedded://.run/pgdata` — prawdziwy Postgres uruchamiany jako proces potomny aplikacji z paczki pip (`pgembed`, `pgserver` lub `pg0-embedded`); pełna współbieżność. **Ten tryb jest zaimplementowany, ale nie był testowany w tym środowisku.**
- `sqlite:///…` — zero zależności (CI, szybkie testy). Profil `pgserver` w compose — klasyczny serwer, gdy potrzebny.

**Jedna komórka jako osobne repozytorium Git?** Tak — nowy profil paczki zawiera jeden plik
implementacji i artefakty kontraktu, testów oraz typów. `make package` tworzy lokalne repo i `git bundle`;
`package.py assemble` składa paczki w aplikację, zapisując commity i hashe w `cellset.lock.json`.
To zachowuje atomową zmianę kodu i kontraktu wewnątrz paczki. Zmiany wielu paczek wymagają osobnego
commita zestawu zależności aplikacji i pełnych testów. Monorepo pozostaje prostszą opcją dla wspólnej ewolucji.

**Forge + SubLLM.** Adapter korzysta z prawdziwego providera i ograniczonego procesu Forge,
natywnego routingu/audytu SubLLM oraz testów Polycell w kontenerze bez sieci. Model proponuje cały
plik; kontroler sprawdza go względem niezmienionego kontraktu i zaufanych przypadków.
[Instrukcja i format paczek](docs/FORGE-HARNESS.md) · [wyniki rzeczywistego pilota](docs/FORGE-RESULTS.md).

**Jak uniknąć luk w funkcjonalności przy wymianie kodu?** `make check` (standard `wellmanifest/polycell`, kody PC001–PC009) wykrywa:
**GAP** (kontrakt bez implementacji), **ORPHAN** (kod bez kontraktu), **STALE** (komórka napisana do starej wersji kontraktu),
I/O w czystej komórce, nieaktualne generaty, błędne procesy. Gateway dodatkowo waliduje wejście i wyjście w runtime
(fail-closed) i odrzuca hosta z innym hashem kontraktu. Przypadki **golden** nagrane z produkcji muszą przejść, zanim stary kod zostanie usunięty.

**Szybkość, nie tylko łatwość zmian.** Właściciel komórki to pole w kontrakcie — gorącą ścieżkę przenosisz do Rusta
bez zmiany URN i bez dotykania klientów (prompt nr 9 w `docs/PROMPTS.md`). Komórki Python i TS przeładowują się po podmianie pliku bez restartu.

## Struktura

```
contracts/cells/*.cell.yaml        SSOT komórek (schemat: standard/polycell-cell.schema.v1.json)
contracts/processes/*.process.yaml procesy poa.process/v1
cells/{python,ts,rust}/            logika - po jednym pliku
proto/polycell/v1/cellhost.proto   niezmienny transport
hosts/{python,ts,rust}/            generyczne hosty: HTTP + gRPC + stdio
gateway/                           REST, UI, NL, MCP, CLI, POA, DB, logi, parity
gen/                               wszystko generowane (nie edytować)
db/pglite/                         Postgres w WASM jako proces aplikacyjny
twin/                              CDP (cdp.ts), runner TestTOON, scenariusze UI
standard/                          conformance.py + schema - propozycja wellmanifest/polycell
tools/polycell/                    gen, prompt, new_cell, adopt (inventory/wrap/golden/switch/prune)
adoption/forge-candidates.md       analiza Twojego map.toon.yaml (forge)
docs/SPEC.md, docs/PROMPTS.md      specyfikacja i prompty do istniejących projektów
AGENTS.md                          reguły dla agentów AI
```

## Integracja z ekosystemem wellmanifest / semcod / autogrammar

- `gen/registry.json` = `wellmanifest.api-registry/v1` (nl-api-llm): `nlIntents` PL/EN, `menuBinding`; UI buduje menu i paletę Ctrl+K z rejestru.
- Procesy = `poa.process/v1`, wynik = `poa.receipt/v1` z `plan_hash` (wellmanifest/poa).
- NL: deterministyczna szybka ścieżka + opcjonalny fallback LLM (`LLM_BASE_URL`), który może wybrać **tylko** endpoint z rejestru (fail-closed, jak w nl-dsl-llm).
- `standard/conformance.py --json` zwraca `findings[{code, severity, message}]` jak `wellman` ConformanceRunner; docelowo `wellman adopt --standard wellmanifest/polycell`.
- TestQL: `tests/generated/smoke.testql.toon.yaml` jest w ścisłym formacie 3-kolumnowym (`testql run <plik> --url …`); pliki per komórka używają rozszerzenia o kolumnę `body`, obsługiwanego przez wbudowany runner. testwins ma backend TestQL, więc może uruchamiać te same scenariusze — **nie testowałem tego z testwins**.

## Ograniczenia (uczciwie)

- WebSocket nie jest zaimplementowany jako transport (dodaje się go jako kolejny adapter gatewaya — ta sama koperta).
- Mini-walidator JSON Schema w gatewayu obsługuje podzbiór (type/required/additionalProperties/items/$ref) — wystarczający dla generowanych schematów.
- Repozytorium `heyasa/forge` nie było dla mnie dostępne (wymaga logowania), więc nie porównywałem się z nim bezpośrednio; analizę `forge` zrobiłem na Twoim pliku `map.toon.yaml`.
- `wellmanifest/polycell` jest propozycją standardu, nie formalnie zatwierdzonym standardem.
- Równoległe wersje `:v1` i `:v2` tej samej nazwy wymagają jeszcze zmiany generatora: ścieżki komórek i typy są obecnie wyprowadzane z `name`, więc kolidują. Samo dopisanie nowego URN nie wystarcza.
- Kontrola czystości w `make check` wykrywa wybrane wzorce I/O wyrażeniami regularnymi; nie jest pełną analizą efektów ani sandboxem.
