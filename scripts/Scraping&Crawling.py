from __future__ import annotations

import argparse
import json
import logging
import os
import re
import ssl
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://store.steampowered.com"
SEARCH_URL = f"{BASE_URL}/search/results/"
APPDETAILS_URL = f"{BASE_URL}/api/appdetails"
APPREVIEWS_URL = f"{BASE_URL}/appreviews/{{app_id}}"

USER_AGENT = "Mozilla/5.0 (compatible; CS313xBot/1.0; Educational Project)"
CRAWL_DELAY = 1.5
MAX_RETRIES = 3
OUTPUT_FILE = Path("data/games_raw.json")
LOG_FILE = Path("data/scraper.log")

DEFAULT_SEARCH_TERMS = ["rpg", "strategy", "adventure"]

SEED_APP_IDS = [
    "1091500",  # Cyberpunk 2077
    "1245620",  # Elden Ring
    "1086940",  # Baldur's Gate 3
    "413150",   # Stardew Valley
    "292030",   # The Witcher 3
    "1174180",  # Red Dead Redemption 2
]


def configure_logging() -> logging.Logger:
    Path("data").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
        force=True,
    )
    return logging.getLogger(__name__)


log = logging.getLogger(__name__)


def ssl_context() -> ssl.SSLContext | None:
    """
    Use normal certificate verification by default.

    Some lab machines intercept HTTPS and break local certificates. For that
    case only, set CS313X_INSECURE_SSL=1 while running the script.
    """
    if os.getenv("CS313X_INSECURE_SSL") == "1":
        return ssl._create_unverified_context()
    return None


def fetch_text(url: str, accept: str = "text/html") -> str | None:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=25, context=ssl_context()) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except HTTPError as exc:
            if exc.code == 429:
                wait = 10 * attempt
                log.warning("Rate limited. Waiting %ss before retrying.", wait)
                time.sleep(wait)
                continue
            log.warning("HTTP %s for %s", exc.code, url)
            return None
        except URLError as exc:
            log.warning("Request failed on attempt %s/%s: %s", attempt, MAX_RETRIES, exc)
            time.sleep(CRAWL_DELAY * attempt)
    return None


def fetch_json(url: str) -> dict[str, Any] | None:
    text = fetch_text(url, accept="application/json,text/plain;q=0.9,*/*;q=0.8")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("Could not decode JSON from %s: %s", url, exc)
        return None


def normalize_html_text(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def discover_app_ids(search_terms: list[str], search_pages: int, per_page: int = 50) -> list[str]:
    found: list[str] = []
    seen = set()

    for term in search_terms:
        for page in range(search_pages):
            params = {
                "query": "",
                "start": page * per_page,
                "count": per_page,
                "term": term,
                "force_infinite": 1,
                "category1": 998,
                "supportedlang": "english",
            }
            url = f"{SEARCH_URL}?{urlencode(params)}"
            html = fetch_text(url)
            if not html:
                continue

            ids = re.findall(r'data-ds-appid="(\d+)"', html)
            ids.extend(re.findall(r"/app/(\d+)/", html))
            for app_id in ids:
                if app_id not in seen:
                    seen.add(app_id)
                    found.append(app_id)

            log.info("Search term '%s', page %s: discovered %s unique apps total", term, page + 1, len(found))
            time.sleep(CRAWL_DELAY)

    ordered = []
    for app_id in SEED_APP_IDS + found:
        if app_id not in ordered:
            ordered.append(app_id)
    return ordered


def get_app_details(app_id: str) -> dict[str, Any] | None:
    params = {
        "appids": app_id,
        "filters": "basic,developers,publishers,genres,release_date,platforms",
    }
    data = fetch_json(f"{APPDETAILS_URL}?{urlencode(params)}")
    if not data or app_id not in data or not data[app_id].get("success"):
        return None

    details = data[app_id].get("data", {})
    if details.get("type") != "game":
        return None

    genres = [g.get("description") for g in details.get("genres", []) if g.get("description")]
    platforms = [
        name.title()
        for name, enabled in (details.get("platforms") or {}).items()
        if enabled
    ]

    return {
        "app_id": int(app_id),
        "title": details.get("name"),
        "genre": genres[0] if genres else None,
        "genres": genres,
        "developer": "; ".join(details.get("developers", []) or []) or None,
        "publisher": "; ".join(details.get("publishers", []) or []) or None,
        "platform": "/".join(platforms) if platforms else None,
        "platforms": platforms,
        "release_date": (details.get("release_date") or {}).get("date"),
        "game_description": normalize_html_text(details.get("short_description")),
        "url": f"{BASE_URL}/app/{app_id}/",
    }


def review_url(app_id: str, cursor: str, reviews_per_page: int) -> str:
    params = {
        "json": 1,
        "num_per_page": reviews_per_page,
        "filter": "recent",
        "language": "english",
        "review_type": "all",
        "purchase_type": "all",
        "cursor": cursor,
    }
    return f"{APPREVIEWS_URL.format(app_id=app_id)}?{urlencode(params, quote_via=quote)}"


def unix_to_iso(value: int | str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return None


def scrape_reviews_for_app(
    app_id: str,
    details: dict[str, Any],
    max_reviews: int,
    page_size: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    cursor = "*"

    while len(records) < max_reviews:
        data = fetch_json(review_url(app_id, cursor, min(page_size, max_reviews - len(records))))
        if not data or data.get("success") != 1:
            break

        query_summary = data.get("query_summary", {})
        reviews = data.get("reviews", [])
        if not reviews:
            break

        for item in reviews:
            text = normalize_html_text(item.get("review"))
            if not text or len(text) < 20:
                continue

            recommended = bool(item.get("voted_up"))
            author = item.get("author", {}) or {}
            record = {
                "id": f"{app_id}-{item.get('recommendationid')}",
                "recommendation_id": item.get("recommendationid"),
                "app_id": details["app_id"],
                "title": details["title"],
                "game_title": details["title"],
                "platform": details["platform"],
                "platforms": details["platforms"],
                "genre": details["genre"],
                "genres": details["genres"],
                "developer": details["developer"],
                "publisher": details["publisher"],
                "release_date": details["release_date"],
                "game_description": details["game_description"],
                "review_text": text,
                "summary": text,
                "recommended": recommended,
                "user_score": 10.0 if recommended else 0.0,
                "weighted_vote_score": float(item.get("weighted_vote_score") or 0),
                "votes_up": int(item.get("votes_up") or 0),
                "votes_funny": int(item.get("votes_funny") or 0),
                "comment_count": int(item.get("comment_count") or 0),
                "playtime_hours_at_review": round((int(author.get("playtime_at_review") or 0) / 60), 2),
                "review_created_at": unix_to_iso(item.get("timestamp_created")),
                "review_updated_at": unix_to_iso(item.get("timestamp_updated")),
                "review_count": query_summary.get("total_reviews"),
                "review_score_desc": query_summary.get("review_score_desc"),
                "source": "Steam",
                "url": details["url"],
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            records.append(record)
            if len(records) >= max_reviews:
                break

        next_cursor = data.get("cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(CRAWL_DELAY)

    return records


def run(
    max_records: int = 120,
    reviews_per_game: int = 25,
    search_pages: int = 2,
    search_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    global log
    log = configure_logging()

    Path("data").mkdir(exist_ok=True)
    search_terms = search_terms or DEFAULT_SEARCH_TERMS

    log.info("Starting Steam scraper | target_records=%s | delay=%ss", max_records, CRAWL_DELAY)
    app_ids = discover_app_ids(search_terms, search_pages=search_pages)
    log.info("Candidate apps discovered: %s", len(app_ids))

    all_records: list[dict[str, Any]] = []
    seen_review_ids = set()

    for app_id in app_ids:
        if len(all_records) >= max_records:
            break

        details = get_app_details(app_id)
        if not details:
            continue

        target_for_app = min(reviews_per_game, max_records - len(all_records))
        reviews = scrape_reviews_for_app(app_id, details, target_for_app, page_size=50)

        added = 0
        for review in reviews:
            key = review.get("recommendation_id") or review["id"]
            if key in seen_review_ids:
                continue
            seen_review_ids.add(key)
            all_records.append(review)
            added += 1
            if len(all_records) >= max_records:
                break

        log.info("App %s (%s): added %s reviews", app_id, details["title"], added)
        time.sleep(CRAWL_DELAY)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    log.info("Done. %s records saved to %s", len(all_records), OUTPUT_FILE)
    return all_records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CS313x Steam review scraper")
    parser.add_argument("--max-records", type=int, default=120)
    parser.add_argument("--reviews-per-game", type=int, default=25)
    parser.add_argument("--search-pages", type=int, default=2)
    parser.add_argument("--terms", nargs="*", default=DEFAULT_SEARCH_TERMS)
    args = parser.parse_args()
    run(
        max_records=args.max_records,
        reviews_per_game=args.reviews_per_game,
        search_pages=args.search_pages,
        search_terms=args.terms,
    )
