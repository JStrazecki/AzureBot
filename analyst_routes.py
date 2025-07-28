# analyst_routes.py - Power BI Analyst Routes and API Endpoints
"""
Power BI Analyst Routes - Handles the /analyst endpoint and related API calls
Fixed version with better error handling and workspace discovery
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from aiohttp import web
from aiohttp.web import Request, Response, json_response
import aiohttp

# Import components
from powerbi_client import powerbi_client, WorkspaceInfo, DatasetInfo, QueryResult
from analyst_translator import analyst_translator, DAXQuery, TranslationContext
from analysis_agent import analysis_agent, AnalysisContext, InsightResult

# Import UI
from analyst_ui import get_analyst_html

logger = logging.getLogger(__name__)

class PowerBIAnalyst:
    """Power BI Analyst endpoint handler"""
    
    def __init__(self):
        self.powerbi_client = powerbi_client
        self.translator = analyst_translator
        self.analysis_agent = analysis_agent
        
        # Cache for workspace and dataset information
        self.workspace_cache = {}
        self.dataset_cache = {}
        self.cache_duration = 300  # 5 minutes
        
        # Active sessions
        self.sessions = {}
        
        logger.info("Power BI Analyst initialized")
        logger.info(f"Power BI configured: {self.powerbi_client.is_configured()}")
    
    async def analyst_page(self, request: Request) -> Response:
        """Serve the analyst HTML page"""
        html_content = get_analyst_html()
        return Response(text=html_content, content_type='text/html')
    
    async def check_configuration(self, request: Request) -> Response:
        """API endpoint to check Power BI configuration"""
        try:
            validation = await self.powerbi_client.validate_configuration()
            
            return json_response({
                "status": "success",
                "configured": validation["configured"],
                "validation": validation
            })
            
        except Exception as e:
            logger.error(f"Configuration check error: {e}")
            return json_response({
                "status": "error",
                "error": str(e)
            })
    
    async def get_workspaces(self, request: Request) -> Response:
        """API endpoint to get user's Power BI workspaces"""
        try:
            # Clear cache if requested
            if request.query.get('refresh', '').lower() == 'true':
                logger.info("Clearing workspace cache due to refresh request")
                self.workspace_cache.clear()
                self.dataset_cache.clear()
            
            # Get access token
            token = await self.powerbi_client.get_access_token()
            if not token:
                return json_response({
                    "status": "error",
                    "error": "Failed to authenticate with Power BI. Please check your credentials."
                })
            
            # Check cache
            cache_key = "workspaces"
            if cache_key in self.workspace_cache:
                cached_data = self.workspace_cache[cache_key]
                if cached_data["expires"] > datetime.now().timestamp():
                    logger.info("Returning cached workspaces")
                    return json_response({
                        "status": "success",
                        "workspaces": cached_data["data"],
                        "cached": True
                    })
            
            # Get workspaces
            logger.info("Fetching workspaces from Power BI API...")
            workspaces = await self.powerbi_client.get_user_workspaces(token)
            
            # Convert to serializable format
            workspace_list = []
            for ws in workspaces:
                workspace_dict = {
                    "id": ws.id,
                    "name": ws.name,
                    "description": ws.description,
                    "is_personal": ws.is_personal,
                    "type": ws.type or "Workspace"
                }
                workspace_list.append(workspace_dict)
                logger.info(f"Workspace: {ws.name} (Personal: {ws.is_personal})")
            
            # If no workspaces found, try to check if we can at least access personal workspace
            if not workspace_list:
                logger.warning("No workspaces found through groups API, checking personal workspace access...")
                
                # Try to list datasets directly to see if we have any access
                try:
                    # Make a direct call to datasets endpoint
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{self.powerbi_client.base_url}/datasets",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            
                            if response.status == 200:
                                data = await response.json()
                                personal_datasets = data.get("value", [])
                                
                                if personal_datasets:
                                    logger.info(f"Found {len(personal_datasets)} datasets in personal workspace")
                                    # Add a virtual "My Workspace" entry
                                    workspace_list.append({
                                        "id": "me",
                                        "name": "My Workspace",
                                        "description": "Personal workspace",
                                        "is_personal": True,
                                        "type": "Personal"
                                    })
                                else:
                                    logger.info("No datasets found in personal workspace either")
                            else:
                                logger.warning(f"Could not check personal datasets: Status {response.status}")
                                
                except Exception as e:
                    logger.error(f"Error checking personal workspace: {e}")
            
            # Cache the results
            self.workspace_cache[cache_key] = {
                "data": workspace_list,
                "expires": datetime.now().timestamp() + self.cache_duration
            }
            
            # Log summary
            logger.info(f"Total workspaces available: {len(workspace_list)}")
            
            # Add helpful information if no workspaces
            response_data = {
                "status": "success",
                "workspaces": workspace_list
            }
            
            if not workspace_list:
                response_data["help"] = {
                    "message": "No workspaces accessible",
                    "steps": [
                        "Grant the app access to Power BI workspaces:",
                        f"1. Go to app.powerbi.com and log in",
                        f"2. Navigate to your workspace",
                        f"3. Click 'Manage access' or the access icon",
                        f"4. Click '+ Add people or groups'",
                        f"5. Search for your app using Client ID: {self.powerbi_client.credentials.client_id}",
                        f"6. Grant 'Viewer' or higher role",
                        f"7. Click 'Add' and wait 1-2 minutes",
                        f"8. Refresh this page"
                    ]
                }
            
            return json_response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting workspaces: {e}", exc_info=True)
            
            # Return more detailed error information
            error_response = {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            # Add specific guidance based on error type
            if "token" in str(e).lower():
                error_response["help"] = "Authentication failed. Check your Power BI credentials."
            elif "timeout" in str(e).lower():
                error_response["help"] = "Request timed out. Please try again."
            else:
                error_response["help"] = "An unexpected error occurred. Check the logs for details."
            
            return json_response(error_response)
    
    async def get_datasets(self, request: Request) -> Response:
        """API endpoint to get datasets in a workspace"""
        try:
            workspace_id = request.query.get('workspace_id')
            workspace_name = request.query.get('workspace_name', 'Unknown')
            
            if not workspace_id:
                return json_response({
                    "status": "error",
                    "error": "workspace_id parameter required"
                })
            
            logger.info(f"Getting datasets for workspace: {workspace_name} (ID: {workspace_id})")
            
            # Get access token
            token = await self.powerbi_client.get_access_token()
            if not token:
                return json_response({
                    "status": "error",
                    "error": "Failed to authenticate with Power BI"
                })
            
            # Check cache
            cache_key = f"datasets_{workspace_id}"
            if cache_key in self.dataset_cache:
                cached_data = self.dataset_cache[cache_key]
                if cached_data["expires"] > datetime.now().timestamp():
                    logger.info(f"Returning cached datasets for workspace {workspace_name}")
                    return json_response({
                        "status": "success",
                        "datasets": cached_data["data"],
                        "cached": True
                    })
            
            # Get datasets
            datasets = await self.powerbi_client.get_workspace_datasets(token, workspace_id, workspace_name)
            
            # Convert to serializable format
            dataset_list = []
            for ds in datasets:
                dataset_dict = {
                    "id": ds.id,
                    "name": ds.name,
                    "workspace_id": ds.workspace_id,
                    "workspace_name": ds.workspace_name,
                    "configured_by": ds.configured_by,
                    "created_date": ds.created_date
                }
                dataset_list.append(dataset_dict)
                logger.info(f"Dataset: {ds.name}")
            
            # Cache the results
            self.dataset_cache[cache_key] = {
                "data": dataset_list,
                "expires": datetime.now().timestamp() + self.cache_duration
            }
            
            logger.info(f"Found {len(dataset_list)} datasets in workspace {workspace_name}")
            
            # Add helpful information if no datasets
            response_data = {
                "status": "success",
                "datasets": dataset_list
            }
            
            if not dataset_list:
                response_data["help"] = {
                    "message": f"No datasets found in workspace '{workspace_name}'",
                    "possible_reasons": [
                        "The workspace may be empty",
                        "The app may not have Dataset.Read.All permission",
                        "The datasets may require additional permissions"
                    ]
                }
            
            return json_response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting datasets: {e}", exc_info=True)
            return json_response({
                "status": "error",
                "error": str(e),
                "workspace_id": workspace_id,
                "workspace_name": workspace_name
            })
    
    async def analyze_query(self, request: Request) -> Response:
        """Main API endpoint for natural language query analysis"""
        try:
            data = await request.json()
            query = data.get('query', '').strip()
            dataset_id = data.get('dataset_id')
            dataset_name = data.get('dataset_name', 'Unknown Dataset')
            session_id = data.get('session_id')
            
            if not query:
                return json_response({
                    "status": "error",
                    "error": "Query is required"
                })
            
            if not dataset_id:
                return json_response({
                    "status": "error",
                    "error": "Please select a dataset first"
                })
            
            logger.info(f"Analyzing query: {query[:100]}... for dataset {dataset_name}")
            
            # Get access token
            token = await self.powerbi_client.get_access_token()
            if not token:
                return json_response({
                    "status": "error",
                    "error": "Failed to authenticate with Power BI. Token acquisition failed."
                })
            
            # Get dataset metadata (cached if possible)
            try:
                metadata = await self._get_dataset_metadata(token, dataset_id)
                logger.info(f"Dataset metadata retrieved. Status: {metadata.get('status', 'unknown')}")
            except Exception as e:
                logger.error(f"Error getting dataset metadata: {e}")
                metadata = {
                    "status": "error",
                    "error": str(e),
                    "tables": [],
                    "measures": []
                }
            
            # Create translation context
            context = TranslationContext(
                dataset_metadata=metadata,
                available_measures=metadata.get("measures", []),
                available_tables=metadata.get("tables", []),
                business_context={
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name
                }
            )
            
            # Add to query history
            if session_id and session_id in self.sessions:
                context.query_history = self.sessions[session_id].get("query_history", [])
            
            # Translate to DAX
            logger.info("Translating natural language to DAX...")
            dax_result = await self.translator.translate_to_dax(query, context)
            
            if dax_result.error:
                return json_response({
                    "status": "error",
                    "error": dax_result.error,
                    "query_type": "translation_failed"
                })
            
            logger.info(f"Generated DAX query: {dax_result.query[:200]}...")
            
            # Execute DAX query
            logger.info("Executing DAX query...")
            query_result = await self.powerbi_client.execute_dax_query(
                token,
                dataset_id,
                dax_result.query,
                dataset_name
            )
            
            if not query_result.success:
                # Try to analyze and fix the error
                if self.translator and dax_result.query:
                    logger.info("Analyzing DAX error...")
                    error_analysis = await self.translator.analyze_dax_error(
                        dax_result.query,
                        query_result.error,
                        context
                    )
                    
                    return json_response({
                        "status": "success",
                        "query_type": "error_with_analysis",
                        "original_query": query,
                        "dax_query": dax_result.query,
                        "error": query_result.error,
                        "error_analysis": error_analysis,
                        "explanation": dax_result.explanation
                    })
                else:
                    return json_response({
                        "status": "error",
                        "error": query_result.error,
                        "dax_query": dax_result.query
                    })
            
            # Log successful execution
            logger.info(f"Query executed successfully. Rows returned: {query_result.row_count}")
            
            # Perform progressive analysis
            logger.info("Performing progressive analysis...")
            try:
                insight_result = await self.analysis_agent.perform_progressive_analysis(
                    query,
                    query_result,
                    metadata,
                    self.powerbi_client,
                    token
                )
                
                insights_data = {
                    "summary": insight_result.summary,
                    "insights": insight_result.insights,
                    "recommendations": insight_result.recommendations,
                    "confidence": insight_result.confidence,
                    "investigation_complete": insight_result.investigation_complete
                }
            except Exception as e:
                logger.error(f"Error in progressive analysis: {e}")
                insights_data = {
                    "summary": "Analysis completed",
                    "insights": ["Query executed successfully"],
                    "recommendations": [],
                    "confidence": 0.5,
                    "investigation_complete": True
                }
            
            # Update session history
            if session_id:
                if session_id not in self.sessions:
                    self.sessions[session_id] = {"query_history": []}
                self.sessions[session_id]["query_history"].append(query)
            
            # Format response
            response_data = {
                "status": "success",
                "query_type": "analysis_complete",
                "original_query": query,
                "dax_query": dax_result.query,
                "explanation": dax_result.explanation,
                "data": query_result.data,
                "row_count": query_result.row_count,
                "execution_time_ms": query_result.execution_time_ms,
                "insights": insights_data,
                "follow_up_queries": self._generate_follow_up_suggestions(query, insights_data)
            }
            
            return json_response(response_data)
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)
            return json_response({
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            })
    
    async def execute_dax(self, request: Request) -> Response:
        """Direct DAX execution endpoint (for fixed queries)"""
        try:
            data = await request.json()
            dax_query = data.get('dax_query')
            dataset_id = data.get('dataset_id')
            dataset_name = data.get('dataset_name', 'Unknown Dataset')
            
            if not dax_query or not dataset_id:
                return json_response({
                    "status": "error",
                    "error": "dax_query and dataset_id are required"
                })
            
            logger.info(f"Executing DAX query directly on dataset {dataset_name}")
            
            # Get access token
            token = await self.powerbi_client.get_access_token()
            if not token:
                return json_response({
                    "status": "error",
                    "error": "Failed to authenticate with Power BI"
                })
            
            # Execute query
            result = await self.powerbi_client.execute_dax_query(
                token,
                dataset_id,
                dax_query,
                dataset_name
            )
            
            if result.success:
                logger.info(f"Direct DAX execution successful. Rows: {result.row_count}")
                return json_response({
                    "status": "success",
                    "data": result.data,
                    "row_count": result.row_count,
                    "execution_time_ms": result.execution_time_ms
                })
            else:
                logger.error(f"Direct DAX execution failed: {result.error}")
                return json_response({
                    "status": "error",
                    "error": result.error
                })
                
        except Exception as e:
            logger.error(f"Error executing DAX: {e}", exc_info=True)
            return json_response({
                "status": "error",
                "error": str(e)
            })
    
    async def test_connection(self, request: Request) -> Response:
        """Test Power BI connection and configuration"""
        try:
            logger.info("Testing Power BI connection...")
            
            # Validate configuration
            validation = await self.powerbi_client.validate_configuration()
            
            test_results = {
                "configuration": validation,
                "test_steps": []
            }
            
            # Step 1: Check credentials
            test_results["test_steps"].append({
                "step": "Check credentials",
                "success": validation["credentials_present"],
                "details": "Power BI credentials are configured" if validation["credentials_present"] else "Missing credentials"
            })
            
            # Step 2: Get access token
            if validation["token_acquired"]:
                test_results["test_steps"].append({
                    "step": "Acquire access token",
                    "success": True,
                    "details": "Successfully authenticated with Azure AD"
                })
                
                # Step 3: Access API
                if validation["api_accessible"]:
                    workspace_count = validation.get('workspace_count', 0)
                    workspace_names = validation.get('workspace_names', [])
                    
                    details = f"Found {workspace_count} accessible workspaces"
                    if workspace_names:
                        details += f": {', '.join(workspace_names[:3])}"
                        if workspace_count > 3:
                            details += f" and {workspace_count - 3} more"
                    
                    test_results["test_steps"].append({
                        "step": "Access Power BI API",
                        "success": True,
                        "details": details
                    })
                else:
                    test_results["test_steps"].append({
                        "step": "Access Power BI API",
                        "success": False,
                        "details": "Could not access Power BI API"
                    })
            else:
                test_results["test_steps"].append({
                    "step": "Acquire access token",
                    "success": False,
                    "details": "Failed to authenticate - check credentials"
                })
            
            # Add troubleshooting if needed
            if "troubleshooting" in validation:
                test_results["troubleshooting"] = validation["troubleshooting"]
            
            # Overall status
            all_success = all(step["success"] for step in test_results["test_steps"])
            
            return json_response({
                "status": "success" if all_success else "partial",
                "test_results": test_results,
                "ready": validation["configured"] and validation["workspaces_accessible"],
                "client_id": self.powerbi_client.credentials.client_id if all_success else None
            })
            
        except Exception as e:
            logger.error(f"Connection test error: {e}", exc_info=True)
            return json_response({
                "status": "error",
                "error": str(e)
            })
    
    async def _get_dataset_metadata(self, token: str, dataset_id: str) -> Dict[str, Any]:
        """Get dataset metadata with caching"""
        cache_key = f"metadata_{dataset_id}"
        
        # Check cache
        if cache_key in self.dataset_cache:
            cached_data = self.dataset_cache[cache_key]
            if cached_data["expires"] > datetime.now().timestamp():
                logger.info(f"Using cached metadata for dataset {dataset_id}")
                return cached_data["data"]
        
        # Fetch metadata
        logger.info(f"Fetching metadata for dataset {dataset_id}")
        metadata = await self.powerbi_client.get_dataset_metadata(token, dataset_id)
        
        # Cache the results
        self.dataset_cache[cache_key] = {
            "data": metadata,
            "expires": datetime.now().timestamp() + self.cache_duration
        }
        
        return metadata
    
    def _generate_follow_up_suggestions(self, original_query: str, insights: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate follow-up query suggestions based on the analysis"""
        suggestions = []
        
        # Use the translator's suggestion capability if available
        if hasattr(self.translator, 'suggest_follow_up_queries'):
            try:
                context = TranslationContext(
                    dataset_metadata={},
                    available_measures=[],
                    available_tables=[],
                    business_context={}
                )
                
                # Create a mock InsightResult for compatibility
                class MockInsightResult:
                    def __init__(self, insights_data):
                        self.insights = insights_data.get("insights", [])
                        self.recommendations = insights_data.get("recommendations", [])
                        self.summary = insights_data.get("summary", "")
                
                translator_suggestions = self.translator.suggest_follow_up_queries(
                    original_query,
                    MockInsightResult(insights),
                    context
                )
                suggestions.extend(translator_suggestions)
            except Exception as e:
                logger.error(f"Error generating follow-up suggestions: {e}")
        
        # Add generic suggestions based on query type
        query_lower = original_query.lower()
        
        if not suggestions:
            if "revenue" in query_lower:
                suggestions.extend([
                    {
                        "question": "Show me the revenue trend over the last 12 months",
                        "purpose": "Understand revenue patterns"
                    },
                    {
                        "question": "What are the top revenue-generating products?",
                        "purpose": "Identify key drivers"
                    }
                ])
            elif "customer" in query_lower:
                suggestions.extend([
                    {
                        "question": "Which customer segments are most valuable?",
                        "purpose": "Customer segmentation"
                    },
                    {
                        "question": "Show me customer retention trends",
                        "purpose": "Loyalty analysis"
                    }
                ])
            else:
                suggestions.extend([
                    {
                        "question": "What are the key performance metrics?",
                        "purpose": "Overview analysis"
                    },
                    {
                        "question": "Show me trends over time",
                        "purpose": "Trend analysis"
                    }
                ])
        
        # Limit to 3 suggestions
        return suggestions[:3]

def add_analyst_routes(app, sql_translator=None):
    """Add Power BI Analyst routes to the application"""
    
    analyst = PowerBIAnalyst()
    
    # Main page
    app.router.add_get('/analyst', analyst.analyst_page)
    app.router.add_get('/analyst/', analyst.analyst_page)
    
    # API endpoints
    app.router.add_get('/analyst/api/check-config', analyst.check_configuration)
    app.router.add_get('/analyst/api/workspaces', analyst.get_workspaces)
    app.router.add_get('/analyst/api/datasets', analyst.get_datasets)
    app.router.add_post('/analyst/api/analyze', analyst.analyze_query)
    app.router.add_post('/analyst/api/execute-dax', analyst.execute_dax)
    app.router.add_get('/analyst/api/test-connection', analyst.test_connection)
    
    logger.info("Power BI Analyst routes added successfully")
    return analyst