#!/usr/bin/env bash
# Stages evals/fixtures/react-app/ into the empty run workspace. Runs only with --scaffold.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/../fixtures/react-app/." .
