FROM python:3.12-alpine
WORKDIR /opt/vscoffline

# Install build dependencies for watchdog and other packages
RUN apk --no-cache add \
    libc-dev \
    binutils \
    gcc \
    python3-dev \
    musl-dev \
    linux-headers

COPY ./vscoffline/ ./

RUN mkdir /artifacts/

RUN pip install --no-cache-dir -r vscgallery/requirements.txt

ENV ARTIFACTS=/artifacts
ENV BIND=0.0.0.0:8080
ENV TIMEOUT=300
ENV WORKERS=4
ENV THREADS=8
ENV MAX_REQUESTS=1000
ENV MAX_REQUESTS_JITTER=50
ENV SSLARGS="--certfile=/opt/vscoffline/vscgallery/ssl/vscoffline.crt --keyfile=/opt/vscoffline/vscgallery/ssl/vscoffline.key"

CMD gunicorn  \
    $SSLARGS \
    --bind $BIND \
    --access-logfile - \
    --timeout $TIMEOUT \
    --workers $WORKERS \
    --threads $THREADS \
    --max-requests $MAX_REQUESTS \
    --max-requests-jitter $MAX_REQUESTS_JITTER \
    --worker-class gthread \
    --preload \
    server:application
