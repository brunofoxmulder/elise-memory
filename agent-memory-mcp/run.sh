#!/bin/sh
set -eu

OPTIONS=/data/options.json
test -r "$OPTIONS" || { echo 'Options indisponibles' >&2; exit 1; }
mkdir -p /config/memory-data/logs /config/memory-documents

export MCP_HTTP_MODE=http MCP_HTTP_HOST=0.0.0.0 MCP_HTTP_PORT=18080
# Compatibilité provisoire avec le client HA existant : accès non authentifié.
export MCP_HTTP_INSECURE_ALLOW_UNAUTHENTICATED=true
export MCP_MEMORY_ENABLED=true MCP_TOOL_GROUPING=true
export MCP_DATA_PATH=/config/memory-data
export MCP_LOG_PATH=/config/memory-data/logs/mcp-diagnostics.log
# Le dossier partagé est monté en lecture seule ; aucun document n'est créé.
case "$(jq -r '.rag_document_source // "app"' "$OPTIONS")" in
  app) export MCP_ROOT=/config/memory-documents ;;
  share)
    test -d /share/memory-documents || { echo 'Dossier /share/memory-documents introuvable.' >&2; exit 1; }
    export MCP_ROOT=/share/memory-documents ;;
  *) echo 'Source documentaire inconnue.' >&2; exit 1 ;;
esac
export MCP_INDEX_DIRS=.
export MCP_RAG_ENABLED="$(jq -r '.rag_enabled // false' "$OPTIONS")"
export MCP_RAG_AUTO_INDEX="$(jq -r '.rag_auto_index // false' "$OPTIONS")"
export MCP_RAG_FILE_WATCHER="$(jq -r '.rag_file_watcher // false' "$OPTIONS")"
export MCP_STATS_ENABLED="$(jq -r '.stats_enabled // false' "$OPTIONS")"
# Classement optionnel, sans cycle automatique de modification des souvenirs.
export MCP_SEDIMENT_ENABLED="$(jq -r '.sediment_enabled // false' "$OPTIONS")"
export MCP_SEDIMENT_SCHEDULE_INTERVAL=0

# Le moteur amont ne démarre la surveillance que si l'indexation auto est active.
if [ "$MCP_RAG_FILE_WATCHER" = true ] && [ "$MCP_RAG_AUTO_INDEX" != true ]; then
  echo 'La surveillance nécessite l’indexation automatique.' >&2
  exit 1
fi
if [ "$MCP_RAG_ENABLED" != true ] && { [ "$MCP_RAG_AUTO_INDEX" = true ] || [ "$MCP_RAG_FILE_WATCHER" = true ]; }; then
  echo 'L’indexation automatique et la surveillance nécessitent le RAG.' >&2
  exit 1
fi

# Le secret est fourni par Supervisor ; ne jamais l'afficher dans les journaux.
unset OPENAI_API_KEY
export MCP_EMBEDDING_PROVIDER_LOCK=none
EMBEDDINGS_ENABLED="$(jq -r '.embeddings_enabled // false' "$OPTIONS")"
if [ "$EMBEDDINGS_ENABLED" = true ]; then
  PROVIDER="$(jq -r '.embedding_provider // "openai_compatible"' "$OPTIONS")"
  DIMENSIONS="$(jq -r '.embedding_dimensions // 1024' "$OPTIONS")"
  case "$PROVIDER" in
    openai_compatible)
      OPENAI_API_KEY="$(jq -r '.openai_api_key // empty' "$OPTIONS")"
      if [ -z "$OPENAI_API_KEY" ]; then
        echo 'Une clé API est nécessaire pour le fournisseur compatible OpenAI.' >&2
        exit 1
      fi
      export OPENAI_API_KEY
      export OPENAI_BASE_URL="$(jq -r '.embedding_api_url // "https://api.openai.com/v1"' "$OPTIONS")"
      export OPENAI_EMBEDDING_MODEL="$(jq -r '.embedding_api_model // "text-embedding-3-small"' "$OPTIONS")"
      export MCP_EMBEDDING_MODE=auto
      export MCP_EMBEDDING_PROVIDER_LOCK=openai
      ;;
    ollama)
      export MCP_EMBEDDING_MODE=local-only
      export MCP_EMBEDDING_PROVIDER_LOCK=ollama
      export OLLAMA_BASE_URL="$(jq -r '.ollama_url // "http://127.0.0.1:11434"' "$OPTIONS")"
      export MCP_OLLAMA_EMBEDDING_MODEL="$(jq -r '.ollama_model // "bge-m3:latest"' "$OPTIONS")"
      ;;
    *) echo 'Fournisseur d’embeddings inconnu.' >&2; exit 1 ;;
  esac
  export MCP_EMBEDDING_DIMENSION="$DIMENSIONS"
fi
unset JINA_API_KEY
echo "Agent Memory MCP : démarrage"
exec /usr/local/bin/agent-memory-mcp
