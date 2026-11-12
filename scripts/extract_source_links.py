"""Extract only canonical links from published free article blocks, entirely locally.

Does not output or save article bodies and never touches paid lessons or user tables.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
container = "hac-audit-20261112"
labels = json.loads(
    subprocess.run(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", container],
        capture_output=True,
        check=True,
    ).stdout
)
if labels.get("project") != "hackandchange" or labels.get("purpose") != "private-data-audit":
    raise SystemExit("Dedicated audit container required")
sql = """BEGIN READ ONLY; SET LOCAL statement_timeout='30s';
SELECT coalesce(json_agg(DISTINCT u.match[1]),'[]')
FROM "ArticleEmbedItems" e JOIN "Articles" a ON a."Id"=e."ArticleId"
JOIN "Statuses" s ON s."Id"=a."StatusId",
LATERAL regexp_matches(e."HtmlContent",'https?://kurs[.]alfabank[.]ru/[A-Za-z0-9_/-]+','g') u(match)
WHERE a."IsPublic" AND NOT a."IsClosed" AND NOT a."IsDeleted" AND s."Title"='Опубликовано'; COMMIT;"""
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
    input=sql.encode(),
    capture_output=True,
    check=True,
)
links = json.loads(result.stdout)
by_slug = defaultdict(set)
for url in links:
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) >= 2:
        by_slug[parts[-1]].add("https://kurs.alfabank.ru/" + parsed.path.strip("/") + "/")
mapped = {slug: next(iter(urls)) for slug, urls in by_slug.items() if len(urls) == 1}
(ROOT / ".private/source-links.json").write_text(
    json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({"links_observed": len(links), "unambiguous_slugs": len(mapped)}, ensure_ascii=False))
