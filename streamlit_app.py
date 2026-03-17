import sys
from pathlib import Path

# Ensure the `app/` package root is importable when Streamlit Cloud runs from repo root.
APP_DIR = Path(__file__).resolve().parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Execute the Streamlit app entrypoint.
# Importing runs the top-level Streamlit code in app/main.py.
import main  # noqa: F401
