# Claude API Setup Guide

Quick setup guide for getting your Claude API key and configuring it.

## Step 1: Get Claude API Key

1. Go to: https://console.anthropic.com/
2. Sign in or create an account
3. Navigate to **API Keys** section
4. Click **Create Key**
5. Give it a name (e.g., "Audio-to-Notion Pipeline")
6. Copy the API key (starts with `sk-ant-`)

**Important:** Save this key immediately - you won't be able to see it again!

## Step 2: Add to .env File

Open your `.env` file and add:

```bash
# Claude API Configuration
CLAUDE_API_KEY=sk-ant-your-key-here
CLAUDE_MODEL=claude-sonnet-4-20250514  # Latest Sonnet model
```

**Model Options:**
- `claude-sonnet-4-20250514` - Latest Sonnet (best balance of speed/quality)
- `claude-opus-4-20250514` - Opus (highest quality, slower)
- `claude-3-5-sonnet-20241022` - Previous Sonnet version

## Step 3: Test Claude Connection

Run the test script:

```bash
python test_claude.py
```

This will:
- ✓ Verify your API key works
- ✓ Test analyzing a sample transcript
- ✓ Show you the structured output format

## What Claude Does in the Pipeline

Claude analyzes your transcripts and extracts:

1. **Summary** - Brief overview of the conversation
2. **Key Points** - Main topics and insights
3. **Action Items** - Tasks or follow-ups mentioned
4. **People Mentioned** - Names and context
5. **Topics/Tags** - Categories for organizing in Notion

## Pricing (as of Nov 2024)

**Claude Sonnet 4:**
- Input: $3 per million tokens (~750k words)
- Output: $15 per million tokens

**Typical Cost per Audio:**
- 5-minute voice memo ≈ $0.01-0.02
- Very affordable for personal use!

## Troubleshooting

**Error: "Invalid API key"**
- Make sure key starts with `sk-ant-`
- No extra spaces or quotes in .env file
- Key must be active in console.anthropic.com

**Error: "Rate limit exceeded"**
- Free tier has limits
- Add credits to your account
- Or wait a few minutes

## Next Steps

After Claude is working:
1. ✓ Google Drive - **DONE**
2. ✓ Whisper transcription - **DONE**
3. ✓ Claude analysis - **YOU ARE HERE**
4. ⏳ Notion API setup
5. ⏳ Run full pipeline!
