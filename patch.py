_application_output="./dist/Converter.app"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os

KEY = "com.apple.SwiftUI.IgnoreSolariumLinkedOnCheck"
def _run_defaults_write(target: str, yes_or_no: str) -> int:
    """
    内部函数：调用 defaults 写入布尔值
    target: bundle 标识，或 '-g' 代表全局
    yes_or_no: 'YES' 或 'NO'
    返回：进程返回码（0 成功）
    """
    # 保存当前工作目录
    original_cwd = os.getcwd()
    try:
        # 切换到 ./dist 目录执行命令
        #os.chdir("./dist")
        proc = subprocess.run(
            ["/usr/bin/defaults", "write", target, KEY, "-bool", yes_or_no],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return proc.returncode
    finally:
        # 确保总是返回原始工作目录
        os.chdir(original_cwd)

def enable(target: str) -> int:
    """
    启用“force liquid glass”：
    等价于 defaults write <target> com.apple.SwiftUI.IgnoreSolariumLinkedOnCheck -bool YES
    target: bundle 标识，或 '-g' 代表全局
    返回：0 成功，非 0 失败
    """
    return _run_defaults_write(target, "YES")

def disable(target: str) -> int:
    """
    禁用“force liquid glass”：
    等价于 defaults write <target> com.apple.SwiftUI.IgnoreSolariumLinkedOnCheck -bool NO
    target: bundle 标识，或 '-g' 代表全局
    返回：0 成功，非 0 失败
    """
    return _run_defaults_write(target, "NO")