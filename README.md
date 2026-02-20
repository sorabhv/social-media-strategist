# Social Media Strategist Agent

An AI agent skill for [NeoClaw](https://docs.openclaw.ai) that helps small businesses discover trending content across TikTok, Google Trends, and Reddit, then generates a personalized weekly content plan with ready-to-film Reel concepts, captions, and hashtags.

Built for the **Gen NeoClaw Hackathon** (Feb 2026).

## Pipeline

```
trend_scraper.py          trend_filter.py          content_planner.py       report_generator.py
     |                         |                         |                        |
TikTok Creative Center    LLM scores each trend    Generates 5 Reel         Renders HTML report
Google Trends RSS         on relevance, virality,  concepts + 7-day         and pushes to GitHub
Reddit JSON API           difficulty, timeliness    posting calendar
     |                         |                         |                        |
     v                         v                         v                        v
 trends.json           filtered_trends.json       content_plan.json       reports/{date}/report.html
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

## Data Sources

| Source | Method | Auth Required |
|--------|--------|---------------|
| TikTok Creative Center | SSR HTML parsing + Node.js API bridge | No |
| Google Trends | RSS feed + `pytrends` library | No |
| Reddit | JSON API (append `.json` to URLs) | No |

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
    test_reddit.py             # P0 validation script
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

The skill remembers your business details across sessions. On first use, it asks for your business type, country, and optional details (business name, target audience, brand voice, etc.). On subsequent runs, it loads your saved profile and confirms before proceeding -- no need to re-enter information. If you share preferences during a session (e.g. "our audience is women 25-40"), the agent automatically saves them for future use.
