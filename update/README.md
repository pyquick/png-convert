# 更新模块使用指南

## 概述

本模块提供了完整的应用程序更新功能，包括版本检查、更新下载和应用。模块包含两个主要组件：

- `UpdateManager`: 负责检查更新和版本管理
- `UpdateDownloader`: 负责下载和应用更新

## 文件结构

```
update/
├── update_manager.py    # 更新管理器 - 版本检查和更新信息获取
├── download_update.py    # 更新下载器 - 下载和应用更新
├── example_usage.py      # 使用示例代码
└── README.md            # 本文档
```

## 快速开始

### 1. 检查更新

```python
from update.update_manager import UpdateManager

# 初始化更新管理器
manager = UpdateManager("1.0.0")  # 传入当前版本号

# 检查更新（不包含预发布版本）
update_info = manager.check_for_updates(include_prerelease=False)

print(f"检查结果: {update_info}")
```

### 2. 下载和应用更新

```python
from update.download_update import download_and_apply_update

# 假设从UpdateManager获取到了更新信息
update_info = {
    "status": "update_available",
    "download_url": "https://github.com/user/repo/releases/tag/v2.1.0A2",
    "latest_version": "v2.1.0A2"  # 注意：需要完整的tag名称
}

# 下载并应用更新
target_directory = "."  # 目标安装目录
result = download_and_apply_update(update_info, target_directory)

print(f"下载结果: {result}")
```

## 完整工作流程示例

```python
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from update.update_manager import UpdateManager
from update.download_update import download_and_apply_update

def perform_update():
    """执行完整的更新流程"""
    
    # 1. 初始化
    current_version = "1.0.0"  # 从配置获取
    manager = UpdateManager(current_version)
    
    # 2. 检查更新
    print("正在检查更新...")
    update_info = manager.check_for_updates(include_prerelease=False)
    
    # 3. 处理结果
    if update_info["status"] == "update_available":
        print(f"发现新版本: {update_info['latest_version']}")
        
        # 4. 下载更新
        print("开始下载更新...")
        result = download_and_apply_update(update_info, ".")
        
        if result["status"] == "success":
            print("✅ 更新成功!")
            print("请重启应用程序")
        else:
            print(f"❌ 更新失败: {result['message']}")
            
    elif update_info["status"] == "latest":
        print("✅ 已是最新版本")
        
    else:
        print(f"ℹ️ {update_info['message']}")
```

## API 参考

### UpdateManager

#### `__init__(current_version: str)`
初始化更新管理器。

- `current_version`: 当前应用程序版本号（格式: "主版本.次版本.修订版本"）

#### `check_for_updates(include_prerelease: bool) -> dict`
检查可用更新。

- `include_prerelease`: 是否包含预发布版本
- 返回: 包含更新信息的字典

返回字典结构：
```python
{
    "status": "update_available" | "latest" | "no_updates" | "error",
    "message": "描述信息",
    "download_url": "下载页面URL",
    "latest_version": "最新版本号（完整的tag名称）"
}
```

### UpdateDownloader

#### `__init__(download_url: str, target_directory: str)`
初始化更新下载器。

- `download_url`: GitHub release页面URL
- `target_directory`: 目标安装目录

#### `download_update(tag_name: str) -> dict`
下载并应用更新。

- `tag_name`: 版本标签名称（如v2.1.0A2）

返回字典结构：
```python
{
    "status": "success" | "error",
    "message": "结果描述",
    "temp_dir": "临时目录路径"
}
```

### 工具函数

#### `download_and_apply_update(update_info: dict, target_directory: str) -> dict`
便捷函数，直接下载和应用更新。

## 版本格式支持

支持以下版本格式：
- `1.0.0` (稳定版)
- `1.0.0beta1` (Beta预发布版)
- `1.0.0B2` (Beta预发布版)
- `1.0.0alpha3` (Alpha预发布版)

## 错误处理

所有方法都返回包含状态信息的字典，建议检查 `status` 字段：

```python
result = download_and_apply_update(update_info, ".")

if result["status"] == "success":
    # 处理成功
else:
    # 处理失败
    print(f"错误: {result['message']}")
```

## 注意事项

1. **网络要求**: 需要互联网连接来检查更新和下载
2. **权限要求**: 需要目标目录的写入权限
3. **GitHub API限制**: 使用GitHub API，请注意速率限制
4. **临时文件**: 下载过程中会创建临时文件，完成后自动清理

## 开发说明

- 模块使用 `requests` 库进行HTTP请求
- 使用 `tempfile` 管理临时文件
- 使用 `zipfile` 和 `shutil` 处理文件操作
- 包含完整的错误处理和日志输出

## 测试

运行测试脚本：
```bash
python3 test_update_integration.py
python3 update/example_usage.py
```

## 许可证

MIT License