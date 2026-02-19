"""
Trend Filter — Step 2 of the Social Media Strategist pipeline.

Reads trends.json, sends it through an LLM to score each trend for
relevance/virality/difficulty/timeliness, and outputs filtered_trends.json.

Usage:
    python trend_filter.py [--input trends.json] [--output filtered_trends.json]

During the hackathon this runs inside NeoClaw which provides LLM access.
For local testing, set OPENAI_API_KEY env var to use the OpenAI API.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

SYSTEM_PROMPT = """You are an expert social media strategist who helps small businesses create viral content.

You will receive:
1. A business type and its niche context (hashtag seeds, content themes)
2. A list of trending signals from TikTok, Google Trends, and Reddit

Your job: Score each trend's usefulness for THIS SPECIFIC business and return the top 10.

IMPORTANT RULES:
- A trend is relevant even if it's not directly about the business — the question is "can this business create content using this trend?"
- Trending sounds/songs are VERY valuable because any business can use them as background music
- Reddit posts that show what customers care about are valuable for content angles
- Google trending topics are only relevant if the business can tie them to their content naturally
- Ignore promoted/ad content from TikTok
- Prefer RISING and STABLE trends over DECLINING and SPIKE trends"""

USER_PROMPT_TEMPLATE = """## Business Context

**Business type:** {display_name}
**Hashtag seeds:** {hashtag_seeds}
**Content themes:** {content_themes}
**Country:** {country}

## Trending Signals ({total} total)

{trends_json}

## Instructions

Score each trend on these 4 dimensions (1-10 scale):
- **relevance**: How well can a {display_name} create content using this trend? (10 = perfect fit)
- **virality**: How likely is this trend to generate views/engagement? Consider rank, views, trajectory. (10 = guaranteed viral)
- **difficulty**: How easy is it for a small business owner to create this content? (10 = very easy, phone-only) 
- **timeliness**: Is this trend still worth jumping on? Use trajectory: RISING=9-10, STABLE=7-8, DECLINING=4-5, SPIKE=2-3, UNKNOWN=6

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
  "top_trends": [
    {{
      "trend_id": "the id field from the trend",
      "name": "trend name",
      "source": "tiktok/google_trends/reddit",
      "type": "hashtag/song/video/search_trend/related_query/reddit_post",
      "scores": {{
        "relevance": 8,
        "virality": 9,
        "difficulty": 7,
        "timeliness": 9,
        "overall": 8.25
      }},
      "suggested_angle": "One sentence: exactly how this business should use this trend in a Reel"
    }}
  ]
}}

Return the top 10 trends sorted by overall score (highest first).
The "overall" score = (relevance * 0.35) + (virality * 0.25) + (difficulty * 0.25) + (timeliness * 0.15)"""


def build_prompt(trends_data: dict) -> tuple[str, str]:
    """Build the system and user prompts from trends.json data."""
    niche = trends_data["niche_config"]
    trends = trends_data["trends"]

    compact_trends = []
    for t in trends:
        compact = {
            "id": t["id"],
            "source": t["source"],
            "type": t["type"],
            "name": t["name"],
            "trajectory": t["trajectory"],
            "metrics": t["metrics"],
        }
        if t.get("description"):
            compact["description"] = t["description"]
        if t.get("trend_curve"):
            compact["trend_curve"] = t["trend_curve"]
        if t.get("url"):
            compact["url"] = t["url"]
        compact_trends.append(compact)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        display_name=niche["display_name"],
        hashtag_seeds=", ".join(niche.get("tiktok_hashtag_seeds", [])),
        content_themes=", ".join(niche.get("content_themes", [])),
        country=trends_data["country"],
        total=len(compact_trends),
        trends_json=json.dumps(compact_trends, indent=2, ensure_ascii=False),
    )

    return SYSTEM_PROMPT, user_prompt


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Call LLM and parse JSON response. Tries OpenAI API if available."""
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("No OPENAI_API_KEY set. Writing prompts to disk for manual/NeoClaw use.")
        return None

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except ImportError:
        print("openai package not installed. pip install openai")
        return None
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Trend Filter — LLM scoring")
    parser.add_argument("--input", default=None, help="Path to trends.json")
    parser.add_argument("--output", default=None, help="Path to filtered_trends.json")
    args = parser.parse_args()

    input_path = args.input or str(PROJECT_DIR / "output" / "trends.json")
    output_path = args.output or str(PROJECT_DIR / "output" / "filtered_trends.json")

    with open(input_path) as f:
        trends_data = json.load(f)

    print(f"Loaded {trends_data['summary']['total']} trends for {trends_data['business_type']}")

    system_prompt, user_prompt = build_prompt(trends_data)

    # Always save prompts for inspection / NeoClaw usage
    prompts_dir = Path(output_path).parent
    prompts_dir.mkdir(parents=True, exist_ok=True)
    with open(prompts_dir / "prompt_filter_system.txt", "w") as f:
        f.write(system_prompt)
    with open(prompts_dir / "prompt_filter_user.txt", "w") as f:
        f.write(user_prompt)
    print(f"Prompts saved to {prompts_dir}/prompt_filter_*.txt")

    result = call_llm(system_prompt, user_prompt)

    if result:
        # Enrich top_trends with URLs from original trend data
        url_map = {t["id"]: t.get("url") for t in trends_data["trends"] if t.get("url")}
        for t in result.get("top_trends", []):
            tid = t.get("trend_id")
            if tid and tid in url_map:
                t["url"] = url_map[tid]

        output = {
            "business_type": trends_data["business_type"],
            "country": trends_data["country"],
            "filtered_at": datetime.now(timezone.utc).isoformat(),
            "input_trends": trends_data["summary"]["total"],
            **result,
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nFiltered trends written to: {output_path}")
        print(f"Top trends:")
        for t in result.get("top_trends", [])[:5]:
            print(f"  {t['scores']['overall']:.1f} | {t['name']} ({t['source']}/{t['type']})")
            print(f"        → {t['suggested_angle']}")
    else:
        print("\nNo LLM response. Use the saved prompts with NeoClaw or paste into ChatGPT.")
        print(f"  System prompt: {prompts_dir}/prompt_filter_system.txt")
        print(f"  User prompt:   {prompts_dir}/prompt_filter_user.txt")


if __name__ == "__main__":
    main()
