from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


INPUT_FILE = Path("data/games_clean.json")
OUTPUT_DIR = Path("outputs")

PALETTE = [
    "#2F6B9A",
    "#5FA35F",
    "#D07A3D",
    "#B54E5A",
    "#7B68A6",
    "#8A7A53",
    "#C06FA5",
    "#5A9BAD",
]


def load_data(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Clean data not found at {path}. Run cleaner.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def field_values(records: Iterable[dict], field: str) -> list:
    return [r.get(field) for r in records if r.get(field) not in (None, "", [])]


def numeric_values(records: Iterable[dict], field: str) -> list[float]:
    values = []
    for record in records:
        value = record.get(field)
        if value in (None, ""):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            pass
    return values


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def safe_median(values: list[float]) -> float:
    return median(values) if values else 0.0


def safe_stdev(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, image_font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=image_font)
    return box[2] - box[0], box[3] - box[1]


def save_chart(image: Image.Image, filename: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    image.save(OUTPUT_DIR / filename)
    print(f"  Saved -> {OUTPUT_DIR / filename}")


def base_canvas(title: str, width: int = 1200, height: int = 720) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = font(34, bold=True)
    tw, _ = text_size(draw, title, title_font)
    draw.text(((width - tw) / 2, 24), title, fill="#111111", font=title_font)
    return image, draw


def draw_vertical_bar_chart(labels: list[str], values: list[int], title: str, ylabel: str, filename: str) -> None:
    image, draw = base_canvas(title)
    axis_font = font(20)
    label_font = font(18)
    value_font = font(20, bold=True)

    left, top, right, bottom = 115, 110, 1120, 610
    draw.line((left, bottom, right, bottom), fill="#222222", width=2)
    draw.line((left, top, left, bottom), fill="#222222", width=2)
    draw.text((30, 340), ylabel, fill="#222222", font=axis_font)

    max_value = max(values) if values else 1
    step_count = 5
    for i in range(step_count + 1):
        y = bottom - (bottom - top) * i / step_count
        val = round(max_value * i / step_count)
        draw.line((left - 6, y, right, y), fill="#E8E8E8", width=1)
        draw.text((70, y - 12), str(val), fill="#333333", font=label_font)

    gap = 44
    bar_width = (right - left - gap * (len(values) + 1)) / max(len(values), 1)
    for i, (label, value) in enumerate(zip(labels, values)):
        x0 = left + gap + i * (bar_width + gap)
        x1 = x0 + bar_width
        y0 = bottom - (bottom - top) * (value / max_value)
        draw.rectangle((x0, y0, x1, bottom), fill=PALETTE[i % len(PALETTE)])
        vw, _ = text_size(draw, str(value), value_font)
        draw.text(((x0 + x1 - vw) / 2, y0 - 30), str(value), fill="#111111", font=value_font)
        lw, _ = text_size(draw, label, label_font)
        draw.text(((x0 + x1 - lw) / 2, bottom + 18), label, fill="#222222", font=label_font)

    save_chart(image, filename)


def draw_horizontal_bar_chart(labels: list[str], values: list[int], title: str, xlabel: str, filename: str) -> None:
    image, draw = base_canvas(title)
    axis_font = font(20)
    label_font = font(18)
    value_font = font(18, bold=True)

    left, top, right, bottom = 310, 110, 1120, 620
    draw.line((left, bottom, right, bottom), fill="#222222", width=2)
    draw.line((left, top, left, bottom), fill="#222222", width=2)

    xw, _ = text_size(draw, xlabel, axis_font)
    draw.text(((left + right - xw) / 2, 660), xlabel, fill="#222222", font=axis_font)

    max_value = max(values) if values else 1
    row_h = (bottom - top) / max(len(values), 1)
    for i, (label, value) in enumerate(zip(labels, values)):
        y0 = top + i * row_h + row_h * 0.18
        y1 = top + (i + 1) * row_h - row_h * 0.18
        x1 = left + (right - left) * (value / max_value)
        draw.rectangle((left, y0, x1, y1), fill=PALETTE[i % len(PALETTE)])
        draw.text((18, y0 + 4), label[:28], fill="#222222", font=label_font)
        draw.text((x1 + 10, y0 + 4), str(value), fill="#111111", font=value_font)

    save_chart(image, filename)


def draw_histogram(values: list[int], title: str, xlabel: str, filename: str) -> None:
    bins = [(0, 9), (10, 19), (20, 29), (30, 39), (40, 59), (60, 89), (90, 10_000)]
    labels = ["0-9", "10-19", "20-29", "30-39", "40-59", "60-89", "90+"]
    counts = []
    for low, high in bins:
        counts.append(sum(1 for value in values if low <= value <= high))
    draw_vertical_bar_chart(labels, counts, title, "Reviews", filename)


def draw_scatter(records: list[dict], filename: str) -> None:
    image, draw = base_canvas("Playtime vs Sentiment")
    axis_font = font(20)
    label_font = font(16)

    left, top, right, bottom = 115, 110, 1120, 610
    draw.line((left, bottom, right, bottom), fill="#222222", width=2)
    draw.line((left, top, left, bottom), fill="#222222", width=2)

    draw.text((480, 660), "Playtime at Review (hours, capped at 200)", fill="#222222", font=axis_font)
    draw.text((24, 340), "Sentiment", fill="#222222", font=axis_font)

    for i in range(6):
        x = left + (right - left) * i / 5
        y = bottom - (bottom - top) * i / 5
        draw.line((x, top, x, bottom + 6), fill="#E8E8E8", width=1)
        draw.line((left - 6, y, right, y), fill="#E8E8E8", width=1)
        draw.text((x - 12, bottom + 10), str(i * 40), fill="#333333", font=label_font)
        sent = -0.1 + i * 0.04
        draw.text((55, y - 10), f"{sent:.2f}", fill="#333333", font=label_font)

    for record in records:
        playtime = min(float(record.get("playtime_hours_at_review") or 0), 200)
        sentiment = max(min(float(record.get("sentiment_score") or 0), 0.1), -0.1)
        x = left + (right - left) * (playtime / 200)
        y = bottom - (bottom - top) * ((sentiment + 0.1) / 0.2)
        color = "#4DA167" if record.get("recommended") else "#C65D5D"
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color, outline="white")

    draw.rectangle((860, 126, 1110, 190), fill="#FFFFFF", outline="#BBBBBB")
    draw.ellipse((880, 145, 892, 157), fill="#4DA167")
    draw.text((902, 138), "Recommended", fill="#222222", font=label_font)
    draw.ellipse((880, 170, 892, 182), fill="#C65D5D")
    draw.text((902, 163), "Not recommended", fill="#222222", font=label_font)

    save_chart(image, filename)


def write_report(records: list[dict]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    user_scores = numeric_values(records, "user_score")
    playtimes = numeric_values(records, "playtime_hours_at_review")
    token_counts = [int(r.get("review_token_count") or 0) for r in records]
    genres = Counter(field_values(records, "genre")).most_common(10)
    games = Counter(field_values(records, "title")).most_common(10)
    sentiments = Counter(field_values(records, "sentiment_label"))

    all_tokens = []
    for record in records:
        all_tokens.extend(record.get("review_tokens", []))
    keywords = Counter(all_tokens).most_common(20)

    lines = [
        "Dataset Overview",
        f"  Total reviews       : {len(records)}",
        f"  Unique games        : {len(set(field_values(records, 'app_id')))}",
        f"  Unique genres       : {len(set(field_values(records, 'genre')))}",
        f"  Recommended reviews : {sum(1 for r in records if r.get('recommended'))}",
        f"  Not recommended     : {sum(1 for r in records if not r.get('recommended'))}",
        "",
        "Score and Text Statistics",
        f"  Mean user score       : {safe_mean(user_scores):.2f}",
        f"  Median user score     : {safe_median(user_scores):.2f}",
        f"  Mean review tokens    : {safe_mean(token_counts):.2f}",
        f"  Median review tokens  : {safe_median(token_counts):.2f}",
        f"  Std dev review tokens : {safe_stdev(token_counts):.2f}",
        f"  Mean playtime hours   : {safe_mean(playtimes):.2f}",
        f"  Median playtime hours : {safe_median(playtimes):.2f}",
        "",
        "Sentiment Labels",
    ]

    for label, count in sentiments.most_common():
        lines.append(f"  {label:<12} {count}")

    lines += ["", "Top Genres"]
    for genre, count in genres:
        lines.append(f"  {genre:<28} {count}")

    lines += ["", "Top Games"]
    for title, count in games:
        lines.append(f"  {title:<40} {count}")

    lines += ["", "Top Review Keywords"]
    row = []
    for word, count in keywords:
        row.append(f"{word}({count})")
    lines.append("  " + ", ".join(row))
    lines.append("")

    report = "\n".join(lines)
    (OUTPUT_DIR / "eda_report.txt").write_text(report, encoding="utf-8")
    print(report)


def run() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    for old_chart in OUTPUT_DIR.glob("*.png"):
        old_chart.unlink()

    records = load_data(INPUT_FILE)
    write_report(records)

    rec_counts = Counter("Recommended" if r.get("recommended") else "Not Recommended" for r in records)
    draw_vertical_bar_chart(
        list(rec_counts.keys()),
        list(rec_counts.values()),
        "Recommendation Distribution",
        "Reviews",
        "01_recommendation_distribution.png",
    )

    sentiment_counts = Counter(field_values(records, "sentiment_label"))
    sentiment_order = [label for label in ["positive", "neutral", "negative"] if label in sentiment_counts]
    draw_vertical_bar_chart(
        sentiment_order,
        [sentiment_counts[label] for label in sentiment_order],
        "Lexicon Sentiment Distribution",
        "Reviews",
        "02_sentiment_distribution.png",
    )

    token_counts = [int(r.get("review_token_count") or 0) for r in records]
    draw_histogram(token_counts, "Review Length Distribution", "Review Tokens", "04_review_length_distribution.png")

    top_genres = Counter(field_values(records, "genre")).most_common(10)
    if top_genres:
        labels, values = zip(*top_genres)
        draw_horizontal_bar_chart(list(labels), list(values), "Top 10 Game Genres", "Number of Reviews", "03_top_genres.png")

    top_games = Counter(field_values(records, "title")).most_common(10)
    if top_games:
        labels, values = zip(*top_games)
        draw_horizontal_bar_chart(list(labels), list(values), "Reviews per Game", "Number of Reviews", "05_reviews_per_game.png")

    draw_scatter(records, "06_playtime_vs_sentiment.png")
    print("\nEDA complete. Reports and charts saved to outputs/.\n")


if __name__ == "__main__":
    run()
