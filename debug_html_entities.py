#!/usr/bin/env python3
"""
Script to debug HTML entity decoding issues in scraped content.
"""

import json
import html
from bs4 import BeautifulSoup

def test_html_entity_decoding():
    """Test HTML entity decoding with sample corrupted data."""
    
    # Sample text with HTML entities (similar to what we see in scraped data)
    corrupted_samples = [
        "Galatasaray&apos;ın yıldız futbolcusu&hellip;",
        "Transfer s&uuml;reci devam ediyor&hellip;",
        "Fenerbah&ccedil;e&apos;nin yeni transferi&hellip;",
        "Be&şti;ikta&şti;&apos;ın son hamlesi&hellip;"
    ]
    
    print("=== HTML Entity Decoding Test ===")
    print()
    
    for i, corrupted_text in enumerate(corrupted_samples, 1):
        print(f"Sample {i}:")
        print(f"  Original (corrupted): {corrupted_text}")
        
        # Test html.unescape
        html_decoded = html.unescape(corrupted_text)
        print(f"  html.unescape():     {html_decoded}")
        
        # Test BeautifulSoup parsing and extraction
        soup = BeautifulSoup(f"<p>{corrupted_text}</p>", 'html.parser')
        soup_decoded = soup.get_text()
        print(f"  BeautifulSoup text:  {soup_decoded}")
        print()

def test_with_actual_scraped_data():
    """Test with actual scraped data from the fotomac file."""
    
    # Load sample scraped data
    sample_file = r"c:\Users\oktay\Documents\aisports\workspace\20250610_222720_690037\www.fotomac.com.tr__galatasaray_2025_06_10_galatasaraya-victor-osimhen-mujdesi-transfer-yarisinda-sona-yaklasildi_3ea443.json"
    
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("=== Actual Scraped Data Test ===")
        print()
        
        title = data.get('title', '')
        content = data.get('content', '')
        
        print("TITLE:")
        print(f"  Original: {title}")
        print(f"  Decoded:  {html.unescape(title)}")
        print()
        
        print("CONTENT (first 200 chars):")
        print(f"  Original: {content[:200]}...")
        print(f"  Decoded:  {html.unescape(content)[:200]}...")
        print()
        
        # Check for common HTML entities
        entities_found = []
        for entity in ['&apos;', '&hellip;', '&uuml;', '&ccedil;', '&Ccedil;', '&ouml;', '&Ouml;', '&iacute;']:
            if entity in title or entity in content:
                entities_found.append(entity)
        
        if entities_found:
            print(f"HTML entities found: {', '.join(entities_found)}")
        else:
            print("No common HTML entities found in this sample.")
            
    except Exception as e:
        print(f"Error loading sample data: {e}")

if __name__ == "__main__":
    test_html_entity_decoding()
    test_with_actual_scraped_data()
