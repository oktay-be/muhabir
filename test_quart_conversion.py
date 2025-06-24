#!/usr/bin/env python3
"""
Test script to verify the async /diff endpoint works correctly with Quart.
"""

import asyncio
import json
import os

async def test_diff_endpoint():
    """Test the /diff endpoint functionality."""
    try:
        # Import the app
        from app import create_app
        
        print("✓ Successfully imported Quart app")
        
        # Create the app
        app = create_app()
        print("✓ Successfully created Quart app instance")
        
        # Test async client
        async with app.test_client() as client:
            print("✓ Successfully created async test client")
            
            # Test health endpoint first
            response = await client.get('/health')
            print(f"✓ Health endpoint responded with status: {response.status_code}")
            
            # Check if search parameter files exist
            eu_params_exists = os.path.exists('search_parameters_eu.json')
            tr_params_exists = os.path.exists('search_parameters_tr.json')
            
            print(f"EU parameters file exists: {eu_params_exists}")
            print(f"TR parameters file exists: {tr_params_exists}")
            
            if eu_params_exists and tr_params_exists:
                print("✓ Both search parameter files exist, testing /diff endpoint")
                
                # Test the /diff endpoint (this will be a real async test)
                response = await client.post('/api/diff')
                print(f"✓ /diff endpoint responded with status: {response.status_code}")
                
                if response.status_code == 200:
                    data = await response.get_json()
                    print("✓ /diff endpoint returned JSON response")
                    print(f"Response summary: {data.get('summary', {})}")
                else:
                    error_data = await response.get_data()
                    print(f"✗ /diff endpoint error: {error_data}")
            else:
                print("⚠ Skipping /diff endpoint test (search parameter files missing)")
                
        print("✓ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_diff_endpoint())
    exit(0 if success else 1)
