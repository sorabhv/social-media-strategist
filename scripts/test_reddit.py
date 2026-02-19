"""
P0 Test: Reddit JSON API
Goal: Verify we can pull trending/hot content from relevant subreddits without auth.
The .json trick: append .json to any Reddit URL to get structured JSON.
"""

import json
import time
import requests

HEADERS = {
    "User-Agent": "SocialMediaStrategist/1.0 (hackathon project; testing data sources)"
}

SUBREDDITS_TO_TEST = [
    "smallbusiness",
    "Entrepreneur",
    "socialmedia",
    "InstagramMarketing",
    "TikTokMarketing",
    "coffeeshops",
    "fitness",
    "technology",
]

LISTINGS = ["hot", "top", "rising"]


def test_subreddit(subreddit: str, listing: str = "hot", limit: int = 10, timeframe: str = "week") -> dict:
    """Fetch posts from a subreddit using the .json API."""
    url = f"https://www.reddit.com/r/{subreddit}/{listing}.json"
    params = {"limit": limit, "t": timeframe}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            return {
                "status": "SUCCESS",
                "subreddit": subreddit,
                "listing": listing,
                "post_count": len(posts),
                "posts": [
                    {
                        "title": p["data"]["title"],
                        "score": p["data"]["score"],
                        "num_comments": p["data"]["num_comments"],
                        "upvote_ratio": p["data"].get("upvote_ratio", 0),
                        "url": p["data"].get("url", ""),
                        "created_utc": p["data"]["created_utc"],
                    }
                    for p in posts
                ],
            }
        elif resp.status_code == 429:
            return {"status": "RATE_LIMITED", "subreddit": subreddit}
        else:
            return {"status": f"HTTP_{resp.status_code}", "subreddit": subreddit}

    except requests.exceptions.RequestException as e:
        return {"status": "EXCEPTION", "subreddit": subreddit, "error": str(e)}


def test_search(query: str, subreddit: str = None, limit: int = 10) -> dict:
    """Test Reddit search API (also works with .json)."""
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {"q": query, "restrict_sr": "on", "sort": "relevance", "t": "month", "limit": limit}
    else:
        url = "https://www.reddit.com/search.json"
        params = {"q": query, "sort": "relevance", "t": "month", "limit": limit}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            return {
                "status": "SUCCESS",
                "query": query,
                "subreddit": subreddit,
                "post_count": len(posts),
                "titles": [p["data"]["title"] for p in posts[:5]],
            }
        else:
            return {"status": f"HTTP_{resp.status_code}", "query": query}
    except requests.exceptions.RequestException as e:
        return {"status": "EXCEPTION", "query": query, "error": str(e)}


def main():
    print("=" * 60)
    print("Reddit JSON API Test")
    print("=" * 60)

    # Test 1: Fetch hot posts from relevant subreddits
    print("\n--- Test 1: Hot Posts from Relevant Subreddits ---")
    subreddit_results = []
    for sub in SUBREDDITS_TO_TEST:
        result = test_subreddit(sub, listing="hot", limit=5)
        subreddit_results.append(result)
        icon = "✓" if result["status"] == "SUCCESS" else "✗"
        count = result.get("post_count", 0)
        print(f"  {icon} r/{sub}: {result['status']} ({count} posts)")
        if result["status"] == "SUCCESS" and result["posts"]:
            top = result["posts"][0]
            print(f"      Top post: \"{top['title'][:60]}...\" (score: {top['score']})")
        time.sleep(1)

    # Test 2: Different listing types on one subreddit
    print("\n--- Test 2: Listing Types (r/smallbusiness) ---")
    for listing in LISTINGS:
        result = test_subreddit("smallbusiness", listing=listing, limit=5)
        icon = "✓" if result["status"] == "SUCCESS" else "✗"
        count = result.get("post_count", 0)
        print(f"  {icon} {listing}: {result['status']} ({count} posts)")
        time.sleep(1)

    # Test 3: Search API
    print("\n--- Test 3: Search API ---")
    search_queries = [
        ("trending sounds tiktok", None),
        ("viral reel ideas", "socialmedia"),
        ("content strategy small business", "smallbusiness"),
    ]
    search_results = []
    for query, sub in search_queries:
        result = test_search(query, subreddit=sub, limit=5)
        search_results.append(result)
        icon = "✓" if result["status"] == "SUCCESS" else "✗"
        scope = f"r/{sub}" if sub else "all"
        print(f"  {icon} \"{query}\" ({scope}): {result['status']} ({result.get('post_count', 0)} results)")
        if result["status"] == "SUCCESS" and result.get("titles"):
            print(f"      First: \"{result['titles'][0][:60]}\"")
        time.sleep(1)

    # Test 4: Check available post fields
    print("\n--- Test 4: Available Post Data Fields ---")
    result = test_subreddit("smallbusiness", listing="hot", limit=1)
    if result["status"] == "SUCCESS":
        url = "https://www.reddit.com/r/smallbusiness/hot.json?limit=1"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            post_data = resp.json()["data"]["children"][0]["data"]
            useful_fields = [
                "title", "selftext", "score", "upvote_ratio", "num_comments",
                "created_utc", "url", "permalink", "subreddit", "link_flair_text",
                "is_video", "media", "thumbnail", "domain",
            ]
            print("  Available useful fields:")
            for field in useful_fields:
                val = post_data.get(field, "MISSING")
                if isinstance(val, str) and len(val) > 80:
                    val = val[:80] + "..."
                print(f"    {field}: {val}")

    # Summary
    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    success_count = sum(1 for r in subreddit_results if r["status"] == "SUCCESS")
    print(f"  Subreddits accessible: {success_count}/{len(SUBREDDITS_TO_TEST)}")
    search_success = sum(1 for r in search_results if r["status"] == "SUCCESS")
    print(f"  Search queries working: {search_success}/{len(search_queries)}")
    print(f"  Auth required: No (using .json endpoint)")
    print(f"  Rate limiting: 1s delay between requests seems sufficient")

    if success_count >= 6 and search_success >= 2:
        print("\nVERDICT: Reddit JSON API works great. No auth needed for our use case.")
    else:
        print("\nVERDICT: Some issues detected. May need PRAW with OAuth for reliability.")


if __name__ == "__main__":
    main()
