FROM ghcr.io/astral-sh/uv:0.11.6 AS uv
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    CALL_TRANSCRIBER_MODELS=/models MPLCONFIGDIR=/tmp/matplotlib NUMBA_CACHE_DIR=/tmp/numba \
    PATH=/app/.venv/bin:$PATH HOME=/home/app
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY call_transcriber ./call_transcriber
RUN uv sync --frozen --no-dev --no-cache && \
    useradd --uid 1000 --create-home app && \
    mkdir /models /calls && chown app:app /models /calls
USER app
EXPOSE 18765
CMD ["call-transcriber", "--container", "--no-browser", "--port", "18765", "--folder", "/calls"]
