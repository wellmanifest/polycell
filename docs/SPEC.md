# wellmanifest/polycell v1 — specyfikacja (propozycja standardu)

Status: **draft / propozycja** do włączenia w katalog `wellmanifest/*` i uruchamiania przez `wellman`.
Słowa MUSI / POWINIEN / MOŻE mają znaczenie jak w RFC 2119.

## 1. Cel

Koszt zmiany kodu generowanego przez AI jest zdominowany przez refaktoryzację warstw komunikacji
(serwer + klient + typy + walidacja + DB + testy). Polycell usuwa tę klasę pracy:

1. **Interfejsy są generowane albo niezmienne.** Transport (`polycell.v1.CellHost`) nie zmienia się nigdy.
   Wszystko zależne od danych (proto, typy, JSON Schema, OpenAPI, MCP, SQL, rejestr, testy) jest generowane z kontraktu.
2. **Logika to wymienne pliki-komórki.** Jedna komórka = jeden plik = jedna czysta funkcja `run(input) -> output`.
   Zmiana zachowania = **regeneracja całego pliku**, nie łatanie.
3. **Adres zamiast lokalizacji.** Komórki są adresowane URN, procesy URI `poa://`; transport wybiera planner.

## 2. Artefakty

| Ścieżka | Rola | Edytowalne |
|---|---|---|
| `contracts/cells/*.cell.yaml` | kontrakt komórki (schema `wellmanifest.polycell.cell/v1`) | tak (SSOT) |
| `contracts/processes/*.process.yaml` | proces `poa.process/v1` z `capability_ref` = URN | tak |
| `contracts/polycell.lock.json` | hash interfejsu ↔ hash pliku komórki ↔ status | generowany |
| `cells/<lang>/<name>.<ext>` | implementacja (python/ts/rust) | regenerowany w całości |
| `proto/polycell/v1/cellhost.proto` | niezmienny kontrakt transportowy | nie |
| `gen/**` | proto typowane, typy, JSON Schema, OpenAPI, MCP, SQL, `registry.json` (`wellmanifest.api-registry/v1`) | nie |
| `tests/generated/**`, `tests/golden/**` | przypadki z przykładów i z produkcji (legacy) | generowane |

## 3. Wymagania

- **R1** Każdy kontrakt MUSI mieć URN `urn:wm:cell:<ns>:<name>:v<major>`; `name` MUSI odpowiadać URN.
- **R2** Zmiana niekompatybilna (usunięcie/zmiana typu pola) MUSI tworzyć nowy URN `:v<major+1>`; stary działa równolegle do wygaszenia.
- **R3** Plik komórki MUSI zaczynać się nagłówkiem `polycell: urn=<urn> contract=<hash12>`; hash = sha256(urn, owner, input, output, types, effects)[:12].
  Zmiana opisu/NL/menu NIE unieważnia komórki.
- **R4** Komórka z `effects: [pure]` NIE MOŻE wykonywać I/O ani importować transportu (sprawdzane statycznie, PC008).
- **R5** Gateway MUSI walidować wejście i wyjście względem wygenerowanej JSON Schema (fail-closed) i odrzucać odpowiedź
  hosta z innym hashem kontraktu niż w rejestrze.
- **R6** Każde wywołanie (dowolny protokół) MUSI być zapisane jako envelope w `wm_invocations`
  (`trace_id, urn, transport, lang, ok, input, output, error, duration_ms, contract`); komórki z `persist.table` dodatkowo w projekcji.
- **R7** Ten sam zestaw przypadków MUSI dawać identyczne wyniki na każdym obsługiwanym transporcie (parity).
- **R8** Procesy MUSZĄ zawierać wyłącznie URN-y capability, nigdy adresy transportowe; plan zawiera `plan_hash`, wynik `poa.receipt/v1`.
- **R9** Kod legacy zastępowany przez komórkę MUSI być wymieniony w `replaces` i usunięty dopiero po zielonym parity na przypadkach golden.

Generator wymaga, aby kontrakt deklarował w `types` wszystkie używane typy złożone,
także te zagnieżdżone. Wspólne nazwy typów muszą mieć identyczne definicje. Przed
zapisem artefaktów sprawdzane są również kolizje nazw komórek, plików i typów
wejścia/wyjścia. Obecne ograniczenie współistnienia majorów opisuje
[instrukcja harnessu](FORGE-HARNESS.md#składanie-aplikacji-i-wersjonowanie).

## 4. Kody zgodności (`standard/conformance.py`)

| Kod | Znaczenie |
|---|---|
| PC001 | niepoprawny kontrakt (schema, URN, owner, efekty, nieznany typ) |
| PC002 | duplikat URN lub sprzeczne definicje typu o tej samej nazwie |
| PC003 | **luka** (brak implementacji), brak nagłówka, **STALE** (komórka do zregenerowania), STUB |
| PC004 | **sierota**: plik komórki bez kontraktu (martwy kod) |
| PC005 | brak przykładów = brak testów kontraktu (warning) |
| PC006 | proces: nieznany URN, zła kolejność zależności, adres transportowy w definicji, mutujący `query` |
| PC007 | artefakty generowane nieaktualne / brak `registry.json` |
| PC008 | I/O w komórce `pure` |
| PC009 | zastąpiony kod legacy wciąż obecny (warning) |

## 5. Transporty

`polycell.v1.CellHost/Invoke` (gRPC/protobuf), `POST /v1/invoke` (HTTP/JSON), JSON-lines na stdio (CLI, sidecar, MCP).
Payload w envelope jest JSON-em zgodnym z JSON Schema; klienci wymagający ścisłego typowania protobuf
korzystają z wygenerowanego `gen/proto/shop/cells.proto` (serwis `ShopCells`). Gateway dodaje REST per komórka,
MCP (`tools/list`, `tools/call`), CLI i NL→API (rejestr `wellmanifest.api-registry/v1`, zgodny z `nl-api-llm`).

## 6. Adopcja przez wellman (proponowane)

```bash
wellman adopt --standard wellmanifest/polycell --dry-run   # po dodaniu standardu do katalogu
python standard/conformance.py --root . --json            # dziś: samodzielnie, format findings jak ConformanceRunner
```
