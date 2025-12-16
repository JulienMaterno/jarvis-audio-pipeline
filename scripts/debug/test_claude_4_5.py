"""
Test Claude Sonnet 4.5 availability
"""
import os
import sys
from anthropic import Anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def test_sonnet_4_5():
    """Test Claude Sonnet 4.5 model names"""
    client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    
    models_to_try = [
        "claude-sonnet-4.5-20250514",
        "claude-sonnet-4-5-20250514",
        "claude-3-5-sonnet-20241022",  # This might be the "4.5" equivalent
        "claude-3-5-sonnet-20240620",
        "claude-sonnet-4-20250514",  # Current working model
    ]
    
    print("\n" + "="*60)
    print("TESTING CLAUDE SONNET 4.5 / 3.5 MODELS")
    print("="*60 + "\n")
    
    working_models = []
    
    for model in models_to_try:
        try:
            print(f"Testing: {model}...", end=" ")
            response = client.messages.create(
                model=model,
                max_tokens=50,
                messages=[{"role": "user", "content": "What model are you?"}]
            )
            print(f"✅ WORKS")
            print(f"   Response: {response.content[0].text[:100]}")
            working_models.append(model)
            print()
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not_found" in error_msg:
                print(f"❌ Not found")
            else:
                print(f"❌ Error: {error_msg[:80]}")
    
    if working_models:
        print("\n" + "="*60)
        print(f"✅ Found {len(working_models)} working model(s)")
        print("="*60)
        for model in working_models:
            print(f"  • {model}")

if __name__ == "__main__":
    test_sonnet_4_5()
