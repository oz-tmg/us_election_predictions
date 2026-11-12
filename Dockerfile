# Dashboard image for Cloud Run. One image serves both audiences; EP_DASH_TIER and the
# bundle roots are set per service at deploy time (docs/deployment-plan.md).
# No data is baked in: bundles are read from Cloud Storage at startup (.dockerignore
# excludes data/, reports/ and everything else not needed to run the app).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[dashboard]" && useradd --uid 10001 --no-create-home app
USER app

ENV PORT=8080
# One worker (the bundle cache is per process), threads for concurrent callbacks;
# --timeout 0 lets Cloud Run's own request timeout govern.
CMD exec gunicorn --bind ":${PORT}" --workers 1 --threads 8 --timeout 0 \
    "election_prediction.dashboard.wsgi:create_server()"
