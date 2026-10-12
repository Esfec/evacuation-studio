"""Start the local studio from any working directory."""
import runpy
import sys
from pathlib import Path

sandbox = Path(__file__).resolve().parent / "02_可视化沙盒"
sys.path.insert(0, str(sandbox))
runpy.run_path(str(sandbox / "live_server.py"), run_name="__main__")

