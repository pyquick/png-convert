#!/bin/bash

# Complete update script - Terminate processes, download and apply updates

echo "🔄 Starting complete update process..."

# 1. Terminate related processes
echo "🛑 Terminating related processes..."
pkill -f "python3.*arc_gui.py" || true
pkill -f "Converter.app" || true
pkill -f "python.*Converter" || true

# Wait for processes to end
echo "⏳ Waiting for processes to end..."
sleep 3

# Force terminate still running processes
echo "🔨 Force terminating still running processes..."
pkill -9 -f "python3.*arc_gui.py" || true
pkill -9 -f "Converter.app" || true
pkill -9 -f "python.*Converter" || true

# Wait again
echo "⏳ Waiting again..."
sleep 2

# 2. Execute Python update script
echo "🚀 Starting to download and apply updates..."
cd /Users/li/Documents/GitHub/Converter
python3 -c "
import sys
import os
sys.path.insert(0, '.')

try:
    from update.update_manager import UpdateManager
    from update.download_update import download_and_apply_update
    
    print('🔄 Starting to check for updates...')
    
    # Get current version
    current_version = '2.1.0A10'
    print(f'📍 Current version: {current_version}')
    
    # Create update manager
    update_manager = UpdateManager(current_version)
    
    # Check for updates
    update_info = update_manager.check_for_updates(include_prerelease=True)
    
    if not update_info:
        print('❌ Unable to get update information')
        sys.exit(1)
    
    if update_info.get('status') != 'update_available':
        print(f'✅ Already up to date: {update_info.get(\"message\", \"Unknown\")}')
        sys.exit(0)
    
    print(f'📦 New version found: {update_info.get(\"latest_version\", \"Unknown\")}')
    
    # Define progress callback function
    def progress_callback(progress, downloaded, total):
        if total > 0:
            percent = progress
            print(f'⏳ Download progress: {percent}% ({downloaded}/{total} bytes)')
        else:
            print(f'⏳ Downloaded: {downloaded} bytes')
    
    print('🚀 Starting to download update...')
    result = download_and_apply_update(update_info, progress_callback)
    
    if result['status'] == 'success':
        print('✅ Update downloaded successfully, preparing to apply...')
        print('🔄 Application will exit and apply update')
        sys.exit(0)
    else:
        print(f'❌ Update failed: {result.get(\"message\", \"Unknown error\")}')
        sys.exit(1)
        
except Exception as e:
    print(f'❌ Update process failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# Check Python script execution result
if [ $? -eq 0 ]; then
    echo "✅ Update process completed successfully"
else
    echo "❌ Update process failed"
    exit 1
fi

echo "🎉 All update operations completed!"