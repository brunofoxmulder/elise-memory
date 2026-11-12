"""Reproduce startup migration using only fictional data and a fake API."""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = "http://127.0.0.1:18080/mcp"
events = []


class Embeddings(BaseHTTPRequestHandler):
    def do_POST(self):
        p = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        events.append(p.get("input"))
        inp = p.get("input")
        n = len(inp) if isinstance(inp, list) else 1
        vec = [1.0] + [0.0] * 1023
        out = json.dumps({"object": "list", "data": [{"object": "embedding", "index": i, "embedding": vec} for i in range(n)], "model": "text-embedding-3-small", "usage": {"prompt_tokens": 3, "total_tokens": 3}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log_message(self, *_args):
        pass


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def call(method, params, ident):
    body = json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=15) as res:
        raw = res.read().decode()
    if raw.lstrip().startswith("data:"):
        raw = "\n".join(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
    result = json.loads(raw)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(f"MCP error: {result}")
    return result["result"]


def tool(action, args, ident):
    return call("tools/call", {"name": "memory", "arguments": {"action": action, **args}}, ident)


def start(data, config):
    docker("run", "-d", "--name", "amem-reembed", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "OPENAI_BASE_URL=http://127.0.0.1:18183/v1", "-v", f"{data}:/data", "-v", f"{config}:/config", "agent-memory-candidate")
    for _ in range(60):
        try:
            call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "startup-test", "version": "1"}}, 1)
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError("MCP server failed to start")


fake = ThreadingHTTPServer(("127.0.0.1", 18183), Embeddings)
threading.Thread(target=fake.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp); data = root / "data"; config = root / "config"
    data.mkdir(); config.mkdir()
    options = {"rag_enabled": False, "rag_auto_index": False, "rag_file_watcher": False, "stats_enabled": False, "session_tracking_enabled": False}
    (data / "options.json").write_text(json.dumps(options))
    try:
        start(data, config)
        ids = []
        for i in range(2):
            result = tool("store", {"title": f"Fictif {i}", "content": f"Fait imaginaire {i}", "type": "semantic"}, 2 + i)
            m = re.search(r"(?m)^- ID:\s*(\S+)", result["content"][0]["text"])
            assert m, result
            ids.append(m.group(1))
        stats_before = json.dumps(tool("stats", {}, 4))
        assert "Without an embedding" in stats_before, stats_before
        docker("stop", "amem-reembed"); docker("rm", "amem-reembed")
        options["openai_api_key"] = "TEST_KEY_NOT_A_SECRET"
        options["embedding_api_url"] = "http://127.0.0.1:18183/v1"
        options["embeddings_enabled"] = False
        (data / "options.json").write_text(json.dumps(options))
        start(data, config)
        time.sleep(3)
        stats_disabled = json.dumps(tool("stats", {}, 5))
        assert "Without an embedding" in stats_disabled and not events, (stats_disabled, events)
        docker("stop", "amem-reembed"); docker("rm", "amem-reembed")
        options["embeddings_enabled"] = True
        (data / "options.json").write_text(json.dumps(options))
        start(data, config)
        for i in range(30):
            stats = json.dumps(tool("stats", {}, 10 + i))
            if "Without an embedding" not in stats and "openai:" in stats.lower():
                break
            time.sleep(1)
        else:
            raise AssertionError(f"Automatic startup reembed not observed: {stats}, API calls={len(events)}")
        listing = json.dumps(tool("list", {"type": "all", "limit": 100}, 45))
        assert all(x in listing for x in ids), listing
        assert len(events) >= 3, events
        print("Startup automatically vectorized two pre-existing fictional memories; their IDs remain present")
    finally:
        docker("rm", "-f", "amem-reembed", check=False)
        fake.shutdown()
