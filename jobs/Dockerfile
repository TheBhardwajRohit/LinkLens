# The jobs image: the API's code plus the data jobs. Build from the repo root:
#   docker compose --profile jobs build jobs
FROM python:3.12-slim AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /src/api/requirements.txt
COPY jobs/requirements.txt /src/jobs/requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r /src/jobs/requirements.txt


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/repo/api:/repo \
    LISTS_DIR=/data/lists \
    GEOIP_DIR=/data/geoip \
    FEATURES_DIR=/data/ml \
    HF_HOME=/tmp/hf

# libgomp is LightGBM's threading library.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
COPY api/requirements.txt api/requirements.txt
COPY jobs/requirements.txt jobs/requirements.txt
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index --find-links=/wheels -r jobs/requirements.txt

COPY api/app api/app
COPY jobs jobs

RUN useradd --create-home --uid 10001 jobuser \
    && mkdir -p /data/lists /data/geoip /data/ml && chown jobuser /data/lists /data/geoip /data/ml
USER jobuser
CMD ["python", "-m", "jobs.seed_phreshphish", "--help"]
