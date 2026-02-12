#!/usr/bin/env python3
"""
Translation script for password_detector.py and update_manager.py
"""

import os

translations = {
    'support/password_detector.py': {
        '自动检测ZIP、RAR、7z格式压缩文件的密码保护状态': 'Automatically detect password protection status of ZIP, RAR, 7z archive files',
        '压缩文件密码检测器': 'Archive Password Detector',
        '支持格式：ZIP、RAR、7z': 'Supported formats: ZIP, RAR, 7z',
        '自动根据文件扩展名和文件头检测格式': 'Automatically detect format based on file extension and file header',
        '文件格式签名（魔数）': 'File format signatures (magic numbers)',
        '初始化密码检测器': 'Initialize password detector',
        '检测压缩文件格式': 'Detect archive file format',
        '压缩文件路径': 'Archive file path',
        "检测到的格式 ('zip', 'rar', '7z') 或 None": "Detected format ('zip', 'rar', '7z') or None",
        '方法1：通过文件扩展名检测': 'Method 1: Detect via file extension',
        '方法2：通过文件头签名检测（更准确）': 'Method 2: Detect via file header signature (more accurate)',
        '优先使用签名检测，如果失败则使用扩展名检测': 'Prioritize signature detection, fallback to extension detection if failed',
        '只返回支持的格式': 'Only return supported formats',
        '通过文件扩展名检测格式': 'Detect format via file extension',
        '通过文件头签名检测格式': 'Detect format via file header signature',
        '读取文件前20字节': 'Read first 20 bytes of file',
        '检测压缩文件是否受密码保护': 'Detect if archive file is password protected',
        '是否受密码保护': 'Whether password protected',
        '检测到的格式': 'Detected format',
        '错误信息（如果有）': 'Error message (if any)',
        '详细信息': 'Detailed information',
        '检测文件是否存在': 'Check if file exists',
        '文件不存在': 'File does not exist',
        '检测格式': 'Detect format',
        '不支持的压缩格式或无法识别的文件': 'Unsupported archive format or unrecognized file',
        '根据格式进行密码检测': 'Perform password detection based on format',
        '不支持的格式': 'Unsupported format',
        '检测失败': 'Detection failed',
    },
    'update/update_manager.py': {
        '支持 Alpha(A), Deepdev(D), Beta(B), RC, Stable 格式': 'Support Alpha(A), Deepdev(D), Beta(B), RC, Stable formats',
        '转换为大写统一处理': 'Convert to uppercase for uniform handling',
        '验证标签是否为支持的类型': 'Verify if tag is a supported type',
        '如果是不支持的标签，当作普通预发布版本处理': 'If unsupported tag, treat as regular pre-release version',
        '读取PAT设置': 'Read PAT settings',
        '如果有PAT，添加到headers': 'If PAT exists, add to headers',
        '如果指定了预发布版本类型，进行筛选': 'If pre-release type is specified, filter accordingly',
        '解析发布版本的标签': 'Parse release version tag',
        '建立预发布类型名称到标签字母的映射': 'Build mapping from pre-release type name to tag letter',
        '将用户输入的预发布类型转换为对应的标签字母': 'Convert user input pre-release type to corresponding tag letter',
        '统一大小写比较，避免大小写不匹配问题': 'Case-insensitive comparison to avoid case mismatch issues',
        '添加版本信息用于UI显示': 'Add version info for UI display',
        '预发布版本优先级：Stable > RC > Beta > Deepdev > Alpha': 'Pre-release version priority: Stable > RC > Beta > Deepdev > Alpha',
        '如果优先级相同，按字母顺序比较': 'If same priority, compare alphabetically',
        '将标签转换回原始格式': 'Convert tag back to original format',
        '获取版本类型的友好名称': 'Get friendly name for version type',
        '支持传入元组或单个标签': 'Support passing tuple or single tag',
        '获取GitHub PAT': 'Get GitHub PAT',
        '解密后的PAT，如果没有设置则返回空字符串': 'Decrypted PAT, returns empty string if not set',
        '获取PAT失败': 'Failed to get PAT',
    },
}

def translate_file(filepath, mapping):
    """Translate Chinese to English in a file"""
    full_path = os.path.join('/Users/ghltbm/Documents/Converter', filepath)
    if not os.path.exists(full_path):
        print(f"File not found: {full_path}")
        return
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    for chinese, english in mapping.items():
        content = content.replace(chinese, english)
    
    if content != original_content:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Translated: {filepath}")
    else:
        print(f"No changes needed: {filepath}")

def main():
    for filename, mapping in translations.items():
        translate_file(filename, mapping)

if __name__ == '__main__':
    main()
