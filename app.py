#!/usr/bin/env python3
# app.py - Main SQL Assistant Bot Application with Console Support
"""
Complete SQL Assistant Bot with all features enabled including SQL Console
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Bot Framework Imports
from botbuilder.core import (
    TurnContext, 
    ActivityHandler, 
    MessageFactory,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    UserState,
    MemoryStorage
)
from botbuilder.schema import Activity, ChannelAccount

# Azure and OpenAI imports
from azure_openai_sql_translator import AzureOpenAISQLTranslator
from autonomous_sql_explorer import AutonomousSQLExplorer
from query_validator import QueryValidator
from token_limiter import TokenLimiter

# Web framework
from aiohttp import web
from aiohttp.web import Request, Response, json_response, middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sql_assistant.log')
    ]
)
logger = logging.getLogger(__name__)

# Suppress verbose logs
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('tiktoken').setLevel(logging.WARNING)

# Environment Configuration
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "production")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL")
MAX_DAILY_TOKENS = int(os.environ.get("MAX_DAILY_TOKENS", "500000"))

# Check and log environment variables
missing_vars = []
def check_environment():
    """Check and log environment variable status"""
    required_vars = {
        "MICROSOFT_APP_ID": "Bot Framework App ID",
        "MICROSOFT_APP_PASSWORD": "Bot Framework Password",
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI Endpoint",
        "AZURE_OPENAI_API_KEY": "Azure OpenAI API Key",
        "AZURE_FUNCTION_URL": "Azure Function URL"
    }
    
    logger.info("Checking environment variables:")
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            if "KEY" in var or "PASSWORD" in var:
                masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
                logger.info(f"✓ {var}: {masked} ({description})")
            else:
                logger.info(f"✓ {var}: {value[:30]}... ({description})")
        else:
            logger.error(f"❌ {var}: NOT SET ({description})")
            missing_vars.append(var)
    
    # Optional variables - Note: AZURE_FUNCTION_KEY is no longer needed
    optional_vars = {
        "AZURE_OPENAI_DEPLOYMENT_NAME": "OpenAI deployment name (defaults to gpt-4)",
        "PORT": "Application port (defaults to 8000)"
    }
    
    # Check if URL has embedded authentication
    function_url = os.environ.get("AZURE_FUNCTION_URL", "")
    if function_url and "code=" in function_url:
        logger.info("✅ Azure Function authentication: URL-embedded (recommended)")
    else:
        logger.warning("⚠️ Azure Function URL does not contain authentication code")
        logger.warning("   Consider using URL with embedded auth code from Azure Portal")
    
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if value:
            logger.info(f"✓ {var}: {value} ({description})")
        else:
            logger.info(f"ℹ {var}: Using default ({description})")
    
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

# Bot Framework Setup
SETTINGS = BotFrameworkAdapterSettings(
    os.environ.get("MICROSOFT_APP_ID", ""),
    os.environ.get("MICROSOFT_APP_PASSWORD", "")
)

ADAPTER = BotFrameworkAdapter(SETTINGS)

# Storage and State
MEMORY_STORAGE = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY_STORAGE)
USER_STATE = UserState(MEMORY_STORAGE)

# Error handler
async def on_error(context: TurnContext, error: Exception):
    """Handle errors in bot"""
    logger.error(f"Bot error: {error}", exc_info=True)
    await context.send_activity(
        MessageFactory.text(
            f"Sorry, an error occurred: {str(error)}\n\n"
            "Please try again or contact support if the issue persists."
        )
    )

ADAPTER.on_turn_error = on_error

# Initialize components based on environment
try:
    SQL_TRANSLATOR = AzureOpenAISQLTranslator()
    logger.info("✓ SQL Translator initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize SQL Translator: {e}")
    SQL_TRANSLATOR = None

# Initialize other components
if SQL_TRANSLATOR:
    try:
        EXPLORER = AutonomousSQLExplorer(SQL_TRANSLATOR)
        VALIDATOR = QueryValidator()
        TOKEN_LIMITER = TokenLimiter(max_daily_tokens=MAX_DAILY_TOKENS)
        logger.info("✓ All SQL components initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize SQL components: {e}")
        EXPLORER = None
        VALIDATOR = None
        TOKEN_LIMITER = None
else:
    EXPLORER = None
    VALIDATOR = None
    TOKEN_LIMITER = None

# Bot Implementation
try:
    # Import the SQL bot if all components are ready
    if all([SQL_TRANSLATOR, EXPLORER, VALIDATOR, TOKEN_LIMITER]):
        from teams_sql_bot import SQLAssistantBot
        BOT = SQLAssistantBot(
            conversation_state=CONVERSATION_STATE,
            user_state=USER_STATE,
            sql_translator=SQL_TRANSLATOR,
            sql_explorer=EXPLORER,
            query_validator=VALIDATOR,
            token_limiter=TOKEN_LIMITER
        )
        logger.info("✓ SQL Assistant Bot initialized with full functionality")
    else:
        raise ImportError("Missing required components")
        
except ImportError as e:
    logger.error(f"Failed to import SQL bot, using fallback: {e}")
    
    # Fallback bot
    class SimpleSQLBot(ActivityHandler):
        """Simple fallback bot when full functionality unavailable"""
        
        def __init__(self):
            super().__init__()
            logger.info("Using SimpleSQLBot (fallback mode)")
        
        async def on_message_activity(self, turn_context: TurnContext):
            """Handle messages in fallback mode"""
            text = turn_context.activity.text.lower() if turn_context.activity.text else ""
            
            if any(word in text for word in ["hello", "hi", "help"]):
                await turn_context.send_activity(
                    MessageFactory.text(
                        "Hi! I'm the SQL Assistant Bot. 🤖\n\n"
                        "I'm currently running in limited mode due to configuration issues.\n\n"
                        "Please check:\n"
                        "1. All environment variables are set correctly\n"
                        "2. Azure OpenAI service is accessible\n"
                        "3. Azure SQL Function is configured\n\n"
                        "Contact your administrator for help."
                    )
                )
            else:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "I'm running in limited mode. Some features may not be available.\n"
                        "Type 'help' for more information."
                    )
                )
    
    class FallbackBot(SimpleSQLBot):
        """Fallback bot when main bot can't be loaded"""
        
        async def on_message_activity(self, turn_context: TurnContext):
            """Handle messages"""
            if SQL_TRANSLATOR:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "I can translate natural language to SQL, but some features are limited.\n"
                        "Try asking me to write a SQL query!"
                    )
                )
            else:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "The SQL Assistant is starting up. Some components are still initializing.\n"
                        "Please wait a moment and try again."
                    )
                )
    
    BOT = FallbackBot()

# Define the main messaging endpoint
async def messages(req: Request) -> Response:
    """Handle incoming messages from Teams"""
    try:
        logger.info(f"Received message request: {req.method} {req.path}")
        
        # Validate content type
        content_type = req.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.error(f"Invalid content type: {content_type}")
            return Response(status=415, text="Unsupported Media Type")
        
        # Parse request body
        try:
            body = await req.json()
            logger.info(f"Request body type: {body.get('type', 'unknown')}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request: {e}")
            return Response(status=400, text="Invalid JSON")
        
        activity = Activity().deserialize(body)
        
        # Get auth header
        auth_header = req.headers.get("Authorization", "")
        
        # Process activity
        await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        
        logger.info("Message processed successfully")
        return Response(status=200)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return Response(status=500, text=f"Internal Server Error: {str(e)}")

# Health check endpoint with detailed status
async def health(req: Request) -> Response:
    """Comprehensive health check endpoint"""
    try:
        # Check if function URL has embedded auth
        function_url = os.environ.get("AZURE_FUNCTION_URL", "")
        has_embedded_auth = "code=" in function_url
        
        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": DEPLOYMENT_ENV,
            "python_version": os.sys.version,
            "working_directory": os.getcwd(),
            "services": {
                "bot": "running",
                "adapter": "configured",
                "openai": "configured" if SQL_TRANSLATOR else "error",
                "sql_function": "configured" if function_url else "not configured",
                "sql_function_auth": "url-embedded" if has_embedded_auth else "none",
                "mcp": "disabled",
                "admin_dashboard": "available" if 'ADMIN_DASHBOARD_AVAILABLE' in globals() and ADMIN_DASHBOARD_AVAILABLE else "not available",
                "sql_console": "available" if 'SQL_CONSOLE_AVAILABLE' in globals() and SQL_CONSOLE_AVAILABLE else "not available"
            },
            "environment_check": {
                "missing_variables": missing_vars,
                "has_critical_vars": len(missing_vars) == 0,
                "function_auth_method": "url-embedded" if has_embedded_auth else "requires-configuration"
            }
        }
        
        # Test Azure Function if configured
        if function_url:
            try:
                logger.info("Testing Azure Function connectivity...")
                test_payload = {"query_type": "test"}
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        function_url,
                        json=test_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            health_status["services"]["sql_function"] = "healthy"
                            logger.info("✓ Azure Function test successful")
                        else:
                            health_status["services"]["sql_function"] = f"error (status: {response.status})"
                            logger.error(f"Azure Function test failed: {response.status}")
            except Exception as e:
                health_status["services"]["sql_function"] = f"error: {str(e)}"
                logger.error(f"Azure Function test error: {e}")
        
        return json_response(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json_response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=503)

# Simple test endpoint
async def test(req: Request) -> Response:
    """Simple test endpoint"""
    return json_response({
        "message": "SQL Assistant Bot is running! 🤖",
        "timestamp": datetime.now().isoformat(),
        "environment": DEPLOYMENT_ENV,
        "auth_method": "URL-embedded authentication",
        "admin_dashboard": f"Available at https://{req.host}/admin" if 'ADMIN_DASHBOARD_AVAILABLE' in globals() and ADMIN_DASHBOARD_AVAILABLE else "Not available"
    })

# Admin dashboard info endpoint
async def admin_info(req: Request) -> Response:
    """Information about admin dashboard"""
    if 'ADMIN_DASHBOARD_AVAILABLE' in globals() and ADMIN_DASHBOARD_AVAILABLE:
        return json_response({
            "available": True,
            "url": f"https://{req.host}/admin",
            "message": "Admin dashboard is available",
            "auth_method": "URL-embedded authentication active",
            "features": [
                "Real-time system monitoring",
                "Component health testing", 
                "Service status display (no env vars)",
                "Microsoft authentication support",
                "Performance metrics",
                "Live activity logs",
                "Automated testing suite",
                "SQL function console with database listing"
            ]
        })
    else:
        return json_response({
            "available": False,
            "message": "Admin dashboard module not found",
            "solution": "Deploy admin_dashboard.py with your bot"
        })

# Create the application
APP = web.Application(middlewares=[aiohttp_error_middleware])

# Add main bot routes
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)
APP.router.add_get("/test", test)
APP.router.add_get("/", health)  # Default route
APP.router.add_get("/admin-info", admin_info)

# Import and add admin dashboard
ADMIN_DASHBOARD_AVAILABLE = False
try:
    from admin_dashboard import add_admin_routes
    logger.info("✓ Successfully imported admin dashboard")
    ADMIN_DASHBOARD_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Admin dashboard not available: {e}")

# Import and add SQL console
SQL_CONSOLE_AVAILABLE = False
try:
    from sql_console import add_console_routes
    logger.info("✓ Successfully imported SQL console")
    SQL_CONSOLE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ SQL console not available: {e}")

# Add admin dashboard routes if available
if ADMIN_DASHBOARD_AVAILABLE:
    try:
        dashboard = add_admin_routes(APP, SQL_TRANSLATOR, BOT)
        logger.info("✓ Admin dashboard routes added")
        logger.info("📊 Admin dashboard will be available at /admin")
    except Exception as e:
        logger.error(f"❌ Failed to add admin dashboard routes: {e}")
        ADMIN_DASHBOARD_AVAILABLE = False

# Add SQL console routes if available
if SQL_CONSOLE_AVAILABLE:
    try:
        console = add_console_routes(APP, SQL_TRANSLATOR, BOT)
        logger.info("✓ SQL console routes added")
        logger.info("🖥️ SQL console will be available at /console")
    except Exception as e:
        logger.error(f"❌ Failed to add SQL console routes: {e}")
        SQL_CONSOLE_AVAILABLE = False

# Startup tasks
async def on_startup(app):
    """Perform startup tasks"""
    logger.info("=== SQL Assistant Bot Startup ===")
    logger.info(f"Environment: {DEPLOYMENT_ENV}")
    logger.info(f"Bot App ID: {os.environ.get('MICROSOFT_APP_ID', 'Not set')[:8]}...")
    
    # Check authentication method
    function_url = os.environ.get("AZURE_FUNCTION_URL", "")
    if function_url and "code=" in function_url:
        logger.info("✅ Using URL-embedded authentication for Azure Function")
    else:
        logger.warning("⚠️ Azure Function URL does not contain authentication")
    
    if missing_vars:
        logger.warning(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
        logger.warning("Bot will run with limited functionality")
    else:
        logger.info("✓ All required environment variables are set")
    
    # Create necessary directories
    dirs = ['.pattern_cache', '.exploration_exports', '.query_logs', '.token_usage', 'logs']
    for dir_name in dirs:
        try:
            os.makedirs(dir_name, exist_ok=True)
            logger.info(f"✓ Created directory: {dir_name}")
        except Exception as e:
            logger.warning(f"Failed to create directory {dir_name}: {e}")
    
    # Log available endpoints
    logger.info("📍 Available endpoints:")
    logger.info("  - /health (health check)")
    logger.info("  - /test (simple test)")
    logger.info("  - /api/messages (bot messaging)")
    if ADMIN_DASHBOARD_AVAILABLE:
        logger.info("  - /admin (admin dashboard) 🎉")
        logger.info("  - /admin-info (dashboard info)")
    else:
        logger.warning("  - /admin (not available - deploy admin_dashboard.py)")
    
    if SQL_CONSOLE_AVAILABLE:
        logger.info("  - /console (SQL console) 🖥️")
    else:
        logger.warning("  - /console (not available - deploy sql_console.py)")
    
    logger.info("=== Bot startup completed ===")

# Cleanup tasks
async def on_cleanup(app):
    """Perform cleanup tasks"""
    logger.info("SQL Assistant Bot shutting down...")
    
    try:
        CONVERSATION_STATE._storage._memory.clear()
        USER_STATE._storage._memory.clear()
        logger.info("✓ Cleared bot state")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    
    logger.info("SQL Assistant Bot shutdown complete")

# Register startup and cleanup handlers
APP.on_startup.append(on_startup)
APP.on_cleanup.append(on_cleanup)

# Main entry point
if __name__ == "__main__":
    try:
        PORT = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting bot on port {PORT}")
        logger.info("Using URL-embedded authentication (no separate function key needed)")
        
        if ADMIN_DASHBOARD_AVAILABLE:
            logger.info(f"🎉 Admin dashboard will be available at: http://localhost:{PORT}/admin")
        
        if SQL_CONSOLE_AVAILABLE:
            logger.info(f"🖥️ SQL console will be available at: http://localhost:{PORT}/console")
        
        web.run_app(
            APP,
            host="0.0.0.0",
            port=PORT,
            access_log_format='%a %t "%r" %s %b "%{Referer}i" "%{User-Agent}i" %Tf'
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        raise

logger.info("App module loaded successfully")