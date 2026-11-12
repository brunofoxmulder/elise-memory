"""Exercise candidate document indexing with synthetic files and a fake API."""
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
OLD = "VALEUR_FICTIVE_7162"
NEW = "VALEUR_FICTIVE_9834"
WATCHED = "VALEUR_FICTIVE_4628"
requests = []


class FakeAPI(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append((self.path, payload.get("model"), payload.get("dimensions")))
        inputs = payload.get("input")
        inputs = inputs if isinstance(inputs, list) else [inputs]
        vector = [0.0] * 1024
        vector[0] = 1.0
        result = json.dumps({"object": "list", "data": [{"object": "embedding", "index": i, "embedding": vector} for i in range(len(inputs))], "model": "text-embedding-3-small", "usage": {"prompt_tokens": 3, "total_tokens": 3}}).encode()
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
    with urllib.request.urlopen(req, timeout=30) as response:
        text = response.read().decode()
    if text.lstrip().startswith("data:"):
        text = "\n".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    result = json.loads(text)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(f"MCP error: {result}")
    return result["result"]


def tool(name, arguments, request_id):
    return call("tools/call", {"name": name, "arguments": arguments}, request_id)


def start(data, config):
    docker("run", "-d", "--name", "amem-rag-mock", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "OPENAI_BASE_URL=http://127.0.0.1:18183/v1", "-e", "MCP_RAG_WATCH_INTERVAL=2s", "-e", "MCP_RAG_DEBOUNCE=1s", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
    for _ in range(60):
        try:
            call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "rag-mock-test", "version": "1"}}, 1)
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError("MCP server did not start")


fake = ThreadingHTTPServer(("127.0.0.1", 18183), FakeAPI)
threading.Thread(target=fake.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    data, config = root / "data", root / "config"
    data.mkdir(); config.mkdir()
    docs = config / "memory-documents"
    docs.mkdir()
    source = docs / "serre.md"
    source.write_text(f"# Serre fictive\nL'arrosage de la serre utilise {OLD}.\n")
    (data / "options.json").write_text(json.dumps({"openai_api_key": "TEST_KEY_NOT_A_SECRET", "embeddings_enabled": True, "embedding_api_url": "http://127.0.0.1:18183/v1", "rag_enabled": True, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False}))
    try:
        start(data, config)
        tool("index_documents", {}, 2)
        first = json.dumps(tool("search", {"action": "semantic", "query": "arrosage serre", "limit": 5}, 3))
        assert OLD in first, f"initial document not found: {first}"
        source.write_text(f"# Serre fictive\nL'arrosage de la serre utilise {NEW}.\n")
        tool("index_documents", {}, 4)
        second = json.dumps(tool("search", {"action": "semantic", "query": "arrosage serre", "limit": 5}, 5))
        assert NEW in second and OLD not in second, f"document was not refreshed: {second}"
        docker("stop", "amem-rag-mock")
        docker("rm", "amem-rag-mock")
        (data / "options.json").write_text(json.dumps({"openai_api_key": "TEST_KEY_NOT_A_SECRET", "embeddings_enabled": True, "embedding_api_url": "http://127.0.0.1:18183/v1", "rag_enabled": True, "rag_auto_index": True, "rag_file_watcher": True, "stats_enabled": False}))
        start(data, config)
        time.sleep(3)  # Allow the watcher to establish its initial baseline.
        source.write_text(f"# Serre fictive\nL'arrosage de la serre utilise {WATCHED}.\n")
        for i in range(20):
            time.sleep(2)
            current = json.dumps(tool("search", {"action": "semantic", "query": "arrosage serre", "limit": 5}, 10 + i))
            if WATCHED in current and NEW not in current:
                break
        else:
            raise AssertionError(f"automatic watcher did not refresh document: {current}")
        assert requests and all(p == "/v1/embeddings" and m == "text-embedding-3-small" and d == 1024 for p, m, d in requests), requests
        print("Candidate indexed and refreshed the synthetic document manually and automatically using a local fake API")
    finally:
        docker("rm", "-f", "amem-rag-mock", check=False)
        fake.shutdown()
