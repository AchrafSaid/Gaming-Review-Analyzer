"""
scraper.py
----------
CS313x - Gaming Review Analyzer | Phase 1
Scrapes game reviews from Metacritic (multi-page crawling).
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import argparse
import os
import logging
from datetime import datetime

BASE_URL    = "https://www.metacritic.com"
BROWSE_URL  = "{base}/browse/game/all/all/all-time/metascore/?releaseYearMin=2015&releaseYearMax=2024&page={page}"
HEADERS     = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
CRAWL_DELAY = 2
MAX_RETRIES = 3
OUTPUT_FILE = "data/games_raw.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def empty_record() -> dict:
    return {
        "id":           None,
        "title":        None,
        "platform":     None,
        "genre":        None,
        "developer":    None,
        "publisher":    None,
        "release_date": None,
        "critic_score": None,
        "user_score":   None,
        "review_count": None,
        "summary":      None,
        "url":          None,
        "scraped_at":   None,
    }


def safe_get(url, session, retries=MAX_RETRIES):
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
            elif resp.status_code == 429:
                wait = 10 * attempt
                log.warning(f"Rate-limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                log.warning(f"HTTP {resp.status_code} for {url}")
                return None
        except requests.RequestException as e:
            log.error(f"Request error (attempt {attempt}/{retries}): {e}")
            time.sleep(CRAWL_DELAY * attempt)
    return None


def parse_score(text):
    if not text:
        return None
    m = re.search(r"\d+", str(text).strip())
    return int(m.group()) if m else None


def parse_user_score(text):
    if not text:
        return None
    t = str(text).strip()
    if t.lower() in ("tbd", "n/a", ""):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_date(text):
    if not text:
        return None
    t = text.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return t


def scrape_game_detail(url, session, record_id):
    record = empty_record()
    record["id"]         = record_id
    record["url"]        = url
    record["scraped_at"] = datetime.now().isoformat()

    soup = safe_get(url, session)
    if soup is None:
        log.warning(f"Skipping (no response): {url}")
        return record

    # Title
    title_tag = (
        soup.find("h1", class_=re.compile(r"product-title|c-productHero_title")) or
        soup.find("h1")
    )
    record["title"] = title_tag.get_text(strip=True) if title_tag else None

    # Critic score
    critic_tag = (
        soup.find("div", class_=re.compile(r"metascore_w|c-siteReviewScore")) or
        soup.find("span", class_=re.compile(r"metascore"))
    )
    record["critic_score"] = parse_score(critic_tag.get_text() if critic_tag else None)

    # User score
    user_tag = soup.find("div", class_=re.compile(r"user_score|c-siteReviewScore_user"))
    record["user_score"] = parse_user_score(user_tag.get_text() if user_tag else None)

    # Summary
    summary_tag = (
        soup.find("span", class_=re.compile(r"c-productDetails_description|blurb")) or
        soup.find("div",  class_=re.compile(r"product_description|summary_detail"))
    )
    record["summary"] = summary_tag.get_text(strip=True) if summary_tag else None

    # Genre (fixed selector)
    genre_tag = soup.find(class_=re.compile(r"c-genreList"))
    if genre_tag:
        record["genre"] = genre_tag.get_text(strip=True)

    # Details sections (fixed selector)
    for section in soup.find_all("div", class_=re.compile(r"c-productDetails_section")):
        label = section.find(class_=re.compile(r"c-productDetails_section_label"))
        value = section.find(class_=re.compile(r"c-productDetails_section_value|c-genreList|c-productDetails_section_list"))
        if not label or not value:
            continue
        key = label.get_text(strip=True).lower()
        val = value.get_text(strip=True)
        if "developer" in key:
            record["developer"] = val
        elif "publisher" in key:
            record["publisher"] = val
        elif "release" in key:
            record["release_date"] = parse_date(val)
        elif "platform" in key:
            record["platform"] = val

    # Review count
    review_count_tag = soup.find(class_=re.compile(r"count|based_on"))
    if review_count_tag:
        record["review_count"] = parse_score(review_count_tag.get_text())

    log.info(f"  [{record_id}] {record['title']} | Critic: {record['critic_score']} | Genre: {record['genre']} | Platform: {record['platform']}")
    return record


def scrape_browse_page(page_num, session):
    url  = BROWSE_URL.format(base=BASE_URL, page=page_num)
    soup = safe_get(url, session)
    if soup is None:
        return []

    links = []
    for tag in soup.find_all("a", href=re.compile(r"/game/")):
        href = tag.get("href", "")
        if href and re.match(r"^/game/[^/]+/?$", href):
            full = BASE_URL + href if href.startswith("/") else href
            if full not in links:
                links.append(full)

    log.info(f"Page {page_num}: found {len(links)} game links")
    return links


def run(total_pages=5):
    os.makedirs("data", exist_ok=True)
    session   = requests.Session()
    all_data  = []
    seen_urls = set()
    record_id = 1

    log.info(f"Starting scraper | pages={total_pages} | delay={CRAWL_DELAY}s")

    for page in range(1, total_pages + 1):
        log.info(f"── Browse page {page}/{total_pages} ──")
        game_urls = scrape_browse_page(page, session)

        for url in game_urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            record = scrape_game_detail(url, session, record_id)
            all_data.append(record)
            record_id += 1
            time.sleep(CRAWL_DELAY)

        time.sleep(CRAWL_DELAY)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    log.info(f"Done. {len(all_data)} records saved to {OUTPUT_FILE}")
    return all_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CS313x Gaming Review Scraper")
    parser.add_argument("--pages", type=int, default=5)
    args = parser.parse_args()
    run(total_pages=args.pages)