# analyst_ui.py - Power BI Analyst User Interface
"""
Power BI Analyst UI - Clean business intelligence interface for natural language queries
"""

def get_analyst_html():
    """Generate the Power BI Analyst HTML interface"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Power BI Analyst - Business Intelligence Assistant</title>
    <style>
        {get_analyst_css()}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-content">
                <div class="logo-section">
                    <div class="logo">📊</div>
                    <div>
                        <h1>Power BI Analyst</h1>
                        <p class="tagline">Your AI-powered business intelligence assistant</p>
                    </div>
                </div>
                <div class="header-actions">
                    <button class="header-button" onclick="testConnection()">
                        <span class="icon">🔌</span> Test Connection
                    </button>
                    <a href="/" class="header-button">
                        <span class="icon">🏠</span> Home
                    </a>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-container">
            <!-- Workspace Selector -->
            <div class="workspace-section">
                <div class="section-header">
                    <h2>Select Workspace & Dataset</h2>
                    <button class="refresh-button" onclick="loadWorkspaces()">
                        <span class="icon">🔄</span> Refresh
                    </button>
                </div>
                
                <div class="selector-container">
                    <div class="selector-group">
                        <label for="workspaceSelect">Workspace:</label>
                        <select id="workspaceSelect" onchange="onWorkspaceChange()">
                            <option value="">Loading workspaces...</option>
                        </select>
                    </div>
                    
                    <div class="selector-group">
                        <label for="datasetSelect">Dataset:</label>
                        <select id="datasetSelect" onchange="onDatasetChange()">
                            <option value="">Select a workspace first</option>
                        </select>
                    </div>
                </div>
                
                <div id="selectionInfo" class="selection-info" style="display: none;">
                    <div class="info-badge">
                        <span class="icon">📊</span>
                        <span id="selectedDatasetName">No dataset selected</span>
                    </div>
                </div>
            </div>

            <!-- Chat Interface -->
            <div class="chat-section">
                <div class="messages-container" id="messagesContainer">
                    <!-- Welcome Message -->
                    <div class="message assistant">
                        <div class="message-header">
                            <span class="icon">🤖</span>
                            <span class="name">Power BI Analyst</span>
                            <span class="time">${{new Date().toLocaleTimeString()}}</span>
                        </div>
                        <div class="message-content">
                            <p>Welcome! I'm your AI-powered business analyst for Power BI.</p>
                            
                            <p><strong>How I can help you:</strong></p>
                            <ul>
                                <li>📈 Analyze business performance and trends</li>
                                <li>🔍 Investigate data patterns and anomalies</li>
                                <li>💡 Provide actionable insights and recommendations</li>
                                <li>📊 Answer complex business questions in natural language</li>
                            </ul>
                            
                            <p><strong>Example questions you can ask:</strong></p>
                            <ul class="example-questions">
                                <li>"How did we perform last quarter?"</li>
                                <li>"What are our top revenue drivers?"</li>
                                <li>"Show me customer satisfaction trends"</li>
                                <li>"Which regions are underperforming?"</li>
                                <li>"Compare this year's sales to last year"</li>
                            </ul>
                            
                            <p class="hint">💡 Select a workspace and dataset above, then ask me anything about your data!</p>
                        </div>
                    </div>
                </div>

                <!-- Input Area -->
                <div class="input-section">
                    <div class="input-container">
                        <textarea 
                            id="queryInput" 
                            placeholder="Ask a business question... (e.g., 'How is revenue trending this quarter?')"
                            rows="2"
                            onkeydown="handleKeyPress(event)"
                        ></textarea>
                        <button id="sendButton" onclick="sendQuery()" disabled>
                            <span class="icon">🚀</span>
                            <span>Analyze</span>
                        </button>
                    </div>
                    
                    <!-- Suggestions -->
                    <div id="suggestions" class="suggestions" style="display: none;">
                        <span class="suggestions-label">Suggested questions:</span>
                        <div id="suggestionButtons" class="suggestion-buttons"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Loading Overlay -->
        <div id="loadingOverlay" class="loading-overlay" style="display: none;">
            <div class="loading-content">
                <div class="spinner"></div>
                <p id="loadingMessage">Initializing Power BI connection...</p>
            </div>
        </div>
    </div>

    <script>
        {get_analyst_javascript()}
    </script>
</body>
</html>'''

def get_analyst_css():
    """Return CSS styles for the analyst interface"""
    return '''
    /* Reset and Base Styles */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        background: #f5f7fa;
        color: #2d3748;
        line-height: 1.6;
        height: 100vh;
        overflow: hidden;
    }

    /* Container */
    .container {
        display: flex;
        flex-direction: column;
        height: 100vh;
    }

    /* Header */
    .header {
        background: white;
        border-bottom: 1px solid #e2e8f0;
        padding: 1rem 2rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }

    .header-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        max-width: 1400px;
        margin: 0 auto;
    }

    .logo-section {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .logo {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .header h1 {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a202c;
        margin: 0;
    }

    .tagline {
        font-size: 0.875rem;
        color: #718096;
        margin: 0;
    }

    .header-actions {
        display: flex;
        gap: 1rem;
    }

    .header-button {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        color: #4a5568;
        text-decoration: none;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .header-button:hover {
        background: #f7fafc;
        border-color: #cbd5e0;
        transform: translateY(-1px);
    }

    /* Main Container */
    .main-container {
        flex: 1;
        display: flex;
        flex-direction: column;
        max-width: 1200px;
        margin: 0 auto;
        width: 100%;
        padding: 2rem;
        gap: 1.5rem;
        overflow: hidden;
    }

    /* Workspace Section */
    .workspace-section {
        background: white;
        border-radius: 0.75rem;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .section-header h2 {
        font-size: 1.125rem;
        font-weight: 600;
        color: #2d3748;
    }

    .refresh-button {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.375rem 0.75rem;
        background: #edf2f7;
        border: none;
        border-radius: 0.375rem;
        color: #4a5568;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .refresh-button:hover {
        background: #e2e8f0;
    }

    .selector-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .selector-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .selector-group label {
        font-size: 0.875rem;
        font-weight: 500;
        color: #4a5568;
    }

    .selector-group select {
        padding: 0.625rem 0.875rem;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        background: white;
        color: #2d3748;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .selector-group select:hover {
        border-color: #cbd5e0;
    }

    .selector-group select:focus {
        outline: none;
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    .selection-info {
        padding: 0.75rem;
        background: #f7fafc;
        border-radius: 0.5rem;
        border: 1px solid #e2e8f0;
    }

    .info-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #4a5568;
        font-size: 0.875rem;
    }

    /* Chat Section */
    .chat-section {
        flex: 1;
        background: white;
        border-radius: 0.75rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .messages-container {
        flex: 1;
        overflow-y: auto;
        padding: 1.5rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    /* Messages */
    .message {
        animation: fadeIn 0.3s ease-out;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .message-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        font-size: 0.875rem;
    }

    .message-header .icon {
        font-size: 1.125rem;
    }

    .message-header .name {
        font-weight: 600;
        color: #2d3748;
    }

    .message-header .time {
        color: #a0aec0;
        margin-left: auto;
    }

    .message-content {
        padding: 1rem;
        border-radius: 0.5rem;
        font-size: 0.875rem;
        line-height: 1.6;
    }

    .message.assistant .message-content {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        color: #2d3748;
    }

    .message.user .message-content {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 4rem;
    }

    .message-content ul {
        margin: 0.5rem 0;
        padding-left: 1.5rem;
    }

    .message-content ul li {
        margin: 0.25rem 0;
    }

    .example-questions {
        list-style: none;
        padding-left: 0;
    }

    .example-questions li {
        padding: 0.5rem;
        margin: 0.25rem 0;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.375rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .example-questions li:hover {
        background: #edf2f7;
        transform: translateX(4px);
    }

    .hint {
        display: inline-block;
        margin-top: 1rem;
        padding: 0.5rem 0.75rem;
        background: #fef3c7;
        border: 1px solid #fcd34d;
        border-radius: 0.375rem;
        color: #92400e;
        font-size: 0.813rem;
    }

    /* Data Display */
    .data-table {
        margin: 1rem 0;
        overflow-x: auto;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
    }

    .data-table table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.813rem;
    }

    .data-table th {
        background: #f7fafc;
        padding: 0.75rem;
        text-align: left;
        font-weight: 600;
        color: #4a5568;
        border-bottom: 1px solid #e2e8f0;
    }

    .data-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #f7fafc;
    }

    .data-table tr:hover {
        background: #f7fafc;
    }

    /* Insights Section */
    .insights-section {
        margin-top: 1rem;
        padding: 1rem;
        background: #f0f4f8;
        border-radius: 0.5rem;
        border: 1px solid #cbd5e0;
    }

    .insights-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
        font-weight: 600;
        color: #2d3748;
    }

    .insight-item {
        margin: 0.5rem 0;
        padding: 0.5rem;
        background: white;
        border-radius: 0.375rem;
        border-left: 3px solid #667eea;
    }

    .recommendations-section {
        margin-top: 1rem;
        padding: 1rem;
        background: #e6fffa;
        border-radius: 0.5rem;
        border: 1px solid #81e6d9;
    }

    .recommendation-item {
        margin: 0.5rem 0;
        padding: 0.5rem;
        background: white;
        border-radius: 0.375rem;
        border-left: 3px solid #10b981;
    }

    /* Error Message */
    .error-section {
        margin: 1rem 0;
        padding: 1rem;
        background: #fed7d7;
        border: 1px solid #fc8181;
        border-radius: 0.5rem;
        color: #742a2a;
    }

    .error-section h4 {
        margin-bottom: 0.5rem;
        color: #742a2a;
    }

    /* Input Section */
    .input-section {
        padding: 1.5rem;
        border-top: 1px solid #e2e8f0;
        background: #f7fafc;
    }

    .input-container {
        display: flex;
        gap: 1rem;
        align-items: flex-end;
    }

    #queryInput {
        flex: 1;
        padding: 0.75rem;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        background: white;
        color: #2d3748;
        font-size: 0.875rem;
        font-family: inherit;
        resize: none;
        transition: all 0.2s;
    }

    #queryInput:focus {
        outline: none;
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    #sendButton {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 0.5rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }

    #sendButton:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }

    #sendButton:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    /* Suggestions */
    .suggestions {
        margin-top: 1rem;
    }

    .suggestions-label {
        font-size: 0.813rem;
        color: #718096;
        font-weight: 500;
    }

    .suggestion-buttons {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.5rem;
        flex-wrap: wrap;
    }

    .suggestion-button {
        padding: 0.5rem 0.875rem;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.375rem;
        color: #4a5568;
        font-size: 0.813rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .suggestion-button:hover {
        background: #f7fafc;
        border-color: #667eea;
        color: #667eea;
        transform: translateY(-1px);
    }

    /* Loading Overlay */
    .loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .loading-content {
        background: white;
        padding: 2rem;
        border-radius: 0.75rem;
        text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }

    .spinner {
        width: 50px;
        height: 50px;
        border: 4px solid #e2e8f0;
        border-left-color: #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 1rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Icon helper */
    .icon {
        display: inline-block;
        font-size: 1rem;
    }

    /* DAX Query Display */
    .dax-query {
        margin: 1rem 0;
        padding: 1rem;
        background: #2d3748;
        color: #e2e8f0;
        border-radius: 0.5rem;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.813rem;
        overflow-x: auto;
        white-space: pre-wrap;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .main-container {
            padding: 1rem;
        }
        
        .selector-container {
            grid-template-columns: 1fr;
        }
        
        .header-content {
            flex-direction: column;
            gap: 1rem;
            align-items: flex-start;
        }
        
        .message.user .message-content {
            margin-left: 0;
        }
    }
    '''

def get_analyst_javascript():
    """Return JavaScript code for the analyst interface"""
    return '''
    // Global state
    let currentWorkspace = null;
    let currentDataset = null;
    let sessionId = generateSessionId();
    let isProcessing = false;

    // Initialize on load
    window.onload = async function() {
        console.log('Power BI Analyst initialized');
        await checkConfiguration();
        await loadWorkspaces();
        setupEventListeners();
    };

    function generateSessionId() {
        return 'analyst_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    function setupEventListeners() {
        // Auto-resize textarea
        const textarea = document.getElementById('queryInput');
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        // Example questions
        document.querySelectorAll('.example-questions li').forEach(item => {
            item.addEventListener('click', function() {
                document.getElementById('queryInput').value = this.textContent;
                document.getElementById('queryInput').focus();
            });
        });
    }

    function showLoading(message = 'Processing...') {
        document.getElementById('loadingMessage').textContent = message;
        document.getElementById('loadingOverlay').style.display = 'flex';
    }

    function hideLoading() {
        document.getElementById('loadingOverlay').style.display = 'none';
    }

    async function checkConfiguration() {
        try {
            const response = await fetch('/analyst/api/check-config');
            const result = await response.json();
            
            if (!result.configured) {
                showError('Power BI is not configured. Please check your environment variables.');
                document.getElementById('sendButton').disabled = true;
            }
        } catch (error) {
            console.error('Configuration check failed:', error);
        }
    }

    async function loadWorkspaces() {
        showLoading('Loading workspaces...');
        
        try {
            const response = await fetch('/analyst/api/workspaces');
            const result = await response.json();
            
            const select = document.getElementById('workspaceSelect');
            select.innerHTML = '<option value="">Select a workspace...</option>';
            
            if (result.status === 'success' && result.workspaces) {
                result.workspaces.forEach(workspace => {
                    const option = document.createElement('option');
                    option.value = workspace.id;
                    option.textContent = workspace.name;
                    option.dataset = workspace;
                    select.appendChild(option);
                });
                
                if (result.workspaces.length === 0) {
                    select.innerHTML = '<option value="">No workspaces available</option>';
                }
            } else {
                showError('Failed to load workspaces: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            showError('Failed to load workspaces: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    async function onWorkspaceChange() {
        const select = document.getElementById('workspaceSelect');
        const workspaceId = select.value;
        
        if (!workspaceId) {
            document.getElementById('datasetSelect').innerHTML = '<option value="">Select a workspace first</option>';
            document.getElementById('sendButton').disabled = true;
            return;
        }
        
        currentWorkspace = {
            id: workspaceId,
            name: select.options[select.selectedIndex].text
        };
        
        await loadDatasets(workspaceId, currentWorkspace.name);
    }

    async function loadDatasets(workspaceId, workspaceName) {
        showLoading('Loading datasets...');
        
        try {
            const response = await fetch(`/analyst/api/datasets?workspace_id=${workspaceId}&workspace_name=${encodeURIComponent(workspaceName)}`);
            const result = await response.json();
            
            const select = document.getElementById('datasetSelect');
            select.innerHTML = '<option value="">Select a dataset...</option>';
            
            if (result.status === 'success' && result.datasets) {
                result.datasets.forEach(dataset => {
                    const option = document.createElement('option');
                    option.value = dataset.id;
                    option.textContent = dataset.name;
                    select.appendChild(option);
                });
                
                if (result.datasets.length === 0) {
                    select.innerHTML = '<option value="">No datasets available in this workspace</option>';
                }
            } else {
                showError('Failed to load datasets: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            showError('Failed to load datasets: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    function onDatasetChange() {
        const select = document.getElementById('datasetSelect');
        const datasetId = select.value;
        
        if (!datasetId) {
            currentDataset = null;
            document.getElementById('sendButton').disabled = true;
            document.getElementById('selectionInfo').style.display = 'none';
            return;
        }
        
        currentDataset = {
            id: datasetId,
            name: select.options[select.selectedIndex].text
        };
        
        // Update UI
        document.getElementById('selectedDatasetName').textContent = currentDataset.name;
        document.getElementById('selectionInfo').style.display = 'block';
        document.getElementById('sendButton').disabled = false;
        
        // Show suggestions
        showSuggestions([
            "What are the key metrics in this dataset?",
            "Show me recent performance trends",
            "What insights can you provide?"
        ]);
    }

    function showSuggestions(questions) {
        const container = document.getElementById('suggestionButtons');
        container.innerHTML = '';
        
        questions.forEach(question => {
            const button = document.createElement('button');
            button.className = 'suggestion-button';
            button.textContent = question;
            button.onclick = () => {
                document.getElementById('queryInput').value = question;
                document.getElementById('queryInput').focus();
            };
            container.appendChild(button);
        });
        
        document.getElementById('suggestions').style.display = 'block';
    }

    function handleKeyPress(event) {
        if (event.key === 'Enter' && !event.shiftKey && !isProcessing) {
            event.preventDefault();
            sendQuery();
        }
    }

    async function sendQuery() {
        const input = document.getElementById('queryInput');
        const query = input.value.trim();
        
        if (!query || !currentDataset || isProcessing) return;
        
        isProcessing = true;
        document.getElementById('sendButton').disabled = true;
        
        // Add user message
        addMessage(query, 'user');
        input.value = '';
        input.style.height = 'auto';
        
        // Show loading
        showLoading('Analyzing your question...');
        
        try {
            const response = await fetch('/analyst/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    dataset_id: currentDataset.id,
                    dataset_name: currentDataset.name,
                    session_id: sessionId
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                handleAnalysisResult(result);
            } else {
                showError(result.error || 'Analysis failed');
            }
        } catch (error) {
            showError('Failed to analyze query: ' + error.message);
        } finally {
            hideLoading();
            isProcessing = false;
            document.getElementById('sendButton').disabled = false;
            input.focus();
        }
    }

    function handleAnalysisResult(result) {
        const container = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        
        const time = new Date().toLocaleTimeString();
        let content = `
            <div class="message-header">
                <span class="icon">🤖</span>
                <span class="name">Power BI Analyst</span>
                <span class="time">${time}</span>
            </div>
            <div class="message-content">
        `;
        
        // Handle different query types
        if (result.query_type === 'error_with_analysis') {
            content += `
                <div class="error-section">
                    <h4>❌ Query Error</h4>
                    <p>${escapeHtml(result.error)}</p>
                </div>
                
                <div class="insights-section">
                    <div class="insights-header">
                        <span class="icon">🔧</span>
                        <span>Error Analysis</span>
                    </div>
                    <p><strong>Issue:</strong> ${escapeHtml(result.error_analysis.explanation)}</p>
                    <p><strong>Fix:</strong> ${escapeHtml(result.error_analysis.suggested_fix)}</p>
                    
                    <button class="suggestion-button" onclick="applyFix('${escapeHtml(result.error_analysis.fixed_query)}')">
                        Apply Suggested Fix
                    </button>
                </div>
            `;
        } else if (result.query_type === 'analysis_complete') {
            // Show explanation
            content += `<p>${escapeHtml(result.explanation)}</p>`;
            
            // Show data if available
            if (result.data && result.data.length > 0) {
                content += createDataTable(result.data);
            }
            
            // Show insights
            if (result.insights) {
                content += `
                    <div class="insights-section">
                        <div class="insights-header">
                            <span class="icon">💡</span>
                            <span>Key Insights</span>
                        </div>
                `;
                
                if (result.insights.insights && result.insights.insights.length > 0) {
                    result.insights.insights.forEach(insight => {
                        content += `<div class="insight-item">${escapeHtml(insight)}</div>`;
                    });
                }
                
                content += '</div>';
                
                // Show recommendations
                if (result.insights.recommendations && result.insights.recommendations.length > 0) {
                    content += `
                        <div class="recommendations-section">
                            <div class="insights-header">
                                <span class="icon">🎯</span>
                                <span>Recommendations</span>
                            </div>
                    `;
                    
                    result.insights.recommendations.forEach((rec, idx) => {
                        content += `<div class="recommendation-item">${idx + 1}. ${escapeHtml(rec)}</div>`;
                    });
                    
                    content += '</div>';
                }
            }
            
            // Show DAX query (collapsible)
            if (result.dax_query) {
                content += `
                    <details style="margin-top: 1rem;">
                        <summary style="cursor: pointer; color: #667eea;">View DAX Query</summary>
                        <div class="dax-query">${escapeHtml(result.dax_query)}</div>
                    </details>
                `;
            }
            
            // Update suggestions with follow-up queries
            if (result.follow_up_queries && result.follow_up_queries.length > 0) {
                const questions = result.follow_up_queries.map(q => q.question);
                showSuggestions(questions);
            }
        }
        
        content += '</div>';
        messageDiv.innerHTML = content;
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
    }

    function createDataTable(data) {
        if (!data || data.length === 0) return '';
        
        const columns = Object.keys(data[0]);
        const maxRows = 20;
        
        let html = `
            <div class="data-table">
                <table>
                    <thead>
                        <tr>
        `;
        
        columns.forEach(col => {
            html += `<th>${escapeHtml(col)}</th>`;
        });
        
        html += `
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        data.slice(0, maxRows).forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                const value = row[col];
                const displayValue = value === null ? 'null' : 
                                   typeof value === 'number' ? formatNumber(value) : 
                                   String(value);
                html += `<td>${escapeHtml(displayValue)}</td>`;
            });
            html += '</tr>';
        });
        
        html += `
                    </tbody>
                </table>
        `;
        
        if (data.length > maxRows) {
            html += `<p style="text-align: center; color: #718096; margin-top: 0.5rem;">
                        Showing ${maxRows} of ${data.length} rows
                     </p>`;
        }
        
        html += '</div>';
        
        return html;
    }

    function formatNumber(num) {
        if (num === null || num === undefined) return 'null';
        if (typeof num !== 'number') return String(num);
        
        // Format large numbers with commas
        if (Math.abs(num) >= 1000) {
            return num.toLocaleString('en-US', { maximumFractionDigits: 2 });
        }
        
        // For small decimals, show up to 4 decimal places
        return num.toLocaleString('en-US', { maximumFractionDigits: 4 });
    }

    async function applyFix(fixedQuery) {
        if (!currentDataset || isProcessing) return;
        
        isProcessing = true;
        showLoading('Applying fixed query...');
        
        try {
            const response = await fetch('/analyst/api/execute-dax', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    dax_query: fixedQuery,
                    dataset_id: currentDataset.id,
                    dataset_name: currentDataset.name
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Create a synthetic analysis result
                const analysisResult = {
                    query_type: 'analysis_complete',
                    explanation: 'Query executed successfully after applying fix.',
                    data: result.data,
                    row_count: result.row_count,
                    execution_time_ms: result.execution_time_ms,
                    dax_query: fixedQuery
                };
                
                handleAnalysisResult(analysisResult);
            } else {
                showError('Fixed query still failed: ' + result.error);
            }
        } catch (error) {
            showError('Failed to apply fix: ' + error.message);
        } finally {
            hideLoading();
            isProcessing = false;
        }
    }

    function addMessage(text, type) {
        const container = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const time = new Date().toLocaleTimeString();
        
        if (type === 'user') {
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="icon">👤</span>
                    <span class="name">You</span>
                    <span class="time">${time}</span>
                </div>
                <div class="message-content">${escapeHtml(text)}</div>
            `;
        }
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
    }

    function showError(message) {
        const container = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        
        const time = new Date().toLocaleTimeString();
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="icon">🤖</span>
                <span class="name">Power BI Analyst</span>
                <span class="time">${time}</span>
            </div>
            <div class="message-content">
                <div class="error-section">
                    <h4>❌ Error</h4>
                    <p>${escapeHtml(message)}</p>
                </div>
            </div>
        `;
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
    }

    async function testConnection() {
        showLoading('Testing Power BI connection...');
        
        try {
            const response = await fetch('/analyst/api/test-connection');
            const result = await response.json();
            
            const container = document.getElementById('messagesContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            
            const time = new Date().toLocaleTimeString();
            let content = `
                <div class="message-header">
                    <span class="icon">🔌</span>
                    <span class="name">Connection Test</span>
                    <span class="time">${time}</span>
                </div>
                <div class="message-content">
                    <h4>Power BI Connection Test Results</h4>
            `;
            
            if (result.test_results && result.test_results.test_steps) {
                result.test_results.test_steps.forEach(step => {
                    const icon = step.success ? '✅' : '❌';
                    content += `
                        <div style="margin: 0.5rem 0;">
                            <strong>${icon} ${step.step}:</strong> ${step.details}
                        </div>
                    `;
                });
            }
            
            if (result.ready) {
                content += '<p style="margin-top: 1rem; color: #10b981;">✅ Power BI is ready to use!</p>';
            } else {
                content += '<p style="margin-top: 1rem; color: #ef4444;">❌ Power BI configuration needs attention.</p>';
            }
            
            content += '</div>';
            messageDiv.innerHTML = content;
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
            
        } catch (error) {
            showError('Connection test failed: ' + error.message);
        } finally {
            hideLoading();
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    '''