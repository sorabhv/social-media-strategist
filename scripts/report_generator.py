"""
Report Generator — Step 4 of the Social Media Strategist pipeline.

Reads pipeline JSON outputs and renders a self-contained HTML report.
ALWAYS pushes the report to GitHub via the REST API.

Usage:
    python report_generator.py [--output-dir output/]
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"

GITHUB_REPO = "sorabhv/social-media-strategist"
GITHUB_API = "https://api.github.com"

# Default posting times by day (from references/posting_schedule.md)
DEFAULT_POSTING_TIMES = {
    "Monday": "9:00 AM",
    "Tuesday": "10:00 AM",
    "Wednesday": "12:00 PM",
    "Thursday": "2:00 PM",
    "Friday": "10:00 AM",
    "Saturday": "10:00 AM",
    "Sunday": None,
}


def get_trending_songs(trends: dict | None) -> list[dict]:
    """Extract songs with TikTok URLs from trends.json, sorted by trajectory."""
    if not trends:
        return []
    songs = []
    for t in trends.get("trends", []):
        if t.get("type") == "song" and t.get("url"):
            songs.append({
                "name": t.get("name", "Unknown"),
                "url": t["url"],
                "trajectory": t.get("trajectory", "UNKNOWN"),
                "rank_change": t.get("rank_change", 0),
            })
    # Prioritize RISING songs, then by rank_change
    order = {"RISING": 0, "SPIKE": 1, "STABLE": 2, "DECLINING": 3, "FLAT": 4, "UNKNOWN": 5}
    songs.sort(key=lambda s: (order.get(s["trajectory"], 5), -(s.get("rank_change") or 0)))
    return songs


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | None:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def inject_sound_links(content_plan: dict, trends: dict | None) -> dict:
    """Match reel concept sounds to TikTok URLs from trends.json.
    
    This runs at report generation time so it works regardless of
    whether the LLM steps were run locally or by the OpenClaw agent.
    """
    if not trends or not content_plan:
        return content_plan

    # Build lookup: normalized name -> url from all song trends
    url_map = {}
    for t in trends.get("trends", []):
        if t.get("url") and t.get("type") == "song":
            name = t.get("name", "").strip().lower()
            url_map[name] = t["url"]
            # Also index by id for direct matching
            url_map[t["id"]] = t["url"]

    for concept in content_plan.get("reel_concepts", []):
        if concept.get("sound_link"):
            continue  # Already has a link

        # Try matching by trend_id
        tid = concept.get("trend_id", "")
        if tid in url_map:
            concept["sound_link"] = url_map[tid]
            continue

        # Match by sound name (before the " — Artist" part)
        sound = concept.get("sound", "")
        sound_base = sound.split("\u2014")[0].split("\u2013")[0].split(" - ")[0].strip().lower()

        # Skip matching if sound_base is empty or just a dash placeholder
        if not sound_base or sound_base in ("—", "-", "–"):
            continue

        if sound_base in url_map:
            concept["sound_link"] = url_map[sound_base]
            continue

        # Fuzzy fallback: partial match (require at least 3 chars to avoid false positives)
        if len(sound_base) >= 3:
            for trend_name, link in url_map.items():
                if not trend_name.startswith("tiktok_"):  # skip id keys
                    if trend_name in sound_base or sound_base in trend_name:
                        concept["sound_link"] = link
                        break

    return content_plan


def format_views(n) -> str:
    if n is None:
        return "—"
    if isinstance(n, str):
        return n
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def trajectory_badge(t: str) -> str:
    colors = {
        "RISING": ("#34d399", "rgba(16,185,129,0.12)", "rgba(16,185,129,0.25)"),
        "STABLE": ("#60a5fa", "rgba(59,130,246,0.12)", "rgba(59,130,246,0.25)"),
        "DECLINING": ("#fbbf24", "rgba(245,158,11,0.12)", "rgba(245,158,11,0.25)"),
        "SPIKE": ("#f87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.25)"),
        "FLAT": ("#9ca3af", "rgba(156,163,175,0.1)", "rgba(156,163,175,0.2)"),
        "UNKNOWN": ("#9ca3af", "rgba(156,163,175,0.1)", "rgba(156,163,175,0.2)"),
    }
    fg, bg, border = colors.get(t, colors["UNKNOWN"])
    return f'<span class="badge" style="color:{fg};background:{bg};border-color:{border}">{escape(t)}</span>'


def difficulty_badge(d: str) -> str:
    colors = {
        "easy": ("#34d399", "rgba(16,185,129,0.12)", "rgba(16,185,129,0.25)"),
        "medium": ("#fbbf24", "rgba(245,158,11,0.12)", "rgba(245,158,11,0.25)"),
        "hard": ("#f87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.25)"),
    }
    fg, bg, border = colors.get(d, ("#9ca3af", "rgba(156,163,175,0.1)", "rgba(156,163,175,0.2)"))
    return f'<span class="badge" style="color:{fg};background:{bg};border-color:{border}">{escape(d)}</span>'


def content_type_badge(ct: str) -> str:
    colors = {
        "trending": ("#c084fc", "rgba(139,92,246,0.12)", "rgba(139,92,246,0.25)"),
        "evergreen": ("#34d399", "rgba(16,185,129,0.12)", "rgba(16,185,129,0.25)"),
        "engagement": ("#fbbf24", "rgba(245,158,11,0.12)", "rgba(245,158,11,0.25)"),
        "rest": ("#9ca3af", "rgba(156,163,175,0.1)", "rgba(156,163,175,0.2)"),
        "promo": ("#60a5fa", "rgba(59,130,246,0.12)", "rgba(59,130,246,0.25)"),
    }
    fg, bg, border = colors.get(ct, ("#9ca3af", "rgba(156,163,175,0.1)", "rgba(156,163,175,0.2)"))
    return f'<span class="badge" style="color:{fg};background:{bg};border-color:{border}">{escape(ct)}</span>'


def hook_pattern_badge(hp: str) -> str:
    colors = {
        "question": ("#c084fc", "rgba(139,92,246,0.12)", "rgba(139,92,246,0.25)"),
        "challenge": ("#f87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.25)"),
        "controversy": ("#fb923c", "rgba(251,146,60,0.12)", "rgba(251,146,60,0.25)"),
        "tutorial": ("#34d399", "rgba(16,185,129,0.12)", "rgba(16,185,129,0.25)"),
        "before_after": ("#60a5fa", "rgba(59,130,246,0.12)", "rgba(59,130,246,0.25)"),
        "reveal": ("#fbbf24", "rgba(245,158,11,0.12)", "rgba(245,158,11,0.25)"),
        "listicle": ("#a78bfa", "rgba(167,139,250,0.12)", "rgba(167,139,250,0.25)"),
    }
    fg, bg, border = colors.get(hp, ("#9ca3af", "rgba(156,163,175,0.1)", "rgba(156,163,175,0.2)"))
    label = hp.replace("_", "/") if hp else "—"
    return f'<span class="badge" style="color:{fg};background:{bg};border-color:{border}">{escape(label)}</span>'


def source_icon(src: str) -> str:
    icons = {"tiktok": "&#9835;", "google_trends": "&#128270;", "reddit": "&#9650;"}
    return icons.get(src, "&#8226;")


def sparkline_svg(values: list[float], width: int = 80, height: int = 24) -> str:
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    points = []
    for i, v in enumerate(values):
        x = (i / (len(values) - 1)) * width
        y = height - ((v - mn) / rng) * (height - 4) - 2
        points.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(points)
    # Build a gradient fill area
    last_x = (len(values) - 1) / (len(values) - 1) * width
    area_points = poly + f" {last_x:.1f},{height} 0,{height}"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="vertical-align:middle">'
        f'<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.3"/>'
        f'<stop offset="100%" stop-color="#8b5cf6" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{area_points}" fill="url(#sg)"/>'
        f'<polyline points="{poly}" fill="none" stroke="#a78bfa" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


# ---------------------------------------------------------------------------
# HTML sections
# ---------------------------------------------------------------------------

def render_header(trends: dict | None, content_plan: dict | None) -> str:
    biz = "—"
    country = "—"
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    if content_plan:
        biz = content_plan.get("business_type", "—").replace("_", " ").title()
        country = content_plan.get("country", "—")
        ts = content_plan.get("generated_at")
    elif trends:
        biz = trends.get("niche_config", {}).get("display_name", trends.get("business_type", "—"))
        country = trends.get("country", "—")
        ts = trends.get("scraped_at")
    else:
        ts = None

    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            date_str = dt.strftime("%B %d, %Y")
        except Exception:
            pass

    total = ""
    if trends:
        total = f' <span class="subtitle">{trends["summary"]["total"]} trends scanned</span>'

    return f"""
    <header>
        <div class="header-inner">
            <h1>Social Media Content Plan</h1>
            <p class="meta">{escape(biz)} &middot; {escape(country)} &middot; {date_str}{total}</p>
        </div>
    </header>"""


def render_calendar(content_plan: dict, business_type: str = "") -> str:
    calendar = content_plan.get("weekly_calendar", [])
    if not calendar:
        return ""

    cards = ""
    for day in calendar:
        platforms = ", ".join(day.get("platforms", [])) or "—"
        time_str = day.get("time") or ""
        # Fill in default posting time if missing
        if not time_str or time_str == "—":
            day_name = day.get("day", "")
            time_str = DEFAULT_POSTING_TIMES.get(day_name, "—") or "—"
        ct = day.get("content_type", "")
        notes = day.get("notes", "")
        title = day.get("title", "—")
        tips = day.get("platform_tips", {})

        tips_html = ""
        if tips:
            tip_items = ""
            for plat, tip in tips.items():
                if tip:
                    tip_items += f'<li><strong>{escape(plat)}:</strong> {escape(tip)}</li>'
            if tip_items:
                tips_html = f'<ul class="platform-tips">{tip_items}</ul>'

        notes_html = f'<div class="cal-notes">{escape(notes)}{tips_html}</div>' if notes or tips_html else ""

        cards += f"""
            <div class="cal-card type-{escape(ct)}">
                <div class="cal-day">{escape(day.get('day', ''))}</div>
                <div class="cal-title">{escape(title)}</div>
                <div class="cal-meta">
                    <span class="cal-chip">&#128337; {escape(time_str)}</span>
                    <span class="cal-chip">{escape(platforms)}</span>
                    {content_type_badge(ct)}
                </div>
                {notes_html}
            </div>"""

    return f"""
    <section>
        <h2>Weekly Calendar</h2>
        <div class="calendar-grid">{cards}</div>
    </section>"""


def render_reel_concepts(content_plan: dict, trending_songs: list[dict] | None = None) -> str:
    concepts = content_plan.get("reel_concepts", [])
    if not concepts:
        return ""

    cards = ""
    for i, c in enumerate(concepts, 1):
        title = c.get("title", f"Concept {i}")
        hook = c.get("hook", "")
        hp = c.get("hook_pattern", "")
        script = c.get("script", [])
        sound = c.get("sound", "—")
        sound_link = c.get("sound_link")
        caption = c.get("caption", "")
        hashtags_raw = c.get("hashtags", [])
        cta = c.get("cta", "")
        diff = c.get("difficulty", "")
        est = c.get("estimated_time", "")

        steps_html = ""
        for j, step in enumerate(script, 1):
            steps_html += f'<li>{escape(step)}</li>'

        if isinstance(hashtags_raw, dict):
            tags_html = ""
            tier_labels = {"large": "Broad Reach", "medium": "Mid-Tier", "niche": "Niche"}
            for tier in ("large", "medium", "niche"):
                tier_tags = hashtags_raw.get(tier, [])
                if tier_tags:
                    tier_label = tier_labels.get(tier, tier)
                    pills = " ".join(f'<span class="hashtag">{escape(h)}</span>' for h in tier_tags)
                    tags_html += f'<span class="hashtag-tier"><span class="tier-label">{tier_label}:</span> {pills}</span> '
        else:
            tags_html = " ".join(f'<span class="hashtag">{escape(h)}</span>' for h in hashtags_raw)

        cards += f"""
        <div class="card">
            <div class="card-header">
                <h3>Reel #{i}: {escape(title)}</h3>
                <div class="card-badges">{hook_pattern_badge(hp)} {difficulty_badge(diff)} <span class="time-est">{escape(est)}</span></div>
            </div>
            <div class="card-body">
                <div class="hook">
                    <strong>Hook (first 3s):</strong> {escape(hook)}
                </div>
                <div class="script">
                    <strong>Script:</strong>
                    <ol>{steps_html}</ol>
                </div>
                <div class="detail-row">
                    <span class="label">Sound:</span> {f'<a href="{escape(sound_link)}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;border-bottom:1px dashed var(--accent)">{escape(sound)} &#127925;</a>' if sound_link else escape(sound)}
                </div>
                {_render_suggested_sounds(sound, sound_link, trending_songs)}
                <div class="detail-row">
                    <span class="label">Caption:</span> {escape(caption)}
                </div>
                <div class="detail-row hashtags-tiered">
                    <span class="label">Hashtags:</span> {tags_html}
                </div>
                <div class="detail-row">
                    <span class="label">CTA:</span> {escape(cta)}
                </div>
            </div>
        </div>"""

    return f"""
    <section>
        <h2>Reel Concepts</h2>
        <div class="concepts-grid">{cards}</div>
    </section>"""


def _render_suggested_sounds(sound: str, sound_link, trending_songs: list[dict] | None) -> str:
    """Render suggested trending sounds when the reel concept has no sound/link."""
    # Don't show suggestions if a valid sound is already provided
    if sound_link or (sound and sound not in ("—", "-", "–", "", "original audio")):
        return ""
    if not trending_songs:
        return ""

    # Show top 3 trending songs as suggestions
    suggestions = trending_songs[:3]
    if not suggestions:
        return ""

    links = []
    for s in suggestions:
        traj = trajectory_badge(s["trajectory"])
        links.append(
            f'<a href="{escape(s["url"])}" target="_blank" rel="noopener" '
            f'style="color:var(--accent);text-decoration:none;border-bottom:1px dashed var(--accent);">'
            f'{escape(s["name"])} &#127925;</a> {traj}'
        )
    pills_html = " &nbsp;|&nbsp; ".join(links)

    return (
        f'<div class="detail-row" style="margin-top:0.25rem;">'
        f'<span class="label" style="color:var(--text-muted)">Suggested sounds:</span> '
        f'{pills_html}'
        f'</div>'
    )


def render_filtered_trends(filtered: dict) -> str:
    top = filtered.get("top_trends", [])
    if not top:
        return ""

    rows = ""
    for i, t in enumerate(top, 1):
        scores = t.get("scores", {})
        overall = scores.get("overall", 0)
        rows += f"""
            <tr>
                <td>{i}</td>
                <td>{source_icon(t.get('source', ''))} {escape(t.get('name', ''))}</td>
                <td>{escape(t.get('source', ''))}</td>
                <td>{escape(t.get('type', ''))}</td>
                <td><strong>{overall:.1f}</strong></td>
                <td>{scores.get('relevance', '—')}</td>
                <td>{scores.get('virality', '—')}</td>
                <td>{scores.get('difficulty', '—')}</td>
                <td>{scores.get('timeliness', '—')}</td>
                <td class="notes-cell">{escape(t.get('suggested_angle', ''))}</td>
            </tr>"""

    return f"""
    <details>
        <summary>Filtered Trends — Top {len(top)} Scored Trends</summary>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>#</th><th>Trend</th><th>Source</th><th>Type</th>
                        <th>Overall</th><th>Rel</th><th>Viral</th><th>Diff</th><th>Time</th>
                        <th>Suggested Angle</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </details>"""


def render_trend_discovery(trends: dict) -> str:
    summary = trends.get("summary", {})
    by_source = summary.get("by_source", {})
    by_type = summary.get("by_type", {})
    all_trends = trends.get("trends", [])

    source_pills = " ".join(
        f'<span class="pill">{source_icon(s)} {escape(s)}: {c}</span>'
        for s, c in by_source.items()
    )
    type_pills = " ".join(
        f'<span class="pill">{escape(t)}: {c}</span>'
        for t, c in by_type.items()
    )

    rows = ""
    for t in all_trends[:30]:
        metrics = t.get("metrics", {})
        views = metrics.get("views") or metrics.get("search_volume") or metrics.get("score")
        rank_change = metrics.get("rank_change", "")
        curve = t.get("trend_curve", [])

        rows += f"""
            <tr>
                <td>{source_icon(t.get('source', ''))} {escape(t.get('source', ''))}</td>
                <td>{escape(t.get('name', '')[:50])}</td>
                <td>{escape(t.get('type', ''))}</td>
                <td>{format_views(views)}</td>
                <td>{escape(str(rank_change))}</td>
                <td>{trajectory_badge(t.get('trajectory', 'UNKNOWN'))}</td>
                <td>{sparkline_svg(curve)}</td>
            </tr>"""

    return f"""
    <details>
        <summary>Trend Discovery — {summary.get('total', 0)} Signals Collected</summary>
        <div class="summary-pills">
            <strong>By source:</strong> {source_pills}
            &nbsp;&nbsp;<strong>By type:</strong> {type_pills}
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Source</th><th>Name</th><th>Type</th>
                        <th>Views/Score</th><th>Rank Chg</th><th>Trajectory</th><th>7d Curve</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        <p class="muted">Showing top 30 of {summary.get('total', 0)} trends.</p>
    </details>"""


def render_no_data() -> str:
    return """
    <section class="empty-state">
        <h2>No Data Available</h2>
        <p>Run the pipeline first to generate data:</p>
        <pre>python3 scripts/trend_scraper.py coffee_shop --country US
python3 scripts/trend_filter.py
python3 scripts/content_planner.py
python3 scripts/report_generator.py</pre>
    </section>"""


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #0f0f13;
    --bg-secondary: #16161d;
    --surface: rgba(255,255,255,0.04);
    --surface-hover: rgba(255,255,255,0.07);
    --surface-solid: #1c1c26;
    --border: rgba(255,255,255,0.08);
    --border-light: rgba(255,255,255,0.05);
    --text: #e8e8ed;
    --text-secondary: #a0a0b0;
    --text-muted: #6b6b80;
    --accent: #8b5cf6;
    --accent-light: rgba(139,92,246,0.12);
    --accent-glow: rgba(139,92,246,0.25);
    --pink: #ec4899;
    --pink-light: rgba(236,72,153,0.12);
    --amber: #f59e0b;
    --amber-light: rgba(245,158,11,0.12);
    --emerald: #10b981;
    --emerald-light: rgba(16,185,129,0.12);
    --blue: #3b82f6;
    --blue-light: rgba(59,130,246,0.12);
    --radius: 16px;
    --radius-sm: 10px;
    --shadow: 0 4px 24px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
    --shadow-lg: 0 8px 40px rgba(0,0,0,0.4);
    --gradient-hero: linear-gradient(135deg, #1a1033 0%, #0f0f13 50%, #0d1117 100%);
    --gradient-card: linear-gradient(135deg, rgba(139,92,246,0.06) 0%, rgba(236,72,153,0.03) 100%);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

.page-wrapper {
    max-width: 1140px;
    margin: 0 auto;
    padding: 0 1.5rem 3rem;
}

/* ---- HERO HEADER ---- */
header {
    background: var(--gradient-hero);
    border-bottom: 1px solid var(--border);
    padding: 3.5rem 1.5rem 3rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 2.5rem;
}
header::before {
    content: '';
    position: absolute;
    top: -60%;
    left: 50%;
    transform: translateX(-50%);
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%);
    pointer-events: none;
}
header::after {
    content: '';
    position: absolute;
    bottom: -40%;
    right: -10%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(236,72,153,0.08) 0%, transparent 70%);
    pointer-events: none;
}
header .header-inner {
    position: relative;
    z-index: 1;
    max-width: 1140px;
    margin: 0 auto;
}
header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #c084fc 0%, #f472b6 50%, #fb923c 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.6rem;
}
.meta {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 400;
}
.subtitle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--accent-light);
    color: var(--accent);
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    margin-left: 0.5rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    border: 1px solid rgba(139,92,246,0.2);
}

/* ---- SECTION ---- */
section { margin-bottom: 3rem; }
h2 {
    font-size: 1.35rem;
    font-weight: 700;
    margin-bottom: 1.2rem;
    color: var(--text);
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
h2::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 1.2em;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--accent), var(--pink));
    flex-shrink: 0;
}

/* ---- CALENDAR ---- */
.calendar-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
}
.cal-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}
.cal-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}
.cal-card:hover {
    border-color: rgba(139,92,246,0.3);
    background: var(--surface-hover);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(139,92,246,0.1);
}
.cal-card.type-trending::before { background: linear-gradient(90deg, var(--accent), var(--pink)); }
.cal-card.type-evergreen::before { background: linear-gradient(90deg, var(--emerald), #34d399); }
.cal-card.type-engagement::before { background: linear-gradient(90deg, var(--amber), #fbbf24); }
.cal-card.type-rest::before { background: linear-gradient(90deg, #6b7280, #9ca3af); }
.cal-card.type-promo::before { background: linear-gradient(90deg, var(--blue), #60a5fa); }
.cal-day {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
}
.cal-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.75rem;
    line-height: 1.4;
}
.cal-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
}
.cal-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    color: var(--text-secondary);
    background: rgba(255,255,255,0.04);
    padding: 3px 10px;
    border-radius: 6px;
    border: 1px solid var(--border-light);
}
.cal-chip svg { width: 12px; height: 12px; opacity: 0.6; }

/* ---- TABLE (for details/trends) ---- */
.table-wrap { overflow-x: auto; border-radius: var(--radius-sm); }
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
    background: var(--surface-solid);
    border-radius: var(--radius-sm);
    overflow: hidden;
}
th {
    background: rgba(255,255,255,0.04);
    color: var(--text-muted);
    font-weight: 600;
    text-align: left;
    padding: 0.7rem 0.85rem;
    white-space: nowrap;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid var(--border);
}
td {
    padding: 0.65rem 0.85rem;
    border-top: 1px solid var(--border-light);
    vertical-align: top;
    color: var(--text-secondary);
}
tr:hover td { background: rgba(139,92,246,0.04); }
.day-cell { white-space: nowrap; min-width: 80px; color: var(--text); }
.notes-cell { color: var(--text-muted); font-size: 0.8rem; max-width: 280px; }

/* ---- BADGES ---- */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 8px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border: 1px solid transparent;
}

/* ---- CONCEPT CARDS ---- */
.concepts-grid { display: flex; flex-direction: column; gap: 1.5rem; }
.card {
    background: var(--gradient-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    overflow: hidden;
    transition: all 0.25s ease;
}
.card:hover {
    border-color: rgba(139,92,246,0.25);
    box-shadow: var(--shadow-lg), 0 0 40px rgba(139,92,246,0.06);
}
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    background: rgba(255,255,255,0.02);
    border-bottom: 1px solid var(--border);
}
.card-header h3 {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.01em;
}
.card-badges { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
.time-est {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
.card-body {
    padding: 1.25rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
}
.hook {
    background: rgba(245,158,11,0.08);
    padding: 0.75rem 1rem;
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--amber);
    font-size: 0.88rem;
    color: var(--text);
    line-height: 1.5;
}
.hook strong { color: var(--amber); font-weight: 600; }
.script { background: rgba(255,255,255,0.02); border-radius: var(--radius-sm); padding: 0.8rem 1rem; }
.script strong { color: var(--text-secondary); font-weight: 600; font-size: 0.84rem; }
.script ol { padding-left: 1.5rem; margin-top: 0.4rem; }
.script li {
    margin-bottom: 0.35rem;
    font-size: 0.86rem;
    color: var(--text-secondary);
    line-height: 1.5;
}
.script li::marker { color: var(--accent); font-weight: 600; }
.detail-row {
    font-size: 0.86rem;
    padding: 0.3rem 0;
    color: var(--text-secondary);
}
.label {
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-right: 0.3rem;
}
.hashtag {
    display: inline-block;
    background: var(--accent-light);
    color: var(--accent);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    margin: 2px 3px;
    border: 1px solid rgba(139,92,246,0.15);
    font-weight: 500;
    transition: all 0.15s ease;
}
.hashtag:hover { background: rgba(139,92,246,0.2); }

/* ---- DETAILS / EXPANDABLE ---- */
details {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    margin-bottom: 1.2rem;
    overflow: hidden;
}
details summary {
    padding: 1rem 1.5rem;
    font-weight: 600;
    cursor: pointer;
    color: var(--text);
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    transition: background 0.15s ease;
}
details summary::before {
    content: '\\25B6';
    font-size: 0.6rem;
    color: var(--accent);
    transition: transform 0.2s ease;
}
details[open] summary::before { transform: rotate(90deg); }
details summary:hover { background: var(--surface-hover); }
details[open] summary { border-bottom: 1px solid var(--border); }
details > :not(summary) { padding: 0 1.5rem; }
details table { box-shadow: none; }
details .table-wrap { margin: 1rem 0; }
.summary-pills { padding: 1rem 0; font-size: 0.84rem; color: var(--text-secondary); }
.pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    padding: 4px 12px;
    border-radius: 8px;
    font-size: 0.78rem;
    margin: 3px;
    color: var(--text-secondary);
}

/* ---- HASHTAG TIERS ---- */
.hashtags-tiered { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
.hashtag-tier { display: inline-flex; align-items: center; gap: 4px; margin-right: 0.5rem; }
.tier-label {
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ---- PLATFORM TIPS ---- */
.platform-tips {
    list-style: none;
    padding: 0.5rem 0 0 0;
    margin: 0.4rem 0 0 0;
    border-top: 1px dashed var(--border);
    font-size: 0.78rem;
    color: var(--text-muted);
}
.platform-tips li { margin-bottom: 0.25rem; }
.platform-tips li strong { color: var(--accent); font-weight: 600; }

/* ---- MISC ---- */
.muted { color: var(--text-muted); font-size: 0.82rem; padding: 0.5rem 0 1rem; }
.empty-state { text-align: center; padding: 4rem 2rem; }
.empty-state h2::before { display: none; }
.empty-state pre {
    background: var(--surface-solid);
    border: 1px solid var(--border);
    padding: 1.2rem;
    border-radius: var(--radius-sm);
    text-align: left;
    display: inline-block;
    margin-top: 1rem;
    font-size: 0.84rem;
    color: var(--text-secondary);
}

/* ---- FOOTER ---- */
footer {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.78rem;
    margin-top: 3rem;
    padding: 2rem 1rem;
    border-top: 1px solid var(--border);
    background: var(--surface);
}
footer span {
    background: linear-gradient(135deg, var(--accent), var(--pink));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 600;
}

/* ---- RESPONSIVE ---- */
@media (max-width: 700px) {
    header { padding: 2.5rem 1rem 2rem; }
    header h1 { font-size: 1.7rem; }
    .page-wrapper { padding: 0 1rem 2rem; }
    .calendar-grid { grid-template-columns: 1fr; }
    .card-header { flex-direction: column; align-items: flex-start; gap: 0.4rem; padding: 0.8rem 1rem; }
    .card-body { padding: 1rem; }
    th, td { padding: 0.4rem 0.5rem; font-size: 0.78rem; }
}
@media (max-width: 480px) {
    header h1 { font-size: 1.4rem; }
    .cal-card { padding: 1rem; }
}
"""


def build_html(trends: dict | None, filtered: dict | None, content_plan: dict | None) -> str:
    header = render_header(trends, content_plan)
    body_parts = []

    if content_plan:
        # Inject sound URLs from trends.json into reel concepts
        content_plan = inject_sound_links(content_plan, trends)
        biz_type = content_plan.get("business_type", "")
        trending_songs = get_trending_songs(trends)
        body_parts.append(render_calendar(content_plan, business_type=biz_type))
        body_parts.append(render_reel_concepts(content_plan, trending_songs=trending_songs))

    if not body_parts:
        body_parts.append(render_no_data())

    pipeline_parts = []
    if filtered:
        pipeline_parts.append(render_filtered_trends(filtered))
    if trends:
        pipeline_parts.append(render_trend_discovery(trends))

    pipeline_section = ""
    if pipeline_parts:
        pipeline_section = f"""
    <section>
        <h2>Full Pipeline Data</h2>
        {"".join(pipeline_parts)}
    </section>"""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Social Media Content Plan</title>
    <style>{CSS}</style>
</head>
<body>
    {header}
    <div class="page-wrapper">
    {"".join(body_parts)}
    {pipeline_section}
    </div>
    <footer>
        Generated by <span>Social Media Strategist Agent</span> &middot; {now}
    </footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# GitHub push
# ---------------------------------------------------------------------------

def push_to_github(html_content: str, date_str: str):
    """Push report to GitHub. Returns the public HTML URL or raises an error."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "GITHUB_TOKEN environment variable is required but not set. "
            "Please set it before running the report generator."
        )

    file_path = f"reports/{date_str}/report.html"
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    existing_sha = None
    check = requests.get(url, headers=headers, timeout=15)
    if check.status_code == 200:
        existing_sha = check.json().get("sha")
        print(f"  File exists at {file_path}, will update (sha: {existing_sha[:8]}...)")

    encoded = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    payload = {
        "message": f"Update content plan report for {date_str}",
        "content": encoded,
        "branch": "main",
    }
    if existing_sha:
        payload["sha"] = existing_sha

    resp = requests.put(url, headers=headers, json=payload, timeout=30)
    if resp.status_code in (200, 201):
        html_url = resp.json().get("content", {}).get("html_url", "")
        print(f"  ✅ Pushed to GitHub: {html_url}")
        return html_url
    else:
        raise Exception(f"GitHub push failed ({resp.status_code}): {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate HTML report from pipeline output and push to GitHub")
    parser.add_argument("--output-dir", default=None, help="Directory containing pipeline JSON files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    print("Loading pipeline data...")
    trends = load_json(output_dir / "trends.json")
    filtered = load_json(output_dir / "filtered_trends.json")
    content_plan = load_json(output_dir / "content_plan.json")

    loaded = []
    if trends:
        loaded.append(f"trends.json ({trends['summary']['total']} signals)")
    if filtered:
        loaded.append(f"filtered_trends.json ({len(filtered.get('top_trends', []))} top trends)")
    if content_plan:
        loaded.append(f"content_plan.json ({len(content_plan.get('reel_concepts', []))} concepts)")

    if loaded:
        print(f"  Found: {', '.join(loaded)}")
    else:
        print("  No pipeline data found. Generating placeholder report.")

    html = build_html(trends, filtered, content_plan)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_dir = output_dir / date_str
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.html"

    with open(report_path, "w") as f:
        f.write(html)
    print(f"\nReport written to: {report_path}")
    print(f"  Size: {len(html):,} bytes")

    # Save a local copy to OpenClaw memory for future reference
    openclaw_memory_dir = (
        Path.home()
        / ".openclaw"
        / "skills"
        / "social-media-strategist"
        / "memory"
        / "reports"
        / date_str
    )
    openclaw_memory_dir.mkdir(parents=True, exist_ok=True)
    openclaw_report_path = openclaw_memory_dir / "report.html"
    with open(openclaw_report_path, "w") as f:
        f.write(html)
    print(f"  Memory copy: {openclaw_report_path}")

    # Also save a summary JSON for quick agent lookback
    summary = {
        "date": date_str,
        "business_type": content_plan.get("business_type", "unknown") if content_plan else "unknown",
        "country": content_plan.get("country", "US") if content_plan else "US",
        "num_concepts": len(content_plan.get("reel_concepts", [])) if content_plan else 0,
        "num_calendar_days": len(content_plan.get("weekly_calendar", [])) if content_plan else 0,
        "num_trends": trends["summary"]["total"] if trends else 0,
        "report_path": str(openclaw_report_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = openclaw_memory_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Memory summary: {summary_path}")

    print("\nPushing to GitHub (mandatory)...")
    try:
        github_url = push_to_github(html, date_str)
        print(f"\n🎉 SUCCESS! View your report at:\n   {github_url}")
        return github_url
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nThe report was saved locally but could not be pushed to GitHub.")
        print(f"Local path: {report_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
