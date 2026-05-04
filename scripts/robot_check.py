from __future__ import annotations

import os
import ssl
import urllib.robotparser
from pathlib import Path
from urllib.request import Request, urlopen


TARGET_SITES = {
    "Steam Store": {
        "base": "https://store.steampowered.com",
        "paths": ["/", "/search/", "/search/results/", "/app/1091500/", "/share/"],
    },
    "Steam Community": {
        "base": "https://steamcommunity.com",
        "paths": ["/", "/app/1091500/reviews/", "/actions/", "/trade/"],
    },
}

USER_AGENT = "Mozilla/5.0 (compatible; CS313xBot/1.0; Educational Project)"


def ssl_context() -> ssl.SSLContext | None:
    if os.getenv("CS313X_INSECURE_SSL") == "1":
        return ssl._create_unverified_context()
    return None


def fetch_robots(base_url: str) -> str:
    request = Request(base_url.rstrip("/") + "/robots.txt", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20, context=ssl_context()) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def check_site(name: str, base_url: str, paths: list[str]) -> dict:
    robots_url = base_url.rstrip("/") + "/robots.txt"
    print(f"\nSite     : {name}")
    print(f"Base URL : {base_url}")
    print(f"Robots   : {robots_url}")

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)

    try:
        robots_text = fetch_robots(base_url)
        rp.parse(robots_text.splitlines())
    except Exception as exc:
        print(f"Could not read robots.txt: {exc}")
        robots_text = ""

    try:
        crawl_delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
    except Exception:
        crawl_delay = None

    print(f"Crawl-delay : {crawl_delay if crawl_delay else 'Not specified (using 1.5s default)'}")
    print("Path Access Check:")

    checked_paths = {}
    for path in paths:
        allowed = rp.can_fetch(USER_AGENT, base_url.rstrip("/") + path)
        checked_paths[path] = allowed
        status = "ALLOWED" if allowed else "DISALLOWED"
        print(f"  [{status}] {path}")

    print("Raw robots.txt (first 500 chars):")
    print(robots_text[:500])

    return {
        "crawl_delay": crawl_delay or "1.5s default",
        "paths": checked_paths,
    }


def save_compliance_report(results: dict, filename: str = "robots_compliance_report.txt") -> None:
    lines = [
        "CS313x Gaming Review Analyzer - robots.txt Compliance Report",
        "",
    ]

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
        "  Proceed only with HTML pages allowed by robots.txt:",
        "  Steam Store search/app pages and Steam Community review pages.",
        "  Do not use Steam API/appreviews JSON endpoints for data collection.",
        "  Do not access disallowed paths such as /share/, /actions/, or /trade/.",
        "",
    ]

    Path(filename).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nCompliance report saved -> {filename}")


def run() -> None:
    print("\nCS313x - Checking robots.txt compliance for HTML scraping sources\n")
    results = {}
    for name, config in TARGET_SITES.items():
        results[name] = check_site(name, config["base"], config["paths"])
    save_compliance_report(results)


if __name__ == "__main__":
    run()
