#!/usr/bin/env python3
"""
创建一个受密码保护的ZIP文件用于测试
"""

import os
import tempfile
import zipfile
import subprocess

def create_protected_zip():
    """创建一个受密码保护的ZIP文件"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "protected_test.zip")
    
    # 创建一个临时文本文件
    test_file = os.path.join(temp_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("This is a test file in a password-protected ZIP archive.")
    
    # 创建ZIP文件并添加密码保护
    password = "test123"
    
    try:
        # 尝试使用zip命令创建受密码保护的ZIP
        subprocess.run([
            'zip', '-r', '-P', password, zip_path, test_file
        ], check=True, capture_output=True)
        print(f"已创建受密码保护的ZIP文件: {zip_path}")
        print(f"密码: {password}")
        print(f"测试文件: {test_file}")
        return zip_path, password
    except (subprocess.CalledProcessError, FileNotFoundError):
        # 如果zip命令不可用，使用Python的zipfile库
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.setpassword(password.encode())
            zf.write(test_file, "test.txt")
        print(f"已创建受密码保护的ZIP文件: {zip_path}")
        print(f"密码: {password}")
        print(f"测试文件: {test_file}")
        return zip_path, password

if __name__ == "__main__":
    create_protected_zip()