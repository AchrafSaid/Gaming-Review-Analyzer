import json
import re
import os
import logging
from datetime import datetime
from collections import Counter

# stopwords
STOPWORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","it","its","be","was","are","were","as","this","that",
    "these","those","has","have","had","do","does","did","will","would",
    "could","should","may","might","can","into","than","then","so","yet",
    "both","either","neither","not","no","nor","very","just","also","only",
    "over","after","before","between","through","during","while","if","when",
    "where","which","who","whom","what","how","all","each","every","more",
    "most","such","own","same","other","another","about","up","out","your",
    "my","their","our","his","her","we","they","he","she","you","i","me",
    "him","us","them","been","being","make","made","get","got","go","comes",
    "new","game","games","play","players","player"  
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

INPUT_FILE  = "data/games_raw.json"
OUTPUT_FILE = "data/games_clean.json"
REPORT_FILE = "data/cleaning_report.txt"


# Preprocessing 
def normalize_text(text: str) -> str:
    """Lowercase and strip extra whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def remove_html(text: str) -> str:
    """Strip any residual HTML tags."""
    return re.sub(r"<[^>]+>", "", text)


def remove_special_chars(text: str) -> str:
    """Keep only alphanumeric and basic punctuation."""
    return re.sub(r"[^a-z0-9\s\.\,\!\?\-\']", "", text)


def tokenize(text: str) -> list[str]:
    """Split text into word tokens."""
    return re.findall(r"\b[a-z][a-z0-9\']*\b", text)


def remove_stopwords(tokens: list[str]) -> list[str]:
    """Remove stopwords from token list."""
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def preprocess_text(raw: str | None) -> dict:
    """
    Full preprocessing pipeline for a text field.
    Returns a dict with cleaned, tokens, and filtered_tokens.
    """
    if not raw:
        return {"cleaned": None, "tokens": [], "filtered_tokens": []}

    step1 = remove_html(raw)
    step2 = normalize_text(step1)
    step3 = remove_special_chars(step2)
    tokens          = tokenize(step3)
    filtered_tokens = remove_stopwords(tokens)

    return {
        "cleaned":          step3.strip(),
        "tokens":           tokens,
        "filtered_tokens":  filtered_tokens,
        "token_count":      len(tokens),
        "unique_terms":     len(set(filtered_tokens)),
    }


# Field Cleaning 
def clean_score(val) -> int | None:
    """Ensure critic score is int 0–100 or None."""
    if val is None:
        return None
    try:
        v = int(val)
        return v if 0 <= v <= 100 else None
    except (ValueError, TypeError):
        return None


def clean_user_score(val) -> float | None:
    """Ensure user score is float 0–10 or None."""
    if val is None:
        return None
    try:
        v = float(val)
        return round(v, 1) if 0.0 <= v <= 10.0 else None
    except (ValueError, TypeError):
        return None


def clean_date(val) -> str | None:
    """Validate and normalize date to YYYY-MM-DD."""
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None   


def clean_title(val) -> str | None:
    if not val:
        return None
    return re.sub(r"\s+", " ", str(val).strip())


def clean_platform(val) -> str | None:
    if not val:
        return None
    return str(val).strip().title()


def clean_genre(val) -> str | None:
    if not val:
        return None
    genres = [g.strip().title() for g in re.split(r"[,/|]", str(val)) if g.strip()]
    return genres[0] if genres else None   # take primary genre


# Record-Level Cleaning 
def clean_record(raw: dict, idx: int) -> tuple[dict, list[str]]:
    """
    Clean one record. Returns (cleaned_record, list_of_issues).
    """
    issues = []
    rec = dict(raw)   # copy

    # Title 
    rec["title"] = clean_title(rec.get("title"))
    if not rec["title"]:
        issues.append("missing_title")

    # Scores
    rec["critic_score"] = clean_score(rec.get("critic_score"))
    if rec["critic_score"] is None:
        issues.append("missing_critic_score")

    rec["user_score"] = clean_user_score(rec.get("user_score"))
    if rec["user_score"] is None:
        issues.append("missing_user_score")

    # Date 
    rec["release_date"] = clean_date(rec.get("release_date"))
    if not rec["release_date"]:
        issues.append("missing_release_date")

    # Platform / Genre 
    rec["platform"] = clean_platform(rec.get("platform"))
    rec["genre"]    = clean_genre(rec.get("genre"))

    #  Text: summary 
    summary_proc = preprocess_text(rec.get("summary"))
    rec["summary_clean"]          = summary_proc["cleaned"]
    rec["summary_tokens"]         = summary_proc["filtered_tokens"]
    rec["summary_token_count"]    = summary_proc.get("token_count", 0)
    rec["summary_unique_terms"]   = summary_proc.get("unique_terms", 0)

    if not rec.get("summary"):
        issues.append("missing_summary")

    rec["data_issues"] = issues
    return rec, issues


# Duplicate Detection
def remove_duplicates(records: list[dict]) -> tuple[list[dict], int]:
    """Remove duplicate records based on title + platform."""
    seen    = set()
    unique  = []
    removed = 0
    for r in records:
        key = (str(r.get("title", "")).lower(), str(r.get("platform", "")).lower())
        if key in seen:
            removed += 1
        else:
            seen.add(key)
            unique.append(r)
    return unique, removed


# Quality Report
def generate_report(raw_count, clean_count, dup_count, issue_counter, output_path):
    lines = [
        "=" * 60,
        "  CS313x Gaming Review Analyzer — Data Cleaning Report",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
        f"  Raw records       : {raw_count}",
        f"  Duplicates removed: {dup_count}",
        f"  Clean records     : {clean_count}",
        f"  Kept rate         : {clean_count/max(raw_count,1)*100:.1f}%",
        "",
        "  Data Quality Issues Breakdown:",
    ]
    for issue, count in issue_counter.most_common():
        pct = count / max(clean_count, 1) * 100
        lines.append(f"    {issue:<30} {count:>4} records  ({pct:.1f}%)")

    lines += [
        "",
        "  Preprocessing Steps Applied:",
        "    1. HTML tag removal",
        "    2. Lowercasing & whitespace normalization",
        "    3. Special character removal",
        "    4. Tokenization (regex word boundaries)",
        "    5. Stopword removal (custom domain list)",
        "    6. Score range validation (0-100 / 0-10)",
        "    7. Date normalization to YYYY-MM-DD",
        "    8. Duplicate removal (title + platform key)",
        "",
    ]
    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


# Main 
def run():
    os.makedirs("data", exist_ok=True)

    # Load raw data
    if not os.path.exists(INPUT_FILE):
        log.error(f"Input file not found: {INPUT_FILE}")
        log.error("Run scraper.py first to generate raw data.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    log.info(f"Loaded {len(raw_data)} raw records from {INPUT_FILE}")

    # Step 1: Remove duplicates
    deduped, dup_count = remove_duplicates(raw_data)
    log.info(f"Removed {dup_count} duplicates → {len(deduped)} records remaining")

    # Step 2: Clean each record
    cleaned_data  = []
    issue_counter = Counter()

    for i, raw_rec in enumerate(deduped):
        cleaned_rec, issues = clean_record(raw_rec, i)
        cleaned_data.append(cleaned_rec)
        issue_counter.update(issues)

    # Step 3: Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    log.info(f" Saved {len(cleaned_data)} clean records → {OUTPUT_FILE}")

    # Step 4: Report
    generate_report(len(raw_data), len(cleaned_data), dup_count, issue_counter, REPORT_FILE)


if __name__ == "__main__":
    run()
