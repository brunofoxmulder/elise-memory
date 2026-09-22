ARG BUILD_FROM=alpine:3.22
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /src
RUN git clone https://github.com/ipiton/agent-memory-mcp.git . \
 && git checkout dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /agent-memory-mcp ./cmd/agent-memory-mcp

FROM $BUILD_FROM
RUN apk add --no-cache ca-certificates
COPY --from=builder /agent-memory-mcp /usr/local/bin/agent-memory-mcp
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
