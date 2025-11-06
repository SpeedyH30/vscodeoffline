FROM python:3.12-alpine
WORKDIR /opt/vscoffline

COPY ./vscoffline/ ./

RUN mkdir /artifacts/

# Install build dependencies, pip packages, then remove build deps in same layer
RUN apk --no-cache add --virtual .build-deps \
    libc-dev \
    binutils \
    gcc \
    python3-dev \
    musl-dev \
    linux-headers \
    && pip install --no-cache-dir -r vscgallery/requirements.txt \
    && apk del .build-deps

ENV ARTIFACTS=/artifacts
ENV BIND=0.0.0.0:8080
ENV TIMEOUT=300
ENV WORKERS=4
ENV THREADS=8
ENV MAX_REQUESTS=1000
ENV MAX_REQUESTS_JITTER=50
ENV REFRESH_INTERVAL=3600
ENV PYTHONUNBUFFERED=1
ENV SSLARGS="--certfile=/opt/vscoffline/vscgallery/ssl/vscoffline.crt --keyfile=/opt/vscoffline/vscgallery/ssl/vscoffline.key"

CMD gunicorn  \
    $SSLARGS \
    --bind $BIND \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance \
    --timeout $TIMEOUT \
    --workers $WORKERS \
    --threads $THREADS \
    --max-requests $MAX_REQUESTS \
    --max-requests-jitter $MAX_REQUESTS_JITTER \
    --worker-class gthread \
    server:application
