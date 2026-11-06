FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version README.md /app/
RUN uv sync --locked --no-dev
COPY boardgame /app/boardgame
COPY doc/FCM_IMPLEMENTATION.md doc/FCM_RULES.md doc/FCM_EXPANSIONS.md /app/doc/
RUN chmod -R a+rX /app && useradd --uid 10001 --create-home boardgame && mkdir /data && chown boardgame:boardgame /data
USER boardgame
VOLUME /data
EXPOSE 8000
CMD ["uv", "run", "--frozen", "--no-sync", "python", "-m", "boardgame.server", "--host", "0.0.0.0", "--database", "/data/boardgame.sqlite3"]
