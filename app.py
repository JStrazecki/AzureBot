#!/usr/bin/env python3
# app.py - Main SQL Assistant Application (Console-focused)
"""
SQL Assistant Application - Simplified for Console Testing
Teams bot functionality will be added later
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

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

# Environment Configuration
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "production")

# Check environment variables
def check_environment():
    """Check and log environment variable status"""
    required_vars = {
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI Endpoint",
        "AZURE_OPENAI_API_KEY": "Azure OpenAI API Key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "OpenAI Deployment Name",
        "AZURE_FUNCTION_URL": "Azure Function URL"
    }
    
    logger.info("=== Environment Check ===")
    missing_vars = []
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            if "KEY" in var or "PASSWORD" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                logger.info(f"✓ {var}: {masked}")
            else:
                logger.info(f"✓ {var}: {value[:30]}...")
        else:
            logger.error(f"❌ {var}: NOT SET ({description})")
            missing_vars.append(var)
    
    # Check if URL has embedded authentication
    function_url = os.environ.get("AZURE_FUNCTION_URL", "")
    if function_url and "code=" in function_url:
        logger.info("✅ Azure Function authentication: URL-embedded (recommended)")
    
    return missing_vars

# Run environment check
missing_vars = check_environment()

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

# Initialize OpenAI translator if available
SQL_TRANSLATOR = None
if not missing_vars or all(var not in missing_vars for var in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY"]):
    try:
        # Import will be created in next artifact
        from sql_translator_simple import SimpleSQLTranslator
        SQL_TRANSLATOR = SimpleSQLTranslator()
        logger.info("✓ SQL Translator initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize SQL Translator: {e}")

# Health check endpoint
async def health(req: Request) -> Response:
    """Health check endpoint"""
    try:
        health_status = {
            "status": "healthy",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": DEPLOYMENT_ENV,
            "services": {
                "console": "available",
                "admin_dashboard": "available",
                "sql_translator": "available" if SQL_TRANSLATOR else "not available",
                "sql_function": "configured" if os.environ.get("AZURE_FUNCTION_URL") else "not configured"
            },
            "missing_vars": missing_vars
        }
        
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
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SQL Assistant</title>
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
                max-width: 500px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 30px;
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
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 SQL Assistant</h1>
            <div class="links">
                <a href="/console">SQL Console</a>
                <a href="/admin">Admin Dashboard</a>
                <a href="/health">Health Status</a>
            </div>
            <div class="status">
                Environment: {DEPLOYMENT_ENV}<br>
                SQL Translator: {'✅ Ready' if SQL_TRANSLATOR else '❌ Not Available'}
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

# Import and add admin dashboard
try:
    from admin_dashboard_routes import add_admin_routes
    add_admin_routes(APP, SQL_TRANSLATOR)
    logger.info("✓ Admin dashboard routes added")
except ImportError as e:
    logger.error(f"❌ Failed to add admin dashboard: {e}")

# Import and add SQL console
try:
    from sql_console_routes import add_console_routes
    add_console_routes(APP, SQL_TRANSLATOR)
    logger.info("✓ SQL console routes added")
except ImportError as e:
    logger.error(f"❌ Failed to add SQL console: {e}")

# Startup tasks
async def on_startup(app):
    """Perform startup tasks"""
    logger.info("=== SQL Assistant Startup ===")
    logger.info(f"Environment: {DEPLOYMENT_ENV}")
    
    if missing_vars:
        logger.warning(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
    else:
        logger.info("✓ All required environment variables are set")
    
    # Create necessary directories
    dirs = ['.token_usage', 'logs']
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

# Register startup and cleanup handlers
APP.on_startup.append(on_startup)
APP.on_cleanup.append(on_cleanup)

# Add additional utility routes
async def test_sql_translation(req: Request) -> Response:
    """Test endpoint for SQL translation"""
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
            'error': result.error
        })
    except Exception as e:
        return json_response({
            'status': 'error',
            'error': str(e)
        }, status=500)

# Add test route
APP.router.add_post("/api/test-translation", test_sql_translation)

# Simple info endpoint
async def info(req: Request) -> Response:
    """Information about the application"""
    return json_response({
        'name': 'SQL Assistant',
        'version': '2.0.0',
        'features': [
            'SQL Console with natural language support',
            'Admin Dashboard with system monitoring',
            'Azure OpenAI integration',
            'Azure SQL Function connectivity'
        ],
        'endpoints': [
            {'path': '/', 'description': 'Home page'},
            {'path': '/console', 'description': 'SQL Console'},
            {'path': '/admin', 'description': 'Admin Dashboard'},
            {'path': '/health', 'description': 'Health check'},
            {'path': '/info', 'description': 'This endpoint'}
        ]
    })

APP.router.add_get("/info", info)

# Main entry point
if __name__ == "__main__":
    try:
        PORT = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting application on port {PORT}")
        logger.info(f"Access the application at: http://localhost:{PORT}")
        
        # Log available endpoints
        logger.info("Available endpoints:")
        logger.info("  - / (Home)")
        logger.info("  - /console (SQL Console)")
        logger.info("  - /admin (Admin Dashboard)")
        logger.info("  - /health (Health Check)")
        logger.info("  - /info (Application Info)")
        
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