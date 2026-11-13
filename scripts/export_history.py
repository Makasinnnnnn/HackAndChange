"""Read-only anonymous historical scenario export. Never exports UserId or personal data."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import load_catalog  # noqa: E402


def snapshot(courses, catalog, version):
    allowed = {m.id for m in catalog if m.source_type == "course"}
    ids = sorted({"course:" + str(course) for course in courses} & allowed)
    if not ids:
        raise ValueError("No completed source courses match the current catalog")
    return {"catalog_version": version, "completed_material_ids": ids[:100]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="hac-audit-20261112")
    parser.add_argument("--case-index", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / ".private/history-case.json")
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to((ROOT / ".private").resolve()) or not 0 <= args.case_index <= 1000:
        raise SystemExit("Private output and bounded case index required")
    inspected = subprocess.run(["docker", "inspect", "--format", "{{json .Config.Labels}}", args.container], capture_output=True, check=True)
    labels = json.loads(inspected.stdout)
    if labels.get("project") != "hackandchange" or labels.get("purpose") != "private-data-audit":
        raise SystemExit("Dedicated audit container required")
    sql = f'''BEGIN READ ONLY; SET LOCAL statement_timeout='30s';
SELECT coalesce(json_agg(x.courses),'[]') FROM (
 SELECT array_agg(DISTINCT "CourseId"::text ORDER BY "CourseId"::text) courses
 FROM "CourseUserBindings" WHERE NOT "IsDeleted" AND "IsCompleted"
 GROUP BY "UserId" ORDER BY count(*) DESC, "UserId" OFFSET {args.case_index} LIMIT 1
) x; COMMIT;'''
    result = subprocess.run(["docker", "exec", "-i", args.container, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "hac_audit"], input=sql.encode(), capture_output=True, check=True)
    cases = json.loads(result.stdout)
    if not cases:
        raise SystemExit("No completed historical scenario")
    os.environ["CATALOG_MODE"] = "full"
    os.environ["CATALOG_PATH"] = str(ROOT / ".private/catalog.json")
    catalog, _, version = load_catalog()
    payload = snapshot(cases[0], catalog, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"completed_courses": len(payload["completed_material_ids"]), "catalog_version": version, "contains_source_user_id": False}))
