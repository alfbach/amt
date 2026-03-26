# AlfsMigrationToolkit — Streamlit app (VMware → OpenShift Virtualization)
# Build: docker build -t alfs-migration-toolkit .
# Run:   docker run --rm -p 8501:8501 alfs-migration-toolkit

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# graphviz: Python package + dot binary for HA topology diagrams
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

# Dependencies (cached layer when only app code changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application (see .dockerignore)
COPY . .

RUN useradd --create-home --uid 1000 --no-log-init appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5)" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
