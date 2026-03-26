#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${WORKSPACE_DIR}/src"

if ! command -v vcs-status >/dev/null 2>&1; then
  echo "Error: 'vcs-status' no está instalado." >&2
  exit 1
fi

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Error: no existe ${SRC_DIR}" >&2
  exit 1
fi

vcs-status "${WORKSPACE_DIR}" "${SRC_DIR}"
