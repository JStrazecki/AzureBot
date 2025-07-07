# sql_translator_simple.py - Simple Azure OpenAI SQL Translator
"""
Simple SQL Translator using Azure OpenAI
Focused on basic natural language to SQL translation
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
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

class SimpleSQLTranslator:
    """Simple SQL translator using Azure OpenAI"""
    
    def __init__(self):
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
        
        self.system_prompt = """You are an expert SQL translator for Microsoft SQL Server.
Convert natural language questions into T-SQL queries.

Rules:
1. ONLY generate SELECT queries - never INSERT, UPDATE, DELETE, or DDL
2. Use proper T-SQL syntax (TOP instead of LIMIT)
3. Always include database name if specified
4. Be conservative with data - add TOP 100 unless user asks for all

Respond with JSON:
{
    "query": "the SQL query",
    "database": "database name or 'master'",
    "explanation": "what the query does",
    "confidence": 0.0-1.0
}"""

    async def translate_to_sql(self, 
                             user_query: str, 
                             database: str = "master",
                             schema_context: Optional[str] = None) -> SQLQuery:
        """Translate natural language to SQL"""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Database: {database}\n{schema_context or ''}\nQuestion: {user_query}"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return SQLQuery(
                query=result.get("query", ""),
                database=result.get("database", database),
                explanation=result.get("explanation", ""),
                confidence=float(result.get("confidence", 0.5))
            )
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return SQLQuery(
                query="",
                database=database,
                explanation=f"Error: {str(e)}",
                confidence=0.0,
                error=str(e)
            )