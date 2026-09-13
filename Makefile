.PHONY: build ensure-python-version install-hooks setup dev check check-python check-platform verify-push deps-bootstrap deps-lock deps-check run serve tls-selfsigned test lint format format-check typecheck docstrings layers repo-hygiene repo-hygiene-staged config-sync config-sync-check config-ref config-ref-check bench profile security ios-build swift-test swift-run showcase-dev showcase-check visual-capture-baseline visual-capture-candidate visual-diff visual-regression preflight-swift preflight-swift-test preflight-ios

VENV ?= .venv
PYTHON_BOOTSTRAP ?= python3.11
PYTHON ?= $(VENV)/bin/python
LOCK_VENV ?= .venv-lock
LOCK_PYTHON ?= $(LOCK_VENV)/bin/python
PYTHON_VERSION ?= 3.11.15
PYTHON_SERIES ?= 3.11
SWIFT_PACKAGE_PATH ?= swift-ui
SWIFT_CACHE_DIR ?= .local/swiftpm
SWIFT ?= swift
SWIFT_APP_ARGS ?=
IOS_PROJECT_PATH ?= ios/MacHealthCheckupMobile/MacHealthCheckupMobile.xcodeproj
IOS_SCHEME ?= MacHealthCheckupMobile
IOS_SHARED_SCHEME_PATH ?= $(IOS_PROJECT_PATH)/xcshareddata/xcschemes/$(IOS_SCHEME).xcscheme
VISUAL_BASELINE_DIR ?= .local/visual-regression/baseline
VISUAL_CANDIDATE_DIR ?= .local/visual-regression/candidate
VISUAL_DIFF_DIR ?= .local/visual-regression/diff
CONFIG_SOURCE ?= config/config.json
PACKAGED_CONFIG ?= mac_health_checkup/resources/default_config.json
PACKAGE_SOURCE ?= .
DIST_DIR ?= dist
SHOWCASE_DIR ?= showcase

SWIFT_COMMON_FLAGS = --package-path $(SWIFT_PACKAGE_PATH) --manifest-cache local --disable-sandbox \
	--scratch-path $(SWIFT_CACHE_DIR)/scratch --cache-path $(SWIFT_CACHE_DIR)/cache \
	--config-path $(SWIFT_CACHE_DIR)/config --security-path $(SWIFT_CACHE_DIR)/security
SWIFT_ENV = CLANG_MODULE_CACHE_PATH=$(PWD)/$(SWIFT_CACHE_DIR)/clang-module-cache

build: config-sync-check
	$(PYTHON) -m build --no-isolation --outdir "$(DIST_DIR)" "$(PACKAGE_SOURCE)"

install-hooks:
	git config core.hooksPath .githooks

ensure-python-version:
	@actual="$$( $(PYTHON_BOOTSTRAP) -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))' )"; \
	actual_series="$$( $(PYTHON_BOOTSTRAP) -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))' )"; \
	if [ "$$actual_series" != "$(PYTHON_SERIES)" ]; then \
		echo "ERROR: Python $(PYTHON_SERIES).x is required, found $$actual via $(PYTHON_BOOTSTRAP)."; \
		echo "Preferred pinned runtime in .python-version: $(PYTHON_VERSION)."; \
		exit 1; \
	fi

setup: ensure-python-version
	$(PYTHON_BOOTSTRAP) -m venv $(VENV)
	$(PYTHON) -m pip install --disable-pip-version-check --require-hashes -r requirements-dev.txt
	$(MAKE) install-hooks

dev:
	./start

check-python: deps-check repo-hygiene lint format-check typecheck docstrings layers config-sync-check config-ref-check test security

check-platform: bench swift-test ios-build

check: check-python check-platform

verify-push: deps-check repo-hygiene lint format-check typecheck config-sync-check test security

deps-bootstrap: ensure-python-version
	@if [ -x "$(LOCK_PYTHON)" ] && [ "$$($(LOCK_PYTHON) -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')" != "$(PYTHON_SERIES)" ]; then rm -rf "$(LOCK_VENV)"; fi
	@if [ ! -x "$(LOCK_PYTHON)" ]; then $(PYTHON_BOOTSTRAP) -m venv "$(LOCK_VENV)"; fi
	$(LOCK_PYTHON) -m pip install --disable-pip-version-check --require-hashes -r requirements-dev.txt

deps-lock: deps-bootstrap
	CUSTOM_COMPILE_COMMAND="make deps-lock" $(LOCK_PYTHON) -m piptools compile --no-header --generate-hashes --resolver=backtracking --strip-extras --allow-unsafe --output-file requirements.txt requirements.in
	CUSTOM_COMPILE_COMMAND="make deps-lock" $(LOCK_PYTHON) -m piptools compile --no-header --generate-hashes --resolver=backtracking --strip-extras --allow-unsafe --output-file requirements-dev.txt requirements-dev.in

deps-check: deps-bootstrap
	@set -eu; \
	tmp_dir="$$(mktemp -d)"; \
	trap 'rm -rf "$$tmp_dir"' 0 1 2 3 15; \
	cp requirements.txt requirements-dev.txt "$$tmp_dir/"; \
	CUSTOM_COMPILE_COMMAND="make deps-lock" $(LOCK_PYTHON) -m piptools compile --quiet --no-header --generate-hashes --resolver=backtracking --strip-extras --allow-unsafe --output-file "$$tmp_dir/requirements.txt" requirements.in; \
	CUSTOM_COMPILE_COMMAND="make deps-lock" $(LOCK_PYTHON) -m piptools compile --quiet --no-header --generate-hashes --resolver=backtracking --strip-extras --allow-unsafe --output-file "$$tmp_dir/requirements-dev.txt" requirements-dev.in; \
	status=0; \
	for lock_file in requirements.txt requirements-dev.txt; do \
		if ! cmp -s "$$lock_file" "$$tmp_dir/$$lock_file"; then \
			echo "ERROR: $$lock_file is out of date. Run 'make deps-lock'." >&2; \
			diff -u "$$lock_file" "$$tmp_dir/$$lock_file" || true; \
			status=1; \
		fi; \
	done; \
	exit "$$status"

preflight-swift:
	@command -v $(SWIFT) >/dev/null 2>&1 || { echo "ERROR: '$(SWIFT)' is required for Swift targets."; echo "Install Xcode and ensure the active developer directory is configured."; exit 2; }
	@xcode-select -p >/dev/null 2>&1 || { echo "ERROR: xcode-select has no active developer directory."; echo "Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"; exit 2; }
	@if [ ! -d "$(SWIFT_PACKAGE_PATH)" ]; then echo "ERROR: Swift package path not found: $(SWIFT_PACKAGE_PATH)"; exit 2; fi
	@if [ ! -f "$(SWIFT_PACKAGE_PATH)/Package.swift" ]; then echo "ERROR: Missing Swift package manifest: $(SWIFT_PACKAGE_PATH)/Package.swift"; exit 2; fi

preflight-swift-test: preflight-swift
	@xcodebuild -version >/dev/null 2>&1 || { \
		echo "ERROR: swift-test requires full Xcode with XCTest support, not Command Line Tools alone."; \
		echo "Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"; \
		exit 2; \
	}

preflight-ios:
	@command -v xcodebuild >/dev/null 2>&1 || { echo "ERROR: xcodebuild is required for ios-build."; echo "Install full Xcode and accept the license."; exit 2; }
	@xcodebuild -version >/dev/null 2>&1 || { echo "ERROR: ios-build requires full Xcode, not Command Line Tools alone."; echo "Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"; exit 2; }
	@xcode-select -p >/dev/null 2>&1 || { echo "ERROR: xcode-select has no active developer directory."; echo "Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"; exit 2; }
	@if [ ! -d "$(IOS_PROJECT_PATH)" ]; then echo "ERROR: iOS project path not found: $(IOS_PROJECT_PATH)"; exit 2; fi
	@if [ ! -f "$(IOS_PROJECT_PATH)/project.pbxproj" ]; then echo "ERROR: Missing Xcode project file: $(IOS_PROJECT_PATH)/project.pbxproj"; exit 2; fi
	@if [ ! -f "$(IOS_SHARED_SCHEME_PATH)" ]; then echo "ERROR: Missing shared Xcode scheme: $(IOS_SHARED_SCHEME_PATH)"; exit 2; fi
	@if ! xcodebuild -showsdks 2>/dev/null | grep -q "iphoneos"; then echo "ERROR: Active Xcode toolchain does not expose iphoneos SDK."; echo "Open Xcode once and complete component installation."; exit 2; fi

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
	$(PYTHON) -m coverage erase
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest -p pytest_cov --cov-config=pyproject.toml --cov-branch --cov=mac_health_checkup.app.backend --cov=mac_health_checkup.core.config --cov-report=term-missing --cov-report=xml

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy --explicit-package-bases mac_health_checkup tests tools benchmarks run.py run_mac_health_checkup.py run_mac_health_checkup_ui.py

docstrings:
	$(PYTHON) tools/check_docstring_headings.py

layers:
	$(PYTHON) tools/enforce_layer_dependencies.py --config tools/layer_rules.json --repo-root .

repo-hygiene:
	$(PYTHON) tools/audit_repo_hygiene.py --repo-root .

repo-hygiene-staged:
	$(PYTHON) tools/audit_repo_hygiene.py --repo-root . --staged-only

config-sync:
	cp "$(CONFIG_SOURCE)" "$(PACKAGED_CONFIG)"

config-sync-check:
	@cmp -s "$(CONFIG_SOURCE)" "$(PACKAGED_CONFIG)" || { \
		echo "ERROR: Packaged config is out of date. Run 'make config-sync'." >&2; \
		diff -u "$(PACKAGED_CONFIG)" "$(CONFIG_SOURCE)" || true; \
		exit 1; \
	}

config-ref:
	$(PYTHON) tools/generate_config_reference.py --config config/config.json --out docs/config_reference.md

config-ref-check:
	$(PYTHON) tools/generate_config_reference.py --config config/config.json --out docs/config_reference.md --check

bench:
	PYTHONPATH=. $(PYTHON) benchmarks/run.py

profile:
	PYTHONPATH=. $(PYTHON) benchmarks/profile.py

security:
	$(PYTHON) -m bandit -r mac_health_checkup
	$(PYTHON) -m pip_audit -r requirements-dev.txt -r requirements.txt
	$(PYTHON) -m detect_secrets scan --exclude-files '\.secrets\.baseline$$' | $(PYTHON) tools/check_detect_secrets_baseline.py --baseline .secrets.baseline

ios-build: preflight-ios
	mkdir -p .local/DerivedData .local/SourcePackages
	xcodebuild \
		-project $(IOS_PROJECT_PATH) \
		-scheme $(IOS_SCHEME) \
		-configuration Release \
		-sdk iphoneos \
		-destination "generic/platform=iOS" \
		-derivedDataPath .local/DerivedData \
		-clonedSourcePackagesDirPath .local/SourcePackages \
		CODE_SIGNING_ALLOWED=NO \
		build

swift-test: preflight-swift-test
	mkdir -p $(SWIFT_CACHE_DIR)/scratch $(SWIFT_CACHE_DIR)/cache $(SWIFT_CACHE_DIR)/config $(SWIFT_CACHE_DIR)/security $(SWIFT_CACHE_DIR)/clang-module-cache
	$(SWIFT_ENV) $(SWIFT) test $(SWIFT_COMMON_FLAGS)

swift-run: preflight-swift
	mkdir -p $(SWIFT_CACHE_DIR)/scratch $(SWIFT_CACHE_DIR)/cache $(SWIFT_CACHE_DIR)/config $(SWIFT_CACHE_DIR)/security $(SWIFT_CACHE_DIR)/clang-module-cache
	$(SWIFT_ENV) $(SWIFT) run $(SWIFT_COMMON_FLAGS) mac-health-checkup-ui -- $(SWIFT_APP_ARGS)

showcase-dev:
	cd $(SHOWCASE_DIR) && npm install --no-audit --no-fund && npm run dev

showcase-check:
	cd $(SHOWCASE_DIR) && npm ci --no-audit --no-fund && npm run lint && npm run build

visual-capture-baseline:
	PYTHONPATH=. $(PYTHON) tools/gui_visual_regression.py capture --output-dir $(VISUAL_BASELINE_DIR)

visual-capture-candidate:
	PYTHONPATH=. $(PYTHON) tools/gui_visual_regression.py capture --output-dir $(VISUAL_CANDIDATE_DIR)

visual-diff:
	PYTHONPATH=. $(PYTHON) tools/gui_visual_regression.py diff --before-dir $(VISUAL_BASELINE_DIR) --after-dir $(VISUAL_CANDIDATE_DIR) --diff-dir $(VISUAL_DIFF_DIR) --fail-on-change

visual-regression: visual-capture-candidate visual-diff
