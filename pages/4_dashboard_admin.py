from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent.parent / "app" / "pages" / "4_dashboard_admin.py"),
    run_name="__main__",
)
