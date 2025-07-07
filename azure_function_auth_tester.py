#!/usr/bin/env python3
# azure_function_auth_tester.py - Comprehensive Azure Function Authentication Tester
"""
Complete Azure Function Authentication Diagnostic Tool
Tests all possible authentication methods and provides detailed debugging

Usage:
    python3 azure_function_auth_tester.py

Or set environment variables first:
    export AZURE_FUNCTION_URL="your_function_url"
    export AZURE_FUNCTION_KEY="your_function_key"
    python3 azure_function_auth_tester.py
"""

import os
import asyncio
import aiohttp
import json
import sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime
import base64
import time

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text, color=Colors.BLUE):
    """Print a colored header"""
    print(f"\n{color}{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{color}{Colors.BOLD}{text.center(70)}{Colors.END}")
    print(f"{color}{Colors.BOLD}{'='*70}{Colors.END}")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")

def print_step(step, text):
    """Print step message"""
    print(f"{Colors.MAGENTA}{Colors.BOLD}Step {step}:{Colors.END} {text}")

class AzureFunctionTester:
    """Comprehensive Azure Function authentication tester"""
    
    def __init__(self):
        self.function_url = ""
        self.function_key = ""
        self.test_results = []
        self.successful_methods = []
        
    def get_user_input(self):
        """Get function URL and key from user or environment"""
        print_header("Azure Function Authentication Tester")
        print("This tool will test all possible authentication methods for your Azure Function.")
        print()
        
        # Try to get from environment first
        env_url = os.environ.get("AZURE_FUNCTION_URL", "")
        env_key = os.environ.get("AZURE_FUNCTION_KEY", "")
        
        if env_url:
            print_info(f"Found AZURE_FUNCTION_URL in environment: {env_url[:50]}...")
            use_env = input("Use this URL? (y/n): ").lower().strip()
            if use_env in ['y', 'yes', '']:
                self.function_url = env_url
            else:
                self.function_url = input("Enter your Azure Function URL: ").strip()
        else:
            print("Please enter your Azure Function URL.")
            print("Example: https://yourapp.azurewebsites.net/api/QuerySQL")
            print("Or: https://yourapp.azurewebsites.net/api/QuerySQL?code=your_key_here")
            self.function_url = input("Azure Function URL: ").strip()
        
        if env_key and not ('code=' in self.function_url.lower()):
            print_info(f"Found AZURE_FUNCTION_KEY in environment: ***{env_key[-8:]}")
            use_env_key = input("Use this key? (y/n): ").lower().strip()
            if use_env_key in ['y', 'yes', '']:
                self.function_key = env_key
            else:
                self.function_key = input("Enter your Function Key (or press Enter if URL contains key): ").strip()
        else:
            if 'code=' in self.function_url.lower():
                print_info("URL appears to contain authentication code")
                self.function_key = input("Enter additional Function Key if needed (or press Enter): ").strip()
            else:
                print("Please enter your Function Key.")
                print("You can find this in Azure Portal -> Function App -> Functions -> QuerySQL -> Function Keys")
                self.function_key = input("Function Key: ").strip()
    
    def analyze_url(self):
        """Analyze the provided URL"""
        print_header("URL Analysis", Colors.CYAN)
        
        try:
            parsed = urlparse(self.function_url)
            query_params = parse_qs(parsed.query)
            
            print(f"Scheme: {parsed.scheme}")
            print(f"Host: {parsed.netloc}")
            print(f"Path: {parsed.path}")
            print(f"Query: {parsed.query}")
            
            if query_params:
                print("\nQuery Parameters:")
                for key, values in query_params.items():
                    if key.lower() == 'code':
                        print(f"  - {key}: ***{values[0][-8:] if values[0] else 'empty'}")
                    else:
                        print(f"  - {key}: {values}")
            
            # Check for embedded authentication
            has_code = 'code' in query_params
            
            if has_code:
                print_success("URL contains embedded authentication (code parameter)")
            else:
                print_info("URL does not contain embedded authentication")
            
            # Validate URL structure
            if not parsed.scheme:
                print_error("URL missing scheme (http/https)")
                return False
            
            if not parsed.netloc:
                print_error("URL missing host")
                return False
            
            if not parsed.path:
                print_warning("URL missing path - this might cause issues")
            
            return True
            
        except Exception as e:
            print_error(f"Error parsing URL: {e}")
            return False
    
    def analyze_function_key(self):
        """Analyze the function key"""
        print_header("Function Key Analysis", Colors.CYAN)
        
        if not self.function_key:
            print_warning("No function key provided")
            return
        
        print(f"Key length: {len(self.function_key)} characters")
        print(f"Key starts with: {self.function_key[:8]}...")
        print(f"Key ends with: ...{self.function_key[-8:]}")
        
        # Check key format
        issues = []
        
        if len(self.function_key) < 20:
            issues.append("Key seems too short")
        
        if len(self.function_key) > 200:
            issues.append("Key seems too long")
        
        if self.function_key.startswith('"') or self.function_key.endswith('"'):
            issues.append("Key contains quotes - remove them")
        
        if self.function_key.startswith("'") or self.function_key.endswith("'"):
            issues.append("Key contains single quotes - remove them")
        
        if ' ' in self.function_key:
            issues.append("Key contains spaces")
        
        if '\n' in self.function_key or '\r' in self.function_key:
            issues.append("Key contains newlines")
        
        if issues:
            print_warning("Potential issues found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print_success("Function key format looks good")
    
    async def test_method(self, method_name, url, headers, payload, timeout=15):
        """Test a specific authentication method"""
        print_step("TEST", f"Testing {method_name}")
        print(f"URL: {url[:80]}{'...' if len(url) > 80 else ''}")
        print(f"Headers: {list(headers.keys())}")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    print(f"Status Code: {response.status}")
                    print(f"Response Time: {response_time:.1f}ms")
                    print(f"Response Headers: {dict(response.headers)}")
                    
                    # Read response
                    try:
                        if response.headers.get('content-type', '').startswith('application/json'):
                            response_data = await response.json()
                            response_text = json.dumps(response_data, indent=2)[:500]
                        else:
                            response_text = await response.text()
                            response_text = response_text[:500]
                    except:
                        response_text = "Could not read response"
                    
                    print(f"Response Preview: {response_text}")
                    
                    result = {
                        'method': method_name,
                        'success': response.status == 200,
                        'status_code': response.status,
                        'response_time_ms': response_time,
                        'response_preview': response_text,
                        'error': None
                    }
                    
                    if response.status == 200:
                        print_success(f"{method_name} - SUCCESS!")
                        self.successful_methods.append(method_name)
                        
                        # Try to extract database count
                        try:
                            if 'databases' in response_text.lower():
                                if isinstance(response_data, dict) and 'databases' in response_data:
                                    db_count = len(response_data['databases'])
                                    print_success(f"Found {db_count} databases!")
                                    if db_count > 0:
                                        print(f"Sample databases: {response_data['databases'][:3]}")
                        except:
                            pass
                            
                    elif response.status == 401:
                        print_error(f"{method_name} - Authentication failed")
                        result['error'] = 'Authentication failed'
                    elif response.status == 404:
                        print_error(f"{method_name} - Function not found")
                        result['error'] = 'Function not found'
                    elif response.status == 403:
                        print_error(f"{method_name} - Access forbidden")
                        result['error'] = 'Access forbidden'
                    else:
                        print_error(f"{method_name} - HTTP {response.status}")
                        result['error'] = f'HTTP {response.status}'
                    
                    self.test_results.append(result)
                    return result
                    
        except asyncio.TimeoutError:
            print_error(f"{method_name} - Timeout after {timeout} seconds")
            result = {
                'method': method_name,
                'success': False,
                'error': 'Timeout',
                'status_code': None,
                'response_time_ms': timeout * 1000
            }
            self.test_results.append(result)
            return result
            
        except Exception as e:
            print_error(f"{method_name} - Connection error: {e}")
            result = {
                'method': method_name,
                'success': False,
                'error': str(e),
                'status_code': None,
                'response_time_ms': None
            }
            self.test_results.append(result)
            return result
    
    async def test_all_methods(self):
        """Test all authentication methods"""
        print_header("Authentication Method Testing", Colors.GREEN)
        
        # Parse URL
        parsed_url = urlparse(self.function_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        
        # Test payload
        test_payload = {"query_type": "metadata"}
        
        print_info(f"Base URL: {base_url}")
        print_info(f"Test Payload: {test_payload}")
        print()
        
        # Method 1: URL as-is (if it contains code)
        if 'code=' in self.function_url.lower():
            await self.test_method(
                "URL-Embedded Authentication",
                self.function_url,
                {"Content-Type": "application/json"},
                test_payload
            )
            print()
        
        # Method 2: No authentication (anonymous/managed identity)
        await self.test_method(
            "No Authentication (Anonymous/Managed Identity)",
            base_url,
            {"Content-Type": "application/json"},
            test_payload
        )
        print()
        
        # Method 3: Function key in header
        if self.function_key:
            await self.test_method(
                "Function Key in Header (x-functions-key)",
                base_url,
                {
                    "Content-Type": "application/json",
                    "x-functions-key": self.function_key
                },
                test_payload
            )
            print()
        
        # Method 4: Function key in URL parameter
        if self.function_key:
            url_with_code = f"{base_url}?code={self.function_key}"
            await self.test_method(
                "Function Key in URL Parameter (?code=)",
                url_with_code,
                {"Content-Type": "application/json"},
                test_payload
            )
            print()
        
        # Method 5: Try alternative header names
        if self.function_key:
            await self.test_method(
                "Function Key in Authorization Header",
                base_url,
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.function_key}"
                },
                test_payload
            )
            print()
            
            await self.test_method(
                "Function Key in Custom Header (x-api-key)",
                base_url,
                {
                    "Content-Type": "application/json",
                    "x-api-key": self.function_key
                },
                test_payload
            )
            print()
        
        # Method 6: Try with different query parameter names
        if self.function_key:
            url_with_key = f"{base_url}?key={self.function_key}"
            await self.test_method(
                "Function Key as 'key' Parameter",
                url_with_key,
                {"Content-Type": "application/json"},
                test_payload
            )
            print()
            
            url_with_token = f"{base_url}?token={self.function_key}"
            await self.test_method(
                "Function Key as 'token' Parameter",
                url_with_token,
                {"Content-Type": "application/json"},
                test_payload
            )
            print()
        
        # Method 7: GET request instead of POST
        get_url = f"{base_url}?query_type=metadata"
        if self.function_key:
            get_url += f"&code={self.function_key}"
        
        print_step("TEST", "GET Request with Query Parameters")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(get_url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    print(f"GET Status Code: {response.status}")
                    response_text = await response.text()
                    print(f"GET Response: {response_text[:200]}")
                    
                    if response.status == 200:
                        print_success("GET method works!")
                        self.successful_methods.append("GET Request")
        except Exception as e:
            print_error(f"GET request failed: {e}")
        
        print()
    
    def generate_summary(self):
        """Generate a summary of all test results"""
        print_header("Test Results Summary", Colors.MAGENTA)
        
        total_tests = len(self.test_results)
        successful_tests = len(self.successful_methods)
        
        print(f"Total tests run: {total_tests}")
        print(f"Successful methods: {successful_tests}")
        print()
        
        if self.successful_methods:
            print_success("🎉 WORKING METHODS FOUND:")
            for i, method in enumerate(self.successful_methods, 1):
                print(f"  {i}. {method}")
            print()
        else:
            print_error("❌ NO WORKING METHODS FOUND")
            print()
        
        # Show all results
        print("Detailed Results:")
        print("-" * 50)
        
        for result in self.test_results:
            status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
            error_info = f" ({result['error']})" if result.get('error') else ""
            time_info = f" - {result['response_time_ms']:.1f}ms" if result.get('response_time_ms') else ""
            
            print(f"{status}: {result['method']}{error_info}{time_info}")
        
        print()
    
    def generate_recommendations(self):
        """Generate recommendations based on test results"""
        print_header("Recommendations", Colors.YELLOW)
        
        if self.successful_methods:
            print_success("🎯 RECOMMENDED ACTIONS:")
            print()
            
            if "URL-Embedded Authentication" in self.successful_methods:
                print("1. ✅ Use URL-embedded authentication:")
                print(f"   - Your current URL already works: {self.function_url}")
                print("   - No additional headers needed")
                print("   - Just use the URL as-is in your bot")
                print()
            
            if "No Authentication (Anonymous/Managed Identity)" in self.successful_methods:
                print("2. ✅ Use Managed Identity (RECOMMENDED):")
                print("   - Your Function App allows anonymous access")
                print("   - Bot can use its Contributor role to access the function")
                print("   - Most secure option - no keys to manage")
                print(f"   - Use base URL: {urlparse(self.function_url).scheme}://{urlparse(self.function_url).netloc}{urlparse(self.function_url).path}")
                print()
            
            if "Function Key in Header (x-functions-key)" in self.successful_methods:
                print("3. ✅ Use Function Key in Header:")
                print("   - Set header: x-functions-key: your_function_key")
                print("   - This is the traditional method")
                print("   - Make sure AZURE_FUNCTION_KEY environment variable is set")
                print()
            
            if "Function Key in URL Parameter (?code=)" in self.successful_methods:
                print("4. ✅ Use Function Key in URL:")
                print(f"   - URL: {urlparse(self.function_url).scheme}://{urlparse(self.function_url).netloc}{urlparse(self.function_url).path}?code=your_key")
                print("   - Simple but key is visible in URLs")
                print()
            
            print("🔧 FOR YOUR BOT:")
            print("Update your environment variables:")
            
            if "URL-Embedded Authentication" in self.successful_methods:
                print(f"AZURE_FUNCTION_URL={self.function_url}")
                print("# No AZURE_FUNCTION_KEY needed")
            elif "No Authentication (Anonymous/Managed Identity)" in self.successful_methods:
                base_url = f"{urlparse(self.function_url).scheme}://{urlparse(self.function_url).netloc}{urlparse(self.function_url).path}"
                print(f"AZURE_FUNCTION_URL={base_url}")
                print("# No AZURE_FUNCTION_KEY needed")
            elif "Function Key in Header (x-functions-key)" in self.successful_methods:
                base_url = f"{urlparse(self.function_url).scheme}://{urlparse(self.function_url).netloc}{urlparse(self.function_url).path}"
                print(f"AZURE_FUNCTION_URL={base_url}")
                print(f"AZURE_FUNCTION_KEY={self.function_key}")
            
        else:
            print_error("🚨 NO WORKING METHODS - TROUBLESHOOTING NEEDED:")
            print()
            
            print("Possible issues:")
            print("1. Function URL is incorrect")
            print("2. Function Key is incorrect or expired")
            print("3. Function App is not running")
            print("4. Function requires different authentication")
            print("5. Network connectivity issues")
            print("6. Function App has strict CORS policies")
            print()
            
            print("Next steps:")
            print("1. Verify Function URL in Azure Portal:")
            print("   - Go to Function App → Functions → QuerySQL")
            print("   - Click 'Get Function URL'")
            print("   - Copy the complete URL")
            print()
            
            print("2. Test Function directly in browser:")
            print("   - Open the Function URL in your browser")
            print("   - You should see a response (even if it's an error)")
            print()
            
            print("3. Check Function App logs:")
            print("   - Go to Function App → Monitor → Log stream")
            print("   - Look for errors when testing")
            print()
            
            print("4. Check Function App authentication settings:")
            print("   - Go to Function App → Authentication")
            print("   - Ensure it allows the authentication method you're using")
            print()
            
            print("5. Regenerate Function Key:")
            print("   - Go to Function App → Functions → QuerySQL → Function Keys")
            print("   - Delete and recreate the default key")
    
    def save_report(self):
        """Save detailed test report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "function_url": self.function_url,
            "has_function_key": bool(self.function_key),
            "successful_methods": self.successful_methods,
            "all_results": self.test_results,
            "url_analysis": {
                "parsed_url": str(urlparse(self.function_url)),
                "has_embedded_code": 'code=' in self.function_url.lower()
            }
        }
        
        filename = f"azure_function_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print_success(f"Detailed report saved to: {filename}")
        except Exception as e:
            print_error(f"Could not save report: {e}")

async def main():
    """Main function"""
    tester = AzureFunctionTester()
    
    try:
        # Get user input
        tester.get_user_input()
        
        if not tester.function_url:
            print_error("Function URL is required!")
            return
        
        # Analyze URL and key
        if not tester.analyze_url():
            print_error("Invalid URL format!")
            return
        
        tester.analyze_function_key()
        
        # Run all tests
        await tester.test_all_methods()
        
        # Generate summary and recommendations
        tester.generate_summary()
        tester.generate_recommendations()
        
        # Save report
        tester.save_report()
        
        print_header("Testing Complete!", Colors.GREEN)
        
        if tester.successful_methods:
            print_success(f"🎉 Found {len(tester.successful_methods)} working authentication method(s)!")
            print("Use the recommendations above to configure your bot.")
        else:
            print_error("😞 No working authentication methods found.")
            print("Follow the troubleshooting steps above.")
        
    except KeyboardInterrupt:
        print_error("\nTest interrupted by user")
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Azure Function Authentication Tester")
    print("=====================================")
    
    # Check Python version
    if sys.version_info < (3, 7):
        print_error("Python 3.7 or higher is required")
        sys.exit(1)
    
    # Check if aiohttp is installed
    try:
        import aiohttp
        print_info("✅ aiohttp is available")
    except ImportError:
        print_error("❌ aiohttp is not installed.")
        print("Install it with one of these commands:")
        print("  pip install aiohttp")
        print("  pip3 install aiohttp")
        print("  python -m pip install aiohttp")
        print("  python3 -m pip install aiohttp")
        sys.exit(1)
    
    print_info(f"✅ Python {sys.version.split()[0]} detected")
    print_info("✅ Starting authentication tests...")
    print()
    
    # Run the main function
    try:
        asyncio.run(main())
    except Exception as e:
        print_error(f"Failed to run tests: {e}")
        import traceback
        traceback.print_exc()