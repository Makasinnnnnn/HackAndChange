"""Import only allowed catalog metadata from the isolated organizer database.

Never queries lesson bodies, embed blocks, users, ratings, IPs or user events.
Both input evidence and generated catalog stay under .private/.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.models import Material  # noqa: E402

# Discriminants were verified against EntityId joins in the actual 62-table dump.
SOURCES = {
    "Articles": ("article", "8ede4179-0faf-407d-a4fc-1d94f9a63089"),
    "Courses": ("course", "8b440b1a-00c3-423a-9bae-3376475eb203"),
    "Documents": ("document", "da1ad865-8605-4ab1-9f6c-4489a26fbc35"),
    "Podcasts": ("podcast", "142c23e2-bf71-4a73-b12e-6b1b5e4d47cc"),
    "Webinars": ("webinar", "ece4acf3-5dd3-47b9-9f08-99c0d6203cc7"),
    "Glossary": ("glossary", None),
    "CalculatorPages": ("calculator", None),
}
# Only these two route patterns have independent public source confirmation.
CONFIRMED_PATHS = {"article": "articles", "course": "courses"}
ALLOWED_COLUMNS = {"Id", "Title", "Description", "Url", "Duration", "Cost", "IsClosed", "IsPublic", "TypeId"}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.blocked += 1
        elif tag in {"p", "div", "br", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.blocked:
            self.blocked -= 1

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)


def plain(value: str | None, limit=400) -> str:
    parser = PlainText()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()[:limit]


def source_url(value: str, kind: str) -> str | None:
    value = (value or "").strip()
    parsed = urlparse(value)
    observed_path = ROOT / ".private/source-links.json"
    if observed_path.is_file():
        observed = json.loads(observed_path.read_text(encoding="utf-8"))
        if value in observed:
            return observed[value]
    if parsed.scheme in {"https", "http"} and parsed.hostname == "kurs.alfabank.ru" and not parsed.username:
        return value
    if kind in CONFIRMED_PATHS and re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        return "https://kurs.alfabank.ru/" + CONFIRMED_PATHS[kind] + "/" + value + "/"
    # Never invent a route for a source type whose path is not established.
    return None


def import_catalog(container: str) -> list[Material]:
    inspected = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", container],
        capture_output=True,
        check=True,
    )
    labels = json.loads(inspected.stdout)
    if labels.get("project") != "hackandchange" or labels.get("purpose") != "private-data-audit":
        raise ValueError("Refusing to read a database without the dedicated audit labels")

    def query(sql):
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "psql",
                "-X",
                "-qAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-d",
                "hac_audit",
            ],
            input=("BEGIN READ ONLY; SET LOCAL statement_timeout='30s'; " + sql + "; COMMIT;").encode(),
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    columns = query(
        "SELECT json_agg(row_to_json(c)) FROM (SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public') c"
    )
    settings = query("""SELECT coalesce(json_agg(row_to_json(s)), '[]') FROM (
      SELECT c."EntityId"::text entity_id,c."EntityTypeId"::text entity_type,t."Title" access_label,
      st."Title" status,
      ARRAY(SELECT x."Title"::text FROM "ContentSettingsTopics" b JOIN "Topics" x ON x."Id"=b."TopicId"
            WHERE b."ContentSettingsId"=c."Id" AND NOT x."IsDeleted" AND x."IsPublic") topics,
      ARRAY(SELECT x."Title"::text FROM "ContentSettingsIndustries" b JOIN "Industries" x ON x."Id"=b."IndustryId"
            WHERE b."ContentSettingsId"=c."Id" AND NOT x."IsDeleted") industries,
      ARRAY(SELECT x."Title"::text FROM "ContentSettingsTags" b JOIN "Tags" x ON x."Id"=b."TagId"
            WHERE b."ContentSettingsId"=c."Id" AND NOT x."IsDeleted") tags
      FROM "ContentSettings" c LEFT JOIN "CourseTypes" t ON t."Id"=c."TypeId"
      LEFT JOIN "Statuses" st ON st."Id"=c."StatusId" WHERE NOT c."IsDeleted") s""")
    mapped = {}
    for setting in settings:
        key = (setting["entity_id"], setting["entity_type"])
        if key in mapped:
            raise ValueError("Ambiguous polymorphic catalog metadata")
        mapped[key] = setting
    types = query('SELECT json_object_agg("Id"::text,"Title"::text) FROM "CourseTypes" WHERE NOT "IsDeleted"')
    course_subs = set(
        query('SELECT coalesce(json_agg(DISTINCT "CourseId"::text),\'[]\') FROM "CourseSubscriptions"')
    )
    podcast_subs = set(
        query('SELECT coalesce(json_agg(DISTINCT "PodcastId"::text),\'[]\') FROM "PodcastSubscriptions"')
    )
    tariff_costs = query(
        'SELECT coalesce(json_object_agg(k,cost),\'{}\') FROM (SELECT "CourseId"::text k,min("Cost") cost FROM "CourseTariffBindings" WHERE "Cost">0 GROUP BY 1) x'
    )
    output = []
    for table, (kind, entity_type) in SOURCES.items():
        available = {c["column_name"] for c in columns if c["table_name"] == table}
        required = {"Id", "Title", "Description", "Url", "StatusId", "IsDeleted"}
        if not required <= available:
            raise ValueError("Source schema differs from the audited version: " + table)
        fields = ",".join('m."' + c + '"' for c in sorted(available & ALLOWED_COLUMNS))
        rows = query(f'''SELECT coalesce(json_agg(row_to_json(r)), '[]') FROM (
          SELECT {fields} FROM "{table}" m JOIN "Statuses" s ON s."Id"=m."StatusId"
          WHERE NOT m."IsDeleted" AND s."Title"='Опубликовано') r''')
        for row in rows:
            if row.get("IsClosed"):
                continue
            meta = mapped.get((row["Id"], entity_type), {})
            if meta and meta["status"] != "Опубликовано":
                continue
            labels = {types.get(row.get("TypeId")), meta.get("access_label")}
            cost = row.get("Cost") or (tariff_costs.get(row["Id"]) if kind == "course" else None)
            if "Платный" in labels or (cost is not None and cost > 0):
                access = "paid"
            elif "По подписке" in labels or row["Id"] in (
                course_subs if kind == "course" else podcast_subs if kind == "podcast" else set()
            ):
                access = "subscription"
            elif kind == "article" and row.get("IsPublic") is not True:
                access = "unknown"
            elif "Открытый" in labels or (kind == "article" and row.get("IsPublic") is True):
                access = "free"
            else:
                access = "unknown"
            output.append(
                Material(
                    id=kind + ":" + row["Id"],
                    source_type=kind,
                    title=plain(row["Title"], 250),
                    description=plain(row.get("Description"), 180 if access != "free" else 400),
                    topics=meta.get("topics", []),
                    industries=meta.get("industries", []),
                    tags=meta.get("tags", []),
                    access=access,
                    price=cost,
                    duration=plain(row.get("Duration"), 80) or None,
                    url=source_url(row.get("Url"), kind),
                    provenance="organizer",
                    stage=[],
                    difficulty=None,
                )
            )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="hac-audit-20261112")
    parser.add_argument("--output", type=Path, default=ROOT / ".private/catalog.json")
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to((ROOT / ".private").resolve()):
        raise SystemExit("Real catalog output must remain in .private/")
    materials = import_catalog(args.container)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([m.model_dump() for m in materials], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "materials": len(materials),
                "types": dict(Counter(m.source_type for m in materials)),
                "access": dict(Counter(m.access for m in materials)),
                "without_confirmed_url": sum(m.url is None for m in materials),
            }
        )
    )
