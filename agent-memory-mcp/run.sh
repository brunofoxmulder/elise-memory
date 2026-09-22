#!/bin/sh
set -eu

mkdir -p /config/memory-data

export MCP_HTTP_MODE=http
export MCP_HTTP_HOST=0.0.0.0
export MCP_HTTP_PORT=18080
export MCP_HTTP_INSECURE_ALLOW_UNAUTHENTICATED=true
export MCP_MEMORY_ENABLED=true
export MCP_RAG_ENABLED=false
export MCP_TOOL_GROUPING=true
export MCP_DATA_PATH=/config/memory-data
export MCP_RAG_AUTO_INDEX=false
export MCP_RAG_FILE_WATCHER=false
export MCP_STATS_ENABLED=false

echo "Agent Memory MCP: http://homeassistant.local:18080/mcp"
echo "Memory ON - RAG OFF - grouped tools ON"
exec /usr/local/bin/agent-memory-mcp
