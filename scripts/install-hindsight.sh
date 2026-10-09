#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="${HINDSIGHT_REPO_OWNER:-calvinvette}"
REPO_NAME="${HINDSIGHT_REPO_NAME:-hindsight-local-memory}"
REPO_REF="${HINDSIGHT_REPO_REF:-main}"
PACKAGE_VERSION="${HINDSIGHT_PACKAGE_VERSION:-0.1.0}"
NPM_PACKAGE="${HINDSIGHT_NPM_PACKAGE:-hindsight-local-memory}"
PYTHON_WHL_URL_DEFAULT="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/v${PACKAGE_VERSION}/hindsight_local_memory-${PACKAGE_VERSION}-py3-none-any.whl"
PYTHON_WHL_URL="${HINDSIGHT_PYTHON_WHL_URL:-$PYTHON_WHL_URL_DEFAULT}"
PYTHON_GIT_FALLBACK="git+https://github.com/${REPO_OWNER}/${REPO_NAME}.git@${REPO_REF}"

prompt_value() {
  local var_name="$1"
  local question="$2"
  local default_value="$3"
  local current_value="${!var_name:-}"
  if [[ -n "$current_value" ]]; then
    printf '%s\n' "$current_value"
    return
  fi

  local input=""
  read -r -p "$question [$default_value]: " input
  if [[ -z "$input" ]]; then
    input="$default_value"
  fi
  printf '%s\n' "$input"
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command not found: $cmd" >&2
    exit 127
  fi
}

set_kv_file() {
  local file_path="$1"
  local key="$2"
  local value="$3"

  mkdir -p "$(dirname "$file_path")"
  local tmp_file
  tmp_file="$(mktemp)"

  if [[ -f "$file_path" ]]; then
    grep -v "^${key}=" "$file_path" > "$tmp_file" || true
  fi
  echo "${key}=${value}" >> "$tmp_file"
  mv "$tmp_file" "$file_path"
}

install_node_project() {
  require_command npm
  npm install --save "$NPM_PACKAGE"
}

install_node_global() {
  require_command npm
  npm install -g "$NPM_PACKAGE"
}

install_python_with_interpreter() {
  local python_bin="$1"
  "$python_bin" -m pip install --upgrade pip

  if ! "$python_bin" -m pip install "$PYTHON_WHL_URL"; then
    echo "Wheel installation failed. Falling back to source install from ${PYTHON_GIT_FALLBACK}."
    "$python_bin" -m pip install "$PYTHON_GIT_FALLBACK"
  fi
}

install_python_venv() {
  require_command python3
  local venv_path="${HINDSIGHT_VENV_PATH:-.venv}"
  if [[ ! -x "$venv_path/bin/python" ]]; then
    python3 -m venv "$venv_path"
  fi
  install_python_with_interpreter "$venv_path/bin/python"
}

install_python_global() {
  require_command python3
  install_python_with_interpreter python3
}

persist_memory_config() {
  local memory_mode="$1"
  local project_root="$2"

  if [[ "$memory_mode" == "global" ]]; then
    local global_home="${HINDSIGHT_GLOBAL_HOME:-$HOME/.hindsight}"
    local db_path="${global_home}/agent-mem.db"

    mkdir -p "$global_home"
    set_kv_file "${global_home}/env" "HINDSIGHT_MEMORY_SCOPE" "global"
    set_kv_file "${global_home}/env" "HINDSIGHT_DB" "$db_path"

    echo "Configured global memory at: $db_path"
    echo "Optional: add this to your shell profile -> source ${global_home}/env"
  else
    local db_path="${project_root}/.hindsight/agent-mem.db"

    mkdir -p "${project_root}/.hindsight"
    set_kv_file "${project_root}/.env" "HINDSIGHT_MEMORY_SCOPE" "project"
    set_kv_file "${project_root}/.env" "HINDSIGHT_PROJECT_ROOT" "$project_root"
    set_kv_file "${project_root}/.env" "HINDSIGHT_DB" "$db_path"

    echo "Configured project memory in ${project_root}/.env"
    echo "Project DB path: $db_path"
  fi
}

main() {
  cat <<'EOF'
Hindsight Local Memory installer
- Install variant: node package or python wheel
- Install target: project-local or global
- Memory mode: project or global
EOF

  local install_variant
  install_variant="$(prompt_value HINDSIGHT_INSTALL_VARIANT "Install variant (node/python)" "python")"
  install_variant="$(echo "$install_variant" | tr '[:upper:]' '[:lower:]')"

  local install_target_default
  if [[ "$install_variant" == "node" ]]; then
    install_target_default="project"
  else
    install_target_default="venv"
  fi

  local install_target
  install_target="$(prompt_value HINDSIGHT_INSTALL_TARGET "Install target (project/global/venv)" "$install_target_default")"
  install_target="$(echo "$install_target" | tr '[:upper:]' '[:lower:]')"

  local memory_mode
  memory_mode="$(prompt_value HINDSIGHT_MEMORY_MODE "Memory mode (project/global)" "project")"
  memory_mode="$(echo "$memory_mode" | tr '[:upper:]' '[:lower:]')"

  local project_root="${HINDSIGHT_PROJECT_ROOT:-$PWD}"
  if [[ "$memory_mode" == "project" ]]; then
    project_root="$(prompt_value HINDSIGHT_PROJECT_ROOT "Project root" "$project_root")"
  fi

  case "$install_variant:$install_target" in
    node:project)
      install_node_project
      ;;
    node:global)
      install_node_global
      ;;
    python:venv)
      install_python_venv
      ;;
    python:project)
      install_python_venv
      ;;
    python:global)
      install_python_global
      ;;
    *)
      echo "Unsupported install combination: ${install_variant}:${install_target}" >&2
      exit 2
      ;;
  esac

  persist_memory_config "$memory_mode" "$project_root"

  cat <<EOF

Installation complete.

Variant command lines:
- Node (project): npm install --save ${NPM_PACKAGE}
- Node (global): npm install -g ${NPM_PACKAGE}
- Python wheel (local venv): python3 -m venv .venv && . .venv/bin/activate && python -m pip install "${PYTHON_WHL_URL}"
- Python wheel (global): python3 -m pip install "${PYTHON_WHL_URL}"

MCP server command:
- agent-mem-mcp
EOF
}

main "$@"
