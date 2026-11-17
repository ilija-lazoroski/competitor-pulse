#!/usr/bin/env bash
# Regenerates the options section of CONFIGURATION.md from the settings
# classes (pydantic-settings) with settings-doc. Run from anywhere:
#   scripts/autogenerate-settings-docs.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_FILE="${PROJECT_DIR}/CONFIGURATION.md"
BACKUP_FILE="$(mktemp)"
START_MARK="<!-- options-start -->"
END_MARK="<!-- options-end -->"
SETTINGS_CLASSES=(
  competitor_pulse.configuration.CompetitorPulseConfiguration
)

save() {
  cp "${DOCS_FILE}" "${BACKUP_FILE}"
  echo "Backup of ${DOCS_FILE} saved to ${BACKUP_FILE}"
}

restore() {
  echo "Generating the options failed; restoring ${DOCS_FILE} from backup."
  rm -f "${DOCS_FILE}"
  cp "${BACKUP_FILE}" "${DOCS_FILE}"
}

generate_docs() {
  local class_args=()
  for settings_class in "${SETTINGS_CLASSES[@]}"; do
    class_args+=(--class "${settings_class}")
  done

  echo "Generating options documentation for ${#SETTINGS_CLASSES[@]} settings classes..."

  (
    cd "${PROJECT_DIR}"
    poetry run settings-doc generate "${class_args[@]}" \
      --output-format markdown \
      --heading-offset 1 \
      --update "${DOCS_FILE}" \
      --between "${START_MARK}" "${END_MARK}"
  )
}

cleanup() {
  echo "Cleaning up backup file ${BACKUP_FILE}"
  rm -f "${BACKUP_FILE}"
}

main() {
  trap cleanup EXIT

  if ! grep -qF "${START_MARK}" "${DOCS_FILE}" || ! grep -qF "${END_MARK}" "${DOCS_FILE}"; then
    echo "Error: ${DOCS_FILE} must contain '${START_MARK}' and '${END_MARK}'." >&2
    exit 1
  fi

  save
  if ! generate_docs; then
    restore
    echo "Error: generating the options failed; ${DOCS_FILE} was left unchanged." >&2
    exit 1
  fi

  echo "Updated ${DOCS_FILE}"
}

main "$@"
