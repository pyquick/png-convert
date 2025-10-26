#!/bin/bash

# 完整的更新脚本 - 终止进程、下载并应用更新

echo "🔄 开始完整更新流程..."

# 1. 终止相关进程
echo "🛑 终止相关进程..."
pkill -f "python3.*arc_gui.py" || true
pkill -f "Converter.app" || true
pkill -f "python.*Converter" || true

# 等待进程结束
echo "⏳ 等待进程结束..."
sleep 3

# 强制终止仍在运行的进程
echo "🔨 强制终止仍在运行的进程..."
pkill -9 -f "python3.*arc_gui.py" || true
pkill -9 -f "Converter.app" || true
pkill -9 -f "python.*Converter" || true

# 再次等待
echo "⏳ 再次等待..."
sleep 2

# 2. 执行Python更新脚本
echo "🚀 开始下载并应用更新..."
cd /Users/li/Documents/GitHub/Converter
python3 -c "
import sys
import os
sys.path.insert(0, '.')

try:
    from update.update_manager import UpdateManager
    from update.download_update import download_and_apply_update
    
    print('🔄 开始检查更新...')
    
    # 获取当前版本
    current_version = '2.0.0B7'
    print(f'📍 当前版本: {current_version}')
    
    # 创建更新管理器
    update_manager = UpdateManager(current_version)
    
    # 检查更新
    update_info = update_manager.check_for_updates(include_prerelease=True)
    
    if not update_info:
        print('❌ 无法获取更新信息')
        sys.exit(1)
    
    if update_info.get('status') != 'update_available':
        print(f'✅ 已是最新版本: {update_info.get(\"message\", \"Unknown\")}')
        sys.exit(0)
    
    print(f'📦 发现新版本: {update_info.get(\"latest_version\", \"Unknown\")}')
    
    # 定义进度回调函数
    def progress_callback(progress, downloaded, total):
        if total > 0:
            percent = progress
            print(f'⏳ 下载进度: {percent}% ({downloaded}/{total} bytes)')
        else:
            print(f'⏳ 已下载: {downloaded} bytes')
    
    print('🚀 开始下载更新...')
    result = download_and_apply_update(update_info, progress_callback)
    
    if result['status'] == 'success':
        print('✅ 更新下载成功，准备应用...')
        print('🔄 应用程序将退出并应用更新')
        sys.exit(0)
    else:
        print(f'❌ 更新失败: {result.get(\"message\", \"Unknown error\")}')
        sys.exit(1)
        
except Exception as e:
    print(f'❌ 更新流程失败: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# 检查Python脚本执行结果
if [ $? -eq 0 ]; then
    echo "✅ 更新流程成功完成"
else
    echo "❌ 更新流程失败"
    exit 1
fi

echo "🎉 所有更新操作已完成！"