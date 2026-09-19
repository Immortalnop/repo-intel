# syntax=docker/dockerfile:1
# Multi-stage build; runs as a non-root user.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# git is required at runtime (GitPython/PyDriller shell out to it)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# deps first for layer caching
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY . .
RUN pip install --no-cache-dir . -c constraints.txt

# non-root
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
# Mount a repository at /repo and it will be analyzed.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

ENTRYPOINT ["repo-intel"]
CMD ["serve", "/repo", "--host", "0.0.0.0", "--port", "8000"]
