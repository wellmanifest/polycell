# Dokumentacja `wellmanifest/polycell`

Indeks dokumentacji repozytorium `wellmanifest/polycell` zgodny ze standardem `wellmanifest/docs`.

## Wprowadzenie i specyfikacja

- [README główny projektu](../README.md) — architektura, szybki start, transporty (HTTP, gRPC, stdio) i integracja ekosystemu
- [Specyfikacja `wellmanifest/polycell` v1](SPEC.md) — kontrakty komórek, procesy POA, kody zgodności `PC001`–`PC009` i granice standardu
- [Reguły dla agentów AI w polycell](../project/polycell-agent-rules.md) — zasady pracy z kontraktami komórek i regeneracją
- [Prompty adopcyjne](PROMPTS.md) — wzorce użycia `polycell` w istniejących projektach

## Weryfikacja i pilotaż Forge + SubLLM

- [Weryfikacja polycell — 2026-11-13](TESTING.md) — wyniki testów hosta, Docker / Digital Twin, parytetu i odtwarzania
- [Forge + SubLLM + Polycell: paczki z jednym plikiem implementacji](FORGE-HARNESS.md) — instrukcja i format paczek kwalifikacyjnych
- [Wynik pilota Forge + SubLLM + Polycell — 2026-11-13](FORGE-RESULTS.md) — obserwacje, granice i metryki pilotażu
- [Kandydaci na komórki polycell (Forge)](../adoption/forge-candidates.md) — analiza `map.toon.yaml`
