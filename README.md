# Marion Holvoet — CV

Live at **[marionholvoet.github.io/CV](https://marionholvoet.github.io/CV/)**

---

## Overview

Single-file bilingual CV (English / French) generated from a LaTeX source.

**Architecture:**

![Architecture diagram](./resources/Live-CV-Arch.jpg)

| File | Role |
|---|---|
| `CV_Marion_Holvoet.tex` | **Source of truth** — edit this to update the CV |
| `tex_watch.py` | Converts the TeX source to `index.html` automatically on save |
| `index.html` | Generated HTML — do not edit by hand |
| `main.go` | Minimal Go web server for self-hosted deployment |
| `scripts/pre-push` | Git pre-push hook — auto-translates and regenerates `index.html` before every push |
| `scripts/auto_translate.py` | DeepL-powered translator — syncs FR translations in `tex_watch.py` |
| `resources/photo.jpg` | Profile photo |

---

## Editing the CV

Only edit `CV_Marion_Holvoet.tex`. Run the watcher to auto-regenerate `index.html`:

```bash
# One-time regeneration
python tex_watch.py --once

# Watch mode — regenerates index.html every time the .tex file is saved
python tex_watch.py
```

Requires Python 3.9+ and `watchdog`:

```bash
pip install watchdog
```

---

## Git hooks

A `pre-push` hook is provided in `scripts/` that automatically:
1. Runs `auto_translate.py` to sync any new/changed English bullets to French via Google Translate (free, no API key)
2. Regenerates `index.html` from the TeX source
3. Commits any updated files before the push

**Install (Linux / macOS / Git Bash on Windows):**
```bash
cp scripts/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

**Install (PowerShell on Windows):**
```powershell
Copy-Item scripts/pre-push .git/hooks/pre-push
```

---

## Auto-translation (Google Translate)

French translations are cached in `tex_watch.py`. When you update the LaTeX source,
run the translator to sync only the new/changed entries:

```bash
# Translate missing entries only
python tex_watch.py --translate

# Retranslate everything from scratch
python tex_watch.py --translate-force
```

**Setup (free, no account or API key required):**
```bash
pip install deep-translator
```

The pre-push hook runs translation automatically on every push.

---

## GitHub Pages deployment

GitHub Pages is configured to serve from the **`main` branch, root (`/`)**.

To publish an update:

```bash
python tex_watch.py --once   # regenerate index.html from the .tex
git add CV_Marion_Holvoet.tex index.html
git commit -m "your message"
git push
```

GitHub Pages will automatically redeploy at `https://marionholvoet.github.io/CV/`.

> **Note:** `index.html` references `resources/photo.jpg` for the profile photo.
> Make sure that file is committed and present in the repo.

---

## PDF download / LinkedIn in-app browser

The **PDF** button calls `window.print()` to trigger the browser's save-to-PDF dialog.

LinkedIn (and some other apps) open links in a built-in WebView that blocks `window.print()`. In that case a banner appears at the bottom of the page:

> *"To save as PDF, **open in browser ↗**"*

Tapping the link opens the page URL in the system browser (Safari / Chrome), from where the user can print/save normally. The banner is dismissed with the "Got it" button.

---

## Self-hosted deployment (Go server)

The Go server exposes the CV at `/marion` and handles a GitHub webhook at `/exit`
for graceful remote restarts. When the webhook fires, the server exits; `run_server.sh`
then pulls the latest code, rebuilds, and restarts automatically.

**First-time setup on the server:**
```bash
cd src/resources
export GITHUB_WEBHOOK_SECRET=your_secret
nohup bash scripts/run_server.sh > server.log 2>&1 &
```

**Manual one-shot build (no auto-restart):**
```bash
go build -buildvcs=false -o main main.go
./main   # starts on :12345
```

Set the `GITHUB_WEBHOOK_SECRET` environment variable to validate webhook calls.

---

## PDF download

The CV includes a **PDF** button in the top-right corner that triggers the browser
print dialog. Select *Save as PDF* to download. Colors, margins, and layout are
optimised for print and match the LaTeX PDF output.
