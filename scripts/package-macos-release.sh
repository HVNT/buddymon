#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
RUNTIME="${ROOT}/.build/release-python-runtimes"
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
for command in codesign ditto file shasum spctl xcrun hdiutil lipo; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "error: ${command} is required for a macOS release" >&2
    exit 1
  fi
done

python3 "${ROOT}/scripts/validate-release-metadata.py" \
  --require-dated-changelog

for architecture in arm64 x86_64; do
  "${ROOT}/scripts/build-python-runtime.sh" \
    --arch "${architecture}" --runtime-dir "${RUNTIME}/${architecture}" --force
  python3 "${ROOT}/scripts/verify-python-runtime.py" "${RUNTIME}/${architecture}" --arch "${architecture}"
done
BUDDYMON_BUNDLE_ID="${PRODUCTION_BUNDLE_ID}" \
BUDDYMON_BUILD_NUMBER="${PRODUCTION_BUILD_NUMBER}" \
  "${ROOT}/scripts/build-macos-app.sh" \
  --universal \
  --no-bootstrap-runtime \
  --runtime-dir "${RUNTIME}"
python3 "${ROOT}/scripts/validate-release-metadata.py" \
  --require-dated-changelog \
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
ARCHIVE="${OUTPUT_DIR}/BuddyMon-notarization.zip"
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
  --require-dated-changelog \
  --app "${APP}" \
  --bundle-id "${PRODUCTION_BUNDLE_ID}" \
  --build-number "${PRODUCTION_BUILD_NUMBER}"
ditto -c -k --keepParent "${APP}" "${ARCHIVE}"
DISK_IMAGE="${OUTPUT_DIR}/BuddyMon-macOS.dmg"
bash "${ROOT}/scripts/create-macos-dmg.sh" "${APP}" "${DISK_IMAGE}"
codesign --force --timestamp --sign "${IDENTITY}" "${DISK_IMAGE}"
xcrun notarytool submit "${DISK_IMAGE}" --keychain-profile "${NOTARY_PROFILE}" --wait
xcrun stapler staple "${DISK_IMAGE}"
xcrun stapler validate "${DISK_IMAGE}"
ARCHIVE_NAME="$(basename "${DISK_IMAGE}")"
(
  cd "${OUTPUT_DIR}"
  shasum -a 256 "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256"
)
python3 "${ROOT}/scripts/verify-release-archive.py" \
  "${DISK_IMAGE}" \
  "${DISK_IMAGE}.sha256"

echo "release download: ${DISK_IMAGE}"
echo "release checksum: ${DISK_IMAGE}.sha256"
