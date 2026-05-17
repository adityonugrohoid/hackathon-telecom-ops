FROM golang:1.21 AS downloader
ARG VERSION=0.23.0
RUN curl -O https://storage.googleapis.com/genai-toolbox/v${VERSION}/linux/amd64/toolbox && \
    chmod +x toolbox

FROM debian:bookworm-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=downloader /go/toolbox /app/toolbox
COPY tools.yaml /app/tools.yaml
# tools.yaml declares `database: data/netpulse.sqlite` as a path relative to
# the working directory. scripts/deploy_toolbox.sh stages a freshly-built
# SQLite file into toolbox-service/data/ before this COPY runs.
COPY data/netpulse.sqlite /app/data/netpulse.sqlite

# Cloud Run injects PORT (default 8080) and expects the process to listen on
# it. Locally, scripts/run_toolbox_local.sh runs the binary directly and pins
# port 5000 for back-compat with telecom_ops/.env and TOOLBOX_URL conventions.
# Shell form so ${PORT} expands at runtime; defaults to 8080 if unset.
EXPOSE 8080
CMD exec /app/toolbox --tools-file /app/tools.yaml --address 0.0.0.0 --port "${PORT:-8080}"
