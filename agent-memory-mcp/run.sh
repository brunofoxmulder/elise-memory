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
export MCP_ROOT=/config/memory-documents MCP_INDEX_DIRS=.
export MCP_RAG_ENABLED="$(jq -r '.rag_enabled // false' "$OPTIONS")"
export MCP_RAG_AUTO_INDEX="$(jq -r '.rag_auto_index // false' "$OPTIONS")"
export MCP_RAG_FILE_WATCHER="$(jq -r '.rag_file_watcher // false' "$OPTIONS")"
export MCP_STATS_ENABLED="$(jq -r '.stats_enabled // false' "$OPTIONS")"

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
EMBEDDINGS_ENABLED="$(jq -r '.embeddings_enabled // false' "$OPTIONS")"
if [ "$EMBEDDINGS_ENABLED" = true ]; then
  OPENAI_API_KEY="$(jq -r '.openai_api_key // empty' "$OPTIONS")"
  if [ -z "$OPENAI_API_KEY" ]; then
    echo 'Une clé API OpenAI est nécessaire pour activer les embeddings.' >&2
    exit 1
  fi
  export OPENAI_API_KEY OPENAI_EMBEDDING_MODEL=text-embedding-3-small
  export MCP_EMBEDDING_DIMENSION=1024
fi
unset JINA_API_KEY
echo "Agent Memory MCP : démarrage"
exec /usr/local/bin/agent-memory-mcp
