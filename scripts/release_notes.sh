#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# Print the CHANGELOG.md section for a release tag (v0.7.0 and v0.7.0-rc.1 both print "## [0.7.0]").
# Fails when the section is missing or empty, so a release never goes out without notes.
set -euo pipefail

tag="${1:?usage: release_notes.sh <tag>}"
version="${tag#v}"
base="${version%%-*}"
notes=$(awk -v v="$base" '
  index($0, "## [" v "]") == 1 { found = 1; next }
  found && /^## \[/ { exit }
  found { print }
' "${2:-CHANGELOG.md}" | sed -e '/./,$!d' | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')

if [[ -z "$notes" ]]; then
  echo "No CHANGELOG.md section for $base" >&2
  exit 1
fi
printf '%s\n' "$notes"
