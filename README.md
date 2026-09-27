# unlost

Search your computer by describing what you remember: *"that invoice I sent in March"*, *"the photo of my
WAEC certificate"*.

unlost searches what's inside your files (PDFs, Office documents, and text in screenshots and scans via OCR),
so it finds `IMG_4821.jpg` or `document(3).pdf` without you knowing the name. You can also ask questions
across your files and get answers that cite their sources, and tidy up messy folders with undoable
rename suggestions.

## How it works

An Electron + React app talks to a local Python sidecar (FastAPI) that indexes your folders, runs OCR with
Tesseract, embeds text on-device (bge-small) and ranks results with SQLite FTS5 plus vector search.

Indexing and search run entirely on your machine. If you add a [Groq](https://console.groq.com) API key
(free tier), Ask, smart Organize and voice search are turned on, and only the relevant snippets are sent to Groq.

## Setup

Requires Node 20+, Python 3.11+ and [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).

```bash
npm install
npm run sidecar:setup   # creates sidecar/.venv and installs Python deps
npm run dev
```

Optionally paste a free Groq key into **Settings**. It's stored encrypted with your OS keychain.

To try it on sample data first, run `npm run demo:files` and pick `~/unlost-demo` during onboarding.

## Usage

- **Ctrl/Cmd+Shift+Space** opens unlost from anywhere; **Ctrl/Cmd+K** focuses search.
- **Enter** opens a result, **Ctrl+Enter** shows it in its folder.
- **Tab** switches to Ask mode.
- **Organize** → pick a folder → review suggestions → **Rename & move**. **Undo** reverts the batch.

The first index of a large folder takes a while (OCR runs as a second background pass), but search works
as soon as it starts. The index lives in `%APPDATA%\unlost\data` or `~/Library/Application Support/unlost/data`.

## Development

```bash
npm run sidecar:test    # Python tests (Groq calls are faked)
npm run typecheck
npm run dist            # build the installer (needs: node scripts/py.mjs -m pip install pyinstaller)
```

## Troubleshooting

- **Electron prints `bad option`**: unset `ELECTRON_RUN_AS_NODE` before `npm run dev`.
- **Model download fails on Windows**: the path exceeds 260 characters; enable long paths or set a shorter `UNLOST_USER_DATA`.
- **Screenshots aren't found by their text**: check that Settings detects Tesseract, or set its path there.
