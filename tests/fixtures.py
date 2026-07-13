"""Load committed API response cassettes for offline tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CASSETTES_DIR = Path(__file__).resolve().parent / "fixtures" / "cassettes"


def load_cassette(name: str) -> Any:
    """Load a JSON cassette by filename (with or without ``.json``)."""
    path = CASSETTES_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not path.is_file():
        raise FileNotFoundError(f"Missing cassette: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
