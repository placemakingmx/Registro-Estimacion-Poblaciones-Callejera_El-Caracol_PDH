import sys
import traceback
from pathlib import Path

print("BOOT: app.py starting...")

ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "app"

for p in (str(ROOT_DIR), str(APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import app.main  # noqa: F401
    print("BOOT: app.main imported OK")
except Exception as exc:
    print("BOOT FAILED:", repr(exc))
    print(traceback.format_exc())
    raise
