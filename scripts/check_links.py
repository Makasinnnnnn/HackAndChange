"""Check source links gently. Reports stay private; TLS errors are not dead links."""
import argparse
import json
import ssl
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def check(url):
    if urlparse(url).hostname != "kurs.alfabank.ru":
        return {"status": "skipped_host"}
    try:
        request = Request(url, method="HEAD", headers={"User-Agent": "AlfaRoute-LinkCheck/0.1"})
        with urlopen(request, timeout=10) as response:
            return {"status": "reachable", "http_status": response.status, "final_url": response.url}
    except HTTPError as exc:
        return {"status": "http_error", "http_status": exc.code}
    except URLError as exc:
        tls = isinstance(exc.reason, ssl.SSLCertVerificationError)
        return {"status": "tls_unverified" if tls else "network_unverified"}
    except (TimeoutError, OSError):
        return {"status": "network_unverified"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / ".private/link-check.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".private").resolve()):
        raise SystemExit("Report must remain private")
    materials = json.loads((ROOT / ".private/catalog.json").read_text(encoding="utf-8"))
    urls = sorted({m["url"] for m in materials if m["url"]})
    results = {}
    consecutive_tls = 0
    for url in urls[:args.limit or None]:
        result = check(url)
        results[url] = result
        consecutive_tls = consecutive_tls + 1 if result["status"] == "tls_unverified" else 0
        if consecutive_tls >= 3 or result.get("http_status") == 429:
            break
        time.sleep(0.5)
    report = {"checked_at_unix": time.time(), "unique_urls": len(urls), "checked": len(results), "unchecked": len(urls)-len(results), "counts": dict(Counter(r["status"] for r in results.values())), "results": results, "note": "Network/TLS failures are unverified, not evidence of dead links. Stops on three consecutive certificate errors or HTTP 429."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "results"}, ensure_ascii=False))
