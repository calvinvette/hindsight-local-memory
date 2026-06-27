.DEFAULT_GOAL := help

VENV ?= .venv
HOST_PYTHON ?= python3
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy
BUILD ?= $(PYTHON) -m build
PACKAGE_EXTRAS ?= dev

DB ?= ./.hindsight/agent-mem.db
SYNC_BUNDLE ?= ./sync-bundle.jsonl
CONFIG_SCRIPT ?= ./scripts/configure-env.sh

IMAGE ?= hindsight-local-memory
IMAGE_TAG ?= latest
IMAGE_REF ?= $(IMAGE):$(IMAGE_TAG)
REMOTE_IMAGE ?=
DOCKERFILE ?= Dockerfile
CONTAINER_ENGINE ?= $(shell if command -v docker >/dev/null 2>&1; then echo docker; elif command -v podman >/dev/null 2>&1; then echo podman; else echo ""; fi)
DEPLOY_IMAGE ?= $(if $(REMOTE_IMAGE),$(REMOTE_IMAGE),$(IMAGE_REF))
DEPLOY_COMMAND ?=
DEPLOY_TOOL ?=

.PHONY: help init install dev configure-init configure-setup configure-setup-ci configure-status configure-edit configure-update test test-cov lint lint-fix format type-check quality build clean clean-venv db-init demo zip docker-build docker-run docker-tag docker-push docker-build-push deploy-image deploy vector-add-entry vector-regenerate graph-add-entry graph-regenerate

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

init: install ## Create the virtual environment and install development dependencies.

install: ## Create .venv if needed and install the package with development extras.
	@command -v "$(HOST_PYTHON)" >/dev/null 2>&1 || { echo "$(HOST_PYTHON) is required to create $(VENV)."; exit 127; }
	@test -x "$(PYTHON)" || "$(HOST_PYTHON)" -m venv "$(VENV)"
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[${PACKAGE_EXTRAS}]"

dev: install configure-setup db-init ## Prepare a local development environment.

configure-init: ## Create or refresh local configuration files.
	$(CONFIG_SCRIPT) init

configure-setup: ## Ensure local configuration exists for development.
	$(CONFIG_SCRIPT) setup

configure-setup-ci: ## Generate CI-oriented configuration in .env.ci.
	$(CONFIG_SCRIPT) setup-ci

configure-status: ## Report configuration health.
	$(CONFIG_SCRIPT) status

configure-edit: ## Open .env in $$EDITOR after ensuring it exists.
	$(CONFIG_SCRIPT) edit

configure-update: ## Update one config value, for example KEY=HINDSIGHT_DB VALUE=./.hindsight/dev.db.
	@test -n "$(KEY)" || { echo "Usage: make configure-update KEY=HINDSIGHT_DB VALUE=./.hindsight/dev.db"; exit 2; }
	@test -n "$(VALUE)" || { echo "Usage: make configure-update KEY=HINDSIGHT_DB VALUE=./.hindsight/dev.db"; exit 2; }
	$(CONFIG_SCRIPT) update -k "$(KEY)" -v "$(VALUE)"

test: install ## Run the test suite.
	$(PYTEST)

test-cov: install ## Run tests with coverage reports.
	$(PYTEST) --cov=hindsight_local --cov-report=term-missing --cov-report=xml

lint: install ## Check code style with Ruff.
	$(RUFF) check src tests examples scripts

lint-fix: install ## Apply safe Ruff lint fixes.
	$(RUFF) check --fix src tests examples scripts

format: install ## Format Python code with Ruff.
	$(RUFF) format src tests examples scripts

type-check: install ## Run mypy over package, tests, examples, and scripts.
	$(MYPY) --ignore-missing-imports src tests examples scripts/config-manager scripts/init_db.py

quality: lint type-check test ## Run linting, type checks, and tests.

build: install ## Build source and wheel distributions.
	$(BUILD)

clean: ## Remove generated caches and build artifacts.
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml htmlcov dist build *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

clean-venv: ## Remove the local virtual environment.
	rm -rf "$(VENV)"

db-init: install ## Initialize the local SQLite database at DB.
	$(PYTHON) scripts/init_db.py --db "$(DB)"

demo: install db-init ## Run the basic ingest and recall demo.
	$(PYTHON) examples/basic_ingest.py

vector-add-entry: install ## Ingest text and populate the vector fallback table.
	$(PYTHON) scripts/vector_add_entry.py --db "$(DB)" --text "$(TEXT)"

vector-regenerate: install ## Rebuild the vector fallback table from existing documents.
	$(PYTHON) scripts/vector_regenerate.py --db "$(DB)"

graph-add-entry: install ## Project a document or edge into FalkorDB.
	$(PYTHON) scripts/graph_add_entry.py --db "$(DB)" --kind "$(KIND)" $(if $(DOC_ID),--doc-id "$(DOC_ID)",) $(if $(TITLE),--title "$(TITLE)",) $(if $(METADATA),--metadata "$(METADATA)",) $(if $(SOURCE_ID),--source-id "$(SOURCE_ID)",) $(if $(RELATION),--relation "$(RELATION)",) $(if $(TARGET_ID),--target-id "$(TARGET_ID)",)

graph-regenerate: install ## Rebuild FalkorDB projections from existing SQLite records.
	$(PYTHON) scripts/graph_regenerate.py --db "$(DB)"

zip: ## Create a distributable project zip one directory above the repo.
	cd .. && zip -r hindsight-local-memory.zip hindsight-local-memory -x 'hindsight-local-memory/.venv/*' 'hindsight-local-memory/.hindsight/*' 'hindsight-local-memory/.pytest_cache/*' 'hindsight-local-memory/.ruff_cache/*' 'hindsight-local-memory/.mypy_cache/*' 'hindsight-local-memory/dist/*' 'hindsight-local-memory/build/*'

docker-build: ## Build a container image with docker or podman.
	@test -n "$(CONTAINER_ENGINE)" || { echo "docker or podman is required for docker-build."; exit 127; }
	@test -f "$(DOCKERFILE)" || { echo "No $(DOCKERFILE) found. Add one or set DOCKERFILE=path/to/Dockerfile."; exit 2; }
	$(CONTAINER_ENGINE) build -f "$(DOCKERFILE)" -t "$(IMAGE_REF)" .

docker-run: ## Run the local container image.
	@test -n "$(CONTAINER_ENGINE)" || { echo "docker or podman is required for docker-run."; exit 127; }
	$(CONTAINER_ENGINE) run --rm -it -v "$$(pwd)/.hindsight:/app/.hindsight" "$(IMAGE_REF)" agent-mem --help

docker-tag: ## Tag IMAGE_REF as REMOTE_IMAGE.
	@test -n "$(CONTAINER_ENGINE)" || { echo "docker or podman is required for docker-tag."; exit 127; }
	@test -n "$(REMOTE_IMAGE)" || { echo "Set REMOTE_IMAGE=registry.example.com/$(IMAGE):$(IMAGE_TAG)."; exit 2; }
	$(CONTAINER_ENGINE) tag "$(IMAGE_REF)" "$(REMOTE_IMAGE)"

docker-push: docker-tag ## Push REMOTE_IMAGE to a registry.
	$(CONTAINER_ENGINE) push "$(REMOTE_IMAGE)"

docker-build-push: docker-build docker-push ## Build, tag, and push a container image.

deploy-image: ## Deploy DEPLOY_IMAGE with DEPLOY_COMMAND.
	@test -n "$(DEPLOY_COMMAND)" || { echo "Set DEPLOY_COMMAND to the deployment command to run. DEPLOY_IMAGE is available in the environment."; exit 2; }
	@if [ -n "$(DEPLOY_TOOL)" ]; then command -v "$(DEPLOY_TOOL)" >/dev/null 2>&1 || { echo "$(DEPLOY_TOOL) is required for deploy-image."; exit 127; }; fi
	DEPLOY_IMAGE="$(DEPLOY_IMAGE)" $(DEPLOY_COMMAND)

deploy: docker-build-push deploy-image ## Build, push, and deploy the image.
