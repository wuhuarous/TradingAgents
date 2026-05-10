"""Pytest defaults for deterministic local runs."""
import os
import sys
from pathlib import Path


os.environ.setdefault("SKIP_NETWORK", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
