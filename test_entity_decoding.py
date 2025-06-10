#!/usr/bin/env python3
"""
Test HTML entity decoding in the enhanced scraper.
"""

import asyncio
import logging
from bs4 import BeautifulSoup
from readability import Document

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_html_entity_decoding():
    """Test HTML entity decoding with different approaches."""
    
    # Sample HTML with entity encoding issues (like in fotomac.com.tr)
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Galatasaray&apos;a Victor Osimhen Müjdesi</title>
    </head>
    <body>
        <article>
            <h1>Galatasaray&apos;a Victor Osimhen müjdesi! Transfer yarışında sona yaklaşıldı</h1>
            <div class="news-text">
                <p>Galatasaray&apos;ın hedefindeki Victor Osimhen için kritik saatler yaşanıyor&hellip;</p>
                <p>Nijeryalı yıldız&apos;ın transferi için görüşmeler devam ediyor.</p>
                <p>Bu sezon&apos;da takımın en önemli transferlerinden biri olması bekleniyor&hellip;</p>
            </div>
        </article>
    </body>
    </html>
    """
    
    print("=== Original HTML (with entities) ===")
    print(sample_html[:200] + "...")
    
    # Test 1: Beautiful Soup only (current problematic approach)
    print("\n=== Test 1: Beautiful Soup only ===")
    soup = BeautifulSoup(sample_html, "html.parser")
    title_bs = soup.find('h1').get_text(strip=True) if soup.find('h1') else "No title"
    content_bs = soup.find('div', class_='news-text').get_text(separator='\n', strip=True) if soup.find('div', class_='news-text') else "No content"
    
    print(f"Title (BeautifulSoup): {title_bs}")
    print(f"Content (BeautifulSoup): {content_bs[:100]}...")
    
    # Test 2: Readability-lxml (enhanced approach)
    print("\n=== Test 2: Readability-lxml ===")
    try:
        doc = Document(sample_html)
        title_readability = doc.title()
        content_html = doc.summary(html_partial=True)
        content_soup = BeautifulSoup(content_html, "html.parser")
        
        # Extract text with proper HTML entity decoding
        body_paragraphs = [p.get_text(strip=True) for p in content_soup.find_all(['p', 'div'])]
        content_readability = "\n\n".join(filter(None, body_paragraphs))
        
        print(f"Title (Readability): {title_readability}")
        print(f"Content (Readability): {content_readability[:100]}...")
        
    except Exception as e:
        print(f"Readability failed: {e}")
    
    # Test 3: HTML entity decoding check
    print("\n=== Test 3: Entity Decoding Analysis ===")
    
    entities_found = {
        'apos': '&apos;' in sample_html,
        'hellip': '&hellip;' in sample_html,
        'apos_in_bs': '&apos;' in title_bs or '&apos;' in content_bs,
        'hellip_in_bs': '&hellip;' in content_bs,
    }
    
    if 'title_readability' in locals():
        entities_found.update({
            'apos_in_readability': '&apos;' in title_readability or '&apos;' in content_readability,
            'hellip_in_readability': '&hellip;' in content_readability,
        })
    
    print("Entity presence analysis:")
    for key, value in entities_found.items():
        print(f"  {key}: {value}")
    
    # Success criteria
    print("\n=== Results ===")
    if 'title_readability' in locals():
        bs_has_entities = entities_found['apos_in_bs'] or entities_found['hellip_in_bs']
        readability_has_entities = entities_found['apos_in_readability'] or entities_found['hellip_in_readability']
        
        print(f"BeautifulSoup still has HTML entities: {bs_has_entities}")
        print(f"Readability still has HTML entities: {readability_has_entities}")
        
        if not readability_has_entities and bs_has_entities:
            print("✅ SUCCESS: Readability-lxml properly decodes HTML entities!")
        elif readability_has_entities:
            print("❌ ISSUE: Readability-lxml still has entity encoding issues")
        else:
            print("ℹ️  Both methods seem to handle entities, but readability provides better content extraction")
    else:
        print("❌ ISSUE: Readability-lxml failed to process content")

if __name__ == "__main__":
    asyncio.run(test_html_entity_decoding())
