"""Record a public release locally for manual submission; does not submit or freeze Git."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def snapshot(ref: str) -> dict:
    if not ref.startswith("v") or any(c not in "v0123456789." for c in ref):
        raise ValueError("Use an existing version tag such as v1.2.1")
    commit = git("rev-parse", "--verify", f"refs/tags/{ref}^{{commit}}").decode().strip()
    version = git("show", f"{commit}:VERSION").decode().strip()
    if ref != f"v{version}":
        raise ValueError("Tag and VERSION disagree")
    minor = ".".join(version.split(".")[:2])
    artifacts = {}
    for suffix in ("pdf", "pptx"):
        path = f"output/presentation/alfa-route-{minor}.{suffix}"
        content = git("show", f"{commit}:{path}")
        artifacts[path] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    return {
        "prepared_at": datetime.now(UTC).isoformat(),
        "submitted": False,
        "version": version,
        "tag": ref,
        "commit": commit,
        "release_url": f"https://github.com/Makasinnnnnn/HackAndChange/releases/tag/{ref}",
        "artifacts": artifacts,
        "note": "Preparation only. Owner submits manually. After submission freeze main and use another branch.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="Existing published version tag")
    args = parser.parse_args()
    try:
        record = snapshot(args.ref)
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Cannot prepare release snapshot: {error}") from error
    target = ROOT / ".private/submission" / f"{args.ref}-{record['commit'][:12]}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"Prepared {target.relative_to(ROOT)}; nothing submitted, main not frozen.")
