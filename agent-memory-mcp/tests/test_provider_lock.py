"""Verify disabled and selected providers never fall back to Ollama."""
import json
import os
import pathlib
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

calls = []


class Endpoint(BaseHTTPRequestHandler):
    def do_POST(self):
        calls.append((self.server.server_port, self.path))
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.server.server_port == 18183:
            data = b'{"error":"simulated outage"}'
            self.send_response(503)
        else:
            data = json.dumps({"embedding": [1.0] + [0.0] * 1023}).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *_args):
        pass


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def call(method, params, ident):
    payload = json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params}).encode()
    req = urllib.request.Request("http://127.0.0.1:18080/mcp", data=payload, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read().decode()
    if raw.lstrip().startswith("data:"):
        raw = "\n".join(x[5:].strip() for x in raw.splitlines() if x.startswith("data:"))
    result = json.loads(raw)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(str(result))
    return result["result"]


def start(data, config):
    docker("run", "-d", "--name", "amem-provider-lock", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "MCP_SESSION_TRACKING_ENABLED=false", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
    for _ in range(60):
        try:
            call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "lock-test", "version": "1"}}, 1)
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError("Server did not start")


servers = [ThreadingHTTPServer(("127.0.0.1", p), Endpoint) for p in (11434, 18183)]
for server in servers:
    threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp); data = root / "data"; config = root / "config"
    data.mkdir(); config.mkdir()
    options = {"openai_api_key": "TEST_KEY_NOT_A_SECRET", "embedding_api_url": "http://127.0.0.1:18183/v1", "embeddings_enabled": False, "rag_enabled": False, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False}
    (data / "options.json").write_text(json.dumps(options))
    try:
        start(data, config)
        call("tools/call", {"name": "memory", "arguments": {"action": "store", "title": "Test fictif", "content": "La serre fictive ferme a 19 heures.", "type": "semantic"}}, 2)
        time.sleep(2)
        assert not calls, f"disabled provider unexpectedly called: {calls}"
        docker("stop", "amem-provider-lock"); docker("rm", "amem-provider-lock")
        options["embeddings_enabled"] = True
        (data / "options.json").write_text(json.dumps(options))
        start(data, config)
        time.sleep(5)
        call("tools/call", {"name": "memory", "arguments": {"action": "store", "title": "Second test", "content": "Un volet fictif reste ouvert.", "type": "semantic"}}, 3)
        assert any(p == 18183 for p, _ in calls), f"API was not attempted: {calls}"
        assert not any(p == 11434 for p, _ in calls), f"unexpected Ollama fallback: {calls}"
        print("Disabled mode made no calls; failing API did not fall back to local Ollama")
    finally:
        docker("rm", "-f", "amem-provider-lock", check=False)
        for server in servers:
            server.shutdown()
