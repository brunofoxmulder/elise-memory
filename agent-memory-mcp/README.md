# Agent Memory MCP — test minimal

But unique : tester Agent Memory MCP avec Home Assistant puis Élise Live, sans modifier Élise Live.

Configuration :
- HTTP MCP : port 18080
- mémoire : activée
- tools groupés : activés
- RAG/documents : désactivés
- stockage persistant : /config/memory-data
- aucune configuration d'embeddings ajoutée
- aucune modification d'Élise Live

Endpoint de test :
http://homeassistant.local:18080/mcp

Si Home Assistant ne peut pas utiliser directement cet endpoint MCP, le test est considéré comme KO et l'App peut être désinstallée.
