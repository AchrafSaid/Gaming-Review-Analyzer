import urllib.robotparser
import urllib.request
import datetime

TARGET_SITES = {
    "Metacritic": "https://www.metacritic.com"
}

USER_AGENT = "Mozilla/5.0 (compatible; CS313xBot/1.0; Educational Project)"

PATHS_TO_CHECK = [
    "/game/",
    "/games/",
    "/reviews/",
    "/browse/",
    "/search/",
    "/api/",
]


def check_site(name, base_url):
    robots_url = base_url.rstrip("/") + "/robots.txt"
    print(f"\n{'='*60}")
    print(f"  Site     : {name}")
    print(f"  Base URL : {base_url}")
    print(f"  Robots   : {robots_url}")
    print(f"{'='*60}")

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)

    try:
        rp.read()
        crawl_delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
        print(f"\n  Crawl-delay : {crawl_delay if crawl_delay else 'Not specified (using 2s default)'}")
        print(f"\n  Path Access Check:")
        for path in PATHS_TO_CHECK:
            full_url = base_url + path
            allowed  = rp.can_fetch(USER_AGENT, full_url)
            symbol   = "ALLOWED" if allowed else " DISALLOWED"
            print(f"    {symbol}  →  {path}")
    except Exception as e:
        print(f"  Could not read robots.txt: {e}")

    # Also print raw robots.txt content
    try:
        with urllib.request.urlopen(robots_url, timeout=10) as r:
            content = r.read().decode("utf-8", errors="ignore")
        print(f"\n  --- Raw robots.txt (first 800 chars) ---")
        print(content[:800])
    except Exception as e:
        print(f"  Could not fetch raw file: {e}")


def save_compliance_report(results: dict, filename="robots_compliance_report.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  CS313x Gaming Review Analyzer — robots.txt Compliance Report\n")
        f.write(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        for site, data in results.items():
            f.write(f"Site: {site}\n")
            f.write(f"  Crawl Delay : {data['crawl_delay']}\n")
            f.write("  Paths:\n")
            for path, allowed in data["paths"].items():
                status = "ALLOWED" if allowed else "DISALLOWED"
                f.write(f"    [{status}]  {path}\n")
            f.write("\n")
        f.write("Decision: Scraping Metacritic /game/ pages with 2s delay between requests.\n")
    print(f"\n  ✅  Compliance report saved → {filename}")


def run():
    print("\n🔍 CS313x — Checking robots.txt Compliance for Gaming Sites\n")
    results = {}

    for name, url in TARGET_SITES.items():
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(url.rstrip("/") + "/robots.txt")
        try:
            rp.read()
        except Exception:
            pass

        crawl_delay = None
        try:
            crawl_delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
        except Exception:
            pass

        paths = {}
        for path in PATHS_TO_CHECK:
            try:
                paths[path] = rp.can_fetch(USER_AGENT, url + path)
            except Exception:
                paths[path] = None

        results[name] = {"crawl_delay": crawl_delay or "2s default", "paths": paths}
        check_site(name, url)

    save_compliance_report(results)


if __name__ == "__main__":
    run()