# GitHub Token Setup

The Social Media Strategist skill **requires** a GitHub personal access token to push reports to the repository.

## How the Agent Should Handle the Token

When executing Step 4 (report generation), the agent MUST pass the `GITHUB_TOKEN` as an environment variable:

```bash
cd ~/.openclaw/skills/social-media-strategist/scripts
GITHUB_TOKEN="ghp_xxxxxxxxxxxxx" python3 report_generator.py
```

## Token Storage Options

### Option 1: Store in Agent Memory (Recommended for OpenClaw)
The agent can store the token in its workspace and read it when needed:

```bash
# Store once
echo "GITHUB_TOKEN=ghp_xxxxxxxxxxxxx" > ~/.openclaw/workspace/.env

# Read and use
source ~/.openclaw/workspace/.env
cd ~/.openclaw/skills/social-media-strategist/scripts
GITHUB_TOKEN="$GITHUB_TOKEN" python3 report_generator.py
```

### Option 2: System Environment Variable
Add to `~/.bashrc` or `~/.profile`:

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxx"
```

Then reload: `source ~/.bashrc`

### Option 3: Gateway Config (if supported)
Some gateway configurations may support environment variables for skills.

## Creating a GitHub Token

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name it: "Social Media Strategist Skill"
4. Scopes needed:
   - ✅ `repo` (full control of private repositories)
   - This allows pushing files to the repository
5. Generate and copy the token (starts with `ghp_`)

## Security Notes

- ⚠️ Never commit tokens to Git
- ⚠️ Never log tokens in plain text
- ⚠️ The agent should treat tokens as sensitive data
- ✅ Always pass tokens via environment variables, not hardcoded

## Troubleshooting

### Error: "GITHUB_TOKEN environment variable is required"
The token wasn't passed to the script. Make sure to prefix the command with `GITHUB_TOKEN="your_token"`.

### Error: "GitHub push failed (401)"
The token is invalid or expired. Generate a new one.

### Error: "GitHub push failed (403)"
The token doesn't have `repo` scope. Regenerate with the correct permissions.
