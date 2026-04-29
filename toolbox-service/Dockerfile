FROM golang:1.21 as downloader
ARG VERSION=0.23.0
RUN curl -O https://storage.googleapis.com/genai-toolbox/v${VERSION}/linux/amd64/toolbox && \
    chmod +x toolbox

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=downloader /go/toolbox /toolbox
COPY tools.yaml /tools.yaml
EXPOSE 5000
CMD ["/toolbox", "--tools-file", "/tools.yaml", "--address", "0.0.0.0", "--port", "5000"]
