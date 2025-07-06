#!/usr/bin/env python3
# debug_openai.py - Debug Azure OpenAI connection issues

import os
import asyncio
import aiohttp
from datetime import datetime

def print_section(title):
    print(f"\n{'='*60}")
    print(f"{title.center(60)}")
    print(f"{'='*60}")

def check_openai_config():
    print_section("AZURE OPENAI CONFIGURATION CHECK")
    
    # Check environment variables
    config = {
        "AZURE_OPENAI_ENDPOINT": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_DEPLOYMENT_NAME": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
        "AZURE_OPENAI_API_VERSION": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
    }
    
    missing = []
    
    print("Environment Variables:")
    for key, value in config.items():
        if value:
            if "KEY" in key:
                masked = value[:8] + "***" + value[-8:] if len(value) > 16 else "***"
                print(f"✓ {key}: {masked}")
            else:
                print(f"✓ {key}: {value}")
        else:
            print(f"✗ {key}: NOT SET")
            if key in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY"]:
                missing.append(key)
    
    return config, missing

async def test_openai_connection(config):
    print_section("AZURE OPENAI CONNECTION TEST")
    
    endpoint = config["AZURE_OPENAI_ENDPOINT"]
    api_key = config["AZURE_OPENAI_API_KEY"]
    deployment = config["AZURE_OPENAI_DEPLOYMENT_NAME"]
    api_version = config["AZURE_OPENAI_API_VERSION"]
    
    if not endpoint or not api_key:
        print("❌ Cannot test - missing endpoint or API key")
        return False
    
    # Clean up endpoint URL
    if endpoint.endswith('/'):
        endpoint = endpoint.rstrip('/')
    
    # Test URL construction
    test_url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    print(f"Testing URL: {test_url}")
    
    # Test headers
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Simple test payload
    payload = {
        "messages": [{"role": "user", "content": "Say 'Hello'"}],
        "max_tokens": 10,
        "temperature": 0
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print("\n🔄 Sending test request...")
            async with session.post(
                test_url, 
                json=payload, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                print(f"Status Code: {response.status}")
                print(f"Response Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    result = await response.json()
                    print("✅ SUCCESS! Azure OpenAI is working")
                    print(f"Response: {result.get('choices', [{}])[0].get('message', {}).get('content', 'No content')}")
                    return True
                    
                elif response.status == 401:
                    print("❌ AUTHENTICATION FAILED")
                    print("Issue: Invalid API key or expired credentials")
                    print("Solution: Check your API key in Azure Portal")
                    return False
                    
                elif response.status == 404:
                    print("❌ DEPLOYMENT NOT FOUND")
                    print(f"Issue: Deployment '{deployment}' not found")
                    print("Solution: Check your deployment name in Azure OpenAI Studio")
                    
                    # List available deployments
                    await list_deployments(endpoint, api_key, api_version)
                    return False
                    
                elif response.status == 429:
                    print("❌ RATE LIMITED")
                    print("Issue: Too many requests or quota exceeded")
                    print("Solution: Check your quota in Azure Portal")
                    return False
                    
                else:
                    error_text = await response.text()
                    print(f"❌ ERROR: {response.status}")
                    print(f"Response: {error_text}")
                    return False
                    
    except asyncio.TimeoutError:
        print("❌ TIMEOUT")
        print("Issue: Request timed out (30 seconds)")
        print("Solution: Check network connectivity or endpoint URL")
        return False
        
    except Exception as e:
        print(f"❌ NETWORK ERROR: {type(e).__name__}")
        print(f"Details: {str(e)}")
        print("Solution: Check endpoint URL format and network connectivity")
        return False

async def list_deployments(endpoint, api_key, api_version):
    """Try to list available deployments"""
    print("\n🔍 Checking available deployments...")
    
    deployments_url = f"{endpoint}/openai/deployments?api-version={api_version}"
    headers = {"api-key": api_key}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                deployments_url, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status == 200:
                    deployments = await response.json()
                    if deployments.get("data"):
                        print("Available deployments:")
                        for dep in deployments["data"]:
                            print(f"  - {dep.get('id', 'Unknown')} ({dep.get('model', 'Unknown model')})")
                    else:
                        print("No deployments found")
                else:
                    print(f"Could not list deployments: {response.status}")
                    
    except Exception as e:
        print(f"Error listing deployments: {str(e)}")

def test_openai_import():
    print_section("OPENAI LIBRARY TEST")
    
    try:
        import openai
        print(f"✓ OpenAI library version: {openai.__version__}")
        
        # Test Azure OpenAI client creation
        from openai import AzureOpenAI
        print("✓ AzureOpenAI class imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ OpenAI library import failed: {e}")
        print("Solution: pip install openai==1.6.1")
        return False
    except Exception as e:
        print(f"❌ OpenAI library error: {e}")
        return False

def test_tiktoken():
    print_section("TIKTOKEN LIBRARY TEST")
    
    try:
        import tiktoken
        print("✓ Tiktoken imported successfully")
        
        # Test encoding
        encoding = tiktoken.encoding_for_model("gpt-4")
        test_text = "Hello, world!"
        tokens = len(encoding.encode(test_text))
        print(f"✓ Test encoding: '{test_text}' = {tokens} tokens")
        
        return True
        
    except ImportError as e:
        print(f"❌ Tiktoken import failed: {e}")
        print("Solution: pip install tiktoken==0.5.2")
        return False
    except Exception as e:
        print(f"❌ Tiktoken error: {e}")
        return False

async def test_sql_translator_init():
    print_section("SQL TRANSLATOR INITIALIZATION TEST")
    
    try:
        # Import the translator
        from azure_openai_sql_translator import AzureOpenAISQLTranslator
        print("✓ AzureOpenAISQLTranslator imported successfully")
        
        # Try to initialize it
        config, missing = check_openai_config()
        
        if missing:
            print(f"❌ Cannot initialize - missing: {', '.join(missing)}")
            return False
        
        translator = AzureOpenAISQLTranslator(
            endpoint=config["AZURE_OPENAI_ENDPOINT"],
            api_key=config["AZURE_OPENAI_API_KEY"],
            deployment_name=config["AZURE_OPENAI_DEPLOYMENT_NAME"],
            api_version=config["AZURE_OPENAI_API_VERSION"]
        )
        
        print("✓ SQL Translator initialized successfully")
        print(f"  - Deployment: {config['AZURE_OPENAI_DEPLOYMENT_NAME']}")
        print(f"  - API Version: {config['AZURE_OPENAI_API_VERSION']}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

def generate_recommendations(results):
    print_section("RECOMMENDATIONS")
    
    if not results['config']:
        print("1. 🔧 FIX ENVIRONMENT VARIABLES:")
        print("   Go to Azure Portal → App Service → Configuration")
        print("   Add missing variables:")
        print("   - AZURE_OPENAI_ENDPOINT: Your OpenAI service endpoint")
        print("   - AZURE_OPENAI_API_KEY: Your OpenAI service key")
        print("   - AZURE_OPENAI_DEPLOYMENT_NAME: Your model deployment name (optional)")
    
    if not results['imports']:
        print("\n2. 📦 FIX PACKAGE IMPORTS:")
        print("   The OpenAI package may not be installed correctly")
        print("   Check requirements.txt and redeploy")
    
    if not results['connection']:
        print("\n3. 🌐 FIX CONNECTION ISSUES:")
        print("   - Verify endpoint URL format")
        print("   - Check API key validity")
        print("   - Confirm deployment name exists")
        print("   - Check quotas in Azure Portal")
    
    if not results['translator']:
        print("\n4. 🔧 FIX TRANSLATOR INITIALIZATION:")
        print("   The SQL translator failed to initialize")
        print("   This may be due to config or connection issues above")
    
    print("\n5. 📋 QUICK FIXES TO TRY:")
    print("   a) Restart the App Service")
    print("   b) Check Azure OpenAI service status")
    print("   c) Regenerate API key if needed")
    print("   d) Try a different deployment name")

async def main():
    print_section(f"AZURE OPENAI DEBUG - {datetime.now()}")
    
    results = {
        'config': False,
        'imports': False,
        'connection': False,
        'translator': False
    }
    
    # Test configuration
    config, missing = check_openai_config()
    results['config'] = len(missing) == 0
    
    # Test imports
    results['imports'] = test_openai_import() and test_tiktoken()
    
    # Test connection (only if config is OK)
    if results['config']:
        results['connection'] = await test_openai_connection(config)
    
    # Test translator initialization
    results['translator'] = await test_sql_translator_init()
    
    # Summary
    print_section("SUMMARY")
    
    tests = [
        ("Configuration", results['config']),
        ("Package Imports", results['imports']),
        ("OpenAI Connection", results['connection']),
        ("Translator Init", results['translator'])
    ]
    
    passed = sum(1 for _, status in tests if status)
    total = len(tests)
    
    for name, status in tests:
        status_text = "✅ PASS" if status else "❌ FAIL"
        print(f"{name}: {status_text}")
    
    print(f"\nOVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Azure OpenAI is fully working!")
    else:
        print(f"\n❌ {total - passed} issues found.")
        generate_recommendations(results)

if __name__ == "__main__":
    asyncio.run(main())