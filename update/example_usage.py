#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UpdateDownloader 使用示例
演示如何与UpdateManager配合使用下载功能
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update.update_manager import UpdateManager
from update.download_update import download_and_apply_update

def example_update_workflow():
    """
    完整的更新工作流程示例
    """
    print("=== 应用程序更新工作流程示例 ===")
    
    # 1. 初始化更新管理器
    current_version = "2.0.0B4"  # 从配置文件或代码中获取当前版本
    manager = UpdateManager(current_version)
    
    print(f"当前应用程序版本: {current_version}")
    
    # 2. 检查更新
    print("\n1. 正在检查更新...")
    update_info = manager.check_for_updates(include_prerelease=True)
    
    # 3. 处理检查结果
    if update_info["status"] == "update_available":
        print(f"✅ 发现新版本: {update_info['latest_version']}")
        print(f"📝 更新说明: {update_info['message']}")
        print(f"🔗 下载页面: {update_info['download_url']}")
        
        # 4. 询问用户是否下载更新
        user_input = input("\n是否下载并安装此更新? (y/n): ").strip().lower()
        
        if user_input in ['y', 'yes']:
            print("\n2. 开始下载更新...")
            
            # 5. 下载并应用更新
            # 目标目录设置为/Applications目录
            target_directory = "/Applications"  # 在实际应用中应该是应用程序目录
            
            download_result = download_and_apply_update(update_info, target_directory)
            
            if download_result["status"] == "success":
                print("✅ 更新成功完成!")
                print(f"📋 消息: {download_result['message']}")
                print("🔄 请重启应用程序以应用更新")
            else:
                print("❌ 更新失败")
                print(f"📋 错误信息: {download_result['message']}")
        else:
            print("⏸️ 用户取消更新")
            
    elif update_info["status"] == "latest":
        print("✅ 您正在运行最新版本")
        print(f"📋 {update_info['message']}")
        
    elif update_info["status"] == "no_updates":
        print("ℹ️ 没有找到可用更新")
        print(f"📋 {update_info['message']}")
        
    elif update_info["status"] == "error":
        print("❌ 检查更新时发生错误")
        print(f"📋 错误信息: {update_info['message']}")
    
    print("\n=== 工作流程结束 ===")


def quick_download_example():
    """
    快速下载示例 - 直接使用下载功能
    """
    print("\n=== 快速下载示例 ===")
    
    # 直接使用下载功能（需要提供完整的更新信息）
    test_update_info = {
        "status": "update_available",
        "message": "测试更新",
        "download_url": "https://github.com/pyquick/converter/releases/tag/v2.0.0",
        "latest_version": "v2.0.0"  # 注意：这里需要完整的tag名称
    }
    
    print("开始测试下载功能...")
    
    # 使用测试目录
    test_dir = "./test_download"
    result = download_and_apply_update(test_update_info, test_dir)
    
    print(f"下载结果: {result}")
    
    # 清理测试目录
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)
        print(f"已清理测试目录: {test_dir}")


if __name__ == "__main__":
    # 运行完整的工作流程示例
    example_update_workflow()
    
    # 运行快速下载示例（取消注释以测试）
    # quick_download_example()