"""
Test the Claude multi-database analyzer with correct model
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from llm_analyzer_multi import ClaudeMultiAnalyzer

def test_claude_analysis():
    """Test Claude analysis with a sample transcript"""
    
    analyzer = ClaudeMultiAnalyzer(Config.ANTHROPIC_API_KEY)
    
    test_transcript = """
    Had a great evening reflection today. I've been thinking about my morning routine 
    and how I can be more productive. I realized I need to start waking up earlier, 
    maybe around 6am. Also want to start meditating for 10 minutes each morning.
    
    On another note, I should probably call my mom this weekend, haven't talked to 
    her in a while. And I need to finish that proposal for the client by Friday.
    """
    
    print("\n" + "="*60)
    print("TESTING CLAUDE MULTI-DATABASE ANALYZER")
    print("="*60 + "\n")
    
    print("Test Transcript:")
    print(test_transcript)
    print("\n" + "-"*60 + "\n")
    
    try:
        result = analyzer.analyze_transcript(
            transcript=test_transcript,
            filename="test_reflection.mp3",
            recording_date="2025-11-22"
        )
        
        print("✅ SUCCESS! Claude API is working\n")
        print("Analysis Result:")
        print(json.dumps(result, indent=2))
        
        print("\n" + "="*60)
        print("BREAKDOWN:")
        print("="*60)
        print(f"Primary Category: {result.get('primary_category')}")
        print(f"Has Meeting Data: {result.get('meeting') is not None}")
        print(f"Has Reflection Data: {result.get('reflection') is not None}")
        print(f"Tasks Extracted: {len(result.get('tasks', []))}")
        print(f"CRM Updates: {len(result.get('crm_updates', []))}")
        
        if result.get('reflection'):
            print(f"\nReflection Title: {result['reflection'].get('title')}")
            print(f"Reflection Tags: {result['reflection'].get('tags')}")
        
        if result.get('tasks'):
            print("\nTasks:")
            for i, task in enumerate(result['tasks'], 1):
                print(f"  {i}. {task.get('title')} (Due: {task.get('due_date', 'No date')})")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_claude_analysis()
