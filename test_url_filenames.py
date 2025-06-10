#!/usr/bin/env python3
"""
Test URL-based filename generation.
"""

import json
from capabilities.scraping.web_scraper import WebScraper

def test_url_filename_generation():
    """Test URL-based filename generation."""
    
    # Initialize scraper
    scraper = WebScraper(cache_dir="test_url_filenames", cache_expiration_hours=1)
    
    # Test data
    test_article = {
        'url': 'https://www.fotomac.com.tr/galatasaray/2025/06/10/galatasaraya-victor-osimhen-mujdesi-transfer-yarisinda-sona-yaklasildi',
        'title': 'Galatasaray\'a Victor Osimhen müjdesi! Transfer yarışında sona yaklaşıldı',
        'content': 'Test content with proper encoding...',
        'scraped_at': '2025-06-10T23:15:00',
        'extraction_method': 'readability:body -> css:title',
        'site': 'www.fotomac.com.tr'
    }
    
    print("=== Testing URL-based Filename Generation ===")
    print(f"URL: {test_article['url']}")
    print(f"Title: {test_article['title']}")
    
    # Test filename generation
    filename = scraper._generate_url_based_filename(test_article['url'], test_article['title'])
    print(f"Generated filename: {filename}")
    
    # Test saving with URL-based filename
    saved_filename = scraper._save_article_with_url_filename(test_article)
    print(f"Saved as: {saved_filename}")
    
    # Verify file exists
    import os
    filepath = os.path.join("test_url_filenames", saved_filename)
    if os.path.exists(filepath):
        print(f"✅ File successfully saved: {filepath}")
        
        # Load and verify content
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        print(f"Loaded title: {loaded_data.get('title', 'No title')}")
        print(f"Content length: {len(loaded_data.get('content', ''))}")
        
        # Check if filename is URL-based (not just a hash)
        if 'fotomac.com.tr' in saved_filename:
            print("✅ SUCCESS: URL-based filename generation working!")
        else:
            print("❌ ISSUE: Filename appears to be hash-based, not URL-based")
    else:
        print(f"❌ ERROR: File not found at {filepath}")

if __name__ == "__main__":
    test_url_filename_generation()
