#!/usr/bin/env python3
"""
Translation script to convert all Chinese comments to English
"""

import os
import re

# Translation mappings for each file
translations = {
    'image_converter.py': {
        '初始化或重置所有变量': 'Initialize or reset all variables',
        '允许用户手动输入路径': 'Allow users to manually input path',
        '不允许用户手动输入信息': 'Do not allow users to manually input information',
        '使用更灵活的高度设置，允许根据内容自动调整': 'Use more flexible height settings, allowing automatic adjustment based on content',
        '使用新的拖拽支持输入框': 'Use new drag-and-drop supported input field',
        '使用更灵活的尺寸策略': 'Use more flexible sizing strategy',
        '使用更灵活的尺寸策略而不是固定最小尺寸': 'Use more flexible sizing strategy instead of fixed minimum size',
    },
    'arc_gui.py': {
        '取消操作': 'Cancel Operation',
        '确定要取消当前的': 'Are you sure you want to cancel the current ',
        '操作吗？': ' operation?',
        '归档创建': 'Archive Creation',
        '归档解压': 'Archive Extraction',
        '添加到归档': 'Add to Archive',
        '列出内容': 'List Contents',
        '强制清理创建归档的线程，确保完全终止': 'Force cleanup archive creation thread to ensure complete termination',
        '强制清理线程，确保完全终止': 'Force cleanup thread to ensure complete termination',
        '强制清理添加到归档的线程，确保完全终止': 'Force cleanup add to archive thread to ensure complete termination',
        '强制清理列出归档内容的线程，确保完全终止': 'Force cleanup list archive contents thread to ensure complete termination',
        '先尝试正常退出': 'First try to exit normally',
        '如果正常退出失败，强制终止': 'If normal exit fails, force terminate',
        '等待0.5秒': 'Wait 0.5 seconds',
        '再等待0.5秒': 'Wait another 0.5 seconds',
        '删除线程对象': 'Delete thread object',
        '删除worker对象': 'Delete worker object',
        '循环提示用户输入密码，直到输入正确的密码或取消': 'Loop prompting user for password until correct password is entered or cancelled',
        '对于非密码错误，确保线程被正确清理': 'For non-password errors, ensure thread is properly cleaned up',
        '使用强制线程清理方法': 'Use forced thread cleanup method',
        '清理可能存在的旧线程': 'Clean up any existing old threads',
        '确保线程被正确清理': 'Ensure thread is properly cleaned up',
        '强制终止之前的线程': 'Force terminate previous thread',
        '创建新的工作线程': 'Create new worker thread',
        '连接信号': 'Connect signals',
        '启动线程': 'Start thread',
    },
    'support/archive_manager.py': {
        '检查异常信息是否包含密码相关关键词': 'Check if exception message contains password-related keywords',
        '为解压出的可执行文件添加执行权限': 'Add execute permissions for extracted executable files',
        '权限设置失败不应该影响解压结果，只是记录警告': 'Permission setting failure should not affect extraction result, just log warning',
    },
}

def translate_file(filepath, mapping):
    """Translate Chinese to English in a file"""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    for chinese, english in mapping.items():
        content = content.replace(chinese, english)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Translated: {filepath}")
    else:
        print(f"No changes needed: {filepath}")

def main():
    base_dir = '/Users/ghltbm/Documents/Converter'
    
    for filename, mapping in translations.items():
        filepath = os.path.join(base_dir, filename)
        translate_file(filepath, mapping)

if __name__ == '__main__':
    main()
