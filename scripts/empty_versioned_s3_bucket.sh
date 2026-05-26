#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/empty_versioned_s3_bucket.sh <bucket-name> --confirm-empty-versioned-bucket

Deletes all object versions and delete markers from a versioned S3 bucket.
Use only after all Terraform environments that depend on this state bucket have
been destroyed or migrated.
USAGE
}

bucket="${1:-}"
confirmation="${2:-}"

if [ -z "${bucket}" ] || [ "${confirmation}" != "--confirm-empty-versioned-bucket" ]; then
  usage
  exit 2
fi

command -v aws >/dev/null
command -v jq >/dev/null

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

printf 'Preparing to empty versioned S3 bucket: %s\n' "${bucket}"

while true; do
  versions_file="${tmpdir}/versions.json"
  delete_file="${tmpdir}/delete.json"

  aws s3api list-object-versions \
    --bucket "${bucket}" \
    --max-items 1000 \
    --output json >"${versions_file}"

  jq '
    [
      (.Versions // [])[] | {Key: .Key, VersionId: .VersionId}
    ] + [
      (.DeleteMarkers // [])[] | {Key: .Key, VersionId: .VersionId}
    ]
    | {Objects: ., Quiet: true}
  ' "${versions_file}" >"${delete_file}"

  object_count="$(jq '.Objects | length' "${delete_file}")"
  if [ "${object_count}" -eq 0 ]; then
    break
  fi

  printf 'Deleting %s object version(s)/delete marker(s) from %s...\n' "${object_count}" "${bucket}"
  aws s3api delete-objects \
    --bucket "${bucket}" \
    --delete "file://${delete_file}" >/dev/null
done

printf 'Bucket is empty: %s\n' "${bucket}"
