"""Launcher: right-click this file in PyCharm -> Run 'run'.

It simply starts the Streamlit dashboard (same as typing
`streamlit run src/dashboard.py` in the terminal).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "src" / "dashboard.py")]
    sys.exit(subprocess.call(cmd, cwd=ROOT))
