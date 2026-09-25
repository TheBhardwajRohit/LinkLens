# Official Playwright image: Ubuntu 24.04 with Chromium and its system libraries already installed.
# The tag must match the playwright version in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    HOME=/tmp

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Tests run inside the same image, against the same browser the real scans use.
FROM base AS test
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
USER pwuser
CMD ["python", "-m", "pytest", "-q"]

# Default target (last stage): the service itself.
FROM base AS runtime
USER pwuser
EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
