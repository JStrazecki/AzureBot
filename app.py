#!/usr/bin/env python3
# app.py - Main SQL Assistant Application with Enhanced Error Handling and Power BI Analyst
"""
SQL Assistant Application - Fixed Power BI Analyst Integration v3
Better error handling and module loading diagnostics
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import traceback

# Web framework
from aiohttp import web
from aiohttp.web import Request, Response, json_response, middleware
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose logs
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('tiktoken').setLevel(logging.WARNING)
logging.getLogger('msal').setLevel(logging.WARNING)

# Environment Configuration
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "production")

# Track what's actually loaded
LOADED_FEATURES = {
    "sql_translator": False,
    "admin_dashboard": False,
    "sql_console": False,
    "powerbi_analyst": False
}

# Track import errors
IMPORT_ERRORS = {}

# Check environment variables
def check_environment():
    """Check and log environment variable status"""
    required_vars = {
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI Endpoint",
        "AZURE_OPENAI_API_KEY": "Azure OpenAI API Key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "OpenAI Deployment Name",
        "AZURE_FUNCTION_URL": "Azure Function URL"
    }
    
    # Power BI variables (optional but needed for analyst)
    powerbi_vars = {
        "POWERBI_TENANT_ID": "Power BI Tenant ID",
        "POWERBI_CLIENT_ID": "Power BI Client ID",
        "POWERBI_CLIENT_SECRET": "Power BI Client Secret"
    }
    
    logger.info("=== Environment Check ===")
    missing_vars = []
    missing_powerbi = []
    powerbi_status = {}
    
    # Check required vars
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            if "KEY" in var or "PASSWORD" in var or "SECRET" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                logger.info(f"✓ {var}: {masked}")
            else:
                logger.info(f"✓ {var}: {value[:30]}...")
        else:
            logger.error(f"❌ {var}: NOT SET ({description})")
            missing_vars.append(var)
    
    # Check Power BI vars
    logger.info("\n=== Power BI Configuration ===")
    for var, description in powerbi_vars.items():
        value = os.environ.get(var)
        if value:
            powerbi_status[var] = True
            if "SECRET" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                logger.info(f"✓ {var}: {masked}")
            else:
                logger.info(f"✓ {var}: {value[:30]}...")
        else:
            powerbi_status[var] = False
            logger.info(f"ℹ️ {var}: NOT SET ({description})")
            missing_powerbi.append(var)
    
    # Check if URL has embedded authentication
    function_url = os.environ.get("AZURE_FUNCTION_URL", "")
    if function_url and "code=" in function_url:
        logger.info("✅ Azure Function authentication: URL-embedded (recommended)")
    
    # Power BI status
    all_powerbi_configured = all(powerbi_status.values())
    if all_powerbi_configured:
        logger.info("✅ Power BI Analyst: Fully configured")
    elif any(powerbi_status.values()):
        logger.info("⚠️ Power BI Analyst: Partially configured")
    else:
        logger.info("ℹ️ Power BI Analyst: Not configured (optional feature)")
    
    return missing_vars, powerbi_status

# Run environment check
missing_vars, powerbi_status = check_environment()

# Error handling middleware
@middleware
async def aiohttp_error_middleware(request: Request, handler):
    """Global error handler for aiohttp"""
    try:
        response = await handler(request)
        return response
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return json_response({
            "error": "Internal server error",
            "message": str(e),
            "type": type(e).__name__
        }, status=500)

# Initialize SQL translator if available
SQL_TRANSLATOR = None
if not missing_vars or all(var not in missing_vars for var in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY"]):
    try:
        # Import the unified SQL translator
        from sql_translator import SQLTranslator
        SQL_TRANSLATOR = SQLTranslator()
        logger.info("✓ Unified SQL Translator initialized with error analysis")
        LOADED_FEATURES["sql_translator"] = True
    except Exception as e:
        logger.error(f"❌ Failed to initialize SQL Translator: {e}")
        IMPORT_ERRORS["sql_translator"] = str(e)

# Health check endpoint
async def health(req: Request) -> Response:
    """Health check endpoint"""
    try:
        # Check actual Power BI configuration status
        powerbi_configured = all([
            os.environ.get("POWERBI_TENANT_ID"),
            os.environ.get("POWERBI_CLIENT_ID"),
            os.environ.get("POWERBI_CLIENT_SECRET")
        ])
        
        # Check if analyst routes are actually registered
        analyst_routes = []
        for route in req.app.router.routes():
            route_info = str(route)
            if '/analyst' in route_info:
                analyst_routes.append(route_info)
        
        analyst_routes_registered = len(analyst_routes) > 0
        
        health_status = {
            "status": "healthy",
            "version": "2.2.3",  # Updated version
            "timestamp": datetime.now().isoformat(),
            "environment": DEPLOYMENT_ENV,
            "services": {
                "console": "available" if LOADED_FEATURES["sql_console"] else "not loaded",
                "admin_dashboard": "available" if LOADED_FEATURES["admin_dashboard"] else "not loaded",
                "sql_translator": "available" if LOADED_FEATURES["sql_translator"] else "not available",
                "sql_function": "configured" if os.environ.get("AZURE_FUNCTION_URL") else "not configured",
                "powerbi_analyst": "available" if LOADED_FEATURES["powerbi_analyst"] else "not loaded"
            },
            "features": {
                "error_analysis": SQL_TRANSLATOR is not None,
                "query_fixing": SQL_TRANSLATOR is not None,
                "multi_database": True,
                "standardization_checks": True,
                "powerbi_integration": powerbi_configured,
                "business_intelligence": powerbi_configured and LOADED_FEATURES["powerbi_analyst"]
            },
            "powerbi_config": {
                "tenant_id_set": bool(os.environ.get("POWERBI_TENANT_ID")),
                "client_id_set": bool(os.environ.get("POWERBI_CLIENT_ID")),
                "client_secret_set": bool(os.environ.get("POWERBI_CLIENT_SECRET")),
                "all_configured": powerbi_configured,
                "routes_registered": analyst_routes_registered,
                "route_count": len(analyst_routes),
                "actual_loaded": LOADED_FEATURES["powerbi_analyst"]
            },
            "loaded_features": LOADED_FEATURES,
            "registered_routes": {
                "total": len(list(req.app.router.routes())),
                "analyst_routes": analyst_routes[:5] if analyst_routes else []  # Show first 5
            },
            "missing_vars": missing_vars,
            "import_errors": IMPORT_ERRORS,
            "python_version": sys.version
        }
        
        # Add token usage if available
        if SQL_TRANSLATOR:
            health_status["token_usage"] = SQL_TRANSLATOR.get_usage_summary()
        
        return json_response(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json_response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=503)

# Root endpoint
async def index(req: Request) -> Response:
    """Root endpoint with navigation"""
    
    # Check if analyst routes are registered
    analyst_routes_registered = LOADED_FEATURES["powerbi_analyst"]
    
    # Check Power BI configuration
    powerbi_configured = all([
        os.environ.get("POWERBI_TENANT_ID"),
        os.environ.get("POWERBI_CLIENT_ID"),
        os.environ.get("POWERBI_CLIENT_SECRET")
    ])
    
    analyst_section = ""
    if analyst_routes_registered:
        analyst_section = '''
                <a href="/analyst">Power BI Analyst</a>
                <span class="new-badge">NEW</span>'''
    elif powerbi_configured:
        analyst_section = '''
                <a href="/analyst" style="opacity: 0.7;">Power BI Analyst</a>
                <span style="font-size: 12px; color: #666;">(Failed to load)</span>'''
    else:
        analyst_section = '''
                <a href="/analyst" style="opacity: 0.5; cursor: not-allowed;">Power BI Analyst</a>
                <span style="font-size: 12px; color: #666;">(Not configured)</span>'''
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SQL Assistant - Enhanced with Power BI</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 600px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            .version {{
                color: #666;
                font-size: 14px;
                margin-bottom: 30px;
            }}
            .features {{
                text-align: left;
                background: #f7f7f7;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }}
            .features h3 {{
                color: #667eea;
                margin-top: 0;
            }}
            .features ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            .features li {{
                margin: 5px 0;
            }}
            .links {{
                display: flex;
                flex-direction: column;
                gap: 15px;
            }}
            a {{
                display: block;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                transition: transform 0.2s;
                position: relative;
            }}
            a:hover {{
                transform: translateY(-2px);
            }}
            .status {{
                margin-top: 20px;
                padding: 10px;
                background: #f0f0f0;
                border-radius: 8px;
                font-size: 14px;
            }}
            .new-badge {{
                background: #10b981;
                color: white;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-left: 5px;
                position: absolute;
                right: 20px;
                top: 50%;
                transform: translateY(-50%);
            }}
            .section {{
                margin: 20px 0;
                text-align: left;
            }}
            .section h4 {{
                color: #667eea;
                margin-bottom: 10px;
            }}
            .debug-info {{
                margin-top: 20px;
                padding: 10px;
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                font-size: 12px;
                text-align: left;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 SQL Assistant</h1>
            <div class="version">Version 2.2.3 - Enhanced with Power BI Integration</div>
            
            <div class="features">
                <h3>✨ What's New</h3>
                <ul>
                    <li>📊 <strong>Power BI Analyst</strong> <span class="new-badge" style="position: relative;">NEW</span><br>
                        Natural language business intelligence from your Power BI datasets</li>
                    <li>🔧 <strong>Intelligent Error Analysis</strong><br>
                        When queries fail, get detailed analysis and fix suggestions</li>
                    <li>🤖 <strong>Automatic Query Fixing</strong><br>
                        One-click application of suggested fixes</li>
                    <li>🔍 <strong>Discovery Queries</strong><br>
                        Find correct table and column names easily</li>
                    <li>📊 <strong>Database Standardization</strong><br>
                        Check schema compliance across systems</li>
                    <li>🗄️ <strong>Multi-Database Support</strong><br>
                        Compare and analyze across multiple databases</li>
                </ul>
            </div>
            
            <div class="section">
                <h4>🚀 Available Tools</h4>
            </div>
            
            <div class="links">
                <a href="/console">SQL Console</a>
                <a href="/admin">Admin Dashboard</a>
                {analyst_section}
                <a href="/health">Health Status</a>
            </div>
            
            <div class="status">
                Environment: {DEPLOYMENT_ENV}<br>
                SQL Translator: {'✅ Ready' if LOADED_FEATURES["sql_translator"] else '❌ Not Available'}<br>
                Power BI Analyst: {'✅ Loaded' if LOADED_FEATURES["powerbi_analyst"] else '⚠️ Not Loaded' if powerbi_configured else '❌ Not Configured'}<br>
                Features Loaded: {sum(1 for v in LOADED_FEATURES.values() if v)}/{len(LOADED_FEATURES)}
            </div>
            
            <div class="debug-info">
                <strong>Debug Info:</strong><br>
                Power BI Routes Loaded: {LOADED_FEATURES["powerbi_analyst"]}<br>
                Power BI Configured: {powerbi_configured}<br>
                Import Errors: {len(IMPORT_ERRORS)}<br>
                Check /health for detailed diagnostics
            </div>
        </div>
    </body>
    </html>
    """
    
    return Response(text=html, content_type='text/html')

# Create the application
APP = web.Application(middlewares=[aiohttp_error_middleware])

# Add main routes
APP.router.add_get("/", index)
APP.router.add_get("/health", health)

# Simple info endpoint (add early to ensure it works)
async def info(req: Request) -> Response:
    """Information about the application"""
    
    # Check Power BI configuration
    powerbi_configured = all([
        os.environ.get("POWERBI_TENANT_ID"),
        os.environ.get("POWERBI_CLIENT_ID"),
        os.environ.get("POWERBI_CLIENT_SECRET")
    ])
    
    info_data = {
        'name': 'SQL Assistant Enhanced with Power BI',
        'version': '2.2.3',
        'features_loaded': LOADED_FEATURES,
        'powerbi_configured': powerbi_configured,
        'routes_count': len(list(APP.router.routes())),
        'timestamp': datetime.now().isoformat(),
        'import_errors': IMPORT_ERRORS
    }
    
    # Add token usage if available
    if SQL_TRANSLATOR:
        info_data['token_usage'] = SQL_TRANSLATOR.get_usage_summary()
    
    return json_response(info_data)

APP.router.add_get("/info", info)

# Import and add admin dashboard
try:
    logger.info("Loading admin dashboard...")
    from admin_dashboard_routes import add_admin_routes
    add_admin_routes(APP, SQL_TRANSLATOR)
    logger.info("✓ Admin dashboard routes added")
    LOADED_FEATURES["admin_dashboard"] = True
except ImportError as e:
    logger.error(f"❌ Failed to add admin dashboard: {e}")
    IMPORT_ERRORS["admin_dashboard"] = str(e)
except Exception as e:
    logger.error(f"❌ Error adding admin dashboard: {e}", exc_info=True)
    IMPORT_ERRORS["admin_dashboard"] = str(e) + "\n" + traceback.format_exc()

# Import and add SQL console with enhanced error handling
try:
    logger.info("Loading SQL console...")
    from sql_console_routes import add_console_routes
    add_console_routes(APP, SQL_TRANSLATOR)
    logger.info("✓ Enhanced SQL console routes added with error analysis")
    LOADED_FEATURES["sql_console"] = True
except ImportError as e:
    logger.error(f"❌ Failed to add SQL console: {e}")
    IMPORT_ERRORS["sql_console"] = str(e)
except Exception as e:
    logger.error(f"❌ Error adding SQL console: {e}", exc_info=True)
    IMPORT_ERRORS["sql_console"] = str(e) + "\n" + traceback.format_exc()

# Import and add Power BI Analyst - BETTER ERROR HANDLING
logger.info("=" * 60)
logger.info("ATTEMPTING TO LOAD POWER BI ANALYST...")
logger.info("=" * 60)

# Check configuration before attempting to load
powerbi_configured = all([
    os.environ.get("POWERBI_TENANT_ID"),
    os.environ.get("POWERBI_CLIENT_ID"),
    os.environ.get("POWERBI_CLIENT_SECRET")
])

if not powerbi_configured:
    logger.warning("Power BI environment variables not configured")
    
    # Add placeholder route
    async def analyst_not_configured(request):
        return Response(text="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Power BI Analyst - Not Configured</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                h1 { color: #333; }
                .error { background: #fee; padding: 15px; border-radius: 5px; border: 1px solid #fcc; }
                code { background: #f0f0f0; padding: 2px 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Power BI Analyst - Configuration Required</h1>
                <div class="error">
                    <p>Power BI environment variables are not configured.</p>
                    <p>Required: POWERBI_TENANT_ID, POWERBI_CLIENT_ID, POWERBI_CLIENT_SECRET</p>
                </div>
                <p><a href="/">Back to Home</a></p>
            </div>
        </body>
        </html>
        """, content_type='text/html')
    
    APP.router.add_get('/analyst', analyst_not_configured)
    logger.info("Added placeholder route for unconfigured Power BI Analyst")
else:
    # Try to load analyst with detailed error tracking
    analyst_loaded = False
    
    try:
        logger.info("Testing individual component imports...")
        
        # Test each import separately to identify the failing component
        components_status = {}
        
        # Test powerbi_client
        try:
            logger.info("  Testing powerbi_client import...")
            import powerbi_client
            components_status['powerbi_client'] = "✓ Loaded"
            logger.info("  ✓ powerbi_client imported successfully")
        except Exception as e:
            components_status['powerbi_client'] = f"✗ Error: {str(e)}"
            logger.error(f"  ✗ powerbi_client import failed: {e}")
            IMPORT_ERRORS['powerbi_client'] = str(e) + "\n" + traceback.format_exc()
            raise
        
        # Test analyst_translator
        try:
            logger.info("  Testing analyst_translator import...")
            import analyst_translator
            components_status['analyst_translator'] = "✓ Loaded"
            logger.info("  ✓ analyst_translator imported successfully")
        except Exception as e:
            components_status['analyst_translator'] = f"✗ Error: {str(e)}"
            logger.error(f"  ✗ analyst_translator import failed: {e}")
            IMPORT_ERRORS['analyst_translator'] = str(e) + "\n" + traceback.format_exc()
            raise
        
        # Test analysis_agent
        try:
            logger.info("  Testing analysis_agent import...")
            import analysis_agent
            components_status['analysis_agent'] = "✓ Loaded"
            logger.info("  ✓ analysis_agent imported successfully")
        except Exception as e:
            components_status['analysis_agent'] = f"✗ Error: {str(e)}"
            logger.error(f"  ✗ analysis_agent import failed: {e}")
            IMPORT_ERRORS['analysis_agent'] = str(e) + "\n" + traceback.format_exc()
            raise
        
        # Test analyst_ui
        try:
            logger.info("  Testing analyst_ui import...")
            import analyst_ui
            components_status['analyst_ui'] = "✓ Loaded"
            logger.info("  ✓ analyst_ui imported successfully")
        except Exception as e:
            components_status['analyst_ui'] = f"✗ Error: {str(e)}"
            logger.error(f"  ✗ analyst_ui import failed: {e}")
            IMPORT_ERRORS['analyst_ui'] = str(e) + "\n" + traceback.format_exc()
            raise
        
        # Now try analyst_routes
        try:
            logger.info("  Testing analyst_routes import...")
            from analyst_routes import add_analyst_routes
            components_status['analyst_routes'] = "✓ Loaded"
            logger.info("  ✓ analyst_routes imported successfully")
            
            # Try to add routes
            logger.info("Adding analyst routes to application...")
            add_analyst_routes(APP)
            logger.info("✓ Power BI Analyst routes added successfully")
            analyst_loaded = True
            LOADED_FEATURES["powerbi_analyst"] = True
            
        except Exception as e:
            components_status['analyst_routes'] = f"✗ Error: {str(e)}"
            logger.error(f"  ✗ analyst_routes import/add failed: {e}")
            IMPORT_ERRORS['analyst_routes'] = str(e) + "\n" + traceback.format_exc()
            raise
            
    except Exception as e:
        logger.error(f"Failed to load Power BI Analyst: {e}", exc_info=True)
        IMPORT_ERRORS['powerbi_analyst'] = str(e) + "\n" + traceback.format_exc()
        
        # Add detailed error page
        async def analyst_error(request):
            import_errors_html = ""
            for module, error in IMPORT_ERRORS.items():
                if 'powerbi' in module or 'analyst' in module:
                    import_errors_html += f"""
                    <div class="error-detail">
                        <h4>{module}</h4>
                        <pre>{error}</pre>
                    </div>
                    """
            
            return Response(text=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Power BI Analyst - Loading Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
                    h1 {{ color: #333; }}
                    .error {{ background: #fee; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                    .error-detail {{ background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                    .error-detail h4 {{ margin-top: 0; color: #c00; }}
                    pre {{ overflow: auto; white-space: pre-wrap; font-size: 12px; }}
                    .suggestions {{ background: #e6f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Power BI Analyst - Module Loading Error</h1>
                    <div class="error">
                        <h2>The Power BI Analyst module failed to load</h2>
                        <h3>Import Errors:</h3>
                        {import_errors_html}
                    </div>
                    <div class="suggestions">
                        <h3>Troubleshooting Steps:</h3>
                        <ol>
                            <li>Check the application logs in Azure Portal</li>
                            <li>Verify all required packages are in requirements.txt</li>
                            <li>Ensure MSAL is installed: <code>pip install msal</code></li>
                            <li>Check for syntax errors in the Python files</li>
                            <li>Restart the App Service after fixing issues</li>
                        </ol>
                    </div>
                    <p><a href="/health">Check Health Status</a> | <a href="/">Back to Home</a></p>
                </div>
            </body>
            </html>
            """, content_type='text/html')
        
        APP.router.add_get('/analyst', analyst_error)
        APP.router.add_get('/analyst/', analyst_error)
        logger.info("✓ Added error page for Power BI Analyst")

logger.info("=" * 60)
logger.info(f"POWER BI ANALYST LOADING COMPLETE - Success: {LOADED_FEATURES.get('powerbi_analyst', False)}")
logger.info("=" * 60)

# Log final route count
route_count = len(list(APP.router.routes()))
logger.info(f"Total routes registered: {route_count}")

# List all routes for debugging
logger.info("Registered routes:")
for i, route in enumerate(APP.router.routes()):
    route_info = str(route)
    if hasattr(route, 'resource'):
        route_info = str(route.resource)
    logger.info(f"  {i+1}. {route_info}")

# Startup tasks
async def on_startup(app):
    """Perform startup tasks"""
    logger.info("=== SQL Assistant Enhanced Startup ===")
    logger.info(f"Environment: {DEPLOYMENT_ENV}")
    logger.info(f"Version: 2.2.3")
    logger.info(f"Features Loaded: {LOADED_FEATURES}")
    logger.info(f"Import Errors: {len(IMPORT_ERRORS)}")
    
    if missing_vars:
        logger.warning(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
    else:
        logger.info("✓ All required environment variables are set")
    
    # Log Power BI status
    powerbi_configured = all([
        os.environ.get("POWERBI_TENANT_ID"),
        os.environ.get("POWERBI_CLIENT_ID"),
        os.environ.get("POWERBI_CLIENT_SECRET")
    ])
    
    logger.info(f"Power BI Configuration: {powerbi_configured}")
    logger.info(f"Power BI Analyst Loaded: {LOADED_FEATURES.get('powerbi_analyst', False)}")
    
    # Final route check
    analyst_routes = [str(r) for r in app.router.routes() if '/analyst' in str(r)]
    logger.info(f"Analyst routes found: {len(analyst_routes)}")
    
    # Log import errors if any
    if IMPORT_ERRORS:
        logger.error("=== Import Errors ===")
        for module, error in IMPORT_ERRORS.items():
            logger.error(f"{module}: {error.splitlines()[0]}")  # First line only
    
    # Create necessary directories
    dirs = ['.token_usage', 'logs', '.query_history', '.error_logs', '.analyst_cache']
    for dir_name in dirs:
        try:
            os.makedirs(dir_name, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create directory {dir_name}: {e}")
    
    logger.info("=== Startup completed ===")

# Cleanup tasks
async def on_cleanup(app):
    """Perform cleanup tasks"""
    logger.info("SQL Assistant shutting down...")
    
    # Save token usage if available
    if SQL_TRANSLATOR:
        usage = SQL_TRANSLATOR.get_usage_summary()
        logger.info(f"Final token usage: {usage['total_tokens']} tokens, ${usage['estimated_cost']:.4f}")

# Register startup and cleanup handlers
APP.on_startup.append(on_startup)
APP.on_cleanup.append(on_cleanup)

# Add additional utility routes
async def test_sql_translation(req: Request) -> Response:
    """Test endpoint for SQL translation with error analysis"""
    try:
        data = await req.json()
        query = data.get('query', 'show me all tables')
        
        if not SQL_TRANSLATOR:
            return json_response({
                'status': 'error',
                'error': 'SQL Translator not available'
            })
        
        result = await SQL_TRANSLATOR.translate_to_sql(query)
        
        return json_response({
            'status': 'success',
            'query': result.query,
            'database': result.database,
            'explanation': result.explanation,
            'confidence': result.confidence,
            'warnings': result.warnings,
            'error': result.error
        })
    except Exception as e:
        return json_response({
            'status': 'error',
            'error': str(e)
        }, status=500)

# Add test route
APP.router.add_post("/api/test-translation", test_sql_translation)

# Main entry point
if __name__ == "__main__":
    try:
        PORT = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting enhanced application on port {PORT}")
        logger.info(f"Access the application at: http://localhost:{PORT}")
        
        # Log available endpoints
        logger.info("Available endpoints:")
        for route in APP.router.routes():
            if hasattr(route, 'resource'):
                logger.info(f"  - {route.resource}")
        
        web.run_app(
            APP,
            host="0.0.0.0",
            port=PORT,
            access_log_format='%a %t "%r" %s %b "%{Referer}i" "%{User-Agent}i" %Tf'
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise

# End of file