#!/usr/bin/env python3
# sql_console.py - Fixed SQL Console with proper authentication
"""
SQL Assistant Console - Web-based SQL query interface
Fixed version with proper Azure Function authentication
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from aiohttp import web
from aiohttp.web import Request, Response, json_response
import aiohttp

# Configure logging
logger = logging.getLogger(__name__)

class SQLConsole:
    """SQL Console handler with proper authentication"""
    
    def __init__(self, sql_translator=None, bot=None):
        self.sql_translator = sql_translator
        self.bot = bot
        self.sessions = {}
        
        # Get function configuration
        self.function_url = os.environ.get("AZURE_FUNCTION_URL", "")
        self.function_key = os.environ.get("AZURE_FUNCTION_KEY", "")
        
        # Check if authentication is embedded in URL
        self.url_has_auth = "code=" in self.function_url
        
        logger.info(f"SQL Console initialized")
        logger.info(f"Function URL configured: {'Yes' if self.function_url else 'No'}")
        logger.info(f"Authentication method: {'URL-embedded' if self.url_has_auth else 'Header-based'}")
    
    async def console_page(self, request: Request) -> Response:
        """Serve the SQL console HTML page"""
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            height: 100vh;
            overflow: hidden;
        }

        .container {
            display: flex;
            height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 280px;
            background-color: #1e293b;
            border-right: 1px solid #334155;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .sidebar-header {
            padding: 1.5rem;
            border-bottom: 1px solid #334155;
        }

        .sidebar-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 0.5rem;
        }

        .current-db {
            font-size: 0.875rem;
            color: #94a3b8;
        }

        .current-db span {
            color: #3b82f6;
            font-weight: 500;
        }

        /* Database section */
        .database-section {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .section-title {
            font-size: 0.875rem;
            font-weight: 600;
            color: #cbd5e1;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .refresh-button {
            background: none;
            border: none;
            color: #3b82f6;
            cursor: pointer;
            font-size: 0.875rem;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            transition: all 0.2s;
        }

        .refresh-button:hover {
            background-color: #1e3a8a;
            color: #93bbfc;
        }

        .database-list, .table-list {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .database-item, .table-item {
            padding: 0.5rem 0.75rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.875rem;
            color: #e2e8f0;
            transition: all 0.2s;
            position: relative;
        }

        .database-item:hover, .table-item:hover {
            background-color: #334155;
        }

        .database-item.active {
            background-color: #1e3a8a;
            color: #93bbfc;
        }

        .table-item {
            padding-left: 1.5rem;
            color: #94a3b8;
        }

        .table-item:before {
            content: "📊";
            position: absolute;
            left: 0.5rem;
        }

        /* Main content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Header */
        .header {
            background-color: #1e293b;
            border-bottom: 1px solid #334155;
            padding: 1.5rem 2rem;
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .title {
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .quick-actions {
            display: flex;
            gap: 0.5rem;
        }

        .quick-action {
            padding: 0.5rem 1rem;
            background-color: #334155;
            border: 1px solid #475569;
            border-radius: 0.375rem;
            color: #e2e8f0;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .quick-action:hover {
            background-color: #475569;
            border-color: #64748b;
        }

        /* Chat container */
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        /* Messages */
        .message {
            max-width: 80%;
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

        .message.user {
            align-self: flex-end;
        }

        .message.bot {
            align-self: flex-start;
        }

        .message-content {
            padding: 1rem 1.5rem;
            border-radius: 1rem;
            position: relative;
        }

        .message.user .message-content {
            background-color: #3b82f6;
            color: white;
            border-bottom-right-radius: 0.25rem;
        }

        .message.bot .message-content {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-bottom-left-radius: 0.25rem;
        }

        .message-header {
            font-size: 0.75rem;
            color: #94a3b8;
            margin-bottom: 0.5rem;
        }

        .message-text {
            font-size: 0.875rem;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        /* SQL Result */
        .sql-result {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 0.5rem;
            overflow-x: auto;
        }

        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #334155;
        }

        .result-info {
            font-size: 0.75rem;
            color: #94a3b8;
        }

        .result-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }

        .result-table th {
            background-color: #0f172a;
            color: #cbd5e1;
            padding: 0.5rem;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #334155;
        }

        .result-table td {
            padding: 0.5rem;
            border-bottom: 1px solid #1e293b;
            color: #e2e8f0;
        }

        .result-table tr:hover {
            background-color: #334155;
        }

        /* Error message */
        .error-message {
            background-color: #7f1d1d;
            border: 1px solid #991b1b;
            color: #fecaca;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-top: 0.5rem;
        }

        /* Input area */
        .input-area {
            padding: 1.5rem 2rem;
            background-color: #1e293b;
            border-top: 1px solid #334155;
        }

        .input-container {
            display: flex;
            gap: 1rem;
            align-items: flex-end;
        }

        .input-wrapper {
            flex: 1;
            position: relative;
        }

        #messageInput {
            width: 100%;
            padding: 0.75rem 1rem;
            background-color: #0f172a;
            border: 1px solid #334155;
            border-radius: 0.5rem;
            color: #e2e8f0;
            font-size: 0.875rem;
            resize: none;
            min-height: 2.5rem;
            max-height: 8rem;
            font-family: inherit;
            line-height: 1.5;
        }

        #messageInput:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        #messageInput::placeholder {
            color: #64748b;
        }

        .send-button {
            padding: 0.75rem 1.5rem;
            background-color: #3b82f6;
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .send-button:hover:not(:disabled) {
            background-color: #2563eb;
        }

        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Typing indicator */
        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 1rem;
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 1rem;
            border-bottom-left-radius: 0.25rem;
            max-width: 200px;
        }

        .typing-dot {
            width: 8px;
            height: 8px;
            background-color: #64748b;
            border-radius: 50%;
            animation: typing 1.4s infinite ease-in-out;
        }

        .typing-dot:nth-child(1) {
            animation-delay: -0.32s;
        }

        .typing-dot:nth-child(2) {
            animation-delay: -0.16s;
        }

        @keyframes typing {
            0%, 80%, 100% {
                transform: scale(0.8);
                opacity: 0.5;
            }
            40% {
                transform: scale(1);
                opacity: 1;
            }
        }

        /* Loading indicator */
        .loading-indicator {
            text-align: center;
            color: #64748b;
            font-size: 0.875rem;
            padding: 1rem;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #0f172a;
        }

        ::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #475569;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">SQL Explorer</div>
                <div class="current-db">Current: <span id="currentDatabase">master</span></div>
            </div>
            
            <div class="database-section">
                <div class="section-header">
                    <div class="section-title">Databases</div>
                    <button class="refresh-button" onclick="refreshDatabases()">Refresh</button>
                </div>
                <div class="database-list" id="databaseList">
                    <div class="loading-indicator">Loading databases...</div>
                </div>
            </div>
            
            <div class="database-section">
                <div class="section-header">
                    <div class="section-title">Tables</div>
                </div>
                <div class="table-list" id="tableList">
                    <div class="loading-indicator">Select a database</div>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="header">
                <div class="header-content">
                    <h1 class="title">SQL Assistant Console</h1>
                    <div class="quick-actions">
                        <button class="quick-action" onclick="quickCommand('SHOW TABLES')">Show Tables</button>
                        <button class="quick-action" onclick="quickCommand('SHOW DATABASES')">Show Databases</button>
                        <button class="quick-action" onclick="quickCommand('help')">Help</button>
                    </div>
                </div>
            </div>

            <div class="chat-container">
                <div class="messages-container" id="messagesContainer">
                    <!-- Welcome message -->
                    <div class="message bot">
                        <div class="message-content">
                            <div class="message-header">SQL Assistant</div>
                            <div class="message-text">Welcome to SQL Assistant Console! I can help you explore databases and write SQL queries.

Try commands like:
• "Show me all tables"
• "What columns does the users table have?"
• "Find the top 10 customers by order count"

Type 'help' for more information.</div>
                        </div>
                    </div>
                </div>

                <div class="input-area">
                    <div class="input-container">
                        <div class="input-wrapper">
                            <textarea 
                                id="messageInput" 
                                placeholder="Type your SQL query or ask a question..."
                                rows="1"
                                onkeydown="handleKeyPress(event)"
                            ></textarea>
                        </div>
                        <button id="sendButton" class="send-button" onclick="sendMessage()">
                            Send
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
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
                    <div class="message-text">${escapeHtml(result.explanation || '')}</div>
            `;
            
            if (result.sql_query) {
                content += `
                    <div class="sql-result">
                        <div class="result-header">
                            <div class="result-info">
                                Query executed on: ${result.database || currentDatabase}
                            </div>
                            <div class="result-info">
                                ${result.row_count || 0} rows • ${result.execution_time || 0}ms
                            </div>
                        </div>
                        <pre style="color: #94a3b8; margin-bottom: 1rem; font-size: 0.75rem;">${escapeHtml(result.sql_query)}</pre>
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

        function addHelpMessage(content) {
            const messagesContainer = document.getElementById('messagesContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message bot';
            
            const time = new Date().toLocaleTimeString();
            
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="message-header">SQL Assistant • ${time}</div>
                    <div class="message-text">${content}</div>
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
                                document.getElementById('messageInput').value = `DESCRIBE ${table}`;
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
    </script>
</body>
</html>'''
        
        return Response(text=html_content, content_type='text/html')
    
    async def handle_message(self, request: Request) -> Response:
        """Handle incoming console messages with proper error handling"""
        try:
            data = await request.json()
            message = data.get('message', '').strip()
            database = data.get('database', 'master')
            session_id = data.get('session_id')
            
            # Check for special commands
            if message.lower() in ['help', '?']:
                return json_response({
                    'status': 'success',
                    'response_type': 'help',
                    'content': self._get_help_text()
                })
            
            if message.lower() in ['show databases', 'databases']:
                databases = await self._get_databases()
                return json_response({
                    'status': 'success',
                    'response_type': 'text',
                    'content': f"Available databases:\n" + "\n".join(f"• {db}" for db in databases)
                })
            
            # Process SQL query
            if self.sql_translator and self.bot:
                try:
                    # Translate natural language to SQL
                    from sqlquery import SQLQuery
                    
                    # Create translation request
                    sql_result = await self.sql_translator.translate_to_sql(
                        message,
                        database_schema=await self._get_schema_context(database),
                        current_database=database
                    )
                    
                    if not sql_result.query:
                        return json_response({
                            'status': 'error',
                            'error': 'Could not translate to SQL query'
                        })
                    
                    # Execute the query
                    result = await self._execute_sql_query_with_auth(sql_result)
                    
                    if result.get('error'):
                        return json_response({
                            'status': 'error',
                            'error': result['error']
                        })
                    
                    return json_response({
                        'status': 'success',
                        'response_type': 'sql_result',
                        'sql_query': sql_result.query,
                        'database': sql_result.database or database,
                        'explanation': sql_result.explanation,
                        'rows': result.get('rows', []),
                        'row_count': result.get('row_count', 0),
                        'execution_time': result.get('execution_time_ms', 0),
                        'current_database': database
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing query: {e}", exc_info=True)
                    return json_response({
                        'status': 'error',
                        'error': f'Query processing error: {str(e)}'
                    })
            else:
                return json_response({
                    'status': 'error',
                    'error': 'SQL translator not available'
                })
                
        except Exception as e:
            logger.error(f"Console message error: {e}", exc_info=True)
            return json_response({
                'status': 'error',
                'error': str(e)
            })
    
    def _get_help_text(self) -> str:
        """Get help text for console"""
        return """SQL Assistant Console Commands:

**Natural Language Queries:**
• "Show me all customers"
• "What's the total revenue by month?"
• "Find products with low inventory"

**SQL Commands:**
• SELECT, WITH, and other read queries
• Direct SQL syntax supported

**Special Commands:**
• help - Show this help message
• show databases - List all databases
• show tables - List tables in current database

**Tips:**
• Click on a database to switch context
• Click on a table name to describe it
• Use natural language or SQL syntax
• Results are limited to prevent overload"""
    
    async def _get_databases(self) -> List[str]:
        """Get list of databases with proper authentication"""
        try:
            # Call Azure Function with proper auth
            result = await self._call_function_metadata()
            
            if result and 'databases' in result:
                return result['databases']
            else:
                # Fallback to default
                return ['master', 'tempdb', 'model', 'msdb']
                
        except Exception as e:
            logger.error(f"Error getting databases: {e}")
            return ['master']
    
    async def _get_tables(self, database: str) -> List[str]:
        """Get list of tables in database"""
        try:
            if not self.sql_translator or not self.bot:
                return []
            
            # Create a schema query
            from sqlquery import SQLQuery
            schema_query = SQLQuery(
                query=f"""SELECT TABLE_NAME 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE' 
                        ORDER BY TABLE_NAME""",
                database=database,
                explanation="Getting list of tables",
                confidence=1.0
            )
            
            result = await self._execute_sql_query_with_auth(schema_query)
            
            if result.get('rows'):
                return [row['TABLE_NAME'] for row in result['rows']]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            return []
    
    async def _get_schema_context(self, database: str) -> str:
        """Get schema context for translation"""
        try:
            tables = await self._get_tables(database)
            if tables:
                return f"Database: {database}\nTables: {', '.join(tables[:10])}"
            return f"Database: {database}"
        except:
            return f"Database: {database}"
    
    async def _call_function_metadata(self) -> dict:
        """Call Azure Function to get metadata with proper authentication"""
        try:
            if not self.function_url:
                logger.error("Azure Function URL not configured")
                return {'databases': []}
            
            headers = {"Content-Type": "application/json"}
            
            # Add authentication header if not embedded in URL
            if not self.url_has_auth and self.function_key:
                headers["x-functions-key"] = self.function_key
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.function_url,
                    json={"query_type": "metadata"},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Function metadata call failed: {response.status} - {error_text}")
                        return {'databases': []}
                        
        except Exception as e:
            logger.error(f"Error calling function metadata: {e}")
            return {'databases': []}
    
    async def _execute_sql_query_with_auth(self, sql_query) -> dict:
        """Execute SQL query using Azure Function with proper authentication"""
        if not self.function_url:
            return {'error': 'Azure Function URL not configured'}
        
        try:
            headers = {"Content-Type": "application/json"}
            
            # Add authentication header if not embedded in URL
            if not self.url_has_auth and self.function_key:
                headers["x-functions-key"] = self.function_key
            
            payload = {
                "query_type": "single",
                "query": sql_query.query,
                "database": sql_query.database or "master",
                "output_format": "raw"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.function_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Function call failed: {response.status} - {error_text}")
                        
                        # Parse error message for user
                        if response.status == 401:
                            return {'error': 'Authentication failed. Please check Azure Function configuration.'}
                        elif response.status == 400:
                            return {'error': f'Invalid request: {error_text}'}
                        else:
                            return {'error': f'Server error ({response.status}): {error_text[:200]}'}
                            
        except aiohttp.ClientTimeout:
            return {'error': 'Query timeout - please try a simpler query'}
        except Exception as e:
            logger.error(f"Error executing query: {e}", exc_info=True)
            return {'error': f'Connection error: {str(e)}'}
    
    async def get_databases_api(self, request: Request) -> Response:
        """API endpoint to get databases"""
        try:
            databases = await self._get_databases()
            return json_response({
                'status': 'success',
                'databases': databases
            })
        except Exception as e:
            logger.error(f"Database API error: {e}", exc_info=True)
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
            logger.error(f"Tables API error: {e}", exc_info=True)
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
    
    logger.info("SQL Console routes added successfully")
    return console