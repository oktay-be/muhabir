#!/usr/bin/env python3
"""Test script to check journ4list import."""

try:
    from journ4list import Journalist
    print("✅ journ4list import successful")
    print("Journalist class:", Journalist)
    
    # Test creating an instance
    journalist = Journalist()
    print("✅ Journalist instance created successfully")
    
except ImportError as e:
    print("❌ Import failed:", e)
except Exception as e:
    print("❌ Other error:", e)
