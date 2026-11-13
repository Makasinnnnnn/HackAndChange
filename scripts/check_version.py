"""Reject inconsistent release metadata before packaging or publishing."""

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(tag=None):
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("VERSION must contain a semantic release version")
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    tree = ast.parse((ROOT / "backend/app/main.py").read_text(encoding="utf-8"))
    api_versions = [
        ast.literal_eval(keyword.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "FastAPI"
        for keyword in node.keywords
        if keyword.arg == "version"
    ]
    if api_versions != [version] or any(
        value != version for value in [package["version"], lock["version"], lock["packages"][""]["version"]]
    ):
        raise ValueError("VERSION, FastAPI, package.json and package-lock.json must agree")
    if tag is not None and tag != "v" + version:
        raise ValueError("Release tag must match VERSION")
    return {"status": "passed", "version": version}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    args = parser.parse_args()
    print(json.dumps(check(args.tag)))
