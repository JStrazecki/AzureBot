# troubleshoot_powerbi.py - Troubleshooting script for Power BI integration
"""
Troubleshooting script to diagnose Power BI Analyst 404 issues
Run this locally or in Azure to check configuration
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment_variables():
    """Check if Power BI environment variables are set"""
    print("\n=== CHECKING ENVIRONMENT VARIABLES ===")
    
    required_vars = {
        "POWERBI_TENANT_ID": "Azure AD Tenant ID",
        "POWERBI_CLIENT_ID": "App Registration Client ID",
        "POWERBI_CLIENT_SECRET": "App Registration Client Secret"
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.environ.get(var, "")
        if value:
            # Mask sensitive values
            if "SECRET" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                print(f"✓ {var}: {masked} ({description})")
            else:
                print(f"✓ {var}: {value[:20]}... ({description})")
        else:
            print(f"✗ {var}: NOT SET ({description})")
            all_set = False
    
    return all_set

def check_imports():
    """Check if all required modules can be imported"""
    print("\n=== CHECKING IMPORTS ===")
    
    modules_to_check = [
        ("aiohttp", "Web framework"),
        ("msal", "Microsoft Authentication Library"),
        ("jwt", "JWT token handling"),
        ("powerbi_client", "Power BI client module"),
        ("analyst_routes", "Analyst routes module"),
        ("analyst_translator", "DAX translator module"),
        ("analysis_agent", "Analysis agent module"),
        ("analyst_ui", "Analyst UI module")
    ]
    
    all_imported = True
    for module_name, description in modules_to_check:
        try:
            if module_name in ["powerbi_client", "analyst_routes", "analyst_translator", "analysis_agent", "analyst_ui"]:
                # These are local modules
                exec(f"import {module_name}")
            else:
                # Standard library modules
                __import__(module_name)
            print(f"✓ {module_name}: Imported successfully ({description})")
        except ImportError as e:
            print(f"✗ {module_name}: Import failed - {e} ({description})")
            all_imported = False
        except Exception as e:
            print(f"✗ {module_name}: Error - {e} ({description})")
            all_imported = False
    
    return all_imported

async def test_powerbi_client():
    """Test Power BI client initialization and basic functionality"""
    print("\n=== TESTING POWER BI CLIENT ===")
    
    try:
        from powerbi_client import powerbi_client
        
        # Check if client is configured
        print(f"Client configured: {powerbi_client.is_configured()}")
        
        if powerbi_client.is_configured():
            # Try to get access token
            print("Attempting to get access token...")
            token = await powerbi_client.get_access_token()
            
            if token:
                print("✓ Successfully acquired access token")
                print(f"  Token length: {len(token)} characters")
                
                # Try to get workspaces
                print("\nAttempting to fetch workspaces...")
                workspaces = await powerbi_client.get_user_workspaces(token)
                
                if workspaces:
                    print(f"✓ Found {len(workspaces)} accessible workspaces:")
                    for ws in workspaces[:5]:  # Show first 5
                        print(f"  - {ws.name} (ID: {ws.id[:8]}...)")
                    if len(workspaces) > 5:
                        print(f"  ... and {len(workspaces) - 5} more")
                else:
                    print("✗ No workspaces found or accessible")
                    print("  Make sure the app registration has been granted access to workspaces")
            else:
                print("✗ Failed to acquire access token")
                print("  Check credentials and app registration")
        else:
            print("✗ Power BI client is not configured")
            
        # Run validation
        print("\nRunning full validation...")
        validation = await powerbi_client.validate_configuration()
        
        print("\nValidation Results:")
        print(f"  Configured: {validation['configured']}")
        print(f"  Credentials Present: {validation['credentials_present']}")
        print(f"  Token Acquired: {validation['token_acquired']}")
        print(f"  API Accessible: {validation['api_accessible']}")
        print(f"  Workspaces Accessible: {validation['workspaces_accessible']}")
        
        if validation['errors']:
            print("\n  Errors:")
            for error in validation['errors']:
                print(f"    - {error}")
        
        if validation['warnings']:
            print("\n  Warnings:")
            for warning in validation['warnings']:
                print(f"    - {warning}")
                
    except Exception as e:
        print(f"✗ Error testing Power BI client: {e}")
        import traceback
        traceback.print_exc()

def check_app_routes():
    """Check if routes can be registered"""
    print("\n=== CHECKING ROUTE REGISTRATION ===")
    
    try:
        from aiohttp import web
        from analyst_routes import add_analyst_routes
        
        # Create a test app
        test_app = web.Application()
        
        # Try to add routes
        print("Attempting to add analyst routes...")
        add_analyst_routes(test_app)
        
        # Check registered routes
        analyst_routes = [r for r in test_app.router.routes() if '/analyst' in str(r)]
        
        if analyst_routes:
            print(f"✓ Successfully registered {len(analyst_routes)} analyst routes:")
            for route in analyst_routes[:10]:  # Show first 10
                if hasattr(route, 'resource'):
                    print(f"  - {route.resource}")
        else:
            print("✗ No analyst routes were registered")
            
    except Exception as e:
        print(f"✗ Error checking routes: {e}")
        import traceback
        traceback.print_exc()

def check_azure_environment():
    """Check Azure-specific environment"""
    print("\n=== CHECKING AZURE ENVIRONMENT ===")
    
    # Check if running in Azure
    if os.environ.get("WEBSITE_INSTANCE_ID"):
        print("✓ Running in Azure App Service")
        print(f"  Instance ID: {os.environ.get('WEBSITE_INSTANCE_ID')}")
        print(f"  Site Name: {os.environ.get('WEBSITE_SITE_NAME')}")
        print(f"  Region: {os.environ.get('REGION_NAME', 'Unknown')}")
    else:
        print("ℹ Running locally (not in Azure)")
    
    # Check Python version
    print(f"\nPython Version: {sys.version}")
    
    # Check if in production
    deployment_env = os.environ.get("DEPLOYMENT_ENV", "unknown")
    print(f"Deployment Environment: {deployment_env}")

def print_troubleshooting_steps():
    """Print troubleshooting steps"""
    print("\n=== TROUBLESHOOTING STEPS ===")
    print("""
1. **Check Environment Variables in Azure:**
   - Go to Azure Portal > Your App Service > Configuration
   - Under "Application settings", ensure these are set:
     * POWERBI_TENANT_ID
     * POWERBI_CLIENT_ID
     * POWERBI_CLIENT_SECRET
   
2. **Verify App Registration:**
   - Go to Azure Portal > Azure Active Directory > App registrations
   - Find your app registration
   - Check API permissions include:
     * Power BI Service > Workspace.Read.All
     * Power BI Service > Dataset.Read.All
   - Ensure permissions are granted (admin consent)
   
3. **Check Client Secret:**
   - In your app registration > Certificates & secrets
   - Verify the client secret hasn't expired
   - If expired, create a new one and update POWERBI_CLIENT_SECRET
   
4. **Grant Workspace Access:**
   - In Power BI Service (app.powerbi.com)
   - Go to each workspace you want to access
   - Click "Access" > "Add" > Add your app as a member/viewer
   
5. **Check Logs:**
   - In Azure Portal > Your App Service > Log stream
   - Look for Power BI related errors during startup
   
6. **Restart App Service:**
   - After making any configuration changes
   - Go to Azure Portal > Your App Service > Overview > Restart
   
7. **Test Individual Components:**
   - Visit /health to see detailed status
   - Visit /info for configuration details
   - Check browser console for JavaScript errors
    """)

async def main():
    """Main troubleshooting function"""
    print("=" * 60)
    print("POWER BI ANALYST TROUBLESHOOTING SCRIPT")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)
    
    # Run checks
    env_ok = check_environment_variables()
    imports_ok = check_imports()
    check_azure_environment()
    
    if env_ok and imports_ok:
        await test_powerbi_client()
        check_app_routes()
    else:
        print("\n✗ Cannot proceed with further tests due to missing requirements")
    
    print_troubleshooting_steps()
    
    print("\n" + "=" * 60)
    print("TROUBLESHOOTING COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())