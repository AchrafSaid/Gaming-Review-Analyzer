from __future__ import annotations

import logging
import os
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STORE_BASE_URL = "https://store.steampowered.com"
COMMUNITY_BASE_URL = "https://steamcommunity.com"
SEARCH_URL = f"{STORE_BASE_URL}/search/results/"

USER_AGENT = "Mozilla/5.0 (compatible; CS313xBot/1.0; Educational Project)"
CRAWL_DELAY = 1.5
MAX_RETRIES = 3

DEFAULT_SEARCH_TERMS = ["rpg", "strategy", "adventure"]

SEED_APP_IDS = [
    "1091500",  # Cyberpunk 2077
    "1245620",  # Elden Ring
    "1086940",  # Baldur's Gate 3
    "413150",   # Stardew Valley
    "292030",   # The Witcher 3
    "1174180",  # Red Dead Redemption 2
]

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


def review_page_url(app_id: str, page: int) -> str:
    params = {
        "browsefilter": "mostrecent",
        "filterLanguage": "english",
        "p": page,
    }
    return f"{COMMUNITY_BASE_URL}/app/{app_id}/reviews/?{urlencode(params)}"
