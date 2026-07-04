# Headline Hunter 🎯

Two web forms that turn the Curtin Media Communications worksheets (*Headline Hunting* + *Key Messages*) into a fun, interactive tool for prepping research for media.

**Try it now:** [landing page](https://michael-borck.github.io/headline-hunter/) · [Studio (AI)](https://michael-borck.github.io/headline-hunter/app/studio.html) · [simple worksheet](https://michael-borck.github.io/headline-hunter/app/index.html)

## Three ways to run it

1. **Browser (GitHub Pages)** — the links above. Bring your own key (or use *Copy prompt*, no key at all). The "Hosted (shared)" provider isn't available there — the site is static, so the Studio detects that and defaults to BYOK.
2. **Self-hosted (Docker)** — you hold one `ANTHROPIC_API_KEY` in `.env` and your users need no key. See [Self-hosting the shared service](#self-hosting-the-shared-service-vps).
3. **Local** — clone and double-click `studio.html`, or `python3 serve.py` for env-var key detection.

The landing page and apps deploy to GitHub Pages automatically on every push to `main` (`.github/workflows/pages.yml` — landing at the root, apps under `/app/`).

## Two versions

| File | What it is | Needs |
|------|-----------|-------|
| **`index.html`** | The simple worksheet. Live newspaper preview, progress meter, copy/print, auto-save. | Just a browser — double-click it. |
| **`studio.html`** | Everything above **+ import a paper (PDF/DOCX/TXT) and let an AI draft your fields**. | A browser; an AI provider (below) only if you want AI drafting. |

Both work **fully offline** — the PDF/DOCX parsers are bundled in the `lib/` folder. The only thing that needs a network is AI drafting (and only to reach the provider you choose). Keep the `lib/` folder next to `studio.html`.

---

## Using AI drafting (`studio.html`)

1. Click **⚙️ Settings**, pick a provider, **Save**. (The hosted service is the default — no key needed.)
2. Click **📄 Import paper**, drop in your PDF/DOCX/TXT. Optionally set the **audience/outlet** and a **tone** (Plain / Warm / Formal / Playful) — both steer the whole draft.
3. Click **✨ Draft my brief with AI** — fields fill with editable drafts grounded in the paper (labelled *"AI draft — edit me"*).
4. **Pick your headline.** The AI offers 3–5 candidates under the headline field — tap one to use it (you can still edit), or hit **🔄 New ideas** to re-roll fresh ones in your chosen tone. *AI suggests, you confirm.*
5. Sharpen the rest, then **📄 Press release (PDF)** downloads a formatted, inverted-pyramid release (headline → significance → call to action) ready to send to Media Comms.

> The draft is **grounded in the paper's text** (first ~40k characters — a full abstract/intro/results, plenty on Haiku's 200K context) with a "don't invent findings" guardrail. It's still a synthesis, not a quote — have researchers sanity-check it, especially the *"Now what?"* call to action.

No AI key? Use **📋 Copy prompt** instead — it builds a ready-made prompt from your paper that you paste into Claude/ChatGPT yourself, then paste the answers back. Zero keys, zero cost.

### Providers
- **Hosted (shared)** — the default. Calls *this site's* own backend (`app.py`), which holds the API key server-side, so visitors need **no key**. If you set an access passcode (`HH_ACCESS_KEY`), paste it into the key box. See [Self-hosting the shared service](#self-hosting-the-shared-service-vps) below.
- **Ollama (local, free)** — install Ollama, run a model (`ollama run llama3.1`). If the browser blocks it, start Ollama with `OLLAMA_ORIGINS=* ollama serve`.
- **Claude (Anthropic)** — paste your own API key in Settings.
- **OpenAI-compatible** — OpenAI, Groq, Together, LM Studio, vLLM… set base URL + key + model.

Keys are stored only in your browser (localStorage) and sent only to the provider you choose.

### "Detect from environment" (optional)
A web page **cannot** read your shell's environment variables — browsers forbid it. To use the *Detect from environment* button, launch via the included helper, which reads the env for you:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY / OLLAMA_HOST
python3 serve.py
# then open http://localhost:8000/studio.html
```

Otherwise just paste your key into Settings manually — everything else works the same.

---

## Self-hosting the shared service (VPS)

`app.py` is a ~40-line proxy so a room full of people can use the AI drafting **without each needing an API key**. It serves the static pages and exposes one endpoint, `POST /draft`, that injects your server-side `ANTHROPIC_API_KEY`, calls a cheap model (Haiku by default), and returns the draft. It also enforces a per-IP rate limit, an input-size cap, and an optional shared passcode.

### 1. Configure
```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY, and optionally HH_ACCESS_KEY (a shared passcode)
```

### 2a. Run without Docker
```bash
pip install -r requirements.txt
python app.py            # or: uvicorn app:app --host 0.0.0.0 --port 8000
```

### 2b. Run with Docker
The image carries no secrets — they come from `.env` at runtime.
```bash
docker build -t headline-hunter .
docker run --rm -p 8000:8000 --env-file .env headline-hunter
# or, with the bundled compose file:
docker compose up -d --build
```

### 2c. Run from the prebuilt image — recommended for the VPS
A GitHub Actions workflow (`.github/workflows/docker.yml`) builds the image on every push to `main` and publishes it to GHCR as `ghcr.io/michael-borck/headline-hunter:latest`. On the VPS you never build — you just pull:

```bash
# one-time: create the .env (key + optional passcode)
cp .env.example .env && nano .env

# deploy / update — that's the whole loop
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` binds to `127.0.0.1:8000` (localhost only) so Caddy is the single public door.

**GHCR auth:** because the repo is private, the image package is private too. Either:
- make the package public — GitHub → repo → Packages → `headline-hunter` → Package settings → *Change visibility → Public* (the image carries no secrets), **or**
- log in on the VPS once with a PAT that has `read:packages`:
  ```bash
  echo "$GHCR_PAT" | docker login ghcr.io -u michael-borck --password-stdin
  ```

### 3. Put Caddy in front (runs separately, outside the container)
The app listens on `:8000`; point your existing Caddy at it for automatic HTTPS:
```caddy
hunter.example.edu {
    reverse_proxy localhost:8000
}
```

Then open `https://hunter.example.edu/` — the page defaults to the **Hosted (shared)** provider and works with no key. Visitors only enter the passcode if you set `HH_ACCESS_KEY`.

### Config (all via `.env`)
| Var | Default | What it does |
|-----|---------|--------------|
| `ANTHROPIC_API_KEY` | — | **Required.** Your key (the only real secret). |
| `HH_MODEL` | `claude-haiku-4-5` | Model for drafting. Bump to `claude-sonnet-4-6`/`claude-opus-4-8` for more polish. |
| `HH_ACCESS_KEY` | *(blank)* | Shared passcode. Blank = open to anyone who can reach it. |
| `HH_MAX_INPUT_CHARS` | `24000` | Reject pasted text longer than this. |
| `HH_MAX_OUTPUT_TOKENS` | `1500` | Cap the draft length. |
| `HH_RATE_LIMIT_PER_MIN` | `20` | Per-IP requests per minute. |
| `PORT` | `8000` | Port the app listens on. |

> Cost is tiny: a paper abstract → press-release draft on Haiku is a fraction of a cent. The rate limit + input cap keep abuse to a few cents even if the link leaks.

---

## Privacy
- Manual use: nothing leaves your machine.
- File text is extracted **in your browser**, never uploaded to us.
- AI drafting sends the paper text only to the provider you choose — your own machine (Ollama), the provider you keyed in, or **your** hosted backend (which forwards it to Anthropic).

---

## License

Released under the [MIT License](LICENSE) — © 2026 Michael Borck. Built for the Curtin University Media & Communications course.

### Third-party libraries
The PDF/DOCX parsers and the PDF generator are bundled in `lib/` and remain under their own licenses (their notices are preserved in the minified files):

| Library | Purpose | License |
|---------|---------|---------|
| [pdf.js](https://github.com/mozilla/pdf.js) | Extract text from PDFs in the browser | Apache-2.0 |
| [mammoth.js](https://github.com/mwilliamson/mammoth.js) | Extract text from DOCX in the browser | BSD-2-Clause |
| [jsPDF](https://github.com/parallax/jsPDF) | Generate the press-release PDF | MIT |
