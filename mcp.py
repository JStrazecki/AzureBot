#!/usr/bin/env python3
# app.py - Simplified version without MCP
"""
Main application entry point for SQL Assistant Teams Bot
Works without MCP server
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

# Import our custom modules
from teams_sql_bot import SQLAssistantBot
from azure_openai_sql_translator import AzureOpenAISQLTranslator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate required environment variables
REQUIRED_ENV_VARS = [
    "MICROSOFT_APP_ID",
    "MICROSOFT_APP_PASSWORD",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_FUNCTION_URL",
    "AZURE_FUNCTION_KEY"
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Get deployment environment
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "development")
logger.info(f"Running in {DEPLOYMENT_ENV} environment")

# Create adapter
SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MICROSOFT_APP_ID", ""),
    app_password=os.environ.get("MICROSOFT_APP_PASSWORD", "")
)

ADAPTER = BotFrameworkAdapter(SETTINGS)

# Error handler
async def on_error(context: TurnContext, error: Exception):
    """Handle errors in the bot"""
    logger.error(f"Error in bot: {error}", exc_info=True)
    
    error_message = "Sorry, an error occurred while processing your request."
    
    if isinstance(error, ErrorResponseException):
        error_message += f"\n\nError details: {error.message}"
    
    try:
        await context.send_activity(MessageFactory.text(error_message))
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

ADAPTER.on_turn_error = on_error

# Create storage and state
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Initialize Azure OpenAI translator
try:
    SQL_TRANSLATOR = AzureOpenAISQLTranslator(
        endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
    )
    logger.info("Azure OpenAI translator initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Azure OpenAI translator: {e}")
    raise

# Create the bot WITHOUT MCP
BOT = SQLAssistantBot(
    conversation_state=CONVERSATION_STATE,
    user_state=USER_STATE,
    sql_translator=SQL_TRANSLATOR,
    function_url=os.environ.get("AZURE_FUNCTION_URL"),
    function_key=os.environ.get("AZURE_FUNCTION_KEY"),
    mcp_client=None  # No MCP for now
)

# Define the main messaging endpoint
async def messages(req: Request) -> Response:
    """Handle incoming messages from Teams"""
    try:
        # Validate content type
        if "application/json" not in req.headers.get("Content-Type", ""):
            return Response(status=415, text="Unsupported Media Type")
        
        # Parse request body
        body = await req.json()
        activity = Activity().deserialize(body)
        
        # Get auth header
        auth_header = req.headers.get("Authorization", "")
        
        # Process activity
        await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        
        return Response(status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request")
        return Response(status=400, text="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing activity: {e}", exc_info=True)
        return Response(status=500, text="Internal Server Error")

# Health check endpoint
async def health(req: Request) -> Response:
    """Health check endpoint"""
    try:
        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": DEPLOYMENT_ENV,
            "services": {
                "bot": "running",
                "openai": "configured" if os.environ.get("AZURE_OPENAI_ENDPOINT") else "not configured",
                "sql_function": "configured" if os.environ.get("AZURE_FUNCTION_URL") else "not configured",
                "mcp": "disabled"
            }
        }
        
        return json_response(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json_response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=503)

# Create the application
APP = web.Application(middlewares=[aiohttp_error_middleware])

# Add routes
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)

# Startup tasks
async def on_startup(app):
    """Perform startup tasks"""
    logger.info("SQL Assistant Bot starting up...")
    logger.info(f"Environment: {DEPLOYMENT_ENV}")
    logger.info(f"Bot App ID: {os.environ.get('MICROSOFT_APP_ID', 'Not set')[:8]}...")
    logger.info("Running without MCP server")
    logger.info("SQL Assistant Bot ready!")

# Cleanup tasks
async def on_cleanup(app):
    """Perform cleanup tasks"""
    logger.info("SQL Assistant Bot shutting down...")
    CONVERSATION_STATE._storage._memory.clear()
    USER_STATE._storage._memory.clear()
    logger.info("SQL Assistant Bot shutdown complete")

# Register startup and cleanup handlers
APP.on_startup.append(on_startup)
APP.on_cleanup.append(on_cleanup)

# Main entry point
if __name__ == "__main__":
    try:
        PORT = int(os.environ.get("PORT", 3978))
        logger.info(f"Starting bot on port {PORT}")
        web.run_app(APP, host="0.0.0.0", port=PORT)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise