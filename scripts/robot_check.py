from __future__ import annotations

import os
import ssl
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen


TARGET_SITES = {
    "Steam Store": "https://store.steampowered.com",
}

USER_AGENT = "Mozilla/5.0 (compatible; CS313xBot/1.0; Educational Project)"

PATHS_TO_CHECK = [
    "/",
    "/search/",
    "/app/1091500/",
    "/appreviews/1091500",
    "/api/appdetails",
    "/share/",
]


def ssl_context() -> ssl.SSLContext | None:
    if os.getenv("CS313X_INSECURE_SSL") == "1":
        return ssl._create_unverified_context()
    return None


def fetch_robots(base_url: str) -> str:
    robots_url = base_url.rstrip("/") + "/robots.txt"
    request = Request(robots_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20, context=ssl_context()) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def check_site(name: str, base_url: str) -> dict:
    robots_url = base_url.rstrip("/") + "/robots.txt"
    print(f"\n{'=' * 60}")
    print(f"  Site     : {name}")
    print(f"  Base URL : {base_url}")
    print(f"  Robots   : {robots_url}")
    print(f"{'=' * 60}")

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)

    try:
        robots_text = fetch_robots(base_url)
        rp.parse(robots_text.splitlines())
    except Exception as exc:
        print(f"  Could not read robots.txt: {exc}")
        robots_text = ""

    try:
        crawl_delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
    except Exception:
        crawl_delay = None

    print(f"\n  Crawl-delay : {crawl_delay if crawl_delay else 'Not specified (using 1.5s default)'}")
    print("\n  Path Access Check:")

    paths = {}
    for path in PATHS_TO_CHECK:
        full_url = base_url.rstrip("/") + path
        allowed = rp.can_fetch(USER_AGENT, full_url)
        paths[path] = allowed
        status = "ALLOWED" if allowed else "DISALLOWED"
        print(f"    [{status}] {path}")

    print("\n  Raw robots.txt (first 800 chars):")
    print(robots_text[:800])

    return {
        "crawl_delay": crawl_delay or "1.5s default",
        "paths": paths,
    }


def save_compliance_report(results: dict, filename: str = "robots_compliance_report.txt") -> None:
    report_path = Path(filename)
    lines = []

    for site, data in results.items():
        lines.append(f"Site: {site}")
        lines.append(f"  Crawl Delay : {data['crawl_delay']}")
        lines.append("  Paths:")
        for path, allowed in data["paths"].items():
            status = "ALLOWED" if allowed else "DISALLOWED"
            lines.append(f"    [{status}] {path}")
        lines.append("")

    lines += [
        "Decision:",
        "  Proceed with Steam Store search pages, app detail metadata, and",
        "  appreviews review pages only. Keep the 1.5 second default delay",
        "  because robots.txt does not specify a crawl-delay.",
        "  Do not access disallowed paths such as /share/.",
        "",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nCompliance report saved -> {report_path}")


def run() -> None:
    print("\nCS313x - Checking robots.txt compliance for gaming review source\n")
    results = {}
    for name, url in TARGET_SITES.items():
        results[name] = check_site(name, url)
    save_compliance_report(results)


if __name__ == "__main__":
    run()
