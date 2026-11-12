"""Check candidate-to-embedding integration with a local fake API only."""
import json
import os
import pathlib
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MCP = "http://127.0.0.1:18080/mcp"
events = []


class FakeEmbeddingAPI(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        events.append((self.path, payload.get("model"), payload.get("dimensions")))
        vector = [0.0] * 1024
        vector[0] = 1.0
        result = json.dumps({"object": "list", "data": [{"object": "embedding", "index": 0, "embedding": vector}], "model": "text-embedding-3-small", "usage": {"prompt_tokens": 3, "total_tokens": 3}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)

    def log_message(self, *_args):
        pass


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def call(method, params, request_id):
    payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}).encode()
    req = urllib.request.Request(MCP, data=payload, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=15) as res:
        text = res.read().decode()
    if text.lstrip().startswith("data:"):
        text = "\n".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    result = json.loads(text)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(f"MCP error: {result}")
    return result["result"]


fake = ThreadingHTTPServer(("127.0.0.1", 18183), FakeEmbeddingAPI)
thread = threading.Thread(target=fake.serve_forever, daemon=True)
thread.start()
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    data, config = root / "data", root / "config"
    data.mkdir(); config.mkdir()
    (data / "options.json").write_text(json.dumps({"openai_api_key": "TEST_KEY_NOT_A_SECRET", "embeddings_enabled": True, "embedding_api_url": "http://127.0.0.1:18183/v1", "rag_enabled": False, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False}))
    try:
        docker("run", "-d", "--name", "amem-embedding-mock", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "OPENAI_BASE_URL=http://127.0.0.1:18183/v1", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
        for _ in range(60):
            try:
                call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "fake-api-test", "version": "1"}}, 1)
                break
            except (OSError, ValueError):
                time.sleep(1)
        else:
            raise RuntimeError("MCP server did not start")
        call("tools/call", {"name": "memory", "arguments": {"action": "store", "title": "Fait fictif", "content": "La serre imaginaire ouvre a sept heures.", "type": "semantic"}}, 2)
        assert events, "candidate did not call the simulated embeddings API"
        assert all(path == "/v1/embeddings" and model == "text-embedding-3-small" and dims == 1024 for path, model, dims in events), events
        stats = call("tools/call", {"name": "memory", "arguments": {"action": "stats"}}, 3)
        assert "openai:" in json.dumps(stats).lower(), "no OpenAI embedding reported in memory stats"
        print("Candidate stored a synthetic memory using the simulated 1024-dimensional API")
    finally:
        docker("rm", "-f", "amem-embedding-mock", check=False)
        fake.shutdown()
