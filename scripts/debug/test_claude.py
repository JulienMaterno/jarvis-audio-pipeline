"""
Test Claude API connection and transcript analysis.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
from anthropic import Anthropic

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ClaudeTest')

# Load environment
load_dotenv()

def test_claude_connection():
    """Test basic Claude API connection."""
    
    api_key = os.getenv('CLAUDE_API_KEY')
    
    if not api_key:
        logger.error("❌ CLAUDE_API_KEY not found in .env file")
        logger.info("\n📝 To fix this:")
        logger.info("1. Go to: https://console.anthropic.com/")
        logger.info("2. Create an API key")
        logger.info("3. Add to .env file: CLAUDE_API_KEY=sk-ant-your-key-here")
        return False
    
    logger.info("✓ API key found in .env")
    logger.info(f"Key prefix: {api_key[:15]}...")
    
    try:
        client = Anthropic(api_key=api_key)
        
        logger.info("\n🧪 Testing API connection...")
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": "Respond with exactly: 'API connection successful!'"
            }]
        )
        
        result = response.content[0].text
        logger.info(f"✓ Response: {result}")
        
        if "successful" in result.lower():
            logger.info("\n✅ Claude API connection working!")
            return True
        else:
            logger.warning("\n⚠ Got response but unexpected format")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Error connecting to Claude API: {e}")
        return False

def test_transcript_analysis():
    """Test analyzing a sample transcript."""
    
    logger.info("\n" + "="*60)
    logger.info("Testing Transcript Analysis")
    logger.info("="*60)
    
    # Load sample transcript
    transcript_path = Path(__file__).parent / 'temp' / 'Zoe_transcript.txt'
    
    if not transcript_path.exists():
        logger.warning("⚠ Sample transcript not found. Using demo transcript.")
        sample_transcript = """
        Just caught up with Sarah about the new product launch. 
        She mentioned we need to finalize the marketing strategy by Friday.
        Key points: target audience is 25-35 year olds, budget is $50k, 
        and we should focus on social media campaigns.
        Action items: 1) Schedule meeting with design team, 2) Review competitor analysis.
        """
    else:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            # Skip metadata, read transcript
            lines = f.readlines()
            transcript_start = None
            for i, line in enumerate(lines):
                if "FULL TRANSCRIPT" in line:
                    transcript_start = i + 3  # Skip header and separator
                    break
            
            if transcript_start:
                sample_transcript = ''.join(lines[transcript_start:lines.index("="*60 + "\n", transcript_start)])
            else:
                sample_transcript = ''.join(lines)
    
    logger.info(f"\nTranscript preview (first 200 chars):")
    logger.info(f"{sample_transcript[:200]}...")
    
    api_key = os.getenv('CLAUDE_API_KEY')
    model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    
    client = Anthropic(api_key=api_key)
    
    prompt = f"""Analyze this voice memo transcript and extract structured information.

Transcript:
{sample_transcript}

Please provide:
1. **Summary** (2-3 sentences): Brief overview
2. **Key Points** (bullet list): Main topics discussed
3. **Action Items** (bullet list): Tasks or follow-ups mentioned
4. **People Mentioned** (list with context): Names and their relevance
5. **Topics/Tags** (comma-separated): Categories for organization

Format your response clearly with these sections."""

    logger.info(f"\n🤖 Sending to Claude ({model})...")
    
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        analysis = response.content[0].text
        
        logger.info("\n" + "="*60)
        logger.info("CLAUDE ANALYSIS RESULT")
        logger.info("="*60)
        print(analysis)
        
        # Show token usage
        logger.info("\n" + "="*60)
        logger.info("USAGE STATS")
        logger.info("="*60)
        logger.info(f"Input tokens: {response.usage.input_tokens}")
        logger.info(f"Output tokens: {response.usage.output_tokens}")
        
        # Estimate cost (Claude Sonnet 4 pricing)
        input_cost = (response.usage.input_tokens / 1_000_000) * 3
        output_cost = (response.usage.output_tokens / 1_000_000) * 15
        total_cost = input_cost + output_cost
        
        logger.info(f"Estimated cost: ${total_cost:.4f}")
        
        logger.info("\n✅ Transcript analysis complete!")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error during analysis: {e}")
        return False

def main():
    """Run Claude API tests."""
    
    logger.info("="*60)
    logger.info("Claude API Test Suite")
    logger.info("="*60)
    
    # Test 1: Connection
    if not test_claude_connection():
        logger.error("\n❌ Connection test failed. Fix API key and try again.")
        sys.exit(1)
    
    # Test 2: Analysis
    if not test_transcript_analysis():
        logger.error("\n❌ Analysis test failed.")
        sys.exit(1)
    
    logger.info("\n" + "="*60)
    logger.info("✅ ALL TESTS PASSED!")
    logger.info("="*60)
    logger.info("\nYou're ready to use Claude in the pipeline!")
    logger.info("Next step: Set up Notion API")

if __name__ == '__main__':
    main()
