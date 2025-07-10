### Current Authentication Issue

The bot uses **Azure Managed Service Identity (MSI)** for SQL authentication:

```python
# In Azure Function
conn_str = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server=tcp:{server},1433;"
    f"Authentication=ActiveDirectoryMsi;"
    f"Encrypt=yes;"
    f"TrustServerCertificate=no;"
)
```

**Why You Only See Master Database:**
1. **Group Permissions**: Your MSI likely has permissions through AD groups
2. **Permission Testing**: The function tests each database individually
3. **Access Verification**: Only databases that pass the access test are shown

### Authentication Methods

1. **MSI Authentication** (Recommended)
   - No passwords in code
   - Automatic credential management
   - Works with AD group permissions

2. **Connection String** (Alternative) ### This was also tested on the demo database and I didnt suceed.
   - Set `SQL_CONNECTION` environment variable
   - Include full connection details
   - Less secure but simpler

### Fixing Database Access

To see more databases:

1. **Check MSI Permissions**:
   ```sql
   -- Run in master database
   SELECT 
       p.name AS PrincipalName,
       p.type_desc AS PrincipalType,
       mp.permission_name,
       mp.state_desc
   FROM sys.database_principals p
   JOIN sys.database_permissions mp ON p.principal_id = mp.grantee_principal_id
   WHERE p.name = 'your-msi-name'
   ```

2. **Grant Database Access**:
   ```sql
   -- For each database
   USE [YourDatabase]
   CREATE USER [your-app-service-name] FROM EXTERNAL PROVIDER
   ALTER ROLE db_datareader ADD MEMBER [your-app-service-name]
   ```

3. **Force Include Pattern**:
   The function supports forcing database inclusion:
   ```python
   # In metadata query
   force_pattern = req_body.get('force_include_pattern', None)
   ```
