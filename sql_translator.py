# sql_translator.py - Unified Azure OpenAI SQL Translator with Error Analysis
"""
Unified SQL Translator using Azure OpenAI
Combines the best features from both versions with error analysis capability
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

@dataclass
class SQLQuery:
    """Represents a translated SQL query"""
    query: str
    database: str
    explanation: str
    confidence: float
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

@dataclass
class ErrorAnalysis:
    """Represents an error analysis result"""
    error_type: str
    explanation: str
    suggested_fix: str
    fixed_query: str
    confidence: float
    alternative_queries: List[str] = field(default_factory=list)
    discovery_queries: List[str] = field(default_factory=list)

@dataclass
class TokenUsage:
    """Track token usage for cost management"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0

class SQLTranslator:
    """Unified SQL translator with error analysis using Azure OpenAI"""
    
    def __init__(self):
        # Azure OpenAI configuration
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        if not self.endpoint or not self.api_key:
            raise ValueError("Azure OpenAI endpoint and API key must be set")
        
        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2024-02-01"
        )
        
        # Token tracking (simplified from complex version)
        self.total_usage = TokenUsage()
        self.cost_per_1k_tokens = float(os.environ.get("OPENAI_COST_PER_1K", "0.03"))
        
        # System prompts
        self.system_prompt = self._create_system_prompt()
        self.error_analysis_prompt = self._create_error_analysis_prompt()
        
    def _create_system_prompt(self) -> str:
        """Create the main system prompt for SQL translation"""
        return """You are an expert SQL translator for Microsoft SQL Server (T-SQL) specializing in database standardization.
Your role is to convert natural language questions into safe, efficient T-SQL queries.

CONTEXT:
- The system uses standardized database schemas: acc (accounting), inv (inventory), hr (human resources), crm (customer relations)
- Views follow naming conventions and standardized column names across different source systems
- This is used for database standardization checks and data analysis

CRITICAL SAFETY RULES:
1. ONLY generate SELECT queries - never generate INSERT, UPDATE, DELETE, DROP, or any DDL/DML commands
2. Always validate that queries are read-only
3. Use proper T-SQL syntax (TOP instead of LIMIT, GETDATE() for current time, square brackets for identifiers)
4. Add appropriate WHERE clauses to prevent full table scans on large tables

QUERY GUIDELINES:
1. For counting: Use COUNT(*) or COUNT(DISTINCT column)
2. For aggregations: Include appropriate GROUP BY clauses
3. For large tables: Always use TOP to limit results unless specifically asked for all
4. For standardization checks: Consider querying INFORMATION_SCHEMA views
5. For schema comparison: Use appropriate system views (sys.tables, sys.columns, etc.)

SPECIAL COMMANDS:
- "show tables" → EXEC sp_tables @table_type = "'TABLE'"
- "show columns in [table]" → SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '[table]'
- "compare schemas" → Generate query to compare table structures across databases
- "check standardization" → Query to verify schema compliance

RESPONSE FORMAT:
Always respond with a JSON object containing:
{
    "query": "the SQL query",
    "database": "target database name",
    "explanation": "detailed explanation of what this query does",
    "confidence": 0.0-1.0,
    "warnings": ["any warnings or considerations"]
}"""

    def _create_error_analysis_prompt(self) -> str:
        """Create the error analysis system prompt"""
        return """You are an expert SQL Server database administrator specializing in T-SQL error diagnosis and query fixing.
Analyze SQL errors and provide corrected queries for a database standardization system.

CONTEXT:
- System uses standardized schemas: acc (accounting), inv (inventory), hr (human resources), crm (customer relations)
- Tables might be views with standardized naming conventions
- Common issues include schema mismatches, column name variations, and missing objects

WHEN ANALYZING ERRORS:
1. Identify the specific error type (syntax, missing object, permissions, etc.)
2. Explain what went wrong in simple, non-technical terms
3. Provide multiple solutions when possible
4. Suggest discovery queries to find the correct table/column names
5. Consider standardization context (e.g., table might be in acc/inv/hr/crm schema)

COMMON FIXES:
- Add schema prefix (e.g., acc.CustomerView instead of CustomerView)
- Check column name variations (CustomerID vs Customer_ID vs CustomerId)
- Use square brackets for reserved words or special characters
- Verify table is a view vs base table for standardized systems
- Consider case sensitivity in column/table names

DISCOVERY QUERIES:
When object not found, suggest queries like:
- List all tables: SELECT TABLE_SCHEMA + '.' + TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'
- Find table by pattern: SELECT TABLE_SCHEMA + '.' + TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%pattern%'
- List columns: SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'tablename'

RESPONSE FORMAT:
Always respond with a JSON object containing:
{
    "error_type": "syntax|object_not_found|permissions|data_type|other",
    "explanation": "simple explanation of what went wrong",
    "suggested_fix": "what needs to be changed",
    "fixed_query": "the primary corrected SQL query",
    "confidence": 0.0-1.0,
    "alternative_queries": ["other possible corrections"],
    "discovery_queries": ["queries to help find correct objects"]
}"""

    async def translate_to_sql(self, 
                             user_query: str, 
                             database: str = "demo",
                             schema_context: Optional[str] = None,
                             conversation_history: Optional[List[Dict]] = None) -> SQLQuery:
        """Translate natural language to SQL with context awareness"""
        try:
            # Build the user message
            user_message = f"Database: {database}\n"
            
            # Add schema context if provided
            if schema_context:
                user_message += f"Schema Context: {schema_context}\n"
            
            # Add recent context if available
            if conversation_history and len(conversation_history) > 0:
                recent = conversation_history[-1]
                if recent.get('type') == 'sql_result' and recent.get('tables_found'):
                    user_message += f"Recent tables queried: {', '.join(recent['tables_found'][:5])}\n"
            
            user_message += f"User Query: {user_query}"
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            logger.info(f"Translating query: {user_query[:50]}...")
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                self._track_usage(response.usage)
            
            result = json.loads(response.choices[0].message.content)
            
            # Post-process for common patterns
            query = result.get("query", "").strip()
            query = self._post_process_query(query, user_query)
            
            return SQLQuery(
                query=query,
                database=result.get("database", database),
                explanation=result.get("explanation", ""),
                confidence=float(result.get("confidence", 0.8)),
                warnings=result.get("warnings", [])
            )
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return SQLQuery(
                query="",
                database=database,
                explanation=f"Translation failed: {str(e)}",
                confidence=0.0,
                error=str(e)
            )

    async def analyze_sql_error(self, 
                               original_query: str, 
                               error_message: str,
                               database: str,
                               user_intent: Optional[str] = None,
                               available_context: Optional[Dict] = None) -> ErrorAnalysis:
        """Analyze SQL error and suggest fixes with discovery queries"""
        try:
            # Build comprehensive context
            context_parts = [
                f"Database: {database}",
                f"Failed Query: {original_query}",
                f"Error Message: {error_message}"
            ]
            
            if user_intent:
                context_parts.append(f"User's Original Request: {user_intent}")
            
            # Add available context
            if available_context:
                if available_context.get('recent_tables'):
                    context_parts.append(f"Recently accessed tables: {', '.join(available_context['recent_tables'][:10])}")
                if available_context.get('known_schemas'):
                    context_parts.append(f"Known schemas in database: {', '.join(available_context['known_schemas'])}")
            
            # Add standardization context
            context_parts.append("Note: This database uses standardized views with schemas: acc, inv, hr, crm")
            
            context = "\n".join(context_parts)
            
            messages = [
                {"role": "system", "content": self.error_analysis_prompt},
                {"role": "user", "content": context}
            ]
            
            logger.info(f"Analyzing SQL error: {error_message[:100]}...")
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.2,  # Slightly higher for creative solutions
                max_tokens=800,   # More tokens for comprehensive analysis
                response_format={"type": "json_object"}
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                self._track_usage(response.usage)
            
            result = json.loads(response.choices[0].message.content)
            
            # Ensure all fields are present
            return ErrorAnalysis(
                error_type=result.get("error_type", "unknown"),
                explanation=result.get("explanation", "Unable to determine error cause"),
                suggested_fix=result.get("suggested_fix", "Please check query syntax"),
                fixed_query=result.get("fixed_query", original_query),
                confidence=float(result.get("confidence", 0.5)),
                alternative_queries=result.get("alternative_queries", []),
                discovery_queries=result.get("discovery_queries", [])
            )
            
        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            # Return a basic analysis even if AI fails
            return ErrorAnalysis(
                error_type="analysis_failed",
                explanation=f"Could not analyze error: {str(e)}",
                suggested_fix="Please verify table and column names",
                fixed_query=original_query,
                confidence=0.0,
                discovery_queries=["EXEC sp_tables", "SELECT * FROM INFORMATION_SCHEMA.TABLES"]
            )

    async def generate_standardization_query(self, check_type: str, target_objects: List[str], database: str) -> SQLQuery:
        """Generate queries for standardization checks"""
        prompt = f"""Generate a T-SQL query for the following standardization check:
Check Type: {check_type}
Target Objects: {', '.join(target_objects)}
Database: {database}

Consider querying system views and INFORMATION_SCHEMA for comprehensive checks."""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            if hasattr(response, 'usage'):
                self._track_usage(response.usage)
            
            result = json.loads(response.choices[0].message.content)
            
            return SQLQuery(
                query=result.get("query", ""),
                database=database,
                explanation=f"Standardization check: {check_type}",
                confidence=float(result.get("confidence", 0.9))
            )
        except Exception as e:
            logger.error(f"Failed to generate standardization query: {e}")
            return SQLQuery(
                query="",
                database=database,
                explanation=f"Error generating query: {str(e)}",
                confidence=0.0,
                error=str(e)
            )

    def _post_process_query(self, query: str, user_query: str) -> str:
        """Post-process query for common patterns"""
        query = query.strip()
        
        # Handle "show columns in X" pattern
        if user_query.lower().startswith("show columns in"):
            table_name = user_query.lower().replace("show columns in", "").strip()
            table_name = table_name.replace("table", "").strip()
            
            if not query or "information_schema" not in query.lower():
                query = f"""
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE,
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = '{table_name}'
ORDER BY ORDINAL_POSITION"""
        
        return query.strip()

    def _track_usage(self, usage):
        """Track token usage for cost monitoring"""
        if usage:
            self.total_usage.prompt_tokens += usage.prompt_tokens
            self.total_usage.completion_tokens += usage.completion_tokens
            self.total_usage.total_tokens += usage.total_tokens
            self.total_usage.estimated_cost = (self.total_usage.total_tokens / 1000) * self.cost_per_1k_tokens
            
            logger.info(f"Token usage - This request: {usage.total_tokens}, Total: {self.total_usage.total_tokens}, Cost: ${self.total_usage.estimated_cost:.4f}")

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current token usage summary"""
        return {
            "total_tokens": self.total_usage.total_tokens,
            "prompt_tokens": self.total_usage.prompt_tokens,
            "completion_tokens": self.total_usage.completion_tokens,
            "estimated_cost": round(self.total_usage.estimated_cost, 4),
            "cost_per_1k_tokens": self.cost_per_1k_tokens
        }

# For backward compatibility with existing code
SimpleSQLTranslator = SQLTranslator