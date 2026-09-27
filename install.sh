#!/bin/sh
# Native bootstrap for Apple Silicon macOS and Linux. See MANUAL.md for Docker on Windows/Intel Mac.
set -eu
VERSION=v1.0.0
REPOSITORY=https://github.com/percheniy/local-call-transcriber
case "$(uname -s):$(uname -m)" in
  Darwin:arm64|Linux:x86_64|Linux:aarch64) ;;
  *) echo 'На этой платформе используйте Docker-команду из MANUAL.md (Windows и Intel Mac).'; exit 1 ;;
esac
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  UV_INSTALLER=$(mktemp)
  curl --fail --silent --show-error --location https://astral.sh/uv/install.sh -o "$UV_INSTALLER"
  UV_NO_MODIFY_PATH=1 sh "$UV_INSTALLER"
  rm -f "$UV_INSTALLER"
fi
APP_HOME="${CALL_TRANSCRIBER_HOME:-$HOME/.local/share/local-call-transcriber}"
RELEASE_DIR="$APP_HOME/releases/$VERSION"
mkdir -p "$APP_HOME/releases"
if [ ! -f "$RELEASE_DIR/pyproject.toml" ]; then
  STAGING=$(mktemp -d "$APP_HOME/releases/.install-XXXXXX")
  trap 'rm -rf "$STAGING"' EXIT HUP INT TERM
  curl --fail --silent --show-error --location "$REPOSITORY/archive/refs/tags/$VERSION.tar.gz" -o "$STAGING/source.tar.gz"
  mkdir "$STAGING/app"
  tar -xzf "$STAGING/source.tar.gz" -C "$STAGING/app" --strip-components=1
  mv "$STAGING/app" "$RELEASE_DIR"
  rm -rf "$STAGING"
  trap - EXIT HUP INT TERM
fi
uv sync --project "$RELEASE_DIR" --python 3.11 --frozen
uv run --project "$RELEASE_DIR" --frozen python -c 'from call_transcriber.runtime import ensure_models; ensure_models(print)'
exec uv run --project "$RELEASE_DIR" --frozen call-transcriber "$@"
