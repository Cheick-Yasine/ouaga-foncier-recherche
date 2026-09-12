FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MCP_SERVER_URL=http://127.0.0.1:8000/mcp

WORKDIR /app

# Installer les dépendances avant le code pour réutiliser le cache Docker.
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

# Le référentiel des quartiers dans app/data est inclus.
COPY app/ ./app/
COPY db/ ./db/

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# /health est fourni par FastAPI, sans appel payant au modèle.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# Un processus héberge le site et le MCP sur le même port.
CMD ["python", "-m", "uvicorn", "app.combined:http_app", "--host", "0.0.0.0", "--port", "8000"]
