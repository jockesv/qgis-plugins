#!/usr/bin/env bash
# Build an installable QGIS plugin zip: ./make_zip.sh garmin_export
# Result: dist/<plugin>-<version>.zip, installable via
# Plugins > Manage and Install Plugins > Install from ZIP.
set -euo pipefail
plugin="${1:?usage: $0 <plugin-folder>}"
cd "$(dirname "$0")"
version=$(sed -n 's/^version=//p' "$plugin/metadata.txt")
mkdir -p dist
out="dist/${plugin}-${version}.zip"
rm -f "$out"
git archive --format=zip --prefix="${plugin}/" -o "$out" "HEAD:${plugin}" ":(exclude)tests"
echo "$out"
