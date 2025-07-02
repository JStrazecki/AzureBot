#!/bin/bash
# deploy.sh - Azure App Service Deployment Script for SQL Assistant Bot

echo "=== SQL Assistant Bot Deployment ==="
echo "Time: $(date)"
echo "Directory: $(pwd)"
echo "Environment: ${DEPLOYMENT_ENV:-production}"

# Navigate to the correct directory
cd /home/site/wwwroot || exit 1

# Use Python 3.11 (Azure App Service default)
export PATH="/opt/python/3.11.12/bin:/opt/python/3.11/bin:$PATH"
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

echo "Python: $(which python3)"
echo "Python version: $(python3 --version)"

# Create necessary directories
echo "Creating required directories..."
mkdir -p .pattern_cache
mkdir -p .exploration_exports
mkdir -p .query_logs
mkdir -p .mcp_cache
mkdir -p .token_usage
mkdir -p logs

# Set permissions
chmod 755 .pattern_cache .exploration_exports .query_logs .mcp_cache .token_usage logs

# Install dependencies
echo "Installing Python packages..."
python3 -m pip install --user --upgrade pip
python3 -m pip install --user --no-cache-dir -r requirements.txt

# Add user site-packages to Python path
export PATH="$PATH:/home/.local/bin"
export PYTHONPATH="$PYTHONPATH:/home/.local/lib/python3.11/site-packages"

# Verify critical packages
echo "Verifying package installation..."
python3 -c "import aiohttp; print('✓ aiohttp installed')" || { echo "❌ aiohttp failed"; exit 1; }
python3 -c "import botbuilder.core; print('✓ botbuilder installed')" || { echo "❌ botbuilder failed"; exit 1; }
python3 -c "import openai; print('✓ openai installed')" || { echo "❌ openai failed"; exit 1; }
python3 -c "import tiktoken; print('✓ tiktoken installed')" || { echo "❌ tiktoken failed"; exit 1; }
python3 -c "import gunicorn; print('✓ gunicorn installed')" || { echo "❌ gunicorn failed"; exit 1; }

# Verify environment variables
echo "Checking environment variables..."
required_vars=(
    "MICROSOFT_APP_ID"
    "MICROSOFT_APP_PASSWORD"
    "AZURE_OPENAI_ENDPOINT"
    "AZURE_OPENAI_API_KEY"
    "AZURE_FUNCTION_URL"
    "AZURE_FUNCTION_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
        echo "❌ Missing: $var"
    else
        if [[ "$var" == *"KEY"* ]] || [[ "$var" == *"PASSWORD"* ]]; then
            echo "✓ $var: ***${!var: -4}"
        else
            echo "✓ $var: ${!var:0:30}..."
        fi
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "ERROR: Missing required environment variables: ${missing_vars[*]}"
    echo "Please configure these in Azure Portal -> App Service -> Configuration"
    exit 1
fi

# Verify main app can be imported
echo "Testing main app import..."
python3 -c "from app import APP; print('✓ Main SQL Assistant app loads successfully')" || {
    echo "❌ Failed to import main app"
    echo "Checking for import errors..."
    python3 -c "import app" 2>&1
    exit 1
}

# Test Azure Function connectivity (optional)
if [ -n "$AZURE_FUNCTION_URL" ] && [ -n "$AZURE_FUNCTION_KEY" ]; then
    echo "Testing Azure Function connectivity..."
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-functions-key: $AZURE_FUNCTION_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query_type":"metadata"}' \
        "$AZURE_FUNCTION_URL" \
        --max-time 10)
    
    if [ "$response" -eq 200 ]; then
        echo "✓ Azure Function is reachable"
    else
        echo "⚠ Azure Function returned status: $response"
        echo "  Bot will attempt connection at runtime"
    fi
fi

# Create a simple health check file
echo "{\"status\":\"deployed\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > health.json

echo "=== Deployment completed successfully ==="
echo "Starting application server..."

# Start the application
# Using exec to replace the shell process with gunicorn
exec python3 -m gunicorn \
    --bind 0.0.0.0:8000 \
    --worker-class aiohttp.GunicornWebWorker \
    --timeout 600 \
    --workers 1 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    app:APP