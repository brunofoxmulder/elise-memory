ARG BUILD_FROM=alpine:3.22
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /src
RUN git clone https://github.com/ipiton/agent-memory-mcp.git . \
 && git checkout dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b
COPY provider-lock.patch /tmp/provider-lock.patch
RUN git apply --check /tmp/provider-lock.patch && git apply /tmp/provider-lock.patch
COPY review-queue-filter.patch /tmp/review-queue-filter.patch
RUN git apply --check /tmp/review-queue-filter.patch \
 && git apply /tmp/review-queue-filter.patch
COPY tests/sessionclose_review_queue_test.go /src/internal/sessionclose/review_queue_regression_test.go
RUN go test ./internal/sessionclose -run '^TestPlanActionsExcludesPendingReviewQueue -trimpath -ldflags="-s -w" -o /agent-memory-mcp ./cmd/agent-memory-mcp
FROM $BUILD_FROM
RUN apk add --no-cache ca-certificates jq
COPY --from=builder /agent-memory-mcp /usr/local/bin/agent-memory-mcp
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
 -count=1
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /agent-memory-mcp ./cmd/agent-memory-mcp
FROM $BUILD_FROM
RUN apk add --no-cache ca-certificates jq
COPY --from=builder /agent-memory-mcp /usr/local/bin/agent-memory-mcp
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
