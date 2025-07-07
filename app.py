# app.py - Updated main application with URL-embedded authentication
"""
Main application entry point for SQL Assistant Teams Bot
Updated to use URL-embedded authentication (code in URL)
"""

import os
import logging
from datetime import datetime
from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    UserState,
    TurnContext,
    MessageFactory
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ErrorResponseException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("=== SQL Assistant Bot Starting ===")
logger.info(f"Python version: {os.sys.version}")
logger.info(f"Working directory: {os.getcwd()}")

# Import our custom modules with error handling
try:
    from azure_openai_sql_translator import AzureOpenAISQLTranslator
    logger.info("✓ Successfully imported AzureOpenAISQLTranslator")
except ImportError as e:
    logger.error(f"❌ Failed to import AzureOpenAISQLTranslator: {e}")
    raise

try:
    from teams_sql_bot import SQLAssistantBot
    logger.info("✓ Successfully imported SQLAssistantBot")
except ImportError as e:
    logger.error(f"❌ Failed to import SQLAssistantBot: {e}")
    # Create a simplified bot as fallback
    logger.warning("Creating fallback bot implementation")
    
    class SimpleSQLBot:
        def __init__(self, **kwargs):
            logger.info("Initialized SimpleSQLBot fallback")
        
        async def on_turn(self, turn_context: TurnContext):
            await turn_context.send_activity(
                MessageFactory.text("🤖 SQL Assistant Bot is running! However, some features are temporarily unavailable. Please check the logs.")
            )
    
    SQLAssistantBot = SimpleSQLBot

# Import admin dashboard
try:
    from admin_dashboard import add_admin_routes
    logger.info("✓ Successfully imported admin dashboard")
    ADMIN_DASHBOARD_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Admin dashboard not available: {e}")
    ADMIN_DASHBOARD_AVAILABLE = False

# Add this import at the top of app.py after the other imports
try:
    from sql_console import add_console_routes
    logger.info("✓ Successfully imported SQL console")
    SQL_CONSOLE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ SQL console not available: {e}")
    SQL_CONSOLE_AVAILABLE = False

# Then after adding admin dashboard routes (around line 440), add:

# Add SQL console routes if available
if SQL_CONSOLE_AVAILABLE:
    try:
        console = add_console_routes(APP, SQL_TRANSLATOR, BOT)
        logger.info("✓ SQL console routes added")
        logger.info("🖥️ SQL console will be available at /console")
    except Exception as e:
        logger.error(f"❌ Failed to add SQL console routes: {e}")
        SQL_CONSOLE_AVAILABLE = False

# Update the startup logs section to include console endpoint:
# In the on_startup function, add this to the endpoints list:
if SQL_CONSOLE_AVAILABLE:
    logger.info("  - /console (SQL console) 🖥️")

# Check critical environment variables
def check_environment():
    """Check and log environment variable status"""
    required_vars = {
        "MICROSOFT_APP_ID": "Bot Framework App ID",
        "MICROSOFT_APP_PASSWORD": "Bot Framework Password",
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI Endpoint",
        "AZURE_OPENAI_API_KEY": "Azure OpenAI API Key",
        "AZURE_FUNCTION_URL": "Azure Function URL"
    }
    
    missing_vars = []
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
        logger.info("✓ AZURE_FUNCTION_URL contains embedded authentication (code parameter)")
        logger.info("ℹ️ AZURE_FUNCTION_KEY: Not needed (using URL-embedded auth)")
    else:
        logger.warning("⚠️ AZURE_FUNCTION_URL does not contain authentication code")
        logger.warning("⚠️ Function calls may fail without proper authentication")
    
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if value:
            logger.info(f"ℹ️ {var}: {value} ({description})")
        else:
            logger.warning(f"⚠️ {var}: Not set ({description})")
    
    return missing_vars

# Check environment
missing_vars = check_environment()

# Get deployment environment
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "production")
logger.info(f"Running in {DEPLOYMENT_ENV} environment")

# Create adapter with enhanced error handling
SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MICROSOFT_APP_ID", ""),
    app_password=os.environ.get("MICROSOFT_APP_PASSWORD", "")
)

ADAPTER = BotFrameworkAdapter(SETTINGS)

# Enhanced error handler
async def on_error(context: TurnContext, error: Exception):
    """Handle errors in the bot"""
    logger.error(f"Bot error: {error}", exc_info=True)
    
    error_message = "Sorry, an error occurred while processing your request."
    
    if isinstance(error, ErrorResponseException):
        error_message += f"\n\nError details: {error.message}"
    elif DEPLOYMENT_ENV == "development":
        error_message += f"\n\nDebug info: {type(error).__name__}: {str(error)}"
    
    try:
        await context.send_activity(MessageFactory.text(error_message))
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

ADAPTER.on_turn_error = on_error

# Create storage and state
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Initialize Azure OpenAI translator with error handling
SQL_TRANSLATOR = None
try:
    if missing_vars:
        logger.warning(f"Missing variables: {missing_vars}. SQL translation will be limited.")
    
    SQL_TRANSLATOR = AzureOpenAISQLTranslator(
        endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
    )
    logger.info("✓ Azure OpenAI translator initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Azure OpenAI translator: {e}")
    logger.warning("Bot will run with limited functionality")

# Create the bot - Note: function_key is now None for URL-embedded auth
try:
    BOT = SQLAssistantBot(
        conversation_state=CONVERSATION_STATE,
        user_state=USER_STATE,
        sql_translator=SQL_TRANSLATOR,
        function_url=os.environ.get("AZURE_FUNCTION_URL", ""),
        function_key=None,  # No separate key needed for URL-embedded auth
        mcp_client=None  # Disabled for now
    )
    logger.info("✓ SQLAssistantBot initialized successfully")
    logger.info("ℹ️ Using URL-embedded authentication for Azure Function")
except Exception as e:
    logger.error(f"❌ Failed to initialize SQLAssistantBot: {e}")
    logger.warning("Using fallback bot")
    
    class FallbackBot:
        async def on_turn(self, turn_context: TurnContext):
            if turn_context.activity.type == "message":
                await turn_context.send_activity(
                    MessageFactory.text(
                        f"🤖 SQL Assistant Bot is running but in limited mode.\n\n"
                        f"Missing environment variables: {', '.join(missing_vars) if missing_vars else 'None'}\n\n"
                        f"Please check your Azure App Service configuration."
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
                "admin_dashboard": "available" if ADMIN_DASHBOARD_AVAILABLE else "not available"
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
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    # No additional headers needed for URL-embedded auth
                    headers = {"Content-Type": "application/json"}
                    
                    async with session.post(
                        function_url,
                        json={"query_type": "metadata"},
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        health_status["services"]["sql_function_status"] = response.status
                        health_status["services"]["sql_function_reachable"] = response.status == 200
            except Exception as e:
                health_status["services"]["sql_function_error"] = str(e)
                health_status["services"]["sql_function_reachable"] = False
        
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
        "message": "SQL Assistant Bot is running!",
        "timestamp": datetime.now().isoformat(),
        "environment": DEPLOYMENT_ENV,
        "auth_method": "URL-embedded authentication",
        "admin_dashboard": f"Available at https://{req.host}/admin" if ADMIN_DASHBOARD_AVAILABLE else "Not available"
    })

# Admin dashboard info endpoint
async def admin_info(req: Request) -> Response:
    """Information about admin dashboard"""
    if ADMIN_DASHBOARD_AVAILABLE:
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

# Add admin dashboard routes if available
if ADMIN_DASHBOARD_AVAILABLE:
    try:
        dashboard = add_admin_routes(APP, SQL_TRANSLATOR, BOT)
        logger.info("✓ Admin dashboard routes added")
        logger.info("📊 Admin dashboard will be available at /admin")
    except Exception as e:
        logger.error(f"❌ Failed to add admin dashboard routes: {e}")
        ADMIN_DASHBOARD_AVAILABLE = False

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