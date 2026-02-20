# Social Media Strategist - Update Summary

## v1.1.0 - Business Profile Memory

### Added
- **Memory system** for returning users: the skill now reads `memory/business_profile.json` before starting and confirms with the user if it's the same business
- Saves business profile fields: name, type, country, location, target audience, brand voice, content preferences, posting frequency, platforms, and additional notes
- **Smart memory updates**: if the user shares relevant preferences mid-conversation (e.g. "we don't do dancing reels"), the agent saves them for future sessions
- Clear rules for what to save (durable business info) vs. what not to save (transient requests)
- Updated SKILL.md description to mention memory capability
- Added `memory/business_profile.json` template with null defaults
- Updated README with memory documentation

---

## v1.0.0 - Initial Release

## Changes Made

### 1. **Mandatory GitHub Push**
- Removed `--push` flag from `report_generator.py`
- GitHub push is now **always executed** (not optional)
- Script fails with clear error if `GITHUB_TOKEN` is not set

### 2. **Token Management System**
- Created `github-token.sh` helper script for secure token storage
- Token is stored in `~/.openclaw/workspace/.env` with secure permissions (600)
- Three commands available:
  - `./github-token.sh store <token>` - Store token securely
  - `./github-token.sh load` - Load token to environment
  - `./github-token.sh generate` - Generate report and push to GitHub

### 3. **Updated Documentation**
- **SKILL.md**: Updated workflow to show token requirement and helper script usage
- **TOKEN_SETUP.md**: Comprehensive guide for token creation and management
- **report_generator.py**: Updated docstring to reflect mandatory push

### 4. **Improved Error Handling**
- Script now raises clear exceptions if token is missing
- Success message includes clickable GitHub URL
- Exit code 1 on GitHub push failure

## How It Works Now

### First-Time Setup (One Time)
```bash
cd ~/.openclaw/skills/social-media-strategist
./scripts/github-token.sh store ghp_xxxxxxxxxxxxx
```

### Every Report Generation
```bash
cd ~/.openclaw/skills/social-media-strategist
./scripts/github-token.sh generate
```

Or manually:
```bash
source ~/.openclaw/workspace/.env
cd ~/.openclaw/skills/social-media-strategist/scripts
GITHUB_TOKEN="$GITHUB_TOKEN" python3 report_generator.py
```

## Agent Workflow

When the agent runs this skill:

1. **Steps 1-3**: Run normally (trend discovery, filtering, content planning)
2. **Step 4**: 
   - Check if token exists: `test -f ~/.openclaw/workspace/.env`
   - If not, ask user for token and run: `./scripts/github-token.sh store <token>`
   - Generate report: `./scripts/github-token.sh generate`
   - Extract GitHub URL from output and share with user

## Files Modified/Created

### Modified:
- `scripts/report_generator.py` - Made GitHub push mandatory
- `SKILL.md` - Updated workflow documentation

### Created:
- `scripts/github-token.sh` - Token management helper script
- `TOKEN_SETUP.md` - Token setup documentation
- `CHANGELOG.md` - This file

### Token Storage:
- `~/.openclaw/workspace/.env` - Secure token storage (created on first use)

## Security Notes

✅ Token stored with 600 permissions (owner read/write only)  
✅ Token passed via environment variable (not command line arguments)  
✅ Token never logged or printed in clear text  
✅ `.env` file should be gitignored in workspace  

## Testing

Tested successfully with a valid GitHub personal access token.

All reports now automatically push to:
`https://github.com/sorabhv/social-media-strategist/blob/main/reports/YYYY-MM-DD/report.html`

## Rollback (if needed)

To revert to optional push:
1. Add back `--push` argument to `report_generator.py`
2. Change `push_to_github()` to return False instead of raising exception
3. Update SKILL.md to show `python3 report_generator.py --push`
