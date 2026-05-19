from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


FEATURE_FILE = Path("data/phase2_features.json")
EVALUATION_JSON = Path("data/phase2_evaluation.json")
EVALUATION_REPORT = Path("outputs/phase2_evaluation_report.txt")


def load_payload() -> dict[str, Any]:
    if not FEATURE_FILE.exists():
        raise FileNotFoundError("Phase 2 features not found. Run: python scripts/phase2_features.py")
    return json.loads(FEATURE_FILE.read_text(encoding="utf-8"))


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_recommendation_prediction(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for review in reviews:
        actual = bool(review.get("recommended"))
        predicted = bool(review.get("ai_recommendation_prediction"))
        if actual and predicted:
            tp += 1
        elif not actual and predicted:
            fp += 1
        elif not actual and not predicted:
            tn += 1
        elif actual and not predicted:
            fn += 1

    accuracy = safe_divide(tp + tn, tp + fp + tn + fn)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def evaluate_topics(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    topics = Counter(review.get("primary_topic") or "general" for review in reviews)
    non_general = sum(count for topic, count in topics.items() if topic != "general")
    return {
        "topic_coverage": round(safe_divide(non_general, len(reviews)), 3),
        "topic_counts": dict(topics.most_common()),
    }


def evaluate_summaries(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(str(review.get("review_summary") or "")) for review in reviews]
    non_empty = sum(1 for length in lengths if length > 0)
    return {
        "summary_coverage": round(safe_divide(non_empty, len(reviews)), 3),
        "average_summary_chars": round(mean(lengths), 1) if lengths else 0,
    }


def evaluate_search_queries(reviews: list[dict[str, Any]]) -> dict[str, int]:
    queries = ["story", "performance", "world", "combat", "price", "crash"]
    results = {}
    for query in queries:
        count = 0
        for review in reviews:
            haystack = " ".join([
                str(review.get("title") or ""),
                str(review.get("primary_topic") or ""),
                str(review.get("keyword_string") or ""),
                str(review.get("review_text") or ""),
            ]).lower()
            if query in haystack:
                count += 1
        results[query] = count
    return results


def build_evaluation(payload: dict[str, Any]) -> dict[str, Any]:
    reviews = payload["review_features"]
    return {
        "records_evaluated": len(reviews),
        "recommendation_prediction": evaluate_recommendation_prediction(reviews),
        "topic_classification": evaluate_topics(reviews),
        "summarization": evaluate_summaries(reviews),
        "search_query_coverage": evaluate_search_queries(reviews),
    }


def write_report(evaluation: dict[str, Any]) -> None:
    EVALUATION_REPORT.parent.mkdir(exist_ok=True)
    rec = evaluation["recommendation_prediction"]
    topics = evaluation["topic_classification"]
    summaries = evaluation["summarization"]
    search = evaluation["search_query_coverage"]

    lines = [
        "CS313x Gaming Review Analyzer - Phase 2 Output Evaluation",
        "",
        f"Records evaluated: {evaluation['records_evaluated']}",
        "",
        "AI Sentiment / Recommendation Prediction vs Steam Recommendation",
        f"  Accuracy : {rec['accuracy']:.3f}",
        f"  Precision: {rec['precision']:.3f}",
        f"  Recall   : {rec['recall']:.3f}",
        f"  F1 score : {rec['f1']:.3f}",
        f"  Confusion matrix: TP={rec['true_positive']}, FP={rec['false_positive']}, TN={rec['true_negative']}, FN={rec['false_negative']}",
        "",
        "Topic Classification",
        f"  Topic coverage: {topics['topic_coverage']:.1%} of reviews received a non-general topic.",
    ]
    for topic, count in topics["topic_counts"].items():
        lines.append(f"  {topic:<16} {count}")

    lines += [
        "",
        "Summarization",
        f"  Summary coverage      : {summaries['summary_coverage']:.1%}",
        f"  Average summary length: {summaries['average_summary_chars']} characters",
        "",
        "Search Query Coverage",
    ]
    for query, count in search.items():
        lines.append(f"  {query:<12} {count} matching reviews")

    lines += [
        "",
        "Interpretation",
        "  The Phase 2 system produces measurable outputs: extracted keywords, topic labels, AI sentiment, review summaries, game profiles, and searchable results.",
        "  The recommendation comparison uses the Steam recommended/not recommended label as a practical ground truth for evaluating AI sentiment usefulness.",
    ]

    EVALUATION_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved -> {EVALUATION_JSON}")
    print(f"Saved -> {EVALUATION_REPORT}")


def run() -> dict[str, Any]:
    payload = load_payload()
    evaluation = build_evaluation(payload)
    EVALUATION_JSON.parent.mkdir(exist_ok=True)
    EVALUATION_JSON.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(evaluation)
    return evaluation


if __name__ == "__main__":
    run()
