#!/usr/bin/env python3
# debug_bot.py - Comprehensive debugging script for Azure deployment

import os
import sys
import json
import importlib
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text.center(60)}")
    print(f"{'='*60}")

def check_python_environment():
    print_header("PYTHON ENVIRONMENT")
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print(f"Current Directory: {os.getcwd()}")
    print(f"Python Path: {sys.path[:3]}...")  # First 3 entries
    
    # Check if we're in the right directory
    expected_files = ['app.py', 'teams_sql_bot.py', 'azure_openai_sql_translator.py']
    missing_files = []
    
    print(f"\nChecking for required files:")
    for file in expected_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - MISSING")
            missing_files.append(file)
    
    return len(missing_files) == 0

def check_environment_variables():
    print_header("ENVIRONMENT VARIABLES")
    
    required_vars = [
        "MICROSOFT_APP_ID",
        "MICROSOFT_APP_PASSWORD", 
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_FUNCTION_URL"
    ]
    
    optional_vars = [
        "AZURE_FUNCTION_KEY",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "PORT",
        "DEPLOYMENT_ENV"
    ]
    
    missing_required = []
    
    print("Required Variables:")
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            if "KEY" in var or "PASSWORD" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                print(f"✓ {var}: {masked}")
            else:
                print(f"✓ {var}: {value[:30]}...")
        else:
            print(f"✗ {var}: NOT SET")
            missing_required.append(var)
    
    print(f"\nOptional Variables:")
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            if "KEY" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                print(f"ℹ {var}: {masked}")
            else:
                print(f"ℹ {var}: {value}")
        else:
            print(f"- {var}: Not set")
    
    return len(missing_required) == 0, missing_required

def check_package_imports():
    print_header("PACKAGE IMPORTS")
    
    packages = [
        ("aiohttp", "Web framework"),
        ("botbuilder.core", "Bot Framework SDK"),
        ("openai", "Azure OpenAI client"),
        ("tiktoken", "Token counting"),
        ("gunicorn", "WSGI server"),
        ("azure.identity", "Azure authentication")
    ]
    
    import_errors = []
    
    for package, description in packages:
        try:
            if "." in package:
                parts = package.split(".")
                module = __import__(parts[0])
                for part in parts[1:]:
                    module = getattr(module, part)
            else:
                __import__(package)
            print(f"✓ {package}: OK ({description})")
        except ImportError as e:
            print(f"✗ {package}: FAILED - {str(e)} ({description})")
            import_errors.append(package)
    
    return len(import_errors) == 0, import_errors

def check_custom_modules():
    print_header("CUSTOM MODULE IMPORTS")
    
    modules = [
        "azure_openai_sql_translator",
        "teams_sql_bot", 
        "query_validator",
        "token_limiter"
    ]
    
    import_errors = []
    
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            print(f"✓ {module_name}: OK")
            
            # Check for main classes
            if module_name == "azure_openai_sql_translator":
                if hasattr(module, 'AzureOpenAISQLTranslator'):
                    print(f"  ✓ AzureOpenAISQLTranslator class found")
                else:
                    print(f"  ✗ AzureOpenAISQLTranslator class missing")
                    
            elif module_name == "teams_sql_bot":
                if hasattr(module, 'SQLAssistantBot'):
                    print(f"  ✓ SQLAssistantBot class found")
                else:
                    print(f"  ✗ SQLAssistantBot class missing")
                    
        except ImportError as e:
            print(f"✗ {module_name}: FAILED - {str(e)}")
            import_errors.append(module_name)
    
    return len(import_errors) == 0, import_errors

def test_main_app():
    print_header("MAIN APP TEST")
    
    try:
        # Try to import the main app
        import app
        print("✓ app.py imported successfully")
        
        if hasattr(app, 'APP'):
            print("✓ APP object found")
            
            # Check if APP has router
            if hasattr(app.APP, 'router'):
                print("✓ Router configured")
                
                # List routes
                routes = []
                for route in app.APP.router.routes():
                    route_info = f"{route.method} {route.resource.canonical}"
                    routes.append(route_info)
                
                print(f"✓ Routes configured: {len(routes)}")
                for route in routes:
                    print(f"  - {route}")
            else:
                print("✗ Router not found")
                return False
                
            return True
        else:
            print("✗ APP object not found")
            return False
            
    except Exception as e:
        print(f"✗ Failed to import app.py: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def generate_recommendations(results):
    print_header("RECOMMENDATIONS")
    
    env_ok, missing_vars = results.get('env', (True, []))
    packages_ok, missing_packages = results.get('packages', (True, []))
    modules_ok, missing_modules = results.get('modules', (True, []))
    app_ok = results.get('app', True)
    
    if not env_ok:
        print("\n1. FIX ENVIRONMENT VARIABLES:")
        print("   In Azure Portal:")
        print("   - Go to your App Service (sqlbot)")
        print("   - Navigate to Settings > Configuration")
        print("   - Click 'New application setting'")
        print("   - Add each missing variable:")
        for var in missing_vars:
            print(f"     * {var}")
        print("   - Click 'Save' and restart the app")
    
    if not packages_ok:
        print(f"\n2. FIX MISSING PACKAGES:")
        print("   Missing packages:", missing_packages)
        print("   - Check requirements.txt has all packages")
        print("   - Redeploy through GitHub Actions")
    
    if not modules_ok:
        print(f"\n3. FIX CUSTOM MODULES:")
        print("   Missing modules:", missing_modules)
        print("   - Ensure all .py files are in the repository root")
        print("   - Check for any 'good.' prefixes in imports")
        print("   - Verify no syntax errors in the modules")
    
    if not app_ok:
        print(f"\n4. FIX MAIN APPLICATION:")
        print("   - Check app.py for syntax errors")
        print("   - Verify all imports work")
        print("   - Test locally first")
    
    print(f"\n5. AZURE APP SERVICE SETTINGS:")
    print("   - Set startup command: see startup.txt")
    print("   - Enable Application Insights for better logging")
    print("   - Check 'Log stream' in Azure Portal for real-time logs")

def main():
    print_header(f"SQL ASSISTANT BOT DEBUG - {datetime.now()}")
    
    results = {}
    
    # Run all checks
    results['python'] = check_python_environment()
    results['env'] = check_environment_variables()
    results['packages'] = check_package_imports()
    results['modules'] = check_custom_modules()
    results['app'] = test_main_app()
    
    # Summary
    print_header("SUMMARY")
    
    checks = [
        ("Python Environment", results['python']),
        ("Environment Variables", results['env'][0] if isinstance(results['env'], tuple) else results['env']),
        ("Package Imports", results['packages'][0] if isinstance(results['packages'], tuple) else results['packages']),
        ("Custom Modules", results['modules'][0] if isinstance(results['modules'], tuple) else results['modules']),
        ("Main Application", results['app'])
    ]
    
    passed = sum(1 for _, status in checks if status)
    total = len(checks)
    
    for name, status in checks:
        status_text = "✓ PASS" if status else "✗ FAIL"
        print(f"{name}: {status_text}")
    
    print(f"\nOVERALL: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 ALL CHECKS PASSED! Your bot should be ready to run.")
        print("\nNext steps:")
        print("1. Make sure startup.txt is correctly configured")
        print("2. Check Azure App Service logs for any runtime errors")
        print("3. Test the /health endpoint")
    else:
        print(f"\n❌ {total - passed} checks failed. See recommendations below.")
        generate_recommendations(results)
    
    # Quick connection tests
    if results['env'][0]:  # If env vars are set
        print_header("QUICK CONNECTION TESTS")
        
        # Test Azure Function
        function_url = os.environ.get("AZURE_FUNCTION_URL")
        if function_url:
            print(f"\nAzure Function URL: {function_url}")
            print("Test in browser (replace YOUR_KEY):")
            print(f"{function_url}?code=YOUR_KEY&query_type=metadata")
        
        # Test Azure OpenAI
        openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if openai_endpoint:
            print(f"\nAzure OpenAI Endpoint: {openai_endpoint}")
            print("This should be accessible if credentials are correct")

if __name__ == "__main__":
    main()