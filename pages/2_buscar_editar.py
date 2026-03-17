from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent.parent / "app" / "pages" / "2_buscar_editar.py"),
    run_name="__main__",
)
