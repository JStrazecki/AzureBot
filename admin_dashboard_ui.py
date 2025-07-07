# admin_dashboard_ui.py - Admin Dashboard UI Components
"""
Admin Dashboard UI - Separated HTML, CSS, and JavaScript
"""

def get_admin_dashboard_css():
    """Return the CSS styles for the admin dashboard"""
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
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
    }

    /* Header */
    .header {
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 30px;
        margin-bottom: 30px;
        color: white;
        text-align: center;
    }

    .header h1 {
        font-size: 2.5rem;
        margin-bottom: 10px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }

    .header p {
        font-size: 1.1rem;
        opacity: 0.9;
    }

    /* Quick Status */
    .quick-status {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }

    .status-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        transition: transform 0.3s;
    }

    .status-card:hover {
        transform: translateY(-3px);
    }

    .status-icon {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        margin-right: 15px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        color: white;
    }

    .status-unknown { background: #6c757d; }
    .status-success { background: #28a745; }
    .status-error { background: #dc3545; }
    .status-warning { background: #ffc107; color: #333; }
    .status-loading { 
        background: #17a2b8; 
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }

    .status-info h3 {
        font-size: 1.2rem;
        margin-bottom: 5px;
    }

    .status-info p {
        color: #666;
        font-size: 0.9rem;
    }

    /* Test Section */
    .test-section {
        background: white;
        border-radius: 12px;
        padding: 30px;
        margin-bottom: 30px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }

    .test-section h2 {
        color: #333;
        margin-bottom: 20px;
        font-size: 1.6rem;
    }

    .test-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
        gap: 20px;
        margin-bottom: 20px;
    }

    .test-item {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 20px;
        border-left: 4px solid #667eea;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .test-info h4 {
        font-size: 1.1rem;
        margin-bottom: 5px;
    }

    .test-status {
        font-size: 0.9rem;
        color: #666;
    }

    .test-result {
        background: #e9ecef;
        border-radius: 6px;
        padding: 10px;
        margin-top: 10px;
        font-family: monospace;
        font-size: 0.85rem;
        white-space: pre-wrap;
        max-height: 200px;
        overflow-y: auto;
    }

    .test-result.success {
        border-left: 4px solid #28a745;
    }

    .test-result.error {
        border-left: 4px solid #dc3545;
    }

    /* Buttons */
    .button {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 600;
        transition: all 0.2s;
        font-size: 14px;
    }

    .button.primary {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
    }

    .button.secondary {
        background: #6c757d;
        color: white;
    }

    .button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    .button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none;
    }

    .button-group {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 20px;
    }

    /* Activity Log */
    .log-section {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
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

    .log-viewer {
        background: #2d3748;
        color: #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        max-height: 400px;
        overflow-y: auto;
    }

    .log-entry {
        margin-bottom: 5px;
        display: flex;
        align-items: flex-start;
    }

    .timestamp {
        color: #a0aec0;
        margin-right: 10px;
        flex-shrink: 0;
    }

    .log-entry.info { color: #63b3ed; }
    .log-entry.success { color: #68d391; }
    .log-entry.warning { color: #fbb041; }
    .log-entry.error { color: #fc8181; }

    /* Responsive */
    @media (max-width: 768px) {
        .dashboard { padding: 10px; }
        .header h1 { font-size: 2rem; }
        .test-grid { grid-template-columns: 1fr; }
        .quick-status { grid-template-columns: 1fr; }
    }

    /* Loading spinner */
    .spinner {
        border: 3px solid rgba(0, 0, 0, 0.1);
        border-left-color: #667eea;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        animation: spin 1s linear infinite;
        display: inline-block;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    '''

def get_admin_dashboard_javascript():
    """Return the JavaScript code for the admin dashboard"""
    return '''
    let testResults = {};
    let logs = [];
    let isTestRunning = false;

    function log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        logs.push({ timestamp, message, type });
        
        const logViewer = document.getElementById('logViewer');
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.innerHTML = `
            <span class="timestamp">[${timestamp}]</span>
            <span class="message">${escapeHtml(message)}</span>
        `;
        logViewer.appendChild(logEntry);
        logViewer.scrollTop = logViewer.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
            detailsEl.className = `test-result ${status}`;
        }
        
        updateOverallStatus();
    }

    function updateOverallStatus() {
        const results = Object.values(testResults);
        const passed = results.filter(r => r === 'success').length;
        const failed = results.filter(r => r === 'error').length;
        
        const statusEl = document.getElementById('overallStatus');
        const statusText = document.getElementById('overallStatusText');
        
        if (results.length === 0) {
            statusEl.className = 'status-icon status-unknown';
            statusEl.textContent = '?';
            statusText.textContent = 'No tests run';
        } else if (failed > 0) {
            statusEl.className = 'status-icon status-error';
            statusEl.textContent = '✗';
            statusText.textContent = `${failed} test(s) failed`;
        } else if (passed === results.length) {
            statusEl.className = 'status-icon status-success';
            statusEl.textContent = '✓';
            statusText.textContent = 'All tests passed';
        } else {
            statusEl.className = 'status-icon status-warning';
            statusEl.textContent = '⚠';
            statusText.textContent = `${passed}/${results.length} tests passed`;
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

    async function testHealth() {
        updateStatus('health', 'loading');
        log('Testing system health...');
        
        try {
            const result = await makeApiCall('/health');
            
            if (result.status === 'healthy') {
                const details = `Version: ${result.version}\\nServices: ${JSON.stringify(result.services, null, 2)}`;
                updateStatus('health', 'success', details);
                log('✅ Health check passed', 'success');
            } else {
                updateStatus('health', 'error', result.error || 'Unknown error');
                log(`❌ Health check failed: ${result.error}`, 'error');
            }
        } catch (error) {
            updateStatus('health', 'error', error.message);
            log(`❌ Health check error: ${error.message}`, 'error');
        }
    }

    async function testOpenAI() {
        updateStatus('openai', 'loading');
        log('Testing Azure OpenAI connection...');
        
        try {
            const result = await makeApiCall('/admin/api/openai');
            
            if (result.status === 'success' && result.data.success) {
                const details = `Deployment: ${result.data.details.deployment}\\nModel: ${result.data.details.model}\\nResponse Time: ${result.data.details.response_time_ms}ms`;
                updateStatus('openai', 'success', details);
                log('✅ Azure OpenAI connection successful', 'success');
            } else {
                const error = result.data ? result.data.error : result.error;
                updateStatus('openai', 'error', error);
                log(`❌ Azure OpenAI test failed: ${error}`, 'error');
            }
        } catch (error) {
            updateStatus('openai', 'error', error.message);
            log(`❌ OpenAI test error: ${error.message}`, 'error');
        }
    }

    async function testSQLFunction() {
        updateStatus('sqlFunction', 'loading');
        log('Testing SQL Function...');
        
        try {
            const result = await makeApiCall('/admin/api/function');
            
            if (result.status === 'success' && result.data.success) {
                const details = `Auth Method: ${result.data.details.auth_method}\\nDatabases: ${result.data.details.databases_found}\\nResponse Time: ${result.data.details.response_time_ms}ms`;
                updateStatus('sqlFunction', 'success', details);
                log(`✅ SQL Function connected - ${result.data.details.databases_found} databases found`, 'success');
            } else {
                const error = result.data ? result.data.error : result.error;
                updateStatus('sqlFunction', 'error', error);
                log(`❌ SQL Function test failed: ${error}`, 'error');
            }
        } catch (error) {
            updateStatus('sqlFunction', 'error', error.message);
            log(`❌ Function test error: ${error.message}`, 'error');
        }
    }

    async function testTranslator() {
        updateStatus('translator', 'loading');
        log('Testing SQL Translator...');
        
        try {
            const result = await makeApiCall('/admin/api/translator', 'POST', {
                query: 'show me all tables'
            });
            
            if (result.status === 'success') {
                const details = `Query: ${result.query}\\nDatabase: ${result.database}\\nConfidence: ${result.confidence}`;
                updateStatus('translator', 'success', details);
                log('✅ SQL Translator working correctly', 'success');
            } else {
                updateStatus('translator', 'error', result.error || 'Translation failed');
                log(`❌ SQL Translator test failed: ${result.error}`, 'error');
            }
        } catch (error) {
            updateStatus('translator', 'error', error.message);
            log(`❌ Translator test error: ${error.message}`, 'error');
        }
    }

    async function testPerformance() {
        updateStatus('performance', 'loading');
        log('Testing performance...');
        
        try {
            const start = performance.now();
            const result = await makeApiCall('/admin/api/performance');
            const end = performance.now();
            const clientLatency = Math.round(end - start);
            
            if (result.status === 'success') {
                const details = `Client Latency: ${clientLatency}ms\\nServer Time: ${result.response_time_ms}ms\\nMemory: ${result.memory_usage_mb}MB`;
                updateStatus('performance', 'success', details);
                log(`✅ Performance test: ${clientLatency}ms latency`, 'success');
            } else {
                updateStatus('performance', 'error', result.error);
                log(`❌ Performance test failed: ${result.error}`, 'error');
            }
        } catch (error) {
            updateStatus('performance', 'error', error.message);
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
        
        const runButton = document.getElementById('runAllTestsBtn');
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner"></span> Running Tests...';
        }
        
        // Reset all test statuses
        ['health', 'openai', 'sqlFunction', 'translator', 'performance'].forEach(test => {
            updateStatus(test, 'loading');
        });
        
        // Run tests sequentially
        await testHealth();
        await new Promise(resolve => setTimeout(resolve, 300));
        
        await testOpenAI();
        await new Promise(resolve => setTimeout(resolve, 300));
        
        await testSQLFunction();
        await new Promise(resolve => setTimeout(resolve, 300));
        
        await testTranslator();
        await new Promise(resolve => setTimeout(resolve, 300));
        
        await testPerformance();
        
        const results = Object.values(testResults);
        const passed = results.filter(r => r === 'success').length;
        const total = results.length;
        
        if (passed === total) {
            log('🎉 All tests passed! System is fully operational.', 'success');
        } else {
            log(`⚠️ Testing completed: ${passed}/${total} tests passed`, 'warning');
        }
        
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = '🚀 Run All Tests';
        }
        
        isTestRunning = false;
    }

    function clearLogs() {
        logs = [];
        document.getElementById('logViewer').innerHTML = '';
        log('Logs cleared', 'info');
    }

    function exportLogs() {
        const logText = logs.map(log => `[${log.timestamp}] ${log.type.toUpperCase()}: ${log.message}`).join('\\n');
        const blob = new Blob([logText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `admin-logs-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        log('📥 Logs exported to file', 'success');
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        log('🚀 Admin dashboard initialized', 'success');
        log('💡 Click "Run All Tests" to check system status', 'info');
        updateOverallStatus();
    });
    '''

def get_admin_dashboard_html(user_name="Admin"):
    """Generate the admin dashboard HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant - Admin Dashboard</title>
    <style>
        {get_admin_dashboard_css()}
    </style>
</head>
<body>
    <div class="dashboard">
        <!-- Header -->
        <div class="header">
            <h1>🤖 SQL Assistant Admin Dashboard</h1>
            <p>System Monitoring & Testing • Welcome, {user_name}</p>
        </div>

        <!-- Quick Status Overview -->
        <div class="quick-status">
            <div class="status-card">
                <div class="status-icon status-unknown" id="overallStatus">?</div>
                <div class="status-info">
                    <h3>System Status</h3>
                    <p id="overallStatusText">Ready for testing</p>
                </div>
            </div>
            
            <div class="status-card">
                <div class="status-icon status-unknown" id="healthIcon">?</div>
                <div class="status-info">
                    <h3>Health Check</h3>
                    <p>Application health status</p>
                </div>
            </div>
            
            <div class="status-card">
                <div class="status-icon status-unknown" id="openaiIcon">?</div>
                <div class="status-info">
                    <h3>Azure OpenAI</h3>
                    <p>Translation service</p>
                </div>
            </div>
        </div>

        <!-- Test Section -->
        <div class="test-section">
            <h2>⚡ Service Tests</h2>
            
            <div class="test-grid">
                <!-- Health Test -->
                <div class="test-item">
                    <div class="test-info">
                        <h4>System Health</h4>
                        <p class="test-status">Check overall system status</p>
                    </div>
                    <button class="button secondary" onclick="testHealth()">Test</button>
                </div>
                <div id="healthDetails" class="test-result" style="display: none;"></div>

                <!-- OpenAI Test -->
                <div class="test-item">
                    <div class="test-info">
                        <h4>Azure OpenAI</h4>
                        <p class="test-status">Test AI translation service</p>
                    </div>
                    <button class="button secondary" onclick="testOpenAI()">Test</button>
                </div>
                <div id="openaiDetails" class="test-result" style="display: none;"></div>

                <!-- SQL Function Test -->
                <div class="test-item">
                    <div class="test-info">
                        <h4>SQL Function</h4>
                        <p class="test-status">Test database connection</p>
                    </div>
                    <button class="button secondary" onclick="testSQLFunction()">Test</button>
                </div>
                <div id="sqlFunctionDetails" class="test-result" style="display: none;"></div>

                <!-- Translator Test -->
                <div class="test-item">
                    <div class="test-info">
                        <h4>SQL Translator</h4>
                        <p class="test-status">Test query translation</p>
                    </div>
                    <button class="button secondary" onclick="testTranslator()">Test</button>
                </div>
                <div id="translatorDetails" class="test-result" style="display: none;"></div>

                <!-- Performance Test -->
                <div class="test-item">
                    <div class="test-info">
                        <h4>Performance</h4>
                        <p class="test-status">Test response times</p>
                    </div>
                    <button class="button secondary" onclick="testPerformance()">Test</button>
                </div>
                <div id="performanceDetails" class="test-result" style="display: none;"></div>
            </div>

            <div class="button-group">
                <button id="runAllTestsBtn" class="button primary" onclick="runAllTests()">🚀 Run All Tests</button>
                <button class="button secondary" onclick="window.location.reload()">🔄 Refresh Page</button>
                <a href="/console" class="button secondary" style="text-decoration: none; display: inline-block;">💻 Open Console</a>
            </div>
        </div>

        <!-- Activity Log -->
        <div class="log-section">
            <div class="log-header">
                <h2>📋 Activity Log</h2>
                <div>
                    <button class="button secondary" onclick="clearLogs()">Clear</button>
                    <button class="button secondary" onclick="exportLogs()">Export</button>
                </div>
            </div>
            <div class="log-viewer" id="logViewer"></div>
        </div>
    </div>

    <script>
        {get_admin_dashboard_javascript()}
    </script>
</body>
</html>'''