# Ferrero web app for a Linux server: FastAPI + the built React frontend (src/ferrero/web/dist), with the case data,
# the document index and the cached text recognition baked in. Credentials (.env) are passed at run time by
# docker-compose.yml and never enter the image. See README, "Deploying to a server".
#
#     docker compose up -d --build
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Dependencies first, pinned to the versions tested on the development machine, so code changes don't reinstall them.
# Editable install, as on Windows: the code then stays in /app/src, which is where it finds docs/ and data/.
COPY pyproject.toml README.md deploy/constraints.txt ./
RUN mkdir -p src/ferrero && touch src/ferrero/__init__.py \
 && pip install -c constraints.txt -e ".[bedrock]"

# The web app reads the case tracker CSVs, the corpus catalogue, the index built by `python -m ferrero.sync`
# (data/index.sqlite) and the OCR cache (data/ocr: recognised text and page images for the viewer); not the PDFs.
COPY src ./src
COPY docs/Ferrero_Demo_Pack/csv ./docs/Ferrero_Demo_Pack/csv
COPY docs/Ferrero_Demo_Pack/documents_full_meta ./docs/Ferrero_Demo_Pack/documents_full_meta
COPY data ./data

# data/records holds what users add (case changes, evidence files, follow-ups, the audit trail): docker-compose.yml
# mounts a named volume there, so it survives rebuilds. Created here so the volume starts owned by the app user.
RUN useradd --create-home --uid 10001 ferrero && mkdir -p /app/data/records && chown -R ferrero:ferrero /app/data
USER ferrero

EXPOSE 8000
# /api/public is the one endpoint that answers without signing in (everything else returns 401 to the health check).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/public', timeout=4)"]
# One process: conversations live in memory, so several workers would lose track of them.
CMD ["python", "-m", "ferrero.web", "--host", "0.0.0.0", "--port", "8000"]
