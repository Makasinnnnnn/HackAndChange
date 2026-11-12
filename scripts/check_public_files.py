"""Inspect tracked and non-ignored files without printing any matched secret."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "GitHub credential": re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,}"),
    "API credential": re.compile(rb"sk-[A-Za-z0-9_-]{40,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def inspect(relative: str) -> list[str]:
    path = ROOT / relative
    problems = []
    if not path.is_file():
        return problems
    data = path.read_bytes()
    if (
        path.suffix in {".backup", ".dump", ".sql", ".sqlite", ".db", ".pem", ".key"}
        or ".private" in path.parts
    ):
        problems.append("private data or key file")
    if data.startswith(b"PGDMP"):
        problems.append("PostgreSQL archive signature")
    for name, pattern in PATTERNS.items():
        if pattern.search(data):
            problems.append(name)
    if path.suffix == ".json":
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list) and any(
                isinstance(v, dict) and v.get("provenance") == "organizer" for v in parsed
            ):
                problems.append("organizer-derived catalog")
        except (ValueError, UnicodeError):
            pass
    return problems


if __name__ == "__main__":
    paths = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    failures = {p: issues for p in paths if p and (issues := inspect(p))}
    if failures:
        print(json.dumps({"status": "failed", "files": failures}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(
        json.dumps(
            {
                "status": "passed",
                "files_checked": len([p for p in paths if p]),
                "scope": "tracked and non-ignored files; signatures and known credential patterns, not a complete security guarantee",
            }
        )
    )
