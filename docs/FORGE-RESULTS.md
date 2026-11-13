# Wynik pilota Forge + SubLLM + Polycell — 2026-11-13

**Działa jako kontrolowany harness budowania i wymiany komórek. Nie jest jeszcze
niezawodnym, bezobsługowym generatorem aplikacji.** Najbardziej przewidywalne są
pakowanie, odtwarzanie i odbiór. Jakość oraz czas modelu nadal wymagają pomiaru
na właściwych zadaniach i jasnych kontraktach.

## Poprawki po pilocie

Kolejny przegląd odtworzył błędy na rzeczywistych paczkach i dodał 11 regresji
(łącznie **39 testów**):

- Przykład kontraktu można było zmienić w `cases.json`, a składanie pomijało taki
  przypadek jako już obecny w kontrakcie. Walidacja wymaga teraz wszystkich przykładów
  z niezmienionymi danymi oraz zgodnych URN/języka i unikalnych nazw przypadków.
- Schemat dostarczony przez paczkę mógł osłabiać kontrolę danych. Schemat i testy są
  teraz porównywane z kontraktem, a brak lokalnej definicji typu jest błędem.
- Walidator Draft 2020-12 wykrył niepoprawne `$id` zawierające fragment `#input` lub
  `#output`. Generator używa teraz końcówek `:input` i `:output`; artefakty odtworzono
  przez `make gen`. Starsze paczki wymagają ponownego eksportu i kwalifikacji.
- Nieudane składanie zostawiało częściową aplikację. CLI składa ją teraz w katalogu
  tymczasowym, sprawdza generację i zgodność, a dopiero potem publikuje wynik.
  Wykrywane są też konflikty współdzielonych typów.
- Globalne reguły Git mogły pominąć plik implementacji podczas tworzenia repozytorium.
  Snapshot dodaje teraz jawnie wszystkie pliki manifestu, niezależnie od globalnych wykluczeń.
- Kwalifikacja pracuje na prywatnych kopiach bez `.git`; hashe w raporcie opisują te
  kopie. Zmiana oryginału w trakcie testu nie przypisuje sukcesu innemu kodowi.

Po poprawkach natywne `check`, parytet 45 wywołań, TestQL 5/5, 39 regresji,
integracja checkout/PGlite/MCP i CDP przeszły. Zapisana odpowiedź Nvidia została
jawnie odtworzona z audytu na bazie nowych artefaktów: `new_inference_calls: 0`.
Test paczek w Dockerze przeszedł w **91,86 s**: cztery klony Git, kwalifikacja
Python/TS/Rust, wygenerowany kandydat 9/9, odrzucenie błędnej funkcji i transakcyjne
składanie aplikacji. Raport: `.run/fix-package-acceptance/report.json`.
Złożona aplikacja przeszła także check, parytet 45 wywołań, TestQL 5/5,
39 regresji, integrację i CDP 20 kroków bez błędów konsoli i sieci.

## Co rzeczywiście wykonano

- Reużyto wheels Forge 0.3.0 i SubLLM 1.14.0+forge.1 po weryfikacji SHA-256.
  Pliki robocze lokalnego `heyasa/forge` pozostały nietknięte.
- Wysłano rzeczywiste żądania do lokalnej Ollama przez `SubLLMProvider` Forge.
  Dziennik SQLite SubLLM zawiera próby, usage i odsyłacze do pełnych odpowiedzi.
- Wygenerowano całe implementacje Python dla `shipping.cost`. Nie poprawiano
  ciała funkcji ręcznie. Kontroler uzupełnił/poprawił nagłówki metadanych.
- Odpowiedzi modeli `nvidia-coding:9b` i `qwen3-coder:30b`, jawnie odtworzone
  z audytu po zmianie kontrolera nagłówka, przeszły po 9 przypadków w kontenerze
  bez sieci. Replay nie wywoływał ponownie modelu ani nie dopisywał zużycia tokenów.
- Utworzono i sklonowano cztery prawdziwe `git bundle`: customer.validate (Python),
  notify.render (TS), pricing.quote (Rust), shipping.cost (wygenerowany Python).
  W każdym repo jest dokładnie jeden śledzony plik implementacji.
- Wszystkie paczki przeszły kwalifikację z użyciem `Forge.run_bounded`. Celowo
  błędna funkcja zwracająca 0 została odrzucona. Odrzucono także podmieniony oracle,
  niespójny hash, symlink, dodatkowy helper i replay z innego kontekstu.
- Z tych czterech repozytoriów złożono nową aplikację i proces checkout.
  `make check` PASS; parytet **15 przypadków × 3 protokoły = 45 wywołań** PASS;
  TestQL 5/5 PASS; integracja checkout/PGlite/MCP/logi PASS; CDP 20 kroków PASS,
  bez błędów konsoli i sieci. To test złożonej aplikacji z wygenerowaną komórką,
  nie tylko pierwotnego demo Polycell.
- Szybkie testy regresyjne: **28 PASS**. Obejmują kontrakty paczki, Git, oracle,
  adapter Forge, nagłówek kontrolera oraz wcześniejsze regresje gatewaya.

## Pomiar przykładowego cyklu

| Etap | Obserwacja |
|---|---:|
| Właściwa odpowiedź Qwen, użyta później przez replay | 16,38 s; 1444 tokeny wejścia, 286 wyjścia |
| Właściwa odpowiedź Nvidia, użyta później przez replay | 234,27 s; 1402 tokeny wejścia, 267 wyjścia |
| Kwalifikacja wygenerowanego Pythona po replay | 0,52–1,10 s wewnątrz workera |
| Kwalifikacja TS | 0,66–0,9 s wewnątrz workera |
| Kwalifikacja Rust po poprawie ścieżki cache Cargo | 27–34 s, w tym kompilacja |
| Końcowy test czterech paczek, Git, odrzucenia błędu i assembly | 81,46 s łącznie, bez inferencji i pełnych testów aplikacji |
| Rozmiar jednego przenośnego `git bundle` | około 4,7–5,8 kB |
| Wspólny obraz kompilatora/runnera | około 1,76 GB; pierwszy build trwał kilka minut |

Czas workera nie obejmuje uruchamiania/obsługi kontenera przez Dockera.
To pomiary pojedynczego pilota na współdzielonej, obciążonej maszynie,
nie kontrolowany benchmark ani gwarancja wydajności. Katalog lokalnej Ollama
opisuje alias `qwen3-coder:30b` jako model 3,1B; samej etykiety nie traktujemy
jako dowodu rozmiaru czy tożsamości modelu.

## Co nie działało od razu i co z tego wynika

Pierwsza próba Nvidia przekroczyła budżet czasu (około 164 s w audycie).
`d1:3b` odpowiedział HTTP 400: model nie obsługuje chat. Qwen zwracał również
zmienione pola sterujące Forge, pustą implementację, brak importu i kod
używający atrybutów zamiast kluczy słownika. Te odpowiedzi nie zostały przyjęte.
Nie raportujemy samych udanych prób jako miary niezawodności modelu.

Stary kontrakt wysyłki miał opis „stary cennik” i za mało przykładów, aby
jednoznacznie wyznaczyć próg 5 kg. Dopisano regułę oraz cztery przypadki graniczne.
Interfejs, URN i działająca implementacja bazowa nie zmieniły się; artefakty
powstały ponownie przez `make gen`. To istotny warunek regeneracji bez kontekstu
całego repozytorium: reguła biznesowa musi istnieć w kontrakcie i przykładach.

Rust ujawnił problem uprawnień do cache utworzonego przy budowaniu obrazu jako root.
Naprawiono czytelność cache dla użytkownika 65534. Zachowanie oryginalnej ścieżki
Cargo ograniczyło ponowną kompilację z około 95 do około 34 s. Chrome otrzymał
oczekiwanie na gotowość CDP, eliminujące wyścig startu testów.

CI wykryło zależność klonowania bundle od lokalnego `init.defaultBranch`.
Bundle zawiera teraz także `HEAD`; regresja sprawdza klonowanie z domyślną
gałęzią `master`, `main` i dowolną własną nazwą.

## Zakres standardu i dalsze granice

Paczka ma kontrakt `wellmanifest.polycell.package/v1`; aplikacja zapisuje pełne
hashe manifestów i commity zależności w `cellset.lock.json`. Sam hash lub raport
nie jest podpisem, niezależną aprobatą ani dowodem poprawności na wszystkich danych.
Wywołania hostów, gateway, transport proto i biblioteki modeli pozostają wspólne.

Nie zmieniono ABI/evaluatora `Forge.Manager`, nie uruchomiono jego całego governance
ani nie opublikowano osobnych repozytoriów GitHub dla czterech paczek. To adapter
publicznych API providera i procesu, z niezależnym oracle Polycell. Brakuje jeszcze
obsługi dwóch majorów o tej samej nazwie, rozwiązywania zależności z centralnego
rejestru, podpisów paczek i szerszego benchmarku wielu rzeczywistych zmian.

Instrukcja odtworzenia: [FORGE-HARNESS.md](FORGE-HARNESS.md).
Lokalne artefakty: `.run/harness-acceptance/` (bundles, klony, aplikacja, raport),
`.run/harness-acceptance-final/` (końcowy pomiar pakowania i kwalifikacji),
`.run/forge-audit/` (prywatny audyt modeli), `artifacts/harness/` (kwalifikacje).
Nie są automatycznie publikowane razem z repozytorium.
