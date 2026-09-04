export ALLTICK_TOKEN ?= $(shell cat .token 2>/dev/null)
PY := PYTHONPATH=packages/probe python3

catalog:      ; python3 packages/catalog/extract.py data/catalog.json
probe:        ; $(PY) packages/probe/rest.py
entitlements: ; $(PY) packages/probe/entitlements.py
suspension:   ; $(PY) packages/probe/suspension.py
stream:       ; $(PY) packages/probe/ws.py
gold:         ; $(PY) packages/probe/gold.py 240
site:         ; python3 packages/site/build.py
serve: site   ; python3 -m http.server 8000 --directory site

all: catalog probe entitlements suspension stream site

.PHONY: catalog probe entitlements suspension stream gold site serve all
