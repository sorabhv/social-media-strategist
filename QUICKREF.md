# Quick Reference - Social Media Strategist

## Token Check
```bash
test -f ~/.openclaw/workspace/.env && echo "✅ Token exists" || echo "❌ Token not found"
```

## Store Token (First Time)
```bash
~/.openclaw/skills/social-media-strategist/scripts/github-token.sh store ghp_xxxxxxxxxxxxx
```

## Generate Report (Standard Flow)
```bash
cd ~/.openclaw/skills/social-media-strategist
./scripts/github-token.sh generate
```

## Manual Commands

### Step 1: Trend Discovery
```bash
cd ~/.openclaw/skills/social-media-strategist/scripts
python3 trend_scraper.py tattoo_shop --country US
```

### Step 2: Filter Trends
```bash
cd ~/.openclaw/skills/social-media-strategist/scripts
python3 trend_filter.py
```

### Step 3: Content Planning
```bash
cd ~/.openclaw/skills/social-media-strategist/scripts
python3 content_planner.py
```

### Step 4: Generate & Push Report
```bash
cd ~/.openclaw/skills/social-media-strategist
./scripts/github-token.sh generate
```

## Expected Output URLs
`https://github.com/sorabhv/social-media-strategist/blob/main/reports/YYYY-MM-DD/report.html`

## Troubleshooting

### Token Missing Error
**Symptom:** `GITHUB_TOKEN environment variable is required but not set`  
**Fix:** Run `./scripts/github-token.sh store <token>`

### Permission Denied
**Symptom:** `Permission denied: ./github-token.sh`  
**Fix:** `chmod +x ~/.openclaw/skills/social-media-strategist/scripts/github-token.sh`

### GitHub Push Failed (401)
**Symptom:** `GitHub push failed (401)`  
**Fix:** Token invalid/expired - generate new one and re-store

### GitHub Push Failed (403)
**Symptom:** `GitHub push failed (403)`  
**Fix:** Token lacks `repo` scope - regenerate with correct permissions
