"""
Enhanced Autonomous SQL Explorer with MCP Pattern Integration
Uses centralized MCP pattern learning instead of local storage
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging
import re
import asyncio

logger = logging.getLogger(__name__)


class ExplanationTracker:
    """Tracks and explains reasoning for each query"""
    
    def __init__(self):
        self.explanations = []
        self.current_reasoning = []
    
    def start_iteration(self, iteration: int, context: Dict[str, Any]):
        """Start tracking a new iteration"""
        self.current_reasoning = [{
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "context_summary": self._summarize_context(context),
            "decisions": []
        }]
    
    def add_decision(self, decision_type: str, reasoning: str, 
                    details: Dict[str, Any] = None):
        """Add a decision point with reasoning"""
        if self.current_reasoning:
            self.current_reasoning[-1]["decisions"].append({
                "type": decision_type,
                "reasoning": reasoning,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            })
    
    def add_query_reasoning(self, query: str, purpose: str, 
                          expected_outcome: str):
        """Add reasoning for why a specific query is being run"""
        self.add_decision(
            "query_selection",
            f"Running query to {purpose}",
            {
                "query": query,
                "purpose": purpose,
                "expected_outcome": expected_outcome
            }
        )
    
    def complete_iteration(self, outcome: str):
        """Complete current iteration with outcome"""
        if self.current_reasoning:
            self.current_reasoning[-1]["outcome"] = outcome
            self.explanations.extend(self.current_reasoning)
            self.current_reasoning = []
    
    def get_explanation_summary(self) -> Dict[str, Any]:
        """Get complete explanation summary"""
        return {
            "total_iterations": len(self.explanations),
            "decision_count": sum(len(e["decisions"]) for e in self.explanations),
            "detailed_reasoning": self.explanations,
            "key_insights": self._extract_key_insights()
        }
    
    def _summarize_context(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Summarize current context state"""
        return {
            "question": context.get("question", ""),
            "tables_discovered": len(context.get("discovered_schema", {})),
            "queries_run": len(context.get("query_results", [])),
            "current_confidence": context.get("confidence", 0.0)
        }
    
    def _extract_key_insights(self) -> List[str]:
        """Extract key insights from reasoning"""
        insights = []
        
        # Find pivotal decisions
        for explanation in self.explanations:
            for decision in explanation["decisions"]:
                if decision["type"] == "breakthrough":
                    insights.append(decision["reasoning"])
        
        return insights[:5]  # Top 5 insights


class ExplorationExporter:
    """Exports and validates exploration sessions"""
    
    def __init__(self, export_dir: str = ".exploration_exports"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(exist_ok=True)
    
    def export_session(self, exploration_result: Dict[str, Any], 
                      explanations: Dict[str, Any],
                      database: str,
                      question: str) -> str:
        """Export exploration session with validation info"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + \
                    hashlib.md5(question.encode()).hexdigest()[:8]
        
        export_data = {
            "session_id": session_id,
            "exported_at": datetime.now().isoformat(),
            "database": database,
            "question": question,
            "exploration_result": exploration_result,
            "explanations": explanations,
            "validation_info": self._create_validation_info(exploration_result),
            "replayable_queries": self._extract_replayable_queries(exploration_result),
            "pattern_id": exploration_result.get("pattern_id"),
            "used_mcp_pattern": exploration_result.get("using_mcp_pattern", False)
        }
        
        # Save as JSON
        export_file = self.export_dir / f"exploration_{session_id}.json"
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        # Also save as markdown report
        report_file = self.export_dir / f"report_{session_id}.md"
        with open(report_file, 'w') as f:
            f.write(self._generate_markdown_report(export_data))
        
        return str(export_file)
    
    def validate_export(self, export_file: str, 
                       current_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if exported exploration is still valid"""
        with open(export_file, 'r') as f:
            export_data = json.load(f)
        
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        # Check schema changes
        validation_info = export_data.get("validation_info", {})
        
        for table in validation_info.get("required_tables", []):
            if table not in current_schema:
                validation_result["is_valid"] = False
                validation_result["errors"].append(
                    f"Required table '{table}' no longer exists"
                )
        
        for table, columns in validation_info.get("required_columns", {}).items():
            if table in current_schema:
                current_columns = {
                    col["COLUMN_NAME"] for col in current_schema[table].get("columns", [])
                }
                missing_columns = set(columns) - current_columns
                if missing_columns:
                    validation_result["is_valid"] = False
                    validation_result["errors"].append(
                        f"Table '{table}' is missing columns: {missing_columns}"
                    )
        
        # Check age of export
        exported_at = datetime.fromisoformat(export_data["exported_at"])
        age_days = (datetime.now() - exported_at).days
        
        if age_days > 30:
            validation_result["warnings"].append(
                f"Export is {age_days} days old, results may be outdated"
            )
        
        # Check if pattern is still valid
        if export_data.get("used_mcp_pattern") and export_data.get("pattern_id"):
            validation_result["suggestions"].append(
                "This used an MCP pattern - verify pattern is still valid"
            )
        
        return validation_result
    
    def _create_validation_info(self, exploration_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create validation information for the export"""
        required_tables = set()
        required_columns = {}
        
        # Extract from discovered schema
        for table, info in exploration_result.get("discovered_schema", {}).items():
            required_tables.add(table)
            columns = [col["COLUMN_NAME"] for col in info.get("columns", [])]
            required_columns[table] = columns
        
        # Extract from queries
        for query_info in exploration_result.get("query_history", []):
            # Simple extraction of table names from queries
            query = query_info.get("query", "")
            table_matches = re.findall(r'FROM\s+\[?(\w+)\]?', query, re.IGNORECASE)
            required_tables.update(table_matches)
        
        return {
            "required_tables": list(required_tables),
            "required_columns": required_columns,
            "schema_fingerprint": hashlib.md5(
                json.dumps(required_columns, sort_keys=True).encode()
            ).hexdigest()
        }
    
    def _extract_replayable_queries(self, exploration_result: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract queries that can be replayed"""
        replayable = []
        
        for query_info in exploration_result.get("query_history", []):
            replayable.append({
                "purpose": query_info.get("purpose", ""),
                "query": query_info.get("query", ""),
                "expected_rows": query_info.get("row_count", 0),
                "can_validate": True  # Can check if returns similar row count
            })
        
        return replayable
    
    def _generate_markdown_report(self, export_data: Dict[str, Any]) -> str:
        """Generate readable markdown report"""
        report = f"""# SQL Exploration Report

**Session ID:** {export_data['session_id']}  
**Date:** {export_data['exported_at']}  
**Database:** {export_data['database']}  

## Question
{export_data['question']}

## Answer
{export_data['exploration_result'].get('answer', 'No answer generated')}

**Confidence:** {export_data['exploration_result'].get('confidence', 0):.1%}  
**Method:** {'MCP Pattern Reuse' if export_data.get('used_mcp_pattern') else 'Fresh Exploration'}

## Exploration Process

### Summary
- **Iterations:** {export_data['exploration_result'].get('iterations_used', 0)}
- **Queries Executed:** {export_data['exploration_result'].get('queries_executed', 0)}
- **Tables Discovered:** {len(export_data['exploration_result'].get('discovered_schema', {}))}

### Query Sequence
"""
        # Add query details
        for i, query in enumerate(export_data.get('replayable_queries', []), 1):
            report += f"\n#### Query {i}: {query['purpose']}\n"
            report += f"```sql\n{query['query']}\n```\n"
            report += f"*Expected rows: {query['expected_rows']}*\n"
        
        # Add reasoning if available
        if export_data.get('explanations'):
            report += "\n## Detailed Reasoning\n"
            for iteration in export_data['explanations'].get('detailed_reasoning', []):
                report += f"\n### Iteration {iteration['iteration']}\n"
                for decision in iteration.get('decisions', []):
                    report += f"- **{decision['type']}**: {decision['reasoning']}\n"
        
        # Add validation info
        if export_data.get('validation_info'):
            report += "\n## Validation Information\n"
            report += f"- **Required Tables:** {', '.join(export_data['validation_info']['required_tables'])}\n"
            report += f"- **Schema Fingerprint:** {export_data['validation_info']['schema_fingerprint']}\n"
        
        return report


class AutonomousSQLExplorer:
    """Enhanced autonomous explorer using MCP for pattern management"""
    
    def __init__(self, sql_translator, query_executor):
        self.translator = sql_translator
        self.executor = query_executor
        self.max_iterations = 10
        
        # Initialize components
        self.explanation_tracker = ExplanationTracker()
        self.exporter = ExplorationExporter()
        
        # MCP client reference (will be set by bot)
        self.mcp_client = None
        
        # Discovery queries
        self.discovery_queries = {
            "schema_overview": """
                SELECT TABLE_SCHEMA, TABLE_NAME, 
                       (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c 
                        WHERE c.TABLE_NAME = t.TABLE_NAME) as column_count
                FROM INFORMATION_SCHEMA.TABLES t
                WHERE TABLE_TYPE = 'BASE TABLE'
            """,
            "table_relationships": """
                SELECT 
                    fk.name AS constraint_name,
                    tp.name AS parent_table,
                    tr.name AS referenced_table
                FROM sys.foreign_keys AS fk
                INNER JOIN sys.tables AS tp ON fk.parent_object_id = tp.object_id
                INNER JOIN sys.tables AS tr ON fk.referenced_object_id = tr.object_id
            """,
            "column_details": """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, 
                       IS_NULLABLE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{table_name}'
            """,
            "sample_data": """
                SELECT TOP 5 * FROM [{table_name}]
            """,
            "statistics": """
                SELECT 
                    '{table_name}' as table_name,
                    COUNT(*) as row_count,
                    COUNT(DISTINCT {column_name}) as distinct_values
                FROM [{table_name}]
            """
        }
    
    def set_mcp_client(self, mcp_client):
        """Set MCP client reference"""
        self.mcp_client = mcp_client
    
    async def explore_and_answer(self, user_question: str, database: str,
                                enable_learning: bool = True,
                                enable_explanation: bool = True,
                                export_session: bool = True) -> Dict[str, Any]:
        """
        Enhanced exploration using MCP patterns
        """
        # Initialize context
        context = {
            "question": user_question,
            "database": database,
            "discovered_schema": {},
            "query_results": [],
            "iterations": 0,
            "final_answer": None,
            "confidence": 0.0,
            "using_mcp_pattern": False,
            "pattern_id": None,
            "iterations_used": 0,
            "queries_executed": 0,
            "query_history": [],
            "total_execution_time": 0
        }
        
        start_time = datetime.now()
        
        # Get current schema hash for pattern validation
        schema_hash = await self._get_schema_hash(database)
        
        # Check for MCP patterns if available
        if enable_learning and self.mcp_client:
            try:
                pattern_result = await self.mcp_client.call_tool(
                    "find_pattern",
                    question=user_question,
                    database=database,
                    schema_hash=schema_hash
                )
                
                if pattern_result.get("found") and pattern_result.get("patterns"):
                    best_pattern = pattern_result["patterns"][0]
                    context["using_mcp_pattern"] = True
                    context["pattern_id"] = best_pattern.get("pattern_id")
                    
                    if enable_explanation:
                        self.explanation_tracker.add_decision(
                            "pattern_reuse",
                            f"Found MCP pattern with {best_pattern['similarity_score']:.1%} similarity and {best_pattern['confidence']:.1%} confidence",
                            {
                                "pattern_id": best_pattern.get("pattern_id"),
                                "use_count": best_pattern.get("use_count", 0),
                                "avg_time": best_pattern.get("avg_execution_time", 0)
                            }
                        )
                    
                    # Try to reuse pattern
                    reuse_result = await self._try_mcp_pattern_reuse(
                        context, best_pattern, schema_hash
                    )
                    
                    if reuse_result["success"]:
                        context["final_answer"] = reuse_result["answer"]
                        context["confidence"] = reuse_result["confidence"]
                        context["iterations_used"] = 1
                        context["queries_executed"] = len(context["query_results"])
                        context["total_execution_time"] = (datetime.now() - start_time).total_seconds() * 1000
                        
                        # Update pattern performance in MCP
                        if best_pattern.get("pattern_id"):
                            await self.mcp_client.call_tool(
                                "update_pattern_performance",
                                pattern_id=best_pattern["pattern_id"],
                                execution_time=context["total_execution_time"],
                                success=True
                            )
                        
                        # Skip to export
                        if export_session:
                            export_file = self.exporter.export_session(
                                context,
                                self.explanation_tracker.get_explanation_summary() if enable_explanation else {},
                                database,
                                user_question
                            )
                            context["export_file"] = export_file
                        
                        return self._ensure_required_fields(context)
                    else:
                        # Pattern reuse failed, update MCP
                        if best_pattern.get("pattern_id"):
                            await self.mcp_client.call_tool(
                                "update_pattern_performance",
                                pattern_id=best_pattern["pattern_id"],
                                execution_time=0,
                                success=False,
                                error="Pattern reuse failed"
                            )
            except Exception as e:
                logger.warning(f"Failed to check MCP patterns: {e}")
        
        # Standard exploration process
        while context["iterations"] < self.max_iterations:
            context["iterations"] += 1
            context["iterations_used"] = context["iterations"]
            
            if enable_explanation:
                self.explanation_tracker.start_iteration(
                    context["iterations"], context
                )
            
            # Determine next action
            next_action = await self._determine_next_action(context)
            
            if enable_explanation:
                self.explanation_tracker.add_decision(
                    "action_selection",
                    f"Decided to: {next_action['type']}",
                    {"reasoning": next_action.get("reasoning", "")}
                )
            
            if next_action["type"] == "query":
                # Execute query with explanation
                if enable_explanation:
                    self.explanation_tracker.add_query_reasoning(
                        next_action["query"],
                        next_action.get("purpose", "Data gathering"),
                        next_action.get("expected_outcome", "Unknown")
                    )
                
                query_start = datetime.now()
                result = await self._execute_safe_query(
                    next_action["query"], 
                    database
                )
                query_time = (datetime.now() - query_start).total_seconds() * 1000
                
                result["purpose"] = next_action.get("purpose", "")
                result["execution_time"] = query_time
                context["query_results"].append(result)
                context["query_history"].append(result)
                context["queries_executed"] += 1
                context["total_execution_time"] += query_time
                
                # Update discovered schema if relevant
                if "information_schema" in next_action["query"].lower():
                    await self._update_discovered_schema(context, result)
                
                # Check completeness
                is_complete = await self._check_answer_completeness(context)
                
                if is_complete["complete"]:
                    context["final_answer"] = is_complete["answer"]
                    context["confidence"] = is_complete["confidence"]
                    
                    if enable_explanation:
                        self.explanation_tracker.add_decision(
                            "breakthrough",
                            "Found complete answer",
                            {"confidence": is_complete["confidence"]}
                        )
                    break
            
            elif next_action["type"] == "complete":
                context["final_answer"] = next_action["answer"]
                context["confidence"] = next_action["confidence"]
                break
            
            elif next_action["type"] == "need_more_info":
                # Explore more schema
                await self._explore_additional_tables(
                    context, 
                    next_action.get("tables", [])
                )
            
            if enable_explanation:
                self.explanation_tracker.complete_iteration(
                    f"Continuing exploration, confidence: {context['confidence']:.1%}"
                )
        
        # Set final answer if not set
        if not context["final_answer"]:
            context["final_answer"] = "Could not find complete answer within iteration limit"
            context["confidence"] = 0.5
        
        context["total_execution_time"] = (datetime.now() - start_time).total_seconds() * 1000
        
        # Learn from successful exploration in MCP
        if enable_learning and self.mcp_client and context["confidence"] > 0.8:
            try:
                # Extract query sequence for pattern
                query_sequence = []
                for q in context["query_history"]:
                    query_sequence.append({
                        "purpose": q.get("purpose", ""),
                        "query": q.get("query", ""),
                        "row_count": q.get("row_count", 0)
                    })
                
                # Send to MCP for learning
                await self.mcp_client.call_tool(
                    "learn_pattern",
                    question=user_question,
                    database=database,
                    query_sequence=query_sequence,
                    discovered_tables=list(context["discovered_schema"].keys()),
                    execution_time=context["total_execution_time"],
                    confidence=context["confidence"],
                    schema_hash=schema_hash,
                    total_rows=sum(q.get("row_count", 0) for q in context["query_history"])
                )
            except Exception as e:
                logger.warning(f"Failed to learn pattern in MCP: {e}")
        
        # Export session
        if export_session:
            export_file = self.exporter.export_session(
                context,
                self.explanation_tracker.get_explanation_summary() if enable_explanation else {},
                database,
                user_question
            )
            context["export_file"] = export_file
        
        # Add explanation summary
        if enable_explanation:
            context["explanation_summary"] = self.explanation_tracker.get_explanation_summary()
        
        return self._ensure_required_fields(context)
    
    async def _get_schema_hash(self, database: str) -> str:
        """Get current schema hash from MCP or calculate it"""
        if self.mcp_client:
            try:
                # Get from MCP cache
                context = await self.mcp_client.call_tool(
                    "get_database_context",
                    database=database
                )
                return context.get("schema_hash", "")
            except:
                pass
        
        # Fallback: calculate locally
        schema_query = """
            SELECT 
                CHECKSUM_AGG(CHECKSUM(
                    TABLE_SCHEMA + TABLE_NAME + COLUMN_NAME + DATA_TYPE
                )) as schema_checksum
            FROM INFORMATION_SCHEMA.COLUMNS
        """
        
        result = await self._execute_safe_query(schema_query, database)
        if result.get("rows") and result["rows"][0].get("schema_checksum"):
            return str(result["rows"][0]["schema_checksum"])
        
        return ""
    
    async def _try_mcp_pattern_reuse(self, context: Dict, pattern: Dict, 
                                   schema_hash: str) -> Dict[str, Any]:
        """Try to reuse an MCP pattern"""
        try:
            # Run the query sequence from the pattern
            for query_info in pattern["query_sequence"]:
                # Adapt query if needed
                query = query_info.get("query", "")
                
                result = await self._execute_safe_query(query, context["database"])
                result["purpose"] = query_info.get("purpose", "")
                context["query_results"].append(result)
                context["query_history"].append(result)
            
            # Check if we got meaningful results
            if context["query_results"] and not any(r.get("error") for r in context["query_results"]):
                # Generate answer based on results
                answer = await self._generate_answer_from_results(
                    context["question"],
                    context["query_results"]
                )
                
                return {
                    "success": True,
                    "answer": answer["answer"],
                    "confidence": answer["confidence"] * pattern.get("confidence", 0.8)
                }
        
        except Exception as e:
            logger.error(f"MCP pattern reuse failed: {e}")
        
        return {"success": False}
    
    async def _update_discovered_schema(self, context: Dict, result: Dict):
        """Update discovered schema from query results"""
        if not result.get("rows"):
            return
        
        # Group by table
        for row in result["rows"]:
            table_name = row.get("TABLE_NAME")
            if table_name and table_name not in context["discovered_schema"]:
                context["discovered_schema"][table_name] = {
                    "columns": [],
                    "discovered_at": datetime.now().isoformat()
                }
            
            if table_name and "COLUMN_NAME" in row:
                context["discovered_schema"][table_name]["columns"].append(row)
    
    async def _determine_next_action(self, context: Dict) -> Dict[str, Any]:
        """Use AI to determine next action based on current context"""
        # First iteration - analyze the question
        if context["iterations"] == 1:
            return await self._analyze_and_start(context)
        
        # Build prompt for next action
        prompt = f"""You are helping answer this question: {context['question']}

Current context:
- Database: {context['database']}
- Discovered tables: {list(context['discovered_schema'].keys())}
- Previous queries executed: {len(context['query_results'])}
- Iterations so far: {context['iterations']}

Previous query results summary:
{self._summarize_results(context['query_results'][-3:])}

Determine the next action:
1. If you have enough information to answer completely, return type "complete"
2. If you need to run another query, return type "query" with the SQL
3. If you need to explore more tables, return type "need_more_info"

Respond with JSON:
{{
    "type": "query|complete|need_more_info",
    "query": "SQL query if type is query",
    "answer": "final answer if type is complete",
    "confidence": 0.0-1.0,
    "reasoning": "explain your decision",
    "tables": ["additional tables to explore if type is need_more_info"],
    "purpose": "what this query will help determine",
    "expected_outcome": "what you expect to find"
}}"""
        
        response = await self.translator.client.chat.completions.create(
            model=self.translator.deployment_name,
            messages=[
                {"role": "system", "content": self.translator.system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _analyze_and_start(self, context: Dict) -> Dict[str, Any]:
        """Analyze question and determine first query"""
        prompt = f"""Analyze this database question: {context['question']}
Database: {context['database']}

Determine the best first query to start answering this question.
Consider:
1. What tables might contain the needed information?
2. Should we start with schema discovery or go directly to data?
3. What's the most efficient path to the answer?

Respond with JSON:
{{
    "type": "query",
    "query": "the SQL query to execute",
    "purpose": "what this query will discover",
    "expected_outcome": "what you expect to find",
    "reasoning": "why this is the best starting point"
}}"""
        
        response = await self.translator.client.chat.completions.create(
            model=self.translator.deployment_name,
            messages=[
                {"role": "system", "content": self.translator.system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _check_answer_completeness(self, context: Dict) -> Dict[str, Any]:
        """Check if we have enough information to answer the question"""
        prompt = f"""Evaluate if we have enough information to answer this question completely:

Question: {context['question']}

Information gathered:
{json.dumps(self._summarize_results(context['query_results']), indent=2)}

Can you provide a complete, accurate answer now?

Respond with JSON:
{{
    "complete": true/false,
    "answer": "the complete answer if true, or what's missing if false",
    "confidence": 0.0-1.0,
    "missing_information": ["list what's still needed if not complete"]
}}"""
        
        response = await self.translator.client.chat.completions.create(
            model=self.translator.deployment_name,
            messages=[
                {"role": "system", "content": "You are a data analyst providing accurate answers."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _execute_safe_query(self, query: str, database: str) -> Dict[str, Any]:
        """Execute query with safety checks"""
        # Import validator
        from query_validator import QueryValidator

        
        # Validate query safety
        is_safe, error = QueryValidator.is_query_safe(query)
        if not is_safe:
            return {"error": error, "query": query, "row_count": 0}
        
        # Add safety limits
        safe_query = QueryValidator.add_safety_limits(query)
        
        # Execute through the bot's executor
        result = await self.executor._execute_sql_query(
            type("SQLQuery", (), {
                "query": safe_query,
                "database": database,
                "explanation": "Autonomous exploration",
                "confidence": 1.0,
                "complexity": "simple",
                "warnings": []
            })(),
            "raw"
        )
        
        return {
            "query": safe_query,
            "rows": result.get("rows", []),
            "row_count": result.get("row_count", 0),
            "execution_time": result.get("execution_time_ms", 0),
            "error": result.get("error")
        }
    
    def _summarize_results(self, results: List[Dict]) -> List[Dict]:
        """Summarize results for context"""
        summaries = []
        for r in results:
            summary = {
                "query": r["query"][:100] + "..." if len(r["query"]) > 100 else r["query"],
                "purpose": r.get("purpose", "Unknown"),
                "row_count": r.get("row_count", 0),
                "error": r.get("error"),
                "sample_data": r.get("rows", [])[:3] if r.get("rows") else []
            }
            summaries.append(summary)
        return summaries
    
    async def _generate_answer_from_results(self, question: str, 
                                          results: List[Dict]) -> Dict[str, Any]:
        """Generate answer from query results using AI"""
        prompt = f"""Based on these query results, answer the question:

Question: {question}

Query Results:
{json.dumps([{
    "purpose": r.get("purpose", ""),
    "row_count": r.get("row_count", 0),
    "sample_data": r.get("rows", [])[:5]
} for r in results], indent=2)}

Provide a complete answer with confidence level.

Respond with JSON:
{{
    "answer": "your complete answer",
    "confidence": 0.0-1.0,
    "key_findings": ["list of key findings"]
}}"""
        
        response = await self.translator.client.chat.completions.create(
            model=self.translator.deployment_name,
            messages=[
                {"role": "system", "content": "You are a data analyst providing accurate answers based on query results."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _explore_additional_tables(self, context: Dict, tables: List[str]):
        """Explore additional tables"""
        for table_name in tables[:3]:  # Limit to 3 tables
            if table_name not in context["discovered_schema"]:
                # Get column details
                columns_result = await self._execute_safe_query(
                    self.discovery_queries["column_details"].format(table_name=table_name),
                    context["database"]
                )
                
                # Get sample data
                sample_result = await self._execute_safe_query(
                    self.discovery_queries["sample_data"].format(table_name=table_name),
                    context["database"]
                )
                
                context["discovered_schema"][table_name] = {
                    "columns": columns_result["rows"],
                    "sample_data": sample_result["rows"]
                }
    
    def _ensure_required_fields(self, context: Dict) -> Dict[str, Any]:
        """Ensure context has all required fields for compatibility"""
        # Required fields
        context["answer"] = context.get("final_answer", "No answer generated")
        
        # Ensure numeric fields
        context["confidence"] = float(context.get("confidence", 0.0))
        context["iterations_used"] = int(context.get("iterations_used", 0))
        context["queries_executed"] = int(context.get("queries_executed", 0))
        
        return context