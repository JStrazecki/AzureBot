
# SQL Assistant Bot - Complete Code Documentation
## Main Application

### 📄 app.py
**Purpose**: Main entry point for the SQL Assistant application. Orchestrates all components and starts the web server.

```python
#!/usr/bin/env python3
```

**Key Components**:

1. **Imports Section**:
   - `aiohttp`: Async web framework for handling HTTP requests
   - `logging`: Structured logging throughout the application
   - Standard libraries: `os`, `json`, `asyncio`, `datetime`

2. **Environment Check Function**:
   ```python
   def check_environment():
   ```
   - Validates all required environment variables are set
   - Masks sensitive values (API keys) in logs
   - Returns list of missing variables
   - Critical for deployment troubleshooting

3. **SQL Translator Initialization**:
   ```python
   SQL_TRANSLATOR = None
   if not missing_vars or all(var not in missing_vars...):
       from sql_translator_simple import SimpleSQLTranslator
       SQL_TRANSLATOR = SimpleSQLTranslator()
   ```
   - Conditionally creates translator if OpenAI credentials exist
   - Falls back gracefully if not configured

4. **Middleware**:
   ```python
   @middleware
   async def aiohttp_error_middleware(request: Request, handler):
   ```
   - Global error handler for all HTTP requests
   - Catches unhandled exceptions
   - Returns JSON error responses

5. **Route Handlers**:
   - `health()`: System health check endpoint
   - `index()`: Homepage with navigation links
   - `info()`: API information endpoint
   - `test_sql_translation()`: Testing endpoint for translation

6. **Application Setup**:
   ```python
   APP = web.Application(middlewares=[aiohttp_error_middleware])
   ```
   - Creates aiohttp application instance
   - Registers all routes
   - Imports and adds console/admin routes

7. **Lifecycle Handlers**:
   - `on_startup()`: Creates directories, logs configuration
   - `on_cleanup()`: Graceful shutdown tasks

**Main Entry Point**:
```python
if __name__ == "__main__":
    web.run_app(APP, host="0.0.0.0", port=PORT)
```

---

## SQL Translation Components

### 📄 sql_translator_simple.py
**Purpose**: Simplified Azure OpenAI integration for natural language to SQL translation.

**Classes**:

1. **SQLQuery Dataclass**:
   ```python
   @dataclass
   class SQLQuery:
       query: str          # Generated SQL query
       database: str       # Target database
       explanation: str    # Human-readable explanation
       confidence: float   # 0.0-1.0 confidence score
       error: Optional[str] = None
   ```

2. **SimpleSQLTranslator Class**:
   
   **Initialization**:
   - Loads Azure OpenAI credentials from environment
   - Creates AzureOpenAI client instance
   - Defines system prompt for SQL generation

   **System Prompt**:
   - Enforces SELECT-only queries
   - Requires T-SQL syntax (TOP not LIMIT)
   - Adds safety limits (TOP 100 default)
   - Returns structured JSON response

   **translate_to_sql() Method**:
   ```python
   async def translate_to_sql(self, user_query: str, database: str = "master", 
                             schema_context: Optional[str] = None) -> SQLQuery:
   ```
   - Constructs messages array with system and user prompts
   - Calls Azure OpenAI API with low temperature (0.1) for consistency
   - Parses JSON response into SQLQuery object
   - Handles errors gracefully

### 📄 azure_openai_sql_translator.py
**Purpose**: Advanced translator with token limiting, context awareness, and multi-step query support.

**Key Features Beyond Simple Translator**:

1. **ConversationContext Dataclass**:
   ```python
   @dataclass
   class ConversationContext:
       messages: List[Dict[str, str]]      # Chat history
       current_database: Optional[str]     # Active database
       recent_tables: List[str]            # Recently accessed tables
       query_history: List[SQLQuery]       # Previous queries
       user_preferences: Dict[str, Any]    # User settings
       schema_context: Optional[Dict[str, Any]]  # Database schema
   ```

2. **Enhanced System Prompt**:
   - More detailed safety rules
   - Multi-step query instructions
   - Schema awareness guidelines
   - Response format specifications

3. **Additional Methods**:

   **explain_results()**:
   - Takes query results and generates natural language explanation
   - Can work with pre-formatted results from Azure Function
   - Adds insights to base explanation

   **suggest_improvements()**:
   - Analyzes query performance
   - Suggests optimizations
   - Provides T-SQL best practices
   - Returns optimized query if applicable

   **handle_complex_query()**:
   - Breaks complex questions into multiple SQL steps
   - Manages dependencies between queries
   - Limits to max_steps (default 5)
   - Returns array of SQLQuery objects

   **Token Management**:
   - Uses TokenLimiter to track usage
   - Prevents exceeding daily/hourly limits
   - Estimates tokens before API calls
   - Logs usage and costs

### 📄 token_limiter.py
**Purpose**: Manages Azure OpenAI token usage to control costs.

**Key Components**:

1. **Usage Tracking**:
   ```python
   self.usage_file = Path(".token_usage.json")
   ```
   - Persists usage data to file
   - Tracks daily, hourly, and total usage
   - Calculates costs based on token pricing

2. **Limit Checking**:
   ```python
   def check_limits(self, estimated_tokens: int) -> Tuple[bool, str]:
   ```
   - Validates against per-request limits
   - Checks daily and hourly quotas
   - Returns detailed rejection reasons

3. **Usage Recording**:
   ```python
   def track_usage(self, prompt_tokens: int, completion_tokens: int):
   ```
   - Updates all usage counters
   - Maintains rolling hourly window
   - Saves to persistent storage

---

## Web Console Components

### 📄 sql_console_routes.py
**Purpose**: Backend logic for the interactive SQL console.

**SQLConsole Class**:

1. **Initialization**:
   - Stores reference to SQL translator
   - Loads Azure Function URL
   - Manages session storage

2. **Main Handler - handle_message()**:
   ```python
   async def handle_message(self, request: Request) -> Response:
   ```
   
   **Process Flow**:
   - Extracts message, database, session from request
   - Checks for special commands (help, show databases)
   - Determines if input is SQL or natural language
   - For natural language: translates via OpenAI
   - Validates query safety
   - Executes via Azure Function
   - Returns formatted response

3. **Database Discovery**:
   ```python
   async def _get_databases(self) -> List[str]:
   ```
   - Calls Azure Function metadata endpoint
   - Returns list of accessible databases
   - Falls back to ['master'] on error

4. **Table Discovery**:
   ```python
   async def _get_tables(self, database: str) -> List[str]:
   ```
   - Executes INFORMATION_SCHEMA query
   - Returns table names for specified database

5. **SQL Execution**:
   ```python
   async def _execute_sql_query(self, query: str, database: str) -> Dict[str, Any]:
   ```
   - Prepares payload for Azure Function
   - Handles authentication (URL-embedded key)
   - Returns execution results or error

### 📄 sql_console_html.py
**Purpose**: Generates complete HTML page for console.

**Structure**:
- Imports CSS from sql_console_ui.py
- Imports JavaScript from sql_console_javascript.py
- Combines into single HTML document
- Includes sidebar for database/table browser
- Main chat interface for queries

### 📄 sql_console_ui.py
**Purpose**: Contains all CSS styles for the console interface.

**Key Styles**:
- Dark theme with purple gradients
- Responsive sidebar design
- Chat message bubbles (user/bot differentiation)
- SQL result tables with hover effects
- Loading indicators and animations
- Smooth transitions and modern aesthetics

### 📄 sql_console_javascript.py
**Purpose**: Client-side JavaScript for console interactivity.

**Key Functions**:

1. **Message Handling**:
   ```javascript
   async function sendMessage()
   ```
   - Sends user input to backend
   - Shows typing indicator
   - Handles response rendering
   - Updates UI based on response type

2. **Database Management**:
   ```javascript
   async function refreshDatabases()
   async function selectDatabase(dbName)
   async function loadTables(database)
   ```
   - Fetches and displays database list
   - Handles database switching
   - Loads tables for selected database

3. **UI Helpers**:
   - `escapeHtml()`: Prevents XSS attacks
   - `addMessage()`: Adds chat messages
   - `addSQLResult()`: Renders query results as tables
   - `showTypingIndicator()`: Visual feedback

---

## Admin Dashboard Components

### 📄 admin_dashboard_routes.py
**Purpose**: Backend logic for system administration and monitoring.

**AdminDashboard Class**:

1. **Test Endpoints**:
   
   **Health Check**:
   ```python
   async def api_test_health(self, request: Request) -> Response:
   ```
   - Returns system version, uptime
   - Shows service availability
   - Overall health status

   **OpenAI Test**:
   ```python
   async def api_test_openai(self, request: Request) -> Response:
   ```
   - Tests Azure OpenAI connectivity
   - Measures response time
   - Validates API configuration

   **SQL Function Test**:
   ```python
   async def api_test_function(self, request: Request) -> Response:
   ```
   - Tests Azure Function endpoint
   - Retrieves database list
   - Checks authentication method

   **Translator Test**:
   ```python
   async def api_test_translator(self, request: Request) -> Response:
   ```
   - Tests natural language translation
   - Uses sample query
   - Returns translated SQL

   **Performance Test**:
   ```python
   async def api_test_performance(self, request: Request) -> Response:
   ```
   - Measures server response time
   - Reports memory usage (if psutil available)
   - Shows system uptime

### 📄 admin_dashboard_ui.py
**Purpose**: Complete admin dashboard UI with HTML, CSS, and JavaScript.

**Components**:

1. **CSS Styles**:
   - Gradient backgrounds
   - Card-based layout
   - Status indicators with colors
   - Responsive grid system
   - Professional dashboard aesthetic

2. **JavaScript Functions**:
   - `runAllTests()`: Executes all service tests sequentially
   - `updateStatus()`: Updates UI indicators
   - `log()`: Activity logging with timestamps
   - `exportLogs()`: Downloads logs as text file

3. **HTML Structure**:
   - System status overview cards
   - Individual service test sections
   - Activity log viewer
   - Test result displays

---

## Azure Function Components

### 📄 Azure Function SQL/QuerySQL/__init__.py
**Purpose**: Main Azure Function for secure SQL query execution.

**Key Components**:

1. **Safety Configuration**:
   ```python
   MAX_DATABASES_TO_QUERY = 50
   MAX_ROWS_TO_RETURN = 10000
   QUERY_TIMEOUT_SECONDS = 30
   DANGEROUS_KEYWORDS = [...]
   ```

2. **QueryValidator Class**:
   - Validates queries are SELECT-only
   - Blocks dangerous SQL keywords
   - Prevents SQL injection
   - Same as shared query_validator.py

3. **SQLQueryExecutor Class**:
   
   **Database Discovery - get_databases()**:
   ```python
   def get_databases(self, check_access: bool = True, 
                    force_include_pattern: str = None) -> List[str]:
   ```
   - Connects to master database
   - Gets all database names
   - Tests each database individually for access
   - Handles group-based permissions properly
   - Caches results for performance

   **Query Execution - execute_query()**:
   ```python
   def execute_query(self, database: str, query: str, 
                    output_format: str = "full") -> QueryResult:
   ```
   - Validates query safety
   - Connects with MSI authentication
   - Executes with timeout protection
   - Formats results using ResultFormatter
   - Handles errors gracefully

4. **Main Function Handler**:
   ```python
   def main(req: func.HttpRequest) -> func.HttpResponse:
   ```
   - Parses request type (single, multi_database, metadata)
   - Routes to appropriate handler
   - Returns JSON responses
   - Handles all error cases

### 📄 result_formatter.py
**Purpose**: Sophisticated result formatting and analysis.

**ResultFormatter Class Methods**:

1. **format_results()**:
   - Main entry point
   - Analyzes query and results
   - Generates multiple format options
   - Returns comprehensive formatted data

2. **Query Analysis - _analyze_query()**:
   - Detects query intent (count, aggregate, filter, etc.)
   - Identifies SQL features used
   - Helps determine best formatting

3. **Result Analysis - _analyze_results()**:
   - Determines result type (scalar, table, metrics, etc.)
   - Analyzes column types and patterns
   - Identifies temporal and numeric data

4. **Natural Language Generation**:
   ```python
   def _generate_natural_language(self, query_analysis: Dict, 
                                 result_analysis: Dict, 
                                 results: List[Dict[str, Any]]) -> str:
   ```
   - Creates human-readable descriptions
   - Handles different result types appropriately
   - Includes relevant statistics and summaries

5. **Insights Generation**:
   - Detects null values
   - Finds outliers in numeric data
   - Analyzes date ranges
   - Suggests data quality improvements

6. **Visualization Suggestions**:
   - Recommends appropriate chart types
   - Based on data structure and content
   - Considers geographic and temporal data

### 📄 HttpQuerySQL/__init__.py
**Purpose**: Simplified HTTP endpoint for demo database queries.

**Differences from Main Function**:
- Hardcoded to 'demo' database
- Simpler error handling
- Direct query execution
- No result formatting
- Used for testing/demos

---

## Utility Components

### 📄 query_validator.py
**Purpose**: Shared SQL query validation logic.

**QueryValidator Class Methods**:

1. **is_query_safe()**:
   - Checks query starts with allowed prefixes
   - Blocks dangerous keywords
   - Detects injection patterns
   - Validates single statement only

2. **add_safety_limits()**:
   - Adds TOP clause if missing
   - Handles WITH (CTE) queries properly
   - Prevents unlimited result sets

3. **validate_database_name()**:
   - Allows only safe characters
   - Prevents injection via database names

4. **sanitize_value()**:
   - Escapes single quotes
   - Removes dangerous patterns
   - For safe value insertion

---

## Configuration Files

### 📄 requirements.txt
**Purpose**: Python package dependencies.

**Key Packages**:
- `aiohttp`: Async web framework
- `openai`: Azure OpenAI SDK
- `tiktoken`: Token counting for OpenAI
- `azure-identity`: MSI authentication
- `gunicorn`: Production WSGI server
- `pyodbc`: SQL Server connectivity (in Function)

### 📄 startup.sh
**Purpose**: Azure App Service startup script.

**Actions**:
1. Sets Python 3.11 path
2. Configures PYTHONPATH
3. Installs packages if needed
4. Verifies core imports
5. Creates required directories
6. Starts gunicorn server

### 📄 .github/workflows/main_sqlbottest.yml
**Purpose**: GitHub Actions deployment workflow.

**Steps**:
1. Checkout code
2. Setup Python 3.11
3. Install dependencies
4. Create deployment artifact
5. Deploy to Azure App Service
6. Uses publish profile for auth

### 📄 function.json (Azure Function)
**Purpose**: Function binding configuration.

**Defines**:
- HTTP trigger settings
- Authentication level
- Allowed methods
- Route configuration

### 📄 host.json (Azure Function)
**Purpose**: Function app host configuration.

**Settings**:
- Runtime version
- Logging configuration
- Performance settings

---

## Code Flow Summary

1. **User Request** → `app.py` routes to appropriate handler
2. **Console Route** → `sql_console_routes.py` processes message
3. **Translation** → `sql_translator_simple.py` calls Azure OpenAI
4. **Validation** → `query_validator.py` ensures safety
5. **Execution** → Azure Function executes query safely
6. **Formatting** → `result_formatter.py` structures response
7. **Response** → Formatted data returns through chain to user

Each component has clear responsibilities and error handling, creating a robust and maintainable system.