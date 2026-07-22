#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${ROOT}/.build/menu-bar-state-harness.png}"

"${ROOT}/scripts/menu-bar-state-harness.sh" "${OUTPUT}"
