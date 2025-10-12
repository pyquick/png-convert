#!/bin/bash

# Update Application Script - Copy update files to /Applications directory
# Copy update files to /Applications/ directory

# Set variables
TEMP_DIR="/tmp/converter_update"
TARGET_DIR="/Applications"
APP_NAME="Converter.app"

# Create target directory
mkdir -p "$TARGET_DIR"

# Check if system temporary directory is passed
if [ -n "$1" ] && [ -d "$1" ]; then
    # Use the passed temporary directory
    SYSTEM_TEMP_DIR="$1"
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

# Find extracted applications
EXTRACTED_DIRS=($(find "$TEMP_DIR" -maxdepth 1 -type d -name "*.app"))

if [ ${#EXTRACTED_DIRS[@]} -eq 0 ]; then
    echo "❌ No application found in temporary directory"
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
