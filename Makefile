.PHONY: build setup run serve tls-selfsigned test lint format typecheck docstrings config-ref config-ref-check bench profile swift-test swift-run visual-capture-baseline visual-capture-candidate visual-diff visual-regression

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
SWIFT_PACKAGE_PATH ?= swift-ui
SWIFT_CACHE_DIR ?= .local/swiftpm
SWIFT ?= swift
SWIFT_APP_ARGS ?=
VISUAL_BASELINE_DIR ?= .local/visual-regression/baseline
VISUAL_CANDIDATE_DIR ?= .local/visual-regression/candidate
VISUAL_DIFF_DIR ?= .local/visual-regression/diff

SWIFT_COMMON_FLAGS = --package-path $(SWIFT_PACKAGE_PATH) --manifest-cache local --disable-sandbox \
	--scratch-path $(SWIFT_CACHE_DIR)/scratch --cache-path $(SWIFT_CACHE_DIR)/cache \
	--config-path $(SWIFT_CACHE_DIR)/config --security-path $(SWIFT_CACHE_DIR)/security
SWIFT_ENV = CLANG_MODULE_CACHE_PATH=$(PWD)/$(SWIFT_CACHE_DIR)/clang-module-cache

build: setup

setup:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

run:
	$(PYTHON) -m mac_health_checkup

serve:
	$(PYTHON) -m mac_health_checkup --serve

tls-selfsigned:
	mkdir -p .local/tls
	openssl req -x509 -newkey rsa:2048 -nodes \
		-keyout .local/tls/agent-key.pem \
		-out .local/tls/agent-cert.pem \
		-days 3650 \
		-subj "/CN=mac-health-checkup-agent"

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -p pytest_cov --cov=mac_health_checkup --cov-report=term-missing --cov-report=xml

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m mypy mac_health_checkup tests

docstrings:
	$(PYTHON) tools/check_docstring_headings.py mac_health_checkup tests

config-ref:
	$(PYTHON) tools/generate_config_reference.py --config config/config.json --out docs/config_reference.md

config-ref-check:
	$(PYTHON) tools/generate_config_reference.py --config config/config.json --out docs/config_reference.md --check

bench:
	PYTHONPATH=. $(PYTHON) benchmarks/run.py

profile:
	PYTHONPATH=. $(PYTHON) benchmarks/profile.py

swift-test:
	mkdir -p $(SWIFT_CACHE_DIR)/scratch $(SWIFT_CACHE_DIR)/cache $(SWIFT_CACHE_DIR)/config $(SWIFT_CACHE_DIR)/security $(SWIFT_CACHE_DIR)/clang-module-cache
	$(SWIFT_ENV) $(SWIFT) test $(SWIFT_COMMON_FLAGS)

swift-run:
	mkdir -p $(SWIFT_CACHE_DIR)/scratch $(SWIFT_CACHE_DIR)/cache $(SWIFT_CACHE_DIR)/config $(SWIFT_CACHE_DIR)/security $(SWIFT_CACHE_DIR)/clang-module-cache
	$(SWIFT_ENV) $(SWIFT) run $(SWIFT_COMMON_FLAGS) mac-health-checkup-ui -- $(SWIFT_APP_ARGS)

visual-capture-baseline:
	PYTHONPATH=. $(PYTHON) tools/gui_visual_regression.py capture --output-dir $(VISUAL_BASELINE_DIR)

visual-capture-candidate:
	PYTHONPATH=. $(PYTHON) tools/gui_visual_regression.py capture --output-dir $(VISUAL_CANDIDATE_DIR)

visual-diff:
	PYTHONPATH=. $(PYTHON) tools/gui_visual_regression.py diff --before-dir $(VISUAL_BASELINE_DIR) --after-dir $(VISUAL_CANDIDATE_DIR) --diff-dir $(VISUAL_DIFF_DIR) --fail-on-change

visual-regression: visual-capture-candidate visual-diff
