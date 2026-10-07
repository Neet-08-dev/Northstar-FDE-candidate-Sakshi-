FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --locked --no-dev
COPY . /app
ENV PATH="/app/.venv/bin:$PATH"
USER 65532:65532
CMD ["python", "-m", "starter.agent", "--host", "0.0.0.0"]
