# Makefile Targets

The Makefile is self-documenting. Run `make` or `make help` to list the available targets.

## Target Matrix

| Target | Purpose |
| --- | --- |
| `help` | Show the target list. |
| `init` | Create the virtual environment and install development dependencies. |
| `install` | Create `.venv` if needed and install the package with development extras. |
| `dev` | Prepare local development configuration and initialize the default database. |
| `configure-init` | Create or refresh `.env.example` and `.env`. |
| `configure-setup` | Ensure local configuration exists for development. |
| `configure-setup-ci` | Generate CI-oriented configuration in `.env.ci`. |
| `configure-status` | Report configuration health. |
| `configure-edit` | Open `.env` in `$EDITOR` after ensuring it exists. |
| `configure-update` | Update one documented config value. |
| `test` | Run the pytest suite. |
| `test-cov` | Run tests with coverage reports. |
| `lint` | Check code style with Ruff. |
| `lint-fix` | Apply safe Ruff lint fixes. |
| `format` | Format Python code with Ruff. |
| `type-check` | Run mypy over the package, tests, examples, and config script. |
| `quality` | Run linting, type checks, and tests. |
| `build` | Build source and wheel distributions. |
| `clean` | Remove generated caches and build artifacts. |
| `clean-venv` | Remove the local virtual environment. |
| `db-init` | Initialize the SQLite database selected by `DB`. |
| `demo` | Run the basic ingest and recall demo. |
| `zip` | Create a project zip one directory above the repo. |
| `docker-build` | Build a container image with Docker or Podman. |
| `docker-run` | Run the local container image. |
| `docker-tag` | Tag `IMAGE_REF` as `REMOTE_IMAGE`. |
| `docker-push` | Push `REMOTE_IMAGE` to a registry. |
| `docker-build-push` | Build, tag, and push a container image. |
| `deploy-image` | Deploy `DEPLOY_IMAGE` with `DEPLOY_COMMAND`. |
| `deploy` | Build, push, and deploy the image. |

## Development

Create the virtual environment and install development tools:

```bash
make install
```

`make init` is kept as a compatibility alias for the same setup. `make dev` runs installation, configuration setup, and database initialization:

```bash
make dev
```

Useful variables:

| Variable | Default | Notes |
| --- | --- | --- |
| `VENV` | `.venv` | Virtual environment directory. |
| `HOST_PYTHON` | `python3` | Python used to create the virtual environment. |
| `PYTHON` | `.venv/bin/python` | Python used for package commands. |
| `PACKAGE_EXTRAS` | `dev` | Extras installed by `make install`. |

## Configuration

Configuration targets call `scripts/configure-env.sh`, which delegates to `scripts/config-manager`. The manifest lives at `config/config-manifest.json`, and `.env.example` documents the supported keys.

Create or refresh local config:

```bash
make configure-init
make configure-setup
```

Generate CI defaults in `.env.ci`:

```bash
make configure-setup-ci
```

Inspect or edit local config:

```bash
make configure-status
EDITOR=code make configure-edit
```

Update a documented key without overwriting other values:

```bash
make configure-update KEY=HINDSIGHT_DB VALUE=./.hindsight/dev.db
```

The current config keys are:

| Key | Default | Required | Sensitive |
| --- | --- | --- | --- |
| `HINDSIGHT_DB` | `./.hindsight/hindsight.db` | Yes | No |
| `HINDSIGHT_ENV` | `local` | No | No |

## Test And Quality

Run tests:

```bash
make test
```

Run tests with coverage:

```bash
make test-cov
```

Run linting, type checks, and tests together:

```bash
make quality
```

Individual quality commands are also available:

```bash
make lint
make lint-fix
make format
make type-check
```

`lint-fix` and `format` may edit files. `quality` only runs checking commands.

## Build And Cleanup

Build package distributions:

```bash
make build
```

Remove generated files:

```bash
make clean
make clean-venv
```

Create a project zip next to the repository directory:

```bash
make zip
```

## Local Database And Demo

Initialize the default SQLite database:

```bash
make db-init
```

Use a different database path:

```bash
make db-init DB=./.hindsight/experiment.db
```

Run the basic ingest and recall demo:

```bash
make demo
```

## Container Targets

Container targets use Docker when available, then Podman. Set `CONTAINER_ENGINE` to choose explicitly.

Build an image:

```bash
make docker-build
```

This project does not currently include a Dockerfile. `docker-build` requires `Dockerfile` by default, or a custom path:

```bash
make docker-build DOCKERFILE=containers/Dockerfile
```

Run an already-built local image:

```bash
make docker-run
```

Tag and push an image:

```bash
make docker-tag REMOTE_IMAGE=registry.example.com/hindsight-local-memory:latest
make docker-push REMOTE_IMAGE=registry.example.com/hindsight-local-memory:latest
make docker-build-push REMOTE_IMAGE=registry.example.com/hindsight-local-memory:latest
```

Useful variables:

| Variable | Default | Notes |
| --- | --- | --- |
| `IMAGE` | `hindsight-local-memory` | Local image name. |
| `IMAGE_TAG` | `latest` | Local image tag. |
| `IMAGE_REF` | `$(IMAGE):$(IMAGE_TAG)` | Local image reference. |
| `REMOTE_IMAGE` | Empty | Required for tag and push targets. |
| `DOCKERFILE` | `Dockerfile` | Dockerfile or Containerfile path. |
| `CONTAINER_ENGINE` | Auto-detected | `docker` or `podman`. |

## Deploy Targets

Deployment is intentionally command-driven because this repo has no deployment platform config yet. Provide a command through `DEPLOY_COMMAND`; `DEPLOY_IMAGE` is exported to that command.

Deploy an existing image:

```bash
make deploy-image \
  DEPLOY_IMAGE=registry.example.com/hindsight-local-memory:latest \
  DEPLOY_TOOL=gcloud \
  DEPLOY_COMMAND='gcloud run deploy hindsight-memory --image $$DEPLOY_IMAGE --region us-central1'
```

Build, push, and deploy:

```bash
make deploy \
  REMOTE_IMAGE=registry.example.com/hindsight-local-memory:latest \
  DEPLOY_TOOL=gcloud \
  DEPLOY_COMMAND='gcloud run deploy hindsight-memory --image $$DEPLOY_IMAGE --region us-central1'
```

`DEPLOY_TOOL` is optional. When set, the target validates that the tool exists before running `DEPLOY_COMMAND`.

## Invoked Scripts

| Script | Used By | Purpose |
| --- | --- | --- |
| `scripts/configure-env.sh` | `configure-*` targets | Makefile-friendly wrapper for config commands. |
| `scripts/config-manager` | `scripts/configure-env.sh` | Creates, updates, edits, and checks `.env` files from `config/config-manifest.json`. |
| `scripts/init_db.py` | `db-init`, `demo` | Initializes the SQLite schema. |
| `examples/basic_ingest.py` | `demo` | Demonstrates ingest and recall. |

## Required Tools

| Tool | Required For | Notes |
| --- | --- | --- |
| `python3` | `install`, config scripts | Used to create `.venv` and run config-manager before dependencies exist. |
| `.venv/bin/python` | Python targets | Created by `make install`. |
| `docker` or `podman` | Container targets | Auto-detected unless `CONTAINER_ENGINE` is set. |
| Deployment CLI such as `gcloud` | Deploy targets | Set `DEPLOY_TOOL=gcloud` to validate it explicitly. |

## Environment Variables

Make variables can be passed as environment variables or command-line overrides. Common examples:

```bash
make test PYTHON=/path/to/python
make db-init DB=./.hindsight/custom.db
make docker-build IMAGE_TAG=dev
```