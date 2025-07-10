# sql-assistant/bot/azure_openai_sql_translator.py
"""
Enhanced Azure OpenAI SQL Translator with Token Limiting
Translates natural language to SQL with improved context awareness and safety
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from openai import AzureOpenAI
import tiktoken
from datetime import datetime
from token_limiter import TokenLimiter

logger = logging.getLogger(__name__)

@dataclass
class SQLQuery:
    """Represents a SQL query with enhanced metadata"""
    query: str
    database: str
    explanation: str
    confidence: float
    requires_followup: bool = False
    followup_queries: List[str] = field(default_factory=list)
    estimated_rows: Optional[int] = None
    complexity: str = "simple"  # simple, moderate, complex
    warnings: List[str] = field(default_factory=list)

@dataclass
class ConversationContext:
    """Enhanced conversation context with query history"""
    messages: List[Dict[str, str]]
    current_database: Optional[str] = None
    recent_tables: List[str] = field(default_factory=list)
    query_history: List[SQLQuery] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    schema_context: Optional[Dict[str, Any]] = None
    
class AzureOpenAISQLTranslator:
    """Enhanced SQL translator with improved safety and context awareness"""
    
    def __init__(self, 
                 endpoint: str,
                 api_key: str,
                 deployment_name: str,
                 api_version: str = "2024-02-01"):
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        self.max_context_tokens = 8000
        
        # Initialize token limiter
        self.token_limiter = TokenLimiter(
            max_daily_tokens=int(os.environ.get("MAX_DAILY_TOKENS", "50000")),
            max_hourly_tokens=int(os.environ.get("MAX_HOURLY_TOKENS", "10000")),
            max_tokens_per_request=int(os.environ.get("MAX_REQUEST_TOKENS", "2000")),
            cost_per_1k_tokens=float(os.environ.get("OPENAI_COST_PER_1K", "0.03"))
        )
        
        # Enhanced system prompt
        self.system_prompt = self._create_enhanced_system_prompt()
        
        # Query validation patterns
        self.dangerous_patterns = [
            'drop', 'delete', 'truncate', 'update', 'insert',
            'alter', 'create', 'exec', 'execute', 'grant', 'revoke'
        ]
    
    def _create_enhanced_system_prompt(self) -> str:
        """Create enhanced system prompt with safety guidelines"""
        return """You are an expert SQL translator specialized in Microsoft SQL Server (T-SQL).
Your role is to convert natural language questions into safe, efficient SQL queries.

CRITICAL SAFETY RULES:
1. ONLY generate SELECT queries - never generate INSERT, UPDATE, DELETE, DROP, or any DDL/DML commands
2. Always validate that queries are read-only
3. Use proper T-SQL syntax (TOP instead of LIMIT, GETDATE() for current time)
4. Quote identifiers with square brackets if they contain spaces or special characters
5. Add appropriate WHERE clauses to prevent full table scans on large tables

QUERY GUIDELINES:
1. For counting: Use COUNT(*) or COUNT(DISTINCT column)
2. For aggregations: Include appropriate GROUP BY clauses
3. For large tables: Always use TOP to limit results unless specifically asked for all
4. For date ranges: Use proper date functions and consider indexes
5. For joins: Prefer INNER JOIN unless outer joins are specifically needed
6. Always explain what the query does and why you structured it that way

RESPONSE FORMAT:
Always respond with a JSON object containing:
{
    "query": "the SQL query",
    "database": "target database name or 'multi' for cross-database",
    "explanation": "detailed explanation of what this query does",
    "confidence": 0.0-1.0,
    "requires_followup": true/false,
    "followup_queries": ["list of follow-up queries if needed"],
    "estimated_rows": estimated number of rows (null if unknown),
    "complexity": "simple|moderate|complex",
    "warnings": ["list of any warnings or considerations"]
}

MULTI-STEP QUERIES:
If a question requires multiple steps:
1. Set requires_followup to true
2. Provide the first query
3. List the follow-up queries needed
4. Explain the overall approach

SCHEMA AWARENESS:
When table/column names are ambiguous:
1. Note the ambiguity in warnings
2. Suggest using schema discovery first
3. Provide best guess with lower confidence

Remember: User safety is paramount. When in doubt, be conservative and add more constraints."""

    def translate_to_sql(self, 
                        user_query: str, 
                        context: ConversationContext,
                        schema_hint: Optional[Dict[str, Any]] = None,
                        safety_check: bool = True) -> SQLQuery:
        """
        Translate natural language to SQL query with enhanced safety.
        
        Args:
            user_query: Natural language query from user
            context: Conversation context with history
            schema_hint: Optional schema information
            safety_check: Whether to perform safety validation
        """
        try:
            # Check token limits first
            user_message = self._build_enhanced_user_message(user_query, context, schema_hint)
            messages = self._trim_context(context)
            
            # Estimate tokens
            estimated_tokens = self._estimate_tokens(self.system_prompt + user_message)
            
            allowed, reason = self.token_limiter.check_limits(estimated_tokens)
            if not allowed:
                logger.warning(f"Token limit exceeded: {reason}")
                usage_summary = self.token_limiter.get_usage_summary()
                return SQLQuery(
                    query="",
                    database="",
                    explanation=f"⚠️ Usage limit reached: {reason}\n\nDaily usage: ${usage_summary['daily']['cost']:.2f}",
                    confidence=0.0,
                    warnings=[reason, f"Try again after the limit resets or use /usage to check your quota"]
                )
            
            # Pre-validate query intent
            if safety_check and self._contains_dangerous_intent(user_query):
                return SQLQuery(
                    query="",
                    database="",
                    explanation="I can only help with SELECT queries for reading data. Modification queries are not allowed.",
                    confidence=0.0,
                    warnings=["Query appears to request data modification which is not permitted"]
                )
            
            # Add to context
            context.messages.append({"role": "user", "content": user_message})
            
            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.1,  # Low temperature for consistent SQL
                max_tokens=1500,  # Increased for complex queries
                response_format={"type": "json_object"}
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                self.token_limiter.track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
                
                # Log usage
                usage = self.token_limiter.get_usage_summary()
                logger.info(f"Token usage - Request: {response.usage.total_tokens}, Daily total: ${usage['daily']['cost']:.2f}")
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            # Validate generated query
            if safety_check:
                is_safe, safety_warnings = self._validate_query_safety(result.get("query", ""))
                if not is_safe:
                    return SQLQuery(
                        query="",
                        database="",
                        explanation="Generated query failed safety validation.",
                        confidence=0.0,
                        warnings=safety_warnings
                    )
                elif safety_warnings:
                    result.setdefault("warnings", []).extend(safety_warnings)
            
            # Add assistant response to context
            context.messages.append({
                "role": "assistant", 
                "content": response.choices[0].message.content
            })
            
            # Create SQLQuery object with all fields
            sql_query = SQLQuery(
                query=result.get("query", ""),
                database=result.get("database", ""),
                explanation=result.get("explanation", ""),
                confidence=float(result.get("confidence", 0.5)),
                requires_followup=result.get("requires_followup", False),
                followup_queries=result.get("followup_queries", []),
                estimated_rows=result.get("estimated_rows"),
                complexity=result.get("complexity", "simple"),
                warnings=result.get("warnings", [])
            )
            
            # Update context
            context.query_history.append(sql_query)
            if sql_query.database:
                context.current_database = sql_query.database
            
            # Track recent tables
            self._update_recent_tables(sql_query.query, context)
            
            return sql_query
            
        except Exception as e:
            logger.error(f"Error translating to SQL: {e}")
            return SQLQuery(
                query="",
                database="",
                explanation=f"Error translating query: {str(e)}",
                confidence=0.0,
                warnings=[f"Translation error: {str(e)}"]
            )
    
    def _contains_dangerous_intent(self, user_query: str) -> bool:
        """Check if user query contains dangerous intent"""
        query_lower = user_query.lower()
        
        # Check for dangerous keywords in context
        dangerous_phrases = [
            "delete all", "drop table", "truncate", "remove all",
            "clear all", "wipe", "destroy", "update all",
            "change all", "modify all", "alter table"
        ]
        
        return any(phrase in query_lower for phrase in dangerous_phrases)
    
    def _validate_query_safety(self, query: str) -> Tuple[bool, List[str]]:
        """Validate that generated query is safe"""
        if not query:
            return True, []
        
        query_lower = query.lower()
        warnings = []
        
        # Check for dangerous operations
        for pattern in self.dangerous_patterns:
            if pattern in query_lower and not (pattern == 'create' and 'create view' not in query_lower):
                return False, [f"Query contains forbidden operation: {pattern}"]
        
        # Check for multiple statements
        if ';' in query and not query.strip().endswith(';'):
            return False, ["Multiple statements detected"]
        
        # Warn about missing TOP clause for potentially large queries
        if 'top' not in query_lower and 'count' not in query_lower:
            warnings.append("Consider adding TOP clause to limit results")
        
        # Warn about missing WHERE clause
        if 'where' not in query_lower and 'join' not in query_lower:
            warnings.append("Query has no WHERE clause - may return many rows")
        
        return True, warnings
    
    def _build_enhanced_user_message(self, 
                                   user_query: str, 
                                   context: ConversationContext,
                                   schema_hint: Optional[Dict[str, Any]] = None) -> str:
        """Build enhanced user message with rich context"""
        message_parts = [f"User Query: {user_query}"]
        
        # Add current database context
        if context.current_database:
            message_parts.append(f"Current Database: {context.current_database}")
        
        # Add recent tables context
        if context.recent_tables:
            message_parts.append(f"Recently Referenced Tables: {', '.join(context.recent_tables[-5:])}")
        
        # Add user preferences
        if context.user_preferences:
            if "row_limit" in context.user_preferences:
                message_parts.append(f"Default Row Limit: {context.user_preferences['row_limit']}")
            if "date_format" in context.user_preferences:
                message_parts.append(f"Preferred Date Format: {context.user_preferences['date_format']}")
        
        # Add schema context if available
        if schema_hint:
            schema_info = []
            
            if "tables" in schema_hint:
                table_list = [t.get("table_name", t) for t in schema_hint["tables"][:10]]
                schema_info.append(f"Available Tables: {', '.join(table_list)}")
                
            if "columns" in schema_hint:
                # Group columns by table
                table_columns = {}
                for col in schema_hint["columns"]:
                    table = col.get("table_name", "unknown")
                    if table not in table_columns:
                        table_columns[table] = []
                    table_columns[table].append(col.get("column_name", col))
                
                # Add column info for each table
                for table, columns in list(table_columns.items())[:3]:
                    schema_info.append(f"{table} columns: {', '.join(columns[:5])}")
            
            if schema_info:
                message_parts.append("Schema Information:\n" + "\n".join(schema_info))
        
        # Add previous query context if this is a follow-up
        if context.query_history and len(context.query_history) > 0:
            last_query = context.query_history[-1]
            if last_query.requires_followup:
                message_parts.append(f"Previous Query: {last_query.query}")
                message_parts.append("This is a follow-up query to the previous one.")
        
        return "\n\n".join(message_parts)
    
    def _update_recent_tables(self, query: str, context: ConversationContext):
        """Extract and update recently referenced tables"""
        # Simple extraction - could be enhanced with proper SQL parsing
        query_upper = query.upper()
        
        # Look for table names after FROM and JOIN
        import re
        
        # Pattern to find table names
        patterns = [
            r'FROM\s+\[?(\w+)\]?',
            r'JOIN\s+\[?(\w+)\]?',
            r'INTO\s+\[?(\w+)\]?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query_upper)
            for match in matches:
                if match not in ['SELECT', 'WHERE', 'ORDER', 'GROUP', 'HAVING']:
                    if match not in context.recent_tables:
                        context.recent_tables.append(match)
        
        # Keep only last 10 tables
        context.recent_tables = context.recent_tables[-10:]
    
    def _trim_context(self, context: ConversationContext) -> List[Dict[str, str]]:
        """Trim conversation context to fit within token limits"""
        # Always include system prompt
        messages = [{"role": "system", "content": self.system_prompt}]
        token_count = self._estimate_tokens(self.system_prompt)
        
        # Add messages from newest to oldest until we hit the limit
        for message in reversed(context.messages):
            message_tokens = self._estimate_tokens(message["content"])
            if token_count + message_tokens > self.max_context_tokens - 500:  # Leave room for response
                break
            messages.insert(1, message)  # Insert after system prompt
            token_count += message_tokens
        
        return messages
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return len(self.encoding.encode(text))
    
    def explain_results(self, 
                       query: str, 
                       results: List[Dict[str, Any]], 
                       user_question: str,
                       formatted_result: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate natural language explanation of query results.
        Now works with pre-formatted results from the Azure Function.
        """
        # Check token limits before explaining
        estimated_tokens = self._estimate_tokens(str(results)[:1000])  # Limit sample
        allowed, reason = self.token_limiter.check_limits(estimated_tokens)
        
        if not allowed:
            return f"Cannot generate explanation: {reason}"
        
        # If we have formatted results, use them
        if formatted_result and "natural_language" in formatted_result:
            base_explanation = formatted_result["natural_language"]
            
            # Enhance with insights if available
            if "insights" in formatted_result and formatted_result["insights"]:
                base_explanation += "\n\nKey insights:\n"
                for insight in formatted_result["insights"][:3]:
                    base_explanation += f"• {insight}\n"
            
            return base_explanation
        
        # Fallback to original explanation logic
        sample_results = results[:10] if len(results) > 10 else results
        
        prompt = f"""Given this user question: "{user_question}"

And this SQL query: {query}

The query returned {len(results)} rows. Here's a sample:
{json.dumps(sample_results, indent=2, default=str)}

Provide a clear, conversational summary of what the results show, highlighting key insights.
Focus on answering the user's original question directly."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a data analyst explaining query results to business users. Be concise and insightful."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            # Track usage
            if hasattr(response, 'usage'):
                self.token_limiter.track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error explaining results: {e}")
            return f"The query returned {len(results)} rows of data."
    
    def suggest_improvements(self, 
                           sql_query: str, 
                           execution_time: float,
                           row_count: int,
                           context: ConversationContext) -> Dict[str, Any]:
        """Suggest improvements for a SQL query based on performance"""
        # Check token limits
        estimated_tokens = self._estimate_tokens(sql_query + str(execution_time))
        allowed, reason = self.token_limiter.check_limits(estimated_tokens)
        
        if not allowed:
            return {
                "improvements": [f"Cannot analyze: {reason}"],
                "performance_tips": [],
                "estimated_improvement": "unknown"
            }
        
        prompt = f"""Analyze this SQL query and suggest improvements:

Query: {sql_query}
Execution Time: {execution_time}ms
Rows Returned: {row_count}
Database: {context.current_database or 'Unknown'}

Consider:
1. Performance optimizations (indexes, query structure)
2. T-SQL best practices
3. Potential issues with the current approach
4. Alternative query structures

Provide response as JSON with:
- improvements: array of improvement suggestions
- optimized_query: the improved query if applicable
- performance_tips: array of performance tips
- estimated_improvement: estimated performance gain (low/medium/high)"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a SQL Server performance expert. Focus on practical, actionable improvements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            # Track usage
            if hasattr(response, 'usage'):
                self.token_limiter.track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            
            suggestions = json.loads(response.choices[0].message.content)
            
            # Validate the optimized query if provided
            if "optimized_query" in suggestions:
                is_safe, warnings = self._validate_query_safety(suggestions["optimized_query"])
                if not is_safe:
                    suggestions["optimized_query"] = None
                    suggestions["warnings"] = warnings
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting improvements: {e}")
            return {
                "improvements": ["Unable to generate suggestions"],
                "performance_tips": [],
                "estimated_improvement": "unknown"
            }
    
    def handle_complex_query(self, 
                           user_query: str, 
                           context: ConversationContext,
                           max_steps: int = 5) -> List[SQLQuery]:
        """
        Break down complex queries into multiple steps.
        Enhanced with better step management and safety checks.
        """
        # Check token limits
        estimated_tokens = self._estimate_tokens(user_query) * max_steps
        allowed, reason = self.token_limiter.check_limits(estimated_tokens)
        
        if not allowed:
            return [SQLQuery(
                query="",
                database="",
                explanation=f"Cannot process complex query: {reason}",
                confidence=0.0,
                warnings=[reason]
            )]
        
        prompt = f"""Break down this complex question into a series of SQL queries:

Question: {user_query}
Current Database: {context.current_database or 'Not specified'}

Consider:
1. What information needs to be gathered first?
2. What depends on previous results?
3. How to combine results for the final answer?
4. Maximum {max_steps} steps allowed

Provide a JSON array of query steps, each with:
- step_number: 1-based step number
- description: what this step does
- query: the SQL query
- database: target database
- depends_on: array of previous step numbers this depends on
- is_final: boolean indicating if this produces the final answer"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            # Track usage
            if hasattr(response, 'usage'):
                self.token_limiter.track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            
            result = json.loads(response.choices[0].message.content)
            steps = result.get("steps", [])[:max_steps]  # Limit steps
            
            queries = []
            for step in steps:
                # Validate each query
                is_safe, warnings = self._validate_query_safety(step.get("query", ""))
                
                if is_safe:
                    queries.append(SQLQuery(
                        query=step["query"],
                        database=step.get("database", context.current_database or ""),
                        explanation=step.get("description", ""),
                        confidence=0.8,
                        requires_followup=not step.get("is_final", False),
                        complexity="complex",
                        warnings=warnings
                    ))
                else:
                    logger.warning(f"Skipping unsafe query in step {step.get('step_number', '?')}")
            
            return queries
            
        except Exception as e:
            logger.error(f"Error handling complex query: {e}")
            return []
    
    def generate_schema_query(self, 
                            database: str,
                            table_pattern: Optional[str] = None) -> SQLQuery:
        """Generate a query to discover database schema"""
        if table_pattern:
            where_clause = f"WHERE TABLE_NAME LIKE '%{table_pattern}%'"
        else:
            where_clause = ""
        
        query = f"""
        SELECT 
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_TYPE,
            COUNT(c.COLUMN_NAME) as COLUMN_COUNT
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN INFORMATION_SCHEMA.COLUMNS c 
            ON t.TABLE_NAME = c.TABLE_NAME 
            AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        {where_clause}
        GROUP BY t.TABLE_SCHEMA, t.TABLE_NAME, t.TABLE_TYPE
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """
        
        return SQLQuery(
            query=query.strip(),
            database=database,
            explanation=f"Retrieve schema information for tables in {database}" + 
                       (f" matching pattern '{table_pattern}'" if table_pattern else ""),
            confidence=1.0,
            complexity="simple",
            warnings=[]
        )
    
    def get_token_usage_summary(self) -> Dict[str, Any]:
        """Get current token usage summary"""
        return self.token_limiter.get_usage_summary()

# Export the main class
__all__ = ['AzureOpenAISQLTranslator', 'SQLQuery', 'ConversationContext']