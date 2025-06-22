#!/usr/bin/env python3
"""
Quick test to verify the new AISummarizer architecture
"""

from capabilities.ai_summarizer import AISummarizer
import os

def main():
    print("=== AISummarizer Architecture Verification ===")
    
    # Initialize the summarizer
    try:
        summarizer = AISummarizer()
        print("✓ AISummarizer initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize AISummarizer: {e}")
        return
    
    # Check if we have any session data files to test with
    workspace_path = '.journalist_workspace'
    session_files_found = []
    
    if os.path.exists(workspace_path):
        print(f"✓ Found .journalist_workspace directory")
        for root, dirs, files in os.walk(workspace_path):
            session_files = [f for f in files if f.startswith('session_data_') and f.endswith('.json')]
            if session_files:
                session_files_found.extend([os.path.join(root, f) for f in session_files])
        
        if session_files_found:
            print(f"✓ Found {len(session_files_found)} session data files:")
            for file in session_files_found[:3]:  # Show first 3
                print(f"  - {file}")
        else:
            print("⚠ No session data files found in .journalist_workspace")
    else:
        print("⚠ No .journalist_workspace directory found")
    
    # Check if PROMPT.md exists
    if os.path.exists('PROMPT.md'):
        print("✓ PROMPT.md file found")
        
        # Check PROMPT.md content
        with open('PROMPT.md', 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        print(f"  - PROMPT.md size: {len(prompt_content)} characters")
    else:
        print("✗ PROMPT.md file not found")
    
    # Test the summarize method signature
    try:
        method = getattr(summarizer, 'summarize_and_classify_session_data_object')
        print("✓ summarize_and_classify_session_data_object method exists")
    except AttributeError:
        print("✗ summarize_and_classify_session_data_object method not found")
    
    print("\n=== Architecture Verification Complete ===")
    
    # If we have session files, show how to test
    if session_files_found:
        print(f"\nTo test with real data, you can run:")
        print(f"result = summarizer.summarize_and_classify_session_data_object('{session_files_found[0]}')")

if __name__ == "__main__":
    main()
