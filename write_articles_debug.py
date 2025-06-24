import json
from datetime import datetime

# Example articles variable with the schema you specified
articles = [
    {
        "id": "article_1",
        "original_url": "https://www.fanatik.com.tr/basketbol/fenerbahceden-dario-saric-hamlesi-teklif-yapildi-2585851",
        "title": "Fenerbahçe'den Dario Saric hamlesi! Teklif yapıldı",
        "summary": "Fenerbahçe Beko has reportedly made an offer for Croatian NBA star Dario Saric, who currently plays for the Denver Nuggets. According to Andrea Calzoni, Dubai Basketball is also interested in acquiring Saric. Saric has a player option worth $5,426,400 for the upcoming season with the Nuggets, and it remains uncertain whether he will exercise this option. Before his NBA career, Saric played for Anadolu Efes in Turkey from 2014 to 2016.",
        "key_entities": {
            "teams": [
                "Fenerbahçe Beko",
                "Denver Nuggets",
                "Dubai Basketball",
                "Anadolu Efes"
            ],
            "players": [
                "Dario Saric"
            ],
            "amounts": [
                "5 million 426 thousand 400 Dolar"
            ],
            "dates": [
                "2014-2016"
            ]
        },
        "categories": [
            {
                "tag": "transfers_rumors",
                "confidence": 0.9,
                "evidence": "Fenerbahçe Beko'nun NBA'de Denver Nuggets kadrosunda bulunan Hırvat yıldız Dario Saric için teklifini yaptığı belirtildi."
            },
            {
                "tag": "transfers_negotiations",
                "confidence": 0.7,
                "evidence": "Andrea Calzoni'nin haberine göre Fenerbahçe, Dario Saric için teklifini yaptı."
            },
            {
                "tag": "business_finance",
                "confidence": 0.6,
                "evidence": "Dario Saric'in Denver Nuggets ile olan sözleşmesinde önümüzdeki sezon için 5 milyon 426 bin 400 Dolar'lık bir oyuncu opsiyonu bulunuyor."
            }
        ],
        "source": "www.fanatik.com.tr",
        "published_date": "2025-06-21T19:45:15+03:00",
        "keywords_matched": [
            "fenerbahce"
        ],
        "content_quality": "high",
        "language": "turkish"
    }
]

# Simple script to write articles to JSON file
try:
    # Write to file with proper JSON formatting
    with open("news_api_result.json", 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully wrote {len(articles)} articles to news_api_result.json")
    
except Exception as e:
    print(f"Error writing to file: {str(e)}")
