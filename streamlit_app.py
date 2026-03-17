import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "app"

for p in (str(ROOT_DIR), str(APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import app.main  # noqa: F401
except Exception as exc:
    print("Failed to import app.main during startup:", repr(exc))
    raise
