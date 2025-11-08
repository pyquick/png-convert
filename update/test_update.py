#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的更新测试脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """主函数 - 测试更新流程"""
    print("🔄 开始测试更新流程...")
    
    try:
        from update.update_manager import UpdateManager
        print("✅ 成功导入UpdateManager")
        
        # 获取当前版本
        current_version = "2.0.0RC1"
        print(f"📍 当前版本: {current_version}")
        
        # 创建更新管理器
        update_manager = UpdateManager(current_version)
        print("✅ 成功创建UpdateManager实例")
        
        # 检查更新
        update_info = update_manager.check_for_updates(include_prerelease=True)
        print(f"📊 更新信息: {update_info}")
        
        if not update_info:
            print("❌ 无法获取更新信息")
            return 1
        
        if update_info.get("status") != "update_available":
            print(f"✅ 已是最新版本: {update_info.get('message', 'Unknown')}")
            return 0
        
        print(f"📦 发现新版本: {update_info.get('latest_version', 'Unknown')}")
        
        # 测试下载功能
        try:
            from update.download_update import download_and_apply_update
            print("✅ 成功导入download_and_apply_update")
            
            # 定义进度回调函数
            def progress_callback(progress, downloaded, total):
                if total > 0:
                    percent = progress
                    print(f"⏳ 下载进度: {percent}% ({downloaded}/{total} bytes)")
                else:
                    print(f"⏳ 已下载: {downloaded} bytes")
            
            print("🚀 开始下载更新...")
            result = download_and_apply_update(update_info, progress_callback)
            print(f"📊 下载结果: {result}")
            
            if result["status"] == "success":
                print("✅ 更新下载成功，准备应用...")
                print("🔄 应用程序将退出并应用更新")
                return 0
            else:
                print(f"❌ 更新失败: {result.get('message', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ 下载更新失败: {e}")
            return 1
            
    except Exception as e:
        print(f"❌ 更新流程失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())