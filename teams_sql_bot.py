# sql-assistant/bot/teams_sql_bot.py
"""
Enhanced Teams SQL Assistant Bot with MCP Pattern Integration
Complete integration with centralized pattern learning and token limiting
"""

import os
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp
from botbuilder.core import TurnContext, ActivityHandler, MessageFactory, CardFactory
from botbuilder.schema import (
    Activity, ChannelAccount, HeroCard, CardAction, ActionTypes, 
    CardImage, Attachment, SuggestedActions, CardAction
)
from botbuilder.core.conversation_state import ConversationState
from botbuilder.core.user_state import UserState
from dataclasses import dataclass, asdict

# Import our custom modules
from azure_openai_sql_translator import AzureOpenAISQLTranslator, ConversationContext, SQLQuery
from autonomous_sql_explorer import AutonomousSQLExplorer
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class QueryExecution:
    """Tracks a query execution with enhanced metadata"""
    query: SQLQuery
    started_at: datetime
    completed_at: Optional[datetime] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    row_count: Optional[int] = None
    used_pattern: bool = False
    pattern_id: Optional[str] = None


class EnhancedMCPClient:
    """Enhanced MCP client wrapper with proper tool calling"""
    
    def __init__(self, url: str):
        self.url = url
        self.session = None
        self.connected = False
        
    async def connect(self):
        """Connect to MCP server"""
        import aiohttp
        self.session = aiohttp.ClientSession()
        
        # Test connection
        try:
            async with self.session.get(f"{self.url}/health") as response:
                if response.status == 200:
                    self.connected = True
                    logger.info(f"Connected to MCP server at {self.url}")
                else:
                    logger.error(f"MCP server returned status {response.status}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            self.connected = False
            
    async def close(self):
        """Close MCP connection"""
        if self.session:
            await self.session.close()
            self.connected = False
            
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call an MCP tool with parameters"""
        if not self.connected:
            logger.warning("MCP client not connected")
            return {"error": "Not connected"}
            
        try:
            # MCP tool calling format
            payload = {
                "jsonrpc": "2.0",
                "method": "tools.call",
                "params": {
                    "name": tool_name,
                    "arguments": kwargs
                },
                "id": 1
            }
            
            async with self.session.post(
                f"{self.url}/rpc",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    # Extract result from JSON-RPC response
                    if "result" in result:
                        return result["result"]
                    elif "error" in result:
                        logger.error(f"MCP tool error: {result['error']}")
                        return {"error": result["error"]["message"]}
                else:
                    return {"error": f"Status {response.status}"}
                    
        except asyncio.TimeoutError:
            logger.error(f"MCP tool call timeout: {tool_name}")
            return {"error": "Timeout"}
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"error": str(e)}
    
    async def get_database_context(self, database: str = None) -> Optional[Dict[str, Any]]:
        """Get database context from MCP"""
        return await self.call_tool("get_database_context", database=database)
    
    async def find_pattern(self, question: str, database: str, 
                          schema_hash: str) -> Dict[str, Any]:
        """Find matching patterns"""
        return await self.call_tool(
            "find_pattern",
            question=question,
            database=database,
            schema_hash=schema_hash
        )
    
    async def learn_pattern(self, **kwargs) -> Dict[str, Any]:
        """Learn a new pattern"""
        return await self.call_tool("learn_pattern", **kwargs)
    
    async def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get pattern statistics"""
        return await self.call_tool("get_pattern_statistics")
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return await self.call_tool("get_cache_statistics")
    
    async def refresh_all_metadata(self) -> Dict[str, Any]:
        """Refresh all metadata"""
        return await self.call_tool("refresh_all_metadata")


class SQLAssistantBot(ActivityHandler):
    """Enhanced Teams bot for SQL query assistance with MCP integration"""
    
    def __init__(self, 
                 conversation_state: ConversationState,
                 user_state: UserState,
                 sql_translator: AzureOpenAISQLTranslator,
                 function_url: str,
                 function_key: str,
                 mcp_client: Any = None):
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.sql_translator = sql_translator
        self.function_url = function_url
        self.function_key = function_key
        self.mcp_client = mcp_client
        
        # Create accessors
        self.conversation_data_accessor = self.conversation_state.create_property("ConversationData")
        self.user_profile_accessor = self.user_state.create_property("UserProfile")
        
        # Initialize autonomous explorer
        self.autonomous_explorer = AutonomousSQLExplorer(
            sql_translator=self.sql_translator,
            query_executor=self
        )
        
        # Set MCP client in explorer if available
        if self.mcp_client:
            self.autonomous_explorer.set_mcp_client(self.mcp_client)
        
        # Command handlers
        self.commands = {
            "/help": self._handle_help_command,
            "/database": self._handle_database_command,
            "/tables": self._handle_tables_command,
            "/history": self._handle_history_command,
            "/clear": self._handle_clear_command,
            "/preferences": self._handle_preferences_command,
            "/refresh": self._handle_refresh_command,
            "/explore": self._handle_explore_command,
            "/explain": self._handle_explain_command,
            "/export": self._handle_export_command,
            "/validate": self._handle_validate_command,
            "/patterns": self._handle_patterns_command,
            "/stats": self._handle_stats_command,
            "/cache": self._handle_cache_command,
            "/usage": self._handle_usage_command  # NEW: Token usage command
        }
    
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle incoming messages"""
        try:
            # Get conversation data
            conversation_data = await self.conversation_data_accessor.get(
                turn_context, 
                lambda: {"context": ConversationContext(messages=[]), "executions": []}
            )
            
            # Get user profile
            user_profile = await self.user_profile_accessor.get(
                turn_context,
                lambda: {"preferences": {"row_limit": 100, "output_format": "natural_language"}}
            )
            
            text = turn_context.activity.text.strip()
            
            # Check for commands
            if text.startswith("/"):
                command = text.split()[0].lower()
                if command in self.commands:
                    await self.commands[command](turn_context, conversation_data, user_profile)
                else:
                    await turn_context.send_activity(
                        MessageFactory.text(f"Unknown command: {command}. Type /help for available commands.")
                    )
            else:
                # Process as natural language query
                await self._process_natural_language_query(turn_context, text, conversation_data, user_profile)
            
            # Save state
            await self.conversation_state.save_changes(turn_context)
            await self.user_state.save_changes(turn_context)
            
        except Exception as e:
            logger.error(f"Error in on_message_activity: {e}", exc_info=True)
            await turn_context.send_activity(
                MessageFactory.text("Sorry, I encountered an error processing your request. Please try again.")
            )
    
    async def on_members_added_activity(self, members_added: List[ChannelAccount], 
                                       turn_context: TurnContext) -> None:
        """Welcome new members"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
    
    async def _send_welcome_message(self, turn_context: TurnContext) -> None:
        """Send welcome message with capabilities"""
        welcome_card = self._create_welcome_card()
        await turn_context.send_activity(MessageFactory.attachment(welcome_card))
    
    def _create_welcome_card(self) -> Attachment:
        """Create welcome card"""
        card = HeroCard(
            title="Welcome to SQL Assistant Bot! 🤖",
            subtitle="I can help you query your databases using natural language",
            text="""I understand questions like:
- "How many orders do we have this month?"
- "Show me top 10 customers by revenue"
- "What's the average order value by country?"
- "List all tables in the Sales database"

**NEW:** I now learn from your queries to provide faster responses!

Type /help to see all available commands.""",
            images=[CardImage(url="https://aka.ms/bf-welcome-card-image")],
            buttons=[
                CardAction(
                    type=ActionTypes.im_back,
                    title="Get Started",
                    value="/help"
                ),
                CardAction(
                    type=ActionTypes.im_back,
                    title="View Stats",
                    value="/stats"
                ),
                CardAction(
                    type=ActionTypes.im_back,
                    title="Check Usage",
                    value="/usage"
                )
            ]
        )
        return CardFactory.hero_card(card)
    
    async def _process_natural_language_query(self, turn_context: TurnContext, 
                                            query: str, 
                                            conversation_data: Dict,
                                            user_profile: Dict) -> None:
        """Process natural language query with MCP pattern checking"""
        # Send typing indicator
        await turn_context.send_activity(Activity(type="typing"))
        
        context = conversation_data["context"]
        
        # Check for MCP patterns first
        pattern_found = False
        if self.mcp_client and context.current_database:
            try:
                # Get schema hash from MCP
                db_context = await self.mcp_client.get_database_context(context.current_database)
                schema_hash = db_context.get("schema_hash", "") if db_context else ""
                
                if schema_hash:
                    # Check for patterns
                    pattern_result = await self.mcp_client.find_pattern(
                        query, context.current_database, schema_hash
                    )
                    
                    if pattern_result.get("found") and pattern_result.get("best_match"):
                        pattern = pattern_result["best_match"]
                        pattern_found = True
                        
                        # Show pattern match card
                        pattern_card = self._create_pattern_match_card(pattern)
                        await turn_context.send_activity(MessageFactory.attachment(pattern_card))
                        
                        # Ask if user wants to use the pattern
                        await turn_context.send_activity(
                            MessageFactory.suggested_actions(
                                SuggestedActions(
                                    suggestions=[
                                        CardAction(
                                            type=ActionTypes.im_back,
                                            title="Use Pattern",
                                            value=f"/use_pattern {pattern.get('pattern_id', '')}"
                                        ),
                                        CardAction(
                                            type=ActionTypes.im_back,
                                            title="New Query",
                                            value="/new_query"
                                        )
                                    ]
                                ),
                                f"Found similar pattern with {pattern['confidence']:.0%} confidence. Use it?"
                            )
                        )
                        
                        # Store pattern info for potential use
                        conversation_data["pending_pattern"] = pattern
                        return
                        
            except Exception as e:
                logger.warning(f"Failed to check MCP patterns: {e}")
        
        # Get schema hint from MCP if available
        schema_hint = None
        if self.mcp_client and context.current_database:
            try:
                schema_hint = await self.mcp_client.get_database_context(context.current_database)
            except Exception as e:
                logger.warning(f"Failed to get schema hint: {e}")
        
        # Translate to SQL
        sql_query = self.sql_translator.translate_to_sql(query, context, schema_hint)
        
        # Check if translation was successful
        if not sql_query.query:
            await turn_context.send_activity(
                MessageFactory.text(sql_query.explanation or "I couldn't translate that to a SQL query. Could you rephrase?")
            )
            return
        
        # Show query card with explanation
        query_card = self._create_query_card(sql_query)
        await turn_context.send_activity(MessageFactory.attachment(query_card))
        
        # Execute query
        execution = QueryExecution(
            query=sql_query,
            started_at=datetime.now()
        )
        
        try:
            # Execute with preferred output format
            result = await self._execute_sql_query(
                sql_query, 
                user_profile["preferences"]["output_format"]
            )
            
            execution.completed_at = datetime.now()
            execution.results = result
            execution.execution_time_ms = result.get("execution_time_ms", 0)
            execution.row_count = result.get("row_count", 0)
            
            # Send results
            if result.get("error"):
                await turn_context.send_activity(
                    MessageFactory.text(f"❌ Error executing query: {result['error']}")
                )
            else:
                await self._send_query_results(turn_context, result, sql_query, user_profile)
                
                # Handle follow-up queries if needed
                if sql_query.requires_followup and sql_query.followup_queries:
                    await self._handle_followup_queries(
                        turn_context, sql_query, conversation_data, user_profile
                    )
            
        except Exception as e:
            logger.error(f"Error executing query: {e}", exc_info=True)
            execution.error = str(e)
            execution.completed_at = datetime.now()
            
            await turn_context.send_activity(
                MessageFactory.text(f"❌ Error executing query: {str(e)}")
            )
        
        # Track execution
        conversation_data["executions"].append(asdict(execution))
    
    async def _process_autonomous_query(self, turn_context: TurnContext, 
                                       query: str, 
                                       conversation_data: Dict,
                                       user_profile: Dict,
                                       enable_explanation: bool = False) -> None:
        """Process query in autonomous exploration mode"""
        context = conversation_data["context"]
        
        # Check if database is set
        if not context.current_database:
            await turn_context.send_activity(
                MessageFactory.text("Please set a database first using `/database set <name>`")
            )
            return
        
        # Send initial message
        mode_text = "with detailed explanation" if enable_explanation else ""
        await turn_context.send_activity(
            MessageFactory.text(f"🤖 Starting autonomous exploration {mode_text}. I'll analyze your question and run multiple queries to find the complete answer...")
        )
        
        # Show typing indicator
        await turn_context.send_activity(Activity(type="typing"))
        
        try:
            # Start autonomous exploration
            result = await self.autonomous_explorer.explore_and_answer(
                user_question=query,
                database=context.current_database,
                enable_learning=True,
                enable_explanation=enable_explanation,
                export_session=True
            )
            
            # Create detailed response card
            exploration_card = self._create_exploration_results_card(result)
            await turn_context.send_activity(MessageFactory.attachment(exploration_card))
            
            # Send the final answer
            confidence_emoji = "🟢" if result["confidence"] > 0.8 else "🟡" if result["confidence"] > 0.5 else "🔴"
            pattern_emoji = "♻️" if result.get("using_mcp_pattern") else "🆕"
            
            answer_text = f"""**Answer {confidence_emoji} {pattern_emoji}**

{result['answer']}

*Confidence: {result['confidence']:.0%}*
*Method: {'MCP Pattern Reuse' if result.get('using_mcp_pattern') else 'Fresh Exploration'}*
*Queries executed: {result['queries_executed']}*
*Iterations: {result['iterations_used']}*"""
            
            await turn_context.send_activity(MessageFactory.text(answer_text))
            
            # If explanation enabled, show reasoning
            if enable_explanation and "explanation_summary" in result:
                explanation_card = self._create_explanation_card(result["explanation_summary"])
                await turn_context.send_activity(MessageFactory.attachment(explanation_card))
            
            # Show query history if user wants details
            if result['queries_executed'] > 1:
                await turn_context.send_activity(
                    MessageFactory.suggested_actions(
                        SuggestedActions(
                            suggestions=[
                                CardAction(
                                    type=ActionTypes.im_back,
                                    title="Show query details",
                                    value="/show_exploration_details"
                                ),
                                CardAction(
                                    type=ActionTypes.im_back,
                                    title="Export results",
                                    value="/export"
                                )
                            ]
                        ),
                        "Would you like to see the exploration details?"
                    )
                )
            
            # Store exploration results in context
            conversation_data["last_exploration"] = result
            
        except Exception as e:
            logger.error(f"Error in autonomous exploration: {e}", exc_info=True)
            await turn_context.send_activity(
                MessageFactory.text(f"❌ Error during exploration: {str(e)}")
            )
    
    async def _execute_sql_query(self, sql_query: SQLQuery, output_format: str = "natural_language") -> Dict[str, Any]:
        """Execute SQL query via Azure Function"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "x-functions-key": self.function_key
            }
            
            # Determine query type
            query_type = "single"
            if sql_query.database == "multi":
                query_type = "multi_database"
            elif "information_schema" in sql_query.query.lower():
                query_type = "schema"
            
            payload = {
                "query_type": query_type,
                "query": sql_query.query,
                "database": sql_query.database if sql_query.database != "multi" else None,
                "output_format": output_format
            }
            
            async with session.post(self.function_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Function returned status {response.status}"}
    
    async def _send_query_results(self, turn_context: TurnContext, 
                                result: Dict[str, Any], 
                                sql_query: SQLQuery,
                                user_profile: Dict) -> None:
        """Send query results in appropriate format"""
        output_format = user_profile["preferences"]["output_format"]
        
        if output_format == "natural_language":
            # Use natural language response
            message = result.get("message", "Query completed successfully.")
            insights = result.get("insights", [])
            
            # Create rich response
            response_text = message
            if insights:
                response_text += "\n\n**Insights:**"
                for insight in insights[:3]:
                    response_text += f"\n• {insight}"
            
            await turn_context.send_activity(MessageFactory.text(response_text))
            
        elif output_format == "summary":
            # Use summary format
            summary = result.get("summary", "")
            structured_data = result.get("structured_data", {})
            
            # Create summary card
            card = self._create_summary_card(summary, structured_data, result.get("metadata", {}))
            await turn_context.send_activity(MessageFactory.attachment(card))
            
        else:
            # Full format - show everything
            if "formatted_result" in result and result["formatted_result"]:
                formatted = result["formatted_result"]
                
                # Send natural language description
                await turn_context.send_activity(
                    MessageFactory.text(formatted.get("natural_language", "Query completed."))
                )
                
                # If table format available and small enough, show it
                if "formatted_table" in formatted:
                    table_text = f"```\n{formatted['formatted_table']}\n```"
                    await turn_context.send_activity(MessageFactory.text(table_text))
                
                # Show insights if any
                if formatted.get("insights"):
                    insights_text = "**Insights:**\n" + "\n".join(
                        f"• {insight}" for insight in formatted["insights"]
                    )
                    await turn_context.send_activity(MessageFactory.text(insights_text))
            else:
                # Fallback to row count
                row_count = result.get("row_count", 0)
                await turn_context.send_activity(
                    MessageFactory.text(f"Query returned {row_count} rows.")
                )
        
        # Add suggested actions based on results
        suggestions = self._generate_suggestions(sql_query, result)
        if suggestions:
            await turn_context.send_activity(
                MessageFactory.suggested_actions(
                    suggestions,
                    "What would you like to do next?"
                )
            )
    
    def _create_pattern_match_card(self, pattern: Dict[str, Any]) -> Attachment:
        """Create card showing pattern match details"""
        card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "♻️ Found Similar Pattern",
                        "weight": "bolder",
                        "size": "large"
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Pattern: {pattern.get('template', 'Unknown')}",
                        "wrap": True,
                        "isSubtle": True
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {
                                "title": "Confidence",
                                "value": f"{pattern.get('confidence', 0):.0%}"
                            },
                            {
                                "title": "Used",
                                "value": f"{pattern.get('use_count', 0)} times"
                            },
                            {
                                "title": "Avg Time",
                                "value": f"{pattern.get('avg_execution_time', 0):.0f}ms"
                            },
                            {
                                "title": "Tables",
                                "value": ", ".join(pattern.get('discovered_tables', [])[:3])
                            }
                        ]
                    }
                ]
            }
        }
        return card
    
    def _create_query_card(self, sql_query: SQLQuery) -> Attachment:
        """Create card showing query details"""
        confidence_emoji = "🟢" if sql_query.confidence > 0.8 else "🟡" if sql_query.confidence > 0.5 else "🔴"
        
        card = HeroCard(
            title=f"SQL Query {confidence_emoji}",
            subtitle=f"Database: {sql_query.database or 'Not specified'}",
            text=f"**Explanation:** {sql_query.explanation}\n\n**Query:**\n```sql\n{sql_query.query}\n```",
            buttons=[
                CardAction(
                    type=ActionTypes.im_back,
                    title="Execute Similar",
                    value=f"Run a similar query"
                )
            ]
        )
        
        return CardFactory.hero_card(card)
    
    def _create_summary_card(self, summary: str, data: Dict, metadata: Dict) -> Attachment:
        """Create summary card for results"""
        facts = []
        
        if metadata.get("row_count"):
            facts.append({"title": "Rows", "value": str(metadata["row_count"])})
        if metadata.get("execution_time_ms"):
            facts.append({"title": "Time", "value": f"{metadata['execution_time_ms']}ms"})
        if metadata.get("database"):
            facts.append({"title": "Database", "value": metadata["database"]})
        
        card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "Query Results",
                        "weight": "bolder",
                        "size": "medium"
                    },
                    {
                        "type": "TextBlock",
                        "text": summary,
                        "wrap": True
                    },
                    {
                        "type": "FactSet",
                        "facts": facts
                    }
                ]
            }
        }
        
        return card
    
    def _create_exploration_results_card(self, result: Dict[str, Any]) -> Attachment:
        """Create a card showing exploration results"""
        # Create facts for the card
        facts = []
        
        # Add discovered tables
        if result.get("discovered_schema"):
            tables = list(result["discovered_schema"].keys())
            facts.append({
                "title": "Tables Explored",
                "value": ", ".join(tables[:3]) + (f" +{len(tables)-3} more" if len(tables) > 3 else "")
            })
        
        # Add pattern usage
        if result.get("using_mcp_pattern"):
            facts.append({
                "title": "Method",
                "value": "Pattern Reuse"
            })
        
        # Add query history summary
        query_purposes = []
        for q in result.get("query_history", [])[:3]:
            purpose = q.get("purpose", "Data exploration")
            rows = q.get("row_count", 0)
            query_purposes.append(f"• {purpose} ({rows} rows)")
        
        card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "🔍 Autonomous Exploration Complete",
                                "weight": "bolder",
                                "size": "large",
                                "wrap": True
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Executed {result['queries_executed']} queries in {result['iterations_used']} iterations",
                                "isSubtle": True,
                                "wrap": True
                            }
                        ]
                    },
                    {
                        "type": "FactSet",
                        "facts": facts
                    },
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Query Progression:",
                                "weight": "bolder",
                                "size": "medium"
                            },
                            {
                                "type": "TextBlock",
                                "text": "\n".join(query_purposes),
                                "wrap": True,
                                "isSubtle": True
                            }
                        ]
                    }
                ],
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "View Full Details",
                        "data": {
                            "action": "show_exploration_details"
                        }
                    }
                ]
            }
        }
        
        return card
    
    def _create_explanation_card(self, explanation_summary: Dict[str, Any]) -> Attachment:
        """Create detailed explanation card"""
        decisions = []
        
        # Extract key decisions
        for iteration in explanation_summary.get("detailed_reasoning", [])[:3]:
            for decision in iteration.get("decisions", [])[:2]:
                decisions.append({
                    "iteration": iteration["iteration"],
                    "type": decision["type"],
                    "reasoning": decision["reasoning"]
                })
        
        card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "🧠 Exploration Reasoning",
                        "weight": "bolder",
                        "size": "large"
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Total iterations: {explanation_summary['total_iterations']} | Decisions made: {explanation_summary['decision_count']}",
                        "isSubtle": True,
                        "wrap": True
                    },
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "**Key Decision Points:**",
                                "weight": "bolder"
                            }
                        ] + [
                            {
                                "type": "Container",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"**Iteration {d['iteration']} - {d['type']}**",
                                        "weight": "bolder",
                                        "size": "small"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": d["reasoning"],
                                        "wrap": True,
                                        "isSubtle": True
                                    }
                                ],
                                "separator": True
                            } for d in decisions
                        ]
                    }
                ] + ([{
                    "type": "Container",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Key Insights:**",
                            "weight": "bolder"
                        },
                        {
                            "type": "TextBlock",
                            "text": "\n".join(f"• {insight}" for insight in explanation_summary.get("key_insights", [])),
                            "wrap": True
                        }
                    ],
                    "separator": True
                }] if explanation_summary.get("key_insights") else [])
            }
        }
        
        return card
    
    def _generate_suggestions(self, sql_query: SQLQuery, result: Dict) -> SuggestedActions:
        """Generate suggested follow-up actions"""
        suggestions = []
        
        # Add follow-up queries if any
        if sql_query.followup_queries:
            for i, followup in enumerate(sql_query.followup_queries[:2]):
                suggestions.append(
                    CardAction(
                        type=ActionTypes.im_back,
                        title=f"Follow-up {i+1}",
                        value=followup
                    )
                )
        
        # Add drill-down options based on result type
        if result.get("structured_data", {}).get("type") == "table":
            suggestions.append(
                CardAction(
                    type=ActionTypes.im_back,
                    title="Show details",
                    value="Show me more details about these results"
                )
            )
        
        # Add explore option
        suggestions.append(
            CardAction(
                type=ActionTypes.im_back,
                title="Deep explore",
                value="/explore"
            )
        )
        
        return SuggestedActions(suggestions=suggestions) if suggestions else None
    
    async def _handle_followup_queries(self, turn_context: TurnContext,
                                     initial_query: SQLQuery,
                                     conversation_data: Dict,
                                     user_profile: Dict) -> None:
        """Handle multi-step queries"""
        await turn_context.send_activity(
            MessageFactory.text("This requires multiple steps. Let me work through them...")
        )
        
        for i, followup in enumerate(initial_query.followup_queries[:3]):  # Limit to 3 follow-ups
            await turn_context.send_activity(
                MessageFactory.text(f"Step {i+2}: {followup}")
            )
            
            # Process each follow-up
            await self._process_natural_language_query(
                turn_context, followup, conversation_data, user_profile
            )
    
    # Command handlers
    async def _handle_help_command(self, turn_context: TurnContext, 
                                 conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /help command"""
        help_text = """**Available Commands:**
        
- `/help` - Show this help message
- `/database [list|set <name>]` - List databases or set current database
- `/tables [pattern]` - List tables in current database
- `/history` - Show recent queries
- `/clear` - Clear conversation history
- `/preferences` - Manage your preferences
- `/refresh` - Refresh database metadata cache
- `/explore <question>` - Autonomous exploration mode
- `/explain <question>` - Exploration with detailed reasoning
- `/export` - Export last exploration results
- `/validate <file>` - Validate exported exploration
- `/patterns` - View learned query patterns
- `/stats` - View performance statistics
- `/cache` - View cache statistics
- `/usage` - View token usage and costs

**Natural Language Queries:**
Just type your question naturally! For example:
- "How many customers do we have?"
- "Show me sales by month for this year"
- "What are the top 10 products by revenue?"

**Tips:**
- Be specific about what data you want
- Mention table names if you know them
- Use `/explore` for complex multi-step questions
- Check `/usage` to monitor your token costs
- The bot learns from your queries for faster responses!"""
        
        await turn_context.send_activity(MessageFactory.text(help_text))
    
    async def _handle_database_command(self, turn_context: TurnContext,
                                     conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /database command"""
        parts = turn_context.activity.text.split()
        
        if len(parts) == 1 or parts[1] == "list":
            # List databases
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "x-functions-key": self.function_key
                }
                
                payload = {
                    "query_type": "metadata"
                }
                
                async with session.post(self.function_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if "databases" in result:
                            databases = result["databases"]
                            response_text = f"**Available Databases ({len(databases)}):**\n"
                            for db in databases[:20]:  # Limit display
                                response_text += f"• {db}\n"
                            if len(databases) > 20:
                                response_text += f"\n... and {len(databases) - 20} more"
                            
                            await turn_context.send_activity(MessageFactory.text(response_text))
                        else:
                            await turn_context.send_activity(
                                MessageFactory.text("Failed to retrieve database list.")
                            )
                    else:
                        await turn_context.send_activity(
                            MessageFactory.text(f"Error: Function returned status {response.status}")
                        )
                
        elif len(parts) > 2 and parts[1] == "set":
            # Set current database
            database_name = " ".join(parts[2:])
            conversation_data["context"].current_database = database_name
            await turn_context.send_activity(
                MessageFactory.text(f"✅ Current database set to: **{database_name}**")
            )
    
    async def _handle_tables_command(self, turn_context: TurnContext,
                                   conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /tables command"""
        context = conversation_data["context"]
        
        if not context.current_database:
            await turn_context.send_activity(
                MessageFactory.text("Please set a database first using `/database set <name>`")
            )
            return
        
        parts = turn_context.activity.text.split()
        pattern = parts[1] if len(parts) > 1 else None
        
        # Generate schema query
        schema_query = self.sql_translator.generate_schema_query(
            context.current_database,
            pattern
        )
        
        # Execute query
        result = await self._execute_sql_query(schema_query, "full")
        
        if result.get("error"):
            await turn_context.send_activity(
                MessageFactory.text(f"Error retrieving tables: {result['error']}")
            )
        else:
            await self._send_query_results(turn_context, result, schema_query, user_profile)
    
    async def _handle_history_command(self, turn_context: TurnContext,
                                    conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /history command"""
        executions = conversation_data.get("executions", [])
        
        if not executions:
            await turn_context.send_activity(
                MessageFactory.text("No query history yet.")
            )
            return
        
        history_text = "**Recent Queries:**\n\n"
        for i, exec_data in enumerate(executions[-5:], 1):  # Last 5 queries
            query_text = exec_data['query']['query'][:100] + "..." if len(exec_data['query']['query']) > 100 else exec_data['query']['query']
            history_text += f"{i}. {query_text}\n"
            history_text += f"   Database: {exec_data['query']['database']}\n"
            if exec_data.get('row_count'):
                history_text += f"   Results: {exec_data['row_count']} rows\n"
            if exec_data.get('used_pattern'):
                history_text += f"   Pattern: ♻️ Reused\n"
            history_text += "\n"
        
        await turn_context.send_activity(MessageFactory.text(history_text))
    
    async def _handle_clear_command(self, turn_context: TurnContext,
                                  conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /clear command"""
        conversation_data["context"] = ConversationContext(messages=[])
        conversation_data["executions"] = []
        
        await turn_context.send_activity(
            MessageFactory.text("✨ Conversation history cleared.")
        )
    
    async def _handle_preferences_command(self, turn_context: TurnContext,
                                        conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /preferences command"""
        prefs = user_profile["preferences"]
        
        pref_text = "**Your Preferences:**\n\n"
        pref_text += f"• Row Limit: {prefs.get('row_limit', 100)}\n"
        pref_text += f"• Output Format: {prefs.get('output_format', 'natural_language')}\n"
        pref_text += f"• Date Format: {prefs.get('date_format', 'YYYY-MM-DD')}\n"
        pref_text += "\nTo change: `/preferences set <key> <value>`"
        
        await turn_context.send_activity(MessageFactory.text(pref_text))
    
    async def _handle_refresh_command(self, turn_context: TurnContext,
                                    conversation_data: Dict, user_profile: Dict) -> None:
        """Handle /refresh command"""
        if self.mcp_client:
            await turn_context.send_activity(
                MessageFactory.text("🔄 Refreshing database metadata cache... This may take a moment.")
            )
            
            try:
                result = await self.mcp_client.refresh_all_metadata()
                
                if result.get("status") == "completed":
                    await turn_context.send_activity(
                        MessageFactory.text(
                            f"✅ Cache refreshed successfully!\n"
                            f"• Databases updated: {result.get('databases_refreshed', 0)}\n"
                            f"• Duration: {result.get('duration_seconds', 0):.1f} seconds"
                        )
                    )
                else:
                    await turn_context.send_activity(
                        MessageFactory.text(f"❌ Cache refresh failed: {result.get('error', 'Unknown error')}")
                    )
            except Exception as e:
                await turn_context.send_activity(
                    MessageFactory.text(f"❌ Failed to refresh cache: {str(e)}")
                )
        else:
            await turn_context.send_activity(
                MessageFactory.text("MCP server not available for cache refresh.")
            )
    
    async def _handle_explore_command(self, turn_context: TurnContext,
                                    conversation_data: Dict, 
                                    user_profile: Dict) -> None:
        """Handle /explore command for autonomous mode"""
        parts = turn_context.activity.text.split(maxsplit=1)
        
        if len(parts) < 2:
            # Show explore help
            help_text = """**Autonomous Exploration Mode** 🤖

This mode allows me to automatically explore the database and run multiple queries to fully answer your question.

**Usage:**
`/explore <your question>`

**Examples:**
- `/explore What are our top performing products by region?`
- `/explore How has customer retention changed over the last year?`
- `/explore Which departments have the highest employee turnover?`

I'll automatically:
1. Analyze your question
2. Discover relevant tables and relationships
3. Run multiple queries to gather information
4. Synthesize a complete answer
5. Learn the pattern for faster future responses

**Note:** This may take 30-60 seconds for complex questions."""
            
            await turn_context.send_activity(MessageFactory.text(help_text))
        else:
            # Process the exploration query
            query = parts[1]
            await self._process_autonomous_query(
                turn_context, 
                query, 
                conversation_data, 
                user_profile,
                enable_explanation=False
            )
    
    async def _handle_explain_command(self, turn_context: TurnContext,
                                    conversation_data: Dict, 
                                    user_profile: Dict) -> None:
        """Handle /explain command - run exploration with detailed explanation"""
        parts = turn_context.activity.text.split(maxsplit=1)
        
        if len(parts) < 2:
            help_text = """**Explanation Mode** 🧠

This mode shows detailed reasoning for every decision made during exploration.

**Usage:**
`/explain <your question>`

**Example:**
`/explain Why are sales declining in the Northeast region?`

I'll show you:
- Why each query was chosen
- What I learned from each result
- How I built up to the final answer
- Key decision points in the exploration"""
            
            await turn_context.send_activity(MessageFactory.text(help_text))
        else:
            # Process with explanation
            query = parts[1]
            await self._process_autonomous_query(
                turn_context, 
                query, 
                conversation_data, 
                user_profile,
                enable_explanation=True
            )
    
    async def _handle_export_command(self, turn_context: TurnContext,
                                   conversation_data: Dict, 
                                   user_profile: Dict) -> None:
        """Handle /export command - export exploration results"""
        last_exploration = conversation_data.get("last_exploration")
        
        if not last_exploration:
            await turn_context.send_activity(
                MessageFactory.text("No exploration to export. Run `/explore` or `/explain` first.")
            )
            return
        
        if "export_file" in last_exploration:
            # Create export summary
            export_text = f"""📁 **Exploration Export**

**File:** `{last_exploration['export_file']}`
**Question:** {last_exploration.get('question', 'Unknown')}
**Database:** {last_exploration.get('database', 'Unknown')}
**Confidence:** {last_exploration.get('confidence', 0):.0%}
**Queries:** {last_exploration.get('queries_executed', 0)}

Export contains:
- Complete query history
- All results and reasoning
- Validation information
- Replayable query sequence

You can validate this export later with:
`/validate {last_exploration['export_file']}`"""
            
            await turn_context.send_activity(MessageFactory.text(export_text))
        else:
            await turn_context.send_activity(
                MessageFactory.text("Export not available for this exploration.")
            )
    
    async def _handle_validate_command(self, turn_context: TurnContext,
                                     conversation_data: Dict, 
                                     user_profile: Dict) -> None:
        """Handle /validate command - validate an export against current schema"""
        parts = turn_context.activity.text.split(maxsplit=1)
        
        if len(parts) < 2:
            await turn_context.send_activity(
                MessageFactory.text("Usage: `/validate <export_file_path>`")
            )
            return
        
        export_file = parts[1]
        context = conversation_data["context"]
        
        if not context.current_database:
            await turn_context.send_activity(
                MessageFactory.text("Please set a database first to validate against.")
            )
            return
        
        try:
            # Get current schema
            schema_snapshot = await self.autonomous_explorer._get_schema_hash(
                context.current_database
            )
            
            # Validate export
            validation_result = self.autonomous_explorer.exporter.validate_export(
                export_file, {"schema_hash": schema_snapshot}
            )
            
            # Send validation results
            status_emoji = "✅" if validation_result["is_valid"] else "❌"
            
            validation_text = f"""{status_emoji} **Export Validation Result**

**Status:** {'Valid' if validation_result["is_valid"] else 'Invalid'}"""
            
            if validation_result.get("errors"):
                validation_text += "\n\n**Errors:**"
                for error in validation_result["errors"]:
                    validation_text += f"\n• {error}"
            
            if validation_result.get("warnings"):
                validation_text += "\n\n**Warnings:**"
                for warning in validation_result["warnings"]:
                    validation_text += f"\n• {warning}"
            
            if validation_result.get("suggestions"):
                validation_text += "\n\n**Suggestions:**"
                for suggestion in validation_result["suggestions"]:
                    validation_text += f"\n• {suggestion}"
            
            await turn_context.send_activity(MessageFactory.text(validation_text))
            
        except Exception as e:
            await turn_context.send_activity(
                MessageFactory.text(f"❌ Error validating export: {str(e)}")
            )
    
    async def _handle_patterns_command(self, turn_context: TurnContext,
                                     conversation_data: Dict, 
                                     user_profile: Dict) -> None:
        """Handle /patterns command - show learned patterns from MCP"""
        if not self.mcp_client:
            await turn_context.send_activity(
                MessageFactory.text("Pattern learning requires MCP server connection.")
            )
            return
        
        try:
            # Get pattern statistics from MCP
            stats = await self.mcp_client.get_pattern_statistics()
            
            if not stats or stats.get("total_patterns", 0) == 0:
                await turn_context.send_activity(
                    MessageFactory.text("No learned patterns yet. Run more explorations to build pattern library.")
                )
                return
            
            # Create patterns summary
            summary_text = f"""**🧠 Learned Query Patterns**

**Overview:**
- Total Patterns: {stats.get('total_patterns', 0)}
- Databases: {stats.get('databases', 0)}
- Success Rate: {stats.get('success_rate', 0):.1f}%
- Avg Confidence: {stats.get('avg_confidence', 0):.0%}
- Total Uses: {stats.get('total_uses', 0)}"""
            
            if stats.get("top_patterns"):
                summary_text += "\n\n**Top Patterns:**"
                for i, pattern in enumerate(stats["top_patterns"][:5], 1):
                    summary_text += f"\n\n{i}. **{pattern['template']}**"
                    summary_text += f"\n   Database: {pattern['database']}"
                    summary_text += f"\n   Used: {pattern['uses']} times"
                    summary_text += f"\n   Confidence: {pattern['confidence']:.0%}"
                    summary_text += f"\n   Avg Time: {pattern['avg_time']:.0f}ms"
            
            await turn_context.send_activity(MessageFactory.text(summary_text))
            
            # Offer actions
            await turn_context.send_activity(
                MessageFactory.suggested_actions(
                    SuggestedActions(
                        suggestions=[
                            CardAction(
                                type=ActionTypes.im_back,
                                title="View Cache Stats",
                                value="/cache"
                            ),
                            CardAction(
                                type=ActionTypes.im_back,
                                title="Refresh Metadata",
                                value="/refresh"
                            )
                        ]
                    ),
                    "Pattern management options:"
                )
            )
            
        except Exception as e:
            await turn_context.send_activity(
                MessageFactory.text(f"❌ Error getting pattern statistics: {str(e)}")
            )
    
    async def _handle_stats_command(self, turn_context: TurnContext,
                                  conversation_data: Dict, 
                                  user_profile: Dict) -> None:
        """Handle /stats command - show performance statistics"""
        # Get stats from MCP if available
        mcp_stats = {}
        if self.mcp_client:
            try:
                mcp_stats = await self.mcp_client.get_cache_statistics()
            except:
                pass
        
        # Calculate bot statistics
        executions = conversation_data.get("executions", [])
        total_queries = len(executions)
        pattern_uses = sum(1 for e in executions if e.get("used_pattern"))
        avg_time = sum(e.get("execution_time_ms", 0) for e in executions) / total_queries if total_queries > 0 else 0
        
        stats_text = f"""**📊 Performance Statistics**

**Query Statistics:**
- Total Queries: {total_queries}
- Pattern Reuses: {pattern_uses} ({pattern_uses/total_queries*100:.0f}% if total_queries > 0 else 0)
- Average Time: {avg_time:.0f}ms"""
        
        if mcp_stats.get("cache"):
            cache = mcp_stats["cache"]
            stats_text += f"""

**Cache Performance:**
- Hit Rate: {cache.get('hit_rate', 0):.1f}%
- L1 Hits: {cache.get('hits_by_tier', {}).get('L1', 0)}
- L2 Hits: {cache.get('hits_by_tier', {}).get('L2', 0)}
- L3 Hits: {cache.get('hits_by_tier', {}).get('L3', 0)}
- Total Items: {cache.get('total_items', 0)}"""
        
        if mcp_stats.get("pattern_stats"):
            patterns = mcp_stats["pattern_stats"]
            stats_text += f"""

**Pattern Learning:**
- Total Patterns: {patterns.get('total_patterns', 0)}
- Success Rate: {patterns.get('success_rate', 0):.1f}%
- Avg Confidence: {patterns.get('avg_confidence', 0):.0%}"""
        
        await turn_context.send_activity(MessageFactory.text(stats_text))
    
    async def _handle_cache_command(self, turn_context: TurnContext,
                                  conversation_data: Dict, 
                                  user_profile: Dict) -> None:
        """Handle /cache command - show cache statistics"""
        if not self.mcp_client:
            await turn_context.send_activity(
                MessageFactory.text("Cache statistics require MCP server connection.")
            )
            return
        
        try:
            stats = await self.mcp_client.get_cache_statistics()
            
            cache_text = "**💾 Cache Statistics**\n"
            
            if stats.get("cache"):
                cache = stats["cache"]
                cache_text += f"""
**Cache Performance:**
- Hit Rate: {cache.get('hit_rate', 0):.1f}%
- Total Requests: {sum(cache.get('hits_by_tier', {}).values()) + cache.get('misses', 0)}
- Misses: {cache.get('misses', 0)}

**Cache Tiers:**
- L1 (Hot): {cache.get('l1_size', 0)} items, {cache.get('hits_by_tier', {}).get('L1', 0)} hits
- L2 (Warm): {cache.get('l2_size', 0)} items, {cache.get('hits_by_tier', {}).get('L2', 0)} hits
- L3 (Cold): {cache.get('l3_size', 0)} items, {cache.get('hits_by_tier', {}).get('L3', 0)} hits"""
            
            if stats.get("performance"):
                perf = stats["performance"]
                cache_text += f"""

**Performance Metrics:**
- Uptime: {perf.get('uptime_seconds', 0)/3600:.1f} hours
- Total Queries: {perf.get('total_queries', 0)}
- Error Rate: {perf.get('error_rate', 0):.1f}%"""
            
            await turn_context.send_activity(MessageFactory.text(cache_text))
            
        except Exception as e:
            await turn_context.send_activity(
                MessageFactory.text(f"❌ Error getting cache statistics: {str(e)}")
            )
    
    async def _handle_usage_command(self, turn_context: TurnContext,
                                  conversation_data: Dict, 
                                  user_profile: Dict) -> None:
        """Handle /usage command - show token usage and costs"""
        usage = self.sql_translator.token_limiter.get_usage_summary()
        
        # Create usage card
        usage_card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "💰 Token Usage & Cost Summary",
                        "weight": "bolder",
                        "size": "large"
                    },
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "**Today's Usage**",
                                "weight": "bolder",
                                "size": "medium"
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {
                                        "title": "Tokens Used",
                                        "value": f"{usage['daily']['used']:,} / {usage['daily']['limit']:,}"
                                    },
                                    {
                                        "title": "Percentage",
                                        "value": f"{usage['daily']['percentage']:.1f}%"
                                    },
                                    {
                                        "title": "Cost",
                                        "value": f"${usage['daily']['cost']:.2f}"
                                    },
                                    {
                                        "title": "Remaining",
                                        "value": f"{usage['daily']['remaining']:,} tokens"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "**Current Hour**",
                                "weight": "bolder",
                                "size": "medium"
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {
                                        "title": "Tokens Used",
                                        "value": f"{usage['hourly']['used']:,} / {usage['hourly']['limit']:,}"
                                    },
                                    {
                                        "title": "Remaining",
                                        "value": f"{usage['hourly']['remaining']:,} tokens"
                                    }
                                ]
                            }
                        ],
                        "separator": True
                    },
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "**All-Time Usage**",
                                "weight": "bolder",
                                "size": "medium"
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {
                                        "title": "Total Tokens",
                                        "value": f"{usage['total']['tokens']:,}"
                                    },
                                    {
                                        "title": "Total Cost",
                                        "value": f"${usage['total']['cost']:.2f}"
                                    }
                                ]
                            }
                        ],
                        "separator": True
                    },
                    {
                        "type": "TextBlock",
                        "text": "⚠️ Limits reset daily at midnight and hourly on the hour.",
                        "wrap": True,
                        "isSubtle": True,
                        "size": "small"
                    }
                ],
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "Refresh Usage",
                        "data": {
                            "action": "refresh_usage"
                        }
                    }
                ]
            }
        }
        
        await turn_context.send_activity(MessageFactory.attachment(usage_card))
        
        # Add warning if approaching limits
        if usage['daily']['percentage'] > 80:
            await turn_context.send_activity(
                MessageFactory.text("⚠️ Warning: You're approaching your daily token limit!")
            )
        elif usage['hourly']['percentage'] > 80:
            await turn_context.send_activity(
                MessageFactory.text("⚠️ Warning: You're approaching your hourly token limit!")
            )

# Export the main class
__all__ = ['SQLAssistantBot', 'EnhancedMCPClient']