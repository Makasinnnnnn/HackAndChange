from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .models import Material


def load_catalog(path: Path | None = None) -> tuple[list[Material], str, str]:
    mode = os.getenv("CATALOG_MODE", "demo")
    if mode not in {"demo", "full"}:
        raise ValueError("CATALOG_MODE must be demo or full")
    source = path or Path(os.getenv("CATALOG_PATH", str(Path(__file__).parents[1] / "data" / "demo.json")))
    raw = source.read_bytes()
    materials = [Material.model_validate(item) for item in json.loads(raw)]
    expected = "synthetic" if mode == "demo" else "organizer"
    if any(m.provenance != expected for m in materials):
        raise ValueError("Catalog provenance does not match selected mode")
    ids = [m.id for m in materials]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate catalog identifiers")
    # Deterministic deduplication: URLs, then normalized titles. No unpublished content.
    seen = set()
    output = []
    for item in sorted(materials, key=lambda m: m.id):
        if not item.published:
            continue
        key = (item.url or item.title.casefold().strip()).rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output, mode, hashlib.sha256(raw).hexdigest()[:16]
