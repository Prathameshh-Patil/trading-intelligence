export ALLTICK_TOKEN ?= $(shell cat .token 2>/dev/null)
PY := PYTHONPATH=packages/probe python3

catalog:      ; python3 packages/catalog/extract.py data/catalog.json
probe:        ; $(PY) packages/probe/rest.py
entitlements: ; $(PY) packages/probe/entitlements.py
suspension:   ; $(PY) packages/probe/suspension.py
stream:       ; $(PY) packages/probe/ws.py
gold:         ; $(PY) packages/probe/gold.py 240
klines:       ; $(PY) packages/probe/pull_klines.py --interval 5m --since 2022-06-01
klines-1m:    ; $(PY) packages/probe/pull_klines.py --interval 1m --since 2022-06-01
edge:         ; ../services/signal-data/.venv/bin/python packages/edge/ohlcv_edge.py

all: catalog probe entitlements suspension stream gold

.PHONY: catalog probe entitlements suspension stream gold klines klines-1m edge all
