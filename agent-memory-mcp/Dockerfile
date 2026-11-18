ARG BUILD_FROM=alpine:3.22
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /src
RUN git clone https://github.com/ipiton/agent-memory-mcp.git . \
 && git checkout dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b
COPY provider-lock.patch /tmp/provider-lock.patch
RUN git apply --check /tmp/provider-lock.patch && git apply /tmp/provider-lock.patch
# CH-REVIEWQ-20261118 / DEC-REVIEWQ-001 piece 1: review-queue cards must not be
# consolidation targets. Applied after provider-lock.patch, which touches other
# files; the two patches are independent.
COPY review-queue-piece1.patch /tmp/review-queue-piece1.patch
RUN git apply --check /tmp/review-queue-piece1.patch && git apply /tmp/review-queue-piece1.patch
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /agent-memory-mcp ./cmd/agent-memory-mcp
FROM $BUILD_FROM
RUN apk add --no-cache ca-certificates jq
COPY --from=builder /agent-memory-mcp /usr/local/bin/agent-memory-mcp
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
