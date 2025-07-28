# kudu_test.py - Quick test script for Azure Kudu console
"""
Run this in Azure Kudu console to test Power BI configuration
Access Kudu: https://sqlbottest.scm.azurewebsites.net
Go to Debug Console > CMD or PowerShell
Navigate to: D:\home\site\wwwroot
Run: python kudu_test.py
"""

import os
import sys

print("=== POWER BI CONFIGURATION TEST ===")
print(f"Python Version: {sys.version}")
print(f"Current Directory: {os.getcwd()}")

# Check environment variables
print("\n1. Checking Environment Variables:")
env_vars = {
    "POWERBI_TENANT_ID": os.environ.get("POWERBI_TENANT_ID", "NOT SET"),
    "POWERBI_CLIENT_ID": os.environ.get("POWERBI_CLIENT_ID", "NOT SET"),
    "POWERBI_CLIENT_SECRET": os.environ.get("POWERBI_CLIENT_SECRET", "NOT SET"),
}

all_set = True
for var, value in env_vars.items():
    if value == "NOT SET":
        print(f"  ✗ {var}: NOT SET")
        all_set = False
    else:
        if "SECRET" in var:
            print(f"  ✓ {var}: ****** (hidden)")
        else:
            print(f"  ✓ {var}: {value[:20]}...")

# Check if files exist
print("\n2. Checking Required Files:")
files_to_check = [
    "powerbi_client.py",
    "analyst_routes.py",
    "analyst_translator.py",
    "analysis_agent.py",
    "analyst_ui.py"
]

for file in files_to_check:
    if os.path.exists(file):
        print(f"  ✓ {file} exists")
    else:
        print(f"  ✗ {file} NOT FOUND")

# Try to import modules
print("\n3. Testing Imports:")
try:
    import msal
    print("  ✓ msal imported successfully")
except ImportError:
    print("  ✗ msal import failed - run: pip install msal")

try:
    from powerbi_client import powerbi_client
    print("  ✓ powerbi_client imported successfully")
    print(f"     Client configured: {powerbi_client.is_configured()}")
except Exception as e:
    print(f"  ✗ powerbi_client import failed: {e}")

try:
    from analyst_routes import add_analyst_routes
    print("  ✓ analyst_routes imported successfully")
except Exception as e:
    print(f"  ✗ analyst_routes import failed: {e}")

# Quick configuration check
print("\n4. Configuration Summary:")
if all_set:
    print("  ✓ All Power BI environment variables are set")
    print("  → The /analyst endpoint should be available")
    print("  → If still getting 404, restart the app service")
else:
    print("  ✗ Missing Power BI configuration")
    print("  → Set the missing environment variables in Azure Portal")
    print("  → App Service > Configuration > Application settings")

print("\n5. Next Steps:")
if all_set:
    print("  1. Restart the app service if you haven't already")
    print("  2. Visit https://sqlbottest.azurewebsites.net/health")
    print("  3. Check if powerbi_analyst shows as 'available'")
    print("  4. Try https://sqlbottest.azurewebsites.net/analyst")
else:
    print("  1. Set the missing environment variables")
    print("  2. Save configuration and restart app service")
    print("  3. Run this test again to verify")

print("\n=== TEST COMPLETE ===")

# If running interactively, try a simple test
if all_set:
    print("\nBonus: Checking Power BI client initialization...")
    try:
        from powerbi_client import PowerBIClient
        client = PowerBIClient()
        print(f"  Client initialized: {client.configured}")
        if client.configured:
            print("  ✓ Power BI client is ready")
        else:
            print("  ✗ Client initialization failed")
    except Exception as e:
        print(f"  ✗ Error: {e}")