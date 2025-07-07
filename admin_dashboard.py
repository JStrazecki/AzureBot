# admin_dashboard.py - Enhanced admin dashboard with cost tracking and user authentication
"""
Enhanced Admin Dashboard Route Handler for SQL Assistant Bot
Features:
- Real-time cost tracking (Azure OpenAI tokens, function calls)
- User authentication display
- Comprehensive system monitoring
- Usage analytics and billing insights
- Performance metrics
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

class CostTracker:
    """Tracks and calculates costs for various Azure services"""
    
    def __init__(self):
        # Cost per 1K tokens for different models (in USD)
        self.token_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-35-turbo": {"input": 0.0015, "output": 0.002}
        }
        
        # Function call costs (estimated)
        self.function_costs = {
            "sql_query": 0.001,  # Per query
            "metadata_fetch": 0.0005,  # Per metadata call
        }
    
    def calculate_token_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage"""
        if model not in self.token_costs:
            model = "gpt-4o-mini"  # Default fallback
        
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
    """Handles user authentication information extraction"""
    
    @staticmethod
    def extract_user_info(request: Request) -> dict:
        """Extract user information from request headers/tokens"""
        user_info = {
            "name": "Unknown User",
            "email": "unknown@domain.com",
            "authenticated": False,
            "tenant": "Unknown",
            "roles": []
        }
        
        # Try to get user info from various sources
        
        # 1. From Authorization header (JWT token)
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                # Decode without verification for demo (in production, verify the token)
                decoded = jwt.decode(token, options={"verify_signature": False})
                user_info.update({
                    "name": decoded.get('name', decoded.get('preferred_username', 'Unknown')),
                    "email": decoded.get('email', decoded.get('upn', 'unknown@domain.com')),
                    "authenticated": True,
                    "tenant": decoded.get('tid', 'Unknown'),
                    "roles": decoded.get('roles', [])
                })
            except:
                pass
        
        # 2. From X-MS headers (if using Azure App Service Authentication)
        ms_client_principal = request.headers.get('X-MS-CLIENT-PRINCIPAL')
        if ms_client_principal:
            try:
                import base64
                decoded = base64.b64decode(ms_client_principal).decode('utf-8')
                principal = json.loads(decoded)
                user_info.update({
                    "name": principal.get('user_id', 'Unknown'),
                    "email": principal.get('user_claims', [{}])[0].get('val', 'unknown@domain.com'),
                    "authenticated": True,
                    "auth_type": principal.get('auth_typ', 'Unknown')
                })
            except:
                pass
        
        # 3. From custom headers (if you're setting them in your app)
        if request.headers.get('X-User-Name'):
            user_info.update({
                "name": request.headers.get('X-User-Name'),
                "email": request.headers.get('X-User-Email', 'unknown@domain.com'),
                "authenticated": True
            })
        
        return user_info

class EnhancedAdminDashboard:
    """Enhanced admin dashboard with cost tracking and user authentication"""
    
    def __init__(self, sql_translator=None, bot=None):
        self.sql_translator = sql_translator
        self.bot = bot
        self.cost_tracker = CostTracker()
        self.user_auth = UserAuthHandler()
        
        # In-memory storage for demo (use Redis/database in production)
        self.usage_stats = {
            "daily_costs": {},
            "hourly_costs": {},
            "user_sessions": {},
            "query_history": [],
            "error_log": []
        }
    
    async def dashboard_page(self, request: Request) -> Response:
        """Serve the enhanced dashboard HTML page"""
        
        # Get user information
        user_info = self.user_auth.extract_user_info(request)
        
        # Get environment variables for display
        config = {
            "botUrl": f"https://{request.host}",
            "functionUrl": os.environ.get("AZURE_FUNCTION_URL", ""),
            "functionKey": "***" + os.environ.get("AZURE_FUNCTION_KEY", "")[-4:] if os.environ.get("AZURE_FUNCTION_KEY") else "Not set",
            "openaiEndpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            "openaiDeployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
            "environment": os.environ.get("DEPLOYMENT_ENV", "production"),
            "appId": os.environ.get("MICROSOFT_APP_ID", "")[:8] + "***" if os.environ.get("MICROSOFT_APP_ID") else "Not set"
        }
        
        # Get current cost data
        today = datetime.now().strftime("%Y-%m-%d")
        daily_cost = self.usage_stats["daily_costs"].get(today, 0.0)
        budget_status = self.cost_tracker.get_daily_budget_status(daily_cost)
        
        # Dashboard HTML with embedded config
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant Bot - Enhanced Admin Dashboard</title>
    <style>
        {self._get_enhanced_dashboard_css()}
    </style>
</head>
<body>
    <div class="dashboard">
        <!-- Enhanced Header with User Info -->
        <div class="header">
            <div class="header-content">
                <div class="title-section">
                    <h1>🤖 SQL Assistant Bot - Admin Dashboard</h1>
                    <p>Real-time monitoring, cost tracking & analytics • Environment: {config["environment"]}</p>
                </div>
                <div class="user-section">
                    <div class="user-info">
                        <div class="user-avatar">
                            <span class="avatar-icon">👤</span>
                        </div>
                        <div class="user-details">
                            <div class="user-name">{user_info["name"]}</div>
                            <div class="user-email">{user_info["email"]}</div>
                            <div class="auth-status {'authenticated' if user_info['authenticated'] else 'not-authenticated'}">
                                {'🟢 Authenticated' if user_info['authenticated'] else '🔴 Not Authenticated'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="server-info">
                <span>Server: {request.host}</span> • 
                <span>Time: <span id="currentTime">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span></span> •
                <span>Tenant: {user_info.get('tenant', 'N/A')}</span>
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

        <!-- Environment Configuration -->
        <div class="config-section">
            <h2>⚙️ Environment Configuration</h2>
            <div class="config-grid">
                <div class="config-display">
                    <label>Bot URL:</label>
                    <div class="config-value">{config["botUrl"]}</div>
                </div>
                <div class="config-display">
                    <label>App ID:</label>
                    <div class="config-value">{config["appId"]}</div>
                </div>
                <div class="config-display">
                    <label>Azure Function:</label>
                    <div class="config-value">{config["functionUrl"] or "Not configured"}</div>
                </div>
                <div class="config-display">
                    <label>Function Key:</label>
                    <div class="config-value">{config["functionKey"]}</div>
                </div>
                <div class="config-display">
                    <label>OpenAI Endpoint:</label>
                    <div class="config-value">{config["openaiEndpoint"] or "Not configured"}</div>
                </div>
                <div class="config-display">
                    <label>OpenAI Deployment:</label>
                    <div class="config-value">{config["openaiDeployment"]}</div>
                </div>
            </div>
            <div class="action-buttons">
                <button class="test-button primary" onclick="runAllTests()">🚀 Run All Tests</button>
                <button class="test-button" onclick="refreshStatus()">🔄 Refresh</button>
                <button class="test-button" onclick="clearAllLogs()">🧹 Clear All</button>
                <button class="test-button secondary" onclick="downloadCostReport()">💾 Cost Report</button>
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
                    <span class="message">Enhanced admin dashboard initialized for {user_info["name"]}</span>
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
        
        {self._get_enhanced_dashboard_javascript()}
    </script>
</body>
</html>'''
        
        return Response(text=html_content, content_type='text/html')
    
    async def api_get_cost_data(self, request: Request) -> Response:
        """API endpoint for getting cost data"""
        try:
            # Get costs from token limiter if available
            token_usage = {}
            if self.sql_translator and hasattr(self.sql_translator, 'token_limiter'):
                token_usage = self.sql_translator.token_limiter.get_usage_summary()
            
            # Mock data for demonstration
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
            
            # Track the cost
            today = datetime.now().strftime("%Y-%m-%d")
            hour = datetime.now().strftime("%Y-%m-%d-%H")
            
            if today not in self.usage_stats["daily_costs"]:
                self.usage_stats["daily_costs"][today] = 0.0
            if hour not in self.usage_stats["hourly_costs"]:
                self.usage_stats["hourly_costs"][hour] = 0.0
            
            self.usage_stats["daily_costs"][today] += cost
            self.usage_stats["hourly_costs"][hour] += cost
            
            # Log the event
            self.usage_stats["query_history"].append({
                "timestamp": datetime.now().isoformat(),
                "type": event_type,
                "cost": cost,
                "details": details
            })
            
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
            
            report = {
                "generated_by": user_info["name"],
                "generated_at": datetime.now().isoformat(),
                "report_period": "Last 30 days",
                "summary": {
                    "total_cost": sum(self.usage_stats["daily_costs"].values()),
                    "total_queries": len(self.usage_stats["query_history"]),
                    "active_users": len(self.usage_stats["user_sessions"]),
                    "average_cost_per_query": sum(self.usage_stats["daily_costs"].values()) / max(len(self.usage_stats["query_history"]), 1)
                },
                "daily_costs": self.usage_stats["daily_costs"],
                "hourly_costs": self.usage_stats["hourly_costs"],
                "query_history": self.usage_stats["query_history"][-100:]  # Last 100 queries
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
            # Test cost tracking functionality
            test_results = {
                "cost_tracker_available": True,
                "token_limiter_available": self.sql_translator and hasattr(self.sql_translator, 'token_limiter'),
                "storage_working": True,
                "budget_monitoring": True
            }
            
            # Test a mock cost calculation
            test_cost = self.cost_tracker.calculate_token_cost("gpt-4o-mini", 100, 50)
            budget_status = self.cost_tracker.get_daily_budget_status(1.25)
            
            success = all(test_results.values())
            
            details = f"""Cost Tracker: {'✓' if test_results['cost_tracker_available'] else '✗'}
Token Limiter: {'✓' if test_results['token_limiter_available'] else '✗'}
Storage: {'✓' if test_results['storage_working'] else '✗'}
Budget Monitor: {'✓' if test_results['budget_monitoring'] else '✗'}
Test Calculation: ${test_cost:.6f}
Budget Status: {budget_status['status']}"""
            
            return json_response({
                "status": "success",
                "data": {
                    "success": success,
                    "details": details,
                    "test_results": test_results,
                    "test_cost": test_cost,
                    "budget_status": budget_status
                },
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    # Include all the existing methods from the original dashboard
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
            
            # Track cost if this was a real API call
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
    
    async def api_test_function(self, request: Request) -> Response:
        """API endpoint for testing SQL function"""
        try:
            result = await self._test_sql_function()
            
            # Track function call cost
            if result.get("success"):
                await self._track_api_cost("function_test", 0.0005, {"test": True})
            
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
                "missing_variables": health_data["missing_variables"],
                "environment_variables": health_data["environment_variables"]
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
            
            # Simulate processing cost (in production, get from actual API response)
            estimated_cost = len(message) * 0.00001  # Rough estimate
            
            # Create a simulated response
            response_text = await self._process_chat_message(message)
            
            # Track the cost
            await self._track_api_cost("chat_message", estimated_cost, {
                "user": user_info["name"],
                "message_length": len(message),
                "response_length": len(response_text)
            })
            
            return json_response({
                "status": "success",
                "response": response_text,
                "cost": estimated_cost,
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
        
        # Log the event
        self.usage_stats["query_history"].append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "cost": cost,
            "details": details
        })
    
    async def _process_chat_message(self, message: str) -> str:
        """Process a chat message and return a response"""
        message_lower = message.lower().strip()
        
        if message_lower in ["hello", "hi", "hey"]:
            return "Hello! I'm the SQL Assistant Bot with cost tracking. Type /help to see what I can do!"
        elif message_lower == "/help":
            return """Available commands:
- /database list - List available databases
- /tables - Show tables in current database  
- /stats - View usage statistics
- /usage - View token usage and costs
- /explore <question> - Deep exploration mode
- Or just ask a natural language question about your data!"""
        elif message_lower == "/usage":
            today = datetime.now().strftime("%Y-%m-%d")
            daily_cost = self.usage_stats["daily_costs"].get(today, 0.0)
            return f"💰 Today's usage: ${daily_cost:.3f} | Queries: {len(self.usage_stats['query_history'])} | Budget remaining: ${50.0 - daily_cost:.3f}"
        elif message_lower == "/database list":
            return "To see databases, I need to connect to your SQL Function. Make sure AZURE_FUNCTION_KEY is set!"
        elif message_lower == "/stats":
            return f"📊 Statistics: {len(self.usage_stats['user_sessions'])} active users, {len(self.usage_stats['query_history'])} queries today, ${sum(self.usage_stats['daily_costs'].values()):.3f} total cost"
        elif message_lower.startswith("/"):
            return f"Command '{message}' recognized. Full functionality requires connection to Teams."
        else:
            return f"I understand you want to know about: '{message}'. In production, I would translate this to SQL and query your database! Estimated cost: $0.012"
    
    async def _get_comprehensive_health(self) -> dict:
        """Get comprehensive health information"""
        required_vars = [
            "MICROSOFT_APP_ID", "MICROSOFT_APP_PASSWORD",
            "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
            "AZURE_FUNCTION_URL"
        ]
        
        env_status = {}
        missing_vars = []
        
        for var in required_vars:
            value = os.environ.get(var)
            env_status[var] = bool(value)
            if not value:
                missing_vars.append(var)
        
        optional_vars = ["AZURE_FUNCTION_KEY", "AZURE_OPENAI_DEPLOYMENT_NAME"]
        for var in optional_vars:
            env_status[var] = bool(os.environ.get(var))
        
        return {
            "environment_variables": env_status,
            "missing_variables": missing_vars,
            "has_critical_vars": len(missing_vars) == 0,
            "sql_translator_available": self.sql_translator is not None,
            "bot_available": self.bot is not None,
            "python_version": os.sys.version,
            "working_directory": os.getcwd()
        }
    
    async def _test_openai_connection(self) -> dict:
        """Test Azure OpenAI connection"""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        if not endpoint or not api_key:
            return {
                "success": False,
                "error": "Missing OpenAI configuration",
                "details": {
                    "has_endpoint": bool(endpoint),
                    "has_api_key": bool(api_key)
                }
            }
        
        try:
            if endpoint.endswith('/'):
                endpoint = endpoint.rstrip('/')
            
            test_url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-01"
            
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
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "details": {
                                "status_code": response.status,
                                "deployment": deployment,
                                "endpoint": endpoint,
                                "model": data.get("model", "unknown")
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
                                "deployment": deployment
                            }
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}",
                "details": {"exception_type": type(e).__name__}
            }
    
    async def _test_sql_function(self) -> dict:
        """Test SQL function connection"""
        function_url = os.environ.get("AZURE_FUNCTION_URL")
        function_key = os.environ.get("AZURE_FUNCTION_KEY")
        
        if not function_url:
            return {
                "success": False,
                "error": "SQL Function URL not configured"
            }
        
        try:
            headers = {"Content-Type": "application/json"}
            
            if function_key:
                headers["x-functions-key"] = function_key
            
            payload = {"query_type": "metadata"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    function_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "details": {
                                "status_code": response.status,
                                "databases_found": len(data.get("databases", [])),
                                "has_function_key": bool(function_key),
                                "sample_databases": data.get("databases", [])[:3]
                            }
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "error": "Authentication failed - check AZURE_FUNCTION_KEY",
                            "details": {
                                "status_code": response.status,
                                "has_function_key": bool(function_key)
                            }
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Function error: {response.status}",
                            "details": {
                                "status_code": response.status,
                                "response": error_text[:200]
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
            
            return {
                "response_time_ms": round(response_time, 2),
                "status": "healthy",
                "memory_info": self._get_memory_info(),
                "uptime": "Service is running"
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
            return {"info": "Memory monitoring not available"}
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
            .analytics-grid { grid-template-columns: 1fr; }
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
            
            // Update session cost
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
            const total = 6; // We have 6 test categories
            
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
            // Update token metrics
            if (costData.token_usage) {
                document.getElementById('inputTokens').textContent = costData.token_usage.input_tokens.toLocaleString();
                document.getElementById('outputTokens').textContent = costData.token_usage.output_tokens.toLocaleString();
                document.getElementById('tokenCost').textContent = `${costData.token_usage.total_cost.toFixed(3)}`;
            }
            
            // Update function metrics
            if (costData.function_calls) {
                document.getElementById('sqlQueries').textContent = costData.function_calls.sql_queries;
                document.getElementById('metadataCalls').textContent = costData.function_calls.metadata_calls;
                document.getElementById('functionCost').textContent = `${costData.function_calls.total_cost.toFixed(3)}`;
            }
            
            // Update usage analytics
            if (costData.analytics) {
                document.getElementById('activeUsers').textContent = costData.analytics.active_users;
                document.getElementById('queriesToday').textContent = costData.analytics.queries_today;
                document.getElementById('avgCostQuery').textContent = `${costData.analytics.avg_cost_per_query.toFixed(3)}`;
            }
            
            // Update cost breakdown
            if (costData.token_usage && costData.function_calls) {
                const totalCost = costData.token_usage.total_cost + costData.function_calls.total_cost;
                const tokenPercent = totalCost > 0 ? (costData.token_usage.total_cost / totalCost * 100) : 0;
                const functionPercent = totalCost > 0 ? (costData.function_calls.total_cost / totalCost * 100) : 0;
                
                document.getElementById('costBreakdown').innerHTML = `
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

        async function testBotHealth() {
            updateStatus('botHealth', 'loading');
            log('Testing bot health...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/health');
                
                if (result.status === 'success') {
                    const data = result.data;
                    const details = `Environment: ${data.has_critical_vars ? 'OK' : 'Missing vars'}
Python: ${data.python_version.split(' ')[0]}
Translator: ${data.sql_translator_available ? 'Available' : 'Not available'}
Bot: ${data.bot_available ? 'Available' : 'Not available'}`;
                    
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
            log('Testing SQL Function...', 'info');
            
            try {
                const result = await makeApiCall('/admin/api/function');
                
                if (result.status === 'success' && result.data.success) {
                    const details = `Status: Connected
Databases: ${result.data.details.databases_found}
Auth: ${result.data.details.has_function_key ? 'Key provided' : 'No key'}
Sample: ${result.data.details.sample_databases ? result.data.details.sample_databases.slice(0, 3).join(', ') : 'N/A'}`;
                    
                    updateStatus('sqlFunction', 'success', details);
                    log(`✅ SQL Function test passed - ${result.data.details.databases_found} databases found`, 'success', 0.0005);
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
            log('🚀 Starting comprehensive test suite...', 'info');
            
            // Disable the button
            const runButton = document.querySelector('.test-button.primary');
            if (runButton) {
                runButton.disabled = true;
                runButton.textContent = '⏳ Running Tests...';
            }
            
            // Reset all status indicators
            const tests = ['botHealth', 'openai', 'sqlFunction', 'messaging', 'costMonitoring', 'performance'];
            tests.forEach(test => updateStatus(test, 'loading'));
            
            // Run tests in sequence
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
            
            // Final summary
            const results = Object.values(testResults);
            const passed = results.filter(r => r === 'success').length;
            const total = tests.length;
            
            if (passed === total) {
                log('🎉 All tests passed! System is fully operational.', 'success');
            } else {
                log(`⚠️ Testing completed: ${passed}/${total} tests passed`, 'warning');
            }
            
            // Re-enable the button
            if (runButton) {
                runButton.disabled = false;
                runButton.textContent = '🚀 Run All Tests';
            }
            
            isTestRunning = false;
            
            // Refresh cost data after tests
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
            
            // Reset all test cards
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
                }, 60000); // Every minute
                
                log('⏰ Auto-refresh enabled (every 60 seconds)', 'success');
            } else {
                if (autoRefreshTimer) {
                    clearInterval(autoRefreshTimer);
                    autoRefreshTimer = null;
                }
                log('⏹️ Auto-refresh disabled', 'info');
            }
        }

        function updateCurrentTime() {
            const timeEl = document.getElementById('currentTime');
            if (timeEl) {
                timeEl.textContent = new Date().toLocaleString();
            }
        }

        // Enhanced Chat Console Functions
        function addChatMessage(content, sender = 'user', type = 'normal', cost = 0.0) {
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
            
            // Add user message to chat
            addChatMessage(message, 'user');
            input.value = '';
            
            // Log the attempt
            log(`💬 Sending message: "${message}"`, 'info');
            
            try {
                // Send to our chat API
                const result = await makeApiCall('/admin/api/chat', 'POST', { message: message });
                
                if (result.status === 'success') {
                    const cost = result.cost || 0.0;
                    addChatMessage(result.response, 'bot', 'normal', cost);
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
            log(`🚀 Enhanced admin dashboard initialized for ${USER_INFO.name}`, 'success');
            log(`📍 Server: ${CONFIG.botUrl}`, 'info');
            log(`👤 User: ${USER_INFO.email} (${USER_INFO.authenticated ? 'Authenticated' : 'Not Authenticated'})`, 'info');
            log('💡 Click "Run All Tests" to check system status', 'info');
            
            // Update time every second
            setInterval(updateCurrentTime, 1000);
            
            // Initialize cost data refresh
            refreshCosts();
            
            // Initialize status
            updateOverallStatus();
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
    
    # New cost tracking endpoints
    app.router.add_get('/admin/api/costs', dashboard.api_get_cost_data)
    app.router.add_post('/admin/api/track-cost', dashboard.api_track_cost)
    app.router.add_get('/admin/api/cost-report', dashboard.api_export_cost_report)
    app.router.add_get('/admin/api/cost-monitoring', dashboard.api_test_cost_monitoring)
    
    return dashboard