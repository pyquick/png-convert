#!/bin/bash

# Restart Application Script
# Launch application from /Applications directory

TARGET_DIR="/Applications"
APP_NAME="Converter.app"

# Wait 2 seconds to ensure update script completes
sleep 2

# Launch application
echo "🚀 Launching application: $TARGET_DIR/$APP_NAME"
open "$TARGET_DIR/$APP_NAME"

echo "✅ Application has been launched"