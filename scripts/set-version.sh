#!/usr/bin/env bash

set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  printf 'Usage: %s <version> [pkgrel]\n' "${0##*/}" >&2
  exit 64
fi

version=$1
pkgrel=${2:-1}
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

[[ $version =~ ^[0-9]+(\.[0-9]+)*$ ]] || {
  printf 'set-version.sh: invalid version: %s\n' "$version" >&2
  exit 64
}

[[ $pkgrel =~ ^[0-9]+$ ]] || {
  printf 'set-version.sh: invalid pkgrel: %s\n' "$pkgrel" >&2
  exit 64
}

printf '%s\n' "$version" >"$repo_root/VERSION"

sed -i \
  -e "s/^pkgver=.*/pkgver=$version/" \
  -e "s/^pkgrel=.*/pkgrel=$pkgrel/" \
  "$repo_root/PKGBUILD"

sed -i \
  -e "s/^version=.*/version=$version/" \
  "$repo_root/bin/asudo"

(cd "$repo_root" && makepkg --printsrcinfo > .SRCINFO)

printf 'Updated version to %s-%s\n' "$version" "$pkgrel"
