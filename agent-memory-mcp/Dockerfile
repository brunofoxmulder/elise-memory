ARG BUILD_FROM=alpine:3.22
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /src
# Base amont : cba46cf (main, 2026-11-18). Remplace dc404e4 (2026-09-22), qui
# n'est pas sur la ligne main et précède T155/T191 — le texte historique des
# révisions et la lecture temporelle dont dépend l'historique des connaissances.
RUN git clone https://github.com/ipiton/agent-memory-mcp.git . \
 && git checkout cba46cf
# Verrous d'environnement : fournisseur d'embedding verrouillé (aucune bascule
# silencieuse vers un autre modèle) et hermes-agent reconnu comme client de
# codage — sans quoi la base v0.18+ classerait nos sessions en « chat » et
# arrêterait l'extraction d'ingénierie.
COPY provider-client-lock.patch /tmp/provider-client-lock.patch
RUN git apply --check /tmp/provider-client-lock.patch && git apply /tmp/provider-client-lock.patch
# CH-REVIEWQ-20261118 / DEC-REVIEWQ-001 pièce 1 : les fiches de revue ne sont
# plus des cibles de consolidation.
COPY review-queue-piece1.patch /tmp/review-queue-piece1.patch
RUN git apply --check /tmp/review-queue-piece1.patch && git apply /tmp/review-queue-piece1.patch
# Historique et temporalité (C1-C7) : archivage par défaut, fenêtres de
# validité, remplacement transactionnel, as_of gradué, historique lisible.
COPY history-temporal.patch /tmp/history-temporal.patch
RUN git apply --check /tmp/history-temporal.patch && git apply /tmp/history-temporal.patch
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /agent-memory-mcp ./cmd/agent-memory-mcp
FROM $BUILD_FROM
RUN apk add --no-cache ca-certificates jq
COPY --from=builder /agent-memory-mcp /usr/local/bin/agent-memory-mcp
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
