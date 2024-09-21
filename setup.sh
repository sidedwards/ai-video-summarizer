#!/bin/bash

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Copy example config file if config.yaml doesn't exist
if [ ! -f config/config.yaml ]; then
    cp config/config-example.yaml config/config.yaml
    echo "Created config/config.yaml. Please edit it with your actual configuration."
fi

echo "Setup complete. Activate the virtual environment with 'source venv/bin/activate'"

