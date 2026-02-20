"""
Unified Trend Scraper — Step 1 of the Social Media Strategist pipeline.

Pulls trending data from TikTok, Google Trends, and Reddit, normalizes
everything into TrendSignal objects, and writes trends.json.

Usage:
    python trend_scraper.py <business_type> [--country US] [--output trends.json]

Example:
    python trend_scraper.py coffee_shop --country US
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
NICHE_MAPPING_PATH = PROJECT_DIR / "references" / "niche_mapping.json"

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
REDDIT_UA = "SocialStrategistAgent/1.0"
GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss"
RSS_NS = {"ht": "https://trends.google.com/trending/rss"}

RANK_DIFF_LABELS = {1: "UP", 2: "DOWN", 3: "NEW", 4: "STABLE"}


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def classify_trend(values: list[float]) -> str:
    if not values or len(values) < 4:
        return "UNKNOWN"
    first = sum(values[:3]) / 3
    second = sum(values[-3:]) / 3
    peak = values.index(max(values))
    if first == 0 and second == 0:
        return "FLAT"
    if peak in (2, 3) and second < first * 0.5:
        return "SPIKE"
    if second > first * 1.15:
        return "RISING"
    if second < first * 0.8:
        return "DECLINING"
    return "STABLE"


def rank_change_str(rdt: int, rd: int) -> str:
    if rdt == 1:
        return f"+{rd}"
    if rdt == 2:
        return f"-{rd}"
    if rdt == 3:
        return "NEW"
    return "0"


def load_niche_mapping(business_type: str) -> dict:
    with open(NICHE_MAPPING_PATH) as f:
        mapping = json.load(f)
    if business_type not in mapping:
        available = ", ".join(sorted(mapping.keys()))
        print(f"Unknown business type: '{business_type}'")
        print(f"Available: {available}")
        sys.exit(1)
    return mapping[business_type]


# ---------------------------------------------------------------------------
# TikTok Creative Center
# ---------------------------------------------------------------------------

TIKTOK_PAGES = {
    "hashtags": {
        "url": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
        "extractor": "dehydrated",
    },
    "songs": {"prefer_node": True, "node_limit": 10},
    "videos": {"prefer_node": True, "node_limit": 10},
}

NODE_LIST_KEYS = {"songs": "sound_list", "hashtags": "list", "creators": "creators", "videos": "videos"}


def _fetch_node_api(content_type: str, country: str, limit: int = 10) -> dict:
    mjs = SCRIPT_DIR / "tiktok_api.mjs"
    env = {**os.environ, "NODE_TLS_REJECT_UNAUTHORIZED": "0"}
    try:
        r = subprocess.run(
            ["node", str(mjs), content_type, country, str(limit), "7"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if r.returncode != 0:
            return {"error": r.stderr.strip()}
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}


def _extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1)) if m else None


def _normalize_node_item(item: dict) -> dict:
    return {
        "rank": item.get("rank"),
        "title": item.get("title"),
        "author": item.get("author"),
        "duration": item.get("duration"),
        "rankDiff": item.get("rank_diff", 0),
        "rankDiffType": item.get("rank_diff_type", 0),
        "trend": item.get("trend", []),
        "songId": item.get("song_id"),
        "isPromoted": item.get("promoted", False),
        "link": item.get("link"),
        "nickName": item.get("nick_name"),
        "followerCnt": item.get("follower_cnt", 0),
        "likedCnt": item.get("liked_cnt", 0),
        "countryCode": item.get("country_code"),
        **{k: v for k, v in item.items() if k[0].islower() and "_" not in k},
    }


def fetch_tiktok(country: str) -> list[dict]:
    """Fetch all TikTok trending data and return normalized TrendSignal list."""
    signals = []

    # --- Hashtags via SSR ---
    print("  [TikTok] Fetching hashtags (SSR)...")
    try:
        resp = requests.get(TIKTOK_PAGES["hashtags"]["url"], headers={"User-Agent": BROWSER_UA}, timeout=15)
        nd = _extract_next_data(resp.text) if resp.status_code == 200 else None
        if nd:
            queries = nd["props"]["pageProps"]["dehydratedState"]["queries"]
            items = []
            for q in queries:
                sd = q.get("state", {}).get("data", {})
                if isinstance(sd, dict) and "pages" in sd and sd["pages"]:
                    items = sd["pages"][0].get("list", [])
                    break
            for item in items:
                curve = [t["value"] for t in item.get("trend", [])]
                rdt = item.get("rankDiffType", 0)
                rd = item.get("rankDiff", 0)
                signals.append({
                    "id": f"tiktok_hashtag_{slugify(item.get('hashtagName', ''))}",
                    "source": "tiktok",
                    "type": "hashtag",
                    "name": f"#{item.get('hashtagName', '')}",
                    "description": None,
                    "metrics": {
                        "views": item.get("videoViews", 0),
                        "posts": item.get("publishCnt", 0),
                        "rank": item.get("rank"),
                        "rank_change": rank_change_str(rdt, rd),
                    },
                    "trajectory": classify_trend(curve),
                    "trend_curve": curve,
                    "url": None,
                    "related": [],
                })
            print(f"    {len(items)} hashtags")
    except Exception as e:
        print(f"    Hashtags failed: {e}")

    # --- Songs via Node API ---
    print("  [TikTok] Fetching songs (Node API)...")
    raw = _fetch_node_api("songs", country, limit=10)
    if "error" not in raw:
        for item in raw.get("sound_list", []):
            item = _normalize_node_item(item)
            curve = [t["value"] for t in item.get("trend", [])]
            rdt = item.get("rankDiffType", 0)
            rd = item.get("rankDiff", 0)
            signals.append({
                "id": f"tiktok_song_{slugify(item.get('title', ''))}",
                "source": "tiktok",
                "type": "song",
                "name": item.get("title", ""),
                "description": f"{item.get('author', '?')} ({item.get('duration', '?')}s)",
                "metrics": {
                    "rank": item.get("rank"),
                    "rank_change": rank_change_str(rdt, rd),
                    "duration": item.get("duration"),
                },
                "trajectory": classify_trend(curve),
                "trend_curve": curve,
                "url": item.get("link"),
                "related": [],
            })
        print(f"    {len(raw.get('sound_list', []))} songs")
    else:
        print(f"    Songs failed: {raw['error']}")

    # --- Videos via Node API ---
    print("  [TikTok] Fetching videos (Node API)...")
    raw = _fetch_node_api("videos", country, limit=10)
    if "error" not in raw:
        for item in raw.get("videos", []):
            item = _normalize_node_item(item)
            signals.append({
                "id": f"tiktok_video_{slugify(item.get('title', '') or str(item.get('id', '')))}",
                "source": "tiktok",
                "type": "video",
                "name": (item.get("title") or "")[:100],
                "description": f"{item.get('region', '?')}, {item.get('duration', '?')}s",
                "metrics": {
                    "duration": item.get("duration"),
                    "region": item.get("region"),
                },
                "trajectory": "UNKNOWN",
                "trend_curve": [],
                "url": item.get("link"),
                "related": [],
            })
        print(f"    {len(raw.get('videos', []))} videos")
    else:
        print(f"    Videos failed: {raw['error']}")

    return signals


# ---------------------------------------------------------------------------
# Google Trends
# ---------------------------------------------------------------------------

def fetch_google_trends(country: str, keywords: list[str]) -> list[dict]:
    """Fetch Google Trends data: RSS trending + pytrends related queries."""
    signals = []

    # --- RSS trending searches ---
    print("  [Google] Fetching trending searches (RSS)...")
    try:
        resp = requests.get(GOOGLE_TRENDS_RSS, params={"geo": country}, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = root.find("channel").findall("item")
        for item in items:
            title = item.find("title").text or ""
            traffic_el = item.find("ht:approx_traffic", RSS_NS)
            traffic = traffic_el.text if traffic_el is not None else None

            news_items = item.findall("ht:news_item", RSS_NS)
            news_desc = None
            if news_items:
                nt = news_items[0].find("ht:news_item_title", RSS_NS)
                if nt is not None:
                    news_desc = nt.text

            signals.append({
                "id": f"google_trending_{slugify(title)}",
                "source": "google_trends",
                "type": "search_trend",
                "name": title,
                "description": news_desc,
                "metrics": {"search_volume": traffic},
                "trajectory": "UNKNOWN",
                "trend_curve": [],
                "url": None,
                "related": [],
            })
        print(f"    {len(items)} trending searches")
    except Exception as e:
        print(f"    RSS failed: {e}")

    # --- Related queries via pytrends ---
    if HAS_PYTRENDS and keywords:
        print(f"  [Google] Fetching related queries for {keywords[:5]}...")
        try:
            batches = [keywords[i:i + 5] for i in range(0, min(len(keywords), 5), 5)]
            for batch in batches:
                pt = TrendReq(hl="en-US", tz=360)
                pt.build_payload(batch, cat=0, timeframe="today 1-m", geo=country)
                related = pt.related_queries()
                for kw in batch:
                    for qtype in ["top", "rising"]:
                        df = related.get(kw, {}).get(qtype)
                        if df is not None and not df.empty:
                            for _, row in df.head(3).iterrows():
                                query_text = row.get("query", "")
                                signals.append({
                                    "id": f"google_related_{slugify(query_text)}",
                                    "source": "google_trends",
                                    "type": "related_query",
                                    "name": query_text,
                                    "description": f"Related to '{kw}' ({qtype})",
                                    "metrics": {"value": int(row.get("value", 0))},
                                    "trajectory": "RISING" if qtype == "rising" else "UNKNOWN",
                                    "trend_curve": [],
                                    "url": None,
                                    "related": [kw],
                                })
                time.sleep(1)
            count = sum(1 for s in signals if s["type"] == "related_query")
            print(f"    {count} related queries")
        except Exception as e:
            print(f"    Related queries failed: {e}")

    return signals


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

def fetch_reddit(subreddits: list[str]) -> list[dict]:
    """Fetch hot and rising posts from niche-specific subreddits."""
    signals = []
    headers = {"User-Agent": REDDIT_UA}

    for sub in subreddits:
        for listing in ["hot", "rising"]:
            print(f"  [Reddit] r/{sub}/{listing}...")
            try:
                url = f"https://www.reddit.com/r/{sub}/{listing}.json"
                resp = requests.get(url, headers=headers, params={"limit": 10, "t": "week"}, timeout=15)
                if resp.status_code != 200:
                    print(f"    HTTP {resp.status_code}")
                    continue
                posts = resp.json().get("data", {}).get("children", [])
                for p in posts:
                    d = p["data"]
                    title = d.get("title", "")
                    score = d.get("score", 0)
                    if score < 2 and listing == "hot":
                        continue
                    signals.append({
                        "id": f"reddit_{slugify(sub)}_{slugify(title[:40])}",
                        "source": "reddit",
                        "type": "reddit_post",
                        "name": title[:120],
                        "description": f"r/{sub} ({listing})",
                        "metrics": {
                            "score": score,
                            "comments": d.get("num_comments", 0),
                            "upvote_ratio": d.get("upvote_ratio", 0),
                        },
                        "trajectory": "UNKNOWN",
                        "trend_curve": [],
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                        "related": [],
                    })
                print(f"    {len(posts)} posts")
            except Exception as e:
                print(f"    Failed: {e}")
            time.sleep(1)

    return signals


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(signals: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for s in signals:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique.append(s)
    return unique


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(business_type: str, country: str = "US") -> dict:
    niche = load_niche_mapping(business_type)
    print(f"\nScraping trends for: {niche['display_name']} ({country})")
    print("=" * 60)

    all_signals = []

    print("\n--- TikTok Creative Center ---")
    all_signals.extend(fetch_tiktok(country))

    print("\n--- Google Trends ---")
    all_signals.extend(fetch_google_trends(country, niche.get("google_trends_keywords", [])))

    print("\n--- Reddit ---")
    all_signals.extend(fetch_reddit(niche.get("subreddits", [])))

    all_signals = deduplicate(all_signals)

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "business_type": business_type,
        "country": country,
        "niche_config": niche,
        "summary": {
            "total": len(all_signals),
            "by_source": {},
            "by_type": {},
        },
        "trends": all_signals,
    }

    for s in all_signals:
        result["summary"]["by_source"][s["source"]] = result["summary"]["by_source"].get(s["source"], 0) + 1
        result["summary"]["by_type"][s["type"]] = result["summary"]["by_type"].get(s["type"], 0) + 1

    return result


def main():
    parser = argparse.ArgumentParser(description="Unified Trend Scraper")
    parser.add_argument("business_type", help="Business type key from niche_mapping.json")
    parser.add_argument("--country", default="US", help="Country code (default: US)")
    parser.add_argument("--output", default=None, help="Output file path (default: stdout + trends.json)")
    args = parser.parse_args()

    result = run(args.business_type, args.country)

    output_path = args.output or str(PROJECT_DIR / "output" / "trends.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"RESULTS: {result['summary']['total']} trends collected")
    print(f"  By source: {result['summary']['by_source']}")
    print(f"  By type:   {result['summary']['by_type']}")
    print(f"  Written to: {output_path}")


if __name__ == "__main__":
    main()
