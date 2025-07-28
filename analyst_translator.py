# analyst_translator.py - Natural Language to DAX Query Translator
"""
Analyst Translator - Converts natural language business queries to DAX queries
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
class DAXQuery:
    """Represents a translated DAX query"""
    query: str
    explanation: str
    measures_used: List[str]
    tables_referenced: List[str]
    confidence: float
    requires_time_intelligence: bool
    error: Optional[str] = None

@dataclass
class TranslationContext:
    """Context for query translation"""
    dataset_metadata: Dict[str, Any]
    available_measures: List[str]
    available_tables: List[str]
    business_context: Dict[str, Any]
    query_history: List[str] = field(default_factory=list)

class AnalystTranslator:
    """Translates natural language queries to DAX using Azure OpenAI"""
    
    def __init__(self):
        # Azure OpenAI configuration (reuse from main translator)
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        if not self.endpoint or not self.api_key:
            logger.warning("Azure OpenAI not configured for analyst translator")
            self.client = None
        else:
            self.client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version="2024-02-01"
            )
        
        # System prompts
        self.system_prompt = self._create_system_prompt()
        self.error_analysis_prompt = self._create_error_analysis_prompt()
        
        # Common DAX patterns
        self.dax_patterns = self._load_dax_patterns()
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for DAX translation"""
        return """You are an expert Power BI DAX query translator specializing in business analytics.
Your role is to convert natural language business questions into accurate, efficient DAX queries.

CONTEXT:
- You're translating queries for business users who want insights from their Power BI models
- The models contain standard business measures and dimensions
- Focus on providing actionable business insights, not just raw data

DAX QUERY GUIDELINES:
1. Always use EVALUATE to return results
2. Use SUMMARIZECOLUMNS for grouping and aggregation
3. Use CALCULATE for measure modifications
4. Use time intelligence functions (SAMEPERIODLASTYEAR, DATEADD, etc.) for time comparisons
5. Include appropriate sorting with ORDER BY
6. Limit results with TOPN when asking for "top" or "best"

COMMON PATTERNS:
- Revenue analysis: Use [Total Revenue], [Revenue YoY], [Revenue MoM]
- Customer metrics: Use [Customer Count], [Average Order Value], [Customer Lifetime Value]
- Product analysis: Use [Units Sold], [Product Margin], [Inventory Turnover]
- Time comparisons: Use CALCULATE with time intelligence functions

SAFETY:
- Only generate read queries (no data modification)
- Validate measure and table names against available metadata
- Use proper DAX syntax with appropriate brackets for measures/columns

RESPONSE FORMAT:
Always respond with a JSON object containing:
{
    "query": "the DAX query",
    "explanation": "what this query does in business terms",
    "measures_used": ["list of measures"],
    "tables_referenced": ["list of tables"],
    "confidence": 0.0-1.0,
    "requires_time_intelligence": true/false
}"""

    def _create_error_analysis_prompt(self) -> str:
        """Create the error analysis prompt for DAX errors"""
        return """You are an expert Power BI DAX debugger helping business users fix query errors.
Analyze DAX errors and provide corrected queries that work with Power BI datasets.

COMMON DAX ERRORS:
1. Measure not found: Check measure name spelling and brackets [Measure Name]
2. Column not found: Verify table name and use 'Table'[Column] syntax
3. Syntax errors: Ensure proper use of commas, parentheses, and functions
4. Context errors: Use CALCULATE to modify filter context properly
5. Type mismatches: Ensure correct data types in comparisons

ERROR FIXING APPROACH:
1. Identify the specific error type
2. Explain what went wrong in simple terms
3. Provide the corrected DAX query
4. Suggest alternative approaches if applicable

RESPONSE FORMAT:
Always respond with a JSON object containing:
{
    "error_type": "syntax|measure_not_found|column_not_found|context|other",
    "explanation": "what went wrong in business terms",
    "fixed_query": "the corrected DAX query",
    "confidence": 0.0-1.0,
    "alternative_approaches": ["other ways to get this information"]
}"""

    def _load_dax_patterns(self) -> Dict[str, str]:
        """Load common DAX query patterns"""
        return {
            "top_n_by_measure": """
EVALUATE
TOPN(
    {n},
    SUMMARIZECOLUMNS(
        {dimension},
        "{measure_name}", {measure}
    ),
    {measure}, DESC
)
""",
            "time_comparison": """
EVALUATE
SUMMARIZECOLUMNS(
    {time_dimension},
    "Current Period", {measure},
    "Previous Period", CALCULATE({measure}, SAMEPERIODLASTYEAR({date_column})),
    "YoY Change", DIVIDE({measure} - CALCULATE({measure}, SAMEPERIODLASTYEAR({date_column})), CALCULATE({measure}, SAMEPERIODLASTYEAR({date_column})))
)
ORDER BY {time_dimension} DESC
""",
            "breakdown_by_dimension": """
EVALUATE
SUMMARIZECOLUMNS(
    {dimension},
    "{measure_name}", {measure},
    "Percentage", DIVIDE({measure}, CALCULATE({measure}, ALL({dimension})))
)
ORDER BY {measure} DESC
""",
            "multi_measure_summary": """
EVALUATE
ROW(
    {measure_list}
)
""",
            "filtered_analysis": """
EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        {dimension},
        "{measure_name}", {measure}
    ),
    {filter_expression}
)
ORDER BY {measure} DESC
""",
            "trend_analysis": """
EVALUATE
SUMMARIZECOLUMNS(
    {date_dimension},
    "Value", {measure},
    "3 Month Avg", AVERAGEX(DATESINPERIOD({date_column}, LASTDATE({date_column}), -3, MONTH), {measure}),
    "Trend", {measure} - CALCULATE({measure}, DATEADD({date_column}, -1, MONTH))
)
ORDER BY {date_dimension}
"""
        }
    
    async def translate_to_dax(self, 
                             natural_language_query: str,
                             context: TranslationContext) -> DAXQuery:
        """Translate natural language query to DAX"""
        
        if not self.client:
            # Fallback to pattern matching if OpenAI not available
            return self._pattern_based_translation(natural_language_query, context)
        
        try:
            # Build the context message
            context_message = self._build_context_message(natural_language_query, context)
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context_message}
            ]
            
            logger.info(f"Translating to DAX: {natural_language_query[:100]}...")
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate the query against available metadata
            validated_query = self._validate_dax_query(result["query"], context)
            
            return DAXQuery(
                query=validated_query,
                explanation=result.get("explanation", ""),
                measures_used=result.get("measures_used", []),
                tables_referenced=result.get("tables_referenced", []),
                confidence=float(result.get("confidence", 0.8)),
                requires_time_intelligence=result.get("requires_time_intelligence", False)
            )
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            # Fallback to pattern matching
            return self._pattern_based_translation(natural_language_query, context)
    
    async def analyze_dax_error(self,
                               failed_query: str,
                               error_message: str,
                               context: TranslationContext) -> Dict[str, Any]:
        """Analyze DAX error and suggest fixes"""
        
        if not self.client:
            return self._basic_error_analysis(failed_query, error_message, context)
        
        try:
            error_context = f"""
Failed DAX Query:
{failed_query}

Error Message:
{error_message}

Available Measures:
{', '.join(context.available_measures[:20])}

Available Tables:
{', '.join(context.available_tables[:20])}
"""
            
            messages = [
                {"role": "system", "content": self.error_analysis_prompt},
                {"role": "user", "content": error_context}
            ]
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.2,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "error_type": result.get("error_type", "unknown"),
                "explanation": result.get("explanation", "Unable to determine error cause"),
                "fixed_query": result.get("fixed_query", failed_query),
                "confidence": float(result.get("confidence", 0.5)),
                "alternative_approaches": result.get("alternative_approaches", [])
            }
            
        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            return self._basic_error_analysis(failed_query, error_message, context)
    
    def _build_context_message(self, query: str, context: TranslationContext) -> str:
        """Build context message for translation"""
        
        # Sample of available measures and tables
        measures_sample = context.available_measures[:30] if context.available_measures else []
        tables_sample = context.available_tables[:20] if context.available_tables else []
        
        message = f"""
Business Question: {query}

Available Measures (sample):
{', '.join(f'[{m}]' for m in measures_sample)}

Available Tables:
{', '.join(tables_sample)}

Additional Context:
- Current date context should use TODAY() or NOW()
- Fiscal year starts in {context.business_context.get('fiscal_year_start', 'January')}
- Default currency is {context.business_context.get('currency', 'USD')}
"""
        
        # Add recent query context if available
        if context.query_history:
            recent = context.query_history[-1]
            message += f"\n\nPrevious query was about: {recent}"
        
        return message
    
    def _pattern_based_translation(self, query: str, context: TranslationContext) -> DAXQuery:
        """Fallback pattern-based translation when AI is not available"""
        query_lower = query.lower()
        
        # Detect query intent
        if "top" in query_lower and any(word in query_lower for word in ["revenue", "sales", "customer"]):
            # Top N pattern
            measure = "[Total Revenue]"  # Default
            dimension = "'Product'[Product Name]"  # Default
            n = 10
            
            # Extract number if specified
            import re
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                n = int(numbers[0])
            
            # Determine measure
            if "customer" in query_lower:
                measure = "[Customer Count]"
                dimension = "'Customer'[Customer Name]"
            elif "product" in query_lower:
                dimension = "'Product'[Product Name]"
            
            dax = self.dax_patterns["top_n_by_measure"].format(
                n=n,
                dimension=dimension,
                measure_name=measure.strip("[]"),
                measure=measure
            )
            
            return DAXQuery(
                query=dax.strip(),
                explanation=f"Shows top {n} by {measure}",
                measures_used=[measure],
                tables_referenced=[dimension.split("'")[1]],
                confidence=0.7,
                requires_time_intelligence=False
            )
        
        elif any(word in query_lower for word in ["compare", "vs", "versus", "last year"]):
            # Time comparison pattern
            measure = "[Total Revenue]"
            time_dim = "'Date'[Month]"
            date_col = "'Date'[Date]"
            
            dax = self.dax_patterns["time_comparison"].format(
                time_dimension=time_dim,
                measure=measure,
                date_column=date_col
            )
            
            return DAXQuery(
                query=dax.strip(),
                explanation="Compares current period with previous period",
                measures_used=[measure],
                tables_referenced=["Date"],
                confidence=0.6,
                requires_time_intelligence=True
            )
        
        else:
            # Default summary query
            measures = []
            if "revenue" in query_lower:
                measures.append('"Total Revenue", [Total Revenue]')
            if "customer" in query_lower:
                measures.append('"Customer Count", [Customer Count]')
            if "profit" in query_lower:
                measures.append('"Total Profit", [Total Profit]')
            
            if not measures:
                measures = ['"Total Revenue", [Total Revenue]']
            
            dax = self.dax_patterns["multi_measure_summary"].format(
                measure_list=",\n    ".join(measures)
            )
            
            return DAXQuery(
                query=dax.strip(),
                explanation="Summary of key metrics",
                measures_used=[m.split(",")[1].strip().strip("]") + "]" for m in measures],
                tables_referenced=[],
                confidence=0.5,
                requires_time_intelligence=False
            )
    
    def _validate_dax_query(self, query: str, context: TranslationContext) -> str:
        """Validate and potentially fix DAX query based on available metadata"""
        # This is a simplified validation - in production, implement more thorough checks
        
        # Check if measures exist (basic check)
        for measure in context.available_measures:
            # Ensure measures are properly bracketed
            if measure in query and f"[{measure}]" not in query:
                query = query.replace(measure, f"[{measure}]")
        
        return query
    
    def _basic_error_analysis(self, query: str, error: str, context: TranslationContext) -> Dict[str, Any]:
        """Basic error analysis without AI"""
        error_lower = error.lower()
        
        if "not found" in error_lower or "cannot find" in error_lower:
            # Try to identify what's not found
            if "measure" in error_lower:
                return {
                    "error_type": "measure_not_found",
                    "explanation": "The measure referenced in the query doesn't exist",
                    "fixed_query": query,  # Can't fix without knowing correct measure
                    "confidence": 0.3,
                    "alternative_approaches": [
                        "Check available measures in the dataset",
                        "Try using a similar measure name"
                    ]
                }
            elif "column" in error_lower or "table" in error_lower:
                return {
                    "error_type": "column_not_found",
                    "explanation": "A table or column referenced doesn't exist",
                    "fixed_query": query,
                    "confidence": 0.3,
                    "alternative_approaches": [
                        "Verify table and column names",
                        "Check if the table is in the current dataset"
                    ]
                }
        
        elif "syntax" in error_lower:
            return {
                "error_type": "syntax",
                "explanation": "The DAX query has a syntax error",
                "fixed_query": query,
                "confidence": 0.2,
                "alternative_approaches": [
                    "Check for missing commas or parentheses",
                    "Verify function syntax"
                ]
            }
        
        return {
            "error_type": "other",
            "explanation": "An error occurred executing the query",
            "fixed_query": query,
            "confidence": 0.1,
            "alternative_approaches": [
                "Simplify the query",
                "Check error details for specific issues"
            ]
        }
    
    def suggest_follow_up_queries(self, 
                                query: str,
                                results: Any,
                                context: TranslationContext) -> List[Dict[str, str]]:
        """Suggest relevant follow-up queries based on results"""
        suggestions = []
        
        # Analyze what type of query was run
        query_lower = query.lower()
        
        if "revenue" in query_lower:
            suggestions.extend([
                {
                    "question": "What are the top contributing products?",
                    "purpose": "Identify revenue drivers"
                },
                {
                    "question": "How does this compare to last year?",
                    "purpose": "Year-over-year comparison"
                },
                {
                    "question": "Which regions are underperforming?",
                    "purpose": "Geographic analysis"
                }
            ])
        
        elif "customer" in query_lower:
            suggestions.extend([
                {
                    "question": "What is the customer retention rate?",
                    "purpose": "Loyalty analysis"
                },
                {
                    "question": "Which customer segments are most valuable?",
                    "purpose": "Segmentation analysis"
                },
                {
                    "question": "What is the average customer lifetime value?",
                    "purpose": "Value analysis"
                }
            ])
        
        elif any(word in query_lower for word in ["efficiency", "cost", "expense"]):
            suggestions.extend([
                {
                    "question": "What are the main cost drivers?",
                    "purpose": "Cost analysis"
                },
                {
                    "question": "How has efficiency changed over time?",
                    "purpose": "Trend analysis"
                },
                {
                    "question": "Which departments have the highest costs?",
                    "purpose": "Departmental analysis"
                }
            ])
        
        return suggestions[:3]  # Return top 3 suggestions

# Create singleton instance
analyst_translator = AnalystTranslator()

# Export
__all__ = ['AnalystTranslator', 'analyst_translator', 'DAXQuery', 'TranslationContext']