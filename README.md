# Social Media Strategist Agent

An AI agent skill for [NeoClaw](https://docs.openclaw.ai) that helps small businesses discover trending content across TikTok and Google Trends, then generates a personalized weekly content plan with ready-to-film Reel concepts, captions, and hashtags.

Built for the **Gen NeoClaw Hackathon** (Feb 2026).

## Problem Statement

Small businesses, Gig Economy workers, and Entrepreneurs face a critical challenge today: **marketing and expanding their business** to reach new markets and audiences — a necessity to grow their footprint and stay competitive. Social media has become the dominant marketing tool of the 21st century, yet leveraging it effectively remains out of reach for most due to the **effort** required to produce consistent content, the **cost** of hiring specialists or running paid campaigns, the complexity of **understanding ever-changing platform algorithms**, and the difficulty of keeping up with **trending features** that drive visibility. This agent solves that gap by automating trend discovery, content planning, and strategy — turning social media from an overwhelming burden into an actionable, accessible growth engine.

## Pipeline

```
memory/business_profile.json ──► loaded on startup, confirmed with user
         │
         ▼
trend_scraper.py          trend_filter.py          content_planner.py       report_generator.py
     |                         |                         |                        |
TikTok Creative Center    LLM scores each trend    Generates 5 Reel         Renders HTML report
Google Trends RSS         on relevance, virality,  concepts + 7-day         and pushes to GitHub
     |                    difficulty, timeliness    posting calendar
     v                         |                         |                        |
 trends.json                   v                         v                        v
                        filtered_trends.json       content_plan.json       reports/{date}/report.html
         │
         ▼
memory/business_profile.json ◄── updated with any new preferences from conversation
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for TikTok API bridge)
- `OPENAI_API_KEY` env var (for LLM steps)
- `GITHUB_TOKEN` env var (optional, for report push)

### Install Dependencies

```bash
cd social-media-strategist
pip install -r requirements.txt
npm install
```

### Run the Pipeline

```bash
# Step 1: Discover trending content
python3 scripts/trend_scraper.py coffee_shop --country US

# Step 2: Filter and score trends (requires OPENAI_API_KEY)
python3 scripts/trend_filter.py

# Step 3: Generate Reel concepts and weekly calendar
python3 scripts/content_planner.py

# Step 4: Generate HTML report (optionally push to GitHub)
python3 scripts/report_generator.py
python3 scripts/report_generator.py --push   # pushes to GitHub
```

## Supported Business Types

| Key | Business |
|-----|----------|
| `auto_detailing` | Auto Detailing |
| `bakery` | Bakery |
| `barbershop` | Barbershop |
| `bookstore` | Bookstore |
| `clothing_boutique` | Clothing Boutique |
| `coffee_shop` | Coffee Shop / Cafe |
| `dog_groomer` | Dog Groomer |
| `education` | Education / Tutoring Center |
| `fitness_gym` | Fitness Gym |
| `florist` | Florist / Flower Shop |
| `food_truck` | Food Truck |
| `hair_salon` | Hair Salon |
| `health_wellness` | Health & Wellness Clinic |
| `home_decor` | Home Decor / Interior Design |
| `jewelry_store` | Jewelry Store |
| `music_school` | Music School / Music Lessons |
| `nail_salon` | Nail Salon |
| `personal_trainer` | Personal Trainer |
| `pet_store` | Pet Store / Pet Services |
| `photographer` | Photographer |
| `real_estate_agent` | Real Estate Agent |
| `restaurant` | Restaurant |
| `tattoo_shop` | Tattoo Shop |
| `yoga_studio` | Yoga Studio |

## Output Files

| File | Description |
|------|-------------|
| `output/trends.json` | Raw trending signals from all sources |
| `output/filtered_trends.json` | Top 10 trends scored by LLM |
| `output/content_plan.json` | 5 Reel concepts + 7-day calendar |
| `output/{date}/report.html` | Self-contained HTML report |
| `output/prompt_*.txt` | Generated LLM prompts (for inspection) |
| `memory/business_profile.json` | Saved business profile for returning users |

## Data Sources

| Source | Method | Auth Required |
|--------|--------|---------------|
| TikTok Creative Center | SSR HTML parsing + Node.js API bridge | No |
| Google Trends | RSS feed + `pytrends` library | No |

## Project Structure

```
social-media-strategist/
  SKILL.md                     # OpenClaw skill definition
  README.md                    # This file
  requirements.txt             # Python dependencies
  package.json                 # Node.js dependencies
  scripts/
    trend_scraper.py           # Step 1: Unified trend scraper
    trend_filter.py            # Step 2: LLM trend filtering
    content_planner.py         # Step 3: Reel concepts + calendar
    report_generator.py        # Step 4: HTML report + GitHub push
    tiktok_api.mjs             # Node.js TikTok API bridge
    test_tiktok.py             # P0 validation script
    test_pytrends.py           # P0 validation script
  references/
    niche_mapping.json         # 24 business types with config
    posting_schedule.md        # Optimal posting times
  memory/
    business_profile.json      # Saved business profile for returning users
  output/                      # Generated pipeline outputs
```

## How It Works on NeoClaw

This project is packaged as an OpenClaw Skill. The `SKILL.md` file tells the NeoClaw agent how to run the pipeline, present results in chat, and interact with the user. The agent handles orchestration -- you just ask it "What should I post this week?" and it runs the full pipeline.

### Business Profile Memory

The skill remembers your business details across sessions so returning users never have to re-enter information.

**First run:** The agent asks for your business type, country, and optional details, then saves everything to `memory/business_profile.json`.

**Returning user:** The agent loads your saved profile, shows a friendly summary, and asks you to confirm before proceeding. You can update specific fields (e.g. "I changed my target audience") or start fresh for a different business.

**Smart updates:** If you share preferences mid-conversation (e.g. "our audience is women 25-40" or "we never do dancing reels"), the agent automatically saves them for future sessions.

#### Saved Profile Fields

| Field | Example |
|-------|---------|
| `business_name` | "Sunrise Bakery" |
| `business_type` | `bakery` |
| `country` | `US` |
| `location_detail` | "Austin, TX" |
| `target_audience` | "Women 25-40, health-conscious" |
| `brand_voice` | "Fun and casual" |
| `content_preferences` | "Behind-the-scenes, no dancing reels" |
| `posting_frequency` | "3 posts per week" |
| `platforms` | "Instagram, TikTok" |
| `additional_notes` | "We're vegan-only, highlight seasonal items" |

The agent saves **durable business info** (audience, voice, preferences) but ignores **transient requests** ("show me this week's trends").

### Past Reports

Past reports are saved locally at `~/.openclaw/skills/social-media-strategist/memory/reports/{YYYY-MM-DD}/`. Before generating a new plan, the agent checks recent reports to avoid repeating the same content ideas.

### OpenClaw Directory

~/.openclaw/skills/social-media-strategist/