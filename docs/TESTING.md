# Weryfikacja polycell — 2026-11-13

Testy wykonano na Linux x86_64, Python 3.13.12, Node 22.23.1, Cargo 1.97.1,
Chrome 157 i Docker 29.1.3 / Compose 2.36.0. Python działa w `.venv` z `requirements.txt`.
Port TS w trybie natywnym: 18102 (8102 zajęty przez inną aplikację).
Docker: gateway 18090, CDP 19222, osobny wolumen PGlite.

## Wyniki

| Sprawdzenie | Wynik |
|---|---|
| `make install` z Node 22 | PASS: venv, pip, npm ci, cargo --locked |
| `make check` | PASS, 0 błędów, 0 ostrzeżeń |
| `make parity TS_HTTP_PORT=18102` | PASS: 11 przypadków × 3 protokoły = 33 wywołania |
| `make testql` | PASS: 5/5 scenariuszy wbudowanych, dodatkowo 12/12 kroków zewnętrznego TestQL |
| `make cdp` | PASS: 20 kroków, bez błędów konsoli i sieci |
| `make test` | PASS: 12 testów regresyjnych |
| `make integration` | PASS: checkout, zapis kroków, guard, walidacja, logi, MCP |
| `APP_PORT=18090 CHROME_PORT=19222 make docker-twin` | PASS: zbudowane obrazy, 5/5 TestQL i 20 kroków CDP bez błędów konsoli/sieci |
| Parytet wewnątrz gatewaya Docker | PASS: te same 33 wywołania, HTTP/gRPC/stdio |
| Integracja przez gateway Docker | PASS: trzy transporty, PGlite, guard, logi kontenerów i MCP |
| Deterministyczne `make gen` | PASS: ponowne generowanie nie zmienia bajtów |
| Schematy czterech kontraktów | PASS: `standard/polycell-cell.schema.v1.json` |
| Oficjalny schemat rejestru API | PASS: lokalny checkout `wellmanifest/nl-api-llm`, commit `26efebda515a5a977d0d0bcaadc070bcc432efae` |
| GAP / ORPHAN / STALE / I/O | PASS: celowe uszkodzenia kopii w katalogu tymczasowym są wykrywane |
| `prune shipping.cost` | Wykrywa 3 odwołania; oryginalny przykład legacy pozostaje na miejscu |

11 przypadków jest rozdzielonych między komórki Python, TS i Rust. Nie są to 11 identycznych
algorytmów zaimplementowanych osobno w każdym z trzech języków.

Integracja sprawdza wynik checkout (221.4), trzy wpisy `wm_invocations` o wspólnym `trace_id`,
zatrzymanie po pierwszym kroku dla błędnego klienta oraz rzeczywistą odpowiedź MCP z wyceną 12.3.
Negatywne testy celowo zostawiają nieudane wywołania w dzienniku — `make diag` może je pokazywać.

## Poprawki wynikające z weryfikacji

- Walidacja nie pomija już wartości `null`; wymagane pola i zagnieżdżone typy są sprawdzane.
- Odpowiedź hosta bez zgodnego hasha kontraktu jest odrzucana.
- Błędny JSON, nieobiektowe żądanie, brak URN i nieznany proces zwracają JSON z błędem HTTP 400.
- Nieobsługiwany transport zwraca wynik błędu zamiast wyjątku przerywającego żądanie.
- Instalacja używa venv, wspólnych wersji bibliotek Python i `npm ci`; `make stop` nie stosuje globalnego `pkill`.
- TestQL jest uruchamiany przez `testql run`; Chrome używa osobnego profilu w `.run`.
- Gateway Docker zawiera również Node, host TS i binarny host Rust, dzięki czemu stdio działa dla wszystkich komórek.
- Compose Bake przekazuje obrazy hostów jako konteksty budowania; Docker wymaga Compose z Bake i buildx.
- `docker-twin` oczekuje na zdrowy gateway i uruchamia TestQL oraz CDP kolejno, sprawdzając oba kody wyjścia.
- Dodano GitHub Actions dla instalacji, conformance, parytetu, TestQL, regresji, integracji i CDP.

## Odtworzenie

```bash
nvm use
make install
make check
make twin TS_HTTP_PORT=18102
make test integration TS_HTTP_PORT=18102
make bench N=300 TS_HTTP_PORT=18102

APP_PORT=18090 CHROME_PORT=19222 make docker-twin
docker compose exec -T gateway python -m gateway.cli parity
APP_URL=http://127.0.0.1:18090 .venv/bin/python tests/integration.py
```

Artefakty CDP zapisują się w `artifacts/twin/`, a logi natywne w `.run/logs/`.
Są lokalne i ignorowane przez Git; workflow CI udostępnia je jako artefakt `digital-twin`.
Zatrzymanie: `make stop` oraz `make down` (wolumen DB pozostaje).

## Granice weryfikacji i znane ograniczenia

- `embedded://`, integracja z testwins i fallback do zewnętrznego LLM nie zostały uruchomione.
- Nie powtarzano całej migracji wrap → golden → regeneracja → switch → fizyczne usunięcie legacy.
  Przetestowano istniejące golden cases i kontrolę odwołań w prune.
- Równoległe URN-y `:v1` / `:v2` o tej samej nazwie kolidują w generatorze ścieżek i typów;
  opis wersjonowania jest celem standardu, a nie gotową obsługą wielu wersji.
- Kontrola I/O jest heurystyką opartą na regexach. Mini-walidator obsługuje podzbiór JSON Schema.
- WebSocket nie jest transportem komórek. WebSocket w testach służy wyłącznie połączeniu z CDP.
- Historyczne opóźnienia 0.04–0.6 ms nie są gwarancją. Aktualny benchmark jest w README;
  obejmuje round-trip i wykonanie komórki na współdzielonej, obciążonej maszynie.
