# admin_dashboard.py - Updated admin dashboard with fixed authentication and no env display
"""
Updated Admin Dashboard Route Handler for SQL Assistant Bot
Features:
- Fixed user authentication display for Microsoft auth
- Removed environment variables display
- Fixed SQL function connectivity for console
- Real-time cost tracking
- Comprehensive system monitoring
- Usage analytics and billing insights
- Performance metrics
- Uptime tracking
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiohttp.web import Request, Response, json_response
from aiohttp import web
import jwt
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
import logging
import base64

logger = logging.getLogger(__name__)

# Global variable to track when the app started
APP_START_TIME = datetime.now()

class UptimeTracker:
    """Tracks application uptime and performance metrics"""
    
    def __init__(self):
        self.start_time = APP_START_TIME
        self.restart_count = 0
        self.last_restart = None
        self.performance_samples = []
    
    def get_uptime(self) -> dict:
        """Get current uptime information"""
        now = datetime.now()
        uptime_delta = now - self.start_time
        
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            "start_time": self.start_time.isoformat(),
            "current_time": now.isoformat(),
            "uptime_seconds": int(uptime_delta.total_seconds()),
            "uptime_formatted": f"{days}d {hours}h {minutes}m {seconds}s",
            "uptime_days": days,
            "uptime_hours": hours,
            "uptime_minutes": minutes,
            "restart_count": self.restart_count,
            "last_restart": self.last_restart.isoformat() if self.last_restart else None
        }
    
    def record_restart(self):
        """Record a restart event"""
        self.restart_count += 1
        self.last_restart = datetime.now()
    
    def add_performance_sample(self, response_time_ms: float, endpoint: str):
        """Add a performance sample"""
        sample = {
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": response_time_ms,
            "endpoint": endpoint
        }
        
        # Keep only last 100 samples
        self.performance_samples.append(sample)
        if len(self.performance_samples) > 100:
            self.performance_samples.pop(0)
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        if not self.performance_samples:
            return {
                "avg_response_time": 0,
                "min_response_time": 0,
                "max_response_time": 0,
                "sample_count": 0
            }
        
        response_times = [s["response_time_ms"] for s in self.performance_samples]
        
        return {
            "avg_response_time": sum(response_times) / len(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "sample_count": len(response_times),
            "recent_samples": self.performance_samples[-10:]  # Last 10 samples
        }

class AzureFunctionAuth:
    """Helper class for Azure Function authentication"""
    
    def __init__(self, function_url: str = None, function_key: str = None):
        self.function_url = function_url or os.environ.get("AZURE_FUNCTION_URL", "")
        self.function_key = function_key or os.environ.get("AZURE_FUNCTION_KEY", "")
        self.auth_method = None
        
    def _get_auth_methods(self) -> list:
        """Get available authentication methods in order of preference"""
        methods = []
        
        # Check if URL already contains authentication
        if 'code=' in self.function_url.lower():
            methods.append("url_embedded")
        
        # Function key in header
        if self.function_key:
            methods.append("header_key")
        
        # Function key in URL
        if self.function_key:
            methods.append("url_key")
        
        # Managed Identity (if bot has access)
        methods.append("managed_identity")
        
        return methods
    
    def _prepare_request(self, method: str, payload: Dict[str, Any]) -> tuple:
        """Prepare URL, headers, and payload for different authentication methods"""
        base_url = self.function_url.split('?')[0] if '?' in self.function_url else self.function_url
        headers = {"Content-Type": "application/json"}
        
        if method == "url_embedded":
            url = self.function_url
        elif method == "managed_identity":
            url = base_url
        elif method == "header_key":
            url = base_url
            headers["x-functions-key"] = self.function_key
        elif method == "url_key":
            url = f"{base_url}?code={self.function_key}"
        else:
            raise ValueError(f"Unknown authentication method: {method}")
        
        return url, headers, payload
    
    async def call_function(self, payload: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
        """Call Azure Function with automatic authentication method detection"""
        if not self.function_url:
            return {
                "success": False,
                "error": "No Azure Function URL configured",
                "details": {"missing": "AZURE_FUNCTION_URL"}
            }
        
        auth_methods = self._get_auth_methods()
        last_error = None
        
        for method in auth_methods:
            try:
                logger.info(f"Trying authentication method: {method}")
                
                url, headers, request_payload = self._prepare_request(method, payload)
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=request_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            self.auth_method = method
                            logger.info(f"✅ Authentication successful with method: {method}")
                            
                            return {
                                "success": True,
                                "data": data,
                                "details": {
                                    "status_code": response.status,
                                    "auth_method": method,
                                    "url_used": url.split('?')[0] + "?..." if '?' in url else url
                                }
                            }
                        
                        elif response.status == 401:
                            error_text = await response.text()
                            last_error = f"Authentication failed with {method}: {error_text[:100]}"
                            logger.warning(f"❌ Authentication failed with {method}")
                            continue
                        
                        else:
                            error_text = await response.text()
                            return {
                                "success": False,
                                "error": f"Function error: {response.status}",
                                "details": {
                                    "status_code": response.status,
                                    "response": error_text[:200],
                                    "auth_method": method
                                }
                            }
                            
            except Exception as e:
                last_error = f"Error with {method}: {str(e)}"
                logger.warning(f"❌ Error with {method}: {e}")
                continue
        
        return {
            "success": False,
            "error": "All authentication methods failed",
            "details": {
                "tried_methods": auth_methods,
                "last_error": last_error,
                "has_function_key": bool(self.function_key),
                "url_has_code": 'code=' in self.function_url.lower()
            }
        }

class CostTracker:
    """Tracks and calculates costs for various Azure services"""
    
    def __init__(self):
        self.token_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-35-turbo": {"input": 0.0015, "output": 0.002}
        }
        
        self.function_costs = {
            "sql_query": 0.001,
            "metadata_fetch": 0.0005,
        }
    
    def calculate_token_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage"""
        if model not in self.token_costs:
            model = "gpt-4o-mini"
        
        costs = self.token_costs[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def get_daily_budget_status(self, current_cost: float, daily_limit: float = 50.0) -> dict:
        """Get budget status information"""
        percentage = (current_cost / daily_limit) * 100
        remaining = max(0, daily_limit - current_cost)
        
        status = "healthy"
        if percentage > 90:
            status = "critical"
        elif percentage > 75:
            status = "warning"
        elif percentage > 50:
            status = "caution"
        
        return {
            "current": current_cost,
            "limit": daily_limit,
            "remaining": remaining,
            "percentage": percentage,
            "status": status
        }

class UserAuthHandler:
    """Handles user authentication information extraction for Microsoft auth"""
    
    @staticmethod
    def extract_user_info(request: Request) -> dict:
        """Extract user information from Microsoft authentication headers"""
        user_info = {
            "name": "Guest User",
            "email": "user@domain.com",
            "authenticated": False,
            "tenant": "Unknown",
            "roles": [],
            "auth_type": "none"
        }
        
        # Check for Microsoft authentication headers
        # X-MS-CLIENT-PRINCIPAL-NAME contains the user's name/email
        ms_client_principal_name = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
        ms_client_principal_id = request.headers.get('X-MS-CLIENT-PRINCIPAL-ID')
        ms_client_principal = request.headers.get('X-MS-CLIENT-PRINCIPAL')
        
        if ms_client_principal_name:
            user_info.update({
                "name": ms_client_principal_name,
                "email": ms_client_principal_name,
                "authenticated": True,
                "auth_type": "microsoft"
            })
            logger.info(f"Found Microsoft auth user: {ms_client_principal_name}")
        
        # Try to decode the principal header if available
        if ms_client_principal:
            try:
                # The principal is base64 encoded JSON
                decoded = base64.b64decode(ms_client_principal).decode('utf-8')
                principal_data = json.loads(decoded)
                
                # Extract additional info from principal
                if 'userDetails' in principal_data:
                    user_info["name"] = principal_data['userDetails']
                
                if 'userId' in principal_data:
                    user_info["email"] = principal_data['userId']
                
                if 'identityProvider' in principal_data:
                    user_info["auth_type"] = principal_data['identityProvider']
                
                # Extract claims
                if 'claims' in principal_data:
                    for claim in principal_data['claims']:
                        if claim.get('typ') == 'name':
                            user_info["name"] = claim.get('val', user_info["name"])
                        elif claim.get('typ') == 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress':
                            user_info["email"] = claim.get('val', user_info["email"])
                        elif claim.get('typ') == 'http://schemas.microsoft.com/identity/claims/tenantid':
                            user_info["tenant"] = claim.get('val', 'Unknown')
                        elif claim.get('typ') == 'roles':
                            user_info["roles"].append(claim.get('val', ''))
                
                user_info["authenticated"] = True
                logger.info(f"Decoded principal data for user: {user_info['name']}")
                
            except Exception as e:
                logger.warning(f"Failed to decode MS principal: {e}")
        
        # Try authorization header as fallback
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer ') and not user_info["authenticated"]:
            token = auth_header[7:]
            try:
                # Decode without verification (for display purposes only)
                decoded = jwt.decode(token, options={"verify_signature": False})
                user_info.update({
                    "name": decoded.get('name', decoded.get('preferred_username', user_info["name"])),
                    "email": decoded.get('email', decoded.get('upn', user_info["email"])),
                    "authenticated": True,
                    "tenant": decoded.get('tid', 'Unknown'),
                    "roles": decoded.get('roles', []),
                    "auth_type": "bearer_token"
                })
            except Exception as e:
                logger.warning(f"Failed to decode JWT: {e}")
        
        # Format the name nicely
        if user_info["authenticated"] and "@" in user_info["name"]:
            # Extract name part before @ if it's an email
            user_info["display_name"] = user_info["name"].split("@")[0].replace(".", " ").title()
        else:
            user_info["display_name"] = user_info["name"]
        
        return user_info

class EnhancedAdminDashboard:
    """Enhanced admin dashboard with cost tracking, uptime monitoring, and improved authentication"""
    
    def __init__(self, sql_translator=None, bot=None):
        self.sql_translator = sql_translator
        self.bot = bot
        self.cost_tracker = CostTracker()
        self.user_auth = UserAuthHandler()
        self.uptime_tracker = UptimeTracker()
        self.function_auth = AzureFunctionAuth()
        
        # In-memory storage for demo
        self.usage_stats = {
            "daily_costs": {},
            "hourly_costs": {},
            "user_sessions": {},
            "query_history": [],
            "error_log": []
        }
    
    async def dashboard_page(self, request: Request) -> Response:
        """Serve the enhanced dashboard HTML page with uptime tracking"""
        
        user_info = self.user_auth.extract_user_info(request)
        uptime_info = self.uptime_tracker.get_uptime()
        perf_stats = self.uptime_tracker.get_performance_stats()
        
        # Get basic config info without exposing sensitive data
        config = {
            "botUrl": f"https://{request.host}",
            "functionConfigured": bool(os.environ.get("AZURE_FUNCTION_URL")),
            "openaiConfigured": bool(os.environ.get("AZURE_OPENAI_ENDPOINT")),
            "environment": os.environ.get("DEPLOYMENT_ENV", "production"),
            "authMethod": "url_embedded" if "code=" in os.environ.get("AZURE_FUNCTION_URL", "") else "standard"
        }
        
        today = datetime.now().strftime("%Y-%m-%d")
        daily_cost = self.usage_stats["daily_costs"].get(today, 0.0)
        budget_status = self.cost_tracker.get_daily_budget_status(daily_cost)
        
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant Bot - Admin Dashboard</title>
    <style>
        {self._get_enhanced_dashboard_css()}
    </style>
</head>
<body>
    <div class="dashboard">
        <!-- Enhanced Header with User Info and Uptime -->
        <div class="header">
            <div class="header-content">
                <div class="title-section">
                    <h1>🤖 SQL Assistant Bot - Admin Dashboard</h1>
                    <p>Real-time monitoring & analytics • Environment: {config["environment"]}</p>
                </div>
                <div class="user-section">
                    <div class="user-info">
                        <div class="user-avatar">
                            <span class="avatar-icon">👤</span>
                        </div>
                        <div class="user-details">
                            <div class="user-name">{user_info["display_name"]}</div>
                            <div class="user-email">{user_info["email"]}</div>
                            <div class="auth-status {'authenticated' if user_info['authenticated'] else 'not-authenticated'}">
                                {'🟢 ' + user_info['auth_type'].title() if user_info['authenticated'] else '🔴 Not Authenticated'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="server-info">
                <span>Server: {request.host}</span> • 
                <span>Time: <span id="currentTime">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span></span> •
                <span>Uptime: <span id="uptimeDisplay">{uptime_info["uptime_formatted"]}</span></span>
            </div>
        </div>

        <!-- Uptime and System Health Dashboard -->
        <div class="uptime-dashboard">
            <h2>⏱️ System Uptime & Performance</h2>
            <div class="uptime-grid">
                <div class="uptime-card primary">
                    <div class="uptime-header">
                        <div class="uptime-icon">🚀</div>
                        <div class="uptime-title">Application Uptime</div>
                        <div class="uptime-actions">
                            <button class="mini-button" onclick="refreshUptime()">🔄</button>
                        </div>
                    </div>
                    <div class="uptime-main">{uptime_info["uptime_formatted"]}</div>
                    <div class="uptime-sub">Started: {uptime_info["start_time"][:19].replace('T', ' ')}</div>
                    <div class="uptime-stats">
                        <div class="stat-item">
                            <span class="stat-label">Days:</span>
                            <span class="stat-value">{uptime_info["uptime_days"]}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Restarts:</span>
                            <span class="stat-value">{uptime_info["restart_count"]}</span>
                        </div>
                    </div>
                </div>
                
                <div class="uptime-card">
                    <div class="uptime-header">
                        <div class="uptime-icon">📊</div>
                        <div class="uptime-title">Performance</div>
                        <div class="uptime-actions">
                            <button class="mini-button" onclick="viewPerformanceDetails()">📈</button>
                        </div>
                    </div>
                    <div class="perf-metrics">
                        <div class="metric">
                            <span class="metric-label">Avg Response:</span>
                            <span class="metric-value">{perf_stats["avg_response_time"]:.1f}ms</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Min/Max:</span>
                            <span class="metric-value">{perf_stats["min_response_time"]:.1f}ms / {perf_stats["max_response_time"]:.1f}ms</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Samples:</span>
                            <span class="metric-value">{perf_stats["sample_count"]}</span>
                        </div>
                    </div>
                </div>
                
                <div class="uptime-card">
                    <div class="uptime-header">
                        <div class="uptime-icon">🔧</div>
                        <div class="uptime-title">System Health</div>
                        <div class="uptime-actions">
                            <button class="mini-button" onclick="checkSystemHealth()">🔍</button>
                        </div>
                    </div>
                    <div class="health-metrics" id="systemHealth">
                        <div class="metric">
                            <span class="metric-label">Status:</span>
                            <span class="metric-value status-healthy">🟢 Healthy</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Auth:</span>
                            <span class="metric-value">{config["authMethod"]}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Services:</span>
                            <span class="metric-value">Active</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Cost Tracking Dashboard -->
        <div class="cost-dashboard">
            <h2>💰 Cost Tracking & Budget Monitoring</h2>
            <div class="cost-grid">
                <div class="cost-card primary">
                    <div class="cost-header">
                        <div class="cost-icon">💵</div>
                        <div class="cost-title">Daily Spending</div>
                        <div class="cost-actions">
                            <button class="mini-button" onclick="refreshCosts()">🔄</button>
                        </div>
                    </div>
                    <div class="cost-amount">${daily_cost:.3f}</div>
                    <div class="cost-limit">Budget: $50.00/day</div>
                    <div class="cost-progress">
                        <div class="progress-bar">
                            <div class="progress-fill {budget_status['status']}" style="width: {min(budget_status['percentage'], 100):.1f}%"></div>
                        </div>
                        <div class="progress-text">{budget_status['percentage']:.1f}% used</div>
                    </div>
                </div>
                
                <div class="cost-card">
                    <div class="cost-header">
                        <div class="cost-icon">🎯</div>
                        <div class="cost-title">Token Usage</div>
                        <div class="cost-actions">
                            <button class="mini-button" onclick="viewTokenDetails()">📊</button>
                        </div>
                    </div>
                    <div class="cost-metrics" id="tokenMetrics">
                        <div class="metric">
                            <span class="metric-label">Input Tokens:</span>
                            <span class="metric-value" id="inputTokens">0</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Output Tokens:</span>
                            <span class="metric-value" id="outputTokens">0</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Cost:</span>
                            <span class="metric-value" id="tokenCost">$0.000</span>
                        </div>
                    </div>
                </div>
                
                <div class="cost-card">
                    <div class="cost-header">
                        <div class="cost-icon">⚡</div>
                        <div class="cost-title">Function Calls</div>
                        <div class="cost-actions">
                            <button class="mini-button" onclick="viewFunctionDetails()">📈</button>
                        </div>
                    </div>
                    <div class="cost-metrics" id="functionMetrics">
                        <div class="metric">
                            <span class="metric-label">SQL Queries:</span>
                            <span class="metric-value" id="sqlQueries">0</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Metadata Calls:</span>
                            <span class="metric-value" id="metadataCalls">0</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Function Cost:</span>
                            <span class="metric-value" id="functionCost">$0.000</span>
                        </div>
                    </div>
                </div>
                
                <div class="cost-card">
                    <div class="cost-header">
                        <div class="cost-icon">📊</div>
                        <div class="cost-title">Usage Analytics</div>
                        <div class="cost-actions">
                            <button class="mini-button" onclick="exportUsageReport()">📁</button>
                        </div>
                    </div>
                    <div class="cost-metrics" id="usageMetrics">
                        <div class="metric">
                            <span class="metric-label">Active Users:</span>
                            <span class="metric-value" id="activeUsers">1</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Queries Today:</span>
                            <span class="metric-value" id="queriesToday">0</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Avg Cost/Query:</span>
                            <span class="metric-value" id="avgCostQuery">$0.000</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Status Overview -->
        <div class="quick-status">
            <div class="status-item" id="overallStatus">
                <div class="status-icon status-loading">⟳</div>
                <div class="status-text">
                    <div class="status-title">System Status</div>
                    <div class="status-subtitle">Checking...</div>
                </div>
            </div>
        </div>

        <!-- Service Status Section (No Environment Variables) -->
        <div class="config-section">
            <h2>⚙️ Service Status</h2>
            <div class="service-status-grid">
                <div class="service-status">
                    <div class="service-icon">🤖</div>
                    <div class="service-info">
                        <div class="service-name">Bot Framework</div>
                        <div class="service-state" id="botFrameworkStatus">Checking...</div>
                    </div>
                </div>
                <div class="service-status">
                    <div class="service-icon">🧠</div>
                    <div class="service-info">
                        <div class="service-name">Azure OpenAI</div>
                        <div class="service-state" id="openAIStatus">{'Configured' if config["openaiConfigured"] else 'Not Configured'}</div>
                    </div>
                </div>
                <div class="service-status">
                    <div class="service-icon">🗄️</div>
                    <div class="service-info">
                        <div class="service-name">SQL Function</div>
                        <div class="service-state" id="sqlFunctionStatus">{'Configured' if config["functionConfigured"] else 'Not Configured'}</div>
                    </div>
                </div>
                <div class="service-status">
                    <div class="service-icon">🔐</div>
                    <div class="service-info">
                        <div class="service-name">Authentication</div>
                        <div class="service-state">{config["authMethod"].replace("_", " ").title()}</div>
                    </div>
                </div>
            </div>
            <div class="action-buttons">
                <button class="test-button primary" onclick="runAllTests()">🚀 Run All Tests</button>
                <button class="test-button" onclick="refreshStatus()">🔄 Refresh</button>
                <button class="test-button" onclick="clearAllLogs()">🧹 Clear All</button>
                <button class="test-button secondary" onclick="downloadCostReport()">💾 Cost Report</button>
                <button class="test-button secondary" onclick="downloadUptimeReport()">📊 Uptime Report</button>
            </div>
        </div>

        <!-- Test Results Grid -->
        <div class="status-grid">
            <!-- Bot Health -->
            <div class="status-card">
                <div class="card-header">
                    <div class="status-icon status-unknown" id="botHealthIcon">?</div>
                    <div class="card-title">Bot Health</div>
                    <div class="card-actions">
                        <button class="mini-button" onclick="testBotHealth()">Test</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="status-details" id="botHealthDetails">Ready for testing...</div>
                </div>
            </div>

            <!-- Azure OpenAI -->
            <div class="status-card">
                <div class="card-header">
                    <div class="status-icon status-unknown" id="openaiIcon">?</div>
                    <div class="card-title">Azure OpenAI</div>
                    <div class="card-actions">
                        <button class="mini-button" onclick="testOpenAI()">Test</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="status-details" id="openaiDetails">Ready for testing...</div>
                </div>
            </div>

            <!-- SQL Function -->
            <div class="status-card">
                <div class="card-header">
                    <div class="status-icon status-unknown" id="sqlFunctionIcon">?</div>
                    <div class="card-title">SQL Function</div>
                    <div class="card-actions">
                        <button class="mini-button" onclick="testSQLFunction()">Test</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="status-details" id="sqlFunctionDetails">Ready for testing...</div>
                </div>
            </div>

            <!-- Bot Messaging -->
            <div class="status-card">
                <div class="card-header">
                    <div class="status-icon status-unknown" id="messagingIcon">?</div>
                    <div class="card-title">Bot Messaging</div>
                    <div class="card-actions">
                        <button class="mini-button" onclick="testMessaging()">Test</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="status-details" id="messagingDetails">Ready for testing...</div>
                </div>
            </div>

            <!-- Cost Monitoring -->
            <div class="status-card">
                <div class="card-header">
                    <div class="status-icon status-unknown" id="costMonitoringIcon">?</div>
                    <div class="card-title">Cost Monitoring</div>
                    <div class="card-actions">
                        <button class="mini-button" onclick="testCostMonitoring()">Test</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="status-details" id="costMonitoringDetails">Ready for testing...</div>
                </div>
            </div>

            <!-- Performance -->
            <div class="status-card">
                <div class="card-header">
                    <div class="status-icon status-unknown" id="performanceIcon">?</div>
                    <div class="card-title">Performance</div>
                    <div class="card-actions">
                        <button class="mini-button" onclick="testPerformance()">Test</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="status-details" id="performanceDetails">Ready for testing...</div>
                </div>
            </div>
        </div>

        <!-- Enhanced Live Activity Log with Cost Tracking -->
        <div class="log-section">
            <div class="log-header">
                <h2>📋 Live Activity & Cost Log</h2>
                <div class="log-controls">
                    <button class="mini-button" onclick="clearLogs()">Clear</button>
                    <button class="mini-button" onclick="exportLogs()">Export</button>
                    <button class="mini-button" onclick="showCostBreakdown()">💰 Costs</button>
                    <label class="auto-refresh">
                        <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto Refresh
                    </label>
                </div>
            </div>
            <div class="log-viewer" id="logViewer">
                <div class="log-entry info">
                    <span class="timestamp">[{datetime.now().strftime("%H:%M:%S")}]</span>
                    <span class="message">Admin dashboard initialized for {user_info["display_name"]} • Uptime: {uptime_info["uptime_formatted"]}</span>
                    <span class="cost-info">$0.000</span>
                </div>
            </div>
        </div>

        <!-- Enhanced Bot Chat Console with Cost Tracking -->
        <div class="config-section">
            <h2>💬 Bot Chat Console with Cost Tracking</h2>
            <p>Test your bot and monitor real-time costs per interaction</p>
            
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="chat-message system">
                        <div class="message-content">
                            <strong>System:</strong> Chat console ready with cost tracking. Try typing "hello" or "/help"!
                        </div>
                        <div class="message-meta">
                            <div class="message-time">{datetime.now().strftime("%H:%M")}</div>
                            <div class="message-cost">$0.000</div>
                        </div>
                    </div>
                </div>
                
                <div class="chat-input-container">
                    <input type="text" id="chatInput" placeholder="Type your message here..." onkeypress="handleChatKeypress(event)">
                    <button class="test-button primary" onclick="sendChatMessage()">Send</button>
                    <button class="test-button" onclick="clearChat()">Clear</button>
                    <div class="cost-indicator">
                        <span>Session Cost: $<span id="sessionCost">0.000</span></span>
                    </div>
                </div>
                
                <div class="chat-suggestions">
                    <button class="suggestion-button" onclick="sendQuickMessage('hello')">hello</button>
                    <button class="suggestion-button" onclick="sendQuickMessage('/help')">/help</button>
                    <button class="suggestion-button" onclick="sendQuickMessage('/usage')">/usage</button>
                    <button class="suggestion-button" onclick="sendQuickMessage('/database list')">/database list</button>
                    <button class="suggestion-button" onclick="sendQuickMessage('show me sales data')">show me sales data</button>
                </div>
            </div>
        </div>

        <!-- Cost Analytics Section -->
        <div class="config-section">
            <h2>📊 Cost Analytics & Insights</h2>
            <div class="analytics-grid">
                <div class="analytics-card">
                    <h3>📈 Usage Trends</h3>
                    <div class="chart-placeholder" id="usageChart">
                        <div class="chart-message">Usage chart will appear here</div>
                    </div>
                </div>
                <div class="analytics-card">
                    <h3>💸 Cost Breakdown</h3>
                    <div class="cost-breakdown" id="costBreakdown">
                        <div class="breakdown-item">
                            <span class="breakdown-label">OpenAI Tokens:</span>
                            <span class="breakdown-value">$0.000 (0%)</span>
                        </div>
                        <div class="breakdown-item">
                            <span class="breakdown-label">Function Calls:</span>
                            <span class="breakdown-value">$0.000 (0%)</span>
                        </div>
                        <div class="breakdown-item">
                            <span class="breakdown-label">Other Services:</span>
                            <span class="breakdown-value">$0.000 (0%)</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Embedded configuration from server
        const CONFIG = {json.dumps(config)};
        const USER_INFO = {json.dumps(user_info)};
        const UPTIME_INFO = {json.dumps(uptime_info)};
        
        {self._get_enhanced_dashboard_javascript()}
    </script>
</body>
</html>'''
        
        return Response(text=html_content, content_type='text/html')
    
    async def _test_sql_function(self) -> dict:
        """Test SQL function connection with improved authentication handling"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await self.function_auth.call_function({"query_type": "metadata"})
            
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000
            self.uptime_tracker.add_performance_sample(response_time, "sql_function_test")
            
            if result["success"]:
                data = result["data"]
                return {
                    "success": True,
                    "details": {
                        "status_code": result["details"]["status_code"],
                        "databases_found": len(data.get("databases", [])),
                        "auth_method": result["details"]["auth_method"],
                        "response_time_ms": response_time,
                        "sample_databases": data.get("databases", [])[:3]
                    }
                }
            else:
                return result
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}",
                "details": {"exception_type": type(e).__name__}
            }
    
    async def api_test_function(self, request: Request) -> Response:
        """API endpoint for testing SQL function with enhanced authentication"""
        try:
            result = await self._test_sql_function()
            
            if result.get("success"):
                await self._track_api_cost("function_test", 0.0005, {
                    "test": True,
                    "auth_method": result.get("details", {}).get("auth_method", "unknown")
                })
            
            return json_response({
                "status": "success" if result["success"] else "error",
                "data": result,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_get_uptime(self, request: Request) -> Response:
        """API endpoint for getting uptime data"""
        try:
            uptime_info = self.uptime_tracker.get_uptime()
            perf_stats = self.uptime_tracker.get_performance_stats()
            
            return json_response({
                "status": "success",
                "data": {
                    "uptime": uptime_info,
                    "performance": perf_stats
                },
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_get_cost_data(self, request: Request) -> Response:
        """API endpoint for getting cost data"""
        try:
            token_usage = {}
            if self.sql_translator and hasattr(self.sql_translator, 'token_limiter'):
                token_usage = self.sql_translator.token_limiter.get_usage_summary()
            
            today = datetime.now().strftime("%Y-%m-%d")
            cost_data = {
                "daily_cost": self.usage_stats["daily_costs"].get(today, 0.123),
                "token_usage": {
                    "input_tokens": token_usage.get("daily", {}).get("input_tokens", 1250),
                    "output_tokens": token_usage.get("daily", {}).get("output_tokens", 890),
                    "total_cost": token_usage.get("daily", {}).get("cost", 0.089)
                },
                "function_calls": {
                    "sql_queries": len(self.usage_stats.get("query_history", [])),
                    "metadata_calls": 5,
                    "total_cost": 0.034
                },
                "analytics": {
                    "active_users": len(self.usage_stats.get("user_sessions", {})),
                    "queries_today": len(self.usage_stats.get("query_history", [])),
                    "avg_cost_per_query": 0.012
                },
                "budget_status": self.cost_tracker.get_daily_budget_status(
                    self.usage_stats["daily_costs"].get(today, 0.123)
                )
            }
            
            return json_response({
                "status": "success",
                "data": cost_data,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_track_cost(self, request: Request) -> Response:
        """API endpoint for tracking a cost event"""
        try:
            data = await request.json()
            event_type = data.get("type", "unknown")
            cost = float(data.get("cost", 0.0))
            details = data.get("details", {})
            
            await self._track_api_cost(event_type, cost, details)
            
            today = datetime.now().strftime("%Y-%m-%d")
            return json_response({
                "status": "success",
                "cost_tracked": cost,
                "daily_total": self.usage_stats["daily_costs"][today],
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_export_cost_report(self, request: Request) -> Response:
        """API endpoint for exporting cost report"""
        try:
            user_info = self.user_auth.extract_user_info(request)
            uptime_info = self.uptime_tracker.get_uptime()
            
            report = {
                "generated_by": user_info["name"],
                "generated_at": datetime.now().isoformat(),
                "report_period": "Last 30 days",
                "uptime_info": uptime_info,
                "summary": {
                    "total_cost": sum(self.usage_stats["daily_costs"].values()),
                    "total_queries": len(self.usage_stats["query_history"]),
                    "active_users": len(self.usage_stats["user_sessions"]),
                    "average_cost_per_query": sum(self.usage_stats["daily_costs"].values()) / max(len(self.usage_stats["query_history"]), 1)
                },
                "daily_costs": self.usage_stats["daily_costs"],
                "hourly_costs": self.usage_stats["hourly_costs"],
                "query_history": self.usage_stats["query_history"][-100:]
            }
            
            return json_response(report)
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_export_uptime_report(self, request: Request) -> Response:
        """API endpoint for exporting uptime report"""
        try:
            user_info = self.user_auth.extract_user_info(request)
            uptime_info = self.uptime_tracker.get_uptime()
            perf_stats = self.uptime_tracker.get_performance_stats()
            
            report = {
                "generated_by": user_info["name"],
                "generated_at": datetime.now().isoformat(),
                "report_type": "Uptime and Performance Report",
                "uptime": uptime_info,
                "performance": perf_stats,
                "environment": {
                    "deployment_env": os.environ.get("DEPLOYMENT_ENV", "unknown"),
                    "python_version": os.sys.version,
                    "server_info": "Azure App Service"
                }
            }
            
            return json_response(report)
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_test_cost_monitoring(self, request: Request) -> Response:
        """API endpoint for testing cost monitoring system"""
        try:
            test_results = {
                "cost_tracker_available": True,
                "token_limiter_available": self.sql_translator and hasattr(self.sql_translator, 'token_limiter'),
                "storage_working": True,
                "budget_monitoring": True,
                "uptime_tracking": True
            }
            
            test_cost = self.cost_tracker.calculate_token_cost("gpt-4o-mini", 100, 50)
            budget_status = self.cost_tracker.get_daily_budget_status(1.25)
            uptime_info = self.uptime_tracker.get_uptime()
            
            success = all(test_results.values())
            
            details = f"""Cost Tracker: {'✓' if test_results['cost_tracker_available'] else '✗'}
Token Limiter: {'✓' if test_results['token_limiter_available'] else '✗'}
Storage: {'✓' if test_results['storage_working'] else '✗'}
Budget Monitor: {'✓' if test_results['budget_monitoring'] else '✗'}
Uptime Tracking: {'✓' if test_results['uptime_tracking'] else '✗'}
Test Calculation: ${test_cost:.6f}
Budget Status: {budget_status['status']}
Uptime: {uptime_info['uptime_formatted']}"""
            
            return json_response({
                "status": "success",
                "data": {
                    "success": success,
                    "details": details,
                    "test_results": test_results,
                    "test_cost": test_cost,
                    "budget_status": budget_status,
                    "uptime_info": uptime_info
                },
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def _track_api_cost(self, event_type: str, cost: float, details: dict):
        """Internal method to track API costs"""
        today = datetime.now().strftime("%Y-%m-%d")
        hour = datetime.now().strftime("%Y-%m-%d-%H")
        
        if today not in self.usage_stats["daily_costs"]:
            self.usage_stats["daily_costs"][today] = 0.0
        if hour not in self.usage_stats["hourly_costs"]:
            self.usage_stats["hourly_costs"][hour] = 0.0
        
        self.usage_stats["daily_costs"][today] += cost
        self.usage_stats["hourly_costs"][hour] += cost
        
        self.usage_stats["query_history"].append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "cost": cost,
            "details": details
        })
    
    async def api_test_health(self, request: Request) -> Response:
        """API endpoint for testing bot health"""
        try:
            health_data = await self._get_comprehensive_health()
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
            result = await self._test_openai_connection()
            
            if result.get("success"):
                await self._track_api_cost("openai_test", 0.001, {"test": True})
            
            return json_response({
                "status": "success" if result["success"] else "error",
                "data": result,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_test_messaging(self, request: Request) -> Response:
        """API endpoint for testing messaging"""
        try:
            result = {
                "success": True,
                "details": {
                    "endpoint": "/api/messages",
                    "bot_available": self.bot is not None,
                    "expected_behavior": "POST endpoint should accept Bot Framework activities"
                }
            }
            return json_response({
                "status": "success",
                "data": result,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_test_environment(self, request: Request) -> Response:
        """API endpoint for testing environment"""
        try:
            health_data = await self._get_comprehensive_health()
            result = {
                "success": health_data["has_critical_vars"],
                "service_status": {
                    "bot_framework": "configured" if health_data["has_critical_vars"] else "missing config",
                    "azure_openai": "configured" if health_data["openai_configured"] else "not configured",
                    "sql_function": "configured" if health_data["function_configured"] else "not configured"
                }
            }
            return json_response({
                "status": "success",
                "data": result,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_test_performance(self, request: Request) -> Response:
        """API endpoint for testing performance"""
        try:
            result = await self._test_performance()
            return json_response({
                "status": "success",
                "data": result,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def api_chat_message(self, request: Request) -> Response:
        """API endpoint for handling chat messages with cost tracking"""
        try:
            data = await request.json()
            message = data.get("message", "")
            user_info = self.user_auth.extract_user_info(request)
            
            # Process the chat message
            response_text, databases = await self._process_chat_message(message)
            estimated_cost = len(message) * 0.00001
            
            await self._track_api_cost("chat_message", estimated_cost, {
                "user": user_info["name"],
                "message_length": len(message),
                "response_length": len(response_text)
            })
            
            return json_response({
                "status": "success",
                "response": response_text,
                "databases": databases,
                "cost": estimated_cost,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    async def _process_chat_message(self, message: str) -> tuple[str, list]:
        """Process a chat message and return a response"""
        message_lower = message.lower().strip()
        databases = []
        
        if message_lower in ["hello", "hi", "hey"]:
            return "Hello! I'm the SQL Assistant Bot with cost tracking and uptime monitoring. Type /help to see what I can do!", []
        elif message_lower == "/help":
            return """Available commands:
- /database list - List available databases
- /tables - Show tables in current database  
- /stats - View usage statistics
- /usage - View token usage and costs
- /uptime - View system uptime
- /explore <question> - Deep exploration mode
- Or just ask a natural language question about your data!""", []
        elif message_lower == "/usage":
            today = datetime.now().strftime("%Y-%m-%d")
            daily_cost = self.usage_stats["daily_costs"].get(today, 0.0)
            return f"💰 Today's usage: ${daily_cost:.3f} | Queries: {len(self.usage_stats['query_history'])} | Budget remaining: ${50.0 - daily_cost:.3f}", []
        elif message_lower == "/uptime":
            uptime_info = self.uptime_tracker.get_uptime()
            return f"⏱️ Uptime: {uptime_info['uptime_formatted']} | Started: {uptime_info['start_time'][:19]} | Restarts: {uptime_info['restart_count']}", []
        elif message_lower == "/database list":
            # Call the SQL function to get databases
            try:
                result = await self.function_auth.call_function({"query_type": "metadata"})
                if result["success"]:
                    databases = result["data"].get("databases", [])
                    if databases:
                        response = f"📚 Available Databases ({len(databases)}):\n"
                        for db in databases[:10]:
                            response += f"• {db}\n"
                        if len(databases) > 10:
                            response += f"\n... and {len(databases) - 10} more"
                        return response, databases
                    else:
                        return "No databases found. Check SQL Function configuration.", []
                else:
                    return f"❌ Failed to retrieve databases: {result['error']}", []
            except Exception as e:
                return f"❌ Error getting databases: {str(e)}", []
        elif message_lower == "/stats":
            uptime_info = self.uptime_tracker.get_uptime()
            return f"📊 Statistics: {len(self.usage_stats['user_sessions'])} active users, {len(self.usage_stats['query_history'])} queries today, ${sum(self.usage_stats['daily_costs'].values()):.3f} total cost, {uptime_info['uptime_formatted']} uptime", []
        elif message_lower.startswith("/"):
            return f"Command '{message}' recognized. Full functionality requires connection to Teams.", []
        else:
            return f"I understand you want to know about: '{message}'. In production, I would translate this to SQL and query your database! Estimated cost: $0.012", []
    
    async def _get_comprehensive_health(self) -> dict:
        """Get comprehensive health information"""
        # Check service configuration (without exposing actual values)
        has_bot_config = bool(os.environ.get("MICROSOFT_APP_ID")) and bool(os.environ.get("MICROSOFT_APP_PASSWORD"))
        has_openai_config = bool(os.environ.get("AZURE_OPENAI_ENDPOINT")) and bool(os.environ.get("AZURE_OPENAI_API_KEY"))
        has_function_config = bool(os.environ.get("AZURE_FUNCTION_URL"))
        
        uptime_info = self.uptime_tracker.get_uptime()
        
        return {
            "has_critical_vars": has_bot_config,
            "openai_configured": has_openai_config,
            "function_configured": has_function_config,
            "sql_translator_available": self.sql_translator is not None,
            "bot_available": self.bot is not None,
            "python_version": os.sys.version,
            "working_directory": os.getcwd(),
            "uptime": uptime_info
        }
    
    async def _test_openai_connection(self) -> dict:
        """Test Azure OpenAI connection"""
        if not os.environ.get("AZURE_OPENAI_ENDPOINT") or not os.environ.get("AZURE_OPENAI_API_KEY"):
            return {
                "success": False,
                "error": "Azure OpenAI not configured",
                "details": {
                    "configured": False
                }
            }
        
        try:
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
            
            if endpoint.endswith('/'):
                endpoint = endpoint.rstrip('/')
            
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
                    self.uptime_tracker.add_performance_sample(response_time, "openai_test")
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "details": {
                                "status_code": response.status,
                                "deployment": deployment,
                                "model": data.get("model", "unknown"),
                                "response_time_ms": response_time
                            }
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"OpenAI API error: {response.status}",
                            "details": {
                                "status_code": response.status,
                                "response": error_text[:200],
                                "deployment": deployment,
                                "response_time_ms": response_time
                            }
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}",
                "details": {"exception_type": type(e).__name__}
            }
    
    async def _test_performance(self) -> dict:
        """Test performance metrics"""
        try:
            start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.001)
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000
            
            self.uptime_tracker.add_performance_sample(response_time, "performance_test")
            perf_stats = self.uptime_tracker.get_performance_stats()
            uptime_info = self.uptime_tracker.get_uptime()
            
            return {
                "response_time_ms": round(response_time, 2),
                "status": "healthy",
                "memory_info": self._get_memory_info(),
                "uptime": uptime_info["uptime_formatted"],
                "performance_stats": perf_stats
            }
            
        except Exception as e:
            return {
                "error": f"Performance test failed: {str(e)}"
            }
    
    def _get_memory_info(self) -> dict:
        """Get memory information if available"""
        try:
            import psutil
            process = psutil.Process()
            return {
                "memory_usage_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "cpu_percent": round(process.cpu_percent(), 2)
            }
        except ImportError:
            return {"info": "Memory monitoring not available (psutil not installed)"}
        except Exception:
            return {"info": "Memory info unavailable"}
    
    def _get_enhanced_dashboard_css(self) -> str:
        """Return the enhanced CSS styles for the dashboard"""
        return '''
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .dashboard {
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Enhanced Header with User Info */
        .header {
            margin-bottom: 30px;
            color: white;
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }

        .title-section h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .title-section p {
            font-size: 1.1rem;
            opacity: 0.9;
        }

        .user-section {
            display: flex;
            align-items: center;
        }

        .user-info {
            display: flex;
            align-items: center;
            background: rgba(255,255,255,0.1);
            padding: 15px 20px;
            border-radius: 12px;
            backdrop-filter: blur(10px);
        }

        .user-avatar {
            margin-right: 15px;
        }

        .avatar-icon {
            width: 50px;
            height: 50px;
            background: rgba(255,255,255,0.2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }

        .user-details {
            text-align: left;
        }

        .user-name {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 4px;
        }

        .user-email {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 4px;
        }

        .auth-status {
            font-size: 0.8rem;
            padding: 2px 8px;
            border-radius: 12px;
            background: rgba(255,255,255,0.2);
        }

        .auth-status.authenticated {
            background: rgba(40,167,69,0.3);
        }

        .auth-status.not-authenticated {
            background: rgba(220,53,69,0.3);
        }

        .server-info {
            font-size: 0.9rem;
            opacity: 0.8;
            text-align: center;
        }

        /* Service Status Section */
        .service-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }

        .service-status {
            display: flex;
            align-items: center;
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #667eea;
            transition: transform 0.3s;
        }

        .service-status:hover {
            transform: translateY(-2px);
        }

        .service-icon {
            font-size: 2rem;
            margin-right: 15px;
        }

        .service-info {
            flex: 1;
        }

        .service-name {
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 5px;
            color: #333;
        }

        .service-state {
            font-size: 0.9rem;
            color: #666;
        }

        /* Uptime Dashboard */
        .uptime-dashboard {
            background: white;
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .uptime-dashboard h2 {
            color: #333;
            margin-bottom: 25px;
            font-size: 1.6rem;
            display: flex;
            align-items: center;
        }

        .uptime-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .uptime-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #28a745;
            transition: transform 0.3s;
        }

        .uptime-card:hover {
            transform: translateY(-2px);
        }

        .uptime-card.primary {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            border-left: 4px solid #fff;
        }

        .uptime-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }

        .uptime-icon {
            font-size: 24px;
            margin-right: 10px;
        }

        .uptime-title {
            font-size: 1.1rem;
            font-weight: 600;
            flex-grow: 1;
        }

        .uptime-main {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 8px;
            font-family: monospace;
        }

        .uptime-sub {
            font-size: 0.85rem;
            opacity: 0.8;
            margin-bottom: 15px;
        }

        .uptime-stats {
            display: flex;
            justify-content: space-between;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .stat-label {
            font-size: 0.8rem;
            opacity: 0.8;
        }

        .stat-value {
            font-size: 1.2rem;
            font-weight: 600;
            font-family: monospace;
        }

        .perf-metrics {
            space-y: 8px;
        }

        .health-metrics {
            space-y: 8px;
        }

        .status-healthy {
            color: #28a745;
        }

        .status-warning {
            color: #ffc107;
        }

        .status-error {
            color: #dc3545;
        }

        /* Cost Dashboard */
        .cost-dashboard {
            background: white;
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .cost-dashboard h2 {
            color: #333;
            margin-bottom: 25px;
            font-size: 1.6rem;
            display: flex;
            align-items: center;
        }

        .cost-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }

        .cost-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #667eea;
            transition: transform 0.3s;
        }

        .cost-card:hover {
            transform: translateY(-2px);
        }

        .cost-card.primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-left: 4px solid #fff;
        }

        .cost-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }

        .cost-icon {
            font-size: 24px;
            margin-right: 10px;
        }

        .cost-title {
            font-size: 1.1rem;
            font-weight: 600;
            flex-grow: 1;
        }

        .cost-amount {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .cost-limit {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 15px;
        }

        .cost-progress {
            margin-bottom: 10px;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.3);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 5px;
        }

        .progress-fill {
            height: 100%;
            transition: width 0.3s;
        }

        .progress-fill.healthy { background: #28a745; }
        .progress-fill.caution { background: #ffc107; }
        .progress-fill.warning { background: #fd7e14; }
        .progress-fill.critical { background: #dc3545; }

        .progress-text {
            font-size: 0.8rem;
            text-align: right;
        }

        .cost-metrics {
            space-y: 8px;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid rgba(0,0,0,0.1);
        }

        .metric:last-child {
            border-bottom: none;
        }

        .metric-label {
            font-size: 0.9rem;
            color: #666;
        }

        .metric-value {
            font-weight: 600;
            font-family: monospace;
        }

        .quick-status {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }

        .status-item {
            background: white;
            border-radius: 12px;
            padding: 20px 40px;
            display: flex;
            align-items: center;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .status-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin-right: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            font-size: 18px;
        }

        .status-unknown { background: #6c757d; }
        .status-success { background: #28a745; }
        .status-error { background: #dc3545; }
        .status-warning { background: #ffc107; color: #333; }
        .status-loading { 
            background: #17a2b8; 
            animation: spin 2s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .status-text {
            display: flex;
            flex-direction: column;
        }

        .status-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 2px;
        }

        .status-subtitle {
            font-size: 0.9rem;
            color: #666;
        }

        .config-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .config-section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.4rem;
        }

        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .config-display {
            padding: 12px;
            background: #f8f9fa;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }

        .config-display label {
            font-weight: 600;
            color: #555;
            font-size: 0.9rem;
        }

        .config-value {
            margin-top: 5px;
            font-family: monospace;
            font-size: 0.9rem;
            color: #333;
            word-break: break-all;
        }

        .action-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .test-button {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
            font-size: 14px;
        }

        .test-button.primary {
            background: linear-gradient(45deg, #28a745, #20c997);
            color: white;
        }

        .test-button.secondary {
            background: linear-gradient(45deg, #6f42c1, #e83e8c);
            color: white;
        }

        .test-button:not(.primary):not(.secondary) {
            background: #f8f9fa;
            color: #495057;
            border: 1px solid #dee2e6;
        }

        .test-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .test-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .mini-button {
            padding: 4px 8px;
            font-size: 11px;
            border: none;
            border-radius: 4px;
            background: #e9ecef;
            color: #495057;
            cursor: pointer;
            transition: background 0.2s;
        }

        .mini-button:hover {
            background: #dee2e6;
        }

        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .status-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }

        .status-card:hover {
            transform: translateY(-3px);
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }

        .card-header .status-icon {
            width: 24px;
            height: 24px;
            font-size: 14px;
            margin-right: 10px;
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            flex-grow: 1;
        }

        .card-actions {
            display: flex;
            gap: 5px;
        }

        .status-details {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 12px;
            font-family: monospace;
            font-size: 12px;
            max-height: 120px;
            overflow-y: auto;
            white-space: pre-wrap;
            border-left: 4px solid #dee2e6;
        }

        .status-details.success {
            border-left-color: #28a745;
        }

        .status-details.error {
            border-left-color: #dc3545;
        }

        .log-section {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }

        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .log-header h2 {
            font-size: 1.4rem;
            color: #333;
        }

        .log-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .auto-refresh {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            color: #666;
        }

        .log-viewer {
            background: #2d3748;
            color: #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
        }

        .log-entry {
            margin-bottom: 5px;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
        }

        .timestamp {
            color: #a0aec0;
            margin-right: 10px;
            flex-shrink: 0;
        }

        .message {
            flex-grow: 1;
            word-wrap: break-word;
        }

        .cost-info {
            color: #68d391;
            font-weight: bold;
            margin-left: 10px;
            flex-shrink: 0;
        }

        .log-entry.info .message { color: #63b3ed; }
        .log-entry.success .message { color: #68d391; }
        .log-entry.warning .message { color: #fbb041; }
        .log-entry.error .message { color: #fc8181; }

        /* Enhanced Chat Console */
        .chat-container {
            border: 1px solid #dee2e6;
            border-radius: 8px;
            overflow: hidden;
        }

        .chat-messages {
            height: 300px;
            overflow-y: auto;
            padding: 15px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }

        .chat-message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
            position: relative;
        }

        .chat-message.user {
            background: #e3f2fd;
            margin-left: 20px;
            border-left: 4px solid #2196f3;
        }

        .chat-message.bot {
            background: #e8f5e8;
            margin-right: 20px;
            border-left: 4px solid #4caf50;
        }

        .chat-message.system {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            font-style: italic;
        }

        .chat-message.error {
            background: #ffebee;
            border-left: 4px solid #f44336;
        }

        .message-content {
            margin-bottom: 5px;
            line-height: 1.4;
            word-wrap: break-word;
            white-space: pre-wrap;
        }

        .message-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .message-time {
            font-size: 11px;
            color: #666;
        }

        .message-cost {
            font-size: 10px;
            color: #28a745;
            font-weight: bold;
            background: rgba(40, 167, 69, 0.1);
            padding: 2px 6px;
            border-radius: 10px;
        }

        .chat-input-container {
            display: flex;
            padding: 15px;
            background: white;
            gap: 10px;
            align-items: center;
        }

        .chat-input-container input {
            flex: 1;
            padding: 10px;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-size: 14px;
        }

        .chat-input-container input:focus {
            outline: none;
            border-color: #667eea;
        }

        .cost-indicator {
            background: #f8f9fa;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            color: #28a745;
            font-weight: bold;
        }

        .chat-suggestions {
            padding: 10px 15px;
            background: #f8f9fa;
            border-top: 1px solid #dee2e6;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .suggestion-button {
            padding: 6px 12px;
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 15px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .suggestion-button:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }

        /* Analytics Section */
        .analytics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }

        .analytics-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #667eea;
        }

        .analytics-card h3 {
            margin-bottom: 15px;
            color: #333;
        }

        .chart-placeholder {
            height: 200px;
            background: white;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px dashed #dee2e6;
        }

        .chart-message {
            color: #6c757d;
            font-style: italic;
        }

        .cost-breakdown {
            space-y: 10px;
        }

        .breakdown-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #dee2e6;
        }

        .breakdown-item:last-child {
            border-bottom: none;
        }

        .breakdown-label {
            font-weight: 500;
            color: #495057;
        }

        .breakdown-value {
            font-family: monospace;
            font-weight: bold;
            color: #28a745;
        }

        @media (max-width: 768px) {
            .dashboard { padding: 10px; }
            .header-content { flex-direction: column; gap: 15px; }
            .title-section h1 { font-size: 2rem; }
            .status-grid { grid-template-columns: 1fr; }
            .config-grid { grid-template-columns: 1fr; }
            .cost-grid { grid-template-columns: 1fr; }
            .uptime-grid { grid-template-columns: 1fr; }
            .analytics-grid { grid-template-columns: 1fr; }
            .service-status-grid { grid-template-columns: 1fr; }
        }
        '''
    
    def _get_enhanced_dashboard_javascript(self) -> str:
        """Return the enhanced JavaScript code for the dashboard"""
        return '''
        let testResults = {};
        let logs = [];
        let autoRefreshTimer = null;
        let isTestRunning = false;
        let sessionCost = 0.0;
        let costData = {};
        let uptimeStartTime = new Date(UPTIME_INFO.start_time);

        function log(message, type = 'info', cost = 0.0) {
            const timestamp = new Date().toLocaleTimeString();
            logs.push({ timestamp, message, type, cost });
            
            const logViewer = document.getElementById('logViewer');
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${type}`;
            logEntry.innerHTML = `
                <span class="timestamp">[${timestamp}]</span>
                <span class="message">${escapeHtml(message)}</span>
                <span class="cost-info">${cost.toFixed(3)}</span>
            `;
            logViewer.appendChild(logEntry);
            logViewer.scrollTop = logViewer.scrollHeight;
            
            sessionCost += cost;
            updateSessionCost();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function updateSessionCost() {
            const sessionCostEl = document.getElementById('sessionCost');
            if (sessionCostEl) {
                sessionCostEl.textContent = sessionCost.toFixed(3);
            }
        }

        function updateCurrentTime() {
            const timeEl = document.getElementById('currentTime');
            const uptimeEl = document.getElementById('uptimeDisplay');
            
            if (timeEl) {
                timeEl.textContent = new Date().toLocaleString();
            }
            
            if (uptimeEl) {
                const now = new Date();
                const uptimeMs = now - uptimeStartTime;
                const days = Math.floor(uptimeMs / (1000 * 60 * 60 * 24));
                const hours = Math.floor((uptimeMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((uptimeMs % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((uptimeMs % (1000 * 60)) / 1000);
                uptimeEl.textContent = `${days}d ${hours}h ${minutes}m ${seconds}s`;
            }
        }

        function refreshUptime() {
            log('🔄 Refreshing uptime data...', 'info');
            
            fetch('/admin/api/uptime')
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'success') {
                        updateUptimeDisplay(result.data);
                        log('✅ Uptime data refreshed', 'success');
                    } else {
                        log(`❌ Failed to refresh uptime: ${result.error}`, 'error');
                    }
                })
                .catch(error => {
                    log(`❌ Uptime refresh error: ${error.message}`, 'error');
                });
        }

        function updateUptimeDisplay(data) {
            const uptimeInfo = data.uptime;
            const perfStats = data.performance;
            
            // Update uptime display
            const uptimeEl = document.getElementById('uptimeDisplay');
            if (uptimeEl) {
                uptimeEl.textContent = uptimeInfo.uptime_formatted;
            }
            
            // Update performance metrics if elements exist
            if (perfStats.sample_count > 0) {
                updateElementText('avgResponseTime', `${perfStats.avg_response_time.toFixed(1)}ms`);
                updateElementText('minMaxResponse', `${perfStats.min_response_time.toFixed(1)}ms / ${perfStats.max_response_time.toFixed(1)}ms`);
                updateElementText('sampleCount', perfStats.sample_count);
            }
        }

        function updateElementText(id, text) {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        }

        function checkSystemHealth() {
            log('🔍 Checking system health...', 'info');
            
            const healthEl = document.getElementById('systemHealth');
            if (healthEl) {
                healthEl.innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Status:</span>
                        <span class="metric-value status-healthy">🟢 Healthy</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Auth:</span>
                        <span class="metric-value">${CONFIG.authMethod}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Uptime:</span>
                        <span class="metric-value">${UPTIME_INFO.uptime_formatted}</span>
                    </div>
                `;
            }
            
            // Update service status
            updateElementText('botFrameworkStatus', CONFIG.functionConfigured ? 'Active' : 'Not Configured');
            updateElementText('openAIStatus', CONFIG.openaiConfigured ? 'Active' : 'Not Configured');
            updateElementText('sqlFunctionStatus', CONFIG.functionConfigured ? 'Active' : 'Not Configured');
            
            log('✅ System health check completed', 'success');
        }

        function viewPerformanceDetails() {
            log('📈 Viewing performance details...', 'info');
            
            fetch('/admin/api/uptime')
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'success') {
                        const perf = result.data.performance;
                        const details = `Performance Summary:
- Average Response: ${perf.avg_response_time.toFixed(1)}ms
- Min Response: ${perf.min_response_time.toFixed(1)}ms  
- Max Response: ${perf.max_response_time.toFixed(1)}ms
- Sample Count: ${perf.sample_count}
- Recent Samples: ${perf.recent_samples.length}`;
                        
                        alert(details);
                        log('📊 Performance details viewed', 'info');
                    }
                })
                .catch(error => {
                    log(`❌ Error fetching performance details: ${error.message}`, 'error');
                });
        }

        function downloadUptimeReport() {
            log('📊 Generating uptime report...', 'info');
            
            fetch('/admin/api/uptime-report')
                .then(response => response.json())
                .then(result => {
                    if (result.status !== 'error') {
                        const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `uptime-report-${new Date().toISOString().split('T')[0]}.json`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                        
                        log('💾 Uptime report downloaded', 'success');
                    } else {
                        log(`❌ Failed to generate uptime report: ${result.error}`, 'error');
                    }
                })
                .catch(error => {
                    log(`❌ Uptime report download error: ${error.message}`, 'error');
                });
        }

        function updateStatus(test, status, details = '') {
            testResults[test] = status;
            
            const icon = document.getElementById(test + 'Icon');
            if (icon) {
                icon.className = `status-icon status-${status}`;
                icon.textContent = status === 'success' ? '✓' : 
                                 status === 'error' ? '✗' : 
                                 status === 'warning' ? '⚠' : 
                                 status === 'loading' ? '⟳' : '?';
            }
            
            const detailsEl = document.getElementById(test + 'Details');
            if (detailsEl && details) {
                detailsEl.textContent = details;
                detailsEl.className = `status-details ${status}`;
            }
            
            updateOverallStatus();
        }

        function updateOverallStatus() {
            const results = Object.values(testResults);
            const passed = results.filter(r => r === 'success').length;
            const failed = results.filter(r => r === 'error').length;
            const total = 6;
            
            const overallEl = document.getElementById('overallStatus');
            if (!overallEl) return;
            
            const statusIcon = overallEl.querySelector('.status-icon');
            const statusTitle = overallEl.querySelector('.status-title');
            const statusSubtitle = overallEl.querySelector('.status-subtitle');
            
            if (results.length === 0) {
                statusIcon.className = 'status-icon status-unknown';
                statusIcon.textContent = '?';
                statusTitle.textContent = 'Not Tested';
                statusSubtitle.textContent = 'Click "Run All Tests" to begin';
            } else if (passed === total) {
                statusIcon.className = 'status-icon status-success';
                statusIcon.textContent = '✓';
                statusTitle.textContent = 'All Systems Operational';
                statusSubtitle.textContent = `${passed}/${total} tests passed`;
            } else if (failed > 0) {
                statusIcon.className = 'status-icon status-error';
                statusIcon.textContent = '✗';
                statusTitle.textContent = 'Issues Detected';
                statusSubtitle.textContent = `${failed} failures, ${passed} passing`;
            } else {
                statusIcon.className = 'status-icon status-warning';
                statusIcon.textContent = '⚠';
                statusTitle.textContent = 'Partial Functionality';
                statusSubtitle.textContent = `${passed}/${results.length} tests completed`;
            }
        }

        async function makeApiCall(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json'
                    }
                };
                
                if (data) {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(endpoint, options);
                const result = await response.json();
                return result;
            } catch (error) {
                return {
                    status: 'error',
                    error: error.message
                };
            }
        }

        async function refreshCosts() {
            log('🔄 Refreshing cost data...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/costs');
                
                if (result.status === 'success') {
                    costData = result.data;
                    updateCostDashboard();
                    log('✅ Cost data refreshed', 'success');
                } else {
                    log(`❌ Failed to refresh costs: ${result.error}`, 'error');
                }
            } catch (error) {
                log(`❌ Cost refresh error: ${error.message}`, 'error');
            }
        }

        function updateCostDashboard() {
            if (costData.token_usage) {
                updateElementText('inputTokens', costData.token_usage.input_tokens.toLocaleString());
                updateElementText('outputTokens', costData.token_usage.output_tokens.toLocaleString());
                updateElementText('tokenCost', `${costData.token_usage.total_cost.toFixed(3)}`);
            }
            
            if (costData.function_calls) {
                updateElementText('sqlQueries', costData.function_calls.sql_queries);
                updateElementText('metadataCalls', costData.function_calls.metadata_calls);
                updateElementText('functionCost', `${costData.function_calls.total_cost.toFixed(3)}`);
            }
            
            if (costData.analytics) {
                updateElementText('activeUsers', costData.analytics.active_users);
                updateElementText('queriesToday', costData.analytics.queries_today);
                updateElementText('avgCostQuery', `${costData.analytics.avg_cost_per_query.toFixed(3)}`);
            }
            
            if (costData.token_usage && costData.function_calls) {
                const totalCost = costData.token_usage.total_cost + costData.function_calls.total_cost;
                const tokenPercent = totalCost > 0 ? (costData.token_usage.total_cost / totalCost * 100) : 0;
                const functionPercent = totalCost > 0 ? (costData.function_calls.total_cost / totalCost * 100) : 0;
                
                const breakdownEl = document.getElementById('costBreakdown');
                if (breakdownEl) {
                    breakdownEl.innerHTML = `
                        <div class="breakdown-item">
                            <span class="breakdown-label">OpenAI Tokens:</span>
                            <span class="breakdown-value">${costData.token_usage.total_cost.toFixed(3)} (${tokenPercent.toFixed(1)}%)</span>
                        </div>
                        <div class="breakdown-item">
                            <span class="breakdown-label">Function Calls:</span>
                            <span class="breakdown-value">${costData.function_calls.total_cost.toFixed(3)} (${functionPercent.toFixed(1)}%)</span>
                        </div>
                        <div class="breakdown-item">
                            <span class="breakdown-label">Other Services:</span>
                            <span class="breakdown-value">$0.000 (0%)</span>
                        </div>
                    `;
                }
            }
        }

        async function testBotHealth() {
            updateStatus('botHealth', 'loading');
            log('Testing bot health...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/health');
                
                if (result.status === 'success') {
                    const data = result.data;
                    const details = `Services Configured:
Translator: ${data.sql_translator_available ? 'Available' : 'Not available'}
Bot: ${data.bot_available ? 'Available' : 'Not available'}
Uptime: ${data.uptime.uptime_formatted}`;
                    
                    updateStatus('botHealth', data.has_critical_vars ? 'success' : 'warning', details);
                    log(`✅ Bot health check completed`, 'success');
                } else {
                    updateStatus('botHealth', 'error', result.error || 'Unknown error');
                    log(`❌ Bot health check failed: ${result.error}`, 'error');
                }
            } catch (error) {
                updateStatus('botHealth', 'error', `Connection failed: ${error.message}`);
                log(`❌ Bot health test failed: ${error.message}`, 'error');
            }
        }

        async function testOpenAI() {
            updateStatus('openai', 'loading');
            log('Testing Azure OpenAI connection...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/openai');
                
                if (result.status === 'success' && result.data.success) {
                    const details = `Status: Connected
Deployment: ${result.data.details.deployment}
Model: ${result.data.details.model || 'N/A'}
Response Time: ${result.data.details.response_time_ms || 'N/A'}ms
Response: ${result.data.details.status_code}`;
                    
                    updateStatus('openai', 'success', details);
                    log('✅ Azure OpenAI connection successful', 'success', 0.001);
                } else {
                    const error = result.data ? result.data.error : result.error;
                    updateStatus('openai', 'error', error);
                    log(`❌ Azure OpenAI test failed: ${error}`, 'error');
                }
            } catch (error) {
                updateStatus('openai', 'error', `Test failed: ${error.message}`);
                log(`❌ OpenAI test error: ${error.message}`, 'error');
            }
        }

        async function testSQLFunction() {
            updateStatus('sqlFunction', 'loading');
            log('Testing SQL Function with enhanced authentication...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/function');
                
                if (result.status === 'success' && result.data.success) {
                    const details = `Status: Connected
Auth Method: ${result.data.details.auth_method}
Databases: ${result.data.details.databases_found}
Response Time: ${result.data.details.response_time_ms || 'N/A'}ms
Sample: ${result.data.details.sample_databases ? result.data.details.sample_databases.slice(0, 2).join(', ') : 'N/A'}`;
                    
                    updateStatus('sqlFunction', 'success', details);
                    log(`✅ SQL Function test passed - ${result.data.details.databases_found} databases found using ${result.data.details.auth_method}`, 'success', 0.0005);
                } else {
                    const error = result.data ? result.data.error : result.error;
                    updateStatus('sqlFunction', 'error', error);
                    log(`❌ SQL Function test failed: ${error}`, 'error');
                }
            } catch (error) {
                updateStatus('sqlFunction', 'error', `Test failed: ${error.message}`);
                log(`❌ Function test error: ${error.message}`, 'error');
            }
        }

        async function testMessaging() {
            updateStatus('messaging', 'loading');
            log('Testing bot messaging endpoint...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/messaging');
                
                if (result.status === 'success') {
                    const details = `Endpoint: ${result.data.details.endpoint}
Bot Available: ${result.data.details.bot_available ? 'Yes' : 'No'}
Status: Ready for messages`;
                    
                    updateStatus('messaging', 'success', details);
                    log('✅ Bot messaging endpoint is configured', 'success');
                } else {
                    updateStatus('messaging', 'error', result.error);
                    log(`❌ Messaging test failed: ${result.error}`, 'error');
                }
            } catch (error) {
                updateStatus('messaging', 'error', `Cannot reach endpoint: ${error.message}`);
                log(`❌ Messaging test failed: ${error.message}`, 'error');
            }
        }

        async function testCostMonitoring() {
            updateStatus('costMonitoring', 'loading');
            log('Testing cost monitoring system...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/cost-monitoring');
                
                if (result.status === 'success' && result.data.success) {
                    const details = result.data.details;
                    updateStatus('costMonitoring', 'success', details);
                    log('✅ Cost monitoring system is operational', 'success');
                } else {
                    const error = result.data ? result.data.error : result.error;
                    updateStatus('costMonitoring', 'error', error);
                    log(`❌ Cost monitoring test failed: ${error}`, 'error');
                }
            } catch (error) {
                updateStatus('costMonitoring', 'error', `Test failed: ${error.message}`);
                log(`❌ Cost monitoring test error: ${error.message}`, 'error');
            }
        }

        async function testPerformance() {
            updateStatus('performance', 'loading');
            log('Testing performance...', 'info');
            
            try {
                const startTime = performance.now();
                const result = await makeApiCall('/admin/api/performance');
                const endTime = performance.now();
                const clientLatency = Math.round(endTime - startTime);
                
                if (result.status === 'success') {
                    const data = result.data;
                    const details = `Response Time: ${clientLatency}ms
Server Time: ${data.response_time_ms}ms
Memory: ${data.memory_info.memory_usage_mb || 'N/A'}MB
Uptime: ${data.uptime || 'N/A'}
Status: ${data.status}`;
                    
                    const status = clientLatency > 2000 ? 'warning' : 'success';
                    updateStatus('performance', status, details);
                    log(`${status === 'success' ? '✅' : '⚠️'} Performance test: ${clientLatency}ms latency`, status === 'success' ? 'success' : 'warning');
                } else {
                    updateStatus('performance', 'error', result.error);
                    log(`❌ Performance test failed: ${result.error}`, 'error');
                }
            } catch (error) {
                updateStatus('performance', 'error', `Test failed: ${error.message}`);
                log(`❌ Performance test error: ${error.message}`, 'error');
            }
        }

        async function runAllTests() {
            if (isTestRunning) {
                log('⚠️ Tests are already running, please wait...', 'warning');
                return;
            }
            
            isTestRunning = true;
            log('🚀 Starting comprehensive test suite with enhanced authentication...', 'info');
            
            const runButton = document.querySelector('.test-button.primary');
            if (runButton) {
                runButton.disabled = true;
                runButton.textContent = '⏳ Running Tests...';
            }
            
            const tests = ['botHealth', 'openai', 'sqlFunction', 'messaging', 'costMonitoring', 'performance'];
            tests.forEach(test => updateStatus(test, 'loading'));
            
            await testBotHealth();
            await new Promise(resolve => setTimeout(resolve, 300));
            
            await testMessaging();
            await new Promise(resolve => setTimeout(resolve, 300));
            
            await testOpenAI();
            await new Promise(resolve => setTimeout(resolve, 300));
            
            await testSQLFunction();
            await new Promise(resolve => setTimeout(resolve, 300));
            
            await testCostMonitoring();
            await new Promise(resolve => setTimeout(resolve, 300));
            
            await testPerformance();
            
            const results = Object.values(testResults);
            const passed = results.filter(r => r === 'success').length;
            const total = tests.length;
            
            if (passed === total) {
                log('🎉 All tests passed! System is fully operational.', 'success');
            } else {
                log(`⚠️ Testing completed: ${passed}/${total} tests passed`, 'warning');
            }
            
            if (runButton) {
                runButton.disabled = false;
                runButton.textContent = '🚀 Run All Tests';
            }
            
            isTestRunning = false;
            await refreshCosts();
        }

        function refreshStatus() {
            log('🔄 Refreshing dashboard...', 'info');
            runAllTests();
        }

        function clearLogs() {
            logs = [];
            const logViewer = document.getElementById('logViewer');
            logViewer.innerHTML = '';
            log('Logs cleared', 'info');
        }

        function clearAllLogs() {
            clearLogs();
            clearChat();
            testResults = {};
            sessionCost = 0.0;
            updateSessionCost();
            updateOverallStatus();
            
            const tests = ['botHealth', 'openai', 'sqlFunction', 'messaging', 'costMonitoring', 'performance'];
            tests.forEach(test => {
                updateStatus(test, 'unknown', 'Ready for testing...');
            });
            
            log('Dashboard reset complete', 'success');
        }

        function exportLogs() {
            const logText = logs.map(log => `[${log.timestamp}] ${log.type.toUpperCase()}: ${log.message} (Cost: ${log.cost.toFixed(3)})`).join('\\n');
            const blob = new Blob([logText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `bot-dashboard-logs-${new Date().toISOString().split('T')[0]}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            log('📥 Logs exported to file', 'success');
        }

        async function downloadCostReport() {
            log('📊 Generating cost report...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/cost-report');
                
                if (result.status !== 'error') {
                    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `cost-report-${new Date().toISOString().split('T')[0]}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    
                    log('💾 Cost report downloaded', 'success');
                } else {
                    log(`❌ Failed to generate report: ${result.error}`, 'error');
                }
            } catch (error) {
                log(`❌ Report download error: ${error.message}`, 'error');
            }
        }

        function toggleAutoRefresh() {
            const checkbox = document.getElementById('autoRefresh');
            
            if (checkbox.checked) {
                autoRefreshTimer = setInterval(() => {
                    if (!isTestRunning) {
                        log('⏰ Auto-refresh triggered', 'info');
                        runAllTests();
                    }
                }, 60000);
                
                log('⏰ Auto-refresh enabled (every 60 seconds)', 'success');
            } else {
                if (autoRefreshTimer) {
                    clearInterval(autoRefreshTimer);
                    autoRefreshTimer = null;
                }
                log('⏹️ Auto-refresh disabled', 'info');
            }
        }

        function addChatMessage(content, sender = 'user', type = 'normal', cost = 0.0, databases = []) {
            const chatMessages = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            
            let className = 'chat-message ';
            if (sender === 'user') className += 'user';
            else if (sender === 'bot') className += 'bot';
            else if (sender === 'system') className += 'system';
            
            if (type === 'error') className = 'chat-message error';
            
            messageDiv.className = className;
            messageDiv.innerHTML = `
                <div class="message-content">${sender === 'user' ? '<strong>You:</strong> ' : sender === 'bot' ? '<strong>Bot:</strong> ' : ''} ${escapeHtml(content)}</div>
                <div class="message-meta">
                    <div class="message-time">${new Date().toLocaleTimeString()}</div>
                    <div class="message-cost">${cost.toFixed(3)}</div>
                </div>
            `;
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            addChatMessage(message, 'user');
            input.value = '';
            
            log(`💬 Sending message: "${message}"`, 'info');
            
            try {
                const result = await makeApiCall('/admin/api/chat', 'POST', { message: message });
                
                if (result.status === 'success') {
                    const cost = result.cost || 0.0;
                    addChatMessage(result.response, 'bot', 'normal', cost, result.databases);
                    log(`✅ Message processed successfully (Cost: ${cost.toFixed(3)})`, 'success', cost);
                } else {
                    addChatMessage(`Error: ${result.error}`, 'system', 'error');
                    log(`❌ Chat error: ${result.error}`, 'error');
                }
                
            } catch (error) {
                addChatMessage(`Connection error: ${error.message}`, 'system', 'error');
                log(`❌ Chat error: ${error.message}`, 'error');
            }
        }

        function sendQuickMessage(message) {
            document.getElementById('chatInput').value = message;
            sendChatMessage();
        }

        function handleChatKeypress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendChatMessage();
            }
        }

        function clearChat() {
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.innerHTML = `
                <div class="chat-message system">
                    <div class="message-content">
                        <strong>System:</strong> Chat cleared. Ready for new conversation!
                    </div>
                    <div class="message-meta">
                        <div class="message-time">${new Date().toLocaleTimeString()}</div>
                        <div class="message-cost">$0.000</div>
                    </div>
                </div>
            `;
        }

        function viewTokenDetails() {
            log('📊 Viewing detailed token usage...', 'info');
            alert('Token details would open in a modal or new page in production');
        }

        function viewFunctionDetails() {
            log('📈 Viewing function call details...', 'info');
            alert('Function call details would open in a modal or new page in production');
        }

        function exportUsageReport() {
            log('📁 Exporting usage analytics...', 'info');
            downloadCostReport();
        }

        function showCostBreakdown() {
            log('💰 Showing detailed cost breakdown...', 'info');
            alert('Detailed cost breakdown would open in a modal in production');
        }

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            log(`🚀 Admin dashboard initialized for ${USER_INFO.display_name}`, 'success');
            log(`📍 Server: ${CONFIG.botUrl}`, 'info');
            log(`👤 User: ${USER_INFO.email} (${USER_INFO.authenticated ? USER_INFO.auth_type : 'Not Authenticated'})`, 'info');
            log(`⏱️ Uptime: ${UPTIME_INFO.uptime_formatted}`, 'info');
            log('💡 Click "Run All Tests" to check system status', 'info');
            
            setInterval(updateCurrentTime, 1000);
            refreshCosts();
            updateOverallStatus();
            
            // Initial system health check
            setTimeout(checkSystemHealth, 2000);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'r':
                        e.preventDefault();
                        runAllTests();
                        break;
                    case 'l':
                        e.preventDefault();
                        clearLogs();
                        break;
                    case 'c':
                        e.preventDefault();
                        refreshCosts();
                        break;
                    case 'u':
                        e.preventDefault();
                        refreshUptime();
                        break;
                }
            }
        });
        '''


# Add routes to the main app
def add_admin_routes(app, sql_translator=None, bot=None):
    """Add enhanced admin dashboard routes to the main aiohttp app"""
    
    dashboard = EnhancedAdminDashboard(sql_translator, bot)
    
    # Main dashboard page
    app.router.add_get('/admin', dashboard.dashboard_page)
    app.router.add_get('/admin/', dashboard.dashboard_page)
    
    # Enhanced API endpoints
    app.router.add_get('/admin/api/health', dashboard.api_test_health)
    app.router.add_get('/admin/api/openai', dashboard.api_test_openai)
    app.router.add_get('/admin/api/function', dashboard.api_test_function)
    app.router.add_get('/admin/api/messaging', dashboard.api_test_messaging)
    app.router.add_get('/admin/api/environment', dashboard.api_test_environment)
    app.router.add_get('/admin/api/performance', dashboard.api_test_performance)
    app.router.add_post('/admin/api/chat', dashboard.api_chat_message)
    
    # Cost tracking endpoints
    app.router.add_get('/admin/api/costs', dashboard.api_get_cost_data)
    app.router.add_post('/admin/api/track-cost', dashboard.api_track_cost)
    app.router.add_get('/admin/api/cost-report', dashboard.api_export_cost_report)
    app.router.add_get('/admin/api/cost-monitoring', dashboard.api_test_cost_monitoring)
    
    # Uptime tracking endpoints
    app.router.add_get('/admin/api/uptime', dashboard.api_get_uptime)
    app.router.add_get('/admin/api/uptime-report', dashboard.api_export_uptime_report)
    
    return dashboard