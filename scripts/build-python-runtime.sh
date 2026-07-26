#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR=""
RUNTIME_DIR_SET=0
FORCE=0
PYTHON_VERSION="${PYTHON_BUILD_STANDALONE_VERSION:-}"
SOURCE_URL="${PYTHON_BUILD_STANDALONE_URL:-}"
SOURCE_TARBALL="${PYTHON_BUILD_STANDALONE_TARBALL:-}"
SOURCE_SHA256="${PYTHON_BUILD_STANDALONE_SHA256:-}"
WORK_DIR=""
BACKUP_DIR=""

usage() {
  cat <<'MSG'
Usage: scripts/build-python-runtime.sh [options]

Creates a standalone Python runtime for self-contained BuddyMon app builds.

Options:
  --runtime-dir DIR      Output directory. Defaults to .build/python-runtime.
  --python-version VER   Exact locked CPython version.
  --url URL              Direct python-build-standalone tarball URL.
  --tarball PATH         Local python-build-standalone tarball.
  --sha256 HASH          Required SHA-256 for URL/tarball overrides.
  --force                Recreate a BuddyMon-managed runtime even if valid.
  -h, --help             Show this help.

Environment aliases:
  PYTHON_BUILD_STANDALONE_VERSION
  PYTHON_BUILD_STANDALONE_URL
  PYTHON_BUILD_STANDALONE_TARBALL
  PYTHON_BUILD_STANDALONE_SHA256
MSG
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime-dir)
      if [[ $# -lt 2 ]]; then
        echo "error: --runtime-dir requires a directory" >&2
        exit 2
      fi
      RUNTIME_DIR="$2"
      RUNTIME_DIR_SET=1
      shift
      ;;
    --runtime-dir=*)
      RUNTIME_DIR="${1#*=}"
      RUNTIME_DIR_SET=1
      ;;
    --python-version)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "error: --python-version requires a version" >&2
        exit 2
      fi
      PYTHON_VERSION="$2"
      shift
      ;;
    --python-version=*)
      PYTHON_VERSION="${1#*=}"
      if [[ -z "${PYTHON_VERSION}" ]]; then
        echo "error: --python-version requires a version" >&2
        exit 2
      fi
      ;;
    --url)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "error: --url requires a URL" >&2
        exit 2
      fi
      SOURCE_URL="$2"
      shift
      ;;
    --url=*)
      SOURCE_URL="${1#*=}"
      if [[ -z "${SOURCE_URL}" ]]; then
        echo "error: --url requires a URL" >&2
        exit 2
      fi
      ;;
    --tarball)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "error: --tarball requires a path" >&2
        exit 2
      fi
      SOURCE_TARBALL="$2"
      shift
      ;;
    --tarball=*)
      SOURCE_TARBALL="${1#*=}"
      if [[ -z "${SOURCE_TARBALL}" ]]; then
        echo "error: --tarball requires a path" >&2
        exit 2
      fi
      ;;
    --sha256)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "error: --sha256 requires a hash" >&2
        exit 2
      fi
      SOURCE_SHA256="$2"
      shift
      ;;
    --sha256=*)
      SOURCE_SHA256="${1#*=}"
      if [[ -z "${SOURCE_SHA256}" ]]; then
        echo "error: --sha256 requires a hash" >&2
        exit 2
      fi
      ;;
    --force)
      FORCE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "${RUNTIME_DIR_SET}" == "1" && -z "${RUNTIME_DIR}" ]]; then
  echo "error: --runtime-dir requires a directory" >&2
  exit 2
fi
RUNTIME_DIR="${RUNTIME_DIR:-${ROOT}/.build/python-runtime}"
ARCH="$(uname -m)"

case "${ARCH}" in
  arm64)
    PBS_PLATFORM="aarch64-apple-darwin"
    ;;
  x86_64)
    PBS_PLATFORM="x86_64-apple-darwin"
    ;;
  *)
    echo "unsupported macOS architecture: ${ARCH}" >&2
    exit 1
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required on the packaging Mac to prepare a runtime" >&2
  exit 1
fi

LOCK_FILE="${ROOT}/scripts/runtime-lock.json"
LOCK_VALUES="$(
  python3 - "${LOCK_FILE}" "${PBS_PLATFORM}" <<'PY'
import json
import sys

lock = json.load(open(sys.argv[1], encoding="utf-8"))
python = lock["python"]
entry = python["platforms"].get(sys.argv[2])
if not entry:
    raise SystemExit(f"runtime lock does not support {sys.argv[2]}")
pillow = entry["pillow"]
print("\t".join((
    python["version"],
    entry["url"],
    entry["sha256"],
    pillow["version"],
    pillow["url"],
    pillow["sha256"],
)))
PY
)"
IFS=$'\t' read -r \
  LOCKED_PYTHON_VERSION \
  LOCKED_SOURCE_URL \
  LOCKED_SOURCE_SHA256 \
  LOCKED_PILLOW_VERSION \
  LOCKED_PILLOW_URL \
  LOCKED_PILLOW_SHA256 <<< "${LOCK_VALUES}"

if [[ -z "${PYTHON_VERSION}" ]]; then
  PYTHON_VERSION="${LOCKED_PYTHON_VERSION}"
elif [[ "${PYTHON_VERSION}" != "${LOCKED_PYTHON_VERSION}" ]]; then
  echo "error: Python ${PYTHON_VERSION} is not in scripts/runtime-lock.json" >&2
  exit 1
fi

if [[ -z "${SOURCE_URL}" && -z "${SOURCE_TARBALL}" ]]; then
  SOURCE_URL="${LOCKED_SOURCE_URL}"
  SOURCE_SHA256="${LOCKED_SOURCE_SHA256}"
elif [[ -n "${SOURCE_URL}" && "${SOURCE_URL}" == "${LOCKED_SOURCE_URL}" && -z "${SOURCE_SHA256}" ]]; then
  SOURCE_SHA256="${LOCKED_SOURCE_SHA256}"
fi
if [[ ! "${SOURCE_SHA256}" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo "error: URL and tarball overrides require --sha256 with a 64-character digest" >&2
  exit 1
fi
SOURCE_SHA256="$(printf '%s' "${SOURCE_SHA256}" | tr '[:upper:]' '[:lower:]')"

lexical_path() {
  python3 - "$1" <<'PY'
import os
import sys

print(os.path.abspath(os.path.expanduser(sys.argv[1])))
PY
}

canonical_path() {
  python3 - "$1" <<'PY'
import os
import sys

print(os.path.realpath(os.path.abspath(os.path.expanduser(sys.argv[1]))))
PY
}

LEXICAL_RUNTIME_DIR="$(lexical_path "${RUNTIME_DIR}")"
if [[ -L "${LEXICAL_RUNTIME_DIR}" ]]; then
  echo "error: refusing symlink runtime destination: ${LEXICAL_RUNTIME_DIR}" >&2
  echo "       Choose a real directory for --runtime-dir." >&2
  exit 1
fi
RUNTIME_DIR="$(canonical_path "${LEXICAL_RUNTIME_DIR}")"
HOME_DIR=""
if [[ -n "${HOME:-}" ]]; then
  HOME_DIR="$(canonical_path "${HOME}")"
fi

path_is_same_or_parent() {
  local candidate="$1"
  local child="$2"
  case "${child}/" in
    "${candidate}/"*) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ "${RUNTIME_DIR}" == "/" ]] \
  || [[ -n "${HOME_DIR}" && "${RUNTIME_DIR}" == "${HOME_DIR}" ]] \
  || path_is_same_or_parent "${RUNTIME_DIR}" "${ROOT}" \
  || [[ "${RUNTIME_DIR}/" == "${ROOT}/.git/"* ]]; then
  echo "error: refusing unsafe runtime destination: ${RUNTIME_DIR}" >&2
  echo "       Choose a dedicated directory such as ${ROOT}/.build/python-runtime." >&2
  exit 1
fi

validate_runtime() {
  local runtime="$1"
  [[ -x "${runtime}/bin/python3" ]] || return 1
  "${runtime}/bin/python3" - <<'PY' >/dev/null 2>&1
import PIL
import ssl
import urllib.request
PY
}

runtime_is_managed() {
  local metadata="$1/buddymon-runtime.json"
  [[ -f "${metadata}" && ! -L "${metadata}" ]] || return 1
  python3 - "${metadata}" <<'PY' >/dev/null 2>&1
import json
import sys

try:
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError, TypeError):
    raise SystemExit(1)

if not isinstance(payload, dict):
    raise SystemExit(1)

owner = payload.get("managed_by")
if owner is not None:
    raise SystemExit(0 if owner == "buddymon" and payload.get("schema_version") == 1 else 1)

# Metadata written before the ownership fields were introduced remains valid.
legacy_fields = {"built_at", "platform", "python", "pillow", "source_url"}
raise SystemExit(0 if legacy_fields.issubset(payload) else 1)
PY
}

directory_is_empty() {
  [[ -d "$1" ]] || return 1
  [[ -z "$(find "$1" -mindepth 1 -print -quit)" ]]
}

if [[ "${FORCE}" != "1" ]] \
  && python3 "${ROOT}/scripts/verify-python-runtime.py" "${RUNTIME_DIR}" \
    >/dev/null 2>&1; then
  echo "runtime already matches lock: ${RUNTIME_DIR}"
  exit 0
fi

if [[ -e "${RUNTIME_DIR}" && ! -d "${RUNTIME_DIR}" ]]; then
  echo "error: runtime destination is not a directory: ${RUNTIME_DIR}" >&2
  exit 1
fi

if [[ -d "${RUNTIME_DIR}" ]] \
  && ! directory_is_empty "${RUNTIME_DIR}" \
  && ! runtime_is_managed "${RUNTIME_DIR}"; then
  cat >&2 <<MSG
error: refusing to replace an unmanaged runtime directory: ${RUNTIME_DIR}
       Choose a new or empty --runtime-dir, or remove this directory yourself.
       --force only replaces runtimes marked by buddymon-runtime.json.
MSG
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "tar is required on the packaging Mac to extract the runtime" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on the packaging Mac to copy the runtime" >&2
  exit 1
fi

if [[ -z "${SOURCE_TARBALL}" ]] && ! command -v curl >/dev/null 2>&1; then
  echo "curl is required on the packaging Mac to download the runtime" >&2
  exit 1
fi

RUNTIME_PARENT="$(dirname "${RUNTIME_DIR}")"
mkdir -p "${RUNTIME_PARENT}"
WORK_DIR="$(mktemp -d "${RUNTIME_PARENT}/.buddymon-python-runtime.XXXXXX")"

cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
    if [[ ! -e "${RUNTIME_DIR}" ]]; then
      mv "${BACKUP_DIR}" "${RUNTIME_DIR}" || true
    else
      echo "warning: previous runtime preserved at ${BACKUP_DIR}" >&2
    fi
  fi
  if [[ -n "${WORK_DIR}" && -d "${WORK_DIR}" ]]; then
    rm -rf "${WORK_DIR}"
  fi
  exit "${status}"
}
trap cleanup EXIT

ARCHIVE="${WORK_DIR}/python-build-standalone.tar.gz"

if [[ -n "${SOURCE_TARBALL}" ]]; then
  if [[ ! -f "${SOURCE_TARBALL}" ]]; then
    echo "runtime tarball does not exist: ${SOURCE_TARBALL}" >&2
    exit 1
  fi
  cp "${SOURCE_TARBALL}" "${ARCHIVE}"
else
  echo "downloading runtime: ${SOURCE_URL}"
  curl -L --fail --show-error --output "${ARCHIVE}" "${SOURCE_URL}"
fi

ACTUAL_SOURCE_SHA256="$(
  python3 - "${ARCHIVE}" <<'PY'
import hashlib
import sys

digest = hashlib.sha256()
with open(sys.argv[1], "rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
)"
if [[ "${ACTUAL_SOURCE_SHA256}" != "${SOURCE_SHA256}" ]]; then
  echo "runtime archive SHA-256 mismatch" >&2
  echo "expected: ${SOURCE_SHA256}" >&2
  echo "actual:   ${ACTUAL_SOURCE_SHA256}" >&2
  exit 1
fi

EXTRACT_DIR="${WORK_DIR}/extract"
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${ARCHIVE}" -C "${EXTRACT_DIR}"

PYTHON_ROOT="${EXTRACT_DIR}/python"
if [[ ! -x "${PYTHON_ROOT}/bin/python3" ]]; then
  PYTHON_ROOT="$(find "${EXTRACT_DIR}" -type f -path '*/bin/python3' -perm -111 -print -quit | sed 's#/bin/python3$##')"
fi
if [[ -z "${PYTHON_ROOT}" || ! -x "${PYTHON_ROOT}/bin/python3" ]]; then
  echo "extracted runtime did not contain bin/python3" >&2
  exit 1
fi

STAGED_RUNTIME="${WORK_DIR}/runtime"
mkdir -p "${STAGED_RUNTIME}"
rsync -a "${PYTHON_ROOT%/}/" "${STAGED_RUNTIME}/"

"${STAGED_RUNTIME}/bin/python3" -m ensurepip --upgrade
RUNTIME_REQUIREMENTS="${WORK_DIR}/runtime-requirements.txt"
printf 'Pillow @ %s --hash=sha256:%s\n' \
  "${LOCKED_PILLOW_URL}" \
  "${LOCKED_PILLOW_SHA256}" > "${RUNTIME_REQUIREMENTS}"
"${STAGED_RUNTIME}/bin/python3" -m pip install \
  --disable-pip-version-check \
  --no-deps \
  --only-binary=:all: \
  --require-hashes \
  --requirement "${RUNTIME_REQUIREMENTS}"
"${STAGED_RUNTIME}/bin/python3" - "${LOCKED_PILLOW_VERSION}" <<'PY'
import PIL
import sys

if PIL.__version__ != sys.argv[1]:
    raise SystemExit(
        f"installed Pillow {PIL.__version__}, expected locked {sys.argv[1]}"
    )
PY

if ! validate_runtime "${STAGED_RUNTIME}"; then
  echo "runtime validation failed before install: ${RUNTIME_DIR}" >&2
  exit 1
fi

BUDDYMON_RUNTIME_PLATFORM="${PBS_PLATFORM}" \
BUDDYMON_RUNTIME_SOURCE_URL="${SOURCE_URL}" \
 BUDDYMON_RUNTIME_SOURCE_SHA256="${SOURCE_SHA256}" \
 BUDDYMON_RUNTIME_PILLOW_URL="${LOCKED_PILLOW_URL}" \
 BUDDYMON_RUNTIME_PILLOW_SHA256="${LOCKED_PILLOW_SHA256}" \
  "${STAGED_RUNTIME}/bin/python3" - <<'PY' >"${STAGED_RUNTIME}/buddymon-runtime.json"
import json
import os
import PIL
import platform
from datetime import datetime, timezone

payload = {
    "schema_version": 1,
    "managed_by": "buddymon",
    "built_at": datetime.now(timezone.utc).isoformat(),
    "platform": os.environ["BUDDYMON_RUNTIME_PLATFORM"],
    "python": platform.python_version(),
    "pillow": getattr(PIL, "__version__", "unknown"),
    "source_url": os.environ["BUDDYMON_RUNTIME_SOURCE_URL"],
    "source_sha256": os.environ["BUDDYMON_RUNTIME_SOURCE_SHA256"],
    "pillow_url": os.environ["BUDDYMON_RUNTIME_PILLOW_URL"],
    "pillow_sha256": os.environ["BUDDYMON_RUNTIME_PILLOW_SHA256"],
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY

if ! runtime_is_managed "${STAGED_RUNTIME}"; then
  echo "runtime ownership metadata validation failed: ${RUNTIME_DIR}" >&2
  exit 1
fi

HAD_EMPTY_TARGET=0
if [[ -d "${RUNTIME_DIR}" ]]; then
  if directory_is_empty "${RUNTIME_DIR}"; then
    rmdir "${RUNTIME_DIR}"
    HAD_EMPTY_TARGET=1
  else
    BACKUP_DIR="$(mktemp -d "${RUNTIME_PARENT}/.buddymon-python-runtime-backup.XXXXXX")"
    rmdir "${BACKUP_DIR}"
    mv "${RUNTIME_DIR}" "${BACKUP_DIR}"
  fi
fi

if ! mv "${STAGED_RUNTIME}" "${RUNTIME_DIR}"; then
  if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
    mv "${BACKUP_DIR}" "${RUNTIME_DIR}"
    BACKUP_DIR=""
  elif [[ "${HAD_EMPTY_TARGET}" == "1" ]]; then
    mkdir -p "${RUNTIME_DIR}"
  fi
  echo "failed to install runtime: ${RUNTIME_DIR}" >&2
  exit 1
fi

if ! validate_runtime "${RUNTIME_DIR}"; then
  mv "${RUNTIME_DIR}" "${WORK_DIR}/failed-runtime"
  if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
    mv "${BACKUP_DIR}" "${RUNTIME_DIR}"
    BACKUP_DIR=""
  elif [[ "${HAD_EMPTY_TARGET}" == "1" ]]; then
    mkdir -p "${RUNTIME_DIR}"
  fi
  echo "runtime validation failed after install: ${RUNTIME_DIR}" >&2
  exit 1
fi

if [[ -z "${SOURCE_TARBALL}" && "${SOURCE_URL}" == "${LOCKED_SOURCE_URL}" ]] \
  && ! python3 "${ROOT}/scripts/verify-python-runtime.py" "${RUNTIME_DIR}"; then
  mv "${RUNTIME_DIR}" "${WORK_DIR}/failed-runtime"
  if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
    mv "${BACKUP_DIR}" "${RUNTIME_DIR}"
    BACKUP_DIR=""
  elif [[ "${HAD_EMPTY_TARGET}" == "1" ]]; then
    mkdir -p "${RUNTIME_DIR}"
  fi
  echo "runtime lock validation failed after install: ${RUNTIME_DIR}" >&2
  exit 1
fi

if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
  rm -rf "${BACKUP_DIR}"
  BACKUP_DIR=""
fi

echo "built runtime: ${RUNTIME_DIR}"
