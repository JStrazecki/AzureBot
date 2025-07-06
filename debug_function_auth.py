# debug_function_auth.py - Debug Azure Function Authentication Issue
#!/usr/bin/env python3
"""
Debug script to test Azure Function authentication
Run this to find out why authentication is failing
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text.center(60)}")
    print(f"{'='*60}\n")

async def test_function_auth():
    """Test Azure Function with different authentication methods"""
    
    # Get environment variables
    function_url = os.environ.get("AZURE_FUNCTION_URL", "")
    function_key = os.environ.get("AZURE_FUNCTION_KEY", "")
    
    print_header("AZURE FUNCTION AUTHENTICATION DEBUG")
    
    print("Environment Variables:")
    print(f"AZURE_FUNCTION_URL: {function_url}")
    if function_key:
        print(f"AZURE_FUNCTION_KEY: {function_key[:8]}...{function_key[-8:]}")
        print(f"Key Length: {len(function_key)} characters")
    else:
        print("AZURE_FUNCTION_KEY: NOT SET")
    
    if not function_url:
        print("\n❌ AZURE_FUNCTION_URL not set!")
        return
    
    # Test 1: Without authentication
    print_header("Test 1: No Authentication")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                function_url,
                json={"query_type": "metadata"},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                if response.status != 200:
                    text = await response.text()
                    print(f"Response: {text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: With x-functions-key header
    if function_key:
        print_header("Test 2: x-functions-key Header")
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "x-functions-key": function_key
                }
                print(f"Sending headers: {list(headers.keys())}")
                
                async with session.post(
                    function_url,
                    json={"query_type": "metadata"},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print("✅ SUCCESS!")
                        print(f"Response: {json.dumps(data, indent=2)[:500]}")
                    else:
                        text = await response.text()
                        print(f"❌ Failed: {text[:500]}")
        except Exception as e:
            print(f"Error: {e}")
    
    # Test 3: With code query parameter
    if function_key:
        print_header("Test 3: Code Query Parameter")
        try:
            # Add code to URL
            separator = "&" if "?" in function_url else "?"
            test_url = f"{function_url}{separator}code={function_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    test_url,
                    json={"query_type": "metadata"},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        print("✅ Query parameter auth works!")
                    else:
                        print("❌ Query parameter auth failed")
        except Exception as e:
            print(f"Error: {e}")
    
    # Test 4: Check key format
    if function_key:
        print_header("Key Analysis")
        print(f"Key starts with: {function_key[:20]}...")
        print(f"Key ends with: ...{function_key[-20:]}")
        print(f"Contains spaces: {' ' in function_key}")
        print(f"Contains newlines: {'\\n' in function_key}")
        print(f"Contains special chars: {any(c in function_key for c in ['<', '>', '&', '"'])}")
        
        # Check if it's a host key or function key
        if function_key.endswith("=="):
            print("Looks like a base64 encoded key (ends with ==)")
        
        # Check common issues
        if function_key.startswith("'") or function_key.endswith("'"):
            print("⚠️ WARNING: Key has quotes - remove them!")
        if function_key.startswith('"') or function_key.endswith('"'):
            print("⚠️ WARNING: Key has double quotes - remove them!")
    
    # Test 5: Direct function info
    print_header("Function URL Analysis")
    print(f"Full URL: {function_url}")
    
    # Parse URL
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(function_url)
    print(f"Host: {parsed.netloc}")
    print(f"Path: {parsed.path}")
    
    if parsed.query:
        params = parse_qs(parsed.query)
        print("Query parameters in URL:")
        for key, values in params.items():
            if key == "code":
                print(f"  - {key}: ***hidden***")
            else:
                print(f"  - {key}: {values}")
    
    # Recommendations
    print_header("RECOMMENDATIONS")
    
    if not function_key:
        print("1. You need to set AZURE_FUNCTION_KEY")
        print("   - Go to Azure Portal")
        print("   - Navigate to your Function App")
        print("   - Go to Functions → QuerySQL")
        print("   - Click 'Function Keys'")
        print("   - Copy the 'default' key (not the _master key)")
    else:
        print("1. Make sure you're using the correct key:")
        print("   - Function keys are specific to each function")
        print("   - Don't use the host key or master key")
        print("   - The key should be the 'default' function key")
        
        print("\n2. Check the key format:")
        print("   - No quotes around the key")
        print("   - No extra spaces or newlines")
        print("   - Should be a long base64 string")
        
        print("\n3. Verify in Azure Portal:")
        print("   - Function App → QuerySQL → Function Keys")
        print("   - Try regenerating the key if needed")
        
        print("\n4. Test directly in browser:")
        print(f"   {function_url}?code=YOUR_KEY&query_type=metadata")

if __name__ == "__main__":
    asyncio.run(test_function_auth())