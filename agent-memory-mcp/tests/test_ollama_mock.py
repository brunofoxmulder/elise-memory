"""Check Ollama selection using only fictional data and a local fake server."""
import json
import os
import pathlib
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

events = []


class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        events.append((self.path, payload.get("model")))
        data = json.dumps({"embedding": [1.0] + [0.0] * 1023}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *_args):
        pass


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def call(method, params, ident):
    data = json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params}).encode()
    req = urllib.request.Request("http://127.0.0.1:18080/mcp", data=data, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=15) as res:
        raw = res.read().decode()
    if raw.lstrip().startswith("data:"):
        raw = "\n".join(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
    result = json.loads(raw)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(str(result))
    return result["result"]


fake = ThreadingHTTPServer(("127.0.0.1", 18183), FakeOllama)
threading.Thread(target=fake.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp); data = root / "data"; config = root / "config"
    data.mkdir(); config.mkdir()
    (data / "options.json").write_text(json.dumps({"embeddings_enabled": True, "embedding_provider": "ollama", "ollama_url": "http://127.0.0.1:18183", "openai_api_key": "UNUSED_TEST_KEY", "rag_enabled": False, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False}))
    try:
        docker("run", "-d", "--name", "amem-ollama-mock", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "OPENAI_BASE_URL=http://127.0.0.1:18183/v1", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
        for _ in range(60):
            try:
                call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "fake-ollama", "version": "1"}}, 1)
                break
            except (OSError, ValueError):
                time.sleep(1)
        else:
            raise RuntimeError("MCP server did not start")
        call("tools/call", {"name": "memory", "arguments": {"action": "store", "title": "Fait fictif", "content": "La serre fictive ouvre a sept heures.", "type": "semantic"}}, 2)
        assert events and all(path == "/api/embeddings" and model == "bge-m3:latest" for path, model in events), events
        stats = json.dumps(call("tools/call", {"name": "memory", "arguments": {"action": "stats"}}, 3))
        assert "ollama:" in stats.lower(), stats
        print("Candidate used simulated Ollama in local-only mode")
    finally:
        docker("rm", "-f", "amem-ollama-mock", check=False)
        fake.shutdown()
