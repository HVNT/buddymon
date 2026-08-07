#!/usr/bin/env bash
set -euo pipefail

REQUIRE_RUNTIME=0
OPEN_APP=0
INSTALL_APP=0
BOOTSTRAP_RUNTIME=1
FORCE_RUNTIME=0
ALLOW_UNLOCKED_RUNTIME=0
RUNTIME_SOURCE="${BUDDYMON_PYTHON_RUNTIME:-}"
PYTHON_VERSION=""

usage() {
  cat <<'MSG'
Usage: scripts/build-macos-app.sh [--friend] [--open] [options]

Builds .build/macos/BuddyMon.app.

Options:
  --friend              Build a self-contained app. Uses
                        BUDDYMON_PYTHON_RUNTIME when set; otherwise bootstraps
                        .build/python-runtime with Python + Pillow.
  --runtime-dir DIR     Use an existing runtime directory containing bin/python3.
  --allow-unlocked-runtime
                        Allow an explicitly supplied external development
                        runtime that does not match BuddyMon's runtime lock.
  --python-version VER  Optional CPython version prefix for bootstrap, such as 3.12.
  --force-runtime       Recreate the bootstrapped runtime.
  --no-bootstrap-runtime
                        Fail instead of downloading/building a runtime.
  --open                Open the built app after a successful build.
  --install             Replace BuddyMon.app in /Applications after building.
  -h, --help            Show this help.

For self-contained builds:
  scripts/build-macos-app.sh --friend
  BUDDYMON_PYTHON_RUNTIME=/path/to/python-runtime scripts/build-macos-app.sh --friend
MSG
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --friend|--require-runtime)
      REQUIRE_RUNTIME=1
      ;;
    --runtime-dir)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "error: --runtime-dir requires a directory" >&2
        exit 2
      fi
      RUNTIME_SOURCE="$2"
      shift
      ;;
    --runtime-dir=*)
      RUNTIME_SOURCE="${1#*=}"
      if [[ -z "${RUNTIME_SOURCE}" ]]; then
        echo "error: --runtime-dir requires a directory" >&2
        exit 2
      fi
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
    --force-runtime)
      FORCE_RUNTIME=1
      ;;
    --allow-unlocked-runtime)
      ALLOW_UNLOCKED_RUNTIME=1
      ;;
    --no-bootstrap-runtime)
      BOOTSTRAP_RUNTIME=0
      ;;
    --open)
      OPEN_APP=1
      ;;
    --install)
      INSTALL_APP=1
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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/.build/macos"
ICON_SOURCE="${ROOT}/macos/BuddyMonApp/Resources/AppIcon.icns"
DEFAULT_RUNTIME_DIR="${ROOT}/.build/python-runtime"
VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
BUNDLE_ID="${BUDDYMON_BUNDLE_ID:-com.hvnt.buddymon}"
BUILD_NUMBER="${BUDDYMON_BUILD_NUMBER:-${VERSION}}"
MINIMUM_MACOS_VERSION="13.0"
SWIFT_TARGET="$(uname -m)-apple-macosx${MINIMUM_MACOS_VERSION}"
APP="${BUILD_DIR}/BuddyMon.app"
CONTENTS="${APP}/Contents"
MACOS="${CONTENTS}/MacOS"
RESOURCES="${CONTENTS}/Resources"
RUNTIME="${RESOURCES}/buddymon"

stop_running_buddymon() {
  local running=()
  local pid
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] && running+=("${pid}")
  done < <(pgrep -f '/BuddyMon[.]app/Contents/MacOS/BuddyMon$' || true)

  if [[ "${#running[@]}" -eq 0 ]]; then
    return
  fi

  echo "stopping running BuddyMon process: ${running[*]}"
  kill -TERM "${running[@]}"
  local attempt
  for attempt in {1..30}; do
    local alive=0
    for pid in "${running[@]}"; do
      if kill -0 "${pid}" >/dev/null 2>&1; then
        alive=1
      fi
    done
    if [[ "${alive}" == "0" ]]; then
      return
    fi
    sleep 0.1
  done

  echo "error: running BuddyMon did not quit; stop it before installing" >&2
  return 1
}

if [[ ! "${VERSION}" =~ ^[0-9]+(\.[0-9]+){2}$ ]]; then
  echo "error: VERSION must contain a three-part numeric version" >&2
  exit 1
fi
if [[ ! "${BUNDLE_ID}" =~ ^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$ ]]; then
  echo "error: invalid BuddyMon bundle identifier: ${BUNDLE_ID}" >&2
  exit 1
fi
if [[ ! "${BUILD_NUMBER}" =~ ^[0-9]+(\.[0-9]+){0,2}$ ]]; then
  echo "error: invalid BuddyMon build number: ${BUILD_NUMBER}" >&2
  exit 1
fi

validate_python_runtime() {
  local runtime="$1"
  [[ -x "${runtime}/bin/python3" ]] || return 1
  "${runtime}/bin/python3" - <<'PY' >/dev/null 2>&1
import PIL
import ssl
import urllib.request
PY
}

runtime_matches_lock() {
  python3 "${ROOT}/scripts/verify-python-runtime.py" "$1" >/dev/null 2>&1
}

if [[ "${ALLOW_UNLOCKED_RUNTIME}" == "1" && -z "${RUNTIME_SOURCE}" ]]; then
  cat >&2 <<'MSG'
error: --allow-unlocked-runtime requires BUDDYMON_PYTHON_RUNTIME or --runtime-dir.
MSG
  exit 2
fi

if [[ "${REQUIRE_RUNTIME}" == "1" && -z "${RUNTIME_SOURCE}" ]]; then
  if [[ "${BOOTSTRAP_RUNTIME}" == "1" ]]; then
    args=(--runtime-dir "${DEFAULT_RUNTIME_DIR}")
    if [[ -n "${PYTHON_VERSION}" ]]; then
      args+=(--python-version "${PYTHON_VERSION}")
    fi
    if [[ "${FORCE_RUNTIME}" == "1" ]]; then
      args+=(--force)
    fi
    "${ROOT}/scripts/build-python-runtime.sh" "${args[@]}"
    RUNTIME_SOURCE="${DEFAULT_RUNTIME_DIR}"
  else
    cat >&2 <<'MSG'
error: --friend needs a bundled Python runtime.
       Remove --no-bootstrap-runtime or set BUDDYMON_PYTHON_RUNTIME/--runtime-dir.
MSG
    exit 1
  fi
fi

RUNTIME_IS_LOCKED=0
if [[ -n "${RUNTIME_SOURCE}" ]]; then
  if runtime_matches_lock "${RUNTIME_SOURCE%/}"; then
    RUNTIME_IS_LOCKED=1
  elif [[ "${ALLOW_UNLOCKED_RUNTIME}" != "1" ]]; then
    cat >&2 <<MSG
error: runtime does not match scripts/runtime-lock.json.
       current value: ${RUNTIME_SOURCE}
       For an intentional external development runtime, pass --allow-unlocked-runtime.
MSG
    exit 1
  elif ! validate_python_runtime "${RUNTIME_SOURCE%/}"; then
    cat >&2 <<MSG
error: runtime must contain bin/python3 with Pillow, ssl, and urllib.request.
       current value: ${RUNTIME_SOURCE}
MSG
    exit 1
  fi
elif [[ "${REQUIRE_RUNTIME}" == "1" ]]; then
  cat >&2 <<'MSG'
error: --friend requires a bundled Python runtime.
       The target user should not need Terminal or Python installed.
MSG
  exit 1
fi

rm -rf "${APP}"
mkdir -p "${MACOS}" "${RESOURCES}" "${RUNTIME}"

if [[ ! -f "${ICON_SOURCE}" ]]; then
  echo "error: missing native app icon: ${ICON_SOURCE}" >&2
  exit 1
fi
cp "${ICON_SOURCE}" "${RESOURCES}/AppIcon.icns"

SWIFT_SOURCE_DIR="${ROOT}/macos/BuddyMonApp/Sources/BuddyMonApp"
SWIFT_SOURCES=(
  "${SWIFT_SOURCE_DIR}/main.swift"
  "${SWIFT_SOURCE_DIR}/AppDelegate.swift"
  "${SWIFT_SOURCE_DIR}/BrandStyle.swift"
  "${SWIFT_SOURCE_DIR}/BuddyMonRunner.swift"
  "${SWIFT_SOURCE_DIR}/LocalStateObserver.swift"
  "${SWIFT_SOURCE_DIR}/MenuBarBuddy.swift"
  "${SWIFT_SOURCE_DIR}/MenuPanelController.swift"
  "${SWIFT_SOURCE_DIR}/MenuPanelSharedViews.swift"
  "${SWIFT_SOURCE_DIR}/CompactRootView.swift"
  "${SWIFT_SOURCE_DIR}/CompactTrainerCardView.swift"
  "${SWIFT_SOURCE_DIR}/CompactTokenUsageView.swift"
  "${SWIFT_SOURCE_DIR}/CompactSettingsView.swift"
  "${SWIFT_SOURCE_DIR}/CompactEncounterView.swift"
  "${SWIFT_SOURCE_DIR}/CompactSetupView.swift"
  "${SWIFT_SOURCE_DIR}/ProcessExecutor.swift"
  "${SWIFT_SOURCE_DIR}/SingleInstanceGuard.swift"
)
SWIFTC_ARGS=(-target "${SWIFT_TARGET}" -framework AppKit)

if [[ "${REQUIRE_RUNTIME}" != "1" ]]; then
  SWIFTC_ARGS+=(-D BUDDYMON_DEVELOPMENT)
  SWIFT_SOURCES+=(
    "${SWIFT_SOURCE_DIR}/BrandStylesPreview.swift"
    "${SWIFT_SOURCE_DIR}/StyleArchivePreview.swift"
  )
fi

swiftc \
  "${SWIFTC_ARGS[@]}" \
  "${SWIFT_SOURCES[@]}" \
  -o "${MACOS}/BuddyMon"

cat > "${CONTENTS}/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>BuddyMon</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleName</key>
  <string>BuddyMon</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${BUILD_NUMBER}</string>
  <key>LSMinimumSystemVersion</key>
  <string>${MINIMUM_MACOS_VERSION}</string>
  <key>LSUIElement</key>
  <true/>
</dict>
</plist>
PLIST

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${ROOT}/buddymon.py" \
  "${ROOT}/statusline.py" \
  "${ROOT}/lib" \
  "${ROOT}/tools" \
  "${ROOT}/hooks" \
  "${ROOT}/commands" \
  "${RUNTIME}/"

if [[ -n "${RUNTIME_SOURCE}" ]]; then
  mkdir -p "${RESOURCES}/python"
  rsync -a "${RUNTIME_SOURCE%/}/" "${RESOURCES}/python/"
  if [[ "${RUNTIME_IS_LOCKED}" == "1" ]]; then
    python3 "${ROOT}/scripts/verify-python-runtime.py" "${RESOURCES}/python"
  else
    validate_python_runtime "${RESOURCES}/python"
  fi
else
  cat >&2 <<'MSG'
warning: BUDDYMON_PYTHON_RUNTIME was not set.
         This development app will fall back to /usr/bin/python3 on this Mac.
         Provide a Python runtime directory with bin/python3 for a zero-Python user build.
MSG
fi

if [[ -x "${RESOURCES}/python/bin/python3" ]]; then
  APP_PYTHON="${RESOURCES}/python/bin/python3"
else
  APP_PYTHON="/usr/bin/python3"
fi

if [[ -x "${APP_PYTHON}" ]]; then
  VALIDATION_STATE="${BUILD_DIR}/validation-state"
  rm -rf "${VALIDATION_STATE}"
  mkdir -p "${VALIDATION_STATE}"
  VALIDATION_JSON="${BUILD_DIR}/app-status-validation.json"
  XDG_STATE_HOME="${VALIDATION_STATE}" "${APP_PYTHON}" "${RUNTIME}/buddymon.py" app-status > "${VALIDATION_JSON}"
  "${APP_PYTHON}" -c 'import json, sys; json.load(open(sys.argv[1], encoding="utf-8"))' "${VALIDATION_JSON}"
fi

python3 "${ROOT}/scripts/validate-release-metadata.py" \
  --app "${APP}" \
  --bundle-id "${BUNDLE_ID}" \
  --build-number "${BUILD_NUMBER}"

echo "built ${APP}"

OPEN_TARGET="${APP}"
if [[ "${INSTALL_APP}" == "1" ]]; then
  INSTALL_ROOT="${BUDDYMON_INSTALL_DIR:-/Applications}"
  INSTALLED_APP="${INSTALL_ROOT%/}/BuddyMon.app"
  stop_running_buddymon
  mkdir -p "${INSTALL_ROOT}"
  rsync -a --delete "${APP}/" "${INSTALLED_APP}/"
  OPEN_TARGET="${INSTALLED_APP}"
  echo "installed ${INSTALLED_APP}"
fi

if [[ "${OPEN_APP}" == "1" ]]; then
  if [[ "${INSTALL_APP}" == "1" ]]; then
    open -n "${OPEN_TARGET}"
  else
    open "${OPEN_TARGET}"
  fi
fi
