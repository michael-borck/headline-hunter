#!/usr/bin/env python3
"""
Optional launcher for Headline Hunter Studio.

Why this exists: a web page CANNOT read your shell's environment variables on its
own (browsers sandbox that for security). This tiny local server reads them for you
and exposes them to the page's "Detect from environment" button.

Usage:
    python3 serve.py
then open the printed URL (http://localhost:8000/studio.html).

It only ever serves files from THIS folder and a /__env endpoint that returns a
short whitelist of AI keys found in your environment. Nothing leaves your machine.

Set keys before launching, e.g.:
    export ANTHROPIC_API_KEY=sk-ant-...
    export OPENAI_API_KEY=sk-...
    export OLLAMA_HOST=http://localhost:11434
    python3 serve.py
"""
import json
import os
from http.server import SimpleHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8000"))

# Only these env vars are ever exposed — add more here if you need them.
WHITELIST = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_HOST"]


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/__env":
            payload = {k: os.environ[k] for k in WHITELIST if os.environ.get(k)}
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def log_message(self, *args):  # keep the console quiet
        pass


if __name__ == "__main__":
    found = [k for k in WHITELIST if os.environ.get(k)]
    print("\n  Headline Hunter Studio")
    print("  ----------------------")
    print(f"  Serving:  http://localhost:{PORT}/studio.html")
    print(f"  Env keys detected: {', '.join(found) if found else 'none (set them with export ...)'}")
    print("  Press Ctrl+C to stop.\n")
    try:
        HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
