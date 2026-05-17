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

EXPOSE 5000
CMD ["/app/toolbox", "--tools-file", "/app/tools.yaml", "--address", "0.0.0.0", "--port", "5000"]
