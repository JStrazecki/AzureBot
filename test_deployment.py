#!/usr/bin/env python3
# test_deployment.py - Comprehensive deployment test script for Azure Bot
"""
Test script to verify SQL Assistant Bot deployment in Azure
Run this in Kudu console to check all components
"""

import os
import sys
import json
import importlib
import asyncio
from datetime import datetime

# Colors for output (work in Kudu console)
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

# Test 1: Python Version and Environment
def test_python_environment():
    print_header("Python Environment Check")
    
    print(f"Python Version: {sys.version}")
    print(f"Python Path: {sys.executable}")
    print(f"Current Directory: {os.getcwd()}")
    
    # Check if we're in the right directory
    expected_files = ['app.py', 'teams_sql_bot.py', 'azure_openai_sql_translator.py']
    missing_files = []
    
    for file in expected_files:
        if os.path.exists(file):
            print_success(f"Found {file}")
        else:
            print_error(f"Missing {file}")
            missing_files.append(file)
    
    return len(missing_files) == 0

# Test 2: Environment Variables
def test_environment_variables():
    print_header("Environment Variables Check")
    
    required_vars = {
        "MICROSOFT_APP_ID": "Bot Framework App ID",
        "MICROSOFT_APP_PASSWORD": "Bot Framework Password", 
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI Endpoint",
        "AZURE_OPENAI_API_KEY": "Azure OpenAI API Key",
        "AZURE_FUNCTION_URL": "Azure Function URL",
        "AZURE_FUNCTION_KEY": "Azure Function Key"
    }
    
    optional_vars = {
        "MCP_SERVER_URL": "MCP Server URL (optional)",
        "DEPLOYMENT_ENV": "Deployment Environment",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "OpenAI Deployment Name",
        "PORT": "Application Port"
    }
    
    all_good = True
    
    print("Required Variables:")
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "PASSWORD" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                print_success(f"{var}: {masked} ({description})")
            else:
                print_success(f"{var}: {value[:30]}... ({description})")
        else:
            print_error(f"{var}: NOT SET ({description})")
            all_good = False
    
    print("\nOptional Variables:")
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if value:
            print_info(f"{var}: {value} ({description})")
        else:
            print_warning(f"{var}: Not set ({description})")
    
    return all_good

# Test 3: Package Dependencies
def test_packages():
    print_header("Package Dependencies Check")
    
    packages = [
        ("aiohttp", "Web framework"),
        ("botbuilder.core", "Bot Framework SDK"),
        ("openai", "Azure OpenAI client"),
        ("tiktoken", "Token counting"),
        ("gunicorn", "WSGI server"),
        ("pyodbc", "SQL database connector"),
        ("azure.identity", "Azure authentication")
    ]
    
    all_good = True
    
    for package, description in packages:
        try:
            if "." in package:
                parts = package.split(".")
                module = __import__(parts[0])
                for part in parts[1:]:
                    module = getattr(module, part)
            else:
                __import__(package)
            print_success(f"{package}: Installed ({description})")
        except ImportError as e:
            print_error(f"{package}: NOT INSTALLED ({description}) - {str(e)}")
            all_good = False
    
    return all_good

# Test 4: Module Imports
def test_module_imports():
    print_header("Module Import Test")
    
    modules_to_test = [
        "teams_sql_bot",
        "azure_openai_sql_translator", 
        "autonomous_sql_explorer",
        "query_validator",
        "token_limiter"
    ]
    
    all_good = True
    
    for module_name in modules_to_test:
        try:
            module = importlib.import_module(module_name)
            print_success(f"Successfully imported {module_name}")
            
            # Check for expected classes
            if module_name == "teams_sql_bot":
                if hasattr(module, 'SQLAssistantBot'):
                    print_success(f"  - Found SQLAssistantBot class")
                else:
                    print_error(f"  - Missing SQLAssistantBot class")
                    all_good = False
                    
            elif module_name == "azure_openai_sql_translator":
                if hasattr(module, 'AzureOpenAISQLTranslator'):
                    print_success(f"  - Found AzureOpenAISQLTranslator class")
                else:
                    print_error(f"  - Missing AzureOpenAISQLTranslator class")
                    all_good = False
                    
        except ImportError as e:
            print_error(f"Failed to import {module_name}: {str(e)}")
            all_good = False
    
    return all_good

# Test 5: Azure Function Connectivity
async def test_azure_function():
    print_header("Azure Function Connectivity Test")
    
    function_url = os.environ.get("AZURE_FUNCTION_URL")
    function_key = os.environ.get("AZURE_FUNCTION_KEY")
    
    if not function_url:
        print_error("AZURE_FUNCTION_URL not set")
        return False
    
    if not function_key:
        print_warning("AZURE_FUNCTION_KEY not set - may get 401 errors")
    
    try:
        import aiohttp
        
        # Test 1: Health check
        print_info("Testing function health endpoint...")
        async with aiohttp.ClientSession() as session:
            headers = {"x-functions-key": function_key} if function_key else {}
            
            # Try health endpoint
            health_url = function_url.replace("/query", "/health")
            try:
                async with session.get(health_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    print_info(f"Health check status: {response.status}")
                    if response.status == 200:
                        print_success("Function health check passed")
                    elif response.status == 404:
                        print_warning("Health endpoint not found (normal for basic functions)")
                    else:
                        print_warning(f"Unexpected status: {response.status}")
            except:
                print_warning("Health endpoint not available")
            
            # Test 2: Metadata query
            print_info("\nTesting metadata query...")
            headers["Content-Type"] = "application/json"
            payload = {"query_type": "metadata"}
            
            async with session.post(function_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                print_info(f"Metadata query status: {response.status}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        if "databases" in result:
                            print_success(f"Function is working! Found {len(result['databases'])} databases")
                            # Show first 3 databases
                            for db in result['databases'][:3]:
                                print_info(f"  - {db}")
                            if len(result['databases']) > 3:
                                print_info(f"  ... and {len(result['databases']) - 3} more")
                            return True
                        else:
                            print_success("Function responded but no databases found")
                            return True
                    except:
                        print_error("Failed to parse function response")
                        return False
                        
                elif response.status == 401:
                    print_error("Authentication failed - check AZURE_FUNCTION_KEY")
                    print_info("Get the key from Azure Portal:")
                    print_info("  1. Go to your Function App")
                    print_info("  2. Navigate to Functions → QuerySQL")
                    print_info("  3. Click 'Function Keys'")
                    print_info("  4. Copy the default key")
                    return False
                    
                else:
                    text = await response.text()
                    print_error(f"Function returned error: {response.status}")
                    print_error(f"Response: {text[:200]}")
                    return False
                    
    except Exception as e:
        print_error(f"Error testing function: {type(e).__name__}: {str(e)}")
        return False

# Test 6: Azure OpenAI Connectivity
async def test_azure_openai():
    print_header("Azure OpenAI Connectivity Test")
    
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
    
    if not endpoint or not api_key:
        print_error("Azure OpenAI credentials not set")
        return False
    
    try:
        import aiohttp
        
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-01"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [{"role": "user", "content": "Say 'OK'"}],
            "max_tokens": 5
        }
        
        print_info(f"Testing Azure OpenAI at: {endpoint}")
        print_info(f"Using deployment: {deployment}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                print_info(f"Response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    if "choices" in result:
                        print_success("Azure OpenAI is working!")
                        print_info(f"Response: {result['choices'][0]['message']['content']}")
                        return True
                    else:
                        print_error("Unexpected response format")
                        return False
                        
                elif response.status == 404:
                    print_error(f"Deployment '{deployment}' not found")
                    print_info("Check your AZURE_OPENAI_DEPLOYMENT_NAME")
                    return False
                    
                elif response.status == 401:
                    print_error("Authentication failed - check AZURE_OPENAI_API_KEY")
                    return False
                    
                else:
                    text = await response.text()
                    print_error(f"Azure OpenAI error: {response.status}")
                    print_error(f"Response: {text[:200]}")
                    return False
                    
    except Exception as e:
        print_error(f"Error testing Azure OpenAI: {type(e).__name__}: {str(e)}")
        return False

# Test 7: Main App Import
def test_main_app():
    print_header("Main Application Test")
    
    try:
        # Try to import the main app
        from app import APP
        print_success("Successfully imported main app (app.py)")
        
        # Check if APP has required attributes
        if hasattr(APP, 'router'):
            print_success("APP has router configured")
            
            # Check routes
            routes = []
            for route in APP.router.routes():
                routes.append(f"{route.method} {route.resource.canonical}")
            
            print_info("Configured routes:")
            for route in routes:
                print_info(f"  - {route}")
        else:
            print_error("APP missing router")
            
        return True
        
    except ImportError as e:
        print_error(f"Failed to import app.py: {str(e)}")
        print_info("This usually means there's an import error in one of the modules")
        return False
    except Exception as e:
        print_error(f"Error testing app: {type(e).__name__}: {str(e)}")
        return False

# Main test runner
async def run_all_tests():
    print_header("SQL Assistant Bot Deployment Test")
    print(f"Test started at: {datetime.now()}")
    
    results = {
        "Python Environment": test_python_environment(),
        "Environment Variables": test_environment_variables(),
        "Package Dependencies": test_packages(),
        "Module Imports": test_module_imports(),
        "Azure Function": await test_azure_function(),
        "Azure OpenAI": await test_azure_openai(),
        "Main Application": test_main_app()
    }
    
    # Summary
    print_header("Test Summary")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print_success("\n🎉 All tests passed! Your bot is ready to use.")
    else:
        print_error(f"\n❌ {total_tests - passed_tests} tests failed. Please fix the issues above.")
        
        # Provide specific recommendations
        print("\n" + "="*60)
        print("RECOMMENDED FIXES:")
        
        if not results["Environment Variables"]:
            print("\n1. Set missing environment variables in Azure Portal:")
            print("   - Go to your App Service")
            print("   - Navigate to Configuration → Application settings")
            print("   - Add the missing variables")
            
        if not results["Package Dependencies"]:
            print("\n2. Install missing packages:")
            print("   - Check requirements.txt")
            print("   - Redeploy through GitHub Actions")
            
        if not results["Module Imports"]:
            print("\n3. Fix import errors:")
            print("   - Check that all .py files are in the root directory")
            print("   - Remove any 'good.' prefixes from imports")
            
        if not results["Azure Function"]:
            print("\n4. Fix Azure Function connection:")
            print("   - Verify AZURE_FUNCTION_URL is correct")
            print("   - Get the function key from Azure Portal")
            print("   - Test the function directly in browser")

if __name__ == "__main__":
    # Run the async tests
    asyncio.run(run_all_tests())