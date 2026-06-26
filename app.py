import runpy
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))
runpy.run_path(str(SRC_DIR / "app.py"), run_name="__main__")
