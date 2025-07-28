# sql_console_javascript.py - Enhanced SQL Console JavaScript with Error Analysis UI
"""
SQL Console JavaScript - Enhanced with intelligent error handling and fix suggestions
"""

def get_sql_console_javascript():
    """Return the enhanced JavaScript code for the SQL console with error analysis"""
    return '''
    let currentDatabase = 'demo';  // Default to demo instead of master
    let isProcessing = false;
    let sessionId = generateSessionId();
    let multiDbMode = false;
    let selectedDatabases = new Set();
    let currentRequest = null;
    let conversationLogs = [];  // Store all logs for export
    let lastErrorAnalysis = null;  // Store last error analysis for reference

    // Initialize
    window.onload = async function() {
        await getCurrentUser();
        document.getElementById('messageInput').focus();
        
        // Auto-resize textarea
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
        
        // Set default database to demo
        currentDatabase = 'demo';
        document.getElementById('currentDatabase').textContent = currentDatabase;
        
        // Add initial log message
        addLogMessage('System initialized. Ready for queries.', 'success');
        addLogMessage('Available databases: _support, demo', 'info');
        addLogMessage('✨ NEW: If a query fails, I will analyze the error and suggest fixes!', 'info');
        addLogMessage('Use multi-database mode for standardization checks', 'info');
        
        // Load databases
        await loadInitialDatabases();
    };

    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function handleKeyPress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }

    function quickCommand(command) {
        document.getElementById('messageInput').value = command;
        if (command === 'COMPARE SCHEMAS') {
            // Auto-enable multi-database mode for schema comparison
            if (!multiDbMode) {
                document.getElementById('multiDbMode').checked = true;
                toggleMultiDbMode();
            }
            addLogMessage('💡 Tip: Select databases to compare and add table name', 'info');
        }
    }

    async function loadInitialDatabases() {
        const databaseList = document.getElementById('databaseList');
        databaseList.innerHTML = '<div class="loading-indicator">Discovering databases...</div>';
        
        addLogMessage('Initializing database discovery...', 'info');
        
        try {
            const response = await fetch('/console/api/databases');
            const result = await response.json();
            
            if (result.status === 'success' && result.databases) {
                databaseList.innerHTML = '';
                
                result.databases.forEach(db => {
                    const dbItem = document.createElement('div');
                    dbItem.className = 'database-item';
                    dbItem.setAttribute('data-db-name', db);
                    
                    if (db === currentDatabase) {
                        dbItem.classList.add('active');
                    }
                    
                    // Add database icon based on type
                    let icon = '🗄️';
                    if (db === '_support') icon = '🛠️';
                    else if (db === 'demo') icon = '📊';
                    
                    dbItem.innerHTML = `<span class="db-icon">${icon}</span> ${db}`;
                    
                    // FIXED: Always allow database selection for viewing tables
                    dbItem.onclick = (e) => {
                        // Check if click was on checkbox
                        if (e.target.classList.contains('database-checkbox')) {
                            return; // Let checkbox handle its own click
                        }
                        
                        // Always select database to view tables
                        selectDatabase(db);
                        
                        // If in multi-db mode and not clicking checkbox, also toggle selection
                        if (multiDbMode && !e.target.classList.contains('database-checkbox')) {
                            toggleDatabaseSelection(db);
                        }
                    };
                    
                    databaseList.appendChild(dbItem);
                });
                
                addLogMessage(`Discovered ${result.databases.length} accessible databases`, 'success');
                
                // Load tables for current database
                await loadTables(currentDatabase);
            }
        } catch (error) {
            addLogMessage(`Error discovering databases: ${error.message}`, 'error');
        }
    }

    function toggleMultiDbMode() {
        multiDbMode = document.getElementById('multiDbMode').checked;
        
        // Show/hide multi-db UI elements
        document.getElementById('selectAllDbBtn').style.display = multiDbMode ? 'block' : 'none';
        document.getElementById('selectedDbIndicator').style.display = multiDbMode ? 'block' : 'none';
        document.getElementById('multiDbIndicator').style.display = multiDbMode ? 'block' : 'none';
        
        // Update database items
        const dbItems = document.querySelectorAll('.database-item');
        dbItems.forEach(item => {
            if (multiDbMode) {
                item.classList.add('multi-select-mode');
                
                // Add checkbox if not exists
                if (!item.querySelector('.database-checkbox')) {
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.className = 'database-checkbox';
                    checkbox.onclick = (e) => {
                        e.stopPropagation();
                        toggleDatabaseSelection(item.getAttribute('data-db-name'));
                    };
                    item.insertBefore(checkbox, item.firstChild);
                }
            } else {
                item.classList.remove('multi-select-mode');
                const checkbox = item.querySelector('.database-checkbox');
                if (checkbox) checkbox.remove();
            }
        });
        
        if (!multiDbMode) {
            selectedDatabases.clear();
            updateSelectedDatabasesUI();
        } else {
            // Auto-select all databases for comparison
            toggleAllDatabases();
        }
        
        addLogMessage(multiDbMode ? 'Multi-database mode enabled for comparisons' : 'Single database mode', 'info');
    }

    function toggleDatabaseSelection(dbName) {
        if (selectedDatabases.has(dbName)) {
            selectedDatabases.delete(dbName);
        } else {
            selectedDatabases.add(dbName);
        }
        updateSelectedDatabasesUI();
    }

    function toggleAllDatabases() {
        const dbItems = document.querySelectorAll('.database-item');
        const allSelected = selectedDatabases.size === dbItems.length;
        
        if (allSelected) {
            selectedDatabases.clear();
        } else {
            dbItems.forEach(item => {
                selectedDatabases.add(item.getAttribute('data-db-name'));
            });
        }
        updateSelectedDatabasesUI();
    }

    function updateSelectedDatabasesUI() {
        const count = selectedDatabases.size;
        
        // Update selected count
        document.querySelector('.selected-count').textContent = `${count} database${count !== 1 ? 's' : ''} selected`;
        document.getElementById('selectedDbCount').textContent = count;
        
        // Update button text
        const selectAllBtn = document.getElementById('selectAllDbBtn');
        const dbItems = document.querySelectorAll('.database-item');
        selectAllBtn.textContent = count === dbItems.length ? 'Deselect All' : 'Select All';
        
        // Update checkboxes and highlighting
        dbItems.forEach(item => {
            const dbName = item.getAttribute('data-db-name');
            const checkbox = item.querySelector('.database-checkbox');
            
            if (selectedDatabases.has(dbName)) {
                item.classList.add('selected');
                if (checkbox) checkbox.checked = true;
            } else {
                item.classList.remove('selected');
                if (checkbox) checkbox.checked = false;
            }
        });
    }

    function addLogMessage(message, type = 'info') {
        const messagesContainer = document.getElementById('messagesContainer');
        const logDiv = document.createElement('div');
        logDiv.className = 'message bot log-message';
        
        const time = new Date().toLocaleTimeString();
        const timestamp = new Date().toISOString();
        
        // Store log for export
        conversationLogs.push({
            timestamp: timestamp,
            type: type,
            message: message
        });
        
        let icon = '';
        let color = '';
        switch(type) {
            case 'info': icon = 'ℹ️'; color = '#3b82f6'; break;
            case 'success': icon = '✅'; color = '#10b981'; break;
            case 'warning': icon = '⚠️'; color = '#f59e0b'; break;
            case 'error': icon = '❌'; color = '#ef4444'; break;
            case 'debug': icon = '🔍'; color = '#6b7280'; break;
        }
        
        logDiv.innerHTML = `
            <div class="message-content" style="background-color: rgba(30, 41, 59, 0.5); border-color: ${color};">
                <div class="message-header" style="color: ${color};">${icon} System Log • ${time}</div>
                <div class="message-text" style="color: #cbd5e1; font-size: 0.875rem;">${escapeHtml(message)}</div>
            </div>
        `;
        
        messagesContainer.appendChild(logDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    async function sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message || isProcessing) return;
        
        isProcessing = true;
        document.getElementById('sendButton').disabled = true;
        document.getElementById('sendButton').innerHTML = '<span class="spinner"></span> Processing...';
        
        // Show cancel button
        const cancelBtn = document.getElementById('cancelButton');
        if (cancelBtn) cancelBtn.style.display = 'inline-block';
        
        // Add user message
        addMessage(message, 'user');
        input.value = '';
        input.style.height = 'auto';
        
        // Show typing indicator
        showTypingIndicator();
        
        // Log the start of processing
        addLogMessage(`Processing query: "${message.substring(0, 50)}${message.length > 50 ? '...' : ''}"`, 'info');
        
        try {
            // Prepare request data
            const requestData = {
                message: message,
                database: currentDatabase,
                session_id: sessionId,
                analyze_results: true  // Enable AI analysis
            };
            
            // Add multi-database info if in multi-db mode
            if (multiDbMode && selectedDatabases.size > 0) {
                requestData.multi_db_mode = true;
                requestData.databases = Array.from(selectedDatabases);
                addLogMessage(`Multi-database query: ${requestData.databases.join(', ')}`, 'info');
            }
            
            addLogMessage('Sending request to server...', 'debug');
            
            currentRequest = fetch('/console/api/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            const response = await currentRequest;
            
            addLogMessage(`Server response received: ${response.status} ${response.statusText}`, 'debug');
            
            const result = await response.json();
            
            hideTypingIndicator();
            
            if (result.status === 'success') {
                addLogMessage('Query processed successfully', 'success');
                
                // Handle different response types
                if (result.response_type === 'sql_result') {
                    if (result.sql_query) {
                        addLogMessage(`SQL Query executed: ${result.sql_query}`, 'info');
                    }
                    
                    if (result.multi_db_results) {
                        handleMultiDbResults(result);
                    } else {
                        handleSingleDbResult(result);
                    }
                } else if (result.response_type === 'sql_result_with_errors') {
                    // Handle multi-database results with errors
                    handleMultiDbResultsWithErrors(result);
                } else if (result.response_type === 'sql_error_with_analysis') {
                    // Handle single database error with analysis
                    handleSqlErrorWithAnalysis(result);
                } else if (result.response_type === 'analyzed_result') {
                    handleAnalyzedResult(result);
                } else if (result.response_type === 'schema_comparison') {
                    handleSchemaComparison(result);
                } else if (result.response_type === 'standardization_check') {
                    handleStandardizationCheck(result);
                } else if (result.response_type === 'help') {
                    addMessage(result.content, 'bot');
                } else {
                    addMessage(result.content || 'Query completed', 'bot');
                }
            } else {
                const errorMsg = result.error || 'An error occurred';
                addLogMessage(`Error: ${errorMsg}`, 'error');
                addErrorMessage(errorMsg);
            }
        } catch (error) {
            hideTypingIndicator();
            addLogMessage(`Connection error: ${error.message}`, 'error');
            addErrorMessage('Connection error: ' + error.message);
        } finally {
            isProcessing = false;
            document.getElementById('sendButton').disabled = false;
            document.getElementById('sendButton').innerHTML = 'Send';
            
            // Hide cancel button
            const cancelBtn = document.getElementById('cancelButton');
            if (cancelBtn) cancelBtn.style.display = 'none';
            
            currentRequest = null;
            input.focus();
        }
    }

    function handleSqlErrorWithAnalysis(result) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        const analysis = result.error_analysis;
        lastErrorAnalysis = analysis;  // Store for reference
        
        // Store the analysis data globally for button clicks
        window.lastErrorAnalysisData = {
            fixed_query: analysis.fixed_query,
            database: result.database,
            alternatives: analysis.alternative_queries || [],
            discovery: analysis.discovery_queries || []
        };
        
        let content = `
            <div class="message-content">
                <div class="message-header">SQL Assistant • ${time}</div>
                <div class="message-text">Query failed on database: ${result.database}</div>
                
                <div class="error-message" style="margin: 1rem 0;">
                    <strong>Error:</strong> ${escapeHtml(result.error)}
                </div>
                
                <div class="error-analysis" style="background-color: rgba(99, 102, 241, 0.1); border: 1px solid #6366f1; border-radius: 0.5rem; padding: 1rem; margin: 1rem 0;">
                    <h4 style="color: #6366f1; margin-bottom: 0.5rem;">🤖 Error Analysis</h4>
                    
                    <div style="margin-bottom: 0.75rem;">
                        <strong>Error Type:</strong> ${escapeHtml(analysis.error_type)}
                    </div>
                    
                    <div style="margin-bottom: 0.75rem;">
                        <strong>Explanation:</strong> ${escapeHtml(analysis.explanation)}
                    </div>
                    
                    <div style="margin-bottom: 0.75rem;">
                        <strong>Suggested Fix:</strong> ${escapeHtml(analysis.suggested_fix)}
                    </div>
                    
                    <div style="margin-bottom: 0.75rem;">
                        <strong>Fixed Query:</strong>
                        <div class="sql-query" style="margin-top: 0.5rem;">${escapeHtml(analysis.fixed_query)}</div>
                    </div>
                    
                    <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
                        <button class="quick-action" onclick="applyFixedQuery()">
                            🔧 Apply Fix
                        </button>
        `;
        
        // Add alternative queries if available
        if (analysis.alternative_queries && analysis.alternative_queries.length > 0) {
            content += `
                        <button class="quick-action" onclick="showAlternativeQueries()">
                            🔄 Show Alternatives (${analysis.alternative_queries.length})
                        </button>
            `;
        }
        
        // Add discovery queries if available
        if (analysis.discovery_queries && analysis.discovery_queries.length > 0) {
            content += `
                        <button class="quick-action" onclick="showDiscoveryQueries()">
                            🔍 Discovery Queries (${analysis.discovery_queries.length})
                        </button>
            `;
        }
        
        content += `
                    </div>
                </div>
                
                <div style="margin-top: 1rem;">
                    <div class="sql-query">${escapeHtml(result.sql_query)}</div>
                </div>
            </div>
        `;
        
        messageDiv.innerHTML = content;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        addLogMessage(`Error analyzed: ${analysis.error_type} - Confidence: ${(analysis.confidence * 100).toFixed(0)}%`, 'info');
    }

    // New simplified apply fix function
    async function applyFixedQuery() {
        if (!window.lastErrorAnalysisData) {
            addErrorMessage('No error analysis data available');
            return;
        }
        
        const data = window.lastErrorAnalysisData;
        
        addLogMessage(`Applying error fix to database: ${data.database}`, 'info');
        showTypingIndicator();
        
        try {
            const response = await fetch('/console/api/apply-fix', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    fixed_query: data.fixed_query,
                    database: data.database,
                    multi_db_mode: multiDbMode,
                    databases: multiDbMode ? Array.from(selectedDatabases) : []
                })
            });
            
            const result = await response.json();
            hideTypingIndicator();
            
            if (result.status === 'success') {
                addLogMessage('✅ Fixed query executed successfully!', 'success');
                
                // Show a message indicating this was a fixed query
                const fixedMessage = document.createElement('div');
                fixedMessage.className = 'message bot';
                fixedMessage.innerHTML = `
                    <div class="message-content" style="border-left: 3px solid #10b981;">
                        <div class="message-header">🔧 Fixed Query Result • ${new Date().toLocaleTimeString()}</div>
                        <div class="message-text">The error was fixed and the query executed successfully!</div>
                    </div>
                `;
                document.getElementById('messagesContainer').appendChild(fixedMessage);
                
                // Handle the result based on type
                if (result.response_type === 'sql_result') {
                    if (result.multi_db_results) {
                        handleMultiDbResults(result);
                    } else {
                        handleSingleDbResult(result);
                    }
                }
            } else {
                addErrorMessage(`Failed to apply fix: ${result.error}`);
            }
        } catch (error) {
            hideTypingIndicator();
            addLogMessage(`Error applying fix: ${error.message}`, 'error');
            addErrorMessage(`Error applying fix: ${error.message}`);
        }
    }

    // Fixed multi-database error handling
    function handleMultiDbResultsWithErrors(result) {
        // First show the regular multi-db results
        addMultiDbSQLResult(result);
        
        // Then add error analysis for failed databases
        if (result.error_analysis && result.error_analysis.length > 0) {
            const messagesContainer = document.getElementById('messagesContainer');
            const analysisDiv = document.createElement('div');
            analysisDiv.className = 'message bot';
            
            const time = new Date().toLocaleTimeString();
            
            // Store analyses for button clicks
            window.multiDbErrorAnalyses = {};
            result.error_analysis.forEach(analysis => {
                window.multiDbErrorAnalyses[analysis.database] = analysis;
            });
            
            let content = `
                <div class="message-content">
                    <div class="message-header">🤖 Error Analysis • ${time}</div>
                    <div class="message-text">Found errors in ${result.error_analysis.length} database(s). Here's the analysis:</div>
                    
                    <div style="margin-top: 1rem;">
            `;
            
            result.error_analysis.forEach((analysis, idx) => {
                content += `
                    <div class="db-error-analysis" style="background-color: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem;">
                        <h5 style="color: #ef4444; margin-bottom: 0.5rem;">Database: ${escapeHtml(analysis.database)}</h5>
                        
                        <div style="font-size: 0.875rem;">
                            <div><strong>Error Type:</strong> ${escapeHtml(analysis.error_type)}</div>
                            <div><strong>Explanation:</strong> ${escapeHtml(analysis.explanation)}</div>
                            <div><strong>Fix:</strong> ${escapeHtml(analysis.suggested_fix)}</div>
                        </div>
                        
                        <button class="quick-action" style="margin-top: 0.5rem;" onclick="applyMultiDbFix('${escapeHtml(analysis.database)}')">
                            🔧 Fix for ${escapeHtml(analysis.database)}
                        </button>
                    </div>
                `;
            });
            
            content += `
                    </div>
                </div>
            `;
            
            analysisDiv.innerHTML = content;
            messagesContainer.appendChild(analysisDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    // New function for multi-db fixes
    async function applyMultiDbFix(database) {
        if (!window.multiDbErrorAnalyses || !window.multiDbErrorAnalyses[database]) {
            addErrorMessage('No error analysis data available for ' + database);
            return;
        }
        
        const analysis = window.multiDbErrorAnalyses[database];
        
        addLogMessage(`Applying error fix to database: ${database}`, 'info');
        showTypingIndicator();
        
        try {
            const response = await fetch('/console/api/apply-fix', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    fixed_query: analysis.fixed_query,
                    database: database,
                    multi_db_mode: true,
                    databases: Array.from(selectedDatabases)
                })
            });
            
            const result = await response.json();
            hideTypingIndicator();
            
            if (result.status === 'success') {
                addLogMessage(`✅ Fixed query executed successfully on ${database}!`, 'success');
                
                // Handle the result
                if (result.response_type === 'sql_result') {
                    if (result.multi_db_results) {
                        handleMultiDbResults(result);
                    } else {
                        handleSingleDbResult(result);
                    }
                }
            } else {
                addErrorMessage(`Failed to apply fix: ${result.error}`);
            }
        } catch (error) {
            hideTypingIndicator();
            addLogMessage(`Error applying fix: ${error.message}`, 'error');
        }
    }

    // Fixed show alternatives function
    function showAlternativeQueries() {
        if (!window.lastErrorAnalysisData || !window.lastErrorAnalysisData.alternatives) return;
        
        const messagesContainer = document.getElementById('messagesContainer');
        const altDiv = document.createElement('div');
        altDiv.className = 'message bot';
        
        let content = `
            <div class="message-content">
                <div class="message-header">🔄 Alternative Queries • ${new Date().toLocaleTimeString()}</div>
                <div class="message-text">Here are alternative queries that might work:</div>
                
                <div style="margin-top: 1rem;">
        `;
        
        window.lastErrorAnalysisData.alternatives.forEach((query, idx) => {
            content += `
                <div style="margin-bottom: 1rem;">
                    <div class="sql-query" style="margin-bottom: 0.5rem;">${escapeHtml(query)}</div>
                    <button class="quick-action" onclick="useAlternativeQuery(${idx})">
                        📋 Use This Query
                    </button>
                </div>
            `;
        });
        
        content += `
                </div>
            </div>
        `;
        
        altDiv.innerHTML = content;
        messagesContainer.appendChild(altDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // New function to use alternative query
    function useAlternativeQuery(index) {
        if (!window.lastErrorAnalysisData || !window.lastErrorAnalysisData.alternatives[index]) return;
        
        const query = window.lastErrorAnalysisData.alternatives[index];
        document.getElementById('messageInput').value = query;
        document.getElementById('messageInput').focus();
        addLogMessage('Alternative query loaded in input box', 'info');
    }

    // Fixed show discovery queries function
    function showDiscoveryQueries() {
        if (!window.lastErrorAnalysisData || !window.lastErrorAnalysisData.discovery) return;
        
        const messagesContainer = document.getElementById('messagesContainer');
        const discDiv = document.createElement('div');
        discDiv.className = 'message bot';
        
        let content = `
            <div class="message-content">
                <div class="message-header">🔍 Discovery Queries • ${new Date().toLocaleTimeString()}</div>
                <div class="message-text">These queries can help you find the correct table/column names:</div>
                
                <div style="margin-top: 1rem;">
        `;
        
        window.lastErrorAnalysisData.discovery.forEach((query, idx) => {
            content += `
                <div style="margin-bottom: 1rem;">
                    <div class="sql-query" style="margin-bottom: 0.5rem;">${escapeHtml(query)}</div>
                    <button class="quick-action" onclick="runDiscoveryQueryByIndex(${idx})">
                        🔍 Run Discovery
                    </button>
                </div>
            `;
        });
        
        content += `
                </div>
            </div>
        `;
        
        discDiv.innerHTML = content;
        messagesContainer.appendChild(discDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // New function to run discovery query by index
    async function runDiscoveryQueryByIndex(index) {
        if (!window.lastErrorAnalysisData || !window.lastErrorAnalysisData.discovery[index]) return;
        
        const query = window.lastErrorAnalysisData.discovery[index];
        await runDiscoveryQuery(query);
    }

    // Fixed run discovery query function
    async function runDiscoveryQuery(query) {
        try {
            addLogMessage('Running discovery query...', 'info');
            showTypingIndicator();
            
            const response = await fetch('/console/api/discovery', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    query: query,
                    database: currentDatabase
                })
            });
            
            const result = await response.json();
            hideTypingIndicator();
            
            if (result.status === 'success') {
                addLogMessage('Discovery query completed', 'success');
                
                const messagesContainer = document.getElementById('messagesContainer');
                const resultDiv = document.createElement('div');
                resultDiv.className = 'message bot';
                
                resultDiv.innerHTML = `
                    <div class="message-content" style="border-left: 3px solid #6366f1;">
                        <div class="message-header">🔍 Discovery Result • ${new Date().toLocaleTimeString()}</div>
                        <div class="message-text">Found ${result.row_count} results in ${result.database}</div>
                    </div>
                `;
                
                messagesContainer.appendChild(resultDiv);
                
                // Show the discovery results
                handleSingleDbResult(result);
            } else {
                addErrorMessage(`Discovery query failed: ${result.error}`);
            }
        } catch (error) {
            hideTypingIndicator();
            addLogMessage(`Discovery error: ${error.message}`, 'error');
        }
    }

    function handleMultiDbResults(result) {
        const successCount = result.multi_db_results.filter(r => !r.error).length;
        addLogMessage(`Multi-DB results: ${successCount}/${result.multi_db_results.length} successful`, 'info');
        addMultiDbSQLResult(result);
    }

    function handleSingleDbResult(result) {
        if (result.row_count !== undefined) {
            addLogMessage(`Query returned ${result.row_count} rows in ${result.execution_time}ms`, 'success');
        }
        addSQLResult(result);
    }

    function handleAnalyzedResult(result) {
        // Add the SQL result first
        if (result.multi_db_results) {
            addMultiDbSQLResult(result);
        }
        
        // Then add the analysis
        if (result.analysis && result.analysis.analysis_text) {
            addAnalysisResult(result.analysis);
        }
    }

    function handleSchemaComparison(result) {
        addSchemaComparisonResult(result);
    }

    function handleStandardizationCheck(result) {
        addStandardizationResult(result);
    }

    function addAnalysisResult(analysis) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-header">🤖 AI Analysis • ${time}</div>
                <div class="message-text">${escapeHtml(analysis.analysis_text)}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addSchemaComparisonResult(result) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        
        let content = `
            <div class="message-content">
                <div class="message-header">📊 Schema Comparison • ${time}</div>
                <div class="message-text">Comparing table: ${result.table_name}</div>
                <div class="sql-result">
        `;
        
        // Show comparison results
        if (result.comparison) {
            content += '<div class="comparison-results">';
            // Add comparison visualization here
            content += '</div>';
        }
        
        content += '</div></div>';
        
        messageDiv.innerHTML = content;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addStandardizationResult(result) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        
        let content = `
            <div class="message-content">
                <div class="message-header">🔍 Standardization Check • ${time}</div>
                <div class="sql-result">
        `;
        
        if (result.analysis) {
            content += '<h4>Database Compliance:</h4><ul>';
            result.analysis.database_compliance.forEach(db => {
                const score = Math.round(db.compliance_score * 100);
                content += `<li>${db.database}: ${score}% compliant (schemas: ${db.schemas_found.join(', ')})</li>`;
            });
            content += '</ul>';
        }
        
        content += '</div></div>';
        
        messageDiv.innerHTML = content;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    async function cancelRequest() {
        if (currentRequest) {
            addLogMessage('Cancelling request...', 'warning');
            
            try {
                await fetch('/console/api/cancel', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ session_id: sessionId })
                });
            } catch (e) {
                console.error('Error sending cancel request:', e);
            }
            
            addLogMessage('Cancel request sent to server', 'warning');
        }
    }

    async function copyLogs() {
        try {
            // Create formatted text from logs
            const logText = conversationLogs.map(log => {
                const time = new Date(log.timestamp).toLocaleString();
                return `[${time}] ${log.type.toUpperCase()}: ${log.message}`;
            }).join('\\n');
            
            // Try to use clipboard API
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(logText);
                addLogMessage('Logs copied to clipboard!', 'success');
            } else {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = logText;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                addLogMessage('Logs copied to clipboard!', 'success');
            }
        } catch (error) {
            addLogMessage('Failed to copy logs: ' + error.message, 'error');
        }
    }

    async function exportLogs() {
        try {
            const response = await fetch('/console/api/export-logs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    logs: conversationLogs,
                    format: 'text',
                    session_id: sessionId
                })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `sql_console_logs_${new Date().toISOString().split('T')[0]}.txt`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                addLogMessage('Logs exported successfully', 'success');
            } else {
                addLogMessage('Failed to export logs', 'error');
            }
        } catch (error) {
            addLogMessage('Export error: ' + error.message, 'error');
        }
    }

    function addMessage(text, sender) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const time = new Date().toLocaleTimeString();
        const header = sender === 'user' ? 'You' : 'SQL Assistant';
        
        // Store message in logs
        conversationLogs.push({
            timestamp: new Date().toISOString(),
            type: sender,
            message: text
        });
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-header">${header} • ${time}</div>
                <div class="message-text">${escapeHtml(text)}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addSQLResult(result) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        
        let content = `
            <div class="message-content">
                <div class="message-header">SQL Assistant • ${time}</div>
                <div class="message-text">${escapeHtml(result.explanation || 'Query executed successfully')}</div>
        `;
        
        if (result.sql_query) {
            content += `
                <div class="sql-result">
                    <div class="result-header">
                        <div class="result-info">
                            Database: ${result.database || currentDatabase}
                        </div>
                        <div class="result-info">
                            ${result.row_count || 0} rows • ${result.execution_time || 0}ms
                        </div>
                    </div>
                    <div class="sql-query">${escapeHtml(result.sql_query)}</div>
            `;
            
            if (result.rows && result.rows.length > 0) {
                // Create table
                const columns = Object.keys(result.rows[0]);
                content += '<table class="result-table"><thead><tr>';
                columns.forEach(col => {
                    content += `<th>${escapeHtml(col)}</th>`;
                });
                content += '</tr></thead><tbody>';
                
                result.rows.forEach(row => {
                    content += '<tr>';
                    columns.forEach(col => {
                        const value = row[col] === null ? 'NULL' : String(row[col]);
                        content += `<td>${escapeHtml(value)}</td>`;
                    });
                    content += '</tr>';
                });
                
                content += '</tbody></table>';
            } else {
                content += '<div style="color: #64748b; padding: 1rem;">No results returned</div>';
            }
            
            content += '</div>';
        }
        
        content += '</div>';
        
        messageDiv.innerHTML = content;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addMultiDbSQLResult(result) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        
        let content = `
            <div class="message-content">
                <div class="message-header">SQL Assistant • ${time}</div>
                <div class="message-text">${escapeHtml(result.explanation || 'Multi-database query executed')}</div>
                <div class="sql-result">
                    <div class="sql-query">${escapeHtml(result.sql_query)}</div>
                    <div class="multi-db-results">
        `;
        
        // Process results for each database
        result.multi_db_results.forEach(dbResult => {
            const hasError = dbResult.error;
            const borderColor = hasError ? '#ef4444' : '#334155';
            
            content += `
                <div class="db-result-section" style="border-color: ${borderColor};">
                    <div class="db-result-header">
                        <div class="db-name">${hasError ? '❌' : '📊'} ${escapeHtml(dbResult.database)}</div>
                        <div class="db-result-stats">
                            ${hasError ? 'Error' : `${dbResult.row_count || 0} rows • ${dbResult.execution_time || 0}ms`}
                        </div>
                    </div>
            `;
            
            if (dbResult.error) {
                content += `<div class="error-message">❌ ${escapeHtml(dbResult.error)}</div>`;
            } else if (dbResult.rows && dbResult.rows.length > 0) {
                // Create table for this database
                const columns = Object.keys(dbResult.rows[0]);
                content += '<table class="result-table"><thead><tr>';
                columns.forEach(col => {
                    content += `<th>${escapeHtml(col)}</th>`;
                });
                content += '</tr></thead><tbody>';
                
                dbResult.rows.forEach(row => {
                    content += '<tr>';
                    columns.forEach(col => {
                        const value = row[col] === null ? 'NULL' : String(row[col]);
                        content += `<td>${escapeHtml(value)}</td>`;
                    });
                    content += '</tr>';
                });
                
                content += '</tbody></table>';
            } else {
                content += '<div style="color: #64748b; padding: 1rem;">No results returned</div>';
            }
            
            content += '</div>';
        });
        
        content += `
                    </div>
                </div>
            </div>
        `;
        
        messageDiv.innerHTML = content;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addErrorMessage(error) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        const time = new Date().toLocaleTimeString();
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-header">SQL Assistant • ${time}</div>
                <div class="error-message">❌ ${escapeHtml(error)}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function showTypingIndicator() {
        const messagesContainer = document.getElementById('messagesContainer');
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typingIndicator';
        typingDiv.className = 'message bot';
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <span>SQL Assistant is thinking...</span>
            </div>
        `;
        
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }

    async function refreshDatabases() {
        await loadInitialDatabases();
    }

    async function selectDatabase(dbName) {
        const previousDb = currentDatabase;
        currentDatabase = dbName;
        document.getElementById('currentDatabase').textContent = dbName;
        
        // Update active state in list
        document.querySelectorAll('.database-item').forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('data-db-name') === dbName) {
                item.classList.add('active');
            }
        });
        
        // Load tables
        await loadTables(dbName);
        
        // Add notification only if database actually changed
        if (previousDb !== dbName) {
            addMessage(`Database changed to: ${dbName}`, 'bot');
            addLogMessage(`Switched to database: ${dbName}`, 'info');
        }
    }

    async function loadTables(database) {
        if (!database) return;
        
        const tableList = document.getElementById('tableList');
        tableList.innerHTML = '<div class="loading-indicator">Loading tables...</div>';
        
        addLogMessage(`Loading tables for database: ${database}`, 'info');
        
        try {
            const response = await fetch(`/console/api/tables?database=${encodeURIComponent(database)}&session_id=${sessionId}`);
            const result = await response.json();
            
            if (result.status === 'success' && result.tables) {
                tableList.innerHTML = '';
                
                if (result.tables.length === 0) {
                    tableList.innerHTML = '<div style="color: #666; font-size: 0.85rem;">No tables found</div>';
                    addLogMessage(`No tables found in ${database}`, 'warning');
                    
                    // Show suggestions if available
                    if (result.suggestions) {
                        const suggestionsDiv = document.createElement('div');
                        suggestionsDiv.style.cssText = 'margin-top: 10px; font-size: 0.75rem; color: #94a3b8;';
                        suggestionsDiv.innerHTML = '<strong>Suggestions:</strong><br>' + result.suggestions.join('<br>');
                        tableList.appendChild(suggestionsDiv);
                    }
                } else {
                    addLogMessage(`Found ${result.tables.length} tables in ${database}`, 'success');
                    
                    // Show counts if available
                    if (result.counts) {
                        const countsDiv = document.createElement('div');
                        countsDiv.style.cssText = 'font-size: 0.75rem; color: #94a3b8; margin-bottom: 10px;';
                        countsDiv.innerHTML = `Tables: ${result.counts.tables}, Views: ${result.counts.views}`;
                        tableList.appendChild(countsDiv);
                    }
                    
                    // Group tables by schema
                    const tablesBySchema = {};
                    result.tables.forEach(table => {
                        const parts = table.split('.');
                        const schema = parts.length > 1 ? parts[0] : 'dbo';
                        const tableName = parts.length > 1 ? parts[1] : table;
                        
                        if (!tablesBySchema[schema]) {
                            tablesBySchema[schema] = [];
                        }
                        tablesBySchema[schema].push(tableName);
                    });
                    
                    // Display tables grouped by schema
                    Object.keys(tablesBySchema).sort().forEach(schema => {
                        if (schema !== 'dbo' || Object.keys(tablesBySchema).length > 1) {
                            const schemaHeader = document.createElement('div');
                            schemaHeader.className = 'schema-header';
                            schemaHeader.textContent = schema;
                            schemaHeader.style.cssText = 'font-weight: bold; color: #3b82f6; margin: 10px 0 5px 0; font-size: 0.8rem;';
                            tableList.appendChild(schemaHeader);
                        }
                        
                        tablesBySchema[schema].sort().forEach(tableName => {
                            const tableItem = document.createElement('div');
                            tableItem.className = 'table-item';
                            tableItem.textContent = tableName;
                            tableItem.onclick = () => {
                                const fullName = schema !== 'dbo' ? `${schema}.${tableName}` : tableName;
                                document.getElementById('messageInput').value = `SELECT TOP 10 * FROM ${fullName}`;
                                addLogMessage(`Query template created for table: ${fullName}`, 'info');
                            };
                            tableList.appendChild(tableItem);
                        });
                    });
                    
                    // Show method used if available
                    if (result.method) {
                        const methodDiv = document.createElement('div');
                        methodDiv.style.cssText = 'margin-top: 10px; font-size: 0.75rem; color: #64748b;';
                        methodDiv.textContent = `Method: ${result.method}`;
                        tableList.appendChild(methodDiv);
                    }
                }
            } else {
                tableList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Error loading tables</div>';
                addLogMessage(`Error loading tables: ${result.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            tableList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Connection error</div>';
            addLogMessage(`Connection error loading tables: ${error.message}`, 'error');
        }
    }

    async function getCurrentUser() {
        try {
            const response = await fetch('/console/api/current-user');
            const result = await response.json();
            
            if (result.status === 'success' && result.user) {
                const userElement = document.getElementById('currentUser');
                userElement.textContent = result.user.name || result.user.email || 'Unknown User';
                
                if (result.user.sql_user) {
                    userElement.title = `SQL User: ${result.user.sql_user}\\nAuth: ${result.user.auth_type || 'MSI'}`;
                }
                
                addLogMessage(`Logged in as: ${result.user.name || result.user.sql_user}`, 'info');
            }
        } catch (error) {
            console.error('Error getting current user:', error);
            document.getElementById('currentUser').textContent = 'Authentication error';
        }
    }
    '''