# sql_console_javascript.py - SQL Console JavaScript
"""
SQL Console JavaScript - Separated for easier management
"""

def get_sql_console_javascript():
    """Return the JavaScript code for the SQL console"""
    return '''
    let currentDatabase = 'master';
    let isProcessing = false;
    let sessionId = generateSessionId();

    // Initialize
    window.onload = async function() {
        await refreshDatabases();
        document.getElementById('messageInput').focus();
        
        // Auto-resize textarea
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
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
        sendMessage();
    }

    async function sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message || isProcessing) return;
        
        isProcessing = true;
        document.getElementById('sendButton').disabled = true;
        
        // Add user message
        addMessage(message, 'user');
        input.value = '';
        input.style.height = 'auto';
        
        // Show typing indicator
        showTypingIndicator();
        
        try {
            const response = await fetch('/console/api/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    database: currentDatabase,
                    session_id: sessionId
                })
            });
            
            const result = await response.json();
            
            hideTypingIndicator();
            
            if (result.status === 'success') {
                // Add bot response
                if (result.response_type === 'sql_result') {
                    addSQLResult(result);
                } else if (result.response_type === 'help') {
                    addMessage(result.content, 'bot');
                } else if (result.response_type === 'error') {
                    addErrorMessage(result.error);
                } else {
                    addMessage(result.content, 'bot');
                }
                
                // Update current database if changed
                if (result.current_database && result.current_database !== currentDatabase) {
                    selectDatabase(result.current_database);
                }
                
                // Refresh tables if needed
                if (result.refresh_tables) {
                    await loadTables(currentDatabase);
                }
            } else {
                addErrorMessage(result.error || 'An error occurred');
            }
        } catch (error) {
            hideTypingIndicator();
            addErrorMessage('Connection error: ' + error.message);
        } finally {
            isProcessing = false;
            document.getElementById('sendButton').disabled = false;
            input.focus();
        }
    }

    function addMessage(text, sender) {
        const messagesContainer = document.getElementById('messagesContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const time = new Date().toLocaleTimeString();
        const header = sender === 'user' ? 'You' : 'SQL Assistant';
        
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
        const databaseList = document.getElementById('databaseList');
        databaseList.innerHTML = '<div class="loading-indicator">Loading databases...</div>';
        
        try {
            const response = await fetch('/console/api/databases');
            const result = await response.json();
            
            if (result.status === 'success' && result.databases) {
                databaseList.innerHTML = '';
                
                result.databases.forEach(db => {
                    const dbItem = document.createElement('div');
                    dbItem.className = 'database-item';
                    if (db === currentDatabase) {
                        dbItem.classList.add('active');
                    }
                    dbItem.textContent = db;
                    dbItem.onclick = () => selectDatabase(db);
                    databaseList.appendChild(dbItem);
                });
                
                if (result.databases.length === 0) {
                    databaseList.innerHTML = '<div style="color: #666; font-size: 0.85rem;">No databases found</div>';
                }
            } else {
                databaseList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Error loading databases</div>';
            }
        } catch (error) {
            databaseList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Connection error</div>';
        }
    }

    async function selectDatabase(dbName) {
        currentDatabase = dbName;
        document.getElementById('currentDatabase').textContent = dbName;
        
        // Update active state in list
        document.querySelectorAll('.database-item').forEach(item => {
            item.classList.remove('active');
            if (item.textContent === dbName) {
                item.classList.add('active');
            }
        });
        
        // Load tables
        await loadTables(dbName);
        
        // Add notification
        addMessage(`Database changed to: ${dbName}`, 'bot');
    }

    async function loadTables(database) {
        if (!database) return;
        
        const tableList = document.getElementById('tableList');
        tableList.innerHTML = '<div class="loading-indicator">Loading tables...</div>';
        
        try {
            const response = await fetch(`/console/api/tables?database=${encodeURIComponent(database)}`);
            const result = await response.json();
            
            if (result.status === 'success' && result.tables) {
                tableList.innerHTML = '';
                
                if (result.tables.length === 0) {
                    tableList.innerHTML = '<div style="color: #666; font-size: 0.85rem;">No tables found</div>';
                } else {
                    result.tables.forEach(table => {
                        const tableItem = document.createElement('div');
                        tableItem.className = 'table-item';
                        tableItem.textContent = table;
                        tableItem.onclick = () => {
                            document.getElementById('messageInput').value = `SELECT TOP 10 * FROM ${table}`;
                        };
                        tableList.appendChild(tableItem);
                    });
                }
            } else {
                tableList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Error loading tables</div>';
            }
        } catch (error) {
            tableList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Connection error</div>';
        }
    }
    '''
    '''