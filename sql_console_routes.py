# sql_console_routes.py - Enhanced SQL Console Routes with Error Analysis
"""
SQL Console Routes - Enhanced with intelligent error handling and query fixing
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from aiohttp import web
from aiohttp.web import Request, Response, json_response
import aiohttp
import asyncio

# Import UI components
from sql_console_html import get_sql_console_html

logger = logging.getLogger(__name__)

class SQLConsole:
    """Enhanced SQL Console with error analysis and auto-fixing capabilities"""
    
    def __init__(self, sql_translator=None):
        self.sql_translator = sql_translator
        self.function_url = os.environ.get("AZURE_FUNCTION_URL", "")
        self.sessions = {}
        self.active_requests = {}
        self.database_cache = {}
        self.cache_timeout = 300  # 5 minutes
        
        # Track query history for better context
        self.query_history = {}  # session_id -> list of recent queries
        self.error_history = {}  # session_id -> list of recent errors
        
        # Check if authentication is embedded in URL
        self.url_has_auth = "code=" in self.function_url
        
        logger.info(f"SQL Console initialized with error analysis features")
        logger.info(f"Function URL configured: {'Yes' if self.function_url else 'No'}")
        logger.info(f"SQL Translator available: {'Yes' if sql_translator else 'No'}")
    
    async def console_page(self, request: Request) -> Response:
        """Serve the SQL console HTML page"""
        html_content = get_sql_console_html()
        return Response(text=html_content, content_type='text/html')
    
    async def handle_message(self, request: Request) -> Response:
        """Handle incoming console messages with enhanced error handling"""
        request_id = datetime.now().strftime("%H%M%S%f")[:10]
        
        try:
            data = await request.json()
            message = data.get('message', '').strip()
            database = data.get('database', 'demo')
            session_id = data.get('session_id')
            multi_db_mode = data.get('multi_db_mode', False)
            databases = data.get('databases', [])
            
            # Initialize session history if needed
            if session_id not in self.query_history:
                self.query_history[session_id] = []
                self.error_history[session_id] = []
            
            # Store request for potential cancellation
            self.active_requests[session_id] = request_id
            
            logger.info(f"[{request_id}] Console message: {message[:50]}...")
            
            # Send initial acknowledgment
            await self._send_log_message(session_id, f"🔍 Processing: {message}", "info")
            
            if multi_db_mode and databases:
                await self._send_log_message(session_id, f"📊 Multi-database mode: {len(databases)} databases selected", "info")
            
            # Check for special commands
            if message.lower() in ['help', '?']:
                return json_response({
                    'status': 'success',
                    'response_type': 'help',
                    'content': self._get_enhanced_help_text()
                })
            
            # Handle schema comparison commands
            if message.lower().startswith('compare schemas'):
                return await self._handle_schema_comparison(message, databases, session_id)
            
            # Handle standardization check commands
            if message.lower().startswith('check standardization'):
                return await self._handle_standardization_check(message, databases, session_id)
            
            # Determine if it's SQL or natural language
            is_sql = self._is_sql_query(message)
            
            if is_sql:
                await self._send_log_message(session_id, "✅ Detected direct SQL query", "info")
                sql_query = message
                explanation = "Direct SQL query execution"
                user_intent = None
            else:
                # Natural language - needs translation
                if not self.sql_translator:
                    return json_response({
                        'status': 'error',
                        'error': 'SQL translator not available. Please check Azure OpenAI configuration.'
                    })
                
                await self._send_log_message(session_id, "🤖 Translating natural language to SQL...", "info")
                
                # Enhanced translation with context
                schema_context = await self._get_enhanced_schema_context(database, databases if multi_db_mode else None)
                conversation_history = self.query_history.get(session_id, [])
                
                result = await self.sql_translator.translate_to_sql(
                    message,
                    database=database,
                    schema_context=schema_context,
                    conversation_history=conversation_history
                )
                
                if result.error or not result.query:
                    return json_response({
                        'status': 'error',
                        'error': result.error or 'Could not translate to SQL query'
                    })
                
                sql_query = result.query
                explanation = result.explanation
                user_intent = message  # Store original intent for error analysis
                
                await self._send_log_message(session_id, f"✅ Translated to SQL: {sql_query[:100]}...", "success")
            
            # Execute the query with enhanced error handling
            if multi_db_mode and databases:
                results = await self._execute_multi_db_query_with_error_handling(
                    sql_query, databases, session_id, user_intent
                )
                
                # Check if any databases had errors and offer to fix
                errors_found = [r for r in results if r.get('error')]
                if errors_found and self.sql_translator:
                    # Offer error analysis for failed queries
                    error_analysis = await self._analyze_multi_db_errors(
                        errors_found, sql_query, user_intent, session_id
                    )
                    
                    return json_response({
                        'status': 'success',
                        'response_type': 'sql_result_with_errors',
                        'sql_query': sql_query,
                        'explanation': explanation,
                        'multi_db_results': results,
                        'error_analysis': error_analysis,
                        'offer_fix': True
                    })
                
                return json_response({
                    'status': 'success',
                    'response_type': 'sql_result',
                    'sql_query': sql_query,
                    'explanation': explanation,
                    'multi_db_results': results
                })
            else:
                # Single database query with error handling
                execution_result = await self._execute_sql_query_with_error_handling(
                    sql_query, database, session_id, user_intent
                )
                
                if execution_result.get('error'):
                    # Offer to analyze and fix the error
                    if self.sql_translator and not execution_result.get('error_analyzed'):
                        error_analysis = await self._analyze_single_error(
                            sql_query, execution_result['error'], database, user_intent, session_id
                        )
                        
                        return json_response({
                            'status': 'success',
                            'response_type': 'sql_error_with_analysis',
                            'sql_query': sql_query,
                            'database': database,
                            'error': execution_result['error'],
                            'error_analysis': error_analysis,
                            'offer_fix': True
                        })
                    else:
                        return json_response({
                            'status': 'error',
                            'error': execution_result['error']
                        })
                
                # Success - store in history
                self._add_to_query_history(session_id, {
                    'type': 'sql_result',
                    'query': sql_query,
                    'database': database,
                    'row_count': execution_result.get('row_count', 0),
                    'tables_found': self._extract_tables_from_query(sql_query)
                })
                
                return json_response({
                    'status': 'success',
                    'response_type': 'sql_result',
                    'sql_query': sql_query,
                    'database': database,
                    'explanation': explanation,
                    'rows': execution_result.get('rows', []),
                    'row_count': execution_result.get('row_count', 0),
                    'execution_time': execution_result.get('execution_time_ms', 0)
                })
                
        except Exception as e:
            logger.error(f"[{request_id}] Console message error: {e}", exc_info=True)
            return json_response({
                'status': 'error',
                'error': str(e)
            })
        finally:
            if session_id in self.active_requests:
                del self.active_requests[session_id]
    
    async def apply_error_fix(self, request: Request) -> Response:
        """Apply the suggested fix from error analysis"""
        try:
            data = await request.json()
            session_id = data.get('session_id')
            fixed_query = data.get('fixed_query')
            database = data.get('database')
            databases = data.get('databases', [])
            multi_db_mode = data.get('multi_db_mode', False)
            alternative_index = data.get('alternative_index', None)
            
            logger.info(f"Applying error fix for session {session_id}")
            
            # If alternative query requested, use that instead
            if alternative_index is not None and 'alternatives' in data:
                alternatives = data.get('alternatives', [])
                if 0 <= alternative_index < len(alternatives):
                    fixed_query = alternatives[alternative_index]
            
            # Execute the fixed query
            if multi_db_mode and databases:
                results = await self._execute_multi_db_query_with_error_handling(
                    fixed_query, databases, session_id, None
                )
                
                return json_response({
                    'status': 'success',
                    'response_type': 'sql_result',
                    'sql_query': fixed_query,
                    'explanation': 'Fixed query executed',
                    'multi_db_results': results,
                    'was_fixed': True
                })
            else:
                execution_result = await self._execute_sql_query_with_error_handling(
                    fixed_query, database, session_id, None
                )
                
                if execution_result.get('error'):
                    return json_response({
                        'status': 'error',
                        'error': f"Fixed query still has errors: {execution_result['error']}",
                        'attempted_query': fixed_query
                    })
                
                return json_response({
                    'status': 'success',
                    'response_type': 'sql_result',
                    'sql_query': fixed_query,
                    'database': database,
                    'explanation': 'Fixed query executed successfully',
                    'rows': execution_result.get('rows', []),
                    'row_count': execution_result.get('row_count', 0),
                    'execution_time': execution_result.get('execution_time_ms', 0),
                    'was_fixed': True
                })
                
        except Exception as e:
            logger.error(f"Error applying fix: {e}")
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def run_discovery_query(self, request: Request) -> Response:
        """Run a discovery query to help find correct table/column names"""
        try:
            data = await request.json()
            discovery_query = data.get('query')
            database = data.get('database')
            session_id = data.get('session_id')
            
            logger.info(f"Running discovery query: {discovery_query[:50]}...")
            
            result = await self._execute_sql_query_with_logging(discovery_query, database, session_id)
            
            if result.get('error'):
                return json_response({
                    'status': 'error',
                    'error': result['error']
                })
            
            return json_response({
                'status': 'success',
                'response_type': 'discovery_result',
                'sql_query': discovery_query,
                'database': database,
                'rows': result.get('rows', []),
                'row_count': result.get('row_count', 0)
            })
            
        except Exception as e:
            logger.error(f"Discovery query error: {e}")
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def _analyze_single_error(self, query: str, error: str, database: str, 
                                   user_intent: Optional[str], session_id: str) -> Dict:
        """Analyze a single database error"""
        # Get context for better analysis
        context = await self._build_error_context(database, session_id)
        
        # Call the translator's error analysis
        analysis = await self.sql_translator.analyze_sql_error(
            original_query=query,
            error_message=error,
            database=database,
            user_intent=user_intent,
            available_context=context
        )
        
        # Convert to dict for JSON response
        return {
            'error_type': analysis.error_type,
            'explanation': analysis.explanation,
            'suggested_fix': analysis.suggested_fix,
            'fixed_query': analysis.fixed_query,
            'confidence': analysis.confidence,
            'alternative_queries': analysis.alternative_queries,
            'discovery_queries': analysis.discovery_queries
        }
    
    async def _analyze_multi_db_errors(self, errors: List[Dict], query: str, 
                                      user_intent: Optional[str], session_id: str) -> List[Dict]:
        """Analyze errors from multiple databases"""
        analyses = []
        
        for error_result in errors:
            if error_result.get('error'):
                analysis = await self._analyze_single_error(
                    query,
                    error_result['error'],
                    error_result['database'],
                    user_intent,
                    session_id
                )
                analysis['database'] = error_result['database']
                analyses.append(analysis)
        
        return analyses
    
    async def _build_error_context(self, database: str, session_id: str) -> Dict:
        """Build context for error analysis"""
        context = {
            'recent_tables': [],
            'known_schemas': ['acc', 'inv', 'hr', 'crm', 'dbo']  # Standard schemas
        }
        
        # Get recent tables from query history
        if session_id in self.query_history:
            for entry in self.query_history[session_id][-5:]:  # Last 5 entries
                if entry.get('tables_found'):
                    context['recent_tables'].extend(entry['tables_found'])
        
        # Remove duplicates
        context['recent_tables'] = list(set(context['recent_tables']))
        
        return context
    
    async def _execute_sql_query_with_error_handling(self, query: str, database: str, 
                                                    session_id: str, user_intent: Optional[str]) -> Dict:
        """Execute query with enhanced error information"""
        result = await self._execute_sql_query_with_logging(query, database, session_id)
        
        # If error occurred, add context
        if result.get('error'):
            self._add_to_error_history(session_id, {
                'query': query,
                'database': database,
                'error': result['error'],
                'timestamp': datetime.now().isoformat(),
                'user_intent': user_intent
            })
        
        return result
    
    async def _execute_multi_db_query_with_error_handling(self, query: str, databases: List[str], 
                                                         session_id: str, user_intent: Optional[str]) -> List[Dict]:
        """Execute multi-database query with error tracking"""
        results = await self._execute_multi_db_query_enhanced(query, databases, session_id)
        
        # Track errors
        for result in results:
            if result.get('error'):
                self._add_to_error_history(session_id, {
                    'query': query,
                    'database': result['database'],
                    'error': result['error'],
                    'timestamp': datetime.now().isoformat(),
                    'user_intent': user_intent
                })
        
        return results
    
    def _add_to_query_history(self, session_id: str, entry: Dict):
        """Add entry to query history"""
        if session_id not in self.query_history:
            self.query_history[session_id] = []
        
        self.query_history[session_id].append(entry)
        
        # Keep only last 20 entries
        if len(self.query_history[session_id]) > 20:
            self.query_history[session_id] = self.query_history[session_id][-20:]
    
    def _add_to_error_history(self, session_id: str, entry: Dict):
        """Add entry to error history"""
        if session_id not in self.error_history:
            self.error_history[session_id] = []
        
        self.error_history[session_id].append(entry)
        
        # Keep only last 10 errors
        if len(self.error_history[session_id]) > 10:
            self.error_history[session_id] = self.error_history[session_id][-10:]
    
    def _extract_tables_from_query(self, query: str) -> List[str]:
        """Extract table names from query (simple implementation)"""
        tables = []
        query_upper = query.upper()
        
        # Look for table names after FROM and JOIN
        import re
        patterns = [
            r'FROM\s+\[?(\w+)\]?',
            r'JOIN\s+\[?(\w+)\]?',
            r'INTO\s+\[?(\w+)\]?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query_upper)
            tables.extend(matches)
        
        # Filter out SQL keywords
        keywords = {'SELECT', 'WHERE', 'ORDER', 'GROUP', 'HAVING'}
        tables = [t for t in tables if t not in keywords]
        
        return list(set(tables))
    
    def _get_enhanced_help_text(self) -> str:
        """Get enhanced help text with error handling features"""
        return """SQL Assistant Console - Enhanced with Intelligent Error Handling:

**NEW: Error Analysis & Auto-Fix Features:**
- When a query fails, I'll analyze the error and suggest fixes
- Multiple alternative queries provided when possible
- Discovery queries to help find correct table/column names
- One-click application of suggested fixes

**Natural Language Queries:**
- "Show me all customers"
- "Compare columns in AD table across all databases"
- "Check standardization of accounting views"
- "Find differences in table structure between systems"

**Multi-Database Features:**
- Toggle "Multi-Database Query" mode in sidebar
- Select databases for comparison
- Automatic result analysis and formatting
- Intelligent query splitting for performance

**Standardization Commands:**
- "compare schemas [table]" - Compare table structure across databases
- "check standardization" - Verify schema compliance
- "show [schema] views" - List views in specific schema (acc, inv, hr, crm)

**SQL Commands:**
- SELECT, WITH, and other read queries
- System procedures (sp_tables, sp_columns, etc.)
- Direct SQL syntax with T-SQL support

**Available Databases:**
- _support - Support database
- demo - Demo database with standardized schemas
- Additional databases discovered dynamically

**Schema Standards:**
- acc - Accounting (financial data)
- inv - Inventory management
- hr - Human resources
- crm - Customer relationship management

**Error Handling Tips:**
- If a query fails, I'll offer to analyze and fix it
- Use discovery queries to find correct object names
- Try alternative suggestions if the first fix doesn't work
- Check the error history to learn from past issues

**Other Features:**
- Copy conversation logs with the copy button
- Export logs for documentation
- Real-time processing status updates
- Query history for context-aware suggestions"""
    
    async def get_tables_api(self, request: Request) -> Response:
        """API endpoint to get tables - with enhanced error handling"""
        try:
            database = request.query.get('database', 'demo')
            session_id = request.query.get('session_id', 'api')
            
            logger.info(f"Getting tables for database: {database}")
            
            # Try multiple approaches to ensure we get tables
            queries_to_try = [
                {
                    "name": "INFORMATION_SCHEMA method",
                    "query": """
                        SELECT 
                            TABLE_SCHEMA,
                            TABLE_NAME,
                            TABLE_TYPE
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                        ORDER BY TABLE_SCHEMA, TABLE_NAME
                    """
                },
                {
                    "name": "sys.objects method",
                    "query": """
                        SELECT 
                            s.name as TABLE_SCHEMA,
                            o.name as TABLE_NAME,
                            CASE o.type 
                                WHEN 'U' THEN 'TABLE'
                                WHEN 'V' THEN 'VIEW'
                            END as TABLE_TYPE
                        FROM sys.objects o
                        JOIN sys.schemas s ON o.schema_id = s.schema_id
                        WHERE o.type IN ('U', 'V')
                        ORDER BY s.name, o.name
                    """
                },
                {
                    "name": "sp_tables method",
                    "query": "sp_tables"
                }
            ]
            
            for query_info in queries_to_try:
                logger.info(f"Trying {query_info['name']}: {query_info['query'][:50]}...")
                
                result = await self._execute_sql_query_with_logging(query_info['query'], database, session_id)
                
                if result.get('rows') and not result.get('error'):
                    tables = []
                    views = []
                    
                    # Process results based on the format
                    for row in result['rows']:
                        # Get table info based on available columns
                        table_name = row.get('TABLE_NAME', '')
                        schema = row.get('TABLE_SCHEMA', row.get('TABLE_OWNER', 'dbo'))
                        table_type = row.get('TABLE_TYPE', 'TABLE')
                        
                        if not table_name:
                            continue
                        
                        # Build full table name
                        if schema and schema != 'dbo':
                            full_name = f"{schema}.{table_name}"
                        else:
                            full_name = table_name
                        
                        # Separate tables and views
                        if 'VIEW' in table_type.upper():
                            views.append(full_name)
                        else:
                            tables.append(full_name)
                    
                    all_objects = tables + views
                    
                    if all_objects:
                        logger.info(f"Found {len(tables)} tables and {len(views)} views using {query_info['name']}")
                        
                        # Store successful tables in history
                        self._add_to_query_history(session_id, {
                            'type': 'table_discovery',
                            'database': database,
                            'tables_found': all_objects[:20]  # Store sample
                        })
                        
                        return json_response({
                            'status': 'success',
                            'tables': sorted(list(set(all_objects))),  # All objects
                            'tables_only': sorted(tables),  # Just tables
                            'views_only': sorted(views),    # Just views
                            'database': database,
                            'method': query_info['name'],
                            'counts': {
                                'tables': len(tables),
                                'views': len(views),
                                'total': len(all_objects)
                            }
                        })
                
                # Log why this method didn't work
                if result.get('error'):
                    logger.warning(f"{query_info['name']} failed: {result['error']}")
            
            # If all methods fail, try one more fallback
            logger.warning(f"All standard methods failed for {database}, trying simplified query")
            
            # Simplified query that should work on most SQL Server databases
            fallback_query = "SELECT name FROM sys.sysobjects WHERE xtype IN ('U', 'V') ORDER BY name"
            result = await self._execute_sql_query_with_logging(fallback_query, database, session_id)
            
            if result.get('rows'):
                tables = [row['name'] for row in result['rows'] if row.get('name')]
                if tables:
                    return json_response({
                        'status': 'success',
                        'tables': sorted(tables),
                        'database': database,
                        'method': 'sys.sysobjects fallback',
                        'note': 'Used fallback method'
                    })
            
            # If everything fails, return empty list with helpful message
            logger.warning(f"No tables found in {database} after trying all methods")
            return json_response({
                'status': 'success',
                'tables': [],
                'database': database,
                'note': 'No accessible tables found. This could be due to permissions or an empty database.',
                'suggestions': [
                    'Check if the database contains any tables',
                    'Verify MSI has SELECT permissions',
                    'Try running: SELECT * FROM INFORMATION_SCHEMA.TABLES'
                ]
            })
                
        except Exception as e:
            logger.error(f"Tables API error: {e}", exc_info=True)
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def _send_log_message(self, session_id: str, message: str, level: str = "info"):
        """Send a log message to the client"""
        logger.info(f"[Console-{session_id}] {level.upper()}: {message}")
    
    def _is_sql_query(self, message: str) -> bool:
        """Check if message is a SQL query"""
        sql_keywords = ['select', 'with', 'exec', 'execute', 'sp_']
        message_lower = message.lower().strip()
        
        for keyword in sql_keywords:
            if message_lower.startswith(keyword):
                return True
        
        sql_patterns = ['from ', 'where ', 'join ', 'group by', 'order by']
        if any(pattern in message_lower for pattern in sql_patterns):
            return True
        
        return False
    
    async def _call_function_with_logging(self, payload: Dict[str, Any], session_id: str) -> Optional[Dict]:
        """Call Azure Function with logging"""
        try:
            headers = {"Content-Type": "application/json"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.function_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Function call failed: {response.status} - {error_text}")
                        return {'error': f'Function returned {response.status}: {error_text[:200]}'}
                        
        except Exception as e:
            logger.error(f"Error calling function: {e}")
            return {'error': f'Function call failed: {str(e)}'}
    
    async def _execute_sql_query_with_logging(self, query: str, database: str, session_id: str) -> Dict[str, Any]:
        """Execute SQL query with logging"""
        if not self.function_url:
            return {'error': 'Azure Function URL not configured'}
        
        try:
            payload = {
                "query_type": "single",
                "query": query,
                "database": database,
                "output_format": "raw"
            }
            
            result = await self._call_function_with_logging(payload, session_id)
            
            if result:
                return result
            else:
                return {'error': 'No response from function'}
                
        except Exception as e:
            return {'error': str(e)}
    
    async def _execute_multi_db_query_enhanced(self, query: str, databases: List[str], session_id: str, output_format: str = 'raw') -> List[Dict]:
        """Execute query across multiple databases with enhanced formatting"""
        if not self.function_url:
            return [{'database': db, 'error': 'Azure Function URL not configured'} for db in databases]
        
        try:
            payload = {
                "query_type": "multi_database",
                "query": query,
                "databases": databases,
                "output_format": output_format
            }
            
            await self._send_log_message(session_id, f"📤 Executing across {len(databases)} databases", "info")
            
            result = await self._call_function_with_logging(payload, session_id)
            
            if result:
                if 'error' in result:
                    # Single error for all databases
                    return [{'database': db, 'error': result['error']} for db in databases]
                elif output_format == 'comparison' and 'comparison' in result:
                    return result['comparison']
                elif isinstance(result, list):
                    return result
                else:
                    return [{'error': 'Invalid response format'}]
            else:
                return [{'database': db, 'error': 'No response from function'} for db in databases]
                
        except Exception as e:
            logger.error(f"Error executing multi-database query: {e}")
            return [{'database': db, 'error': str(e)} for db in databases]
    
    async def _get_enhanced_schema_context(self, database: str, additional_databases: Optional[List[str]] = None) -> str:
        """Get enhanced schema context for translation"""
        context_parts = [f"Primary database: {database}"]
        
        if additional_databases:
            context_parts.append(f"Additional databases: {', '.join(additional_databases)}")
        
        # Add standardization context
        context_parts.append("Standard schemas: acc (accounting), inv (inventory), hr (human resources), crm (customer relations)")
        
        # Add recent tables if available
        recent_tables = []
        for entry in self.query_history.get(database, [])[-5:]:
            if entry.get('tables_found'):
                recent_tables.extend(entry['tables_found'])
        
        if recent_tables:
            context_parts.append(f"Recently accessed tables: {', '.join(set(recent_tables)[:10])}")
        
        return "\n".join(context_parts)
    
    async def _handle_schema_comparison(self, message: str, databases: List[str], session_id: str) -> Response:
        """Handle schema comparison requests"""
        await self._send_log_message(session_id, "📊 Performing schema comparison...", "info")
        
        # Extract table name from message
        parts = message.lower().split()
        table_name = parts[-1] if len(parts) > 2 else None
        
        if not table_name or not databases or len(databases) < 2:
            return json_response({
                'status': 'error',
                'error': 'Please specify a table name and select at least 2 databases for comparison'
            })
        
        # Query to get column information
        query = f"""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            CHARACTER_MAXIMUM_LENGTH,
            IS_NULLABLE,
            COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        
        # Execute across selected databases
        results = await self._execute_multi_db_query_enhanced(query, databases, session_id, output_format='comparison')
        
        return json_response({
            'status': 'success',
            'response_type': 'schema_comparison',
            'table_name': table_name,
            'comparison': results
        })
    
    async def _handle_standardization_check(self, message: str, databases: List[str], session_id: str) -> Response:
        """Handle database standardization checks"""
        await self._send_log_message(session_id, "🔍 Checking database standardization...", "info")
        
        # Query to check view schemas
        query = """
        SELECT 
            s.name as SchemaName,
            COUNT(DISTINCT v.name) as ViewCount
        FROM sys.schemas s
        JOIN sys.views v ON s.schema_id = v.schema_id
        WHERE s.name IN ('acc', 'inv', 'hr', 'crm')
        GROUP BY s.name
        ORDER BY s.name
        """
        
        results = await self._execute_multi_db_query_enhanced(query, databases, session_id)
        
        # Analyze standardization
        analysis = {
            'standardized_schemas': ['acc', 'inv', 'hr', 'crm'],
            'database_compliance': []
        }
        
        for result in results:
            if not result.get('error'):
                schemas_found = [row['SchemaName'] for row in result.get('rows', [])]
                analysis['database_compliance'].append({
                    'database': result['database'],
                    'schemas_found': schemas_found,
                    'compliance_score': len(schemas_found) / len(analysis['standardized_schemas'])
                })
        
        return json_response({
            'status': 'success',
            'response_type': 'standardization_check',
            'analysis': analysis,
            'raw_results': results
        })
    
    async def get_databases_api(self, request: Request) -> Response:
        """API endpoint to get databases (excluding master)"""
        try:
            session_id = request.query.get('session_id', 'api')
            force_refresh = request.query.get('force_refresh', '').lower() == 'true'
            
            # Get databases from Azure Function
            payload = {
                "query_type": "metadata",
                "force_refresh": force_refresh
            }
            
            result = await self._call_function_with_logging(payload, session_id)
            
            if result and 'databases' in result:
                # Filter out excluded databases (master is excluded in the function now)
                databases = result['databases']
                
                return json_response({
                    'status': 'success',
                    'databases': databases,
                    'msi_identity': result.get('msi_identity', 'Unknown'),
                    'note': 'Showing user-accessible databases only'
                })
            else:
                # Fallback list without master
                return json_response({
                    'status': 'success',
                    'databases': ['_support', 'demo'],
                    'note': 'Using fallback database list'
                })
                
        except Exception as e:
            logger.error(f"Database API error: {e}")
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def export_logs_api(self, request: Request) -> Response:
        """API endpoint to export conversation logs"""
        try:
            data = await request.json()
            logs = data.get('logs', [])
            format_type = data.get('format', 'text')
            
            # Include error history if available
            session_id = data.get('session_id')
            if session_id and session_id in self.error_history:
                logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'error_summary',
                    'message': f"Session had {len(self.error_history[session_id])} errors"
                })
            
            if format_type == 'json':
                content = json.dumps(logs, indent=2)
                content_type = 'application/json'
                filename = f'sql_console_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            else:
                # Text format
                lines = []
                for log in logs:
                    timestamp = log.get('timestamp', '')
                    level = log.get('type', 'info').upper()
                    message = log.get('message', '')
                    lines.append(f"[{timestamp}] {level}: {message}")
                
                content = '\n'.join(lines)
                content_type = 'text/plain'
                filename = f'sql_console_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            
            return Response(
                text=content,
                content_type=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
            
        except Exception as e:
            logger.error(f"Export logs error: {e}")
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def cancel_request_api(self, request: Request) -> Response:
        """API endpoint to cancel active request"""
        try:
            data = await request.json()
            session_id = data.get('session_id')
            
            if session_id in self.active_requests:
                del self.active_requests[session_id]
                return json_response({
                    'status': 'success',
                    'message': 'Request cancelled'
                })
            else:
                return json_response({
                    'status': 'success',
                    'message': 'No active request to cancel'
                })
                
        except Exception as e:
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def get_current_user_api(self, request: Request) -> Response:
        """API endpoint to get current user information"""
        try:
            user_info = {
                'name': 'SQL User',
                'email': None,
                'auth_type': 'Managed Service Identity',
                'sql_user': 'Function App MSI'
            }
            
            # Check for Azure App Service headers
            headers_to_check = {
                'X-MS-CLIENT-PRINCIPAL-NAME': 'email',
                'X-MS-CLIENT-PRINCIPAL': 'principal',
                'X-MS-CLIENT-PRINCIPAL-ID': 'id'
            }
            
            for header, field in headers_to_check.items():
                value = request.headers.get(header)
                if value:
                    if field == 'email':
                        user_info['email'] = value
                        user_info['name'] = value.split('@')[0]
            
            return json_response({
                'status': 'success',
                'user': user_info
            })
            
        except Exception as e:
            return json_response({
                'status': 'error',
                'error': str(e)
            })

def add_console_routes(app, sql_translator=None):
    """Add SQL console routes to the main app"""
    
    console = SQLConsole(sql_translator)
    
    # Console UI
    app.router.add_get('/console', console.console_page)
    app.router.add_get('/console/', console.console_page)
    
    # Console API endpoints
    app.router.add_post('/console/api/message', console.handle_message)
    app.router.add_get('/console/api/databases', console.get_databases_api)
    app.router.add_get('/console/api/tables', console.get_tables_api)
    app.router.add_get('/console/api/current-user', console.get_current_user_api)
    app.router.add_post('/console/api/cancel', console.cancel_request_api)
    app.router.add_post('/console/api/export-logs', console.export_logs_api)
    
    # New endpoints for error handling
    app.router.add_post('/console/api/apply-fix', console.apply_error_fix)
    app.router.add_post('/console/api/discovery', console.run_discovery_query)
    
    logger.info("Enhanced SQL Console routes with error analysis added successfully")
    return console