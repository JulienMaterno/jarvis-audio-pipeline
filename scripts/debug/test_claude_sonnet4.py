"""
Test Claude Sonnet 4 / 4.5 model names
"""
import os
import sys
from anthropic import Anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def test_claude_sonnet_4():
    """Test Claude Sonnet 4 variations"""
    client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    
    models_to_try = [
        "claude-sonnet-4-20250514",  # From your .env
        "claude-sonnet-4-20241022",
        "claude-sonnet-4.5-20241022",
        "claude-4-sonnet-20241022",
        "claude-3-5-sonnet-20241022",
    ]
    
    print("\n" + "="*60)
    print("TESTING CLAUDE SONNET 4/4.5 MODELS")
    print("="*60 + "\n")
    
    for model in models_to_try:
        try:
            print(f"Testing: {model}...", end=" ")
            response = client.messages.create(
                model=model,
                max_tokens=20,
                messages=[{"role": "user", "content": "Say 'working'"}]
            )
            print(f"✅ WORKS")
            print(f"   Response: {response.content[0].text}")
            return model  # Return the first working model
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not_found" in error_msg:
                print(f"❌ Not found")
            elif "400" in error_msg:
                print(f"❌ Bad request: {error_msg[:100]}")
            else:
                print(f"❌ Error: {error_msg[:100]}")
    
    print("\n⚠️  None of the models worked!")
    return None

if __name__ == "__main__":
    working_model = test_claude_sonnet_4()
    if working_model:
        print(f"\n✅ Use this model: {working_model}")
