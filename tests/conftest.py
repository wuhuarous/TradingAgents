"""Pytest defaults for deterministic local runs."""
import os


os.environ.setdefault("SKIP_NETWORK", "1")
