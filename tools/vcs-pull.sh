#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPOS_FILE="${WORKSPACE_DIR}/.repos"
SRC_DIR="${WORKSPACE_DIR}/src"
IMPORT_BASE_DIR="${SRC_DIR}"

if ! command -v vcs-import >/dev/null 2>&1; then
  echo "Error: 'vcs-import' no está instalado." >&2
  exit 1
fi

if ! command -v vcs-pull >/dev/null 2>&1; then
  echo "Error: 'vcs-pull' no está instalado." >&2
  exit 1
fi

if [[ ! -f "${REPOS_FILE}" ]]; then
  echo "Error: no existe ${REPOS_FILE}" >&2
  exit 1
fi

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Error: no existe ${SRC_DIR}" >&2
  exit 1
fi

# Si el .repos define rutas como "src/paquete", hay que importar desde la raíz.
if grep -Eq '^[[:space:]]{2}src/' "${REPOS_FILE}"; then
  IMPORT_BASE_DIR="${WORKSPACE_DIR}"
fi

echo "[1/3] Actualizando repo raíz..."
git -C "${WORKSPACE_DIR}" pull --ff-only

echo "[2/3] Importando repos definidos en .repos..."
import_failed=0
if ! vcs-import "${IMPORT_BASE_DIR}" < "${REPOS_FILE}"; then
  import_failed=1
  echo "Warning: vcs-import terminó con errores. Continuando con vcs-pull..." >&2
fi

echo "[3/3] Haciendo pull de repos en src..."
vcs-pull "${SRC_DIR}"

if (( import_failed )); then
  echo "Workspace actualizado con advertencias: vcs-import tuvo errores, pero vcs-pull se ejecutó."
else
  echo "Workspace actualizado."
fi
