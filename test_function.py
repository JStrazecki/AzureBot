#!/usr/bin/env python3
# test_function.py - Test Azure Function connection with authentication

import os
import asyncio
import aiohttp
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_function():
    """Test Azure Function with different authentication methods"""
    
    function_url = os.environ.get("AZURE_FUNCTION_URL", "")
    function_key = os.environ.get("AZURE_FUNCTION_KEY", "")
    
    if not function_url:
        print("❌ AZURE_FUNCTION_URL not set")
        return
    
    print(f"Testing Azure Function: {function_url}")
    print(f"Function Key: {'Set' if function_key else 'Not set'}")
    print("-" * 50)
    
    # Test 1: Without authentication
    print("\n1. Testing without authentication:")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                function_url,
                json={"query_type": "metadata"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                print(f"   Status: {response.status}")
                if response.status == 401:
                    print("   ❌ Got 401 Unauthorized (expected without key)")
                elif response.status == 200:
                    print("   ✅ Function allows anonymous access")
                else:
                    print(f"   ❓ Unexpected status: {response.status}")
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
    
    # Test 2: With key in header
    if function_key:
        print("\n2. Testing with key in header (x-functions-key):")
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "x-functions-key": function_key
                }
                async with session.post(
                    function_url,
                    json={"query_type": "metadata"},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"   Status: {response.status}")
                    if response.status == 200:
                        result = await response.json()
                        print("   ✅ Authentication successful!")
                        if "databases" in result:
                            print(f"   ✅ Found {len(result['databases'])} databases")
                            print(f"   First 3: {result['databases'][:3]}")
                    else:
                        text = await response.text()
                        print(f"   ❌ Failed: {text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")
    
    # Test 3: With key in query parameter (like browser)
    print("\n3. Testing with key in URL (like browser):")
    try:
        test_url = function_url
        if function_key and "?" not in test_url:
            test_url += f"?code={function_key}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                test_url + "&query_type=metadata",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    print("   ✅ Query parameter authentication works")
                else:
                    print(f"   ❌ Status: {response.status}")
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
    
    # Test 4: Test actual SQL query
    if function_key:
        print("\n4. Testing actual SQL query:")
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "x-functions-key": function_key
                }
                payload = {
                    "query_type": "single",
                    "query": "SELECT TOP 1 name FROM sys.tables",
                    "database": "master"
                }
                async with session.post(
                    function_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    print(f"   Status: {response.status}")
                    if response.status == 200:
                        result = await response.json()
                        print("   ✅ SQL query executed successfully!")
                        if "rows" in result:
                            print(f"   Rows returned: {len(result['rows'])}")
                            if result['rows']:
                                print(f"   First row: {result['rows'][0]}")
                    else:
                        text = await response.text()
                        print(f"   ❌ Failed: {text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 50)
    print("RECOMMENDATIONS:")
    if not function_key:
        print("1. Get the function key from Azure Portal:")
        print("   - Go to your Function App")
        print("   - Navigate to Functions → HttpQuerySQL")
        print("   - Click 'Function Keys'")
        print("   - Copy the default key")
        print("   - Add as AZURE_FUNCTION_KEY environment variable")
    else:
        print("✅ Function key is configured and working!")
    
    print("\n2. In your bot's app.py, the function is called with:")
    print("   headers = {")
    print('       "Content-Type": "application/json",')
    print('       "x-functions-key": function_key')
    print("   }")

if __name__ == "__main__":
    print("=== Azure Function Connection Test ===\n")
    asyncio.run(test_function())