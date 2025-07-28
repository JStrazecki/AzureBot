# sql_console_html.py - Enhanced SQL Console HTML
"""
SQL Console HTML - Enhanced with standardization buttons and copy logs
"""

from sql_console_ui import get_sql_console_css
from sql_console_javascript import get_sql_console_javascript

def get_sql_console_html():
    """Generate the enhanced SQL console HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant Console - Database Standardization</title>
    <style>
        {get_sql_console_css()}
        
        /* Additional styles for enhanced features */
        .cancel-button {{
            display: none;
            padding: 0.75rem 1.5rem;
            background-color: #ef4444;
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
        }}
        
        .cancel-button:hover {{
            background-color: #dc2626;
        }}
        
        .spinner {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Log message styles */
        .log-message .message-content {{
            border-left: 3px solid;
            background-color: rgba(30, 41, 59, 0.5) !important;
        }}
        
        /* Schema header in table list */
        .schema-header {{
            font-weight: bold;
            color: #3b82f6;
            margin: 10px 0 5px 0;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        /* Database icons */
        .db-icon {{
            margin-right: 0.5rem;
            font-size: 1.1rem;
        }}
        
        /* Copy logs button */
        .copy-logs-btn {{
            padding: 0.5rem 1rem;
            background-color: #6366f1;
            border: 1px solid #4f46e5;
            color: white;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            margin-left: 0.5rem;
        }}
        
        .copy-logs-btn:hover {{
            background-color: #4f46e5;
            border-color: #4338ca;
        }}
        
        /* Enhanced result styles */
        .db-result-section {{
            background-color: rgba(30, 41, 59, 0.5);
            border: 1px solid #334155;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        
        .comparison-results {{
            background-color: #0f172a;
            border-radius: 0.375rem;
            padding: 1rem;
            margin-top: 1rem;
        }}
        
        /* Analysis result styles */
        .analysis-section {{
            background-color: rgba(99, 102, 241, 0.1);
            border: 1px solid #6366f1;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">SQL Explorer</div>
                <div class="current-db">Current: <span id="currentDatabase">demo</span></div>
                <div class="user-info">
                    <div class="user-label">Logged in as:</div>
                    <div class="user-name" id="currentUser">Loading...</div>
                </div>
            </div>
            
            <div class="database-section">
                <div class="section-header">
                    <div class="section-title">Databases</div>
                    <button class="refresh-button" onclick="refreshDatabases()">Refresh</button>
                </div>
                
                <!-- Multi-database query toggle -->
                <div class="multi-db-toggle">
                    <label class="toggle-container">
                        <input type="checkbox" id="multiDbMode" onchange="toggleMultiDbMode()">
                        <span class="toggle-label">Multi-Database Mode</span>
                    </label>
                    <button id="selectAllDbBtn" class="select-all-btn" style="display: none;" onclick="toggleAllDatabases()">
                        Select All
                    </button>
                </div>
                
                <div class="database-list" id="databaseList">
                    <!-- Will be populated dynamically -->
                </div>
                
                <!-- Selected databases indicator -->
                <div id="selectedDbIndicator" class="selected-db-indicator" style="display: none;">
                    <div class="selected-count">0 databases selected</div>
                </div>
            </div>
            
            <div class="database-section">
                <div class="section-header">
                    <div class="section-title">Tables & Views</div>
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
                        <button class="quick-action" onclick="quickCommand('COMPARE SCHEMAS')">Compare Schemas</button>
                        <button class="quick-action" onclick="quickCommand('check standardization')">Check Standards</button>
                        <button class="quick-action" onclick="quickCommand('sp_tables')">List Tables</button>
                        <button class="quick-action" onclick="quickCommand('help')">Help</button>
                        <button class="copy-logs-btn" onclick="copyLogs()">📋 Copy Logs</button>
                        <button class="copy-logs-btn" onclick="exportLogs()">💾 Export Logs</button>
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
                            <div class="message-text">Welcome to SQL Assistant Console - Database Standardization Tool!

<strong>Purpose:</strong> Help standardize database schemas across different systems and perform compliance checks.

<strong>Available Databases:</strong>
• _support - Support database  
• demo - Demo database with standardized schemas

<strong>Standard Schemas:</strong>
• acc - Accounting/Financial data
• inv - Inventory management
• hr - Human resources
• crm - Customer relationship management

<strong>Key Features:</strong>
• <strong>Multi-Database Mode:</strong> Compare schemas across databases
• <strong>Schema Comparison:</strong> Check column differences between systems
• <strong>Standardization Checks:</strong> Verify compliance with standards
• <strong>AI Analysis:</strong> Get insights from query results

<strong>Try these commands:</strong>
• "Compare columns in AD table across all databases"
• "Check standardization of accounting views"
• "Show differences in customer tables"
• "List all views in acc schema"

Type 'help' for detailed information.

<strong>💡 Tip:</strong> Enable Multi-Database Mode to compare across systems!</div>
                        </div>
                    </div>
                </div>

                <div class="input-area">
                    <!-- Multi-database indicator -->
                    <div id="multiDbIndicator" class="multi-db-indicator" style="display: none;">
                        <span class="indicator-icon">🗄️</span>
                        <span class="indicator-text">Multi-database mode: <span id="selectedDbCount">0</span> databases selected</span>
                    </div>
                    
                    <div class="input-container">
                        <div class="input-wrapper">
                            <textarea 
                                id="messageInput" 
                                placeholder="Ask about schema differences, run standardization checks, or type SQL queries..."
                                rows="1"
                                onkeydown="handleKeyPress(event)"
                            ></textarea>
                        </div>
                        <button id="sendButton" class="send-button" onclick="sendMessage()">
                            Send
                        </button>
                        <button id="cancelButton" class="cancel-button" onclick="cancelRequest()">
                            Cancel
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
</html>'''# sql_console_html.py - Enhanced SQL Console HTML
"""
SQL Console HTML - Enhanced with standardization buttons and copy logs
"""

from sql_console_ui import get_sql_console_css
from sql_console_javascript import get_sql_console_javascript

def get_sql_console_html():
    """Generate the enhanced SQL console HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL Assistant Console - Database Standardization</title>
    <style>
        {get_sql_console_css()}
        
        /* Additional styles for enhanced features */
        .cancel-button {{
            display: none;
            padding: 0.75rem 1.5rem;
            background-color: #ef4444;
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
        }}
        
        .cancel-button:hover {{
            background-color: #dc2626;
        }}
        
        .spinner {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Log message styles */
        .log-message .message-content {{
            border-left: 3px solid;
            background-color: rgba(30, 41, 59, 0.5) !important;
        }}
        
        /* Schema header in table list */
        .schema-header {{
            font-weight: bold;
            color: #3b82f6;
            margin: 10px 0 5px 0;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        /* Database icons */
        .db-icon {{
            margin-right: 0.5rem;
            font-size: 1.1rem;
        }}
        
        /* Copy logs button */
        .copy-logs-btn {{
            padding: 0.5rem 1rem;
            background-color: #6366f1;
            border: 1px solid #4f46e5;
            color: white;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            margin-left: 0.5rem;
        }}
        
        .copy-logs-btn:hover {{
            background-color: #4f46e5;
            border-color: #4338ca;
        }}
        
        /* Enhanced result styles */
        .db-result-section {{
            background-color: rgba(30, 41, 59, 0.5);
            border: 1px solid #334155;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        
        .comparison-results {{
            background-color: #0f172a;
            border-radius: 0.375rem;
            padding: 1rem;
            margin-top: 1rem;
        }}
        
        /* Analysis result styles */
        .analysis-section {{
            background-color: rgba(99, 102, 241, 0.1);
            border: 1px solid #6366f1;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">SQL Explorer</div>
                <div class="current-db">Current: <span id="currentDatabase">demo</span></div>
                <div class="user-info">
                    <div class="user-label">Logged in as:</div>
                    <div class="user-name" id="currentUser">Loading...</div>
                </div>
            </div>
            
            <div class="database-section">
                <div class="section-header">
                    <div class="section-title">Databases</div>
                    <button class="refresh-button" onclick="refreshDatabases()">Refresh</button>
                </div>
                
                <!-- Multi-database query toggle -->
                <div class="multi-db-toggle">
                    <label class="toggle-container">
                        <input type="checkbox" id="multiDbMode" onchange="toggleMultiDbMode()">
                        <span class="toggle-label">Multi-Database Mode</span>
                    </label>
                    <button id="selectAllDbBtn" class="select-all-btn" style="display: none;" onclick="toggleAllDatabases()">
                        Select All
                    </button>
                </div>
                
                <div class="database-list" id="databaseList">
                    <!-- Will be populated dynamically -->
                </div>
                
                <!-- Selected databases indicator -->
                <div id="selectedDbIndicator" class="selected-db-indicator" style="display: none;">
                    <div class="selected-count">0 databases selected</div>
                </div>
            </div>
            
            <div class="database-section">
                <div class="section-header">
                    <div class="section-title">Tables & Views</div>
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
                        <button class="quick-action" onclick="quickCommand('COMPARE SCHEMAS')">Compare Schemas</button>
                        <button class="quick-action" onclick="quickCommand('check standardization')">Check Standards</button>
                        <button class="quick-action" onclick="quickCommand('sp_tables')">List Tables</button>
                        <button class="quick-action" onclick="quickCommand('help')">Help</button>
                        <button class="copy-logs-btn" onclick="copyLogs()">📋 Copy Logs</button>
                        <button class="copy-logs-btn" onclick="exportLogs()">💾 Export Logs</button>
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
                            <div class="message-text">Welcome to SQL Assistant Console - Database Standardization Tool!

<strong>Purpose:</strong> Help standardize database schemas across different systems and perform compliance checks.

<strong>Available Databases:</strong>
• _support - Support database  
• demo - Demo database with standardized schemas

<strong>Standard Schemas:</strong>
• acc - Accounting/Financial data
• inv - Inventory management
• hr - Human resources
• crm - Customer relationship management

<strong>Key Features:</strong>
• <strong>Multi-Database Mode:</strong> Compare schemas across databases
• <strong>Schema Comparison:</strong> Check column differences between systems
• <strong>Standardization Checks:</strong> Verify compliance with standards
• <strong>AI Analysis:</strong> Get insights from query results

<strong>Try these commands:</strong>
• "Compare columns in AD table across all databases"
• "Check standardization of accounting views"
• "Show differences in customer tables"
• "List all views in acc schema"

Type 'help' for detailed information.

<strong>💡 Tip:</strong> Enable Multi-Database Mode to compare across systems!</div>
                        </div>
                    </div>
                </div>

                <div class="input-area">
                    <!-- Multi-database indicator -->
                    <div id="multiDbIndicator" class="multi-db-indicator" style="display: none;">
                        <span class="indicator-icon">🗄️</span>
                        <span class="indicator-text">Multi-database mode: <span id="selectedDbCount">0</span> databases selected</span>
                    </div>
                    
                    <div class="input-container">
                        <div class="input-wrapper">
                            <textarea 
                                id="messageInput" 
                                placeholder="Ask about schema differences, run standardization checks, or type SQL queries..."
                                rows="1"
                                onkeydown="handleKeyPress(event)"
                            ></textarea>
                        </div>
                        <button id="sendButton" class="send-button" onclick="sendMessage()">
                            Send
                        </button>
                        <button id="cancelButton" class="cancel-button" onclick="cancelRequest()">
                            Cancel
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