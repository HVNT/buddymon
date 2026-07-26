#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
ARCH="$(uname -m)"
RUNTIME="${ROOT}/.build/release-python-runtime"
APP="${ROOT}/.build/macos/BuddyMon.app"
OUTPUT_DIR="${ROOT}/.build/release"
IDENTITY="${BUDDYMON_CODESIGN_IDENTITY:-}"
NOTARY_PROFILE="${BUDDYMON_NOTARY_PROFILE:-}"
PRODUCTION_BUNDLE_ID="com.hvnt.buddymon"
PRODUCTION_BUILD_NUMBER="${VERSION}"

if [[ "${BUDDYMON_BUNDLE_ID+x}" == "x" ]] \
  || [[ "${BUDDYMON_BUILD_NUMBER+x}" == "x" ]]; then
  echo "error: release bundle metadata overrides are not allowed" >&2
  exit 2
fi
if [[ -z "${IDENTITY}" ]]; then
  echo "error: BUDDYMON_CODESIGN_IDENTITY is required" >&2
  exit 2
fi
if [[ -z "${NOTARY_PROFILE}" ]]; then
  echo "error: BUDDYMON_NOTARY_PROFILE is required" >&2
  exit 2
fi
for command in codesign ditto file shasum spctl xcrun; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "error: ${command} is required for a macOS release" >&2
    exit 1
  fi
done

"${ROOT}/scripts/build-python-runtime.sh" \
  --runtime-dir "${RUNTIME}" \
  --force
python3 "${ROOT}/scripts/verify-python-runtime.py" "${RUNTIME}"
BUDDYMON_BUNDLE_ID="${PRODUCTION_BUNDLE_ID}" \
BUDDYMON_BUILD_NUMBER="${PRODUCTION_BUILD_NUMBER}" \
  "${ROOT}/scripts/build-macos-app.sh" \
  --friend \
  --no-bootstrap-runtime \
  --runtime-dir "${RUNTIME}"
python3 "${ROOT}/scripts/validate-release-metadata.py" \
  --app "${APP}" \
  --bundle-id "${PRODUCTION_BUNDLE_ID}" \
  --build-number "${PRODUCTION_BUILD_NUMBER}"

while IFS= read -r -d '' item; do
  if file -b "${item}" | grep -q "Mach-O"; then
    codesign \
      --force \
      --options runtime \
      --timestamp \
      --sign "${IDENTITY}" \
      "${item}"
  fi
done < <(find "${APP}/Contents/Resources/python" -type f -print0)

codesign \
  --force \
  --options runtime \
  --timestamp \
  --sign "${IDENTITY}" \
  "${APP}/Contents/MacOS/BuddyMon"
codesign \
  --force \
  --options runtime \
  --timestamp \
  --sign "${IDENTITY}" \
  "${APP}"
codesign --verify --deep --strict --verbose=2 "${APP}"

mkdir -p "${OUTPUT_DIR}"
ARCHIVE="${OUTPUT_DIR}/BuddyMon-${VERSION}-${ARCH}.zip"
rm -f "${ARCHIVE}" "${ARCHIVE}.sha256"
ditto -c -k --keepParent "${APP}" "${ARCHIVE}"
xcrun notarytool submit \
  "${ARCHIVE}" \
  --keychain-profile "${NOTARY_PROFILE}" \
  --wait
xcrun stapler staple "${APP}"
xcrun stapler validate "${APP}"
spctl --assess --type execute --verbose=2 "${APP}"
python3 "${ROOT}/scripts/validate-release-metadata.py" \
  --app "${APP}" \
  --bundle-id "${PRODUCTION_BUNDLE_ID}" \
  --build-number "${PRODUCTION_BUILD_NUMBER}"
ditto -c -k --keepParent "${APP}" "${ARCHIVE}"
ARCHIVE_NAME="$(basename "${ARCHIVE}")"
(
  cd "${OUTPUT_DIR}"
  shasum -a 256 "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256"
)

echo "release archive: ${ARCHIVE}"
echo "release checksum: ${ARCHIVE}.sha256"
