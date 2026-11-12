"""Migration de l'image 0.1.1 vers la candidate avec données jetables."""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.request

PORT = 18184
URL = f"http://127.0.0.1:{PORT}/mcp"
MARKER = "migration-fictive-cerisier-421"

def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def call(method, params, number):
    body = json.dumps({"jsonrpc": "2.0", "id": number, "method": method, "params": params}).encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode()
    if raw.lstrip().startswith("data:"):
        raw = "\n".join(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
    result = json.loads(raw)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(f"MCP error: {result}")
    return result["result"]

def start(name, image, data, config):
    docker("run", "-d", "--name", name, "--user", f"{os.getuid()}:{os.getgid()}", "-p", f"127.0.0.1:{PORT}:18080", "-v", f"{data}:/data", "-v", f"{config}:/config", image)
    for _ in range(60):
        try:
            call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "upgrade-test", "version": "1"}}, 1)
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError(f"{name} did not start")

def tool(action, args, number):
    return call("tools/call", {"name": "memory", "arguments": {"action": action, **args}}, number)

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    data, config = root / "data", root / "config"
    data.mkdir(); config.mkdir()
    (data / "options.json").write_text(json.dumps({"embeddings_enabled": False, "rag_enabled": False, "session_tracking_enabled": False}))
    try:
        start("amem-upgrade-old", "agent-memory-previous", data, config)
        created = tool("store", {"title": "Migration fictive", "content": MARKER, "type": "semantic", "context": "migration-test"}, 2)
        match = re.search(r"(?m)^- ID:\s*(\S+)", created["content"][0]["text"])
        if not match:
            raise RuntimeError("store response missing ID")
        memory_id = match.group(1)
        docker("stop", "amem-upgrade-old")
        docker("rm", "amem-upgrade-old")
        start("amem-upgrade-new", "agent-memory-candidate", data, config)
        result = json.dumps(tool("list", {"type": "all", "limit": 100}, 3), ensure_ascii=False)
        assert memory_id in result and MARKER in result, "memory missing or changed after upgrade"
        print("Synthetic memory and ID survived upgrade on persistent volume")
    finally:
        docker("rm", "-f", "amem-upgrade-old", check=False)
        docker("rm", "-f", "amem-upgrade-new", check=False)
