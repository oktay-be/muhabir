#!/usr/bin/env python3
"""
Simple test script for the rebuilt AISummarizer.
Tests the summarize_and_classify_session_data_object method.
"""

import asyncio
import os
import json
from pathlib import Path
from capabilities.ai_summarizer import AISummarizer

async def test_ai_summarizer():
    """Test the AISummarizer with a session data file."""
    print("🧪 Testing AISummarizer with session data processing...")
    
    # Check if Google API key is available
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  GOOGLE_API_KEY not set. Set it to test with real API.")
        print("Testing basic initialization and file loading only...")
      # Initialize the summarizer
    try:
        summarizer = AISummarizer()
        print(f"✅ AISummarizer initialized successfully")
        print(f"   Model ready: {summarizer.model is not None}")
    except Exception as e:
        print(f"❌ Failed to initialize AISummarizer: {e}")
        return
      # Use the hardcoded session data file
    test_file = "session_data_fanatik_com_tr.json"
    
    print(f"🔍 Looking for session data file: {test_file}")
    print(f"📂 Current working directory: {os.getcwd()}")
    print(f"📋 Files in current directory:")
    try:
        for file in sorted(os.listdir(".")):
            if file.endswith('.json'):
                print(f"   📄 {file}")
    except Exception as e:
        print(f"   ❌ Error listing files: {e}")
    
    # Also check the journalist workspace
    workspace_path = ".journalist_workspace"
    if Path(workspace_path).exists():
        print(f"📋 Checking {workspace_path} directory:")
        for session_dir in Path(workspace_path).iterdir():
            if session_dir.is_dir():
                print(f"   📁 {session_dir.name}/")
                for file in session_dir.iterdir():
                    if file.name.endswith('.json'):
                        print(f"      📄 {file.name}")
    
    if not Path(test_file).exists():
        print(f"❌ Session data file not found: {test_file}")
        print("💡 Trying to find session file in workspace...")
        
        # Try to find the file in the workspace
        workspace_file = ".journalist_workspace/20250621_235627_808728/session_data_fanatik_com_tr.json"
        if Path(workspace_file).exists():
            test_file = workspace_file
            print(f"✅ Found file in workspace: {test_file}")
        else:
            print(f"❌ File not found in workspace either: {workspace_file}")
            return    
    print(f"📁 Using session data file: {test_file}")
    print(f"📏 File size: {Path(test_file).stat().st_size} bytes")
    print(f"\n🔄 Testing with session file: {test_file}")
    
    # Load and preview the session data
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        print(f"📊 Session data preview:")
        print(f"   Domain: {session_data.get('source_domain', 'N/A')}")
        print(f"   Articles count: {len(session_data.get('articles', []))}")
        print(f"   First article title: {session_data.get('articles', [{}])[0].get('title', 'N/A')[:50]}..." if session_data.get('articles') else "   No articles found")
    except Exception as e:
        print(f"⚠️  Error previewing session data: {e}")
    
    try:
        # Test the main method
        print(f"🚀 Starting AI processing...")
        result = await summarizer.summarize_and_classify_session_data_object(test_file)
        
        print(f"\n📊 Results:")
        print(f"   Has error: {'error' in result}")
        print(f"   Result keys: {list(result.keys())}")
        
        if 'error' not in result:
            processed_articles = result.get('processed_articles', [])
            processing_summary = result.get('processing_summary', {})
            
            print(f"   Processed articles: {len(processed_articles)}")
            print(f"   Processing summary: {processing_summary}")
            
            # Show sample processed article if available
            if processed_articles:
                sample = processed_articles[0]
                print(f"\n📰 Sample processed article:")
                print(f"   Title: {sample.get('title', 'N/A')}")
                print(f"   Categories: {[cat.get('tag') for cat in sample.get('categories', [])]}")
                print(f"   Summary: {sample.get('summary', 'N/A')[:100]}...")
            
            print(f"\n🎉 Test completed successfully!")
        else:
            print(f"   Error: {result.get('error', 'Unknown error')}")
            if 'raw_response' in result:
                print(f"   Raw response preview: {result['raw_response'][:200]}...")
    
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_summarizer())
