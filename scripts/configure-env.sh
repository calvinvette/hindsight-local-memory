#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

command_name="${1:-init}"
if [ "$#" -gt 0 ]; then
  shift
fi

python_bin="${CONFIG_PYTHON:-python3}"

case "$command_name" in
  init|setup)
    exec "$python_bin" scripts/config-manager init "$@"
    ;;
  setup-ci)
    exec "$python_bin" scripts/config-manager init --ci "$@"
    ;;
  status)
    exec "$python_bin" scripts/config-manager status "$@"
    ;;
  edit)
    exec "$python_bin" scripts/config-manager edit "$@"
    ;;
  update)
    exec "$python_bin" scripts/config-manager update "$@"
    ;;
  *)
    exec "$python_bin" scripts/config-manager "$command_name" "$@"
    ;;
esac