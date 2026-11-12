"""Deux clients MCP simulés sur une base jetable, sans accès à HA."""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.request

URL = "http://127.0.0.1:18183/mcp"
NAME = "amem-shared-test"

def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def call(client, method, params, number):
    body = json.dumps({"jsonrpc": "2.0", "id": number, "method": method, "params": params}).encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode()
    if raw.lstrip().startswith("data:"):
        raw = "\n".join(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
    result = json.loads(raw)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(f"{client}: MCP error: {result}")
    return result["result"]

def tool(client, action, args, number):
    return call(client, "tools/call", {"name": "memory", "arguments": {"action": action, **args}}, number)

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    data, config = root / "data", root / "config"
    data.mkdir(); config.mkdir()
    (data / "options.json").write_text(json.dumps({"rag_enabled": False, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False}))
    try:
        docker("run", "-d", "--name", NAME, "--user", f"{os.getuid()}:{os.getgid()}", "-p", "127.0.0.1:18183:18080", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
        for attempt in range(60):
            try:
                call("hermes-simule", "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "hermes-simule", "version": "1"}}, 1)
                break
            except (OSError, ValueError):
                time.sleep(1)
        else:
            raise RuntimeError("server did not start")
        call("assist-simule", "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "assist-simule", "version": "1"}}, 2)
        created = tool("hermes-simule", "store", {"title": "Test partage fictif", "content": "lilas-fictif-108", "type": "semantic", "context": "test-partage"}, 3)
        match = re.search(r"(?m)^- ID:\\s*(\\S+)", created["content"][0]["text"])
        if not match:
            raise RuntimeError("store response missing ID")
        memory_id = match.group(1)
        listed = json.dumps(tool("assist-simule", "list", {"type": "all", "limit": 100}, 4))
        assert memory_id in listed and "lilas-fictif-108" in listed
        tool("assist-simule", "update", {"id": memory_id, "content": "lilas-fictif-109"}, 5)
        listed = json.dumps(tool("hermes-simule", "list", {"type": "all", "limit": 100}, 6))
        assert memory_id in listed and "lilas-fictif-109" in listed and "lilas-fictif-108" not in listed
        tool("hermes-simule", "delete", {"id": memory_id}, 7)
        listed = json.dumps(tool("assist-simule", "list", {"type": "all", "limit": 100}, 8))
        assert memory_id not in listed and "lilas-fictif-109" not in listed
        print("Fictional memory shared, updated and deleted between independent simulated clients")
    finally:
        docker("rm", "-f", NAME, check=False)
