# Prompty: jak użyć polycell w istniejących projektach

Prompty są pisane dla agenta z dostępem do repozytorium i terminala (Claude Code, Cursor, Aider itp.).
Zakładają, że katalog `polycell/` (lub jego zawartość) jest skopiowany do projektu, a `AGENTS.md` leży w korzeniu.
Fragmenty w `<…>` podmień.

---

## 1. Rozpoznanie projektu (bez zmian w kodzie)

```
Przeczytaj AGENTS.md i docs/SPEC.md. Nie zmieniaj kodu aplikacji.
1) Uruchom: make inventory SRC=<ścieżka do kodu>   (albo MAP=<plik map.toon.yaml z code2llm>)
2) Przeczytaj adoption/candidates.md.
3) Przygotuj adoption/PLAN.md:
   - 5 pierwszych komórek do adopcji (czyste funkcje, duplikaty, hotspoty) z uzasadnieniem,
   - dla każdej: proponowany URN urn:wm:cell:<ns>:<nazwa>:v1, owner (python|ts|rust) i dlaczego,
   - które istniejące endpointy/klienty z niej korzystają (grep),
   - ryzyka: efekty uboczne, stan globalny, I/O wymieszane z logiką.
Zakończ listą pytań, na które muszę odpowiedzieć przed krokiem 2.
```

## 2. Owinięcie istniejącej funkcji (strangler fig — interfejsy od razu, logika bez zmian)

```
Dla funkcji <plik.py>:<funkcja>:
1) make wrap FUNC=<plik.py>:<funkcja> CELL=<ns.nazwa> LEGACY_ROOT=<korzeń projektu>
2) Uzupełnij w contracts/cells/<ns.nazwa>.cell.yaml: dokładne typy output (zamiast json), summary,
   frazy nl (pl i en), menu, minimum 3 przykłady wzięte z istniejących testów projektu.
3) make gen && make check && make dev
4) Wywołaj komórkę przez REST, gRPC i MCP (make parity) — pokaż, że wyniki są identyczne jak w starym kodzie.
Nie zmieniaj starego kodu.
```

## 3. Nagranie zachowania produkcyjnego (golden)

```
Komórka <ns.nazwa> działa jako shim legacy. Przepnij <miejsce wywołania, np. endpoint /api/x albo job>
tak, by wołał gateway (POST /api/cells/<ns.nazwa>) zamiast funkcji bezpośrednio.
Po <okresie / zestawie scenariuszy testowych> uruchom make golden CELL=<ns.nazwa> i make gen.
Raport: ile unikalnych przypadków, jakie przypadki brzegowe są niepokryte (zaproponuj brakujące przykłady do kontraktu).
```

## 4. Regeneracja logiki (zamiast refaktoryzacji)

```
Zmień w kontrakcie <ns.nazwa> effects na [pure] i doprecyzuj typy. make gen.
Następnie wygeneruj od nowa CAŁY plik komórki na podstawie WYŁĄCZNIE wyniku `make prompt CELL=<ns.nazwa>`
(nie czytaj starego kodu — ma zostać odtworzone zachowanie z przykładów i golden, nie implementacja).
Pętla: zapisz plik -> make check -> make parity. Maksymalnie 3 iteracje; jeśli nadal czerwone, pokaż różnice
między wynikiem a golden i zaproponuj, czy to błąd legacy (do akceptacji) czy błąd nowej komórki.
Gdy zielone: make switch CELL=<ns.nazwa>.
```

## 5. Usuwanie starego kodu bez luk

```
Dla komórek z impl: cell i niepustym replaces:
1) make prune CELL=<ns.nazwa> LEGACY_ROOT=<korzeń> — pokaż wszystkie pozostałe odwołania.
2) Każde odwołanie zamień na wywołanie przez gateway/klienta wygenerowanego z gen/ (REST, gRPC lub MCP).
3) Uruchom testy projektu, make parity i make testql.
4) Dopiero gdy 0 odwołań: make prune CELL=<ns.nazwa> APPLY=1 i ponownie testy.
5) make check musi dać PASS bez ostrzeżeń PC009.
```

## 6. Nowa funkcjonalność (generowanie zamiast doklejania)

```
Potrzebuję: <opis biznesowy>.
1) Zaprojektuj kontrakt(y) w contracts/cells (make new-cell CELL=<ns.nazwa> OWNER=<lang>), wybierz owner:
   rust dla obliczeń na gorącej ścieżce, ts dla renderowania/UI-bliskiej logiki, python dla integracji/danych.
2) Jeśli funkcja łączy kilka kroków — zdefiniuj proces POA w contracts/processes (tylko URN-y).
3) make gen; wygeneruj każdą komórkę osobno z `make prompt CELL=...` (osobne konteksty, osobne pliki).
4) Dopisz scenariusz UI w twin/scenarios/<nazwa>.cdp.tql, jeśli funkcja jest widoczna w UI.
5) make check && make parity && make testql && make cdp. Nie modyfikuj hostów ani gatewaya.
```

## 7. Zmiana niekompatybilna (wersjonowanie bez łamania klientów)

```
Kontrakt <ns.nazwa>:v1 musi zmienić <pole>. Nie edytuj v1.
Utwórz contracts/cells/<ns.nazwa>.v2.cell.yaml z URN ...:v2 i nazwą <ns.nazwa_v2>, wygeneruj komórkę v2,
dodaj do procesu POA nową wersję capability. Pokaż w adoption/MIGRATION.md, którzy klienci (z wm_invocations,
GET /api/invocations) nadal używają v1, i zaproponuj datę wygaszenia.
```

## 8. Autodiagnostyka w sandboxie (digital twin)

```
Uruchom make twin (lub make docker-twin). Jeżeli cokolwiek jest czerwone:
- przeczytaj artifacts/twin/cdp-report.json (kroki, consoleErrors, networkErrors, domText) i *.failure.png,
- GET /api/logs?tail=200 i GET /api/invocations?limit=200 (szukaj ok=false, contract mismatch, input/output contract),
- ustal, czy błąd jest w kontrakcie, komórce, czy w scenariuszu.
Napraw wyłącznie przez regenerację komórki lub korektę kontraktu/scenariusza. Raport: przyczyna, dowód (trace_id), zmiana.
```

## 9. Przeniesienie gorącej ścieżki do Rust

```
Na podstawie make bench i GET /api/invocations (duration_ms) wskaż komórkę z największym łącznym czasem.
Zmień w jej kontrakcie owner na rust (URN bez zmian — interfejs się nie zmienia, zmienia się tylko hash).
make gen, wygeneruj cells/rust/<nazwa>.rs z make prompt, make dev, make parity, make bench — pokaż różnicę.
Usuń starą komórkę w poprzednim języku (make check wykaże ją jako ORPHAN).
```

## 10. Projekt bez Pythona/TS/Rusta (np. Go, Java, PHP)

```
Projekt jest w <język>. Nie przepisuj go. Wygeneruj klienta gRPC z proto/polycell/v1/cellhost.proto
(lub użyj REST z gen/openapi.json) i zastąp wywołania funkcji <lista> wywołaniami gateway.
Opcjonalnie: zaproponuj host komórek w <język> implementujący CellHost (HTTP /v1/invoke + gRPC + --stdio),
tak by przeszedł make parity — wtedy komórki mogą być generowane także w <język>.
```
