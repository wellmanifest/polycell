# polycell - kontrakty -> generowane interfejsy, logika jako wymienne pliki-komórki (Python | TS | Rust)
SHELL := /bin/bash
PY    ?= $(if $(wildcard .venv/bin/python),$(CURDIR)/.venv/bin/python,python3)
NODE  ?= node --experimental-strip-types --no-warnings
RUN   := .run
DB_URL ?= postgresql://postgres:postgres@127.0.0.1:55432/postgres?sslmode=disable
CHROME_PORT ?= 9222
CHROME_STARTUP_TIMEOUT ?= 60
CDP_URL ?= http://127.0.0.1:$(CHROME_PORT)
APP_URL ?= http://127.0.0.1:8080
CELL ?=
FORGE_ROOT ?= $(abspath ../../heyasa/forge)
PACKAGE ?=
OUT ?=
TS_HTTP_PORT ?= 8102
export HOST_TS_HTTP ?= http://127.0.0.1:$(TS_HTTP_PORT)
export COMPOSE_BAKE ?= true
.DEFAULT_GOAL := help

help: ## lista komend
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- kontrakty i generowanie
install: ## zależności lokalne (pip, npm, cargo)
	node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 18)) { console.error("Node >=22.18 required; run nvm use"); process.exit(1); }'
	python3 -m venv .venv
	.venv/bin/python -m pip install -q -r requirements.txt
	cd hosts/ts && npm ci --silent
	cd db/pglite && npm ci --silent
	cd hosts/rust && cargo build --release --locked -q

gen: ## kontrakty YAML -> proto/registry/SQL/typy/JSON Schema/OpenAPI/MCP/testy + szkielety komórek
	$(PY) tools/polycell/gen.py
	$(PY) -m grpc_tools.protoc -Iproto --python_out=gen/python --grpc_python_out=gen/python proto/polycell/v1/cellhost.proto

check: gen ## zgodność ze standardem (wellmanifest.polycell): luki, sieroty, nieaktualne komórki
	$(PY) standard/conformance.py --root .

stale: ## lista komórek do (re)generacji po zmianie kontraktu
	@$(PY) -c "import json;l=json.load(open('contracts/polycell.lock.json'))['cells'];[print(u,v['cell']) for u,v in l.items() if v['status']!='ok']" || true

prompt: ## prompt dla LLM do wygenerowania jednej komórki: make prompt CELL=pricing.quote
	@$(PY) tools/polycell/prompt.py $(CELL)

new-cell: ## szkielet nowego kontraktu: make new-cell CELL=invoice.pdf OWNER=python
	$(PY) tools/polycell/new_cell.py $(CELL) $(or $(OWNER),python)

# ---------------------------------------------------------------- uruchomienie natywne (bez Dockera)
dev: gen stop ## uruchom db(PGlite) + 3 hosty + gateway lokalnie, logi w .run/logs
	@mkdir -p $(RUN)/logs
	(cd db/pglite && PGLITE_DATA=../../$(RUN)/pglite PGPORT=55432 PGHOST=127.0.0.1 exec node server.mjs) > $(RUN)/logs/db-pglite.log 2>&1 < /dev/null & echo $$! > $(RUN)/db.pid
	$(PY) hosts/python/host.py > $(RUN)/logs/host-python.log 2>&1 < /dev/null & echo $$! > $(RUN)/py.pid
	HTTP_PORT=$(TS_HTTP_PORT) $(NODE) hosts/ts/host.ts > $(RUN)/logs/host-ts.log 2>&1 < /dev/null & echo $$! > $(RUN)/ts.pid
	cd hosts/rust && cargo build --release -q
	hosts/rust/target/release/host > $(RUN)/logs/host-rust.log 2>&1 < /dev/null & echo $$! > $(RUN)/rs.pid
	@sleep 3
	WM_DB='$(DB_URL)' $(PY) -m gateway.app > $(RUN)/logs/gateway.log 2>&1 < /dev/null & echo $$! > $(RUN)/gw.pid
	@curl --fail --silent --show-error --retry 20 --retry-connrefused --retry-delay 1 $(APP_URL)/health && echo && echo "UI: $(APP_URL)"

dev-sqlite: ## jak dev, ale DB=SQLite (zero zależności)
	$(MAKE) dev DB_URL=sqlite:///$(CURDIR)/$(RUN)/wm.db

stop: ## zatrzymaj procesy z make dev
	@for f in $(RUN)/*.pid; do [ -f $$f ] && kill $$(cat $$f) 2>/dev/null; rm -f $$f; done; true
	@sleep 1

# ---------------------------------------------------------------- testy i digital twin
parity: ## te same przypadki na HTTP, gRPC i stdio dla każdego języka
	$(PY) -m gateway.cli parity

test: ## regresje walidacji gatewaya i obsługi błędów HTTP
	$(PY) -m unittest discover -s tests -p 'test_*.py' -v

integration: ## komórki/procesy bieżącej aplikacji, DB, logi i MCP (wymaga dev)
	APP_URL=$(APP_URL) $(PY) -m tools.polycell.integration
	@if [ -f tests/integration.py ]; then APP_URL=$(APP_URL) $(PY) tests/integration.py; fi

testql: ## scenariusze TestTOON (tests/generated) - testql jeśli zainstalowany, inaczej wbudowany runner
	@if command -v testql >/dev/null; then testql run tests/generated/smoke.testql.toon.yaml --url $(APP_URL); fi
	$(PY) twin/testql_runner.py tests/generated/*.testql.toon.yaml --url $(APP_URL)

# Relative TMPDIR keeps Unix socket names short inside deep worktree paths.
chrome: ## lokalny Chrome headless (CHROME_PORT=9222, CHROME_STARTUP_TIMEOUT=60)
	@mkdir -p $(RUN)/logs .subactor/cache/chrome-tmp
	TMPDIR=.subactor/cache/chrome-tmp google-chrome --headless=new --no-sandbox --disable-gpu --user-data-dir=$(CURDIR)/$(RUN)/chrome --remote-debugging-port=$(CHROME_PORT) --remote-allow-origins=* about:blank > $(RUN)/logs/chrome.log 2>&1 < /dev/null & echo $$! > $(RUN)/chrome.pid
	@pid=$$(cat $(RUN)/chrome.pid); deadline=$$((SECONDS + $(CHROME_STARTUP_TIMEOUT))); \
	while :; do \
		if ! kill -0 $$pid 2>/dev/null; then \
			echo "Chrome exited before CDP became ready" >&2; \
			tail -n 20 $(RUN)/logs/chrome.log >&2; exit 1; \
		fi; \
		if curl --fail --silent --connect-timeout 1 --max-time 2 $(CDP_URL)/json/version > /dev/null; then break; fi; \
		if (( SECONDS >= deadline )); then \
			echo "Chrome CDP startup timed out after $(CHROME_STARTUP_TIMEOUT) seconds: $(CDP_URL)" >&2; \
			tail -n 20 $(RUN)/logs/chrome.log >&2; exit 1; \
		fi; \
		sleep 1; \
	done

cdp: ## scenariusze UI przez Chrome DevTools Protocol -> artifacts/twin (zrzuty, konsola, sieć)
	CDP_URL=$(CDP_URL) APP_URL=$(APP_URL) $(NODE) twin/cdp.ts

bench: ## porównanie protokołów (N wywołań)
	$(PY) tests/bench.py $(or $(N),300)

mcp-test: ## test serwera MCP po stdio
	APP_URL=$(APP_URL) $(PY) -m tools.polycell.integration --mcp-only

twin: dev chrome ## pełny sandbox natywnie: dev + chrome + parity + testql + cdp
	@sleep 2; $(MAKE) parity testql cdp

diag: ## autodiagnostyka: zdrowie hostów, ostatnie błędy, logi
	@curl -s $(APP_URL)/api/hosts; echo
	@curl -s "$(APP_URL)/api/invocations?limit=200" | $(PY) -c "import json,sys;r=json.load(sys.stdin);bad=[x for x in r if not x['ok']];print(f'{len(bad)}/{len(r)} failed');[print(' ',x['urn'],x['transport'],x['error']) for x in bad[:10]]"
	@tail -n 5 $(RUN)/logs/*.log

# ---------------------------------------------------------------- docker
up: gen ## docker compose: db + hosty + gateway
	docker compose up -d --build
docker-twin: gen ## docker compose z profilem twin (chrome CDP, dozzle, testql, cdp)
	docker compose --profile twin up -d --build --wait gateway chrome logs
	docker compose --profile twin build twin testql
	docker compose --profile twin run --rm testql
	docker compose --profile twin run --rm twin
logs: ## logi kontenerów
	docker compose logs -f --tail=100
down: ## zatrzymaj docker compose
	docker compose --profile twin --profile pgserver down

# ---------------------------------------------------------------- adopcja w istniejącym projekcie
forge-install: ## osobny provider Forge/SubLLM z przypiętych wheels (FORGE_ROOT=...)
	$(PY) tools/polycell/setup_forge.py --forge-root '$(FORGE_ROOT)'

package-image: ## wspólny sandbox/kompilator paczek (Docker + Forge run_bounded)
	docker buildx build --load --build-context forge_wheels='$(FORGE_ROOT)/wheels' -f docker/package.Dockerfile -t polycell/package-worker:dev .

package: gen ## paczka z jednym plikiem kodu: make package CELL=shipping.cost OUT=.run/shipping
	$(PY) tools/polycell/package.py export '$(CELL)' --out '$(OUT)' --git --bundle '$(OUT).bundle'

package-check: ## odbiór w sandboxie: make package-check PACKAGE=... ORACLE=...
	$(PY) tools/polycell/package.py qualify '$(PACKAGE)' --oracle '$(ORACLE)'

package-test: ## eksport, git bundle, klonowanie, trzy języki, odrzucenie błędu, assembly
	$(PY) tests/package_acceptance.py --out '$(OUT)' $(if $(CANDIDATE),--candidate '$(CANDIDATE)',)

composition-test: check stop ## pełny test aplikacji z jedną komórką (w repo demo; OUT=nowy-katalog)
	$(PY) tests/composition_acceptance.py --out '$(OUT)' --ts-http-port '$(TS_HTTP_PORT)'

inventory: ## kandydaci na komórki z istniejącego kodu: make inventory SRC=../projekt lub MAP=map.toon.yaml
	$(PY) tools/polycell/adopt.py inventory $(if $(MAP),--map $(MAP),) $(if $(SRC),--src $(SRC),)

wrap: ## owiń istniejącą funkcję jako komórkę legacy: make wrap FUNC=pkg/mod.py:fn CELL=ns.name
	$(PY) tools/polycell/adopt.py wrap --func $(FUNC) --name $(CELL)

golden: ## zrzut prawdziwych wywołań z DB do przypadków testowych (strangler fig): make golden CELL=x
	APP_URL=$(APP_URL) WM_DB='$(DB_URL)' $(PY) tools/polycell/adopt.py golden $(CELL)

switch: ## po regeneracji komórki: legacy -> cell (tylko przy zielonym parity): make switch CELL=x
	$(PY) tools/polycell/adopt.py switch $(CELL)

prune: ## usuń zastąpiony kod legacy (raport; APPLY=1 usuwa): make prune CELL=x LEGACY_ROOT=../app
	LEGACY_ROOT=$(LEGACY_ROOT) $(PY) tools/polycell/adopt.py prune $(CELL) $(if $(APPLY),--apply,)

clean: stop ## usuń wygenerowane i runtime
	rm -rf gen $(RUN) artifacts tests/generated

.PHONY: help install gen check stale prompt new-cell dev dev-sqlite stop parity test integration testql chrome cdp bench mcp-test twin diag up docker-twin logs down forge-install package-image package package-check package-test composition-test inventory wrap golden switch prune clean
