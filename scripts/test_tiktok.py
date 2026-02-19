"""
P0 Test: TikTok Creative Center Scraping

Two methods:
  1. SSR: Parse __NEXT_DATA__ from HTML (no auth, limited items)
     - Hashtags: 20, Songs: 3, Creators: 3, Videos: 5
  2. API via Node.js: tiktok-discovery-api handles signatures (up to 20/60 items)
     - Requires: npm install tiktok-discovery-api

Songs/creators/videos use the Node API for full results; hashtags use SSR (already 20).
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

SCRIPT_DIR = Path(__file__).parent

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}

PAGES = {
    "hashtags": {
        "url": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
        "extractor": "dehydrated",
    },
    "songs": {
        "url": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/music/pc/en",
        "extractor": "direct",
        "list_key": "soundList",
        "prefer_node": True,
        "node_limit": 10,
    },
    "creators": {
        "url": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/creator/pc/en",
        "extractor": "direct",
        "list_key": "creators",
        "prefer_node": True,
        "node_limit": 10,
    },
    "videos": {
        "url": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/pc/en",
        "extractor": "direct",
        "list_key": "videos",
        "prefer_node": True,
        "node_limit": 10,
    },
}


def extract_next_data(html: str) -> dict | None:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if match:
        return json.loads(match.group(1))
    return None


def fetch_via_node_api(content_type: str, country: str = "US", limit: int = 10, period: int = 7) -> dict:
    """Fetch trending data via the Node.js tiktok-discovery-api (handles signatures)."""
    mjs_path = SCRIPT_DIR / "tiktok_api.mjs"
    env = {**os.environ, "NODE_TLS_REJECT_UNAUTHORIZED": "0"}
    try:
        result = subprocess.run(
            ["node", str(mjs_path), content_type, country, str(limit), str(period)],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "Node.js subprocess timed out"}
    except Exception as e:
        return {"error": str(e)}


def normalize_api_item(item: dict) -> dict:
    """Convert snake_case API response keys to camelCase to match SSR format."""
    return {
        "rank": item.get("rank"),
        "title": item.get("title"),
        "author": item.get("author"),
        "duration": item.get("duration"),
        "rankDiff": item.get("rank_diff", 0),
        "rankDiffType": item.get("rank_diff_type", 0),
        "trend": item.get("trend", []),
        "songId": item.get("song_id"),
        "onListTimes": item.get("on_list_times"),
        "isPromoted": item.get("promoted", False),
        "link": item.get("link"),
        # Creator fields
        "nickName": item.get("nick_name"),
        "followerCnt": item.get("follower_cnt", 0),
        "likedCnt": item.get("liked_cnt", 0),
        "countryCode": item.get("country_code"),
        # Pass through any camelCase fields already present
        **{k: v for k, v in item.items() if k[0].islower() and "_" not in k},
    }


NODE_API_LIST_KEYS = {
    "songs": "sound_list",
    "hashtags": "list",
    "creators": "creators",
    "videos": "videos",
}


def scrape_page(name: str, config: dict) -> dict:
    """Scrape a Creative Center page. Uses Node API for songs/creators/videos, SSR for hashtags."""
    print(f"\n{'='*60}")
    print(f"Fetching: {name}")

    use_node = config.get("prefer_node", False)

    if use_node:
        limit = config.get("node_limit", 10)
        print(f"Method: Node.js API (limit={limit})")
        print("-" * 60)

        raw = fetch_via_node_api(name, limit=limit)
        if "error" in raw:
            print(f"Node API failed: {raw['error']}")
            print("Falling back to SSR...")
            use_node = False
        else:
            list_key = NODE_API_LIST_KEYS.get(name, "list")
            raw_items = raw.get(list_key, [])
            items = [normalize_api_item(i) for i in raw_items]
            pagination = raw.get("pagination", {})
            print(f"Items: {len(items)}")
            print(f"Pagination: {pagination}")
            return {
                "status": "SUCCESS",
                "name": name,
                "items": items,
                "pagination": pagination,
            }

    # SSR fallback / primary for hashtags
    print(f"Method: SSR (__NEXT_DATA__)")
    print(f"URL: {config['url']}")
    print("-" * 60)

    try:
        resp = requests.get(config["url"], headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            return {"status": f"HTTP_{resp.status_code}", "name": name, "items": []}

        next_data = extract_next_data(resp.text)
        if not next_data:
            print("__NEXT_DATA__ not found")
            return {"status": "NO_SSR_DATA", "name": name, "items": []}

        page_props = next_data["props"]["pageProps"]

        if config["extractor"] == "dehydrated":
            queries = page_props["dehydratedState"]["queries"]
            for q in queries:
                state_data = q.get("state", {}).get("data", {})
                if isinstance(state_data, dict) and "pages" in state_data:
                    pages = state_data["pages"]
                    if pages:
                        items = pages[0].get("list", [])
                        pagination = pages[0].get("pagination", {})
                        break
            else:
                items, pagination = [], {}
        else:
            data = page_props["data"]
            items = data.get(config["list_key"], [])
            pagination = data.get("pagination", {})

        print(f"Items: {len(items)}")
        print(f"Pagination: {pagination}")

        return {
            "status": "SUCCESS",
            "name": name,
            "items": items,
            "pagination": pagination,
        }
    except Exception as e:
        print(f"ERROR: {e}")
        return {"status": "ERROR", "name": name, "error": str(e), "items": []}


RANK_DIFF_LABELS = {1: "UP", 2: "DOWN", 3: "NEW", 4: "STABLE"}
SPARKLINE_BLOCKS = " ▁▂▃▄▅▆▇█"


def classify_trend(trend_values: list[float]) -> str:
    """Classify a 7-day trend curve into a human-readable trajectory.

    Compares average of first 3 days vs last 3 days.
    Returns one of: RISING, DECLINING, SPIKE, STABLE.
    """
    if not trend_values or len(trend_values) < 4:
        return "UNKNOWN"
    first_half = sum(trend_values[:3]) / 3
    second_half = sum(trend_values[-3:]) / 3
    peak_idx = trend_values.index(max(trend_values))

    if first_half == 0 and second_half == 0:
        return "FLAT"
    if peak_idx in (2, 3) and second_half < first_half * 0.5:
        return "SPIKE"
    if second_half > first_half * 1.15:
        return "RISING"
    if second_half < first_half * 0.8:
        return "DECLINING"
    return "STABLE"


def make_sparkline(values: list[float]) -> str:
    max_v = max(values) if values and max(values) > 0 else 1
    return "".join(SPARKLINE_BLOCKS[min(8, int(v / max_v * 8))] for v in values)


def display_hashtags(items: list):
    print(f"\n  {'Rank':<5} {'Hashtag':<28} {'Views':<15} {'Posts':<10} {'Rank Move':<12} {'7d Curve':<10} {'Signal'}")
    print("  " + "-" * 105)
    for item in items[:15]:
        rank = item.get("rank", "?")
        name = item.get("hashtagName", "N/A")
        views = item.get("videoViews", 0)
        pub_cnt = item.get("publishCnt", 0)
        rdt = item.get("rankDiffType", 0)
        rd = item.get("rankDiff", 0)
        promoted = " [AD]" if item.get("isPromoted") else ""

        rdt_label = RANK_DIFF_LABELS.get(rdt, "?")
        if rdt == 1:
            rank_str = f"UP +{rd}"
        elif rdt == 2:
            rank_str = f"DOWN -{rd}"
        elif rdt == 3:
            rank_str = "NEW"
        else:
            rank_str = "—"

        trend_values = [t["value"] for t in item.get("trend", [])]
        spark = make_sparkline(trend_values)
        signal = classify_trend(trend_values)

        print(f"  #{rank:<4} {name:<28} {views:>13,} {pub_cnt:>9,} {rank_str:<12} {spark:<10} {signal}{promoted}")


def display_songs(items: list):
    print(f"\n  {'Rank':<5} {'Song':<30} {'Artist':<20} {'Dur':<5} {'Rank Move':<12} {'7d Curve':<10} {'Signal'}")
    print("  " + "-" * 95)
    for item in items:
        rank = item.get("rank", "?")
        title = item.get("title", "N/A")[:28]
        author = item.get("author", "N/A")[:18]
        duration = item.get("duration", "?")
        rdt = item.get("rankDiffType", 0)
        rd = item.get("rankDiff", 0)

        if rdt == 1:
            rank_str = f"UP +{rd}"
        elif rdt == 2:
            rank_str = f"DOWN -{rd}"
        elif rdt == 3:
            rank_str = "NEW"
        else:
            rank_str = "—"

        trend_values = [t["value"] for t in item.get("trend", [])]
        spark = make_sparkline(trend_values)
        signal = classify_trend(trend_values)

        print(f"  #{rank:<4} {title:<30} {author:<20} {duration:>3}s {rank_str:<12} {spark:<10} {signal}")


def display_creators(items: list):
    print("\n  Top Trending Creators:")
    for item in items:
        nick = item.get("nickName", "N/A")
        followers = item.get("followerCnt", 0)
        likes = item.get("likedCnt", 0)
        country = item.get("countryCode", "?")
        print(f"    @{nick} ({country}) — {followers:,} followers, {likes:,} likes")


def display_videos(items: list):
    print("\n  Top Trending Videos:")
    for item in items:
        title = item.get("title", "N/A")[:80]
        region = item.get("region", "?")
        duration = item.get("duration", "?")
        print(f"    \"{title}\" ({region}, {duration}s)")


DISPLAY_FNS = {
    "hashtags": display_hashtags,
    "songs": display_songs,
    "creators": display_creators,
    "videos": display_videos,
}


def main():
    print("=" * 60)
    print("TikTok Creative Center — Trend Scraper")
    print("Hashtags: SSR (__NEXT_DATA__) | Songs/Creators/Videos: Node.js API")
    print("=" * 60)

    results = {}
    for name, config in PAGES.items():
        result = scrape_page(name, config)
        results[name] = result
        if result["items"]:
            DISPLAY_FNS[name](result["items"])
        time.sleep(1)

    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        icon = "✓" if result["status"] == "SUCCESS" and result["items"] else "✗"
        count = len(result["items"])
        total = result.get("pagination", {}).get("total", result.get("pagination", {}).get("totalCount", "?"))
        print(f"  {icon} {name}: {result['status']} — {count} items (total available: {total})")

    all_success = all(r["status"] == "SUCCESS" and r["items"] for r in results.values())
    print()
    if all_success:
        print("VERDICT: All content types fetched successfully!")
        print("  - Hashtags: 20 via SSR (no auth)")
        print("  - Songs/Creators/Videos: 10 via Node.js API (signed requests)")
        print("  - No browser automation needed")
    else:
        failures = [n for n, r in results.items() if r["status"] != "SUCCESS" or not r["items"]]
        print(f"VERDICT: Most types OK, but failed for: {failures}")
        print("  Consider SSR fallback or Playwright for failed endpoints")


if __name__ == "__main__":
    main()
