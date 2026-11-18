#!/usr/bin/env python3
"""Headline Hunter — tiny proxy backend.

Serves the two static pages (index.html, studio.html) plus the bundled PDF/DOCX
parsers in lib/, and exposes ONE endpoint — POST /draft — that holds the
Anthropic API key server-side. Visitors never need their own key.

Why a proxy at all: studio.html can already call Claude directly if a visitor
pastes their own key, but for a course/demo audience that's a friction wall.
This backend lets the page call a "Hosted (shared)" provider instead, keyed by
your single ANTHROPIC_API_KEY and (optionally) gated by one shared passcode.

Config is read from the environment — see .env.example. Run it with:

    uvicorn app:app --host 0.0.0.0 --port 8000      # production-ish
    python app.py                                   # convenience (same thing)

Then put Caddy (or any reverse proxy) in front for HTTPS. The app itself only
serves a whitelist of files, so .env / app.py / requirements.txt are never
exposed.
"""
import os
import time
from collections import defaultdict, deque

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

MODEL = os.environ.get("HH_MODEL", "claude-haiku-4-5")
ACCESS_KEY = os.environ.get("HH_ACCESS_KEY", "").strip()
MAX_INPUT_CHARS = int(os.environ.get("HH_MAX_INPUT_CHARS", "48000"))
MAX_OUTPUT_TOKENS = int(os.environ.get("HH_MAX_OUTPUT_TOKENS", "1500"))
RATE_LIMIT_PER_MIN = int(os.environ.get("HH_RATE_LIMIT_PER_MIN", "20"))

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES = {"index.html", "studio.html"}  # the only top-level files we serve

if not os.environ.get("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set — copy .env.example to .env and fill it in "
        "(or pass it via --env-file with Docker)."
    )

# AsyncAnthropic so the API call doesn't block the event loop.
client = anthropic.AsyncAnthropic()
app = FastAPI(title="Headline Hunter")

# --- tiny in-memory per-IP rate limiter (good enough for a low-volume demo) ---
_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Behind Caddy/nginx the real IP is in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    window = _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MIN:
        return True
    window.append(now)
    return False


@app.get("/healthz")
async def healthz():
    # max_input_chars lets the Studio trim the paper to whatever this server allows.
    return {"ok": True, "model": MODEL, "max_input_chars": MAX_INPUT_CHARS}


@app.post("/draft")
async def draft(request: Request):
    if ACCESS_KEY and request.headers.get("x-hh-access", "") != ACCESS_KEY:
        return JSONResponse(
            {"error": {"message": "Wrong or missing access passcode."}}, status_code=401
        )

    if _rate_limited(_client_ip(request)):
        return JSONResponse(
            {"error": {"message": "Too many requests — wait a minute and try again."}},
            status_code=429,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": {"message": "Invalid JSON body."}}, status_code=400)

    prompt = (body.get("prompt") or "").strip()
    system = (body.get("system") or "").strip()
    if not prompt:
        return JSONResponse({"error": {"message": "No prompt provided."}}, status_code=400)
    if len(prompt) > MAX_INPUT_CHARS:
        return JSONResponse(
            {"error": {"message": f"Input too long ({len(prompt)} chars; limit {MAX_INPUT_CHARS})."}},
            status_code=413,
        )

    max_tokens = min(int(body.get("max_tokens") or MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS)

    try:
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system or "You output only JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as e:
        return JSONResponse(
            {"error": {"message": f"AI provider error ({e.status_code})."}}, status_code=502
        )
    except anthropic.APIConnectionError:
        return JSONResponse(
            {"error": {"message": "Could not reach the AI provider."}}, status_code=502
        )

    text = "".join(b.text for b in msg.content if b.type == "text")
    return {"text": text}


# --- static serving (whitelisted) ------------------------------------------
# Defined AFTER the API routes so /draft and /healthz take precedence.
app.mount("/lib", StaticFiles(directory=os.path.join(STATIC_DIR, "lib")), name="lib")


@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "studio.html"))


@app.get("/{name}")
async def page(name: str):
    if name in PAGES:
        return FileResponse(os.path.join(STATIC_DIR, name))
    return JSONResponse({"error": {"message": "Not found"}}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
