"""Read-only, aggregate-only audit of the isolated organizer database.

Never prints table rows, user identifiers, HTML, lesson bodies or URLs.
The complete local report is restricted to .private/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, check=True)
    return result.stdout.decode("utf-8").strip()


def identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def audit(container: str) -> dict:
    labels = json.loads(command("docker", "inspect", "--format", "{{json .Config.Labels}}", container))
    if labels.get("project") != "hackandchange" or labels.get("purpose") != "private-data-audit":
        raise ValueError("Refusing to inspect a container without the dedicated audit labels")

    def query(sql: str):
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "psql",
                "-X",
                "-q",
                "-A",
                "-t",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-d",
                "hac_audit",
            ],
            input=("BEGIN READ ONLY; SET LOCAL statement_timeout = '30s'; " + sql + "; COMMIT;").encode(),
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout.decode("utf-8"))

    columns = query("""SELECT coalesce(json_agg(row_to_json(c)), '[]') FROM (
      SELECT table_name, column_name, data_type, is_nullable
      FROM information_schema.columns WHERE table_schema='public'
      ORDER BY table_name, ordinal_position) c""")
    tables = query("""SELECT json_agg(table_name ORDER BY table_name)
      FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'""")
    by_table = {name: [c for c in columns if c["table_name"] == name] for name in tables}
    profiles = {}
    for name in tables:
        table = "public." + identifier(name)
        pieces = ["count(*) AS rows"]
        for col in by_table[name]:
            field = col["column_name"]
            quoted = identifier(field)
            if field in {"Title", "Description", "Url", "Duration", "Published", "Cost", "StatusId"}:
                pieces.append(f"count(*) FILTER (WHERE {quoted} IS NULL) AS {identifier(field + '_null')}")
            if field in {"IsDeleted", "IsClosed", "IsPublic", "IsPaid", "IsCompleted", "IsTrial"}:
                pieces.append(f"count(*) FILTER (WHERE {quoted} IS TRUE) AS {identifier(field + '_true')}")
        profiles[name] = query(f"SELECT row_to_json(p) FROM (SELECT {', '.join(pieces)} FROM {table}) p")
    constraints = query("""SELECT coalesce(json_agg(row_to_json(c)), '[]') FROM (
      SELECT conrelid::regclass::text AS source, conname AS name, contype AS type,
        pg_get_constraintdef(oid) AS definition
      FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conrelid, conname) c""")
    statuses = query(
        'SELECT json_agg(row_to_json(s)) FROM (SELECT "Id", "Title" FROM public."Statuses" ORDER BY "Title") s'
    )
    return {
        "audited_at": datetime.now(UTC).isoformat(),
        "server": query("SELECT json_build_object('version', version())"),
        "extensions": query("SELECT json_agg(extname ORDER BY extname) FROM pg_extension"),
        "table_count": len(tables),
        "total_rows": sum(p["rows"] for p in profiles.values()),
        "columns": columns,
        "constraints": constraints,
        "tables": profiles,
        "statuses": statuses,
        "archive_sha256": hashlib.file_digest(
            (ROOT / ".private/alfa_course_hackathon.backup").open("rb"), "sha256"
        ).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="hac-audit-20261112")
    parser.add_argument("--output", type=Path, default=ROOT / ".private/data-audit.json")
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to((ROOT / ".private").resolve()):
        raise SystemExit("Audit output must remain under .private/")
    report = audit(args.container)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"table_count": report["table_count"], "total_rows": report["total_rows"], "output": str(target)}
        )
    )
