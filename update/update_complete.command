#!/bin/bash

# Complete Update Script - Kill processes, extract update files and copy to /Applications directory
# Usage: update_complete.command [temp_update_dir]
# If temp_update_dir is provided, use it as the source directory, otherwise use the default path

echo "🔄 Starting complete update process..."

# Get the temporary update directory from the first parameter, if provided
TEMP_UPDATE_DIR="$1"
if [ -z "$TEMP_UPDATE_DIR" ]; then
    # If no parameter is provided, use the default temporary directory
    TEMP_UPDATE_DIR="/tmp/converter_update"
fi

echo "🔄 Applying update from: $TEMP_UPDATE_DIR"

# Set variables
TEMP_DIR="/tmp/converter_update"
TARGET_DIR="/Applications"
APP_NAME="Converter.app"

# Create target directory
mkdir -p "$TARGET_DIR"

# Kill all Python processes related to Converter
echo "🛑 Terminating Python processes related to Converter..."
pkill -f "python.*arc_gui.py" 2>/dev/null || true
pkill -f "python.*Converter.py" 2>/dev/null || true
pkill -f "python.*converter" 2>/dev/null || true

# Kill Converter.app processes
echo "🛑 Terminating Converter.app processes..."
pkill -f "Converter.app" 2>/dev/null || true
pkill -f "com.intsant.converter" 2>/dev/null || true

# Wait for processes to fully terminate
echo "⏳ Waiting for processes to terminate..."
sleep 3

# Force kill any remaining processes
echo "🔨 Force killing any remaining processes..."
pkill -9 -f "python.*arc_gui.py" 2>/dev/null || true
pkill -9 -f "python.*Converter.py" 2>/dev/null || true
pkill -9 -f "python.*converter" 2>/dev/null || true
pkill -9 -f "Converter.app" 2>/dev/null || true
pkill -9 -f "com.intsant.converter" 2>/dev/null || true

# Wait again
sleep 2

# Check if system temporary directory is passed
if [ -n "$TEMP_UPDATE_DIR" ] && [ -d "$TEMP_UPDATE_DIR" ]; then
    # Use the passed temporary directory
    SYSTEM_TEMP_DIR="$TEMP_UPDATE_DIR"
    echo "📦 Using system temporary directory: $SYSTEM_TEMP_DIR"
    
    # Copy system temporary directory contents to TEMP_DIR
    echo "📋 Copying update files to $TEMP_DIR..."
    mkdir -p "$TEMP_DIR"
    cp -R "$SYSTEM_TEMP_DIR/"* "$TEMP_DIR/" 2>/dev/null || true
    
    # Clean up system temporary directory
    rm -rf "$SYSTEM_TEMP_DIR"
    echo "✅ System temporary directory cleaned up"
else
    # Check if temporary directory exists
    if [ ! -d "$TEMP_DIR" ]; then
        echo "❌ Temporary update directory does not exist: $TEMP_DIR, need to create temporary directory"
        mkdir -p "$TEMP_DIR"
    fi
fi

# Check if there are ZIP files in the temporary directory
ZIP_FILES=($(find "$TEMP_DIR" -maxdepth 1 -type f -name "*.zip"))

if [ ${#ZIP_FILES[@]} -gt 0 ]; then
    echo "📦 Found ZIP files, extracting..."
    for ZIP_FILE in "${ZIP_FILES[@]}"; do
        echo "📂 Extracting: $ZIP_FILE"
        # Create a subdirectory for extraction
        EXTRACT_DIR="$TEMP_DIR/extracted_$(basename "$ZIP_FILE" .zip)"
        mkdir -p "$EXTRACT_DIR"
        # Extract the ZIP file
        unzip -q "$ZIP_FILE" -d "$EXTRACT_DIR"
        echo "✅ Extracted to: $EXTRACT_DIR"
    done
fi

# Find extracted applications
EXTRACTED_DIRS=($(find "$TEMP_DIR" -maxdepth 2 -type d -name "*.app"))

if [ ${#EXTRACTED_DIRS[@]} -eq 0 ]; then
    echo "❌ No application found in temporary directory"
    echo "📋 Contents of temporary directory:"
    ls -la "$TEMP_DIR"
    exit 1
fi

# Get the first found .app directory
SOURCE_APP="${EXTRACTED_DIRS[0]}"
echo "📦 Found update application: $SOURCE_APP"

# Set executable file permissions
echo "🔧 Setting executable file permissions..."
find "$SOURCE_APP" -name "*.app" -exec chmod -R 755 {} \;
find "$SOURCE_APP" -path "*/Contents/MacOS/*" -exec chmod +x {} \;

# Special permission for Converter executable
if [ -f "$SOURCE_APP/Contents/MacOS/Converter" ]; then
    chmod +x "$SOURCE_APP/Contents/MacOS/Converter"
    echo "✅ Set executable permission for Converter"
fi

# Backup current application (if exists)
if [ -d "$TARGET_DIR/$APP_NAME" ]; then
    BACKUP_DIR="$TARGET_DIR/${APP_NAME}.backup.$(date +%Y%m%d%H%M%S)"
    echo "🗂️  Backing up current application to: $BACKUP_DIR"
    mv "$TARGET_DIR/$APP_NAME" "$BACKUP_DIR"
fi

# Remove old program from target directory
echo "🗑️  Cleaning target directory..."
rm -rf "$TARGET_DIR/$APP_NAME"

# Copy new program to target directory
echo "📋 Copying new application to $TARGET_DIR..."
cp -R "$SOURCE_APP" "$TARGET_DIR/"

# Ensure permissions are correct again
chmod -R 755 "$TARGET_DIR/$APP_NAME"
find "$TARGET_DIR/$APP_NAME" -path "*/Contents/MacOS/*" -exec chmod +x {} \;

if [ -f "$TARGET_DIR/$APP_NAME/Contents/MacOS/Converter" ]; then
    chmod +x "$TARGET_DIR/$APP_NAME/Contents/MacOS/Converter"
fi

# Also copy to user directory for restart script
USER_TARGET_DIR="$HOME/.converter/update/com"
mkdir -p "$USER_TARGET_DIR"
echo "📋 Also copying to user directory: $USER_TARGET_DIR"
cp -R "$SOURCE_APP" "$USER_TARGET_DIR/"

echo "✅ Update completed! Application has been updated to: $TARGET_DIR/$APP_NAME"
echo "🚀 You can now launch the application from /Applications/Converter.app"