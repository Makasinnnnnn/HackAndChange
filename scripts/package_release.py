"""Package exactly a committed public tree. Organizer data and local runtimes are excluded."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT.parent / "output/hackandchange/alfa-route-1.1.0.zip"
    )
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        raise SystemExit("Output exists; choose another filename to preserve the prior artifact")
    subprocess.run(["git", "diff", "--exit-code", "HEAD"], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([sys.executable, "scripts/check_public_files.py"], cwd=ROOT, check=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "archive", "--format=zip", "--output", str(target), "HEAD"], cwd=ROOT, check=True)
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        forbidden = {".private", ".venv", "node_modules", ".git"}
        for name in names:
            if any(part in forbidden for part in Path(name).parts) or name.endswith(
                (".backup", ".dump", ".onnx", ".safetensors", ".pem", ".key")
            ):
                raise SystemExit("Unexpected private file in archive: " + name)
        assert "README.md" in names and "compose.yaml" in names
        assert "output/presentation/alfa-route-1.1.pdf" in names
        demo = json.loads(archive.read("backend/data/demo.json"))
        assert all(item["provenance"] == "synthetic" for item in demo)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(digest + "  " + target.name + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"archive": str(target), "entries": len(names), "sha256": digest, "bytes": target.stat().st_size}
        )
    )
