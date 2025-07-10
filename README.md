# SQL Assistant Bot -  Documentation


## 🏗️ Architecture Overview

CURRENT FLOW (What's Active):
'''
┌────────────────────┐
│ User Question      │
│ "Show Databases"   │
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ sql_translator_    │      ┌─────────────────┐
│ simple.py          │─────▶│ Azure OpenAI    │
│                    │◀─────│ Returns SQL     │
└─────────┬──────────┘      └─────────────────┘
          ▼
┌────────────────────┐
│ Azure Function     │
│ Executes SQL       │
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ result_formatter.py│
│ Basic formatting   │
│ (No AI analysis)   │
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Console displays   │
│ raw results        │
└────────────────────┘
'''

## 📁 Project Structure


sql-assistant/
├── app.py                                  # Main application entry point
├── requirements.txt                        # Python dependencies
├── startup.sh                              # Azure App Service startup script
│
├── Bot Components/
│   ├── sql_translator_simple.py            # Azure OpenAI integration
│   ├── azure_openai_sql_translator.py      # Advanced translator (full version)
│   ├── token_limiter.py                    # Token usage management
│   └── query_validator.py                  # SQL query validation
│
├── Web Interface/
│   ├── sql_console_routes.py               # Console backend logic
│   ├── sql_console_html.py                 # Console HTML generator
│   ├── sql_console_ui.py                   # Console CSS styles
│   ├── sql_console_javascript.py           # Console client-side logic
│   │
│   ├── admin_dashboard_routes.py           # Admin backend logic
│   └── admin_dashboard_ui.py               # Admin UI components
│
└── Azure Function SQL/
    ├── QuerySQL/
        ├── __init__.py                     # Main function handler
        └── result_formatter.py             # Result formatting logic

## 🔧 Component Breakdown

### 1. **app.py** - Main Application
The heart of the application that:
- Initializes the web server using aiohttp
- Sets up routing for all endpoints
- Manages environment configuration
- Handles global error handling
- Integrates all components


### 2. **SQL Translator Components**

#### **sql_translator_simple.py**
A simplified Azure OpenAI translator for basic natural language to SQL conversion.
- Uses Azure OpenAI API to convert questions to SQL
- Returns `SQLQuery` objects with query, database, explanation, and confidence
- Handles errors gracefully

#### **azure_openai_sql_translator.py** (Advanced Version)
Full-featured translator with:
- Token usage limiting
- Context awareness (conversation history)
- Query safety validation
- Multi-step query handling
- Schema awareness
- Performance suggestions

#### **token_limiter.py**
Prevents excessive API costs by:
- Tracking daily/hourly token usage
- Enforcing usage limits
- Calculating costs
- Persisting usage data

### 3. **Web Console Components**

#### **sql_console_routes.py**
Backend logic for the SQL console:
- Handles message processing
- Manages database/table discovery
- Executes SQL queries via Azure Function
- Maintains session state

#### **sql_console_html.py, sql_console_ui.py, sql_console_javascript.py**
Frontend components providing:
- Interactive chat interface
- Database/table browser
- Query results display
- Real-time updates

### 4. **Admin Dashboard**

#### **admin_dashboard_routes.py**
Administrative interface backend:
- System health monitoring
- Service testing (OpenAI, SQL Function, etc.)
- Performance metrics
- Troubleshooting tools

#### **admin_dashboard_ui.py**
Dashboard UI with:
- Service status indicators
- Test runners
- Activity logs
- Export capabilities

### 5. **Azure Function Components**

#### **QuerySQL/__init__.py**
Main SQL execution function that:
- Validates queries for safety
- Connects to SQL databases using MSI authentication
- Executes queries with timeout protection
- Formats results using ResultFormatter
- Handles multi-database queries

**Key Features:**
- Group-based permission handling
- Database discovery with access testing
- Safety validation to prevent dangerous operations
- Result formatting with natural language output

#### **result_formatter.py**
Sophisticated result formatting:
- Analyzes query intent
- Structures data appropriately
- Generates natural language explanations
- Provides visualization hints
- Creates insights from data patterns

### 6. **Supporting Components**

#### **query_validator.py**
Shared validation logic ensuring:
- Only SELECT queries are executed
- No dangerous keywords
- SQL injection prevention
- Proper sanitization

## 🔐 Authentication Flow


## 🚀 Deployment Configuration


### Azure App Service Setup

1. **Runtime**: Python 3.11
2. **Startup Command**: Uses `startup.sh`
3. **Managed Identity**: Enable for SQL access

## 🔄 Request Flow Example

1. **User enters query in console**: "Show me all customers"

2. **Console sends to backend**:
   ```javascript
   POST /console/api/message
   {
     "message": "Show me all customers",
     "database": "master",
     "session_id": "session_123"
   }
   ```

3. **Backend processes**:
   - Checks if SQL or natural language
   - If natural language, translates via Azure OpenAI
   - Validates query safety

4. **Executes via Azure Function**:
   ```python
   POST /api/query
   {
     "query_type": "single",
     "query": "SELECT TOP 100 * FROM customers",
     "database": "sales"
   }
   ```

5. **Function executes safely**:
   - Validates permissions
   - Executes with timeout
   - Formats results

6. **Response flows back**:
   - Formatted results returned
   - Console displays in table
   - Natural language explanation provided




### Debug Steps

## 📊 Performance Considerations

1. **Token Usage**
   - Monitor via admin dashboard
   - Adjust limits in environment
   - Check `.token_usage.json`

2. **Query Performance**
   - Always use TOP clause
   - Index awareness
   - Timeout protection (30s)

3. **Caching**
   - Database list cached per session
   - Schema information cached
   - Query results not cached

## 🔒 Security Features

1. **Query Validation**
   - Only SELECT queries allowed
   - Dangerous keywords blocked
   - SQL injection prevention

2. **Authentication**
   - MSI for database access
   - Function keys for API access
   - No passwords in code

3. **Rate Limiting**
   - Token usage limits
   - Query timeout protection
   - Row count limits (10,000)
