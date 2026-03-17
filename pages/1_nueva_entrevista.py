from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent.parent / "app" / "pages" / "1_nueva_entrevista.py"),
    run_name="__main__",
)
