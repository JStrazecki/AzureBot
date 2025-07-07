# sql_console_html.py - SQL Console HTML Generation
"""
SQL Console HTML - Combined UI components to generate full HTML
"""

from sql_console_ui import get_sql_console_css
from sql_console_javascript import get_sql_console_javascript

def get_sql_console_html():
    """Generate the complete SQL console HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant Console</title>
    <style>
        {get_sql_console_css()}
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
                        <button class="quick-action" onclick="quickCommand('SELECT TOP 10 * FROM ')">Select Top 10</button>
                        <button class="quick-action" onclick="quickCommand('SHOW TABLES')">Show Tables</button>
                        <button class="quick-action" onclick="quickCommand('help')">Help</button>
                        <a href="/admin" class="quick-action" style="text-decoration: none;">Admin</a>
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
• Direct SQL queries: SELECT, WITH, etc.

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
        {get_sql_console_javascript()}
    </script>
</body>
</html>'''