#!/usr/bin/env python3
# debug_startup.py - Debug script to verify environment before starting main app

import os
import sys
import importlib.util

print("=== SQL Assistant Environment Check ===\n")

# Check Python version
print(f"Python Version: {sys.version}")
print(f"Python Executable: {sys.executable}\n")

# Check required environment variables
env_vars = {
    "MICROSOFT_APP_ID": "Bot Framework App ID",
    "MICROSOFT_APP_PASSWORD": "Bot Framework Password",
    "AZURE_OPENAI_ENDPOINT": "Azure OpenAI Endpoint",
    "AZURE_OPENAI_API_KEY": "Azure OpenAI Key",
    "AZURE_FUNCTION_URL": "SQL Function URL",
    "AZURE_FUNCTION_KEY": "SQL Function Key"
}

print("Environment Variables:")
missing_vars = []
for var, description in env_vars.items():
    value = os.environ.get(var)
    if value:
        if "KEY" in var or "PASSWORD" in var:
            masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
            print(f"✅ {var}: {masked} ({description})")
        else:
            print(f"✅ {var}: {value[:30]}... ({description})")
    else:
        print(f"❌ {var}: NOT SET ({description})")
        missing_vars.append(var)

print("\nOptional Variables:")
optional_vars = {
    "MCP_SERVER_URL": "MCP Server URL",
    "MAX_DAILY_TOKENS": "Daily token limit",
    "DEPLOYMENT_ENV": "Deployment environment"
}

for var, description in optional_vars.items():
    value = os.environ.get(var)
    if value:
        print(f"✅ {var}: {value} ({description})")
    else:
        print(f"ℹ️ {var}: Not set ({description})")

# Check required Python packages
print("\nRequired Packages:")
packages = [
    ("aiohttp", "Web framework"),
    ("botbuilder.core", "Bot Framework SDK"),
    ("openai", "Azure OpenAI client"),
    ("tiktoken", "Token counting"),
    ("gunicorn", "WSGI server"),
    ("dotenv", "Environment loading")
]

missing_packages = []
for package, description in packages:
    try:
        if "." in package:
            # Handle submodules
            parts = package.split(".")
            module = __import__(parts[0])
            for part in parts[1:]:
                module = getattr(module, part)
        else:
            __import__(package)
        print(f"✅ {package}: Installed ({description})")
    except ImportError:
        print(f"❌ {package}: NOT INSTALLED ({description})")
        missing_packages.append(package)

# Check required files
print("\nRequired Files:")
files = [
    "app.py",
    "teams_sql_bot.py",
    "azure_openai_sql_translator.py",
    "autonomous_sql_explorer.py",
    "query_validator.py",
    "token_limiter.py",
    "requirements.txt"
]

missing_files = []
for file in files:
    if os.path.exists(file):
        print(f"✅ {file}: Found")
    else:
        print(f"❌ {file}: NOT FOUND")
        missing_files.append(file)

# Try to import main app
print("\nApp Import Test:")
try:
    spec = importlib.util.spec_from_file_location("app", "app.py")
    if spec and spec.loader:
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        if hasattr(app_module, 'APP'):
            print("✅ Main app (app.py) imports successfully")
            print("✅ APP object found")
        else:
            print("❌ APP object not found in app.py")
    else:
        print("❌ Could not load app.py")
except Exception as e:
    print(f"❌ Error importing app.py: {e}")

# Summary
print("\n=== SUMMARY ===")
if missing_vars:
    print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
    print("   Add these to Azure App Service Configuration")
else:
    print("✅ All required environment variables are set")

if missing_packages:
    print(f"❌ Missing packages: {', '.join(missing_packages)}")
    print("   Run: pip install -r requirements.txt")
else:
    print("✅ All required packages are installed")

if missing_files:
    print(f"❌ Missing files: {', '.join(missing_files)}")
    print("   Make sure all files are deployed")
else:
    print("✅ All required files are present")

# Azure Function Key special check
if not os.environ.get("AZURE_FUNCTION_KEY") and os.environ.get("AZURE_FUNCTION_URL"):
    print("\n⚠️  WARNING: Azure Function URL is set but no key provided")
    print("   This will cause 401 errors when querying the database")
    print("   Get the key from Azure Portal → Function App → HttpQuerySQL → Function Keys")

# Final verdict
print("\n=== READY TO START? ===")
if not missing_vars and not missing_packages and not missing_files:
    print("✅ YES - Environment is ready for main SQL Assistant bot!")
    print("   Update startup.sh to run 'app:APP' instead of 'test_bot:APP'")
else:
    print("❌ NO - Fix the issues above first")

print("\nTo run this check in Azure:")
print("1. Add this file to your repository")
print("2. In Kudu console or SSH: python debug_startup.py")