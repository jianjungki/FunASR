ARG BASE_IMAGE=python:3.10-slim

FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FUNASR_MODEL=sensevoice \
    FUNASR_DEVICE=cpu \
    FUNASR_PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        libsndfile1 \
        python3 \
        python3-pip \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --upgrade pip \
    && if [ "${FUNASR_DEVICE}" = "cuda" ]; then \
        pip3 install --no-cache-dir \
            torch==2.7.1 \
            torchaudio==2.7.1 \
            --index-url https://download.pytorch.org/whl/cu129; \
    else \
        pip3 install --no-cache-dir \
            torch==2.7.1 \
            torchaudio==2.7.1; \
    fi \
    && pip3 install --no-cache-dir \
        funasr \
        fastapi \
        "uvicorn[standard]" \
        python-multipart

COPY server.py /app/server.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('FUNASR_PORT', '8000'), timeout=3).read()" || exit 1

CMD ["sh", "-c", "python3 server.py --host 0.0.0.0 --port ${FUNASR_PORT:-8000} --device ${FUNASR_DEVICE:-cpu} --model ${FUNASR_MODEL:-sensevoice}"]
