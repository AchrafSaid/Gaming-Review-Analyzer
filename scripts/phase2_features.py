from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


INPUT_FILE = Path("data/games_clean.json")
FEATURE_FILE = Path("data/phase2_features.json")
REPORT_FILE = Path("outputs/phase2_feature_report.txt")

TOPIC_LEXICON = {
    "story": {"story", "stories", "narrative", "quest", "quests", "character", "characters", "ending", "dialogue", "writing", "lore"},
    "gameplay": {"gameplay", "combat", "fight", "fighting", "mechanic", "mechanics", "controls", "build", "builds", "level", "levels"},
    "performance": {"bug", "bugs", "buggy", "crash", "crashes", "lag", "fps", "performance", "optimization", "stutter", "broken"},
    "world": {"world", "open", "map", "explore", "exploration", "environment", "city", "area", "areas", "immersive"},
    "visual_audio": {"graphics", "visual", "visuals", "art", "music", "sound", "soundtrack", "voice", "animation", "beautiful"},
    "value": {"price", "worth", "money", "sale", "buy", "bought", "refund", "expensive", "cheap", "value"},
    "replayability": {"hours", "time", "replay", "replayable", "again", "grind", "content", "endgame", "long"},
    "multiplayer": {"online", "multiplayer", "coop", "co-op", "server", "servers", "friends", "community", "pvp"},
}

POSITIVE_WORDS = {
    "amazing", "awesome", "beautiful", "best", "better", "brilliant", "classic",
    "enjoy", "enjoyed", "excellent", "fantastic", "fun", "good", "great",
    "incredible", "love", "loved", "masterpiece", "perfect", "recommend",
    "recommended", "solid", "worth", "favorite", "immersive",
}

NEGATIVE_WORDS = {
    "bad", "boring", "broken", "bug", "bugs", "buggy", "crash", "crashes",
    "dead", "disappointing", "hate", "hated", "issue", "issues", "lag",
    "negative", "poor", "refund", "slow", "terrible", "unplayable",
    "worse", "worst", "stutter",
}

NEGATORS = {"not", "no", "never", "didn't", "dont", "don't", "without", "hardly"}


def load_records(path: Path = INPUT_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Clean data not found at {path}. Run scraper.py and cleaner.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def tokenize_text(text: str) -> list[str]:
    return re.findall(r"\b[a-z][a-z0-9']*\b", text.lower())


def review_tokens(record: dict[str, Any]) -> list[str]:
    tokens = record.get("review_tokens")
    if isinstance(tokens, list) and tokens:
        return [str(token).lower() for token in tokens if str(token).strip()]
    return tokenize_text(record.get("review_clean") or record.get("review_text") or "")


def raw_tokens(record: dict[str, Any]) -> list[str]:
    return tokenize_text(record.get("review_clean") or record.get("review_text") or "")


def build_idf(records: list[dict[str, Any]]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for record in records:
        document_frequency.update(set(review_tokens(record)))
    total_docs = max(len(records), 1)
    return {
        term: math.log((total_docs + 1) / (count + 1)) + 1
        for term, count in document_frequency.items()
    }


def topic_scores(tokens: list[str]) -> dict[str, int]:
    token_set = set(tokens)
    return {
        topic: sum(1 for word in token_set if word in words)
        for topic, words in TOPIC_LEXICON.items()
    }


def classify_topic(tokens: list[str]) -> str:
    scores = topic_scores(tokens)
    topic, score = max(scores.items(), key=lambda item: item[1])
    return topic if score > 0 else "general"


def classify_sentiment(tokens: list[str]) -> tuple[float, str, bool]:
    score = 0
    for index, token in enumerate(tokens):
        if token not in POSITIVE_WORDS and token not in NEGATIVE_WORDS:
            continue
        window = tokens[max(0, index - 3):index]
        negated = any(word in NEGATORS for word in window)
        polarity = 1 if token in POSITIVE_WORDS else -1
        if negated:
            polarity *= -1
        score += polarity

    normalized = round(score / max(len(tokens), 1), 3)
    if normalized > 0.01:
        return normalized, "positive", True
    if normalized < -0.01:
        return normalized, "negative", False
    return normalized, "neutral", True


def split_sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in candidates if len(sentence.strip()) >= 20]


def summarize_review(text: str, term_weights: dict[str, float]) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return text[:220].strip()

    best_sentence = sentences[0]
    best_score = -1.0
    for sentence in sentences:
        words = tokenize_text(sentence)
        if not words:
            continue
        score = sum(term_weights.get(word, 0.0) for word in words) / len(words)
        if score > best_score:
            best_score = score
            best_sentence = sentence
    return best_sentence[:240].strip()


def top_tfidf_terms(tokens: list[str], idf: dict[str, float], limit: int = 8) -> list[dict[str, Any]]:
    counts = Counter(tokens)
    total = max(sum(counts.values()), 1)
    scored = []
    for term, count in counts.items():
        score = (count / total) * idf.get(term, 1.0)
        scored.append((term, round(score, 4), count))
    scored.sort(key=lambda item: (item[1], item[2], item[0]), reverse=True)
    return [
        {"term": term, "tfidf": score, "count": count}
        for term, score, count in scored[:limit]
    ]


def build_review_features(records: list[dict[str, Any]], idf: dict[str, float]) -> list[dict[str, Any]]:
    features = []
    for record in records:
        filtered = review_tokens(record)
        all_tokens = raw_tokens(record)
        terms = top_tfidf_terms(filtered, idf)
        term_weight = {item["term"]: item["tfidf"] for item in terms}
        ai_score, ai_label, predicted_recommended = classify_sentiment(all_tokens)
        topic = classify_topic(filtered)

        features.append({
            "id": record.get("id"),
            "app_id": record.get("app_id"),
            "title": record.get("title"),
            "genre": record.get("genre"),
            "recommended": bool(record.get("recommended")),
            "user_score": record.get("user_score"),
            "playtime_hours_at_review": record.get("playtime_hours_at_review"),
            "original_sentiment_label": record.get("sentiment_label"),
            "ai_sentiment_label": ai_label,
            "ai_sentiment_score": ai_score,
            "ai_recommendation_prediction": predicted_recommended,
            "primary_topic": topic,
            "topic_scores": topic_scores(filtered),
            "top_tfidf_terms": terms,
            "keyword_string": ", ".join(item["term"] for item in terms[:5]),
            "review_summary": summarize_review(record.get("review_text") or "", term_weight),
            "review_text": record.get("review_text"),
        })
    return features


def build_game_profiles(records: list[dict[str, Any]], features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_app: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    by_app_features: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_app[record.get("app_id")].append(record)
    for feature in features:
        by_app_features[feature.get("app_id")].append(feature)

    profiles = []
    for app_id, game_records in by_app.items():
        title = game_records[0].get("title")
        feature_records = by_app_features.get(app_id, [])
        token_counter: Counter[str] = Counter()
        topic_counter: Counter[str] = Counter()
        for feature in feature_records:
            topic_counter.update([feature["primary_topic"]])
            for item in feature.get("top_tfidf_terms", []):
                token_counter.update({item["term"]: item["count"]})

        recommended_count = sum(1 for record in game_records if record.get("recommended"))
        sentiment_scores = [float(f.get("ai_sentiment_score") or 0) for f in feature_records]
        playtimes = [float(r.get("playtime_hours_at_review") or 0) for r in game_records]
        top_terms = [term for term, _ in token_counter.most_common(8)]
        top_topics = [topic for topic, _ in topic_counter.most_common(3)]

        profiles.append({
            "app_id": app_id,
            "title": title,
            "genre": game_records[0].get("genre"),
            "review_count": len(game_records),
            "recommended_count": recommended_count,
            "recommendation_rate": round(recommended_count / max(len(game_records), 1), 3),
            "average_ai_sentiment": round(mean(sentiment_scores), 3) if sentiment_scores else 0,
            "average_playtime_hours": round(mean(playtimes), 2) if playtimes else 0,
            "top_terms": top_terms,
            "top_topics": top_topics,
            "insight_summary": make_game_insight(title, top_topics, top_terms, recommended_count, len(game_records)),
        })

    profiles.sort(key=lambda item: (item["review_count"], item["recommendation_rate"]), reverse=True)
    return profiles


def make_game_insight(title: str, topics: list[str], terms: list[str], recommended: int, total: int) -> str:
    topic_text = ", ".join(topic.replace("_", " ") for topic in topics[:2]) or "general feedback"
    term_text = ", ".join(terms[:4]) or "mixed feedback"
    rate = round(100 * recommended / max(total, 1))
    return f"{title}: {rate}% of sampled reviews are recommended. Main discussion themes are {topic_text}; key terms include {term_text}."


def build_feature_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    idf = build_idf(records)
    review_features = build_review_features(records, idf)
    game_profiles = build_game_profiles(records, review_features)

    global_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    for feature in review_features:
        topic_counter.update([feature["primary_topic"]])
        for item in feature["top_tfidf_terms"]:
            global_counter.update({item["term"]: item["count"]})

    return {
        "metadata": {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_file": str(INPUT_FILE),
            "record_count": len(records),
            "feature_methods": [
                "TF-IDF keyword extraction",
                "rule-based topic classification",
                "negation-aware lexicon sentiment classification",
                "extractive review summarization",
                "per-game insight aggregation",
            ],
        },
        "global_terms": [{"term": term, "count": count} for term, count in global_counter.most_common(25)],
        "topic_distribution": [{"topic": topic, "count": count} for topic, count in topic_counter.most_common()],
        "game_profiles": game_profiles,
        "review_features": review_features,
    }


def write_report(payload: dict[str, Any]) -> None:
    REPORT_FILE.parent.mkdir(exist_ok=True)
    lines = [
        "CS313x Gaming Review Analyzer - Phase 2 Feature Extraction Report",
        f"Generated: {payload['metadata']['created_at']}",
        "",
        "Methods Used",
    ]
    for method in payload["metadata"]["feature_methods"]:
        lines.append(f"  - {method}")

    lines += [
        "",
        f"Review records processed: {payload['metadata']['record_count']}",
        f"Game profiles created  : {len(payload['game_profiles'])}",
        "",
        "Top Global TF-IDF Terms",
    ]
    lines.append("  " + ", ".join(f"{item['term']}({item['count']})" for item in payload["global_terms"][:15]))

    lines += ["", "Topic Distribution"]
    for item in payload["topic_distribution"]:
        lines.append(f"  {item['topic']:<16} {item['count']}")

    lines += ["", "Game Insight Samples"]
    for profile in payload["game_profiles"][:8]:
        lines.append(f"  - {profile['insight_summary']}")

    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved -> {FEATURE_FILE}")
    print(f"Saved -> {REPORT_FILE}")


def run() -> dict[str, Any]:
    records = load_records()
    payload = build_feature_payload(records)
    FEATURE_FILE.parent.mkdir(exist_ok=True)
    FEATURE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(payload)
    return payload


if __name__ == "__main__":
    run()
