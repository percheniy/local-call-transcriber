#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PATH="$HOME/.local/bin:$PATH"
uv sync --project "$PROJECT_DIR" --python 3.11 --frozen
uv run --project "$PROJECT_DIR" --frozen python -c 'from call_transcriber.runtime import ensure_models; ensure_models(print)'
printf '%s\n' 'Готово. Интерфейс: ./ui. Терминал: ./transcribe "/путь/к/папке"'
