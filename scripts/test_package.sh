#!/usr/bin/env bash
# Exercise the built wheel without the checkout or development dependencies.
set -euo pipefail

wheel=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
entrypoint=$2
repo_root=$(cd "$(dirname "$0")/.." && pwd)
package_test_dir=$(mktemp -d)
trap 'rm -rf "$package_test_dir"' EXIT

uv venv --python 3.10 "$package_test_dir/venv"
uv pip install --python "$package_test_dir/venv/bin/python" "$wheel" pytest
cp "$repo_root/tests/unit/clients/test_error_report.py" "$package_test_dir/test_error_report.py"
cd "$package_test_dir"
unset PYTHONPATH VIRTUAL_ENV
"$package_test_dir/venv/bin/python" -I -c 'import src.server'
"$package_test_dir/venv/bin/$entrypoint" --help
"$package_test_dir/venv/bin/python" -I -m pytest --import-mode=importlib -o "markers=unit: unit tests" test_error_report.py -q
