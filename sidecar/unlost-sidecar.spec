# PyInstaller spec: builds sidecar/dist/unlost-sidecar/ (one-folder), which electron-builder ships as
# resources/sidecar. Models are not bundled; they download to the user's data folder on first run.
# Build with: npm run sidecar:bundle   (needs: pip install pyinstaller)
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []
for pkg in ("fastembed", "onnxruntime", "tokenizers", "langchain_anthropic", "langchain_core", "pypdfium2", "pptx"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("uvicorn") + ["unlost.server"]

a = Analysis(["run_sidecar.py"], pathex=["."], datas=datas, binaries=binaries, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="unlost-sidecar", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="unlost-sidecar")
