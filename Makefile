PY := .venv/bin/python

.PHONY: patch data audit changelog build check dev setup

patch: data audit changelog build

# One target per dataset script; build_entities/build_backlinks run last
# because they aggregate every other dataset's output.
data:
	$(PY) scripts/build_concepts.py
	$(PY) scripts/build_goods.py
	$(PY) scripts/build_advances.py
	$(PY) scripts/build_buildings.py
	$(PY) scripts/build_units.py
	$(PY) scripts/build_laws.py
	$(PY) scripts/build_reforms.py
	$(PY) scripts/build_estates.py
	$(PY) scripts/build_religions.py
	$(PY) scripts/build_cultures.py
	$(PY) scripts/build_pops.py
	$(PY) scripts/build_missions.py
	$(PY) scripts/build_locations.py
	$(PY) scripts/build_events.py
	$(PY) scripts/build_countries.py
	$(PY) scripts/build_simple.py
	$(PY) scripts/build_defines.py
	$(PY) scripts/build_map.py
	$(PY) scripts/build_planner.py
	$(PY) scripts/build_entities.py
	$(PY) scripts/build_backlinks.py

audit:
	$(PY) scripts/audit_coverage.py

changelog:
	$(PY) scripts/changelog.py

build:
	npx astro build

check:
	npx astro check || true

dev:
	npx astro dev

# One-time local setup: venv + toolkit deps + rakaly binary.
setup:
	python3 -m venv .venv
	.venv/bin/pip install -q colormath pillow luadata
	@echo "Now: copy tools/PyHelpersForPDXWikis/PyHelpersForPDXWikis/localsettings.py.example"
	@echo "to localsettings.py, point EU5DIR at this repo root and RAKALY_CLI at a"
	@echo "rakaly binary (github.com/rakaly/cli), CACHEPATH at ./.cache"
