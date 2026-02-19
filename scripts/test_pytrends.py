"""
P0 Test: Google Trends
Methods:
  - RSS feed (trends.google.com/trending/rss) for real-time trending searches
  - pytrends library for interest_over_time and related_queries
"""

import time
import xml.etree.ElementTree as ET

import requests
from pytrends.request import TrendReq

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss"
RSS_NS = {"ht": "https://trends.google.com/trending/rss"}


def test_trending_searches_rss(geo: str = "US"):
    """Get today's trending searches via the Google Trends RSS feed."""
    print("\n" + "=" * 60)
    print(f"Test 1: Trending Searches via RSS (geo={geo})")
    print("-" * 60)

    try:
        resp = requests.get(
            GOOGLE_TRENDS_RSS,
            params={"geo": geo},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = root.find("channel").findall("item")

        print(f"Returned {len(items)} trending searches")
        for i, item in enumerate(items, 1):
            title = item.find("title").text
            traffic_el = item.find("ht:approx_traffic", RSS_NS)
            traffic = traffic_el.text if traffic_el is not None else "N/A"

            news_items = item.findall("ht:news_item", RSS_NS)
            news_title = ""
            if news_items:
                nt = news_items[0].find("ht:news_item_title", RSS_NS)
                if nt is not None:
                    news_title = nt.text[:70]

            print(f"  {i:>2}. {title} ({traffic} searches)")
            if news_title:
                print(f"      └ {news_title}")

        return {"status": "SUCCESS", "count": len(items)}
    except Exception as e:
        print(f"FAILED: {e}")
        return {"status": "FAILED", "error": str(e)}


def test_trending_multi_geo():
    """Verify RSS works across multiple countries."""
    print("\n" + "=" * 60)
    print("Test 2: Trending Searches — Multi-Geo")
    print("-" * 60)

    geos = ["US", "GB", "IN", "CA", "AU"]
    results = {}
    for geo in geos:
        try:
            resp = requests.get(
                GOOGLE_TRENDS_RSS,
                params={"geo": geo},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            items = root.find("channel").findall("item")
            top = items[0].find("title").text if items else "N/A"
            results[geo] = len(items)
            print(f"  {geo}: {len(items)} trends (top: \"{top}\")")
        except Exception as e:
            results[geo] = 0
            print(f"  {geo}: FAILED — {e}")
        time.sleep(0.5)

    success = sum(1 for v in results.values() if v > 0)
    return {"status": "SUCCESS" if success >= 4 else "FAILED", "geos_ok": success}


def test_interest_over_time():
    """Test interest over time for sample keywords relevant to small business content."""
    print("\n" + "=" * 60)
    print("Test 3: Interest Over Time (pytrends)")
    print("-" * 60)

    keywords = ["coffee shop", "small business", "reels ideas"]
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(keywords, cat=0, timeframe="now 7-d", geo="US")
        df = pytrends.interest_over_time()
        print(f"Returned {len(df)} data points")
        print(f"Columns: {list(df.columns)}")
        if not df.empty:
            print(f"\nLatest values:")
            latest = df.iloc[-1]
            for kw in keywords:
                print(f"  {kw}: {latest[kw]}")
            print(f"\nPeak values:")
            for kw in keywords:
                print(f"  {kw}: {df[kw].max()} (at {df[kw].idxmax()})")
        return {"status": "SUCCESS", "rows": len(df)}
    except Exception as e:
        print(f"FAILED: {e}")
        return {"status": "FAILED", "error": str(e)}


def test_related_queries():
    """Test related queries — useful for content ideation."""
    print("\n" + "=" * 60)
    print("Test 4: Related Queries (pytrends)")
    print("-" * 60)

    keyword = "trending reels"
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], cat=0, timeframe="today 1-m", geo="US")
        related = pytrends.related_queries()
        print(f"Keyword: {keyword}")

        for qtype in ["top", "rising"]:
            df = related[keyword].get(qtype)
            if df is not None and not df.empty:
                print(f"\n  {qtype.upper()} related queries ({len(df)} results):")
                for _, row in df.head(5).iterrows():
                    print(f"    - {row['query']} (value: {row['value']})")
            else:
                print(f"\n  {qtype.upper()}: No data")

        return {"status": "SUCCESS"}
    except Exception as e:
        print(f"FAILED: {e}")
        return {"status": "FAILED", "error": str(e)}


def test_interest_by_region():
    """Test interest by region — useful for geo-targeting content."""
    print("\n" + "=" * 60)
    print("Test 5: Interest by Region (pytrends)")
    print("-" * 60)

    keyword = "coffee shop"
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], cat=0, timeframe="today 1-m", geo="US")
        df = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True)
        df = df.sort_values(keyword, ascending=False)
        print(f"Keyword: \"{keyword}\"")
        print(f"Regions with data: {len(df[df[keyword] > 0])}")
        print(f"\nTop 10 states:")
        for i, (region, row) in enumerate(df.head(10).iterrows(), 1):
            print(f"  {i:>2}. {region}: {row[keyword]}")
        return {"status": "SUCCESS", "regions": len(df[df[keyword] > 0])}
    except Exception as e:
        print(f"FAILED: {e}")
        return {"status": "FAILED", "error": str(e)}


def main():
    print("=" * 60)
    print("Google Trends — Combined Test")
    print("RSS feed + pytrends library")
    print("=" * 60)

    results = {}
    tests = [
        ("trending_rss", test_trending_searches_rss),
        ("trending_multi_geo", test_trending_multi_geo),
        ("interest_over_time", test_interest_over_time),
        ("related_queries", test_related_queries),
        ("interest_by_region", test_interest_by_region),
    ]

    for name, test_fn in tests:
        results[name] = test_fn()
        time.sleep(2)

    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        icon = "✓" if result["status"] == "SUCCESS" else "✗"
        print(f"  {icon} {name}: {result['status']}")
        if result["status"] == "FAILED":
            print(f"    Error: {result.get('error', 'unknown')[:100]}")

    working = sum(1 for r in results.values() if r["status"] == "SUCCESS")
    print(f"\n{working}/{len(results)} tests passed")

    if working >= 4:
        print("VERDICT: Google Trends is fully usable for the hackathon.")
    elif working >= 3:
        print("VERDICT: Google Trends mostly works. Sufficient for hackathon.")
    else:
        print("VERDICT: Google Trends unreliable. Consider SerpApi as fallback.")


if __name__ == "__main__":
    main()
