# query_validator.py - Shared Query Validator
# This shares the validation logic between the bot and Azure Function

class QueryValidator:
    """Validates queries for safety - shared between bot and function"""
    
    # Safety constants
    MAX_ROWS_TO_RETURN = 10000
    ALLOWED_QUERY_PREFIXES = ['select', 'with', 'sp_', 'execute', 'exec', 'show', 'describe']
    
    # Dangerous SQL keywords to block
    DANGEROUS_KEYWORDS = [
        'insert', 'update', 'delete', 'drop', 'create', 'alter', 'truncate',
        'grant', 'revoke', 'backup', 'restore', 'merge',
        'bulk', 'shutdown', 'reconfigure', 'xp_cmdshell',
        'openrowset', 'openquery', 'opendatasource'
    ]
    
    # Safe keywords that might appear in dangerous context but are OK
    SAFE_EXCEPTIONS = {
        'into': ['insert into', 'bulk insert'],  # OK if not in these contexts
        'sp_configure': ['reconfigure']  # OK if not followed by reconfigure
    }
    
    @staticmethod
    def is_query_safe(query: str) -> tuple[bool, str]:
        """
        Check if query is safe to execute.
        Returns (is_safe, error_message)
        """
        if not query:
            return False, "Query cannot be empty"
        
        query_lower = query.strip().lower()
        
        # Allow system procedures
        if query_lower.startswith(('sp_', 'exec sp_', 'execute sp_')):
            # Check if it's a safe system procedure
            safe_procedures = [
                'sp_tables', 'sp_databases', 'sp_columns', 'sp_help', 
                'sp_helptext', 'sp_who', 'sp_who2', 'sp_helpdb'
            ]
            if any(proc in query_lower for proc in safe_procedures):
                return True, "Safe system procedure"
        
        # Check if query starts with allowed prefix
        if not any(query_lower.startswith(prefix) for prefix in QueryValidator.ALLOWED_QUERY_PREFIXES):
            return False, f"Query must start with one of: {', '.join(QueryValidator.ALLOWED_QUERY_PREFIXES)}"
        
        # Check for dangerous keywords with context awareness
        for keyword in QueryValidator.DANGEROUS_KEYWORDS:
            if keyword in query_lower:
                # Check for safe exceptions
                if keyword in QueryValidator.SAFE_EXCEPTIONS:
                    dangerous_contexts = QueryValidator.SAFE_EXCEPTIONS[keyword]
                    if not any(context in query_lower for context in dangerous_contexts):
                        continue  # This usage is safe
                
                # Special handling for common safe patterns
                if keyword == 'into' and 'insert' not in query_lower and 'bulk' not in query_lower:
                    continue  # SELECT INTO temp table is OK
                
                return False, f"Query contains forbidden keyword: {keyword}"
        
        # Check for SQL injection patterns
        injection_patterns = [
            '/*',  # Block comment start
            '*/',  # Block comment end
            'xp_', # Extended procedures
        ]
        
        for pattern in injection_patterns:
            if pattern in query_lower:
                return False, f"Query contains potentially dangerous pattern: {pattern}"
        
        # Check for multiple statements (but allow single semicolon at end)
        semicolon_count = query.count(';')
        if semicolon_count > 1 or (semicolon_count == 1 and not query.strip().endswith(';')):
            return False, "Multiple statements are not allowed"
        
        # Additional safety checks
        if 'into' in query_lower and 'select' in query_lower:
            # Allow SELECT INTO for temp tables only
            if not any(temp in query_lower for temp in ['#', 'tempdb']):
                return False, "SELECT INTO statements are only allowed for temp tables"
        
        return True, ""
    
    @staticmethod
    def add_safety_limits(query: str) -> str:
        """Add safety limits to query if not present"""
        query_lower = query.lower()
        
        # Don't add limits to system procedures or certain queries
        if any(query_lower.startswith(prefix) for prefix in ['sp_', 'exec', 'execute', 'show', 'describe']):
            return query
        
        # Add TOP limit if not present
        if 'top' not in query_lower and 'count' not in query_lower:
            # Handle both SELECT and WITH clauses
            if query_lower.startswith('with'):
                # Find the actual SELECT after the CTE
                select_pos = query_lower.find('select', query_lower.find(')'))
                if select_pos > -1:
                    before = query[:select_pos + 6]  # Include 'select'
                    after = query[select_pos + 6:]
                    query = f"{before} TOP {QueryValidator.MAX_ROWS_TO_RETURN}{after}"
            else:
                query = query.replace('SELECT', f'SELECT TOP {QueryValidator.MAX_ROWS_TO_RETURN}', 1)
                query = query.replace('select', f'select TOP {QueryValidator.MAX_ROWS_TO_RETURN}', 1)
        
        return query
    
    @staticmethod
    def validate_database_name(database: str) -> bool:
        """Validate database name for safety"""
        if not database:
            return False
        
        # Only allow alphanumeric, underscore, and hyphen
        if not database.replace('_', '').replace('-', '').isalnum():
            return False
        
        # Prevent obvious SQL injection attempts
        dangerous_db_patterns = ['drop', 'delete', 'exec', ';', '--', '/*']
        db_lower = database.lower()
        
        for pattern in dangerous_db_patterns:
            if pattern in db_lower:
                return False
        
        return True
    
    @staticmethod
    def validate_table_name(table: str) -> bool:
        """Validate table name for safety"""
        if not table:
            return False
        
        # Allow brackets
        clean_table = table.replace('[', '').replace(']', '')
        
        # Allow schema.table format
        parts = clean_table.split('.')
        for part in parts:
            if not part.replace('_', '').replace('-', '').isalnum():
                return False
        
        return True
    
    @staticmethod
    def sanitize_value(value: str) -> str:
        """Sanitize a value for use in queries"""
        if not isinstance(value, str):
            return str(value)
        
        # Escape single quotes
        sanitized = value.replace("'", "''")
        
        # Remove potential SQL injection patterns
        dangerous_patterns = ['--', '/*', '*/', ';', 'exec', 'xp_']
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, '')
        
        return sanitized