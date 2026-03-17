import sys
import traceback
from pathlib import Path

print("BOOT: streamlit_app.py starting...")

ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "app"

for p in (str(ROOT_DIR), str(APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import streamlit as st  # fuerza import temprano (y valida entorno)
    print("BOOT: streamlit imported OK, version:", getattr(st, "__version__", "unknown"))

    import app.main  # noqa: F401
    print("BOOT: app.main imported OK")
except Exception as exc:
    tb = traceback.format_exc()
    print("BOOT FAILED:", repr(exc))
    print(tb)

    # Intento de persistir el error para inspección (si el entorno lo permite)
    try:
        (ROOT_DIR / "startup_error.txt").write_text(tb, encoding="utf-8")
        print("BOOT: wrote startup_error.txt")
    except Exception as write_exc:
        print("BOOT: could not write startup_error.txt:", repr(write_exc))

    raise
