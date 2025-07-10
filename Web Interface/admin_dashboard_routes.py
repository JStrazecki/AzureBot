# admin_dashboard_routes.py - Admin Dashboard Routes and Logic
"""
Admin Dashboard Routes - Separated backend logic from UI
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from aiohttp import web
from aiohttp.web import Request, Response, json_response
import aiohttp

# Import UI components
from admin_dashboard_ui import get_admin_dashboard_html

logger = logging.getLogger(__name__)

class AdminDashboard:
    """Admin dashboard handler"""
    
    def __init__(self, sql_translator=None):
        self.sql_translator = sql_translator
        self.function_url = os.environ.get("AZURE_FUNCTION_URL", "")
        self.start_time = datetime.now()
    
    async def dashboard_page(self, request: Request) -> Response:
        """Serve the admin dashboard page"""
        html_content = get_admin_dashboard_html()
        return Response(text=html_content, content_type='text/html')
    
    async def api_test_health(self, request: Request) -> Response:
        """API endpoint for health check"""
        try:
            health_data = {
                "status": "healthy",
                "version": "2.0.0",
                "uptime": str(datetime.now() - self.start_time),
                "services": {
                    "sql_translator": self.sql_translator is not None,
                    "sql_function": bool(self.function_url),
                    "console": True,
                    "admin": True
                }
            }
            
            return json_response({
                "status": "success",
                "data": health_data,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_test_openai(self, request: Request) -> Response:
        """API endpoint for testing Azure OpenAI"""
        try:
            if not os.environ.get("AZURE_OPENAI_ENDPOINT") or not os.environ.get("AZURE_OPENAI_API_KEY"):
                return json_response({
                    "status": "error",
                    "data": {
                        "success": False,
                        "error": "Azure OpenAI not configured"
                    }
                })
            
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT").rstrip('/')
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
            
            test_url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-01"
            
            start_time = asyncio.get_event_loop().time()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    test_url,
                    headers={
                        "api-key": api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "messages": [{"role": "user", "content": "Test"}],
                        "max_tokens": 5
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    end_time = asyncio.get_event_loop().time()
                    response_time = (end_time - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        return json_response({
                            "status": "success",
                            "data": {
                                "success": True,
                                "details": {
                                    "deployment": deployment,
                                    "model": data.get("model", "unknown"),
                                    "response_time_ms": response_time,
                                    "status_code": response.status
                                }
                            }
                        })
                    else:
                        error_text = await response.text()
                        return json_response({
                            "status": "error",
                            "data": {
                                "success": False,
                                "error": f"API error: {response.status}",
                                "details": {
                                    "status_code": response.status,
                                    "response": error_text[:200]
                                }
                            }
                        })
                        
        except Exception as e:
            return json_response({
                "status": "error",
                "data": {
                    "success": False,
                    "error": f"Connection error: {str(e)}"
                }
            })
    
    async def api_test_function(self, request: Request) -> Response:
        """API endpoint for testing SQL function"""
        try:
            if not self.function_url:
                return json_response({
                    "status": "error",
                    "data": {
                        "success": False,
                        "error": "Azure Function URL not configured"
                    }
                })
            
            headers = {"Content-Type": "application/json"}
            
            start_time = asyncio.get_event_loop().time()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.function_url,
                    json={"query_type": "metadata"},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    end_time = asyncio.get_event_loop().time()
                    response_time = (end_time - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        return json_response({
                            "status": "success",
                            "data": {
                                "success": True,
                                "details": {
                                    "auth_method": "url_embedded" if "code=" in self.function_url else "header",
                                    "databases_found": len(data.get("databases", [])),
                                    "response_time_ms": response_time,
                                    "sample_databases": data.get("databases", [])[:3]
                                }
                            }
                        })
                    else:
                        error_text = await response.text()
                        return json_response({
                            "status": "error",
                            "data": {
                                "success": False,
                                "error": f"Function error: {response.status}",
                                "details": {
                                    "status_code": response.status,
                                    "response": error_text[:200]
                                }
                            }
                        })
                        
        except Exception as e:
            return json_response({
                "status": "error",
                "data": {
                    "success": False,
                    "error": f"Connection error: {str(e)}"
                }
            })
    
    async def api_test_translator(self, request: Request) -> Response:
        """API endpoint for testing SQL translator"""
        try:
            if not self.sql_translator:
                return json_response({
                    "status": "error",
                    "error": "SQL Translator not available"
                })
            
            data = await request.json()
            test_query = data.get("query", "show me all tables")
            
            result = await self.sql_translator.translate_to_sql(test_query)
            
            if result.error:
                return json_response({
                    "status": "error",
                    "error": result.error
                })
            
            return json_response({
                "status": "success",
                "query": result.query,
                "database": result.database,
                "explanation": result.explanation,
                "confidence": result.confidence
            })
            
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    async def api_test_performance(self, request: Request) -> Response:
        """API endpoint for testing performance"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Simulate some work
            await asyncio.sleep(0.001)
            
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000
            
            # Get memory info if available
            memory_info = {}
            try:
                import psutil
                process = psutil.Process()
                memory_info = {
                    "memory_usage_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                    "cpu_percent": round(process.cpu_percent(), 2)
                }
            except ImportError:
                memory_info = {"memory_usage_mb": 100, "info": "psutil not available"}
            
            return json_response({
                "status": "success",
                "response_time_ms": round(response_time, 2),
                "uptime": str(datetime.now() - self.start_time),
                **memory_info
            })
            
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e)
            }, status=500)

def add_admin_routes(app, sql_translator=None):
    """Add admin dashboard routes to the main app"""
    
    dashboard = AdminDashboard(sql_translator)
    
    # Dashboard page
    app.router.add_get('/admin', dashboard.dashboard_page)
    app.router.add_get('/admin/', dashboard.dashboard_page)
    
    # API endpoints
    app.router.add_get('/admin/api/health', dashboard.api_test_health)
    app.router.add_get('/admin/api/openai', dashboard.api_test_openai)
    app.router.add_get('/admin/api/function', dashboard.api_test_function)
    app.router.add_post('/admin/api/translator', dashboard.api_test_translator)
    app.router.add_get('/admin/api/performance', dashboard.api_test_performance)
    
    return dashboard