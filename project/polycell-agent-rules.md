# Reguły dla agentów AI (Claude Code, Cursor, Aider, Gemini…) w repozytorium polycell

Ten plik czytają agenci przed pracą. Skopiuj go (lub zlinkuj jako CLAUDE.md / GEMINI.md) do projektu, który adoptuje polycell.

## Zasady twarde
1. **Nie edytuj `gen/`, `tests/generated/`, `contracts/polycell.lock.json`.** Są generowane: `make gen`.
2. **Zmiana danych/interfejsu = zmiana kontraktu** w `contracts/cells/<name>.cell.yaml`, potem `make gen`.
   Zmiana niekompatybilna (usunięcie pola, zmiana typu) = **nowy plik kontraktu z URN `:v<N+1>`**, stary zostaje.
3. **Zmiana logiki = regeneracja CAŁEGO pliku komórki** (`cells/<lang>/<name>.<ext>`). Nie łataj fragmentów.
   Kontekst do generacji: `make prompt CELL=<name>` (tylko kontrakt + typy + przykłady + golden).
4. Komórka to czysta funkcja `run(input) -> output`. Zero I/O, sieci, DB, logowania — to robią hosty i gateway.
5. Nigdy nie modyfikuj hostów (`hosts/*`) ani `proto/polycell/v1/cellhost.proto`, żeby dodać funkcję. Jeśli wydaje się to konieczne — zatrzymaj się i opisz dlaczego.
6. Procesy (`contracts/processes`) zawierają tylko URN-y, nigdy adresy ani nazwy protokołów.

## Pętla pracy (zawsze w tej kolejności)
```
make gen            # po każdej zmianie kontraktu
make check          # luki / sieroty / STALE / I/O w czystych komórkach -> musi być PASS
make parity         # te same przypadki na http/grpc/stdio
make testql         # scenariusze API
make cdp            # (gdy zmienia się UI) scenariusze przeglądarki przez CDP, zrzuty w artifacts/twin
make diag           # przy błędach: zdrowie hostów, ostatnie nieudane wywołania, logi
```
Zadanie jest skończone dopiero, gdy `make check && make parity` przechodzą.

## Diagnostyka (digital twin)
- `GET /api/logs` — logi wszystkich kontenerów projektu (docker.sock) lub `.run/logs/*` w trybie natywnym.
- `GET /api/invocations`, `GET /api/table/<tabela>` — co faktycznie przeszło przez system (z danymi wejścia/wyjścia).
- `artifacts/twin/cdp-report.json` — kroki UI, błędy konsoli i sieci, tekst DOM; `*.failure.png` przy błędzie.
- Chrome z CDP: `http://127.0.0.1:9222` (możesz sterować nim samodzielnie).
