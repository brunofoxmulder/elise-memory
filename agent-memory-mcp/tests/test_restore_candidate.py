"""Container-only recovery check with synthetic data; never touches HA."""
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request
import shutil

PORT = 18182
URL = f"http://127.0.0.1:{PORT}/mcp"
MARKER = "TEST_MEMOIRE_SAUGE_VIOLETTE_7184"


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


def start(name, data, config):
    docker("run", "-d", "--name", name, "-p", f"127.0.0.1:{PORT}:18080", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
    for _ in range(60):
        try:
            call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "restore-test", "version": "1"}}, 1)
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError("MCP server did not start")


def tool(action, args, number):
    return call("tools/call", {"name": "memory", "arguments": {"action": action, **args}}, number)


with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    data = root / "data"
    config = root / "config"
    restored = root / "restored"
    data.mkdir(); config.mkdir()
    (data / "options.json").write_text(json.dumps({"rag_enabled": False, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False}))
    try:
        start("amem-restore-source", data, config)
        created = tool("store", {"title": "Test sauvegarde fictif", "content": MARKER, "type": "semantic", "context": "test-isole"}, 2)
        text = created["content"][0]["text"]
        saved_id = json.loads(text)["id"]
        docker("stop", "amem-restore-source")
        docker("rm", "amem-restore-source")
        shutil.copytree(config, restored)
        start("amem-restore-copy", data, restored)
        results = tool("list", {"type": "all", "limit": 100}, 3)
        payload = json.dumps(results, ensure_ascii=False)
        assert saved_id in payload and MARKER in payload, "synthetic memory missing or changed after restoration"
        print("Synthetic memory and ID survived stop, copy, and independent restart")
    finally:
        docker("rm", "-f", "amem-restore-source", check=False)
        docker("rm", "-f", "amem-restore-copy", check=False)
