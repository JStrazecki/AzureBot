#!/usr/bin/env python3
# test_bot.py - Test bot for SQL Assistant

import os
import logging
import json
from datetime import datetime
from aiohttp import web
from aiohttp.web import Request, Response, json_response
import aiohttp
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
    MessageFactory,
    CardFactory
)
from botbuilder.schema import Activity, HeroCard, CardAction, ActionTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create adapter
SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MICROSOFT_APP_ID", ""),
    app_password=os.environ.get("MICROSOFT_APP_PASSWORD", "")
)

ADAPTER = BotFrameworkAdapter(SETTINGS)

# Error handler
async def on_error(context: TurnContext, error: Exception):
    logger.error(f"Error: {error}", exc_info=True)
    await context.send_activity(MessageFactory.text(f"❌ Error: {str(error)}"))

ADAPTER.on_turn_error = on_error


class TestBot:
    """Simple test bot"""
    
    async def on_turn(self, turn_context: TurnContext):
        """Handle bot messages"""
        if turn_context.activity.type == "message":
            text = turn_context.activity.text.lower().strip() if turn_context.activity.text else ""
            
            if text in ["test", "/test"]:
                await self.run_tests(turn_context)
            elif text in ["help", "/help"]:
                await self.show_help(turn_context)
            else:
                await self.show_welcome(turn_context)
    
    async def show_welcome(self, turn_context: TurnContext):
        """Show welcome message"""
        card = HeroCard(
            title="🧪 SQL Assistant Test Bot",
            subtitle="Test your connections",
            text="Type 'test' to run all tests or 'help' for more options.",
            buttons=[
                CardAction(
                    type=ActionTypes.im_back,
                    title="Run Tests",
                    value="test"
                ),
                CardAction(
                    type=ActionTypes.im_back,
                    title="Help",
                    value="help"
                )
            ]
        )
        await turn_context.send_activity(MessageFactory.attachment(CardFactory.hero_card(card)))
    
    async def show_help(self, turn_context: TurnContext):
        """Show help message"""
        help_text = """**Available Commands:**
- `test` - Run connection tests
- `help` - Show this help message

**What gets tested:**
✅ Environment variables
✅ Azure OpenAI connection
✅ Azure Function connection"""
        
        await turn_context.send_activity(MessageFactory.text(help_text))
    
    async def run_tests(self, turn_context: TurnContext):
        """Run all tests"""
        await turn_context.send_activity(MessageFactory.text("🔄 Running tests..."))
        
        # Test environment
        env_result = self._check_environment()
        await turn_context.send_activity(MessageFactory.text(env_result))
        
        # Test Azure OpenAI
        openai_result = await self._test_openai()
        await turn_context.send_activity(MessageFactory.text(openai_result))
        
        # Test Azure Function
        function_result = await self._test_function()
        await turn_context.send_activity(MessageFactory.text(function_result))
    
    def _check_environment(self) -> str:
        """Check environment variables"""
        required = {
            "MICROSOFT_APP_ID": os.environ.get("MICROSOFT_APP_ID"),
            "MICROSOFT_APP_PASSWORD": os.environ.get("MICROSOFT_APP_PASSWORD"),
            "AZURE_OPENAI_ENDPOINT": os.environ.get("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY"),
            "AZURE_FUNCTION_URL": os.environ.get("AZURE_FUNCTION_URL")
        }
        
        results = ["**🔧 Environment Check:**"]
        all_good = True
        
        for var, value in required.items():
            if value:
                masked = value[:4] + "***" if "KEY" in var or "PASSWORD" in var else value[:20] + "..."
                results.append(f"✅ {var}: {masked}")
            else:
                results.append(f"❌ {var}: NOT SET")
                all_good = False
        
        status = "✅ All configured!" if all_good else "❌ Missing variables!"
        return "\n".join(results) + f"\n\n{status}"
    
    async def _test_openai(self) -> str:
        """Test Azure OpenAI"""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        
        if not endpoint or not api_key:
            return "❌ Azure OpenAI: Missing credentials"
        
        try:
            url = f"{endpoint.rstrip('/')}/openai/deployments/gpt-4/chat/completions?api-version=2024-02-01"
            headers = {"api-key": api_key, "Content-Type": "application/json"}
            data = {
                "messages": [{"role": "user", "content": "Say 'OK'"}],
                "max_tokens": 5
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=10) as response:
                    if response.status == 200:
                        return "✅ Azure OpenAI: Connected"
                    else:
                        return f"❌ Azure OpenAI: Status {response.status}"
        except Exception as e:
            return f"❌ Azure OpenAI: {type(e).__name__}"
    
    async def _test_function(self) -> str:
        """Test Azure Function"""
        function_url = os.environ.get("AZURE_FUNCTION_URL", "")
        function_key = os.environ.get("AZURE_FUNCTION_KEY", "")
        
        if not function_url:
            return "❌ Azure Function: Missing URL"
        
        try:
            headers = {"Content-Type": "application/json"}
            if function_key:
                headers["x-functions-key"] = function_key
            
            data = {"query_type": "metadata"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(function_url, headers=headers, json=data, timeout=15) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "databases" in result:
                            return f"✅ Azure Function: Connected ({len(result['databases'])} databases)"
                        return "✅ Azure Function: Connected"
                    else:
                        return f"❌ Azure Function: Status {response.status}"
        except Exception as e:
            return f"❌ Azure Function: {type(e).__name__}"


# Create bot
BOT = TestBot()

# Message handler
async def messages(req: Request) -> Response:
    """Handle messages"""
    try:
        body = await req.json()
        activity = Activity().deserialize(body)
        auth_header = req.headers.get("Authorization", "")
        
        await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        return Response(status=200)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return Response(status=500)

# Health endpoint
async def health(req: Request) -> Response:
    """Health check"""
    return json_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    })

# Create app
APP = web.Application()
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)

# Startup
async def on_startup(app):
    logger.info("Test bot starting...")
    logger.info(f"App ID: {'Configured' if os.environ.get('MICROSOFT_APP_ID') else 'Not configured'}")

APP.on_startup.append(on_startup)

# For local testing
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting on port {PORT}")
    web.run_app(APP, host="0.0.0.0", port=PORT)