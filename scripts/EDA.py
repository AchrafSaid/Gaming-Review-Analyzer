"""
eda.py
------
CS313x - Gaming Review Analyzer | Phase 1
Exploratory Data Analysis + Visualizations

Produces:
  - Summary statistics (scores, counts, dates)
  - Top genres, platforms, developers
  - Keyword frequency analysis
  - 5 charts saved to outputs/
  - Printed EDA report

Usage:
    python eda.py
"""

import json
import os
import re
from collections import Counter
from datetime import datetime

import matplotlib
matplotlib.use("Agg")                  # non-interactive backend (no display needed)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

INPUT_FILE  = "data/games_clean.json"
OUTPUT_DIR  = "outputs"

# ── Color Palette ─────────────────────────────────────────────────
PALETTE = ["#4C72B0","#DD8452","#55A868","#C44E52","#8172B2",
           "#937860","#DA8BC3","#8C8C8C","#CCB974","#64B5CD"]


# ── Data Loading ──────────────────────────────────────────────────
def load_data(path: str) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Clean data not found at {path}. Run cleaner.py first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_field(records, field, cast=None) -> list:
    """Return non-null values of a field, optionally cast."""
    out = []
    for r in records:
        v = r.get(field)
        if v is not None:
            try:
                out.append(cast(v) if cast else v)
            except (ValueError, TypeError):
                pass
    return out


# ── Stats Helpers ─────────────────────────────────────────────────
def mean(vals):   return sum(vals) / len(vals) if vals else 0
def median(vals):
    if not vals: return 0
    s = sorted(vals)
    n = len(s)
    return (s[n//2] + s[n//2-1]) / 2 if n % 2 == 0 else s[n//2]
def stdev(vals):
    if len(vals) < 2: return 0
    m = mean(vals)
    return (sum((v-m)**2 for v in vals) / (len(vals)-1)) ** 0.5


# ── Chart Helpers ─────────────────────────────────────────────────
def save_fig(name: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, name)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  📊 Saved → {path}")


# ── Chart 1: Critic Score Distribution ───────────────────────────
def plot_critic_distribution(critic_scores: list[int]):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(critic_scores, bins=20, color=PALETTE[0], edgecolor="white", linewidth=0.6)
    ax.axvline(mean(critic_scores),   color="red",    linestyle="--", linewidth=1.5,
               label=f"Mean: {mean(critic_scores):.1f}")
    ax.axvline(median(critic_scores), color="orange", linestyle=":",  linewidth=1.5,
               label=f"Median: {median(critic_scores):.1f}")
    ax.set_title("Critic Score Distribution", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Critic Score (0–100)", fontsize=11)
    ax.set_ylabel("Number of Games",      fontsize=11)
    ax.legend()
    ax.set_facecolor("#F8F8F8")
    fig.patch.set_facecolor("white")
    save_fig("01_critic_score_distribution.png")


# ── Chart 2: User Score Distribution ─────────────────────────────
def plot_user_distribution(user_scores: list[float]):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(user_scores, bins=20, color=PALETTE[1], edgecolor="white", linewidth=0.6)
    ax.axvline(mean(user_scores),   color="red",    linestyle="--", linewidth=1.5,
               label=f"Mean: {mean(user_scores):.2f}")
    ax.axvline(median(user_scores), color="orange", linestyle=":",  linewidth=1.5,
               label=f"Median: {median(user_scores):.2f}")
    ax.set_title("User Score Distribution", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("User Score (0–10)", fontsize=11)
    ax.set_ylabel("Number of Games",   fontsize=11)
    ax.legend()
    ax.set_facecolor("#F8F8F8")
    save_fig("02_user_score_distribution.png")


# ── Chart 3: Top 10 Genres ────────────────────────────────────────
def plot_top_genres(records):
    genres  = extract_field(records, "genre")
    counter = Counter(genres).most_common(10)
    if not counter:
        print("  ⚠️  No genre data to plot.")
        return
    labels, values = zip(*counter)
    colors = PALETTE[:len(labels)]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], edgecolor="white")
    ax.bar_label(bars, padding=4, fontsize=9)
    ax.set_title("Top 10 Game Genres", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Number of Games", fontsize=11)
    ax.set_facecolor("#F8F8F8")
    save_fig("03_top_genres.png")


# ── Chart 4: Games per Platform ──────────────────────────────────
def plot_platform_breakdown(records):
    platforms = extract_field(records, "platform")
    counter   = Counter(platforms).most_common(8)
    if not counter:
        print("  ⚠️  No platform data to plot.")
        return
    labels, values = zip(*counter)
    colors = PALETTE[:len(labels)]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=140,
        pctdistance=0.82, labeldistance=1.08
    )
    for t in autotexts: t.set_fontsize(9)
    ax.set_title("Games by Platform", fontsize=14, fontweight="bold", pad=16)
    save_fig("04_platform_breakdown.png")


# ── Chart 5: Critic vs User Score Scatter ────────────────────────
def plot_score_correlation(records):
    pairs = [(r["critic_score"], r["user_score"] * 10)   # scale user to 0-100
             for r in records
             if r.get("critic_score") is not None
             and r.get("user_score") is not None]
    if len(pairs) < 5:
        print("  ⚠️  Not enough data for correlation plot.")
        return
    cx, uy = zip(*pairs)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(cx, uy, alpha=0.55, color=PALETTE[4], edgecolors="white", linewidths=0.4, s=50)

    # Trend line (simple linear regression)
    n   = len(cx)
    sx  = sum(cx);   sy  = sum(uy)
    sxy = sum(x*y for x,y in zip(cx,uy))
    sx2 = sum(x*x for x in cx)
    if n * sx2 - sx**2 != 0:
        m = (n*sxy - sx*sy) / (n*sx2 - sx**2)
        b = (sy - m*sx) / n
        xs = [min(cx), max(cx)]
        ys = [m*x + b for x in xs]
        ax.plot(xs, ys, color="red", linewidth=1.5, linestyle="--", label="Trend line")
        ax.legend()

    ax.set_title("Critic Score vs User Score (scaled 0–100)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Critic Score", fontsize=11)
    ax.set_ylabel("User Score (×10)", fontsize=11)
    ax.set_facecolor("#F8F8F8")
    save_fig("05_score_correlation.png")


# ── Keyword Frequency ─────────────────────────────────────────────
def keyword_frequency(records, top_n=20) -> Counter:
    all_tokens = []
    for r in records:
        all_tokens.extend(r.get("summary_tokens", []))
    return Counter(all_tokens).most_common(top_n)


# ── Printed EDA Report ────────────────────────────────────────────
def print_report(records, critic_scores, user_scores):
    print("\n" + "="*60)
    print("  CS313x Gaming Review Analyzer — EDA Report")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    print(f"\n  📦 Dataset Overview")
    print(f"     Total records    : {len(records)}")
    print(f"     With critic score: {len(critic_scores)}")
    print(f"     With user score  : {len(user_scores)}")

    if critic_scores:
        print(f"\n  🎯 Critic Score Stats (0–100)")
        print(f"     Mean   : {mean(critic_scores):.2f}")
        print(f"     Median : {median(critic_scores):.2f}")
        print(f"     Std Dev: {stdev(critic_scores):.2f}")
        print(f"     Min    : {min(critic_scores)}")
        print(f"     Max    : {max(critic_scores)}")
        bins = {"<50":0, "50-59":0, "60-69":0, "70-79":0, "80-89":0, "90+":0}
        for s in critic_scores:
            if   s < 50: bins["<50"] += 1
            elif s < 60: bins["50-59"] += 1
            elif s < 70: bins["60-69"] += 1
            elif s < 80: bins["70-79"] += 1
            elif s < 90: bins["80-89"] += 1
            else:        bins["90+"] += 1
        print(f"     Distribution: {bins}")

    if user_scores:
        print(f"\n  👤 User Score Stats (0–10)")
        print(f"     Mean   : {mean(user_scores):.2f}")
        print(f"     Median : {median(user_scores):.2f}")
        print(f"     Std Dev: {stdev(user_scores):.2f}")

    # Top genres
    genres = Counter(extract_field(records, "genre")).most_common(5)
    if genres:
        print(f"\n  🎮 Top 5 Genres")
        for g, c in genres:
            print(f"     {g:<25} {c} games")

    # Top platforms
    platforms = Counter(extract_field(records, "platform")).most_common(5)
    if platforms:
        print(f"\n  🖥️  Top 5 Platforms")
        for p, c in platforms:
            print(f"     {p:<25} {c} games")

    # Top developers
    devs = Counter(extract_field(records, "developer")).most_common(5)
    if devs:
        print(f"\n  🏢 Top 5 Developers")
        for d, c in devs:
            print(f"     {d:<25} {c} games")

    # Keywords
    print(f"\n  🔑 Top 20 Keywords (from summaries)")
    kw = keyword_frequency(records, 20)
    row = ""
    for i, (word, count) in enumerate(kw):
        row += f"{word}({count})  "
        if (i+1) % 5 == 0:
            print(f"     {row.strip()}")
            row = ""
    if row:
        print(f"     {row.strip()}")

    print("\n" + "="*60 + "\n")


# ── Main ──────────────────────────────────────────────────────────
def run():
    records       = load_data(INPUT_FILE)
    critic_scores = extract_field(records, "critic_score", int)
    user_scores   = extract_field(records, "user_score",   float)

    print_report(records, critic_scores, user_scores)

    print("  📊 Generating charts...")
    if critic_scores: plot_critic_distribution(critic_scores)
    if user_scores:   plot_user_distribution(user_scores)
    plot_top_genres(records)
    plot_platform_breakdown(records)
    if critic_scores and user_scores:
        plot_score_correlation(records)

    print("\n  ✅  EDA complete. Charts saved to outputs/\n")


if __name__ == "__main__":
    run()