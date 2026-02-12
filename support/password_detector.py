#!/usr/bin/env python3
"""
Archive Password Detector
Automatically detect password protection status of ZIP, RAR, 7z archive files
"""

import os
import zipfile
import rarfile
import py7zr
import tempfile
from typing import Optional, Dict, Any


class PasswordDetector:
    """
    Archive Password Detector
    
    Supported formats: ZIP, RAR, 7z
    Automatically detect format based on file extension and file header
    """
    
    SUPPORTED_FORMATS = ['zip', 'rar', '7z']
    
    # File format signatures (magic numbers)
    FORMAT_SIGNATURES = {
        'zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
        'rar': [b'Rar!\x1a\x07\x00', b'Rar!\x1a\x07\x01\x00'],
        '7z': [b'7z\xbc\xaf\x27\x1c']
    }
    
    def __init__(self):
        """Initialize password detector"""
        self._temp_dir = None
    
    def detect_format(self, file_path: str) -> Optional[str]:
        """
        Detect archive file format
        
        Args:
            file_path: Archive file path
            
        Returns:
            str: Detected format ('zip', 'rar', '7z') or None
        """
        if not os.path.exists(file_path):
            return None
            
        # Method 1: Detect via file extension
        ext_format = self._detect_format_by_extension(file_path)
        
        # Method 2: Detect via file header signature (more accurate)
        signature_format = self._detect_format_by_signature(file_path)
        
        # Prioritize signature detection, fallback to extension detection if failed
        detected_format = signature_format or ext_format
        
        # Only return supported formats
        return detected_format if detected_format in self.SUPPORTED_FORMATS else None
    
    def _detect_format_by_extension(self, file_path: str) -> Optional[str]:
        """Detect format via file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        
        format_map = {
            '.zip': 'zip',
            '.rar': 'rar',
            '.7z': '7z'
        }
        
        return format_map.get(ext)
    
    def _detect_format_by_signature(self, file_path: str) -> Optional[str]:
        """Detect format via file header signature"""
        try:
            with open(file_path, 'rb') as f:
                # Read first 20 bytes of file
                header = f.read(20)
                
                for format_name, signatures in self.FORMAT_SIGNATURES.items():
                    for signature in signatures:
                        if header.startswith(signature):
                            return format_name
                            
        except (IOError, OSError):
            pass
            
        return None
    
    def is_password_protected(self, file_path: str) -> Dict[str, Any]:
        """
        Detect if archive file is password protected
        
        Args:
            file_path: Archive file path
            
        Returns:
            dict: 检测结果 {
                'is_protected': bool,  # Whether password protected
                'format': str,         # Detected format
                'error': str,          # Error message (if any)
                'details': dict        # Detailed information
            }
        """
        result = {
            'is_protected': False,
            'format': None,
            'error': None,
            'details': {}
        }
        
        # Check if file exists
        if not os.path.exists(file_path):
            result['error'] = f"File does not exist: {file_path}"
            return result
        
        # Detect format
        detected_format = self.detect_format(file_path)
        if not detected_format:
            result['error'] = f"Unsupported archive format or unrecognized file: {file_path}"
            return result
            
        result['format'] = detected_format
        
        # Perform password detection based on format
        try:
            if detected_format == 'zip':
                result.update(self._check_zip_password_protection(file_path))
            elif detected_format == 'rar':
                result.update(self._check_rar_password_protection(file_path))
            elif detected_format == '7z':
                result.update(self._check_7z_password_protection(file_path))
            else:
                result['error'] = f"Unsupported format: {detected_format}"
                
        except Exception as e:
            result['error'] = f"Detection failed: {str(e)}"
            
        return result
    
    def _check_zip_password_protection(self, file_path: str) -> Dict[str, Any]:
        """检测ZIP文件密码保护状态"""
        result = {'is_protected': False, 'details': {}}
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                # 检查是否有加密的文件
                encrypted_files = []
                total_files = len(zipf.infolist())
                
                for info in zipf.infolist():
                    # 检查加密标志位
                    if info.flag_bits & 0x1:  # 通用加密标志
                        encrypted_files.append(info.filename)
                    # 检查CRC32和压缩大小来判断是否加密
                    elif info.CRC == 0 and info.compress_size == 0 and info.file_size == 0:
                        # 可能是加密的空文件，需要进一步验证
                        try:
                            # 尝试不使用密码读取
                            zipf.open(info.filename).read(1)
                        except RuntimeError as e:
                            if 'password required' in str(e).lower() or 'encrypted' in str(e).lower():
                                encrypted_files.append(info.filename)
                
                # 如果没有发现加密文件，尝试读取文件内容来确认
                if not encrypted_files and total_files > 0:
                    try:
                        # 尝试读取第一个文件
                        first_file = zipf.infolist()[0]
                        zipf.open(first_file.filename).read(1)
                    except RuntimeError as e:
                        if 'password required' in str(e).lower() or 'encrypted' in str(e).lower():
                            result['is_protected'] = True
                            result['details']['password_required'] = True
                
                result['is_protected'] = len(encrypted_files) > 0 or result.get('is_protected', False)
                result['details'] = {
                    'total_files': total_files,
                    'encrypted_files': len(encrypted_files),
                    'encrypted_file_names': encrypted_files[:10]  # 最多显示10个文件名
                }
                
        except zipfile.BadZipFile:
            result['error'] = '无效的ZIP文件'
        except Exception as e:
            result['error'] = f'ZIPDetection failed: {str(e)}'
            
        return result
    
    def _check_rar_password_protection(self, file_path: str) -> Dict[str, Any]:
        """检测RAR文件密码保护状态"""
        result = {'is_protected': False, 'details': {}}
        
        try:
            with rarfile.RarFile(file_path) as rarf:
                # 尝试不使用密码列出文件
                try:
                    rarf.namelist()
                    result['is_protected'] = False
                except rarfile.RarCannotExec as e:
                    if 'password' in str(e).lower():
                        result['is_protected'] = True
                        result['details']['password_required'] = True
                    else:
                        raise
                except Exception as e:
                    if 'password' in str(e).lower() or 'encrypted' in str(e).lower():
                        result['is_protected'] = True
                        result['details']['password_required'] = True
                    else:
                        raise
                        
                result['details']['total_files'] = len(rarf.infolist()) if hasattr(rarf, 'infolist') else 'unknown'
                
        except Exception as e:
            result['error'] = f'RARDetection failed: {str(e)}'
            
        return result
    
    def _check_7z_password_protection(self, file_path: str) -> Dict[str, Any]:
        """检测7Z文件密码保护状态"""
        result = {'is_protected': False, 'details': {}}
        
        try:
            with py7zr.SevenZipFile(file_path, mode='r') as szf:
                # 检查是否需要密码
                if szf.needs_password():
                    result['is_protected'] = True
                    result['details']['password_required'] = True
                else:
                    # 尝试列出文件内容
                    try:
                        file_list = szf.list()
                        result['is_protected'] = False
                        result['details']['total_files'] = len(file_list)
                    except Exception as e:
                        if 'password' in str(e).lower():
                            result['is_protected'] = True
                            result['details']['password_required'] = True
                        else:
                            raise
                            
        except Exception as e:
            result['error'] = f'7ZDetection failed: {str(e)}'
            
        return result
    
    def verify_password(self, file_path: str, password: str) -> Dict[str, Any]:
        """
        验证压缩文件密码是否正确
        
        Args:
            file_path: Archive file path
            password: 待验证的密码
            
        Returns:
            dict: 验证结果 {
                'is_valid': bool,      # 密码是否正确
                'format': str,         # 文件格式
                'error': str,          # Error message (if any)
                'details': dict        # Detailed information
            }
        """
        result = {
            'is_valid': False,
            'format': None,
            'error': None,
            'details': {}
        }
        
        # 先检测文件格式和密码保护状态
        detection_result = self.is_password_protected(file_path)
        
        if detection_result['error']:
            result['error'] = detection_result['error']
            return result
            
        if not detection_result['is_protected']:
            result['error'] = '文件不受密码保护'
            return result
            
        result['format'] = detection_result['format']
        
        # 验证密码
        try:
            if result['format'] == 'zip':
                result.update(self._verify_zip_password(file_path, password))
            elif result['format'] == 'rar':
                result.update(self._verify_rar_password(file_path, password))
            elif result['format'] == '7z':
                result.update(self._verify_7z_password(file_path, password))
                
        except Exception as e:
            result['error'] = f'密码验证失败: {str(e)}'
            
        return result
    
    def _verify_zip_password(self, file_path: str, password: str) -> Dict[str, Any]:
        """验证ZIP文件密码"""
        result = {'is_valid': False, 'details': {}}
        
        try:
            # 使用pyzipper验证密码
            try:
                import pyzipper
                with pyzipper.AESZipFile(file_path, 'r') as zipf:
                    # 设置密码
                    zipf.pwd = password.encode()
                    # 尝试列出文件
                    file_list = zipf.namelist()
                    if file_list:
                        # 尝试读取第一个文件
                        first_file = file_list[0]
                        with zipf.open(first_file) as f:
                            f.read(1)  # 读取1字节验证密码
                        result['is_valid'] = True
                        result['details']['verified_file'] = first_file
                        result['details']['file_count'] = len(file_list)
            except ImportError:
                # 如果没有pyzipper，使用标准zipfile尝试验证
                with zipfile.ZipFile(file_path, 'r') as zipf:
                    # 设置密码
                    zipf.setpassword(password.encode())
                    
                    # 尝试读取第一个加密文件的信息
                    encrypted_files = [info for info in zipf.infolist() if info.flag_bits & 0x1]
                    
                    if encrypted_files:
                        # 尝试读取文件头部来验证密码
                        first_file = encrypted_files[0]
                        try:
                            zipf.open(first_file).read(1)  # 只读取1字节
                            result['is_valid'] = True
                            result['details']['verified_file'] = first_file.filename
                        except (RuntimeError, zipfile.BadZipFile):
                            result['is_valid'] = False
                            result['details']['failed_file'] = first_file.filename
                            
        except Exception as e:
            result['error'] = f'ZIP密码验证失败: {str(e)}'
            
        return result
    
    def _verify_rar_password(self, file_path: str, password: str) -> Dict[str, Any]:
        """验证RAR文件密码"""
        result = {'is_valid': False, 'details': {}}
        
        try:
            with rarfile.RarFile(file_path) as rarf:
                # 设置密码
                rarf.setpassword(password)
                
                # 尝试列出文件
                try:
                    file_list = rarf.namelist()
                    result['is_valid'] = True
                    result['details']['file_count'] = len(file_list)
                except Exception as e:
                    result['is_valid'] = False
                    if 'password' in str(e).lower():
                        result['details']['error_type'] = 'incorrect_password'
                    else:
                        result['details']['error_type'] = str(e)
                        
        except Exception as e:
            result['error'] = f'RAR密码验证失败: {str(e)}'
            
        return result
    
    def _verify_7z_password(self, file_path: str, password: str) -> Dict[str, Any]:
        """验证7Z文件密码"""
        result = {'is_valid': False, 'details': {}}
        
        # 空密码检查
        if not password:
            result['is_valid'] = False
            result['details']['error_type'] = 'empty_password'
            return result
            
        try:
            with py7zr.SevenZipFile(file_path, mode='r', password=password) as szf:
                # 尝试列出文件
                try:
                    file_list = szf.list()
                    # 检查是否真的获取到了文件列表
                    if file_list and len(file_list) > 0:
                        # 进一步验证：尝试提取第一个文件
                        try:
                            # 创建临时目录用于提取
                            import tempfile
                            with tempfile.TemporaryDirectory() as temp_dir:
                                # 尝试提取文件
                                szf.extract(path=temp_dir)
                                # 检查文件是否成功提取
                                first_file_path = os.path.join(temp_dir, file_list[0].filename)
                                if os.path.exists(first_file_path):
                                    # 文件成功提取，密码正确
                                    result['is_valid'] = True
                                    result['details']['file_count'] = len(file_list)
                                    result['details']['first_file'] = file_list[0].filename
                                else:
                                    # 文件未提取，可能是密码错误
                                    result['is_valid'] = False
                                    result['details']['error_type'] = 'file_not_extracted'
                        except Exception as extract_e:
                            # 提取文件时出错，可能是密码错误
                            result['is_valid'] = False
                            error_msg = str(extract_e).lower()
                            if any(keyword in error_msg for keyword in ['corrupt', 'password', 'incorrect', 'wrong', 'bad', 'authentication', 'invalid', 'cipher']):
                                result['details']['error_type'] = 'incorrect_password'
                            else:
                                result['details']['error_type'] = 'extraction_failed'
                                result['details']['extraction_error'] = str(extract_e)
                    else:
                        # 如果文件列表为空，可能是密码错误
                        result['is_valid'] = False
                        result['details']['error_type'] = 'empty_file_list'
                except Exception as e:
                    result['is_valid'] = False
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['password', 'incorrect', 'wrong', 'bad', 'authentication', 'invalid', 'cipher']):
                        result['details']['error_type'] = 'incorrect_password'
                    else:
                        result['details']['error_type'] = str(e)
                        
        except Exception as e:
            result['is_valid'] = False
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['password', 'incorrect', 'wrong', 'bad', 'authentication', 'invalid', 'cipher', 'corrupt']):
                result['details']['error_type'] = 'incorrect_password'
            else:
                result['error'] = f'7Z密码验证失败: {str(e)}'
            
        return result
    
    def get_supported_formats(self) -> list:
        """获取支持的格式列表"""
        return self.SUPPORTED_FORMATS.copy()
    
    def get_format_info(self, file_path: str) -> Dict[str, Any]:
        """
        获取压缩文件格式信息
        
        Args:
            file_path: Archive file path
            
        Returns:
            dict: 格式信息
        """
        result = {
            'file_path': file_path,
            'format': None,
            'format_by_extension': None,
            'format_by_signature': None,
            'confidence': 'low',
            'error': None
        }
        
        if not os.path.exists(file_path):
            result['error'] = 'File does not exist'
            return result
            
        # 通过扩展名检测
        result['format_by_extension'] = self._detect_format_by_extension(file_path)
        
        # 通过签名检测
        result['format_by_signature'] = self._detect_format_by_signature(file_path)
        
        # 确定最终格式
        if result['format_by_signature']:
            result['format'] = result['format_by_signature']
            result['confidence'] = 'high'
        elif result['format_by_extension']:
            result['format'] = result['format_by_extension']
            result['confidence'] = 'medium'
        else:
            result['confidence'] = 'none'
            
        return result


# 全局密码检测器实例
password_detector = PasswordDetector()


def detect_password_protection(file_path: str) -> bool:
    """
    快速Detect if archive file is password protected
    
    Args:
        file_path: Archive file path
        
    Returns:
        bool: Whether password protected
    """
    result = password_detector.is_password_protected(file_path)
    return result.get('is_protected', False)


def verify_archive_password(file_path: str, password: str) -> bool:
    """
    验证压缩文件密码是否正确
    
    Args:
        file_path: Archive file path
        password: 待验证的密码
        
    Returns:
        bool: 密码是否正确
    """
    result = password_detector.verify_password(file_path, password)
    return result.get('is_valid', False)


def get_archive_format(file_path: str) -> Optional[str]:
    """
    获取压缩文件格式
    
    Args:
        file_path: Archive file path
        
    Returns:
        str: 文件格式或None
    """
    return password_detector.detect_format(file_path)


# 测试函数
def test_password_detector():
    """测试密码检测器"""
    import tempfile
    import os
    
    print("=== 测试密码检测器 ===")
    
    # 创建测试文件
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("这是一个测试文件，用于测试密码检测功能。")
        
        # 测试不同格式
        formats_to_test = ['zip']  # 先测试ZIP格式
        
        for fmt in formats_to_test:
            print(f"\n--- 测试 {fmt.upper()} 格式 ---")
            
            # 创建普通压缩文件
            normal_archive = os.path.join(temp_dir, f"normal.{fmt}")
            try:
                if fmt == 'zip':
                    with zipfile.ZipFile(normal_archive, 'w') as zf:
                        zf.write(test_file, os.path.basename(test_file))
                
                # 检测普通文件
                result = password_detector.is_password_protected(normal_archive)
                print(f"普通{fmt.upper()}: {'受密码保护' if result['is_protected'] else '不受密码保护'}")
                print(f"格式: {result['format']}")
                if result['error']:
                    print(f"错误: {result['error']}")
                
            except Exception as e:
                print(f"创建普通{fmt.upper()}文件失败: {e}")
            
            # 创建密码保护压缩文件
            protected_archive = os.path.join(temp_dir, f"protected.{fmt}")
            try:
                if fmt == 'zip':
                    with zipfile.ZipFile(protected_archive, 'w') as zf:
                        info = zipfile.ZipInfo(os.path.basename(test_file))
                        info.flag_bits |= 0x1  # 设置密码保护标志
                        zf.writestr(info, "这是一个受密码保护的文件内容")
                
                # 检测密码保护文件
                result = password_detector.is_password_protected(protected_archive)
                print(f"密码保护{fmt.upper()}: {'受密码保护' if result['is_protected'] else '不受密码保护'}")
                print(f"格式: {result['format']}")
                print(f"Detailed information: {result['details']}")
                if result['error']:
                    print(f"错误: {result['error']}")
                
                # 验证密码
                if result['is_protected']:
                    verify_result = password_detector.verify_password(protected_archive, "test123")
                    print(f"密码验证: {'正确' if verify_result['is_valid'] else '错误'}")
                    if verify_result['error']:
                        print(f"验证错误: {verify_result['error']}")
                
            except Exception as e:
                print(f"创建密码保护{fmt.upper()}文件失败: {e}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_password_detector()