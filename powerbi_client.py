# powerbi_client.py - Power BI Authentication and API Client
"""
Power BI Client - Handles authentication and API calls to Power BI service
Enhanced with better debugging for workspace access issues
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import aiohttp

# Handle MSAL import with fallback
try:
    from msal import ConfidentialClientApplication
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False
    ConfidentialClientApplication = None

# Handle JWT import (pyjwt installs as jwt)
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class PowerBICredentials:
    """Power BI authentication credentials"""
    tenant_id: str
    client_id: str
    client_secret: str
    scope: List[str] = field(default_factory=lambda: ["https://analysis.windows.net/powerbi/api/.default"])

@dataclass
class WorkspaceInfo:
    """Power BI workspace information"""
    id: str
    name: str
    description: Optional[str] = None
    is_personal: bool = False
    capacity_id: Optional[str] = None
    type: Optional[str] = None
    state: Optional[str] = None

@dataclass
class DatasetInfo:
    """Power BI dataset information"""
    id: str
    name: str
    workspace_id: str
    workspace_name: str
    configured_by: Optional[str] = None
    created_date: Optional[str] = None
    content_provider_type: Optional[str] = None
    tables: List[Dict[str, Any]] = field(default_factory=list)
    measures: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class QueryResult:
    """Result from a DAX query execution"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    row_count: int = 0

class PowerBIClient:
    """Client for interacting with Power BI REST API"""
    
    def __init__(self):
        # Check dependencies first
        if not MSAL_AVAILABLE:
            logger.error("MSAL library not available. Install with: pip install msal")
            self.configured = False
            self.msal_app = None
            return
            
        # Load credentials from environment
        self.credentials = PowerBICredentials(
            tenant_id=os.environ.get("POWERBI_TENANT_ID", "").strip(),
            client_id=os.environ.get("POWERBI_CLIENT_ID", "").strip(),
            client_secret=os.environ.get("POWERBI_CLIENT_SECRET", "").strip()
        )
        
        # Log credential status (without exposing secrets)
        logger.info("Power BI Client initialization:")
        logger.info(f"  Tenant ID: {'SET' if self.credentials.tenant_id else 'NOT SET'}")
        logger.info(f"  Client ID: {'SET' if self.credentials.client_id else 'NOT SET'}")
        logger.info(f"  Client Secret: {'SET' if self.credentials.client_secret else 'NOT SET'}")
        logger.info(f"  MSAL Available: {MSAL_AVAILABLE}")
        logger.info(f"  JWT Available: {JWT_AVAILABLE}")
        
        # Validate credentials
        if not all([self.credentials.tenant_id, self.credentials.client_id, self.credentials.client_secret]):
            logger.warning("Power BI credentials not fully configured")
            self.configured = False
            self.msal_app = None
        else:
            self.configured = True
            logger.info("Power BI credentials are fully configured")
        
        # Initialize MSAL client
        if self.configured and MSAL_AVAILABLE:
            try:
                self.msal_app = ConfidentialClientApplication(
                    self.credentials.client_id,
                    authority=f"https://login.microsoftonline.com/{self.credentials.tenant_id}",
                    client_credential=self.credentials.client_secret
                )
                logger.info("MSAL client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize MSAL client: {e}")
                self.msal_app = None
                self.configured = False
        else:
            self.msal_app = None
        
        # Base URLs
        self.base_url = "https://api.powerbi.com/v1.0/myorg"
        self.token_cache = {}
        
        logger.info(f"Power BI Client initialized - Configured: {self.configured}")
    
    async def get_access_token(self) -> Optional[str]:
        """Get access token for Power BI API with enhanced debugging"""
        if not self.configured:
            logger.error("Power BI client not configured - cannot get access token")
            return None
        
        if not self.msal_app:
            logger.error("MSAL app not initialized - cannot get access token")
            return None
        
        try:
            # Check cache
            cache_key = "powerbi_token"
            if cache_key in self.token_cache:
                cached_token = self.token_cache[cache_key]
                # FIX: Compare datetime to datetime, not float to datetime
                if cached_token["expires_at"] > datetime.now() + timedelta(minutes=5):
                    logger.info("Using cached Power BI access token")
                    return cached_token["access_token"]
            
            logger.info("Acquiring new Power BI access token...")
            
            # Get new token
            result = self.msal_app.acquire_token_for_client(scopes=self.credentials.scope)
            
            if "access_token" in result:
                # Cache the token with datetime object (not timestamp)
                self.token_cache[cache_key] = {
                    "access_token": result["access_token"],
                    "expires_at": datetime.now() + timedelta(seconds=result.get("expires_in", 3600))
                }
                logger.info("Successfully acquired Power BI access token")
                
                # Decode token to check app permissions (if JWT available)
                if JWT_AVAILABLE:
                    try:
                        # Decode without verification to inspect claims
                        decoded = jwt.decode(result["access_token"], options={"verify_signature": False})
                        logger.info(f"Token app ID: {decoded.get('appid', 'Unknown')}")
                        logger.info(f"Token audience: {decoded.get('aud', 'Unknown')}")
                        
                        # Check for application permissions
                        roles = decoded.get('roles', [])
                        if roles:
                            logger.info(f"Token application permissions (roles): {', '.join(roles)}")
                        else:
                            logger.warning("No application permissions (roles) found in token - using delegated permissions?")
                        
                        # Check scopes
                        scp = decoded.get('scp', '')
                        if scp:
                            logger.info(f"Token delegated permissions (scp): {scp}")
                    except Exception as e:
                        logger.warning(f"Could not decode token for inspection: {e}")
                
                return result["access_token"]
            else:
                error_msg = result.get('error_description', result.get('error', 'Unknown error'))
                logger.error(f"Failed to acquire token: {error_msg}")
                
                # Provide more specific error guidance
                if "AADSTS700016" in str(error_msg):
                    logger.error("Application not found - check POWERBI_CLIENT_ID")
                elif "AADSTS7000215" in str(error_msg):
                    logger.error("Invalid client secret - check POWERBI_CLIENT_SECRET")
                elif "AADSTS90002" in str(error_msg):
                    logger.error("Tenant not found - check POWERBI_TENANT_ID")
                
                return None
                
        except Exception as e:
            logger.error(f"Exception while getting access token: {e}", exc_info=True)
            return None
    
    async def get_user_workspaces(self, access_token: str) -> List[WorkspaceInfo]:
        """Get list of workspaces accessible to the user/app with enhanced debugging"""
        try:
            logger.info("Fetching accessible workspaces...")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                # First, let's check what kind of access we have
                logger.info("Testing API access levels...")
                
                # Test 1: Try admin endpoint (requires Tenant.Read.All)
                try:
                    async with session.get(
                        f"{self.base_url}/admin/workspaces?$top=5",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as admin_response:
                        
                        if admin_response.status == 200:
                            logger.info("✓ Admin API access confirmed (Tenant.Read.All working)")
                            admin_data = await admin_response.json()
                            admin_workspaces = admin_data.get("value", [])
                            logger.info(f"Admin API shows {len(admin_workspaces)} workspaces in tenant")
                        else:
                            logger.info(f"✗ Admin API access denied (status: {admin_response.status})")
                except Exception as e:
                    logger.info(f"✗ Admin API test failed: {e}")
                
                # Test 2: Regular groups endpoint
                async with session.get(
                    f"{self.base_url}/groups",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    logger.info(f"Groups API response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        workspaces = []
                        
                        # Log raw response for debugging
                        logger.info(f"Groups API returned {len(data.get('value', []))} items")
                        
                        # Process workspaces from groups endpoint
                        for ws in data.get("value", []):
                            logger.info(f"Found workspace: {ws.get('name', 'Unknown')} (ID: {ws.get('id', 'Unknown')[:8]}..., type: {ws.get('type', 'Unknown')}, state: {ws.get('state', 'Unknown')})")
                            
                            workspace = WorkspaceInfo(
                                id=ws["id"],
                                name=ws["name"],
                                description=ws.get("description"),
                                is_personal=ws.get("isPersonal", False),
                                capacity_id=ws.get("capacityId"),
                                type=ws.get("type", "Workspace"),
                                state=ws.get("state", "Active")
                            )
                            
                            # Only include active workspaces
                            if workspace.state == "Active":
                                workspaces.append(workspace)
                            else:
                                logger.info(f"Skipping inactive workspace: {workspace.name}")
                        
                        # Test 3: Check if we're a service principal
                        try:
                            async with session.get(
                                f"{self.base_url}/apps",
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as apps_response:
                                
                                if apps_response.status == 200:
                                    apps_data = await apps_response.json()
                                    logger.info(f"Apps API shows {len(apps_data.get('value', []))} apps")
                                else:
                                    logger.info(f"Apps API status: {apps_response.status}")
                        except Exception as e:
                            logger.info(f"Apps API test: {e}")
                        
                        # Test 4: Try to get available features
                        try:
                            async with session.get(
                                f"{self.base_url}/availableFeatures",
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as features_response:
                                
                                if features_response.status == 200:
                                    features_data = await features_response.json()
                                    features = features_data.get("features", [])
                                    logger.info(f"Available features: {', '.join(features[:5])}...")
                                else:
                                    logger.info(f"Features API status: {features_response.status}")
                        except Exception as e:
                            logger.info(f"Features API test: {e}")
                        
                        # If no workspaces found through groups API
                        if len(workspaces) == 0:
                            logger.warning("No workspaces found through groups API")
                            
                            # Test 5: Try datasets endpoint to see if we have any access
                            try:
                                async with session.get(
                                    f"{self.base_url}/datasets",
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)
                                ) as dataset_response:
                                    
                                    if dataset_response.status == 200:
                                        dataset_data = await dataset_response.json()
                                        datasets = dataset_data.get("value", [])
                                        logger.info(f"Found {len(datasets)} datasets in personal workspace")
                                        
                                        if datasets:
                                            # Add a virtual "My Workspace" entry
                                            workspaces.append(WorkspaceInfo(
                                                id="me",  # Special ID for personal workspace
                                                name="My Workspace",
                                                description="Personal workspace",
                                                is_personal=True,
                                                state="Active"
                                            ))
                                    else:
                                        logger.info(f"Datasets API status: {dataset_response.status}")
                            except Exception as e:
                                logger.warning(f"Could not check personal workspace: {e}")
                        
                        logger.info(f"Retrieved {len(workspaces)} accessible workspaces")
                        
                        # Provide helpful messages if no workspaces found
                        if len(workspaces) == 0:
                            logger.warning("=" * 60)
                            logger.warning("NO WORKSPACES FOUND - TROUBLESHOOTING GUIDE:")
                            logger.warning("=" * 60)
                            logger.warning("1. Check API Permissions in Azure Portal:")
                            logger.warning("   - You currently have DELEGATED permissions")
                            logger.warning("   - For app-only auth, you need APPLICATION permissions")
                            logger.warning("   - Add: Workspace.Read.All (Application)")
                            logger.warning("   - Add: Dataset.Read.All (Application)")
                            logger.warning("")
                            logger.warning("2. Alternative: Enable Service Principals in Power BI:")
                            logger.warning("   - Go to Power BI Admin Portal")
                            logger.warning("   - Tenant settings → Developer settings")
                            logger.warning("   - Enable 'Service principals can use Power BI APIs'")
                            logger.warning("   - Add your app's Object ID to the security group")
                            logger.warning("")
                            logger.warning("3. Grant Workspace Access:")
                            logger.warning("   - Go to each Power BI workspace")
                            logger.warning("   - Click 'Access' → 'Add people or groups'")
                            logger.warning("   - Search for your app by name or Application ID")
                            logger.warning("   - Grant 'Viewer' or higher role")
                            logger.warning("")
                            logger.warning("4. Wait 5-15 minutes for permissions to propagate")
                            logger.warning("=" * 60)
                        
                        return workspaces
                    
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"Unauthorized access to workspaces API: {error_text}")
                        logger.error("The access token is valid but lacks proper permissions")
                        return []
                    
                    elif response.status == 403:
                        error_text = await response.text()
                        logger.error(f"Forbidden access to workspaces API: {error_text}")
                        
                        # Parse error for more details
                        try:
                            error_json = json.loads(error_text)
                            error_code = error_json.get("error", {}).get("code", "Unknown")
                            error_message = error_json.get("error", {}).get("message", "Unknown")
                            logger.error(f"Error code: {error_code}")
                            logger.error(f"Error message: {error_message}")
                            
                            if "Unauthorized" in error_message:
                                logger.error("The app registration lacks required API permissions")
                        except:
                            pass
                            
                        return []
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get workspaces: {response.status} - {error_text}")
                        return []
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching workspaces: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching workspaces: {e}", exc_info=True)
            return []
    
    async def get_workspace_datasets(self, access_token: str, workspace_id: str, workspace_name: str = "") -> List[DatasetInfo]:
        """Get datasets in a specific workspace"""
        try:
            logger.info(f"Fetching datasets for workspace: {workspace_name} (ID: {workspace_id[:8] if workspace_id != 'me' else 'personal'}...)")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Handle personal workspace differently
            if workspace_id == "me":
                url = f"{self.base_url}/datasets"
            else:
                url = f"{self.base_url}/groups/{workspace_id}/datasets"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    logger.info(f"Dataset API response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        datasets = []
                        
                        for ds in data.get("value", []):
                            # Log dataset info
                            logger.info(f"Found dataset: {ds.get('name', 'Unknown')} (ID: {ds.get('id', 'Unknown')[:8]}...)")
                            
                            # Only include datasets that can be queried
                            if ds.get("isRefreshable", True) or ds.get("isEffectiveIdentityRequired", False) or True:  # Be more permissive
                                dataset = DatasetInfo(
                                    id=ds["id"],
                                    name=ds["name"],
                                    workspace_id=workspace_id,
                                    workspace_name=workspace_name or "My Workspace" if workspace_id == "me" else workspace_name,
                                    configured_by=ds.get("configuredBy"),
                                    created_date=ds.get("createdDate"),
                                    content_provider_type=ds.get("contentProviderType")
                                )
                                datasets.append(dataset)
                            else:
                                logger.info(f"Skipping non-queryable dataset: {ds.get('name', 'Unknown')}")
                        
                        logger.info(f"Retrieved {len(datasets)} queryable datasets from workspace {workspace_name}")
                        return datasets
                    
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"Unauthorized access to datasets in workspace {workspace_name}: {error_text}")
                        return []
                    
                    elif response.status == 403:
                        error_text = await response.text()
                        logger.error(f"Forbidden access to datasets in workspace {workspace_name}: {error_text}")
                        logger.error("The app may not have access to this workspace's datasets")
                        return []
                    
                    elif response.status == 404:
                        logger.error(f"Workspace {workspace_name} not found or not accessible")
                        return []
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get datasets: {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching datasets for workspace {workspace_name}: {e}", exc_info=True)
            return []
    
    async def get_dataset_metadata(self, access_token: str, dataset_id: str) -> Dict[str, Any]:
        """Get detailed metadata for a dataset including tables and measures"""
        try:
            logger.info(f"Fetching metadata for dataset: {dataset_id[:8]}...")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            metadata = {
                "tables": [],
                "measures": [],
                "relationships": []
            }
            
            # First, try to get dataset refresh history to understand the model better
            async with aiohttp.ClientSession() as session:
                try:
                    # Get dataset refresh history
                    async with session.get(
                        f"{self.base_url}/datasets/{dataset_id}/refreshes",
                        headers=headers,
                        params={"$top": 1},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        
                        if response.status == 200:
                            refresh_data = await response.json()
                            if refresh_data.get("value"):
                                metadata["last_refresh"] = refresh_data["value"][0].get("endTime")
                                logger.info(f"Dataset last refreshed: {metadata['last_refresh']}")
                except Exception as e:
                    logger.warning(f"Could not get refresh history: {e}")
                
                # Execute a metadata query to discover tables and measures
                metadata_query = """
                EVALUATE
                    UNION(
                        SELECTCOLUMNS(
                            INFO.TABLES(),
                            "Type", "Table",
                            "Name", [Name],
                            "Description", [Description]
                        ),
                        SELECTCOLUMNS(
                            INFO.MEASURES(),
                            "Type", "Measure",
                            "Name", [Name],
                            "Description", [Description]
                        )
                    )
                """
                
                # Try to execute metadata query
                logger.info("Attempting to discover dataset schema using DAX query...")
                result = await self.execute_dax_query(access_token, dataset_id, metadata_query)
                
                if result.success and result.data:
                    for item in result.data:
                        if item.get("Type") == "Table":
                            metadata["tables"].append({
                                "name": item.get("Name", ""),
                                "description": item.get("Description", "")
                            })
                        elif item.get("Type") == "Measure":
                            metadata["measures"].append({
                                "name": item.get("Name", ""),
                                "description": item.get("Description", "")
                            })
                    
                    logger.info(f"Discovered {len(metadata['tables'])} tables and {len(metadata['measures'])} measures")
                else:
                    # Fallback: Try simpler queries
                    logger.info("Metadata query failed, using fallback approach")
                    
                    # Try to get at least some basic info
                    simple_query = """
                    EVALUATE
                    ROW("Dataset", "Available")
                    """
                    
                    test_result = await self.execute_dax_query(access_token, dataset_id, simple_query)
                    if test_result.success:
                        metadata["status"] = "accessible"
                        logger.info("Dataset is accessible for queries")
                    else:
                        metadata["status"] = "inaccessible"
                        metadata["error"] = test_result.error
                        logger.warning(f"Dataset may not be fully accessible: {test_result.error}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error fetching dataset metadata: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def execute_dax_query(self, access_token: str, dataset_id: str, dax_query: str, dataset_name: str = "") -> QueryResult:
        """Execute a DAX query against a Power BI dataset"""
        start_time = datetime.now()
        
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Prepare the query payload
            payload = {
                "queries": [
                    {
                        "query": dax_query
                    }
                ],
                "serializerSettings": {
                    "includeNulls": True
                }
            }
            
            logger.info(f"Executing DAX query on dataset {dataset_name or dataset_id[:8]}: {dax_query[:100]}...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/datasets/{dataset_id}/executeQueries",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    
                    logger.info(f"DAX query response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract results from the response
                        if "results" in data and len(data["results"]) > 0:
                            result = data["results"][0]
                            
                            if "tables" in result and len(result["tables"]) > 0:
                                table = result["tables"][0]
                                rows = table.get("rows", [])
                                
                                # Convert rows to list of dictionaries
                                formatted_rows = []
                                for row in rows:
                                    formatted_rows.append(row)
                                
                                logger.info(f"Query successful: {len(formatted_rows)} rows returned in {execution_time}ms")
                                
                                return QueryResult(
                                    success=True,
                                    data=formatted_rows,
                                    row_count=len(formatted_rows),
                                    execution_time_ms=execution_time,
                                    dataset_id=dataset_id,
                                    dataset_name=dataset_name
                                )
                            else:
                                # Query executed but no data returned
                                logger.info("Query executed successfully but returned no data")
                                return QueryResult(
                                    success=True,
                                    data=[],
                                    row_count=0,
                                    execution_time_ms=execution_time,
                                    dataset_id=dataset_id,
                                    dataset_name=dataset_name
                                )
                        else:
                            # No results in response
                            logger.warning("Query response contains no results")
                            return QueryResult(
                                success=False,
                                error="No results returned from query",
                                execution_time_ms=execution_time
                            )
                    
                    elif response.status == 400:
                        # Bad request - likely DAX syntax error
                        error_data = await response.json()
                        error_message = self._extract_error_message(error_data)
                        
                        logger.error(f"DAX syntax error: {error_message}")
                        
                        return QueryResult(
                            success=False,
                            error=f"DAX syntax error: {error_message}",
                            execution_time_ms=execution_time
                        )
                    
                    elif response.status == 401:
                        # Unauthorized
                        error_text = await response.text()
                        logger.error(f"Unauthorized access to dataset: {error_text}")
                        return QueryResult(
                            success=False,
                            error="Unauthorized: Access token may be expired or invalid",
                            execution_time_ms=execution_time
                        )
                    
                    elif response.status == 403:
                        # Forbidden
                        error_text = await response.text()
                        logger.error(f"Forbidden access to dataset: {error_text}")
                        return QueryResult(
                            success=False,
                            error="Access denied: The app may not have permission to query this dataset",
                            execution_time_ms=execution_time
                        )
                    
                    elif response.status == 404:
                        # Dataset not found
                        logger.error(f"Dataset {dataset_id} not found")
                        return QueryResult(
                            success=False,
                            error=f"Dataset {dataset_id} not found or not accessible",
                            execution_time_ms=execution_time
                        )
                    
                    else:
                        # Other error
                        error_text = await response.text()
                        logger.error(f"Query failed with status {response.status}: {error_text}")
                        
                        return QueryResult(
                            success=False,
                            error=f"Query failed with status {response.status}: {error_text[:200]}",
                            execution_time_ms=execution_time
                        )
                        
        except asyncio.TimeoutError:
            logger.error("DAX query timed out after 60 seconds")
            return QueryResult(
                success=False,
                error="Query timeout: The query took too long to execute",
                execution_time_ms=60000
            )
        except Exception as e:
            logger.error(f"Error executing DAX query: {e}", exc_info=True)
            return QueryResult(
                success=False,
                error=f"Error executing query: {str(e)}",
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    def _extract_error_message(self, error_data: Dict[str, Any]) -> str:
        """Extract meaningful error message from Power BI error response"""
        if "error" in error_data:
            error = error_data["error"]
            if isinstance(error, dict):
                # Check for detailed error information
                if "pbi.error" in error:
                    pbi_error = error["pbi.error"]
                    if "details" in pbi_error and len(pbi_error["details"]) > 0:
                        detail = pbi_error["details"][0]
                        return detail.get("detail", {}).get("value", error.get("message", "Unknown error"))
                return error.get("message", "Unknown error")
            else:
                return str(error)
        
        return "Unknown error occurred"
    
    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate Power BI configuration and connectivity"""
        validation_result = {
            "configured": self.configured,
            "credentials_present": False,
            "token_acquired": False,
            "api_accessible": False,
            "workspaces_accessible": False,
            "errors": [],
            "warnings": [],
            "dependencies": {
                "msal": MSAL_AVAILABLE,
                "jwt": JWT_AVAILABLE
            }
        }
        
        logger.info("Starting Power BI configuration validation...")
        
        # Check dependencies
        if not MSAL_AVAILABLE:
            validation_result["errors"].append("MSAL library not installed. Run: pip install msal")
            logger.error("✗ MSAL library not available")
            return validation_result
            
        # Check credentials
        if all([self.credentials.tenant_id, self.credentials.client_id, self.credentials.client_secret]):
            validation_result["credentials_present"] = True
            logger.info("✓ Power BI credentials are present")
        else:
            missing = []
            if not self.credentials.tenant_id:
                missing.append("POWERBI_TENANT_ID")
            if not self.credentials.client_id:
                missing.append("POWERBI_CLIENT_ID")
            if not self.credentials.client_secret:
                missing.append("POWERBI_CLIENT_SECRET")
            
            error_msg = f"Missing Power BI credentials: {', '.join(missing)}"
            validation_result["errors"].append(error_msg)
            logger.error(f"✗ {error_msg}")
            return validation_result
        
        # Try to get access token
        token = await self.get_access_token()
        if token:
            validation_result["token_acquired"] = True
            logger.info("✓ Successfully acquired access token")
            
            # Try to access API
            try:
                workspaces = await self.get_user_workspaces(token)
                validation_result["api_accessible"] = True
                
                if workspaces:
                    validation_result["workspaces_accessible"] = True
                    validation_result["workspace_count"] = len(workspaces)
                    logger.info(f"✓ Found {len(workspaces)} accessible workspaces")
                else:
                    validation_result["warnings"].append("No workspaces accessible - You need APPLICATION permissions, not DELEGATED")
                    validation_result["warnings"].append("Add Workspace.Read.All and Dataset.Read.All as APPLICATION permissions in Azure Portal")
                    validation_result["warnings"].append("Alternative: Enable service principals in Power BI Admin Portal")
                    logger.warning("⚠ No workspaces accessible")
                    
            except Exception as e:
                validation_result["errors"].append(f"API access error: {str(e)}")
                logger.error(f"✗ API access error: {str(e)}")
        else:
            validation_result["errors"].append("Failed to acquire access token - check credentials")
            logger.error("✗ Failed to acquire access token")
            
            # Add specific guidance
            validation_result["warnings"].append("Ensure app registration has correct API permissions (Application, not Delegated)")
            validation_result["warnings"].append("Verify the client secret hasn't expired")
        
        # Summary
        if validation_result["workspaces_accessible"]:
            logger.info("✓ Power BI configuration is valid and working")
        else:
            logger.warning("⚠ Power BI configuration has issues - check errors and warnings")
        
        return validation_result
    
    def is_configured(self) -> bool:
        """Check if Power BI client is properly configured"""
        return self.configured and MSAL_AVAILABLE

# Create singleton instance
powerbi_client = PowerBIClient()

# Export
__all__ = ['PowerBIClient', 'powerbi_client', 'WorkspaceInfo', 'DatasetInfo', 'QueryResult']