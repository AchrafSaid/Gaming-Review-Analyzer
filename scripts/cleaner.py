from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "be", "was", "are",
    "were", "as", "this", "that", "these", "those", "has", "have", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "can", "into", "than", "then", "so", "yet", "not", "no",
    "very", "just", "also", "only", "over", "after", "before", "between",
    "through", "during", "while", "if", "when", "where", "which", "who",
    "what", "how", "all", "each", "every", "more", "most", "such", "own",
    "same", "other", "another", "about", "up", "out", "your", "my",
    "their", "our", "his", "her", "we", "they", "he", "she", "you", "i",
    "me", "him", "us", "them", "been", "being", "make", "made", "get",
    "got", "go", "new", "game", "games", "play", "played", "player",
    "players", "steam", "review", "reviews"
}

POSITIVE_WORDS = {
    "amazing", "awesome", "beautiful", "best", "better", "brilliant",
    "classic", "enjoy", "enjoyed", "excellent", "fantastic", "fun", "good",
    "great", "incredible", "love", "loved", "masterpiece", "perfect",
    "recommend", "recommended", "solid", "worth"
}

NEGATIVE_WORDS = {
    "bad", "boring", "broken", "bug", "buggy", "crash", "crashes", "dead",
    "disappointing", "hate", "hated", "issue", "issues", "lag", "negative",
    "poor", "refund", "slow", "terrible", "unplayable", "worse", "worst"
}

INPUT_FILE = Path("data/games_raw.json")
OUTPUT_FILE = Path("data/games_clean.json")
REPORT_FILE = Path("data/cleaning_report.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def remove_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def remove_special_chars(text: str) -> str:
    return re.sub(r"[^a-z0-9\s\.\,\!\?\-\']", " ", text)


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z][a-z0-9']*\b", text)


def remove_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def preprocess_text(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {"cleaned": None, "tokens": [], "filtered_tokens": [], "token_count": 0, "unique_terms": 0}

    step1 = remove_html(str(raw))
    step2 = normalize_text(step1)
    step3 = remove_special_chars(step2)
    step4 = normalize_text(step3)
    tokens = tokenize(step4)
    filtered_tokens = remove_stopwords(tokens)

    return {
        "cleaned": step4,
        "tokens": tokens,
        "filtered_tokens": filtered_tokens,
        "token_count": len(tokens),
        "unique_terms": len(set(filtered_tokens)),
    }


def clean_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_user_score(value, recommended=None) -> float | None:
    score = clean_float(value)
    if score is not None and 0 <= score <= 10:
        return round(score, 2)
    if isinstance(recommended, bool):
        return 10.0 if recommended else 0.0
    return None


def clean_date(value) -> str | None:
    if not value:
        return None

    text = str(value).strip()
    formats = (
        "%Y-%m-%d",
        "%d %b, %Y",
        "%d %B, %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def clean_text_field(value) -> str | None:
    if value in (None, ""):
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    return text or None


def clean_string_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[,/|;]", str(value))
    cleaned = []
    for item in items:
        text = clean_text_field(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def infer_sentiment(tokens: list[str]) -> tuple[float, str]:
    if not tokens:
        return 0.0, "neutral"
    pos = sum(1 for token in tokens if token in POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    score = round((pos - neg) / max(len(tokens), 1), 3)
    if score > 0.015:
        return score, "positive"
    if score < -0.015:
        return score, "negative"
    return score, "neutral"


def clean_record(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    rec = dict(raw)

    rec["id"] = clean_text_field(rec.get("id"))
    if not rec["id"]:
        rec["id"] = clean_text_field(rec.get("recommendation_id"))
    if not rec["id"]:
        issues.append("missing_id")

    rec["recommendation_id"] = clean_text_field(rec.get("recommendation_id"))
    rec["app_id"] = clean_int(rec.get("app_id"))
    if rec["app_id"] is None:
        issues.append("missing_app_id")

    rec["title"] = clean_text_field(rec.get("title") or rec.get("game_title"))
    rec["game_title"] = rec["title"]
    if not rec["title"]:
        issues.append("missing_title")

    rec["genre"] = clean_text_field(rec.get("genre"))
    rec["genres"] = clean_string_list(rec.get("genres") or rec.get("genre"))
    if not rec["genre"] and rec["genres"]:
        rec["genre"] = rec["genres"][0]
    if not rec["genre"]:
        issues.append("missing_genre")

    rec["platforms"] = clean_string_list(rec.get("platforms") or rec.get("platform"))
    rec["platform"] = "/".join(rec["platforms"]) if rec["platforms"] else clean_text_field(rec.get("platform"))
    if not rec["platform"]:
        issues.append("missing_platform")

    rec["developer"] = clean_text_field(rec.get("developer"))
    rec["publisher"] = clean_text_field(rec.get("publisher"))
    rec["release_date"] = clean_date(rec.get("release_date"))
    if not rec["release_date"]:
        issues.append("missing_release_date")

    rec["review_text"] = clean_text_field(rec.get("review_text") or rec.get("summary"))
    rec["summary"] = rec["review_text"]
    if not rec["review_text"]:
        issues.append("missing_review_text")

    review_proc = preprocess_text(rec["review_text"])
    rec["review_clean"] = review_proc["cleaned"]
    rec["review_tokens"] = review_proc["filtered_tokens"]
    rec["review_token_count"] = review_proc["token_count"]
    rec["review_unique_terms"] = review_proc["unique_terms"]

    desc_proc = preprocess_text(rec.get("game_description"))
    rec["description_clean"] = desc_proc["cleaned"]
    rec["description_tokens"] = desc_proc["filtered_tokens"]

    rec["recommended"] = bool(rec.get("recommended"))
    rec["user_score"] = clean_user_score(rec.get("user_score"), rec["recommended"])
    if rec["user_score"] is None:
        issues.append("missing_user_score")

    rec["weighted_vote_score"] = clean_float(rec.get("weighted_vote_score"))
    rec["votes_up"] = clean_int(rec.get("votes_up")) or 0
    rec["votes_funny"] = clean_int(rec.get("votes_funny")) or 0
    rec["comment_count"] = clean_int(rec.get("comment_count")) or 0
    rec["playtime_hours_at_review"] = clean_float(rec.get("playtime_hours_at_review")) or 0.0
    rec["review_count"] = clean_int(rec.get("review_count"))
    rec["review_created_at"] = clean_date(rec.get("review_created_at"))
    rec["review_updated_at"] = clean_date(rec.get("review_updated_at"))

    sentiment_score, sentiment_label = infer_sentiment(rec["review_tokens"])
    rec["sentiment_score"] = sentiment_score
    rec["sentiment_label"] = sentiment_label

    rec["data_issues"] = issues
    return rec, issues


def remove_duplicates(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen = set()
    unique = []
    removed = 0

    for record in records:
        key = record.get("recommendation_id") or record.get("id")
        if not key:
            key = (
                str(record.get("app_id", "")).lower(),
                str(record.get("review_text", "")).lower(),
            )
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        unique.append(record)

    return unique, removed


def generate_report(
    raw_count: int,
    clean_count: int,
    dup_count: int,
    dropped_count: int,
    issue_counter: Counter,
    output_path: Path,
    records: list[dict[str, Any]],
) -> None:
    token_total = sum(len(r.get("review_tokens", [])) for r in records)
    with_text = sum(1 for r in records if r.get("review_text"))
    recommended = sum(1 for r in records if r.get("recommended"))
    not_recommended = clean_count - recommended
    unique_games = len({r.get("app_id") for r in records if r.get("app_id")})

    lines = [
        f"  Raw records        : {raw_count}",
        f"  Duplicates removed : {dup_count}",
        f"  Empty-text dropped : {dropped_count}",
        f"  Clean records      : {clean_count}",
        f"  Unique games       : {unique_games}",
        f"  Reviews with text  : {with_text}",
        f"  Filtered tokens    : {token_total}",
        f"  Recommended        : {recommended}",
        f"  Not recommended    : {not_recommended}",
        f"  Kept rate          : {clean_count / max(raw_count, 1) * 100:.1f}%",
        "",
        "  Data Quality Issues Breakdown:",
    ]

    if issue_counter:
        for issue, count in issue_counter.most_common():
            pct = count / max(clean_count, 1) * 100
            lines.append(f"    {issue:<30} {count:>4} records  ({pct:.1f}%)")
    else:
        lines.append("    No recurring quality issues detected.")

    lines += [
        "",
        "  Preprocessing Steps Applied:",
        "    1. HTML tag removal",
        "    2. Lowercasing and whitespace normalization",
        "    3. Special character cleanup",
        "    4. Regex tokenization",
        "    5. Stopword removal with game-domain terms",
        "    6. Date normalization to YYYY-MM-DD",
        "    7. Duplicate removal by Steam recommendation id",
        "    8. Lightweight sentiment scoring from cleaned tokens",
        "",
    ]

    text = "\n".join(lines)
    output_path.write_text(text, encoding="utf-8")
    print(text)


def run() -> list[dict[str, Any]] | None:
    Path("data").mkdir(exist_ok=True)

    if not INPUT_FILE.exists():
        log.error("Input file not found: %s", INPUT_FILE)
        log.error("Run Scraping&Crawling.py first to generate raw data.")
        return None

    raw_data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    log.info("Loaded %s raw records from %s", len(raw_data), INPUT_FILE)

    deduped, dup_count = remove_duplicates(raw_data)
    cleaned_data = []
    issue_counter = Counter()
    dropped_count = 0

    for raw_record in deduped:
        cleaned_record, issues = clean_record(raw_record)
        issue_counter.update(issues)
        if "missing_review_text" in issues:
            dropped_count += 1
            continue
        cleaned_data.append(cleaned_record)

    OUTPUT_FILE.write_text(
        json.dumps(cleaned_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Saved %s clean records to %s", len(cleaned_data), OUTPUT_FILE)

    generate_report(
        raw_count=len(raw_data),
        clean_count=len(cleaned_data),
        dup_count=dup_count,
        dropped_count=dropped_count,
        issue_counter=issue_counter,
        output_path=REPORT_FILE,
        records=cleaned_data,
    )
    return cleaned_data


if __name__ == "__main__":
    run()
