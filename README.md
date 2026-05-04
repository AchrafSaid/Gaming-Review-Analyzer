# Gaming Review Analyzer - CS313x Phase 1

## Project Overview

Gaming Review Analyzer is a web intelligence project that collects public Steam game review data, stores it in JSON, cleans and preprocesses review text, and produces exploratory analysis charts for review trends.

## Team

- Ashraf Said - 247413
- Nadeem Ahmed - 249167
- Mohamed Kadri - 247619
- Mohamed Mahmoud - 247371
- Omar Ali - 241921

## Data Source and Ethics

The project uses only HTML web pages for scraping, not API/JSON endpoints:

- Search discovery pages: `https://store.steampowered.com/search/`
- App metadata pages: `https://store.steampowered.com/app/{app_id}/`
- Review pages: `https://steamcommunity.com/app/{app_id}/reviews/`

The robots checker writes `robots_compliance_report.txt`. Steam Store and Steam Community robots.txt allow the HTML paths used by this project. The scraper uses a 1.5 second delay because no crawl delay is specified.

## Dataset

The scraper targets 50-200 records for Phase 1. Each raw record contains:

- game title, app id, source URL
- genre, developer, publisher, release date, platforms
- review text, recommendation label, user score proxy
- vote counts, playtime at review, review timestamps
- scrape timestamp and source name

Generated files:

- `data/games_raw.json`
- `data/games_clean.json`
- `data/cleaning_report.txt`
- `data/scraper.log`
- `outputs/eda_report.txt`
- `outputs/*.png`

## How to Run

From the project root:

```bash
python -m pip install -r requirements.txt
python scripts/robot_check.py
python "scripts/Scraping&Crawling.py" --max-records 120 --reviews-per-game 15 --search-pages 1 --review-pages-per-game 3
python scripts/cleaner.py
python scripts/EDA.py
```

If a lab machine has local HTTPS certificate interception, run with `CS313X_INSECURE_SSL=1`. Normal SSL verification remains the default.

## Phase 1 Rubric Mapping

- Project idea: Gaming review intelligence and trend analysis.
- Web scraping and crawling: Multi-page Steam HTML search discovery, app-page metadata parsing, and Steam Community HTML review-page extraction.
- Robots compliance: `scripts/robot_check.py` and `robots_compliance_report.txt`.
- Data storage: Consistent JSON schema in `games_raw.json` and `games_clean.json`.
- Cleaning and preprocessing: HTML cleanup, normalization, tokenization, stopword removal, date normalization, duplicate handling, and sentiment scoring.
- Data quality handling: Missing-field tracking and duplicate removal in `cleaning_report.txt`.
- EDA: Review recommendation distribution, sentiment labels, review lengths, top genres, top games, keyword frequencies, and playtime analysis.
- Visualization: PNG charts saved under `outputs/`.
