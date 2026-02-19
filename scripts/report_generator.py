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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | None:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


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
        "RISING": ("#065f46", "#d1fae5"),
        "STABLE": ("#1e40af", "#dbeafe"),
        "DECLINING": ("#92400e", "#fef3c7"),
        "SPIKE": ("#7c2d12", "#ffe4e6"),
        "FLAT": ("#6b7280", "#f3f4f6"),
        "UNKNOWN": ("#6b7280", "#f3f4f6"),
    }
    fg, bg = colors.get(t, colors["UNKNOWN"])
    return f'<span class="badge" style="color:{fg};background:{bg}">{escape(t)}</span>'


def difficulty_badge(d: str) -> str:
    colors = {
        "easy": ("#065f46", "#d1fae5"),
        "medium": ("#92400e", "#fef3c7"),
        "hard": ("#991b1b", "#ffe4e6"),
    }
    fg, bg = colors.get(d, ("#6b7280", "#f3f4f6"))
    return f'<span class="badge" style="color:{fg};background:{bg}">{escape(d)}</span>'


def content_type_badge(ct: str) -> str:
    colors = {
        "trending": ("#7c3aed", "#ede9fe"),
        "evergreen": ("#065f46", "#d1fae5"),
        "engagement": ("#b45309", "#fef3c7"),
        "rest": ("#6b7280", "#f3f4f6"),
        "promo": ("#1e40af", "#dbeafe"),
    }
    fg, bg = colors.get(ct, ("#6b7280", "#f3f4f6"))
    return f'<span class="badge" style="color:{fg};background:{bg}">{escape(ct)}</span>'


def hook_pattern_badge(hp: str) -> str:
    colors = {
        "question": ("#7c3aed", "#ede9fe"),
        "challenge": ("#b91c1c", "#ffe4e6"),
        "controversy": ("#c2410c", "#fff7ed"),
        "tutorial": ("#065f46", "#d1fae5"),
        "before_after": ("#1e40af", "#dbeafe"),
        "reveal": ("#a16207", "#fef3c7"),
        "listicle": ("#6d28d9", "#f5f3ff"),
    }
    fg, bg = colors.get(hp, ("#6b7280", "#f3f4f6"))
    label = hp.replace("_", "/") if hp else "—"
    return f'<span class="badge" style="color:{fg};background:{bg}">{escape(label)}</span>'


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
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="vertical-align:middle">'
        f'<polyline points="{poly}" fill="none" stroke="#6366f1" stroke-width="2" '
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
        <h1>Social Media Content Plan</h1>
        <p class="meta">{escape(biz)} &middot; {escape(country)} &middot; {date_str}{total}</p>
    </header>"""


def render_calendar(content_plan: dict) -> str:
    calendar = content_plan.get("weekly_calendar", [])
    if not calendar:
        return ""

    rows = ""
    for day in calendar:
        platforms = ", ".join(day.get("platforms", [])) or "—"
        time_str = day.get("time") or "—"
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

        rows += f"""
            <tr>
                <td class="day-cell"><strong>{escape(day.get('day', ''))}</strong></td>
                <td>{escape(title)}</td>
                <td>{escape(time_str)}</td>
                <td>{escape(platforms)}</td>
                <td>{content_type_badge(ct)}</td>
                <td class="notes-cell">{escape(notes)}{tips_html}</td>
            </tr>"""

    return f"""
    <section>
        <h2>Weekly Calendar</h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Day</th><th>Content</th><th>Time</th>
                        <th>Platforms</th><th>Type</th><th>Notes / Platform Tips</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </section>"""


def render_reel_concepts(content_plan: dict) -> str:
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
                    <span class="label">Sound:</span> {escape(sound)}
                </div>
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
:root {
    --bg: #f8fafc;
    --surface: #ffffff;
    --border: #e2e8f0;
    --text: #1e293b;
    --text-muted: #64748b;
    --accent: #6366f1;
    --accent-light: #eef2ff;
    --radius: 10px;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem 1rem;
    max-width: 1100px;
    margin: 0 auto;
}
header {
    text-align: center;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid var(--border);
}
header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 0.3rem;
}
.meta { color: var(--text-muted); font-size: 0.95rem; }
.subtitle {
    display: inline-block;
    background: var(--accent-light);
    color: var(--accent);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    margin-left: 0.5rem;
    font-weight: 600;
}
section { margin-bottom: 2.5rem; }
h2 {
    font-size: 1.3rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: var(--text);
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--accent-light);
}
.table-wrap { overflow-x: auto; }
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    background: var(--surface);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
}
th {
    background: var(--accent-light);
    color: var(--accent);
    font-weight: 600;
    text-align: left;
    padding: 0.65rem 0.75rem;
    white-space: nowrap;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
td {
    padding: 0.6rem 0.75rem;
    border-top: 1px solid var(--border);
    vertical-align: top;
}
tr:hover td { background: #fafaff; }
.day-cell { white-space: nowrap; min-width: 80px; }
.notes-cell { color: var(--text-muted); font-size: 0.82rem; max-width: 250px; }
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.concepts-grid { display: flex; flex-direction: column; gap: 1.2rem; }
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    overflow: hidden;
}
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.8rem 1.2rem;
    background: var(--accent-light);
    border-bottom: 1px solid var(--border);
}
.card-header h3 {
    font-size: 1rem;
    color: var(--accent);
    margin: 0;
}
.card-badges { display: flex; align-items: center; gap: 0.5rem; }
.time-est { font-size: 0.8rem; color: var(--text-muted); }
.card-body { padding: 1rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }
.hook {
    background: #fffbeb;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    border-left: 3px solid #f59e0b;
    font-size: 0.9rem;
}
.script ol { padding-left: 1.5rem; margin-top: 0.3rem; }
.script li { margin-bottom: 0.2rem; font-size: 0.88rem; }
.detail-row { font-size: 0.88rem; }
.label { font-weight: 600; color: var(--text-muted); }
.hashtag {
    display: inline-block;
    background: var(--accent-light);
    color: var(--accent);
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 0.8rem;
    margin: 1px 2px;
}
details {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    margin-bottom: 1.2rem;
}
details summary {
    padding: 0.8rem 1.2rem;
    font-weight: 600;
    cursor: pointer;
    color: var(--accent);
    font-size: 0.95rem;
}
details summary:hover { background: var(--accent-light); }
details[open] summary { border-bottom: 1px solid var(--border); }
details > :not(summary) { padding: 0 1.2rem; }
details table { box-shadow: none; }
details .table-wrap { margin: 0.8rem 0; }
.summary-pills { padding: 0.8rem 0; font-size: 0.85rem; }
.pill {
    display: inline-block;
    background: var(--bg);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.8rem;
    margin: 2px;
}
.hashtags-tiered { display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: baseline; }
.hashtag-tier { display: inline-flex; align-items: baseline; gap: 3px; margin-right: 0.5rem; }
.tier-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.platform-tips {
    list-style: none;
    padding: 0.4rem 0 0 0;
    margin: 0.3rem 0 0 0;
    border-top: 1px dashed var(--border);
    font-size: 0.78rem;
    color: var(--text-muted);
}
.platform-tips li { margin-bottom: 0.2rem; }
.platform-tips li strong { color: var(--accent); font-weight: 600; }
.muted { color: var(--text-muted); font-size: 0.82rem; padding: 0.5rem 0 1rem; }
.empty-state { text-align: center; padding: 3rem; }
.empty-state pre {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 1rem;
    border-radius: var(--radius);
    text-align: left;
    display: inline-block;
    margin-top: 1rem;
    font-size: 0.85rem;
}
footer {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
}
@media (max-width: 700px) {
    body { padding: 1rem 0.5rem; }
    .card-header { flex-direction: column; align-items: flex-start; gap: 0.3rem; }
    th, td { padding: 0.4rem 0.5rem; font-size: 0.8rem; }
}
"""


def build_html(trends: dict | None, filtered: dict | None, content_plan: dict | None) -> str:
    header = render_header(trends, content_plan)
    body_parts = []

    if content_plan:
        body_parts.append(render_calendar(content_plan))
        body_parts.append(render_reel_concepts(content_plan))

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
    {"".join(body_parts)}
    {pipeline_section}
    <footer>
        Generated by Social Media Strategist Agent &middot; {now}
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
