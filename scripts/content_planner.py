"""
Content Planner — Step 3 of the Social Media Strategist pipeline.

Reads filtered_trends.json, sends it through an LLM to generate
Reel concepts and a weekly posting calendar, outputs content_plan.json.

Usage:
    python content_planner.py [--input filtered_trends.json] [--output content_plan.json]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

SYSTEM_PROMPT = """You are a viral short-form video content creator and social media calendar planner for small businesses.

You create Reel/TikTok/Shorts concepts that are:
- Easy for a small business owner to film (phone-only, no pro equipment)
- Tied to current trending sounds or formats
- Designed to stop the scroll in the first 3 seconds
- Include ready-to-post captions and hashtags

You also build weekly posting calendars that:
- Balance trending content with evergreen niche content
- Include optimal posting times for the business's audience
- Spread content across TikTok, Instagram Reels, and YouTube Shorts"""

REEL_CONCEPTS_TEMPLATE = """## Business Context

**Business type:** {display_name}
**Content themes:** {content_themes}
**Country:** {country}

## Top Scoring Trends

{filtered_trends_json}

## Instructions

For each of the top 5 trends above, generate a complete Reel concept.

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
  "reel_concepts": [
    {{
      "id": "concept_1",
      "trend_id": "the trend_id this concept is based on",
      "title": "catchy working title for the Reel",
      "hook_pattern": "question/challenge/controversy/tutorial/before_after/reveal/listicle",
      "hook": "The first 3 seconds — what stops the scroll. Be specific.",
      "script": ["Step 1: ...", "Step 2: ...", "Step 3: ...", "Step 4: ..."],
      "sound": "Trending sound name — Artist (or 'original audio' if not using a trending sound)",
      "caption": "Ready-to-post caption with emojis. 2-3 sentences max.",
      "hashtags": {{
        "large": ["#hashtag1", "#hashtag2"],
        "medium": ["#hashtag3", "#hashtag4"],
        "niche": ["#hashtag5"]
      }},
      "cta": "Call to action — what should the viewer do?",
      "difficulty": "easy/medium/hard",
      "estimated_time": "how long to film + edit (e.g. '15 min', '30 min')"
    }}
  ]
}}

IMPORTANT field details:

- **hook_pattern**: Classify the hook into exactly one of these patterns:
  - "question" — opens with a question to trigger comments
  - "challenge" — sets up a timed/difficulty challenge to drive shares and duets
  - "controversy" — makes a bold claim to trigger saves and debates
  - "tutorial" — teaches something step-by-step to drive saves
  - "before_after" — shows a transformation to maximize watch time and replays
  - "reveal" — builds suspense before showing a result
  - "listicle" — rapid-fire list format ("3 things you didn't know about...")

- **hashtags**: Use a TIERED strategy for maximum reach:
  - "large" (2 tags): High-volume hashtags with 1M+ posts for broad discoverability
  - "medium" (2 tags): Mid-volume hashtags with 100K-1M posts for balanced competition
  - "niche" (1 tag): Low-volume hashtags under 100K posts where you can rank higher

Make exactly 5 concepts. Mix trending-sound Reels with topic/format-based Reels."""

CALENDAR_TEMPLATE = """## Business Context

**Business type:** {display_name}
**Country:** {country}

## Reel Concepts Available

{concepts_json}

## Instructions

Create a 7-day posting calendar (Monday through Sunday) using the 5 Reel concepts above.

Rules:
- Post 1 Reel per day Monday-Friday
- Saturday: optional lightweight content (repost, behind-the-scenes story, poll)
- Sunday: rest / plan next week
- Alternate between trending content and evergreen content
- Choose optimal posting times for a {display_name} audience
- Specify which platforms to post on (TikTok, Instagram Reels, YouTube Shorts)

Return ONLY a JSON object with this exact structure:
{{
  "weekly_calendar": [
    {{
      "day": "Monday",
      "concept_id": "concept_1",
      "title": "Morning Rush Latte Art",
      "time": "7:30 AM",
      "platforms": ["TikTok", "Instagram Reels"],
      "content_type": "trending",
      "notes": "Post right when morning commuters are scrolling",
      "platform_tips": {{
        "TikTok": "Keep under 15s, add text hook on screen in first frame, reply to top comment with a follow-up video",
        "Instagram Reels": "Use 3-5 niche hashtags in caption, set a custom cover image, add to a Reel highlight/guide",
        "YouTube Shorts": "Write a keyword-rich title, end with 'subscribe for more', add vertical thumbnail"
      }}
    }},
    {{
      "day": "Saturday",
      "concept_id": null,
      "title": "Weekend Poll: What's your go-to order?",
      "time": "10:00 AM",
      "platforms": ["Instagram Stories"],
      "content_type": "engagement",
      "notes": "Low effort, high engagement. Use poll sticker.",
      "platform_tips": {{
        "Instagram Stories": "Use poll sticker + question sticker, post 2-3 story slides, share a DM prompt"
      }}
    }},
    {{
      "day": "Sunday",
      "concept_id": null,
      "title": "Rest / Plan Next Week",
      "time": null,
      "platforms": [],
      "content_type": "rest",
      "notes": "Review this week's analytics, plan next week",
      "platform_tips": {{}}
    }}
  ]
}}

IMPORTANT: The "platform_tips" field is required for every day. Include a specific, actionable tip for EACH platform listed in that day's "platforms" array. Tips should cover algorithm-specific optimizations:
- TikTok: watch time, duets, stitches, trending sounds, text-on-screen hooks
- Instagram Reels: saves, shares, hashtag strategy, cover images, Guides
- YouTube Shorts: titles, thumbnails, retention, subscribe CTAs, SEO keywords
- Instagram Stories: stickers (poll, quiz, question), DM engagement, multi-slide strategy"""


def inject_sound_links(concepts: list[dict], trends: list[dict]) -> list[dict]:
    """Match concept sounds back to trend data and inject real TikTok links."""
    # Build lookup: trend_id -> url, and normalized name -> url
    id_map = {}
    name_map = {}
    for t in trends:
        if t.get("url"):
            id_map[t.get("trend_id", "")] = t["url"]
            name = t.get("name", "").strip().lower()
            name_map[name] = t["url"]

    for concept in concepts:
        # First try matching by trend_id
        tid = concept.get("trend_id", "")
        if tid in id_map:
            concept["sound_link"] = id_map[tid]
            continue

        # Fallback: match by sound name (before the " — Artist" part)
        sound = concept.get("sound", "")
        sound_base = sound.split("\u2014")[0].split("\u2013")[0].split(" - ")[0].strip().lower()

        if sound_base in name_map:
            concept["sound_link"] = name_map[sound_base]
            continue

        # Fuzzy fallback: partial match
        for trend_name, link in name_map.items():
            if trend_name in sound_base or sound_base in trend_name:
                concept["sound_link"] = link
                break
        else:
            concept["sound_link"] = None

    return concepts


def build_prompts(filtered_data: dict, niche_config: dict) -> list[tuple[str, str, str]]:
    """Build prompt pairs for each LLM pass. Returns [(label, system, user), ...]."""
    display_name = niche_config["display_name"]
    content_themes = ", ".join(niche_config.get("content_themes", []))
    country = filtered_data.get("country", "US")

    top = filtered_data.get("top_trends", [])[:5]
    trends_json = json.dumps(top, indent=2, ensure_ascii=False)

    reel_user = REEL_CONCEPTS_TEMPLATE.format(
        display_name=display_name,
        content_themes=content_themes,
        country=country,
        filtered_trends_json=trends_json,
    )

    prompts = [("reel_concepts", SYSTEM_PROMPT, reel_user)]
    return prompts


def build_calendar_prompt(filtered_data: dict, niche_config: dict, concepts: list[dict]) -> tuple[str, str]:
    display_name = niche_config["display_name"]
    country = filtered_data.get("country", "US")
    concepts_json = json.dumps(concepts, indent=2, ensure_ascii=False)

    cal_user = CALENDAR_TEMPLATE.format(
        display_name=display_name,
        country=country,
        concepts_json=concepts_json,
    )
    return SYSTEM_PROMPT, cal_user


def call_llm(system_prompt: str, user_prompt: str) -> dict | None:
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
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
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Content Planner — Reel concepts + calendar")
    parser.add_argument("--input", default=None, help="Path to filtered_trends.json")
    parser.add_argument("--output", default=None, help="Path to content_plan.json")
    args = parser.parse_args()

    input_path = args.input or str(PROJECT_DIR / "output" / "filtered_trends.json")
    output_path = args.output or str(PROJECT_DIR / "output" / "content_plan.json")

    with open(input_path) as f:
        filtered_data = json.load(f)

    # Load niche config
    niche_path = PROJECT_DIR / "references" / "niche_mapping.json"
    with open(niche_path) as f:
        niche_config = json.load(f)[filtered_data["business_type"]]

    print(f"Planning content for: {niche_config['display_name']}")
    print(f"Top trends: {len(filtered_data.get('top_trends', []))}")

    prompts_dir = Path(output_path).parent
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: Reel concepts
    prompts = build_prompts(filtered_data, niche_config)
    label, sys_p, usr_p = prompts[0]

    with open(prompts_dir / "prompt_concepts_system.txt", "w") as f:
        f.write(sys_p)
    with open(prompts_dir / "prompt_concepts_user.txt", "w") as f:
        f.write(usr_p)

    concepts_result = call_llm(sys_p, usr_p)
    concepts = []
    if concepts_result:
        concepts = concepts_result.get("reel_concepts", [])
        # Inject real sound links from trend data
        all_trends = filtered_data.get("top_trends", [])
        concepts = inject_sound_links(concepts, all_trends)
        print(f"\nGenerated {len(concepts)} Reel concepts:")
        for c in concepts:
            link_status = "\u2713 link" if c.get("sound_link") else "\u2717 no link"
            print(f"  - {c['title']} ({c['difficulty']}, {c['estimated_time']}) [{link_status}]")
    else:
        print(f"\nPrompts saved to {prompts_dir}/prompt_concepts_*.txt")

    # Pass 2: Calendar (only if concepts were generated)
    calendar = []
    if concepts:
        cal_sys, cal_usr = build_calendar_prompt(filtered_data, niche_config, concepts)
        with open(prompts_dir / "prompt_calendar_system.txt", "w") as f:
            f.write(cal_sys)
        with open(prompts_dir / "prompt_calendar_user.txt", "w") as f:
            f.write(cal_usr)

        cal_result = call_llm(cal_sys, cal_usr)
        if cal_result:
            calendar = cal_result.get("weekly_calendar", [])
            print(f"\nWeekly calendar ({len(calendar)} days):")
            for day in calendar:
                title = day.get("title", "—")
                time_str = day.get("time", "—")
                platforms = ", ".join(day.get("platforms", []))
                print(f"  {day['day']}: {title} @ {time_str} [{platforms}]")
    else:
        cal_sys, cal_usr = build_calendar_prompt(filtered_data, niche_config, [])
        with open(prompts_dir / "prompt_calendar_system.txt", "w") as f:
            f.write(cal_sys)
        with open(prompts_dir / "prompt_calendar_user.txt", "w") as f:
            f.write(cal_usr)
        print(f"Calendar prompts saved to {prompts_dir}/prompt_calendar_*.txt")

    # Write final output
    output = {
        "business_type": filtered_data["business_type"],
        "country": filtered_data.get("country", "US"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reel_concepts": concepts,
        "weekly_calendar": calendar,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nContent plan written to: {output_path}")

    if not concepts:
        print("\nNo LLM available. To use the prompts:")
        print("  1. During hackathon: NeoClaw agent reads these prompts automatically")
        print("  2. Local testing: set OPENAI_API_KEY and re-run")
        print("  3. Manual: paste prompt_concepts_user.txt into ChatGPT/Claude")


if __name__ == "__main__":
    main()
