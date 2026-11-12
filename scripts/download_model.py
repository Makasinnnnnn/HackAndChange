"""Download public weights with the HF CLI, then seal a local checksum manifest."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Xenova/multilingual-e5-small"
REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
FILES = ["onnx/model_quantized.onnx", "tokenizer.json", "tokenizer_config.json", "config.json"]


if __name__ == "__main__":
    target = ROOT / ".private/models/e5"
    target.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HF_HUB_DISABLE_TELEMETRY": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1"}
    subprocess.run(
        [
            "hf",
            "download",
            MODEL,
            *FILES,
            "--revision",
            REVISION,
            "--local-dir",
            str(target),
            "--max-workers",
            "2",
        ],
        check=True,
        env=env,
    )
    checksums = {}
    for relative in FILES:
        with (target / relative).open("rb") as stream:
            checksums[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
    (target / "manifest.json").write_text(
        json.dumps({"model": MODEL, "revision": REVISION, "sha256": checksums}, indent=2), encoding="utf-8"
    )
    print("Public model downloaded and local checksums recorded. No catalog data uploaded.")
