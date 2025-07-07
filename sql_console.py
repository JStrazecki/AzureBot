# sql_console.py - Standalone SQL Console for SQL Assistant Bot
"""
Web-based SQL Console that provides full bot functionality in a browser
Access at: /console
"""

import json
from datetime import datetime
from aiohttp.web import Request, Response
import logging

logger = logging.getLogger(__name__)

class SQLConsole:
    """Web-based SQL console with full bot functionality"""
    
    def __init__(self, sql_translator=None, bot=None):
        self.sql_translator = sql_translator
        self.bot = bot
        self.sessions = {}  # Store session data
    
    async def console_page(self, request: Request) -> Response:
        """Serve the SQL console page"""
        
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant Console</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .console-header {
            background: #1a1a1a;
            padding: 15px 20px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .console-title {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .console-title h1 {
            font-size: 1.5rem;
            color: #667eea;
            font-weight: 600;
        }

        .status-indicator {
            width: 10px;
            height: 10px;
            background: #10b981;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .console-info {
            display: flex;
            gap: 20px;
            font-size: 0.9rem;
            color: #888;
        }

        .info-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .info-item strong {
            color: #667eea;
        }

        .console-container {
            flex: 1;
            display: flex;
            overflow: hidden;
        }

        .sidebar {
            width: 250px;
            background: #1a1a1a;
            border-right: 1px solid #333;
            display: flex;
            flex-direction: column;
        }

        .sidebar-section {
            border-bottom: 1px solid #333;
            padding: 15px;
        }

        .sidebar-section h3 {
            font-size: 0.85rem;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 10px;
            letter-spacing: 0.5px;
        }

        .database-selector {
            width: 100%;
            background: #2a2a2a;
            border: 1px solid #444;
            color: #e0e0e0;
            padding: 8px;
            border-radius: 4px;
            font-size: 0.9rem;
        }

        .database-list {
            max-height: 200px;
            overflow-y: auto;
        }

        .database-item {
            padding: 8px;
            cursor: pointer;
            border-radius: 4px;
            font-size: 0.9rem;
            transition: background 0.2s;
        }

        .database-item:hover {
            background: #2a2a2a;
        }

        .database-item.active {
            background: #667eea;
            color: white;
        }

        .table-list {
            max-height: 300px;
            overflow-y: auto;
        }

        .table-item {
            padding: 8px;
            cursor: pointer;
            border-radius: 4px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: background 0.2s;
        }

        .table-item:hover {
            background: #2a2a2a;
        }

        .table-icon {
            color: #667eea;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #0a0a0a;
        }

        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .message {
            max-width: 80%;
            animation: fadeIn 0.3s ease-in;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
        }

        .message.bot {
            align-self: flex-start;
        }

        .message-content {
            padding: 12px 16px;
            border-radius: 12px;
            position: relative;
        }

        .message.user .message-content {
            background: #667eea;
            color: white;
            border-bottom-right-radius: 4px;
        }

        .message.bot .message-content {
            background: #1a1a1a;
            border: 1px solid #333;
            border-bottom-left-radius: 4px;
        }

        .message-header {
            font-size: 0.75rem;
            margin-bottom: 5px;
            opacity: 0.7;
        }

        .message-text {
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .message-time {
            font-size: 0.7rem;
            opacity: 0.5;
            margin-top: 5px;
        }

        .sql-result {
            margin-top: 10px;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 8px;
            overflow: hidden;
        }

        .result-header {
            background: #1a1a1a;
            padding: 10px 15px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .result-stats {
            font-size: 0.85rem;
            color: #888;
        }

        .result-table {
            overflow-x: auto;
            max-height: 400px;
            overflow-y: auto;
        }

        .result-table table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        .result-table th {
            background: #1a1a1a;
            color: #667eea;
            padding: 10px;
            text-align: left;
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 2px solid #333;
        }

        .result-table td {
            padding: 8px 10px;
            border-bottom: 1px solid #222;
        }

        .result-table tr:hover {
            background: #1a1a1a;
        }

        .code-block {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 12px;
            margin: 10px 0;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
            overflow-x: auto;
        }

        .code-block pre {
            margin: 0;
            color: #e0e0e0;
        }

        .input-container {
            background: #1a1a1a;
            border-top: 1px solid #333;
            padding: 20px;
        }

        .input-wrapper {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }

        .input-field {
            flex: 1;
            background: #0a0a0a;
            border: 1px solid #444;
            color: #e0e0e0;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 0.95rem;
            font-family: inherit;
            resize: none;
            min-height: 50px;
            max-height: 150px;
        }

        .input-field:focus {
            outline: none;
            border-color: #667eea;
            background: #0f0f0f;
        }

        .send-button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .send-button:hover {
            background: #5a67d8;
            transform: translateY(-1px);
        }

        .send-button:active {
            transform: translateY(0);
        }

        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .quick-commands {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .quick-command {
            background: #2a2a2a;
            border: 1px solid #444;
            color: #e0e0e0;
            padding: 6px 12px;
            border-radius: 16px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .quick-command:hover {
            background: #667eea;
            border-color: #667eea;
            color: white;
        }

        .loading-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #888;
            font-size: 0.9rem;
            padding: 10px;
        }

        .typing-dots {
            display: flex;
            gap: 4px;
        }

        .typing-dot {
            width: 8px;
            height: 8px;
            background: #667eea;
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }

        .typing-dot:nth-child(2) {
            animation-delay: 0.2s;
        }

        .typing-dot:nth-child(3) {
            animation-delay: 0.4s;
        }

        @keyframes typing {
            0%, 60%, 100% {
                opacity: 0.3;
                transform: scale(0.8);
            }
            30% {
                opacity: 1;
                transform: scale(1);
            }
        }

        .error-message {
            background: #dc2626;
            color: white;
            padding: 10px 15px;
            border-radius: 6px;
            margin: 10px 0;
        }

        .success-message {
            background: #10b981;
            color: white;
            padding: 10px 15px;
            border-radius: 6px;
            margin: 10px 0;
        }

        .help-panel {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }

        .help-panel h4 {
            color: #667eea;
            margin-bottom: 10px;
        }

        .help-panel ul {
            list-style: none;
            padding-left: 0;
        }

        .help-panel li {
            padding: 5px 0;
            color: #ccc;
        }

        .help-panel code {
            background: #2a2a2a;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.85rem;
            color: #667eea;
        }

        @media (max-width: 768px) {
            .sidebar {
                display: none;
            }
            
            .message {
                max-width: 95%;
            }
        }
    </style>
</head>
<body>
    <div class="console-header">
        <div class="console-title">
            <div class="status-indicator"></div>
            <h1>SQL Assistant Console</h1>
        </div>
        <div class="console-info">
            <div class="info-item">
                <strong>Database:</strong>
                <span id="currentDatabase">Not selected</span>
            </div>
            <div class="info-item">
                <strong>Status:</strong>
                <span id="connectionStatus">Connected</span>
            </div>
            <div class="info-item">
                <strong>Mode:</strong>
                <span>Natural Language</span>
            </div>
        </div>
    </div>

    <div class="console-container">
        <div class="sidebar">
            <div class="sidebar-section">
                <h3>Databases</h3>
                <button class="quick-command" onclick="refreshDatabases()" style="width: 100%; margin-bottom: 10px;">
                    🔄 Refresh Databases
                </button>
                <div class="database-list" id="databaseList">
                    <div class="loading-indicator">Loading databases...</div>
                </div>
            </div>
            
            <div class="sidebar-section">
                <h3>Tables</h3>
                <div class="table-list" id="tableList">
                    <div style="color: #666; font-size: 0.85rem;">Select a database first</div>
                </div>
            </div>
            
            <div class="sidebar-section">
                <h3>Quick Actions</h3>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button class="quick-command" onclick="showHelp()" style="width: 100%;">
                        ❓ Help
                    </button>
                    <button class="quick-command" onclick="showUsage()" style="width: 100%;">
                        📊 Usage Stats
                    </button>
                    <button class="quick-command" onclick="clearChat()" style="width: 100%;">
                        🗑️ Clear Chat
                    </button>
                </div>
            </div>
        </div>

        <div class="main-content">
            <div class="chat-container">
                <div class="messages-container" id="messagesContainer">
                    <div class="message bot">
                        <div class="message-content">
                            <div class="message-header">SQL Assistant</div>
                            <div class="message-text">Welcome to SQL Assistant Console! 🚀

I can help you query your databases using natural language. Just type your question and I'll translate it to SQL and execute it for you.

Try:
- "Show me all tables"
- "How many records are in each table?"
- "What are the top 10 customers by revenue?"

Select a database from the sidebar to get started!</div>
                            <div class="message-time">${new Date().toLocaleTimeString()}</div>
                        </div>
                    </div>
                </div>

                <div class="input-container">
                    <div class="input-wrapper">
                        <textarea 
                            id="messageInput" 
                            class="input-field" 
                            placeholder="Ask a question or type a command..."
                            onkeydown="handleKeyPress(event)"
                        ></textarea>
                        <button id="sendButton" class="send-button" onclick="sendMessage()">
                            <span>Send</span>
                            <span>→</span>
                        </button>
                    </div>
                    <div class="quick-commands">
                        <div class="quick-command" onclick="quickCommand('/help')">Help</div>
                        <div class="quick-command" onclick="quickCommand('/tables')">Show Tables</div>
                        <div class="quick-command" onclick="quickCommand('/usage')">Usage</div>
                        <div class="quick-command" onclick="quickCommand('show me sample data')">Sample Data</div>
                        <div class="quick-command" onclick="quickCommand('/explore')">Deep Explore</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentDatabase = null;
        let sessionId = generateSessionId();
        let isProcessing = false;

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
                        addHelpMessage(result.content);
                    } else {
                        addMessage(result.content, 'bot');
                    }
                    
                    // Update current database if changed
                    if (result.current_database) {
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
                    <div class="message-header">${header}</div>
                    <div class="message-text">${escapeHtml(text)}</div>
                    <div class="message-time">${time}</div>
                </div>
            `;
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function addSQLResult(result) {
            const messagesContainer = document.getElementById('messagesContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message bot';
            
            let content = `
                <div class="message-content">
                    <div class="message-header">SQL Assistant</div>
                    <div class="message-text">${escapeHtml(result.explanation || '')}</div>
            `;
            
            // Add SQL query
            if (result.query) {
                content += `
                    <div class="code-block">
                        <pre>${escapeHtml(result.query)}</pre>
                    </div>
                `;
            }
            
            // Add results table
            if (result.rows && result.rows.length > 0) {
                content += `
                    <div class="sql-result">
                        <div class="result-header">
                            <span>Query Results</span>
                            <span class="result-stats">${result.row_count} rows • ${result.execution_time_ms || 0}ms</span>
                        </div>
                        <div class="result-table">
                            <table>
                                <thead>
                                    <tr>
                                        ${Object.keys(result.rows[0]).map(col => 
                                            `<th>${escapeHtml(col)}</th>`
                                        ).join('')}
                                    </tr>
                                </thead>
                                <tbody>
                                    ${result.rows.slice(0, 100).map(row => `
                                        <tr>
                                            ${Object.values(row).map(val => 
                                                `<td>${escapeHtml(String(val ?? 'NULL'))}</td>`
                                            ).join('')}
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
                
                if (result.row_count > 100) {
                    content += `<div style="color: #888; font-size: 0.85rem; margin-top: 10px;">Showing first 100 of ${result.row_count} rows</div>`;
                }
            } else if (result.content) {
                content += `<div class="message-text">${escapeHtml(result.content)}</div>`;
            }
            
            content += `
                    <div class="message-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            
            messageDiv.innerHTML = content;
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function addHelpMessage(content) {
            const messagesContainer = document.getElementById('messagesContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message bot';
            
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="message-header">SQL Assistant</div>
                    <div class="help-panel">
                        <h4>Available Commands</h4>
                        <ul>
                            <li><code>/help</code> - Show this help message</li>
                            <li><code>/database list</code> - List all databases</li>
                            <li><code>/database set &lt;name&gt;</code> - Set current database</li>
                            <li><code>/tables</code> - Show tables in current database</li>
                            <li><code>/usage</code> - View token usage and costs</li>
                            <li><code>/explore &lt;question&gt;</code> - Deep exploration mode</li>
                            <li><code>/clear</code> - Clear conversation history</li>
                        </ul>
                        
                        <h4 style="margin-top: 15px;">Natural Language Examples</h4>
                        <ul>
                            <li>"Show me all customers"</li>
                            <li>"What are the top 10 products by sales?"</li>
                            <li>"How many orders were placed this month?"</li>
                            <li>"List employees with salary above 50000"</li>
                        </ul>
                    </div>
                    <div class="message-time">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function addErrorMessage(error) {
            const messagesContainer = document.getElementById('messagesContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message bot';
            
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="message-header">SQL Assistant</div>
                    <div class="error-message">❌ ${escapeHtml(error)}</div>
                    <div class="message-time">${new Date().toLocaleTimeString()}</div>
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
                <div class="message-content">
                    <div class="loading-indicator">
                        <div class="typing-dots">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                        <span>SQL Assistant is thinking...</span>
                    </div>
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
                    
                    result.tables.forEach(table => {
                        const tableItem = document.createElement('div');
                        tableItem.className = 'table-item';
                        tableItem.innerHTML = `
                            <span class="table-icon">📊</span>
                            <span>${table}</span>
                        `;
                        tableItem.onclick = () => quickCommand(`show me data from ${table}`);
                        tableList.appendChild(tableItem);
                    });
                    
                    if (result.tables.length === 0) {
                        tableList.innerHTML = '<div style="color: #666; font-size: 0.85rem;">No tables found</div>';
                    }
                } else {
                    tableList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Error loading tables</div>';
                }
            } catch (error) {
                tableList.innerHTML = '<div style="color: #dc2626; font-size: 0.85rem;">Connection error</div>';
            }
        }

        function clearChat() {
            const messagesContainer = document.getElementById('messagesContainer');
            messagesContainer.innerHTML = `
                <div class="message bot">
                    <div class="message-content">
                        <div class="message-header">SQL Assistant</div>
                        <div class="message-text">Chat cleared. Ready for new queries!</div>
                        <div class="message-time">${new Date().toLocaleTimeString()}</div>
                    </div>
                </div>
            `;
        }

        function showHelp() {
            quickCommand('/help');
        }

        function showUsage() {
            quickCommand('/usage');
        }

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {
            refreshDatabases();
            document.getElementById('messageInput').focus();
        });

        // Handle window resize
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                const messagesContainer = document.getElementById('messagesContainer');
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }, 100);
        });
    </script>
</body>
</html>'''
        
        return Response(text=html_content, content_type='text/html')
    
    async def handle_message(self, request: Request) -> Response:
        """Handle console messages with full bot functionality"""
        try:
            data = await request.json()
            message = data.get('message', '')
            database = data.get('database')
            session_id = data.get('session_id', 'default')
            
            # Create or get session
            if session_id not in self.sessions:
                from azure_openai_sql_translator import ConversationContext
                self.sessions[session_id] = {
                    'context': ConversationContext(messages=[]),
                    'current_database': database
                }
            
            session = self.sessions[session_id]
            context = session['context']
            
            # Update current database
            if database:
                context.current_database = database
                session['current_database'] = database
            
            # Process commands
            if message.startswith('/'):
                return await self._handle_command(message, session)
            
            # Process natural language query
            if not self.sql_translator:
                return json_response({
                    'status': 'error',
                    'error': 'SQL translator not available'
                })
            
            # Translate to SQL
            sql_query = self.sql_translator.translate_to_sql(message, context)
            
            if not sql_query.query:
                return json_response({
                    'status': 'success',
                    'response_type': 'text',
                    'content': sql_query.explanation or "I couldn't translate that to SQL. Could you rephrase?"
                })
            
            # Execute query
            result = await self._execute_sql_query(sql_query)
            
            if result.get('error'):
                return json_response({
                    'status': 'error',
                    'error': result['error']
                })
            
            # Format response
            response = {
                'status': 'success',
                'response_type': 'sql_result',
                'explanation': sql_query.explanation,
                'query': sql_query.query,
                'database': sql_query.database,
                'rows': result.get('rows', []),
                'row_count': result.get('row_count', 0),
                'execution_time_ms': result.get('execution_time_ms', 0),
                'current_database': context.current_database
            }
            
            # Add natural language explanation if available
            if 'formatted_result' in result and result['formatted_result']:
                response['content'] = result['formatted_result'].get('natural_language', '')
            
            return json_response(response)
            
        except Exception as e:
            logger.error(f"Console message error: {e}", exc_info=True)
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def _handle_command(self, command: str, session: dict) -> Response:
        """Handle console commands"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/help':
            return json_response({
                'status': 'success',
                'response_type': 'help',
                'content': 'Help content'
            })
        
        elif cmd == '/database':
            if len(parts) > 1 and parts[1] == 'list':
                databases = await self._get_databases()
                content = f"Available Databases ({len(databases)}):\n"
                for db in databases:
                    content += f"• {db}\n"
                return json_response({
                    'status': 'success',
                    'response_type': 'text',
                    'content': content
                })
            
            elif len(parts) > 2 and parts[1] == 'set':
                db_name = ' '.join(parts[2:])
                session['current_database'] = db_name
                session['context'].current_database = db_name
                return json_response({
                    'status': 'success',
                    'response_type': 'text',
                    'content': f'Database set to: {db_name}',
                    'current_database': db_name,
                    'refresh_tables': True
                })
        
        elif cmd == '/tables':
            if not session.get('current_database'):
                return json_response({
                    'status': 'success',
                    'response_type': 'text',
                    'content': 'Please select a database first using: /database set <name>'
                })
            
            # Get tables for current database
            tables = await self._get_tables(session['current_database'])
            content = f"Tables in {session['current_database']} ({len(tables)}):\n"
            for table in tables:
                content += f"• {table}\n"
            return json_response({
                'status': 'success',
                'response_type': 'text',
                'content': content
            })
        
        elif cmd == '/usage':
            if self.sql_translator and hasattr(self.sql_translator, 'token_limiter'):
                usage = self.sql_translator.token_limiter.get_usage_summary()
                content = f"Token Usage:\n"
                content += f"Daily: {usage['daily']['used']:,} / {usage['daily']['limit']:,} ({usage['daily']['percentage']:.1f}%)\n"
                content += f"Cost: ${usage['daily']['cost']:.3f}\n"
                content += f"Remaining: {usage['daily']['remaining']:,} tokens"
            else:
                content = "Usage tracking not available"
            
            return json_response({
                'status': 'success',
                'response_type': 'text',
                'content': content
            })
        
        elif cmd == '/clear':
            from azure_openai_sql_translator import ConversationContext
            session['context'] = ConversationContext(messages=[])
            return json_response({
                'status': 'success',
                'response_type': 'text',
                'content': 'Conversation history cleared.'
            })
        
        else:
            return json_response({
                'status': 'success',
                'response_type': 'text',
                'content': f'Unknown command: {cmd}'
            })
    
    async def _get_databases(self) -> list:
        """Get list of databases"""
        if not self.bot:
            return []
        
        try:
            from azure_openai_sql_translator import SQLQuery
            
            # Create a metadata query
            metadata_query = SQLQuery(
                query="SELECT name FROM sys.databases WHERE state = 0 AND name NOT IN ('master', 'tempdb', 'model', 'msdb')",
                database="master",
                explanation="Getting list of databases",
                confidence=1.0
            )
            
            result = await self.bot._execute_sql_query(metadata_query, "raw")
            
            if result.get('rows'):
                # First try master database to see all databases
                databases = [row['name'] for row in result['rows']]
                databases.insert(0, 'master')  # Add master at the beginning
                return databases
            else:
                # Fallback: use function metadata endpoint
                function_result = await self._call_function_metadata()
                return function_result.get('databases', [])
                
        except Exception as e:
            logger.error(f"Error getting databases: {e}")
            return []
    
    async def _get_tables(self, database: str) -> list:
        """Get list of tables for a database"""
        if not self.bot:
            return []
        
        try:
            from azure_openai_sql_translator import SQLQuery
            
            # Create a schema query
            schema_query = SQLQuery(
                query="""SELECT TABLE_NAME 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE' 
                        ORDER BY TABLE_NAME""",
                database=database,
                explanation="Getting list of tables",
                confidence=1.0
            )
            
            result = await self.bot._execute_sql_query(schema_query, "raw")
            
            if result.get('rows'):
                return [row['TABLE_NAME'] for row in result['rows']]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            return []
    
    async def _call_function_metadata(self) -> dict:
        """Call Azure Function to get metadata"""
        try:
            import aiohttp
            function_url = os.environ.get("AZURE_FUNCTION_URL", "")
            
            if not function_url:
                return {'databases': []}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    function_url,
                    json={"query_type": "metadata"},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {'databases': []}
                        
        except Exception as e:
            logger.error(f"Error calling function metadata: {e}")
            return {'databases': []}
    
    async def _execute_sql_query(self, sql_query) -> dict:
        """Execute SQL query using bot's executor"""
        if not self.bot:
            return {'error': 'Bot not available'}
        
        try:
            return await self.bot._execute_sql_query(sql_query, "full")
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return {'error': str(e)}
    
    async def get_databases_api(self, request: Request) -> Response:
        """API endpoint to get databases"""
        try:
            databases = await self._get_databases()
            return json_response({
                'status': 'success',
                'databases': databases
            })
        except Exception as e:
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    async def get_tables_api(self, request: Request) -> Response:
        """API endpoint to get tables"""
        try:
            database = request.query.get('database')
            if not database:
                return json_response({
                    'status': 'error',
                    'error': 'Database parameter required'
                })
            
            tables = await self._get_tables(database)
            return json_response({
                'status': 'success',
                'tables': tables
            })
        except Exception as e:
            return json_response({
                'status': 'error',
                'error': str(e)
            })


def add_console_routes(app, sql_translator=None, bot=None):
    """Add SQL console routes to the main app"""
    
    console = SQLConsole(sql_translator, bot)
    
    # Console UI
    app.router.add_get('/console', console.console_page)
    app.router.add_get('/console/', console.console_page)
    
    # Console API endpoints
    app.router.add_post('/console/api/message', console.handle_message)
    app.router.add_get('/console/api/databases', console.get_databases_api)
    app.router.add_get('/console/api/tables', console.get_tables_api)
    
    return console