# analysis_agent.py - Intelligent Analysis Agent for Progressive Investigation
"""
Analysis Agent - Provides intelligent, progressive analysis with automatic follow-up queries
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class AnalysisContext:
    """Context for an analysis session"""
    query: str
    dataset_id: str
    dataset_name: str
    initial_results: Dict[str, Any]
    follow_up_queries: List[Dict[str, Any]] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    business_context: Dict[str, Any] = field(default_factory=dict)
    investigation_depth: int = 0
    max_depth: int = 3

@dataclass
class AnalysisPattern:
    """Represents an analysis pattern for automatic investigation"""
    name: str
    trigger_conditions: List[str]
    follow_up_queries: List[Dict[str, str]]
    insight_template: str
    recommendation_templates: List[str]

@dataclass
class InsightResult:
    """Result of an analysis including insights and recommendations"""
    summary: str
    insights: List[str]
    recommendations: List[str]
    supporting_data: List[Dict[str, Any]]
    confidence: float
    investigation_complete: bool

class AnalysisAgent:
    """Intelligent agent for progressive business analysis"""
    
    def __init__(self, business_context_provider=None):
        self.business_context_provider = business_context_provider
        self.analysis_patterns = self._load_analysis_patterns()
        self.query_history = {}  # session_id -> list of queries
        self.kpi_thresholds = self._load_kpi_thresholds()
        
    def _load_analysis_patterns(self) -> List[AnalysisPattern]:
        """Load predefined analysis patterns"""
        patterns = [
            # Revenue Analysis Pattern
            AnalysisPattern(
                name="revenue_decline",
                trigger_conditions=[
                    "revenue.*down",
                    "revenue.*decrease",
                    "sales.*decline",
                    "revenue.*drop"
                ],
                follow_up_queries=[
                    {
                        "purpose": "Regional breakdown",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Geography'[Region],
                            "Revenue", [Total Revenue],
                            "Change %", [Revenue Change %],
                            "Prior Period", [Prior Period Revenue]
                        )
                        ORDER BY [Revenue Change %] ASC
                        """
                    },
                    {
                        "purpose": "Product category analysis",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Product'[Category],
                            "Revenue", [Total Revenue],
                            "Units", [Units Sold],
                            "Avg Price", DIVIDE([Total Revenue], [Units Sold]),
                            "Change %", [Revenue Change %]
                        )
                        ORDER BY [Revenue] DESC
                        """
                    },
                    {
                        "purpose": "Customer segment impact",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Customer'[Segment],
                            "Customer Count", DISTINCTCOUNT('Sales'[CustomerID]),
                            "Revenue", [Total Revenue],
                            "Avg Order Value", DIVIDE([Total Revenue], COUNTROWS('Sales')),
                            "Retention Rate", [Customer Retention Rate]
                        )
                        """
                    },
                    {
                        "purpose": "Time trend analysis",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Date'[Month],
                            "Revenue", [Total Revenue],
                            "YoY Change", [YoY Revenue Change],
                            "MoM Change", [MoM Revenue Change]
                        )
                        ORDER BY 'Date'[Month] DESC
                        """
                    }
                ],
                insight_template="Revenue decline of {decline_percent}% detected. Primary drivers: {drivers}",
                recommendation_templates=[
                    "Focus on {best_region} region which shows resilience with {region_performance}",
                    "Investigate pricing strategy for {declining_category} category showing {category_decline}% decline",
                    "Engage with {at_risk_segment} customer segment showing reduced activity"
                ]
            ),
            
            # Performance Comparison Pattern
            AnalysisPattern(
                name="performance_comparison",
                trigger_conditions=[
                    "compare.*performance",
                    "vs.*last",
                    "year.*over.*year",
                    "comparison"
                ],
                follow_up_queries=[
                    {
                        "purpose": "Period over period metrics",
                        "template": """
                        EVALUATE
                        VAR CurrentPeriod = [Total Revenue]
                        VAR PriorPeriod = [Prior Period Revenue]
                        VAR Growth = DIVIDE(CurrentPeriod - PriorPeriod, PriorPeriod)
                        RETURN
                        ROW(
                            "Current Period", CurrentPeriod,
                            "Prior Period", PriorPeriod,
                            "Growth Rate", Growth,
                            "Absolute Change", CurrentPeriod - PriorPeriod
                        )
                        """
                    },
                    {
                        "purpose": "Top performers",
                        "template": """
                        EVALUATE
                        TOPN(
                            10,
                            SUMMARIZECOLUMNS(
                                'Product'[Product Name],
                                "Revenue", [Total Revenue],
                                "Growth", [Revenue Growth %]
                            ),
                            [Growth], DESC
                        )
                        """
                    },
                    {
                        "purpose": "Bottom performers",
                        "template": """
                        EVALUATE
                        TOPN(
                            10,
                            SUMMARIZECOLUMNS(
                                'Product'[Product Name],
                                "Revenue", [Total Revenue],
                                "Decline", [Revenue Growth %]
                            ),
                            [Decline], ASC
                        )
                        """
                    }
                ],
                insight_template="Performance comparison shows {overall_trend} with {key_metric} change of {change_value}",
                recommendation_templates=[
                    "Capitalize on success of {top_performer} showing {top_growth}% growth",
                    "Address underperformance in {bottom_performer} with {bottom_decline}% decline",
                    "Replicate strategies from {period} which showed better performance"
                ]
            ),
            
            # Customer Analysis Pattern
            AnalysisPattern(
                name="customer_analysis",
                trigger_conditions=[
                    "customer.*satisfaction",
                    "customer.*churn",
                    "customer.*retention",
                    "nps.*score"
                ],
                follow_up_queries=[
                    {
                        "purpose": "Satisfaction breakdown",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Survey'[Category],
                            "Avg Score", AVERAGE('Survey'[Score]),
                            "Response Count", COUNTROWS('Survey'),
                            "Detractor %", [Detractor Percentage]
                        )
                        ORDER BY [Avg Score] ASC
                        """
                    },
                    {
                        "purpose": "Churn risk analysis",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Customer'[Risk Level],
                            "Customer Count", DISTINCTCOUNT('Customer'[CustomerID]),
                            "Revenue at Risk", [Revenue at Risk],
                            "Avg Lifetime Value", AVERAGE('Customer'[Lifetime Value])
                        )
                        """
                    },
                    {
                        "purpose": "Retention drivers",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Customer'[Tenure Bucket],
                            "Retention Rate", [Customer Retention Rate],
                            "Avg Purchase Frequency", [Purchase Frequency],
                            "Avg Order Value", [Average Order Value]
                        )
                        """
                    }
                ],
                insight_template="Customer satisfaction at {satisfaction_score} with {key_driver} as primary concern",
                recommendation_templates=[
                    "Improve {problem_area} which has lowest satisfaction score of {low_score}",
                    "Implement retention program for {risk_segment} with {churn_risk}% churn risk",
                    "Focus on {high_value_segment} representing {revenue_percent}% of revenue"
                ]
            ),
            
            # Operational Efficiency Pattern
            AnalysisPattern(
                name="operational_efficiency",
                trigger_conditions=[
                    "efficiency",
                    "productivity",
                    "operational.*performance",
                    "cost.*optimization"
                ],
                follow_up_queries=[
                    {
                        "purpose": "Cost breakdown",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Cost'[Category],
                            "Total Cost", SUM('Cost'[Amount]),
                            "Cost per Unit", [Cost per Unit],
                            "YoY Change", [Cost YoY Change]
                        )
                        ORDER BY [Total Cost] DESC
                        """
                    },
                    {
                        "purpose": "Efficiency metrics",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Operations'[Department],
                            "Efficiency Score", [Operational Efficiency Score],
                            "Output per Hour", [Output per Hour],
                            "Resource Utilization", [Resource Utilization Rate]
                        )
                        """
                    },
                    {
                        "purpose": "Bottleneck analysis",
                        "template": """
                        EVALUATE
                        SUMMARIZECOLUMNS(
                            'Process'[Stage],
                            "Avg Duration", AVERAGE('Process'[Duration]),
                            "Bottleneck Score", [Bottleneck Score],
                            "Wait Time", AVERAGE('Process'[Wait Time])
                        )
                        ORDER BY [Bottleneck Score] DESC
                        """
                    }
                ],
                insight_template="Operational efficiency at {efficiency_score}% with {bottleneck} as main constraint",
                recommendation_templates=[
                    "Optimize {bottleneck_process} reducing {wait_time} hours of wait time",
                    "Reduce {highest_cost} costs showing {cost_increase}% increase",
                    "Improve {lowest_efficiency} department efficiency from {current}% to target {target}%"
                ]
            )
        ]
        
        return patterns
    
    def _load_kpi_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load KPI thresholds for intelligent alerting"""
        return {
            "revenue_change": {
                "critical_decline": -10.0,
                "warning_decline": -5.0,
                "good_growth": 5.0,
                "excellent_growth": 10.0
            },
            "customer_satisfaction": {
                "poor": 3.0,
                "fair": 3.5,
                "good": 4.0,
                "excellent": 4.5
            },
            "operational_efficiency": {
                "poor": 60.0,
                "fair": 70.0,
                "good": 80.0,
                "excellent": 90.0
            },
            "churn_rate": {
                "excellent": 5.0,
                "good": 10.0,
                "warning": 15.0,
                "critical": 20.0
            }
        }
    
    async def analyze_query_intent(self, query: str, business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the intent of a natural language query"""
        query_lower = query.lower()
        
        # Identify query type
        query_type = "general"
        focus_areas = []
        time_context = None
        
        # Time context detection
        if any(term in query_lower for term in ["today", "yesterday", "this week", "this month"]):
            time_context = "current_period"
        elif any(term in query_lower for term in ["last month", "last quarter", "last year"]):
            time_context = "previous_period"
        elif any(term in query_lower for term in ["ytd", "year to date"]):
            time_context = "year_to_date"
        
        # Focus area detection
        if any(term in query_lower for term in ["revenue", "sales", "income"]):
            focus_areas.append("revenue")
            query_type = "financial"
        if any(term in query_lower for term in ["customer", "client", "satisfaction", "nps"]):
            focus_areas.append("customer")
            query_type = "customer"
        if any(term in query_lower for term in ["cost", "expense", "efficiency", "productivity"]):
            focus_areas.append("operations")
            query_type = "operational"
        if any(term in query_lower for term in ["compare", "vs", "versus", "comparison"]):
            query_type = "comparison"
        
        # Find matching patterns
        matching_patterns = []
        for pattern in self.analysis_patterns:
            for condition in pattern.trigger_conditions:
                if re.search(condition, query_lower):
                    matching_patterns.append(pattern)
                    break
        
        return {
            "query_type": query_type,
            "focus_areas": focus_areas,
            "time_context": time_context,
            "matching_patterns": matching_patterns,
            "requires_deep_analysis": len(matching_patterns) > 0 or "why" in query_lower
        }
    
    async def perform_progressive_analysis(self, 
                                         initial_query: str,
                                         initial_results: Dict[str, Any],
                                         dataset_metadata: Dict[str, Any],
                                         powerbi_client,
                                         access_token: str) -> InsightResult:
        """Perform progressive analysis with automatic follow-up queries"""
        
        # Create analysis context
        context = AnalysisContext(
            query=initial_query,
            dataset_id=initial_results.get("dataset_id", ""),
            dataset_name=initial_results.get("dataset_name", ""),
            initial_results=initial_results,
            business_context=dataset_metadata
        )
        
        # Analyze query intent
        intent = await self.analyze_query_intent(initial_query, dataset_metadata)
        
        # Generate initial insights
        initial_insights = self._analyze_results(initial_results, intent)
        context.insights.extend(initial_insights["insights"])
        
        # Determine if follow-up analysis is needed
        if intent["requires_deep_analysis"] and intent["matching_patterns"]:
            # Perform follow-up queries
            for pattern in intent["matching_patterns"][:1]:  # Use first matching pattern
                follow_up_results = await self._execute_follow_up_queries(
                    pattern,
                    context,
                    powerbi_client,
                    access_token
                )
                
                # Analyze follow-up results
                for result in follow_up_results:
                    follow_up_insights = self._analyze_results(result["result"], intent)
                    context.insights.extend(follow_up_insights["insights"])
                
                # Generate recommendations based on pattern
                recommendations = self._generate_recommendations(
                    pattern,
                    context,
                    follow_up_results
                )
                context.recommendations.extend(recommendations)
        
        # Create final insight result
        return InsightResult(
            summary=self._generate_summary(context),
            insights=context.insights,
            recommendations=context.recommendations,
            supporting_data=context.follow_up_queries,
            confidence=self._calculate_confidence(context),
            investigation_complete=context.investigation_depth >= context.max_depth
        )
    
    async def _execute_follow_up_queries(self, 
                                       pattern: AnalysisPattern,
                                       context: AnalysisContext,
                                       powerbi_client,
                                       access_token: str) -> List[Dict[str, Any]]:
        """Execute follow-up queries based on pattern"""
        results = []
        
        for follow_up in pattern.follow_up_queries:
            try:
                # Execute the query
                result = await powerbi_client.execute_dax_query(
                    access_token,
                    context.dataset_id,
                    follow_up["template"],
                    context.dataset_name
                )
                
                if result.success:
                    context.follow_up_queries.append({
                        "purpose": follow_up["purpose"],
                        "query": follow_up["template"],
                        "result": result,
                        "row_count": result.row_count,
                        "insights": []
                    })
                    
                    results.append({
                        "purpose": follow_up["purpose"],
                        "result": result
                    })
                    
                context.investigation_depth += 1
                
                # Stop if we've reached max depth
                if context.investigation_depth >= context.max_depth:
                    break
                    
            except Exception as e:
                logger.error(f"Error executing follow-up query: {e}")
                
        return results
    
    def _analyze_results(self, results: Any, intent: Dict[str, Any]) -> Dict[str, List[str]]:
        """Analyze query results and extract insights"""
        insights = []
        
        if hasattr(results, 'data') and results.data:
            data = results.data
            
            # Analyze numeric trends
            numeric_columns = self._identify_numeric_columns(data)
            for col in numeric_columns:
                values = [row.get(col, 0) for row in data if row.get(col) is not None]
                if values:
                    avg_val = sum(values) / len(values)
                    max_val = max(values)
                    min_val = min(values)
                    
                    # Check against thresholds
                    threshold_insights = self._check_thresholds(col, avg_val)
                    insights.extend(threshold_insights)
                    
                    # Identify outliers
                    if max_val > avg_val * 2:
                        insights.append(f"Significant outlier detected in {col}: {max_val:.2f} (average: {avg_val:.2f})")
                    
                    # Identify trends
                    if len(values) > 3:
                        trend = self._calculate_trend(values)
                        if abs(trend) > 0.1:
                            direction = "increasing" if trend > 0 else "decreasing"
                            insights.append(f"{col} shows {direction} trend with {abs(trend):.1%} change rate")
        
        return {"insights": insights}
    
    def _generate_recommendations(self, 
                                pattern: AnalysisPattern,
                                context: AnalysisContext,
                                follow_up_results: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        # Extract key metrics from results
        metrics = self._extract_key_metrics(context, follow_up_results)
        
        # Generate recommendations using pattern templates
        for template in pattern.recommendation_templates:
            try:
                # Simple template filling (in production, use more sophisticated templating)
                recommendation = template
                for key, value in metrics.items():
                    placeholder = "{" + key + "}"
                    if placeholder in recommendation:
                        recommendation = recommendation.replace(placeholder, str(value))
                
                # Only add if all placeholders were filled
                if "{" not in recommendation:
                    recommendations.append(recommendation)
                    
            except Exception as e:
                logger.error(f"Error generating recommendation: {e}")
        
        return recommendations[:3]  # Return top 3 recommendations
    
    def _extract_key_metrics(self, 
                           context: AnalysisContext,
                           follow_up_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key metrics from analysis results"""
        metrics = {}
        
        # Extract from initial results
        if hasattr(context.initial_results, 'data') and context.initial_results.data:
            data = context.initial_results.data
            if data:
                # Get first row metrics
                first_row = data[0]
                for key, value in first_row.items():
                    if isinstance(value, (int, float)):
                        metrics[key.lower().replace(" ", "_")] = value
        
        # Extract from follow-up results
        for follow_up in follow_up_results:
            if follow_up["result"].success and follow_up["result"].data:
                # Find best/worst performers
                data = follow_up["result"].data
                if data:
                    if "region" in follow_up["purpose"].lower():
                        # Find best region
                        best = max(data, key=lambda x: x.get("Revenue", 0))
                        metrics["best_region"] = best.get("Region", "Unknown")
                        metrics["region_performance"] = f"{best.get('Change %', 0):.1f}%"
                    
                    elif "product" in follow_up["purpose"].lower():
                        # Find declining category
                        if any("Change %" in row for row in data):
                            worst = min(data, key=lambda x: x.get("Change %", 0))
                            metrics["declining_category"] = worst.get("Category", "Unknown")
                            metrics["category_decline"] = abs(worst.get("Change %", 0))
        
        return metrics
    
    def _generate_summary(self, context: AnalysisContext) -> str:
        """Generate executive summary of the analysis"""
        summary_parts = []
        
        # Start with query context
        summary_parts.append(f"Analysis of: {context.query}")
        
        # Add key insights count
        if context.insights:
            summary_parts.append(f"Found {len(context.insights)} key insights")
        
        # Add recommendation count
        if context.recommendations:
            summary_parts.append(f"Generated {len(context.recommendations)} actionable recommendations")
        
        # Add investigation depth
        if context.investigation_depth > 0:
            summary_parts.append(f"Performed {context.investigation_depth} follow-up investigations")
        
        return ". ".join(summary_parts)
    
    def _calculate_confidence(self, context: AnalysisContext) -> float:
        """Calculate confidence score for the analysis"""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on data availability
        if context.initial_results and hasattr(context.initial_results, 'row_count'):
            if context.initial_results.row_count > 0:
                confidence += 0.2
        
        # Increase confidence based on follow-up queries
        if context.follow_up_queries:
            confidence += min(0.2, len(context.follow_up_queries) * 0.05)
        
        # Increase confidence based on insights generated
        if context.insights:
            confidence += min(0.1, len(context.insights) * 0.02)
        
        return min(confidence, 0.95)  # Cap at 95%
    
    def _identify_numeric_columns(self, data: List[Dict[str, Any]]) -> List[str]:
        """Identify numeric columns in the data"""
        if not data:
            return []
        
        numeric_columns = []
        first_row = data[0]
        
        for key, value in first_row.items():
            if isinstance(value, (int, float)):
                numeric_columns.append(key)
        
        return numeric_columns
    
    def _check_thresholds(self, metric_name: str, value: float) -> List[str]:
        """Check if metric values cross important thresholds"""
        insights = []
        metric_lower = metric_name.lower()
        
        # Check revenue thresholds
        if "revenue" in metric_lower and "change" in metric_lower:
            thresholds = self.kpi_thresholds["revenue_change"]
            if value <= thresholds["critical_decline"]:
                insights.append(f"⚠️ Critical revenue decline of {value:.1f}%")
            elif value <= thresholds["warning_decline"]:
                insights.append(f"⚠️ Revenue decline of {value:.1f}% requires attention")
            elif value >= thresholds["excellent_growth"]:
                insights.append(f"✅ Excellent revenue growth of {value:.1f}%")
        
        # Check satisfaction thresholds
        elif "satisfaction" in metric_lower or "score" in metric_lower:
            thresholds = self.kpi_thresholds["customer_satisfaction"]
            if value >= thresholds["excellent"]:
                insights.append(f"✅ Excellent satisfaction score: {value:.1f}")
            elif value <= thresholds["poor"]:
                insights.append(f"⚠️ Poor satisfaction score: {value:.1f} needs immediate attention")
        
        return insights
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate simple trend coefficient"""
        if len(values) < 2:
            return 0.0
        
        # Simple linear trend
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * v for i, v in enumerate(values))
        x2_sum = sum(i * i for i in range(n))
        
        denominator = (n * x2_sum - x_sum * x_sum)
        if denominator == 0:
            return 0.0
        
        slope = (n * xy_sum - x_sum * y_sum) / denominator
        
        # Normalize by average value
        avg_value = y_sum / n
        if avg_value == 0:
            return 0.0
        
        return slope / avg_value
    
    def format_analysis_for_display(self, insight_result: InsightResult) -> str:
        """Format analysis results for display to user"""
        sections = []
        
        # Summary section
        sections.append(f"📊 {insight_result.summary}")
        sections.append("")
        
        # Key Insights section
        if insight_result.insights:
            sections.append("🔍 Key Insights:")
            for i, insight in enumerate(insight_result.insights[:5], 1):
                sections.append(f"{i}. {insight}")
            sections.append("")
        
        # Recommendations section
        if insight_result.recommendations:
            sections.append("🎯 Recommendations:")
            for i, recommendation in enumerate(insight_result.recommendations, 1):
                sections.append(f"{i}. {recommendation}")
            sections.append("")
        
        # Confidence indicator
        confidence_emoji = "🟢" if insight_result.confidence > 0.8 else "🟡" if insight_result.confidence > 0.6 else "🟠"
        sections.append(f"{confidence_emoji} Analysis Confidence: {insight_result.confidence:.0%}")
        
        return "\n".join(sections)

# Create singleton instance
analysis_agent = AnalysisAgent()

# Export
__all__ = ['AnalysisAgent', 'analysis_agent', 'AnalysisContext', 'InsightResult']