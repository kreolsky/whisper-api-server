FROM nvidia/cuda:12.8.1-cudnn9-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv \
    ffmpeg sox libmagic1 \
    git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv $VIRTUAL_ENV

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код монтируется через volume — rebuild не нужен при изменениях

EXPOSE 5042

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5042/health')" || exit 1

CMD ["python", "server.py", "--config", "config.json"]
