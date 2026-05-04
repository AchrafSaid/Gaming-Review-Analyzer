from __future__ import annotations

import argparse
import hashlib
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
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STORE_BASE_URL = "https://store.steampowered.com"
COMMUNITY_BASE_URL = "https://steamcommunity.com"
SEARCH_URL = f"{STORE_BASE_URL}/search/results/"

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
    if os.getenv("CS313X_INSECURE_SSL") == "1":
        return ssl._create_unverified_context()
    return None


def fetch_html(url: str) -> str | None:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "birthtime=568022401; lastagecheckage=1-January-1988; mature_content=1",
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


def strip_tags(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def first_match(pattern: str, text: str, flags: int = re.S | re.I) -> str | None:
    match = re.search(pattern, text, flags)
    return strip_tags(match.group(1)) if match else None


def all_matches(pattern: str, text: str, flags: int = re.S | re.I) -> list[str]:
    values = []
    for match in re.finditer(pattern, text, flags):
        value = strip_tags(match.group(1))
        if value and value not in values:
            values.append(value)
    return values


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
            html = fetch_html(url)
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


def parse_store_details(app_id: str, html: str) -> dict[str, Any] | None:
    title = first_match(r'id="appHubAppName"[^>]*>(.*?)</div>', html)
    if not title:
        title = first_match(r"<title>(.*?) on Steam</title>", html)
    if not title:
        return None

    description = first_match(r'<div class="game_description_snippet">(.*?)</div>', html)
    release_date = first_match(r'<div class="release_date">.*?<div class="date">(.*?)</div>', html)
    developer = first_match(r'<div class="subtitle column">\s*Developer:\s*</div>.*?<div class="summary column"[^>]*>(.*?)</div>', html)
    publisher = first_match(r'<div class="subtitle column">\s*Publisher:\s*</div>.*?<div class="summary column"[^>]*>(.*?)</div>', html)
    tags = all_matches(r'class="app_tag"[^>]*>(.*?)</a>', html)

    platforms = []
    purchase_match = re.search(r'<div class="game_area_purchase_platform">(.*?)</div>', html, flags=re.S | re.I)
    platform_source = purchase_match.group(1) if purchase_match else html
    for css_class, name in [("win", "Windows"), ("mac", "Mac"), ("linux", "Linux")]:
        if re.search(rf'platform_img\s+{css_class}', platform_source):
            platforms.append(name)

    return {
        "app_id": int(app_id),
        "title": title,
        "genre": tags[0] if tags else None,
        "genres": tags[:8],
        "developer": developer,
        "publisher": publisher,
        "platform": "/".join(platforms) if platforms else None,
        "platforms": platforms,
        "release_date": release_date,
        "game_description": description,
        "url": f"{STORE_BASE_URL}/app/{app_id}/",
    }


def get_app_details(app_id: str) -> dict[str, Any] | None:
    html = fetch_html(f"{STORE_BASE_URL}/app/{app_id}/")
    if not html:
        return None
    details = parse_store_details(app_id, html)
    if not details:
        log.warning("Could not parse app page HTML for app %s", app_id)
    return details


def review_page_url(app_id: str, page: int) -> str:
    params = {
        "browsefilter": "mostrecent",
        "filterLanguage": "english",
        "p": page,
    }
    return f"{COMMUNITY_BASE_URL}/app/{app_id}/reviews/?{urlencode(params)}"


def parse_review_cards(app_id: str, details: dict[str, Any], html: str) -> list[dict[str, Any]]:
    records = []
    starts = [match.start() for match in re.finditer(r'<div[^>]+class="apphub_Card modalContentLink interactable"', html, flags=re.I)]
    if not starts:
        return records

    starts.append(len(html))

    for index in range(len(starts) - 1):
        card_html = html[starts[index]:starts[index + 1]]
        review_url = first_match(r'data-modal-content-url="([^"]+)"', card_html) or ""
        text_start = re.search(r'<div class="apphub_CardTextContent">', card_html, flags=re.I)
        footer_start = re.search(r'<div class="UserReviewCardContent_Footer">', card_html, flags=re.I)
        if not text_start or not footer_start:
            continue

        text_html = card_html[text_start.end():footer_start.start()]
        text_html = re.sub(r'<div class="date_posted">.*?</div>', " ", text_html, flags=re.S | re.I)
        review_text = strip_tags(text_html)
        if not review_text or len(review_text) < 20:
            continue

        recommendation = first_match(r'<div class="reviewInfo">.*?<div class="title">(.*?)</div>', card_html)
        recommended = recommendation != "Not Recommended"
        hours_text = first_match(r'<div class="hours">(.*?)</div>', card_html) or ""
        hours_match = re.search(r"([\d,.]+)\s+hrs", hours_text)
        playtime = float(hours_match.group(1).replace(",", "")) if hours_match else 0.0
        posted = first_match(r'<div class="date_posted">(.*?)</div>', card_html)
        review_id = hashlib.sha1(review_url.encode("utf-8")).hexdigest()[:12] if review_url else f"{app_id}-{index + 1}"

        records.append({
            "id": f"{app_id}-{review_id}",
            "recommendation_id": review_id,
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
            "review_text": review_text,
            "summary": review_text,
            "recommended": recommended,
            "user_score": 10.0 if recommended else 0.0,
            "weighted_vote_score": None,
            "votes_up": None,
            "votes_funny": None,
            "comment_count": None,
            "playtime_hours_at_review": playtime,
            "review_created_at": posted,
            "review_updated_at": posted,
            "review_count": None,
            "review_score_desc": recommendation,
            "source": "Steam Community HTML",
            "url": review_url,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

    return records


def scrape_reviews_for_app(
    app_id: str,
    details: dict[str, Any],
    max_reviews: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen = set()

    for page in range(1, max_pages + 1):
        if len(records) >= max_reviews:
            break

        html = fetch_html(review_page_url(app_id, page))
        if not html:
            break

        page_records = parse_review_cards(app_id, details, html)
        if not page_records:
            break

        for record in page_records:
            key = record["recommendation_id"]
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
            if len(records) >= max_reviews:
                break

        log.info("App %s review page %s: parsed %s review cards", app_id, page, len(page_records))
        time.sleep(CRAWL_DELAY)

    return records


def run(
    max_records: int = 120,
    reviews_per_game: int = 25,
    search_pages: int = 2,
    review_pages_per_game: int = 4,
    search_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    global log
    log = configure_logging()

    Path("data").mkdir(exist_ok=True)
    search_terms = search_terms or DEFAULT_SEARCH_TERMS

    log.info("Starting Steam HTML scraper | target_records=%s | delay=%ss", max_records, CRAWL_DELAY)
    app_ids = discover_app_ids(search_terms, search_pages=search_pages)
    log.info("Candidate apps discovered from HTML search pages: %s", len(app_ids))

    all_records: list[dict[str, Any]] = []
    seen_review_ids = set()

    for app_id in app_ids:
        if len(all_records) >= max_records:
            break

        details = get_app_details(app_id)
        if not details:
            continue
        time.sleep(CRAWL_DELAY)

        target_for_app = min(reviews_per_game, max_records - len(all_records))
        reviews = scrape_reviews_for_app(app_id, details, target_for_app, review_pages_per_game)

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

        log.info("App %s (%s): added %s HTML-scraped reviews", app_id, details["title"], added)
        time.sleep(CRAWL_DELAY)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    log.info("Done. %s records saved to %s", len(all_records), OUTPUT_FILE)
    return all_records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CS313x Steam HTML review scraper")
    parser.add_argument("--max-records", type=int, default=120)
    parser.add_argument("--reviews-per-game", type=int, default=25)
    parser.add_argument("--search-pages", type=int, default=2)
    parser.add_argument("--review-pages-per-game", type=int, default=4)
    parser.add_argument("--terms", nargs="*", default=DEFAULT_SEARCH_TERMS)
    args = parser.parse_args()
    run(
        max_records=args.max_records,
        reviews_per_game=args.reviews_per_game,
        search_pages=args.search_pages,
        review_pages_per_game=args.review_pages_per_game,
        search_terms=args.terms,
    )
