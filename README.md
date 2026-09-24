# unlost

Search your computer by describing what you remember.

> "that invoice I sent in March" · "the photo of my WAEC certificate" · "the slides from last week's meeting"

unlost finds the file even when it's called `IMG_4821.jpg` or `document(3).pdf`, because it searches what's
*inside* your files: text in PDFs, Word, PowerPoint and Excel files, and text read from screenshots, photos
and scanned documents (OCR). You can also ask questions across your files ("How much did I pay for rent last
year?") and get an answer that cites the source file. An optional Organize view suggests clear names and
folders for messy downloads, and every change can be undone.

## How it works

```
Electron (React + TypeScript)                Python sidecar (FastAPI, 127.0.0.1 + per-launch token)
┌──────────────────────────────┐   HTTP    ┌───────────────────────────────────────────────────────┐
│ Search · Ask · Organize      │ ────────▶ │ indexer   walk folders → extract → chunk → embed      │
│ Settings / onboarding        │  SSE for  │           watchdog keeps the index fresh              │
│ main: spawns sidecar,        │  answers  │ extract   pypdf, docx2txt, python-pptx, openpyxl,     │
│ keychain-encrypted Groq key, │           │           Tesseract OCR for images and scanned PDFs   │
│ opens files (only inside     │           │ search    embeddings (bge-small, on-device) + SQLite  │
│ indexed folders)             │           │           FTS5 + filename match, fused with RRF,      │
└──────────────────────────────┘           │           boosted by parsed dates ("in March") and    │
                                           │           file types ("photo", "pdf")                 │
                                           │ qa        LangChain prompt → ChatGroq, cited [n]      │
                                           │ organize  LangChain structured output (or on-device  │
                                           │           rules), safe apply with undo log            │
                                           └───────────────────────────────────────────────────────┘
```

- **Private by default.** Indexing, OCR, embeddings and search all run on your computer. Nothing leaves it
  unless you add a Groq API key; then only the passages relevant to a question (or the first ~500
  characters of files you ask to organize, or a voice recording) are sent to Groq.
- **Free LLM.** Answers and smart organizing use [Groq](https://console.groq.com)'s free tier through LangChain's
  `ChatGroq`. The default model is `openai/gpt-oss-120b`; Settings also offers GPT-OSS 20B, Llama 3.3 70B and
  Llama 3.1 8B. The free tier is rate-limited (e.g. 30 requests and 8K tokens per minute for GPT-OSS). If you
  hit it, unlost says so; wait a minute or switch to Llama 3.1 8B, which has higher limits.
- **Photos with no text** ("beach sunset") can be found with the optional on-device CLIP model (Settings →
  "Recognise what's in photos", ~600 MB download).
- **Voice search** is transcribed by Groq's free Whisper (`whisper-large-v3-turbo`), or on-device with the optional faster-whisper install.

## Setup

Requirements: Node 20+, Python 3.11+, and [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
for screenshots and scans (auto-detected, or set the path in Settings).

```bash
npm install
npm run sidecar:setup        # creates sidecar/.venv and installs Python deps
npm run dev                  # launches the app (the sidecar starts automatically)
```

Get a free Groq API key (no card needed) at <https://console.groq.com/keys>, then paste it into
**Settings → Groq API key** in the app. The key is encrypted with your OS keychain. Search works without it;
the key turns on Ask, smart Organize suggestions and voice search.

Optional on-device voice (no Groq key needed, ~150 MB):

```bash
node scripts/py.mjs -m pip install -r sidecar/requirements-voice.txt
```

On first run unlost downloads the ~70 MB embedding model into its data folder.

## Using it

- **Ctrl/Cmd+Shift+Space** opens unlost from anywhere. **Ctrl/Cmd+K** focuses search.
- Type what you remember; results update as you type. **↑/↓** to move, **Enter** opens, **Ctrl+Enter** shows it in its folder.
- Press **Tab** (or pick **Ask**) to ask a question instead. Citation numbers link to the source files.
- **Organize** → choose a folder → **Suggest names** → review and edit → **Rename & move**. **Undo** puts everything back.

## Testing it yourself

1. **Make a safe playground.** Don't point it at your real files yet:
   ```bash
   npm run demo:files          # writes ~/unlost-demo: a messy folder of PDFs, Word docs, screenshots, receipts
   ```
2. **Start the app:** `npm run dev`. In onboarding, untick the suggested folders, click **Add another folder**,
   pick `unlost-demo`, and start indexing. The status bar shows progress; the first run downloads the search model.
3. **Find** (works offline, no key). Try:
   - `the photo of my WAEC certificate` → `IMG_4821.png` (found by the text in the image)
   - `the PDF about Canadian study permits` → `document(3).pdf`
   - `that invoice I sent in March` → `Untitled.docx`
   - `screenshot of my flight booking` → `Screenshot 2026-05-02 091514.png`
   - `my electricity bill` → `download (2).docx`
4. **Add your Groq key** in Settings, then **Ask** (press Tab in the search box):
   - `How much did I pay for rent last year?` → should list the 12 receipts and total N3,000,000, with [n] citations
   - `When does my passport expire?` → 3 June 2031, citing `scan_0007.pdf`
5. **Organize:** choose the demo folder → **Suggest names** → review → **Rename & move** → then **Undo** in the
   toast and check the files are back.
6. **Voice:** with a Groq key, click the mic and say "the pdf about study permits".
7. When you're happy, add your real Downloads/Documents in Settings and remove the demo folder.

### On your own files

`npm run dev`, then in onboarding keep the folders you want (Downloads, Documents, Desktop, Pictures are
suggested) and start indexing. Or add them later under **Settings → Folders to search**.

Indexing runs in two passes, newest files first, and search works while it runs:

1. **Text, names and dates** of every file. Roughly 1 s per document on a laptop CPU; images take milliseconds.
2. **Text inside images and scanned PDFs (OCR)**, several at a time, in the background. Roughly 0.75 s per image.

On a folder of ~10,000 files (mostly images) expect about 45 minutes for pass 1 and 1.5 to 2 hours for
pass 2 the first time. After that only new and changed files are processed, and the folder watcher picks
up new downloads within seconds. The index takes roughly 0.3 to 0.6 GB for that many files. It lives in
`%APPDATA%\unlost\data` (Windows) or `~/Library/Application Support/unlost/data` (macOS); delete that
folder to start over.

Organize only renames and moves files after you click **Rename & move**, never overwrites anything, and
**Undo** restores the last batch.

Automated tests (no key needed; Groq calls are faked):

```bash
npm run sidecar:test         # 41 tests: parsing, extraction + OCR, ranking, organize, API, Groq wiring
npm run typecheck
```

## Development

```bash
npm run typecheck
```

The sidecar can be run on its own: `cd sidecar && .venv/Scripts/python -m unlost --port 8765`
(set `UNLOST_TOKEN` and `UNLOST_DATA_DIR`). Setting `UNLOST_USER_DATA` makes the Electron app use a throwaway
profile, which is useful for demos and automated runs.

### Packaging

```bash
node scripts/py.mjs -m pip install pyinstaller
npm run dist                 # electron-vite build → PyInstaller sidecar → electron-builder installer
```

## Troubleshooting

- **"Python sidecar not set up"**: run `npm run sidecar:setup`.
- **Electron prints `bad option` or behaves like Node**: `ELECTRON_RUN_AS_NODE` is set in your environment
  (some editors set it). Unset it before `npm run dev`.
- **Model download fails on Windows**: the data folder path is too long for Windows' 260-character limit. Use
  a shorter `UNLOST_USER_DATA`, or enable long paths in Windows.
- **Screenshots aren't found by their text**: Settings shows whether Tesseract was found; set its path there.
