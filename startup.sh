#!/bin/bash
# startup.sh - Main SQL Assistant Bot Startup Script

echo "=== SQL Assistant Bot Startup ==="
echo "Time: $(date)"
echo "Directory: $(pwd)"
echo "Running MAIN SQL Assistant (not test bot)"

cd /home/site/wwwroot

# Use Python 3.11
export PATH="/opt/python/3.11.12/bin:/opt/python/3.11/bin:$PATH"
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

echo "Python: $(which python3)"
echo "Python version: $(python3 --version)"

# Install packages if not already installed
if [ ! -d "/home/.local/lib/python3.11/site-packages/botbuilder" ]; then
    echo "Installing packages..."
    python3 -m pip install --user --upgrade pip
    python3 -m pip install --user -r requirements.txt
else
    echo "Packages already installed, skipping installation"
fi

# Add user site-packages to Python path
export PATH="$PATH:/home/.local/bin"
export PYTHONPATH="$PYTHONPATH:/home/.local/lib/python3.11/site-packages"

# Verify core packages
echo "Verifying packages..."
python3 -c "import aiohttp; print('✓ aiohttp installed')" || exit 1
python3 -c "import botbuilder.core; print('✓ botbuilder installed')" || exit 1
python3 -c "import openai; print('✓ openai installed')" || exit 1
python3 -c "import tiktoken; print('✓ tiktoken installed')" || exit 1
python3 -c "import gunicorn; print('✓ gunicorn installed')" || exit 1

# Create necessary directories
echo "Creating directories..."
mkdir -p .pattern_cache
mkdir -p .exploration_exports
mkdir -p .query_logs
mkdir -p .token_usage
mkdir -p logs

# Verify main app loads
echo "Testing main app import..."
python3 -c "from app import APP; print('✓ Main SQL Assistant app loads successfully')" || exit 1

# Start the MAIN app (not test bot!)
echo "Starting SQL Assistant Bot on port 8000..."
exec python3 -m gunicorn --bind 0.0.0.0:8000 --worker-class aiohttp.GunicornWebWorker --timeout 600 --workers 1 app:APP