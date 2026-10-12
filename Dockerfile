# AlfsMigrationToolkit — Streamlit (VMware → OpenShift Virtualization)
# Podman:  podman build --format docker -t alfs-migration-toolkit:latest .
# Run:     podman run --rm -p 8501:8501 alfs-migration-toolkit:latest
# OpenShift: siehe docs/OPENSHIFT-DEPLOY.md (Projekt vma)

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/app \
    STREAMLIT_HOME=/app/.streamlit \
    TMPDIR=/tmp \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_SERVER_MAX_UPLOAD_SIZE=200 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# graphviz: Python-Paket + dot-Binary für HA-Topologie-Diagramme
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# OpenShift restricted SCC: beliebige UID in Gruppe 0, beschreibbare Pfade
RUN mkdir -p /app/.streamlit /tmp/amt-uploads \
    && chgrp -R 0 /app /tmp \
    && chmod -R g=u /app /tmp

# Kein festes USER: OpenShift setzt arbitrary UID; lokal als non-root starten
USER 1001

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5)" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false", \
     "--server.maxUploadSize=200", \
     "--browser.gatherUsageStats=false"]
