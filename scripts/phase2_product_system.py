from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


FEATURE_FILE = Path("data/phase2_features.json")
DASHBOARD_FILE = Path("outputs/phase2_dashboard.html")
INSIGHTS_FILE = Path("outputs/phase2_insights.txt")


def load_payload() -> dict[str, Any]:
    if not FEATURE_FILE.exists():
        raise FileNotFoundError("Phase 2 features not found. Run: python scripts/phase2_features.py")
    return json.loads(FEATURE_FILE.read_text(encoding="utf-8"))


def query_terms(query: str) -> list[str]:
    return re.findall(r"\b[a-z][a-z0-9']*\b", query.lower())


def rank_reviews(payload: dict[str, Any], query: str, limit: int = 10) -> list[dict[str, Any]]:
    terms = query_terms(query)
    if not terms:
        return []

    scored = []
    for review in payload["review_features"]:
        haystack = " ".join([
            str(review.get("title") or ""),
            str(review.get("genre") or ""),
            str(review.get("primary_topic") or ""),
            str(review.get("keyword_string") or ""),
            str(review.get("review_text") or ""),
        ]).lower()
        score = sum(haystack.count(term) for term in terms)
        score += sum(3 for item in review.get("top_tfidf_terms", []) if item["term"] in terms)
        if score > 0:
            result = dict(review)
            result["search_score"] = score
            scored.append(result)

    scored.sort(key=lambda item: (item["search_score"], item.get("ai_sentiment_score") or 0), reverse=True)
    return scored[:limit]


def write_insights(payload: dict[str, Any]) -> None:
    INSIGHTS_FILE.parent.mkdir(exist_ok=True)
    reviews = payload["review_features"]
    profiles = payload["game_profiles"]
    recommended = sum(1 for review in reviews if review.get("recommended"))
    negative = sum(1 for review in reviews if review.get("ai_sentiment_label") == "negative")
    topics = payload["topic_distribution"][:5]
    terms = payload["global_terms"][:10]

    lines = [
        "CS313x Gaming Review Analyzer - Phase 2 Product Insights",
        "",
        f"Total analyzed reviews: {len(reviews)}",
        f"Recommendation rate   : {recommended / max(len(reviews), 1):.1%}",
        f"AI negative reviews   : {negative}",
        "",
        "Most Common Topics",
    ]
    for item in topics:
        lines.append(f"  - {item['topic']}: {item['count']} reviews")

    lines += ["", "Top Keywords"]
    lines.append("  " + ", ".join(item["term"] for item in terms))

    lines += ["", "Product Interpretation"]
    for profile in profiles[:6]:
        lines.append(f"  - {profile['insight_summary']}")

    lines += [
        "",
        "How to use the product system",
        "  1. Open outputs/phase2_dashboard.html in a browser.",
        "  2. Search keywords such as story, performance, world, combat, crash, or price.",
        "  3. Filter by topic or AI sentiment to inspect matching reviews and game profiles.",
    ]

    INSIGHTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved -> {INSIGHTS_FILE}")


def dashboard_html(payload: dict[str, Any]) -> str:
    safe_payload = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gaming Review Analyzer - Phase 2</title>
  <style>
    :root {{ --ink:#17212b; --muted:#5f6d7a; --bg:#f6f2ea; --panel:#ffffff; --accent:#0f7c80; --amber:#c27a2c; --line:#ded6ca; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial, sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ background:#10202a; color:#fff; padding:28px 42px; }}
    h1 {{ margin:0 0 8px; font-size:34px; }}
    h2 {{ margin:0 0 14px; font-size:22px; }}
    .sub {{ color:#c9d5df; max-width:920px; line-height:1.45; }}
    main {{ padding:28px 42px 48px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4, minmax(140px,1fr)); gap:14px; margin-bottom:24px; }}
    .metric, .panel, .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }}
    .metric b {{ display:block; font-size:30px; margin-bottom:4px; }}
    .metric span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .controls {{ display:grid; grid-template-columns:2fr 1fr 1fr; gap:12px; margin-bottom:18px; }}
    input, select {{ width:100%; padding:12px 14px; border:1px solid var(--line); border-radius:6px; font-size:15px; background:#fff; }}
    .grid {{ display:grid; grid-template-columns:1.2fr .8fr; gap:18px; align-items:start; }}
    .results {{ display:grid; gap:12px; }}
    .card h3 {{ margin:0 0 8px; font-size:18px; }}
    .meta {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
    .badge {{ display:inline-block; padding:4px 8px; border-radius:999px; background:#e9f3f3; color:var(--accent); font-size:12px; margin-right:6px; }}
    .badge.neg {{ background:#f6e7e9; color:#b54e5a; }}
    .badge.neu {{ background:#f4eee4; color:#936221; }}
    .summary {{ line-height:1.45; }}
    .profiles {{ display:grid; gap:10px; }}
    .profile {{ border-top:1px solid var(--line); padding-top:10px; }}
    .profile:first-child {{ border-top:0; padding-top:0; }}
    .terms {{ color:var(--muted); font-size:13px; }}
    @media (max-width: 900px) {{ .metrics, .controls, .grid {{ grid-template-columns:1fr; }} main, header {{ padding-left:20px; padding-right:20px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Gaming Review Analyzer</h1>
    <div class="sub">Phase 2 product system: searchable review intelligence with TF-IDF keywords, AI sentiment, topic classification, summaries, and game-level insights.</div>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><b id="mReviews">0</b><span>Analyzed reviews</span></div>
      <div class="metric"><b id="mGames">0</b><span>Game profiles</span></div>
      <div class="metric"><b id="mTerms">0</b><span>Feature terms</span></div>
      <div class="metric"><b id="mTopics">0</b><span>Topic classes</span></div>
    </section>
    <section class="panel">
      <h2>Search and filter review intelligence</h2>
      <div class="controls">
        <input id="query" placeholder="Search story, combat, performance, crash, price..." />
        <select id="topic"><option value="">All topics</option></select>
        <select id="sentiment"><option value="">All AI sentiment</option><option>positive</option><option>neutral</option><option>negative</option></select>
      </div>
      <div class="grid">
        <div class="results" id="results"></div>
        <aside class="panel">
          <h2>Game insight profiles</h2>
          <div class="profiles" id="profiles"></div>
        </aside>
      </div>
    </section>
  </main>
  <script>
    const DATA = {safe_payload};
    const reviews = DATA.review_features || [];
    const profiles = DATA.game_profiles || [];
    const topics = [...new Set(reviews.map(r => r.primary_topic).filter(Boolean))].sort();
    document.getElementById('mReviews').textContent = reviews.length;
    document.getElementById('mGames').textContent = profiles.length;
    document.getElementById('mTerms').textContent = (DATA.global_terms || []).length;
    document.getElementById('mTopics').textContent = topics.length;
    for (const topic of topics) {{
      const opt = document.createElement('option');
      opt.value = topic;
      opt.textContent = topic.replaceAll('_', ' ');
      document.getElementById('topic').appendChild(opt);
    }}
    function sentimentBadge(label) {{
      const cls = label === 'negative' ? 'neg' : label === 'neutral' ? 'neu' : '';
      return `<span class="badge ${{cls}}">${{label || 'unknown'}}</span>`;
    }}
    function matchesQuery(review, q) {{
      if (!q) return true;
      const haystack = [review.title, review.genre, review.primary_topic, review.keyword_string, review.review_text].join(' ').toLowerCase();
      return q.toLowerCase().split(/\\s+/).every(term => haystack.includes(term));
    }}
    function render() {{
      const q = document.getElementById('query').value.trim();
      const topic = document.getElementById('topic').value;
      const sentiment = document.getElementById('sentiment').value;
      const filtered = reviews.filter(r => matchesQuery(r, q) && (!topic || r.primary_topic === topic) && (!sentiment || r.ai_sentiment_label === sentiment)).slice(0, 20);
      document.getElementById('results').innerHTML = filtered.map(r => `
        <article class="card">
          <h3>${{r.title || 'Unknown game'}}</h3>
          <div class="meta">${{r.genre || 'unknown genre'}} | topic: ${{(r.primary_topic || 'general').replaceAll('_',' ')}} | score: ${{r.ai_sentiment_score}}</div>
          <div>${{sentimentBadge(r.ai_sentiment_label)}}<span class="badge">${{r.recommended ? 'Steam recommended' : 'Steam not recommended'}}</span></div>
          <p class="summary">${{escapeHtml(r.review_summary || '')}}</p>
          <div class="terms">Keywords: ${{r.keyword_string || 'none'}}</div>
        </article>
      `).join('') || '<div class="card">No matching reviews found.</div>';

      document.getElementById('profiles').innerHTML = profiles.slice(0, 10).map(p => `
        <div class="profile">
          <b>${{p.title}}</b>
          <div class="meta">${{p.review_count}} reviews | recommended: ${{Math.round(p.recommendation_rate * 100)}}%</div>
          <div class="summary">${{escapeHtml(p.insight_summary || '')}}</div>
          <div class="terms">Top terms: ${{(p.top_terms || []).join(', ')}}</div>
        </div>
      `).join('');
    }}
    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[ch]));
    }}
    document.getElementById('query').addEventListener('input', render);
    document.getElementById('topic').addEventListener('change', render);
    document.getElementById('sentiment').addEventListener('change', render);
    render();
  </script>
</body>
</html>
"""


def write_dashboard(payload: dict[str, Any]) -> None:
    DASHBOARD_FILE.parent.mkdir(exist_ok=True)
    DASHBOARD_FILE.write_text(dashboard_html(payload), encoding="utf-8")
    print(f"Saved -> {DASHBOARD_FILE}")


def print_query_results(payload: dict[str, Any], query: str, limit: int) -> None:
    results = rank_reviews(payload, query, limit)
    print(f"Search query: {query}")
    print(f"Matches shown: {len(results)}")
    for index, review in enumerate(results, start=1):
        print(f"\n{index}. {review.get('title')} | {review.get('primary_topic')} | {review.get('ai_sentiment_label')}")
        print(f"   Keywords: {review.get('keyword_string')}")
        print(f"   Summary : {review.get('review_summary')}")


def run(query: str | None = None, limit: int = 10) -> None:
    payload = load_payload()
    write_dashboard(payload)
    write_insights(payload)
    if query:
        print_query_results(payload, query, limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2 product system for searchable game review intelligence")
    parser.add_argument("--query", help="Optional keyword search to run in the terminal")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    run(query=args.query, limit=args.limit)
