#!/bin/bash

# Simple Converter script for PNG to ICNS Converter
# This script can be used as an alternative to a compiled .app bundle

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if requirements.txt exists and install dependencies if needed
if [ -f "requirements.txt" ]; then
    echo "Checking dependencies..."
    python3.14 -c "import PIL" 2>/dev/null || {
        echo "Installing required dependencies..."
        pip3.13 install -r requirements.txt
    }
fi

# Run the Python application
echo "Starting PNG to ICNS Converter..."
echo ""

python3.14 Converter.py

# Check if the command was successful
if [ $? -eq 0 ]; then
    echo "Application closed successfully."
else
    echo "Application failed to start."
    echo "Please make sure you have Python 3 and Pillow installed:"
    echo "pip3 install -r requirements.txt"
    echo ""
    echo "Press any key to exit..."
    read -n 1 -s
fi