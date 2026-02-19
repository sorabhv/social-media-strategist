# P0 Findings — Data Source Validation

**Date:** Feb 18, 2026 (Pre-hackathon)

---

## TL;DR

| Source | Works? | Auth Needed? | Method | Data Quality |
|--------|--------|-------------|--------|-------------|
| TikTok Creative Center | **Yes** | No | SSR HTML parsing (`__NEXT_DATA__`) | Excellent — hashtags, songs, creators, videos with trend data |
| Google Trends (pytrends) | **Partial** | No | `pytrends` library | Good for keyword interest & related queries; trending searches broken |
| Reddit JSON API | **Yes** | No | Append `.json` to URLs | Excellent — full post data, search, multiple listings |

---

## 1. TikTok Creative Center

### What Works
- **Method:** Plain HTTP GET → parse `__NEXT_DATA__` from server-rendered HTML
- **No browser automation, no API signatures, no cookies needed**
- All 4 content types work:

| Content Type | URL Path | Items per SSR Page | Total Available |
|-------------|----------|-------------------|----------------|
| Hashtags | `/hashtag/pc/en` | 20 | 100 |
| Songs | `/music/pc/en` | 3 | 100 |
| Creators | `/creator/pc/en` | 3 | 39,000+ |
| Videos | `/pc/en` | 5 | 500 |

### Data Fields Available
- **Hashtags:** `hashtagName`, `videoViews`, `publishCnt`, `rank`, `rankDiff`, `trend` (7-day time series), `isPromoted`
- **Songs:** `title`, `author`, `duration`, `rank`, `rankDiff`, `trend`, `songId`, `relatedItems`
- **Creators:** `nickName`, `followerCnt`, `likedCnt`, `countryCode`, `items` (their top videos)
- **Videos:** `title`, `region`, `duration`, `itemId`, `itemUrl`, `cover`

### Limitations
- SSR only gives page 1 (top items). The internal API (`creative_radar_api/v1/`) requires crypto signatures for pagination.
- Country filtering doesn't work via URL params — the SSR data is global defaults.
- **Hackathon impact:** Top 20 hashtags + top 3 songs is MORE than enough for content strategy.

### API Endpoint Info (if we need more data later)
```
Base: https://ads.tiktok.com/creative_radar_api/v1/
Endpoints:
  popular_trend/hashtag/list    (trending hashtags)
  popular_trend/sound/rank_list (trending songs)
  popular_trend/creator/list    (trending creators)
  popular_trend/list            (trending videos)
Requires: tiktok-user-sign signature headers (JS library)
```

---

## 2. Google Trends (pytrends)

### What Works
| Feature | Status | Notes |
|---------|--------|-------|
| `interest_over_time` | **Works** | Returns hourly data for "now 7-d", keyword comparison |
| `related_queries` | **Works** | Top & rising queries for a keyword |
| `trending_searches` | **Broken** | Returns 404 (Google changed endpoint) |
| `realtime_trending_searches` | **Broken** | Returns 404 |
| `related_topics` | **Broken** | Index error (library bug) |

### Useful For Hackathon
- **Keyword validation:** Check if a TikTok trend is also trending on Google (cross-platform signal)
- **Content ideation:** `related_queries` gives content angle ideas (e.g., "trending reels" → "new trending reels", "trending reels songs")
- **Timing:** `interest_over_time` shows if a trend is rising or fading

### Fallback Options
- SerpApi Google Trends API (100 free searches/month)
- Direct Google Trends RSS feed: `https://trends.google.com/trending/rss?geo=US`

---

## 3. Reddit JSON API

### What Works — Everything
| Feature | Status | Notes |
|---------|--------|-------|
| Hot/Top/Rising posts | **Works** | All listing types, no auth |
| Multiple subreddits | **Works** | 8/8 tested (smallbusiness, Entrepreneur, socialmedia, InstagramMarketing, TikTokMarketing, coffeeshops, fitness, technology) |
| Search API | **Works** | Global and subreddit-scoped search |
| Post metadata | **Works** | title, score, comments, upvote_ratio, flair, url, selftext |

### How to Use
```python
import requests
url = f"https://www.reddit.com/r/{subreddit}/{listing}.json"
params = {"limit": 25, "t": "week"}
headers = {"User-Agent": "YourBot/1.0"}
resp = requests.get(url, headers=headers, params=params)
```

### Rate Limiting
- 1 second delay between requests is sufficient
- No auth required for read-only access
- User-Agent header is recommended

### Useful Subreddits for Content Strategy
- `r/smallbusiness`, `r/Entrepreneur` — business owner discussions
- `r/socialmedia`, `r/InstagramMarketing`, `r/TikTokMarketing` — platform strategy
- Niche subreddits matching the business type (e.g., `r/coffeeshops`, `r/fitness`)

---

## Hackathon Architecture Decision

### Data Pipeline for Trend Discovery
```
1. TikTok Creative Center (SSR)  → Top trending hashtags, songs, creators
2. Reddit (.json API)             → Community discussions, viral content signals
3. Google Trends (pytrends)       → Cross-platform trend validation + related queries
```

### No Browser Automation Needed!
All three sources work with plain `requests` HTTP calls. This simplifies the hackathon build significantly — no Playwright/Selenium dependency, faster execution, fewer failure modes.

### Test Scripts
- `scripts/test_tiktok.py` — TikTok Creative Center SSR scraping
- `scripts/test_pytrends.py` — Google Trends via pytrends
- `scripts/test_reddit.py` — Reddit JSON API
