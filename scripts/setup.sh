#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
    uv sync --locked
else
    if [ ! -x .tools/uv/bin/uv ]; then
        python3 -m venv .tools/uv
        .tools/uv/bin/python -m pip install 'uv==0.12.23'
    fi
    .tools/uv/bin/uv sync --locked
fi
