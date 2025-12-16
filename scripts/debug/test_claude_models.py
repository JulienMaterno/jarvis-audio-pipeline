"""
Test available Claude models
"""
import os
import sys
from anthropic import Anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def test_claude_models():
    """Test different Claude model names"""
    client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    
    models_to_try = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet-latest",
        "claude-3-sonnet-20240229",
        "claude-3-opus-20240229",
    ]
    
    print("\n" + "="*60)
    print("TESTING CLAUDE MODEL AVAILABILITY")
    print("="*60 + "\n")
    
    for model in models_to_try:
        try:
            print(f"Testing: {model}...", end=" ")
            response = client.messages.create(
                model=model,
                max_tokens=100,
                messages=[{"role": "user", "content": "Say 'working'"}]
            )
            print(f"✅ WORKS - Response: {response.content[0].text}")
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not_found" in error_msg:
                print(f"❌ Model not found")
            else:
                print(f"❌ Error: {error_msg[:100]}")

if __name__ == "__main__":
    test_claude_models()
