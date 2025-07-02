#!/usr/bin/env python3
# app.py - Main application entry point for SQL Assistant Teams Bot
"""
Main application entry point for SQL Assistant Teams Bot
Enhanced with MCP integration and performance monitoring
"""

import os
import logging
import asyncio
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

# Import our custom modules - FIXED: removed 'good.' prefix
from teams_sql_bot import SQLAssistantBot, EnhancedMCPClient
from azure_openai_sql_translator import AzureOpenAISQLTranslator
from autonomous_sql_explorer import AutonomousSQLExplorer

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

# Create adapter with enhanced error handling
SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MICROSOFT_APP_ID", ""),
    app_password=os.environ.get("MICROSOFT_APP_PASSWORD", "")
)

ADAPTER = BotFrameworkAdapter(SETTINGS)

# Enhanced error handler
async def on_error(context: TurnContext, error: Exception):
    """Handle errors in the bot"""
    logger.error(f"Error in bot: {error}", exc_info=True)
    
    # Send error message to user
    error_message = "Sorry, an error occurred while processing your request."
    
    if isinstance(error, ErrorResponseException):
        error_message += f"\n\nError details: {error.message}"
    elif DEPLOYMENT_ENV == "development":
        # Show more details in development
        error_message += f"\n\nDebug info: {type(error).__name__}: {str(error)}"
    
    try:
        await context.send_activity(MessageFactory.text(error_message))
        
        # Send a trace activity for debugging
        if DEPLOYMENT_ENV == "development":
            trace_activity = MessageFactory.trace(
                "BotError",
                {
                    "error_type": error.__class__.__name__,
                    "error_message": str(error),
                    "timestamp": datetime.now().isoformat()
                },
                label="Error"
            )
            await context.send_activity(trace_activity)
        
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

# Initialize MCP client (optional but recommended)
MCP_CLIENT = None
if os.environ.get("MCP_SERVER_URL"):
    try:
        MCP_CLIENT = EnhancedMCPClient(os.environ.get("MCP_SERVER_URL"))
        logger.info("MCP client initialized")
    except Exception as e:
        logger.warning(f"MCP client not available: {e}")
        logger.warning("Bot will run without MCP features (pattern learning, caching)")

# Performance tracking
class PerformanceTracker:
    """Track application performance metrics"""
    def __init__(self):
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0
        self.message_count = 0
        self.query_count = 0
        self.pattern_hits = 0
        
    def record_request(self):
        self.request_count += 1
        
    def record_error(self):
        self.error_count += 1
        
    def record_message(self):
        self.message_count += 1
        
    def record_query(self, used_pattern: bool = False):
        self.query_count += 1
        if used_pattern:
            self.pattern_hits += 1
    
    def get_stats(self):
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "uptime_seconds": uptime,
            "uptime_hours": uptime / 3600,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "message_count": self.message_count,
            "query_count": self.query_count,
            "pattern_hits": self.pattern_hits,
            "pattern_hit_rate": (self.pattern_hits / self.query_count * 100) if self.query_count > 0 else 0,
            "error_rate": (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        }

# Initialize performance tracker
PERF_TRACKER = PerformanceTracker()

# Create the bot
BOT = SQLAssistantBot(
    conversation_state=CONVERSATION_STATE,
    user_state=USER_STATE,
    sql_translator=SQL_TRANSLATOR,
    function_url=os.environ.get("AZURE_FUNCTION_URL"),
    function_key=os.environ.get("AZURE_FUNCTION_KEY"),
    mcp_client=MCP_CLIENT
)

# Define the main messaging endpoint
async def messages(req: Request) -> Response:
    """Handle incoming messages from Teams"""
    PERF_TRACKER.record_request()
    
    try:
        # Validate content type
        if "application/json" not in req.headers.get("Content-Type", ""):
            PERF_TRACKER.record_error()
            return Response(status=415, text="Unsupported Media Type")
        
        # Parse request body
        body = await req.json()
        activity = Activity().deserialize(body)
        
        # Track message
        if activity.type == "message":
            PERF_TRACKER.record_message()
        
        # Get auth header
        auth_header = req.headers.get("Authorization", "")
        
        # Process activity
        await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        
        return Response(status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request")
        PERF_TRACKER.record_error()
        return Response(status=400, text="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing activity: {e}", exc_info=True)
        PERF_TRACKER.record_error()
        return Response(status=500, text="Internal Server Error")

# Health check endpoint with detailed status
async def health(req: Request) -> Response:
    """Health check endpoint with detailed status"""
    try:
        health_status = {
            "status": "healthy",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": DEPLOYMENT_ENV,
            "services": {
                "bot": "running",
                "openai": "configured" if os.environ.get("AZURE_OPENAI_ENDPOINT") else "not configured",
                "sql_function": "configured" if os.environ.get("AZURE_FUNCTION_URL") else "not configured",
                "mcp": "configured" if MCP_CLIENT else "not configured",
                "mcp_connected": MCP_CLIENT.connected if MCP_CLIENT else False,
                "memory_state": "active",
                "conversation_state": "active"
            },
            "features": {
                "autonomous_mode": os.environ.get("ENABLE_AUTONOMOUS_MODE", "true") == "true",
                "pattern_learning": MCP_CLIENT is not None,
                "explanation_mode": os.environ.get("ENABLE_EXPLANATION_MODE", "true") == "true",
                "export": os.environ.get("ENABLE_EXPORT", "true") == "true",
                "tiered_caching": MCP_CLIENT is not None
            },
            "performance": PERF_TRACKER.get_stats()
        }
        
        # Test Azure Function connectivity if configured
        if os.environ.get("AZURE_FUNCTION_URL"):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        os.environ.get("AZURE_FUNCTION_URL").replace("/query", "/health"),
                        headers={"x-functions-key": os.environ.get("AZURE_FUNCTION_KEY")},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        health_status["services"]["sql_function_reachable"] = response.status == 200
            except:
                health_status["services"]["sql_function_reachable"] = False
        
        # Test MCP connectivity if configured
        if MCP_CLIENT and MCP_CLIENT.connected:
            try:
                cache_stats = await MCP_CLIENT.get_cache_statistics()
                health_status["services"]["mcp_responsive"] = True
                health_status["mcp_stats"] = {
                    "cache_hit_rate": cache_stats.get("cache", {}).get("hit_rate", 0),
                    "pattern_count": cache_stats.get("pattern_stats", {}).get("total_patterns", 0)
                }
            except:
                health_status["services"]["mcp_responsive"] = False
        
        return json_response(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json_response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=503)

# Metrics endpoint for monitoring
async def metrics(req: Request) -> Response:
    """Metrics endpoint for monitoring (Prometheus format)"""
    try:
        stats = PERF_TRACKER.get_stats()
        
        # Format metrics in Prometheus format
        metrics_text = f"""# HELP sqlbot_uptime_seconds Time since bot started
# TYPE sqlbot_uptime_seconds counter
sqlbot_uptime_seconds {stats['uptime_seconds']}

# HELP sqlbot_requests_total Total number of requests
# TYPE sqlbot_requests_total counter
sqlbot_requests_total {stats['request_count']}

# HELP sqlbot_errors_total Total number of errors
# TYPE sqlbot_errors_total counter
sqlbot_errors_total {stats['error_count']}

# HELP sqlbot_messages_total Total number of messages processed
# TYPE sqlbot_messages_total counter
sqlbot_messages_total {stats['message_count']}

# HELP sqlbot_queries_total Total number of SQL queries executed
# TYPE sqlbot_queries_total counter
sqlbot_queries_total {stats['query_count']}

# HELP sqlbot_pattern_hits_total Total number of pattern cache hits
# TYPE sqlbot_pattern_hits_total counter
sqlbot_pattern_hits_total {stats['pattern_hits']}

# HELP sqlbot_pattern_hit_rate Pattern cache hit rate percentage
# TYPE sqlbot_pattern_hit_rate gauge
sqlbot_pattern_hit_rate {stats['pattern_hit_rate']}

# HELP sqlbot_error_rate Error rate percentage
# TYPE sqlbot_error_rate gauge
sqlbot_error_rate {stats['error_rate']}

# HELP sqlbot_conversations_active Active conversations
# TYPE sqlbot_conversations_active gauge
sqlbot_conversations_active {len(CONVERSATION_STATE._storage._memory)}

# HELP sqlbot_users_active Active users
# TYPE sqlbot_users_active gauge
sqlbot_users_active {len(USER_STATE._storage._memory)}
"""
        
        return Response(text=metrics_text, content_type="text/plain")
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return Response(status=500, text=f"Error generating metrics: {str(e)}")

# Ready check endpoint for Kubernetes
async def ready(req: Request) -> Response:
    """Readiness probe endpoint"""
    # Check if all services are ready
    ready_checks = {
        "bot": True,
        "openai": bool(SQL_TRANSLATOR),
        "function": bool(os.environ.get("AZURE_FUNCTION_URL")),
        "mcp": MCP_CLIENT.connected if MCP_CLIENT else True  # Optional service
    }
    
    if all(ready_checks.values()):
        return json_response({"ready": True, "checks": ready_checks})
    else:
        return json_response({"ready": False, "checks": ready_checks}, status=503)

# Live check endpoint for Kubernetes
async def live(req: Request) -> Response:
    """Liveness probe endpoint"""
    return json_response({"alive": True, "timestamp": datetime.now().isoformat()})

# Create the application
APP = web.Application(middlewares=[aiohttp_error_middleware])

# Add routes
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)
APP.router.add_get("/health/ready", ready)
APP.router.add_get("/health/live", live)
APP.router.add_get("/metrics", metrics)

# Startup tasks
async def on_startup(app):
    """Perform startup tasks"""
    logger.info("SQL Assistant Bot starting up...")
    logger.info(f"Environment: {DEPLOYMENT_ENV}")
    logger.info(f"Bot App ID: {os.environ.get('MICROSOFT_APP_ID', 'Not set')[:8]}...")
    logger.info(f"Features enabled:")
    logger.info(f"  - Autonomous Mode: {os.environ.get('ENABLE_AUTONOMOUS_MODE', 'true')}")
    logger.info(f"  - Pattern Learning: {MCP_CLIENT is not None}")
    logger.info(f"  - Explanation Mode: {os.environ.get('ENABLE_EXPLANATION_MODE', 'true')}")
    logger.info(f"  - Export: {os.environ.get('ENABLE_EXPORT', 'true')}")
    
    # Initialize MCP connection if available
    if MCP_CLIENT:
        try:
            await MCP_CLIENT.connect()
            if MCP_CLIENT.connected:
                logger.info("✅ Connected to MCP server")
                
                # Log initial cache stats
                try:
                    stats = await MCP_CLIENT.get_cache_statistics()
                    logger.info(f"MCP Cache Stats: Hit rate {stats.get('cache', {}).get('hit_rate', 0):.1f}%")
                    logger.info(f"MCP Patterns: {stats.get('pattern_stats', {}).get('total_patterns', 0)} patterns learned")
                except:
                    pass
            else:
                logger.warning("⚠️  MCP server not responding - running without pattern learning")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            logger.warning("Bot will run without MCP features")
    
    # Create cache directories
    from pathlib import Path
    cache_dirs = [
        Path(os.environ.get("PATTERN_CACHE_DIR", ".pattern_cache")),
        Path(os.environ.get("EXPORT_DIR", ".exploration_exports")),
        Path(os.environ.get("QUERY_LOG_DIR", ".query_logs"))
    ]
    
    for cache_dir in cache_dirs:
        cache_dir.mkdir(exist_ok=True)
        logger.info(f"Created cache directory: {cache_dir}")
    
    logger.info("SQL Assistant Bot ready!")
    logger.info(f"Listening on port {os.environ.get('PORT', 3978)}")

# Cleanup tasks
async def on_cleanup(app):
    """Perform cleanup tasks"""
    logger.info("SQL Assistant Bot shutting down...")
    
    # Log final statistics
    final_stats = PERF_TRACKER.get_stats()
    logger.info(f"Final statistics:")
    logger.info(f"  - Total requests: {final_stats['request_count']}")
    logger.info(f"  - Total queries: {final_stats['query_count']}")
    logger.info(f"  - Pattern hit rate: {final_stats['pattern_hit_rate']:.1f}%")
    logger.info(f"  - Error rate: {final_stats['error_rate']:.1f}%")
    logger.info(f"  - Uptime: {final_stats['uptime_hours']:.1f} hours")
    
    # Close MCP connection if available
    if MCP_CLIENT:
        try:
            await MCP_CLIENT.close()
            logger.info("Closed MCP connection")
        except Exception as e:
            logger.error(f"Error closing MCP connection: {e}")
    
    # Clear state
    CONVERSATION_STATE._storage._memory.clear()
    USER_STATE._storage._memory.clear()
    
    logger.info("SQL Assistant Bot shutdown complete")

# Register startup and cleanup handlers
APP.on_startup.append(on_startup)
APP.on_cleanup.append(on_cleanup)

# Main entry point
if __name__ == "__main__":
    try:
        # Get port from environment or default
        PORT = int(os.environ.get("PORT", 3978))
        
        logger.info(f"Starting bot on port {PORT}")
        
        # Run the app
        web.run_app(
            APP,
            host="0.0.0.0",
            port=PORT,
            access_log_format='%a %t "%r" %s %b "%{Referer}i" "%{User-Agent}i" %Tf'
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise