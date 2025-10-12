import os
import zipfile
import tarfile
import platform
from pathlib import Path
import tempfile
import shutil
import subprocess
import time

# Define supported formats
SUPPORTED_ARCHIVE_FORMATS = [
    "zip", "rar", "7z", "tar", "tar.gz", "bz2", "tar.bz2", 
    "xz", "tar.xz", "lzma", "zipx", "iso", "cab", "arj", "lzh"
]

# CLI工具路径
CLI_BASE_PATH = os.path.join(os.path.dirname(__file__), "CLI", "Darwin")

def _get_archive_type(file_path):
    """Determines the archive type based on file extension and magic bytes."""
    file_path_str = str(file_path).lower()
    
    # 首先尝试通过文件头检测实际格式
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(26)  # 读取更多字节以识别各种格式
            
        # ZIP文件头: PK (0x504B)
        if magic.startswith(b'PK'):
            # 进一步检查是否是ZIPX格式
            if len(magic) >= 4 and magic[2:4] == b'\x07\x08':
                return "zipx"
            return "zip"
            
        # RAR文件头: Rar! (0x526172211A0700) 或 Rar! (0x526172211A070100)
        if magic.startswith(b'Rar!'):
            return "rar"
            
        # 7z文件头: 7z (0x377ABCAF271C)
        if magic.startswith(b'7z\xBC\xAF\x27\x1C'):
            return "7z"
            
        # CAB文件头: MSCF (0x4D534346)
        if magic.startswith(b'MSCF'):
            return "cab"
            
        # ARJ文件头: 标识符在偏移0-1处是0x60EA
        if len(magic) >= 2 and magic[:2] == b'\xea\x60':
            return "arj"
            
        # TAR文件头: 通常在偏移257处有"ustar"标识
        if len(magic) >= 26:
            # 重新读取更多字节以检测TAR
            with open(file_path, 'rb') as f:
                f.seek(257)
                tar_magic = f.read(5)
            if tar_magic == b'ustar':
                return "tar"
                
        # ISO文件头: 通常以"CD001"开头在偏移32769处 (ISO 9660)
        if len(magic) >= 6:
            with open(file_path, 'rb') as f:
                f.seek(32769)
                iso_header = f.read(5)
            if iso_header == b'CD001':
                return "iso"
                
        # LZMA/XZ格式: 检查LZMA魔数
        if len(magic) >= 6 and magic[:6] == b'\xfd7zXZ\x00':
            return "xz"
            
        # BZ2格式: BZh
        if len(magic) >= 3 and magic[:3] == b'BZh':
            return "bz2"
            
        # GZIP格式: \x1f\x8b
        if len(magic) >= 2 and magic[:2] == b'\x1f\x8b':
            return "tar.gz"  # 通常GZIP用于TAR.GZ
            
        # LZMA格式 (无XZ容器)
        if len(magic) >= 5 and magic[:5] == b'\x5d\x00\x00\x80\x00':
            return "lzma"
    except (IOError, OSError):
        # 如果读取文件失败，回退到扩展名检测
        pass
    
    # 如果文件头检测失败，回退到扩展名检测
    # Check for multi-part extensions first
    if file_path_str.endswith('.tar.bz2') or file_path_str.endswith('.tbz2'):
        return "tar.bz2"
    elif file_path_str.endswith('.tar.gz') or file_path_str.endswith('.tgz'):
        return "tar.gz"
    elif file_path_str.endswith('.tar.xz') or file_path_str.endswith('.txz'):
        return "tar.xz"
    
    # Check for single extensions
    ext = Path(file_path).suffix.lower()
    if ext == ".zip":
        return "zip"
    elif ext == ".rar":
        return "rar"
    elif ext == ".7z":
        return "7z"
    elif ext == ".tar":
        return "tar"
    elif ext == ".bz2":
        return "bz2"
    elif ext == ".xz":
        return "xz"
    elif ext == ".lzma":
        return "lzma"
    elif ext == ".zipx":
        return "zipx"
    elif ext == ".iso":
        return "iso"
    elif ext == ".cab":
        return "cab"
    elif ext == ".arj":
        return "arj"
    elif ext == ".lzh" or ext == ".lha":
        return "lzh"
    return None

def _run_command_with_timeout(cmd, timeout=2, progress_callback=None):
    """运行命令并设置超时限制"""
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if progress_callback:
            elapsed = time.time() - start_time
            progress_callback(f"Command completed in {elapsed:.2f}s", 100)
            
        return result
    except subprocess.TimeoutExpired:
        if progress_callback:
            progress_callback("Command timed out", -1)
        raise RuntimeError(f"Command timed out after {timeout} seconds")
    except Exception as e:
        if progress_callback:
            progress_callback(f"Command failed: {str(e)}", -1)
        raise

def _get_cli_tool(tool_name, arch_specific=False):
    """获取CLI工具路径"""
    if arch_specific:
        # 根据架构选择工具
        arch = platform.machine()
        if arch == "arm64":
            arch_dir = "AppleSi"
        else:
            arch_dir = "Intel"
        tool_path = os.path.join(CLI_BASE_PATH, arch_dir, tool_name)
    else:
        # 使用通用工具
        tool_path = os.path.join(CLI_BASE_PATH, "Universal", tool_name)
    
    if os.path.exists(tool_path):
        return tool_path
    else:
        raise FileNotFoundError(f"CLI tool not found: {tool_path}")

def _count_files_in_sources(source_paths):
    """Count total files in source paths for progress tracking."""
    total = 0
    for source_path in source_paths:
        path = Path(source_path)
        if path.is_file():
            total += 1
        elif path.is_dir():
            total += sum(1 for _ in path.rglob('*') if _.is_file())
    return max(total, 1)  # Ensure at least 1 to avoid division by zero

def create_archive(output_path, source_paths, archive_format, progress_callback=None):
    """
    Create an archive file from the specified source paths.

    Args:
        output_path (str): Path to the output archive file.
        source_paths (list): List of file/directory paths to include in the archive.
        archive_format (str): The format of the archive to create.
        progress_callback (function): Optional callback for progress updates.
    """
    try:
        # 验证输入参数
        if not output_path:
            raise ValueError("Output path is empty")
        if not source_paths:
            raise ValueError("No source paths specified")
        if not archive_format:
            raise ValueError("Archive format is not specified")
        
        # 检查源文件是否存在
        for source_path in source_paths:
            if not os.path.exists(source_path):
                raise ValueError(f"Source file does not exist: {source_path}")
        
        if progress_callback:
            progress_callback(f"Starting {archive_format} archive creation...", 0)
        
        # 创建一个临时目录，目录名为压缩包名称（不带扩展名）
        archive_name = os.path.splitext(os.path.basename(output_path))[0]
        temp_dir = tempfile.mkdtemp()
        wrapper_dir = os.path.join(temp_dir, archive_name)
        os.makedirs(wrapper_dir)
        
        try:
            # 复制所有源文件到包装目录中
            total_files = _count_files_in_sources(source_paths)
            copied_files = 0
            
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    shutil.copy2(source_path, wrapper_dir)
                    copied_files += 1
                elif os.path.isdir(source_path):
                    # 对于目录，递归复制并计算文件数量
                    dest_dir = os.path.join(wrapper_dir, os.path.basename(source_path))
                    shutil.copytree(source_path, dest_dir)
                    # 计算目录中的文件数量
                    for root, dirs, files in os.walk(source_path):
                        copied_files += len(files)
                
                # 更新进度 - 复制阶段占40%
                if progress_callback and total_files > 0:
                    progress = min(40, (copied_files / total_files) * 40)
                    progress_callback(f"Copying files to wrapper directory... ({copied_files}/{total_files})", progress)
            
            # 使用包装目录作为源路径
            wrapped_source_path = wrapper_dir
            
            # 根据格式选择处理方式
            if progress_callback:
                progress_callback(f"Creating {archive_format} archive...", 40)
                
            success = False
            if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "zipx"]:
                # 使用patool处理
                success = _create_with_patool(output_path, [wrapped_source_path], archive_format, progress_callback)
            elif archive_format in ["bz2", "xz", "lzma"]:
                # 这些格式只能压缩单个文件，所以需要先创建tar，再压缩
                success = _create_single_file_compression(output_path, [wrapped_source_path], archive_format, progress_callback)
            elif archive_format == "cab":
                # 使用cabextract相关工具处理CAB创建
                success = _create_cab_with_cli(output_path, [wrapped_source_path], progress_callback)
            elif archive_format in ["arj", "lzh"]:
                # 使用unar/lsar处理
                success = _create_with_unar(output_path, [wrapped_source_path], archive_format, progress_callback)
            elif archive_format == "rar":
                # 使用rar CLI工具
                success = _create_rar_with_cli(output_path, [wrapped_source_path], progress_callback)
            elif archive_format == "7z":
                # 使用7zz CLI工具
                success = _create_7z_with_cli(output_path, [wrapped_source_path], progress_callback)
            elif archive_format == "iso":
                # 使用系统命令
                success = _create_iso_with_system(output_path, [wrapped_source_path], progress_callback)
            else:
                raise ValueError(f"Unsupported archive format for creation: {archive_format}")
            
            if not success:
                raise RuntimeError(f"Failed to create {archive_format} archive")

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir)

        if progress_callback:
            progress_callback(f"Archive created: {output_path}", 100)
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating archive: {str(e)}", -1)
        return False

def _create_with_patool(output_path, source_paths, archive_format, progress_callback=None):
    """使用patool创建归档文件"""
    try:
        import patoolib
    except ImportError:
        raise ImportError("patool is required for this format. Install with: pip install patool")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 复制所有源文件到临时目录
        for source_path in source_paths:
            if os.path.isfile(source_path):
                shutil.copy2(source_path, temp_dir)
            elif os.path.isdir(source_path):
                shutil.copytree(source_path, os.path.join(temp_dir, os.path.basename(source_path)))
        
        # 使用patool创建归档 - 修复路径问题，使用完整路径
        temp_files = []
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            temp_files.append(item_path)
        
        if not temp_files:
            raise ValueError("No files found to archive")
            
        if progress_callback:
            progress_callback(f"Creating {archive_format} archive with patool...", 50)
        
        # 添加调试信息
        if progress_callback:
            progress_callback(f"Output path: {output_path}", 55)
            progress_callback(f"Temp files: {temp_files}", 60)
            
        # 尝试使用不同的patool调用方式
        try:
            # 方法1：直接传递文件路径
            patoolib.create_archive(output_path, temp_files)
        except Exception as e1:
            # 方法2：切换到临时目录并使用相对路径
            try:
                original_cwd = os.getcwd()
                os.chdir(temp_dir)
                rel_files = [os.path.basename(f) for f in temp_files]
                patoolib.create_archive(output_path, rel_files)
                os.chdir(original_cwd)
            except Exception as e2:
                os.chdir(original_cwd)
                
                # 方法3：使用完整路径和patool的--verbose选项
                try:
                    import subprocess
                    cmd = ["patool", "create", output_path] + temp_files
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"patool command failed: {result.stderr}")
                except Exception as e3:
                    raise RuntimeError(f"All patool methods failed: {e1}, {e2}, {e3}")
        
        if progress_callback:
            progress_callback(f"{archive_format} archive created", 90)
            
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating {archive_format} archive: {str(e)}", -1)
        return False
    finally:
        shutil.rmtree(temp_dir)

def _create_single_file_compression(output_path, source_paths, compression_format, progress_callback=None):
    """
    创建单个文件压缩格式（bz2, xz, lzma）
    这些格式只能压缩单个文件，所以需要先创建tar，再压缩
    """
    try:
        import patoolib
    except ImportError:
        raise ImportError("patool is required for this format. Install with: pip install patool")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 第一步：创建tar文件
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        tar_path = os.path.join(temp_dir, f"{base_name}.tar")
        
        if progress_callback:
            progress_callback(f"Creating intermediate tar file...", 50)
        
        # 创建tar文件
        patoolib.create_archive(tar_path, source_paths)
        
        if not os.path.exists(tar_path):
            raise RuntimeError("Failed to create intermediate tar file")
        
        # 第二步：压缩tar文件
        if progress_callback:
            progress_callback(f"Compressing tar file with {compression_format}...", 70)
        
        # 使用patool压缩tar文件
        patoolib.create_archive(output_path, [tar_path])
        
        if progress_callback:
            progress_callback(f"{compression_format} archive created", 90)
            
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating {compression_format} archive: {str(e)}", -1)
        return False
    finally:
        shutil.rmtree(temp_dir)

def _create_cab_with_cli(output_path, source_paths, progress_callback=None):
    """使用gcab工具创建CAB归档文件"""
    try:
        gcab_tool = _get_cli_tool("gcab")
    except FileNotFoundError:
        # 尝试从系统路径获取gcab
        gcab_tool = shutil.which("gcab")
        if not gcab_tool:
            raise RuntimeError("gcab tool not found. Please install with: brew install gcab")
    
    # 创建临时目录用于存放源文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 复制所有源文件到临时目录
        copied_files = []
        for i, source_path in enumerate(source_paths):
            source = Path(source_path)
            if not source.exists():
                continue
                
            dest_path = Path(temp_dir) / source.name
            if source.is_file():
                shutil.copy2(source, dest_path)
                copied_files.append(dest_path)
            elif source.is_dir():
                # 对于目录，递归复制
                dest_dir = Path(temp_dir) / source.name
                shutil.copytree(source, dest_dir)
                copied_files.append(dest_dir)
            
            # 更新进度
            if progress_callback:
                progress = (i + 1) / len(source_paths) * 50  # 前半部分进度用于复制文件
                progress_callback(progress)
        
        if not copied_files:
            raise ValueError("No valid source files found")
        
        # 构建gcab命令
        cmd = [gcab_tool, "-c", "-n", output_path]
        cmd.extend([str(f) for f in copied_files])
        
        # 执行命令
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            # 更新最终进度
            if progress_callback:
                progress_callback(100)
                
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create CAB archive: {e.stderr}")

def _create_rar_with_cli(output_path, source_paths, progress_callback=None):
    """使用rar CLI工具创建RAR文件"""
    try:
        rar_tool = _get_cli_tool("rar", arch_specific=True)
    except FileNotFoundError:
        # 备用方案：使用unar/lsar
        return _create_with_unar(output_path, source_paths, "rar", progress_callback)
    
    # 构建rar命令
    cmd = [rar_tool, "a", "-r", output_path] + source_paths
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR creation failed: {result.stderr}")
    
    return True

def _create_7z_with_cli(output_path, source_paths, progress_callback=None):
    """使用7zz CLI工具创建7z文件"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # 备用方案：使用unar/lsar
        _create_with_unar(output_path, source_paths, "7z", progress_callback)
        return True
    
    cmd = [sevenz_tool, "a", output_path] + source_paths
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z creation failed: {result.stderr}")
    
    return True

def _create_iso_with_system(output_path, source_paths, progress_callback=None):
    """使用系统命令创建ISO文件"""
    if len(source_paths) != 1 or not os.path.isdir(source_paths[0]):
        raise ValueError("ISO format only supports creating from a single directory")
    
    source_dir = source_paths[0]
    
    # 尝试使用hdiutil（macOS）
    if platform.system() == "Darwin":
        cmd = ["hdiutil", "makehybrid", "-o", output_path, "-hfs", "-iso", "-joliet", source_dir]
    else:
        # 其他系统使用mkisofs
        cmd = ["mkisofs", "-o", output_path, "-J", "-R", source_dir]
    
    result = _run_command_with_timeout(cmd, timeout=60, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"ISO creation failed: {result.stderr}")
    
    return True

def _create_arj_with_isar(output_path, source_paths, progress_callback=None):
    """使用Isar工具创建ARJ归档"""
    try:
        # 尝试获取Isar工具
        isar_tool = _get_cli_tool("isar")
    except FileNotFoundError:
        # 如果Isar不可用，尝试使用arj工具
        try:
            isar_tool = _get_cli_tool("arj")
        except FileNotFoundError:
            # 如果两者都不可用，回退到7z格式
            if progress_callback:
                progress_callback("Isar/ARJ tool not available, creating 7z instead", 50)
            
            sevenz_path = output_path.replace('.arj', '.7z')
            success = _create_7z_with_cli(sevenz_path, source_paths, progress_callback)
            if success and os.path.exists(sevenz_path):
                os.rename(sevenz_path, output_path)
                if progress_callback:
                    progress_callback("Created 7z file renamed as ARJ", 100)
                return True
            return False
    
    try:
        if progress_callback:
            progress_callback("Creating ARJ archive with Isar...", 0)
        
        # 创建临时目录用于处理文件
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制所有源文件到临时目录
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    shutil.copy2(source_path, temp_dir)
                elif os.path.isdir(source_path):
                    # 如果是目录，递归复制
                    dest_dir = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copytree(source_path, dest_dir)
            
            # 构建Isar命令
            # Isar命令格式: isar a -r [archive.arj] [files...]
            cmd = [isar_tool, "a", "-r", output_path, os.path.join(temp_dir, "*")]
            
            if progress_callback:
                progress_callback("Running Isar command...", 50)
            
            result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
            
            if result.returncode != 0:
                raise RuntimeError(f"ARJ creation failed: {result.stderr}")
            
            if progress_callback:
                progress_callback("ARJ archive created successfully", 100)
            
            return True
    
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating ARJ archive: {str(e)}", -1)
        return False

def _create_with_unar(output_path, source_paths, format_name, progress_callback=None):
    """使用unar支持的格式创建归档"""
    try:
        # 检查是否是ARJ格式，如果是则尝试使用Isar工具
        if format_name == "arj":
            return _create_arj_with_isar(output_path, source_paths, progress_callback)
        
        # 对于其他unar支持的格式，创建7z文件并修改扩展名
        if format_name == "lzh":
            # 创建7z文件并修改扩展名
            sevenz_path = output_path.replace('.lzh', '.7z')
            success = _create_7z_with_cli(sevenz_path, source_paths, progress_callback)
            if success and os.path.exists(sevenz_path):
                os.rename(sevenz_path, output_path)
                return True
            return False
        
        return False
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating {format_name} archive: {str(e)}", -1)
        return False

def extract_archive(archive_path, extract_to, progress_callback=None):
    """
    Extract an archive file to the specified directory.

    Args:
        archive_path (str): Path to the archive file to extract.
        extract_to (str): Directory to extract files to.
        progress_callback (function): Optional callback for progress updates.
    """
    try:
        archive_format = _get_archive_type(archive_path)
        if not archive_format:
            raise ValueError(f"Unknown archive format for extraction: {archive_path}")

        os.makedirs(extract_to, exist_ok=True)

        if progress_callback:
            progress_callback(f"Starting {archive_format} extraction...", 0)
        
        # 根据格式选择处理方式 - 优先使用专用工具，unar作为终极备用方案
        if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "bz2", "xz", "lzma"]:
            # 使用Python内置库（最稳定）
            try:
                _extract_with_python(archive_path, extract_to, archive_format, progress_callback)
            except Exception:
                # 失败时使用unar作为备用方案
                _extract_with_unar(archive_path, extract_to, progress_callback)
        elif archive_format in ["zipx"]:
            # 使用patool，失败时使用unar
            try:
                _extract_with_patool(archive_path, extract_to, progress_callback)
            except Exception:
                _extract_with_unar(archive_path, extract_to, progress_callback)
        elif archive_format == "cab":
            # 优先使用cabextract工具解压CAB文件
            try:
                _extract_cab_with_cabextract(archive_path, extract_to, progress_callback)
            except Exception:
                # 备用方案：使用unar
                _extract_with_unar(archive_path, extract_to, progress_callback)
        elif archive_format in ["arj", "lzh"]:
            # 这些格式unar支持很好，优先使用unar
            _extract_with_unar(archive_path, extract_to, progress_callback)
        elif archive_format == "rar":
            # 使用unrar CLI工具，失败时使用unar
            try:
                _extract_rar_with_cli(archive_path, extract_to, progress_callback)
            except Exception:
                _extract_with_unar(archive_path, extract_to, progress_callback)
        elif archive_format == "7z":
            # 使用7zz CLI工具，失败时使用unar
            try:
                _extract_7z_with_cli(archive_path, extract_to, progress_callback)
            except Exception:
                _extract_with_unar(archive_path, extract_to, progress_callback)
        elif archive_format == "iso":
            # 使用系统命令，失败时使用unar
            try:
                _extract_iso_with_system(archive_path, extract_to, progress_callback)
            except Exception:
                _extract_with_unar(archive_path, extract_to, progress_callback)
        else:
            # 未知格式，使用unar作为终极备用方案
            _extract_with_unar(archive_path, extract_to, progress_callback)

        if progress_callback:
            progress_callback(f"Archive extracted to: {extract_to}", 100)
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error extracting archive: {str(e)}", -1)
        return False

def _extract_with_python(archive_path, extract_to, archive_format, progress_callback=None):
    """使用Python内置库解压"""
    if archive_format == "zip":
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            file_list = zipf.namelist()
            total_files = len(file_list)
            for i, file_name in enumerate(file_list):
                zipf.extract(file_name, extract_to)
                if progress_callback:
                    progress = ((i + 1) / total_files) * 100
                    progress_callback(f"Extracting {file_name}", progress)
    
    elif archive_format.startswith("tar"):
        mode = "r"
        if archive_format == "tar.gz":
            mode = "r:gz"
        elif archive_format == "tar.bz2":
            mode = "r:bz2"
        elif archive_format == "tar.xz":
            mode = "r:xz"
            
        with tarfile.open(archive_path, mode) as tarf:
            members = tarf.getmembers()
            total_members = len(members)
            for i, member in enumerate(members):
                # 修复TAR.GZ解压路径问题 - 只保留文件名，去掉路径
                if member.name.startswith('/') or member.name.startswith('./'):
                    member.name = os.path.basename(member.name)
                elif os.path.dirname(member.name):  # 如果包含路径
                    member.name = os.path.basename(member.name)
                tarf.extract(member, extract_to)
                if progress_callback:
                    progress = ((i + 1) / total_members) * 100
                    progress_callback(f"Extracting {member.name}", progress)
    
    elif archive_format in ["bz2", "xz", "lzma"]:
        # 单文件压缩格式
        import bz2
        import lzma
        
        output_file = os.path.join(extract_to, os.path.basename(archive_path).rsplit('.', 1)[0])
        
        if archive_format == "bz2":
            with bz2.open(archive_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    # 使用二进制模式读取和写入
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        else:
            with lzma.open(archive_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    # 使用二进制模式读取和写入
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        
        if progress_callback:
            progress_callback(f"Extracted {output_file}", 100)

def _extract_with_patool(archive_path, extract_to, progress_callback=None):
    """使用patool解压"""
    try:
        import patoolib
    except ImportError:
        raise ImportError("patool is required for this format")
    
    patoolib.extract_archive(archive_path, outdir=extract_to)
    
    if progress_callback:
        progress_callback("Archive extracted", 100)

def _extract_rar_with_cli(archive_path, extract_to, progress_callback=None):
    """使用unrar CLI工具解压RAR文件"""
    try:
        unrar_tool = _get_cli_tool("unrar", arch_specific=True)
    except FileNotFoundError:
        # 终极备用方案：使用unar
        _extract_with_unar(archive_path, extract_to, progress_callback)
        return
    
    cmd = [unrar_tool, "x", archive_path, extract_to + "/", "-ep"]  # 添加-ep参数来忽略路径
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR extraction failed: {result.stderr}")

def _extract_7z_with_cli(archive_path, extract_to, progress_callback=None):
    """使用7zz CLI工具解压7z文件"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # 备用方案：使用unar
        _extract_with_unar(archive_path, extract_to, progress_callback)
        return
    
    cmd = [sevenz_tool, "x", archive_path, f"-o{extract_to}"]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z extraction failed: {result.stderr}")

def _extract_iso_with_system(archive_path, extract_to, progress_callback=None):
    """使用系统命令解压ISO文件"""
    if platform.system() == "Darwin":
        # macOS系统，优先使用hdiutil
        try:
            if progress_callback:
                progress_callback("Mounting ISO with hdiutil...", 0)
            
            # 挂载ISO文件
            cmd = ["hdiutil", "attach", archive_path]
            result = _run_command_with_timeout(cmd, timeout=10, progress_callback=progress_callback)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to mount ISO: {result.stderr}")
            
            # 解析挂载点
            mount_point = None
            lines = result.stdout.split('\n')
            for line in lines:
                if "/Volumes/" in line:
                    parts = line.split()
                    for part in parts:
                        if part.startswith("/Volumes/"):
                            mount_point = part
                            break
                    if mount_point:
                        break
            
            if not mount_point:
                raise RuntimeError("Could not determine mount point")
            
            if progress_callback:
                progress_callback(f"Copying files from {mount_point}...", 50)
            
            # 使用rsync复制文件，保留权限和时间戳
            cmd = ["rsync", "-a", f"{mount_point}/", extract_to + "/"]
            result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
            
            # 卸载ISO
            cmd = ["hdiutil", "detach", mount_point]
            try:
                _run_command_with_timeout(cmd, timeout=5, progress_callback=progress_callback)
            except RuntimeError as e:
                # 如果卸载失败，记录警告但不中断流程
                if progress_callback:
                    progress_callback(f"Warning: Failed to unmount ISO: {str(e)}", 90)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to copy files from ISO: {result.stderr}")
            
            if progress_callback:
                progress_callback("ISO extracted successfully", 100)
            
            return True
            
        except Exception as e:
            # 如果hdiutil失败，尝试使用7z作为备用方案
            if progress_callback:
                progress_callback(f"hdiutil failed, trying 7z: {str(e)}", 25)
            
            try:
                sevenz_tool = _get_cli_tool("7zz")
                cmd = [sevenz_tool, "x", archive_path, f"-o{extract_to}", "-y"]
                result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
                
                if result.returncode != 0:
                    raise RuntimeError(f"7z extraction failed: {result.stderr}")
                
                if progress_callback:
                    progress_callback("ISO extracted with 7z", 100)
                
                return True
                
            except Exception as e2:
                if progress_callback:
                    progress_callback(f"All ISO extraction methods failed: {str(e2)}", -1)
                return False
    else:
        # 其他系统，使用7z
        try:
            sevenz_tool = _get_cli_tool("7zz")
            cmd = [sevenz_tool, "x", archive_path, f"-o{extract_to}", "-y"]
            result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
            
            if result.returncode != 0:
                raise RuntimeError(f"ISO extraction failed: {result.stderr}")
            
            if progress_callback:
                progress_callback("ISO extracted successfully", 100)
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"ISO extraction failed: {str(e)}", -1)
            return False

def _extract_cab_with_cabextract(archive_path, extract_to, progress_callback=None):
    """使用cabextract工具解压CAB文件"""
    try:
        cabextract_tool = _get_cli_tool("cabextract")
    except FileNotFoundError:
        # 备用方案：使用unar
        return _extract_with_unar(archive_path, extract_to, progress_callback)
    
    cmd = [cabextract_tool, "-d", extract_to, archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"CAB extraction failed: {result.stderr}")

def _extract_with_unar(archive_path, extract_to, progress_callback=None):
    """使用unar作为终极备用方案"""
    try:
        unar_tool = _get_cli_tool("unar")
    except FileNotFoundError:
        raise RuntimeError("No extraction tool available for this format")
    
    cmd = [unar_tool, "-o", extract_to, archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"Extraction failed: {result.stderr}")

def list_archive_contents(archive_path, progress_callback=None):
    """
    List the contents of an archive file.

    Args:
        archive_path (str): Path to the archive file.
        progress_callback (function): Optional callback for progress updates.

    Returns:
        list: List of dictionaries containing file information.
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive file not found: {archive_path}")
        
        # 检查文件是否为空
        if os.path.getsize(archive_path) == 0:
            raise ValueError(f"Archive file is empty: {archive_path}")
        
        archive_format = _get_archive_type(archive_path)
        if not archive_format:
            raise ValueError(f"Unknown archive format: {archive_path}")

        if progress_callback:
            progress_callback(f"Listing {archive_format} contents...", 0)
        
        # 根据格式选择处理方式 - 优先使用专用工具，lsar作为终极备用方案
        if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "bz2", "xz", "lzma", "zipx"]:
            # 使用Python内置库（最稳定）
            try:
                contents = _list_with_python(archive_path, archive_format, progress_callback)
            except Exception as e:
                # 失败时使用lsar作为备用方案
                if progress_callback:
                    progress_callback(f"Python listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback)
        elif archive_format in ["rar"]:
            # 使用unrar CLI工具，失败时使用lsar
            try:
                contents = _list_rar_with_cli(archive_path, progress_callback)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"RAR listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback)
        elif archive_format in ["7z"]:
            # 使用7zz CLI工具，失败时使用lsar
            try:
                contents = _list_7z_with_cli(archive_path, progress_callback)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"7z listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback)
        elif archive_format == "cab":
            # 优先使用cabextract工具列出CAB文件内容
            try:
                contents = _list_cab_with_cabextract(archive_path, progress_callback)
            except Exception as e:
                # 备用方案：使用lsar
                if progress_callback:
                    progress_callback(f"CAB listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback)
        elif archive_format in ["arj", "lzh"]:
            # 这些格式lsar支持很好，优先使用lsar
            contents = _list_with_lsar(archive_path, progress_callback)
        elif archive_format == "iso":
            # ISO格式使用7zz工具列出内容
            try:
                contents = _list_iso_with_7z(archive_path, progress_callback)
            except Exception as e:
                # 备用方案：使用lsar
                if progress_callback:
                    progress_callback(f"7z ISO listing failed, trying lsar: {str(e)}", 50)
                contents = _list_iso_with_lsar(archive_path, progress_callback)
        else:
            # 未知格式，使用lsar作为终极备用方案
            if progress_callback:
                progress_callback(f"Unknown format {archive_format}, trying lsar", 50)
            contents = _list_with_lsar(archive_path, progress_callback)

        if progress_callback:
            progress_callback("Contents listed", 100)
        
        return contents

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error listing archive contents: {str(e)}", -1)
        raise  # 重新抛出异常以便调用者处理

def _list_with_python(archive_path, archive_format, progress_callback=None):
    """使用Python内置库列出内容"""
    contents = []
    
    if archive_format == "zip" or archive_format == "zipx":
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            file_list = zipf.namelist()
            total_files = len(file_list)
            for i, file_name in enumerate(file_list):
                try:
                    info = zipf.getinfo(file_name)
                    file_info = {
                        "name": file_name,
                        "size": info.file_size,
                        "compressed_size": info.compress_size,
                        "date": info.date_time,
                        "is_dir": file_name.endswith('/')
                    }
                except:
                    file_info = {
                        "name": file_name,
                        "size": 0,
                        "compressed_size": 0,
                        "date": None,
                        "is_dir": file_name.endswith('/')
                    }
                contents.append(file_info)
                
                if progress_callback:
                    progress = ((i + 1) / total_files) * 100
                    progress_callback(f"Listing {file_name}", progress)
    
    elif archive_format.startswith("tar") or archive_format in ["bz2", "xz", "lzma"]:
        mode = "r"
        if archive_format == "tar.gz":
            mode = "r:gz"
        elif archive_format == "tar.bz2":
            mode = "r:bz2"
        elif archive_format == "tar.xz":
            mode = "r:xz"
        elif archive_format == "bz2":
            # 单个bz2文件处理
            import bz2
            file_info = {
                "name": os.path.basename(archive_path).replace('.bz2', ''),
                "size": os.path.getsize(archive_path),
                "compressed_size": os.path.getsize(archive_path),
                "date": None,
                "is_dir": False
            }
            contents.append(file_info)
            if progress_callback:
                progress_callback("Listing bz2 file", 100)
            return contents
        elif archive_format == "xz":
            # 单个xz文件处理
            import lzma
            file_info = {
                "name": os.path.basename(archive_path).replace('.xz', ''),
                "size": os.path.getsize(archive_path),
                "compressed_size": os.path.getsize(archive_path),
                "date": None,
                "is_dir": False
            }
            contents.append(file_info)
            if progress_callback:
                progress_callback("Listing xz file", 100)
            return contents
        elif archive_format == "lzma":
            # 单个lzma文件处理
            file_info = {
                "name": os.path.basename(archive_path).replace('.lzma', ''),
                "size": os.path.getsize(archive_path),
                "compressed_size": os.path.getsize(archive_path),
                "date": None,
                "is_dir": False
            }
            contents.append(file_info)
            if progress_callback:
                progress_callback("Listing lzma file", 100)
            return contents
        elif archive_format == "tar.xz":
            mode = "r:xz"
        else:
            mode = "r"
            
        with tarfile.open(archive_path, mode) as tarf:
            members = tarf.getmembers()
            total_members = len(members)
            for i, member in enumerate(members):
                file_info = {
                    "name": member.name,
                    "size": member.size,
                    "compressed_size": member.size,
                    "date": member.mtime,
                    "is_dir": member.isdir()
                }
                contents.append(file_info)
                
                if progress_callback:
                    progress = ((i + 1) / total_members) * 100
                    progress_callback(f"Listing {member.name}", progress)
    
    return contents

def _list_rar_with_cli(archive_path, progress_callback=None):
    """使用unrar CLI工具列出RAR内容"""
    try:
        unrar_tool = _get_cli_tool("unrar", arch_specific=True)
    except FileNotFoundError:
        # 终极备用方案：使用lsar
        return _list_with_lsar(archive_path, progress_callback)
    
    cmd = [unrar_tool, "l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR listing failed: {result.stderr}")
    
    # 解析输出
    contents = []
    lines = result.stdout.split('\n')
    for line in lines:
        if line.strip() and not line.startswith('---'):
            parts = line.split()
            if len(parts) >= 4:
                file_info = {
                    "name": ' '.join(parts[3:]),
                    "size": int(parts[1]) if parts[1].isdigit() else 0,
                    "compressed_size": int(parts[0]) if parts[0].isdigit() else 0,
                    "date": None,
                    "is_dir": line.endswith('/')
                }
                contents.append(file_info)
    
    return contents

def _list_7z_with_cli(archive_path, progress_callback=None):
    """使用7zz CLI工具列出7z内容"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # 备用方案：使用lsar
        return _list_with_lsar(archive_path, progress_callback)
    
    cmd = [sevenz_tool, "l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z listing failed: {result.stderr}")
    
    # 解析输出
    contents = []
    lines = result.stdout.split('\n')
    for line in lines:
        if line.strip() and '----' not in line:
            parts = line.split()
            if len(parts) >= 4:
                file_info = {
                    "name": ' '.join(parts[5:]),
                    "size": int(parts[3]) if parts[3].isdigit() else 0,
                    "compressed_size": int(parts[2]) if parts[2].isdigit() else 0,
                    "date": None,
                    "is_dir": line.endswith('/')
                }
                contents.append(file_info)
    
    return contents

def _list_cab_with_cabextract(archive_path, progress_callback=None):
    """使用cabextract工具列出CAB文件内容"""
    try:
        cabextract_tool = _get_cli_tool("cabextract")
    except FileNotFoundError:
        # 备用方案：使用lsar
        return _list_with_lsar(archive_path, progress_callback)
    
    cmd = [cabextract_tool, "-l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"CAB listing failed: {result.stderr}")
    
    # 解析cabextract输出
    contents = []
    lines = result.stdout.split('\n')
    for line in lines:
        line = line.strip()
        # 跳过标题行和空行
        if (line and not line.startswith('Viewing cabinet:') and 
            not line.startswith('File size') and not line.startswith('-----------') and 
            not line.startswith('All done')):
            # 解析格式：文件大小 | 日期 时间 | 文件名
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 3:
                    try:
                        file_size = int(parts[0].strip())
                        file_name = parts[2].strip()
                        file_info = {
                            "name": file_name,
                            "size": file_size,
                            "compressed_size": file_size,
                            "date": f"{parts[1].strip()}",
                            "is_dir": False  # CAB文件不支持目录
                        }
                        contents.append(file_info)
                    except ValueError:
                        # 如果解析失败，跳过该行
                        continue
    
    return contents

def _list_iso_with_7z(archive_path, progress_callback=None):
    """使用7zz CLI工具列出ISO内容"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # 备用方案：使用lsar
        return _list_iso_with_lsar(archive_path, progress_callback)
    
    cmd = [sevenz_tool, "l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"ISO listing failed: {result.stderr}")
    
    # 解析7z输出
    contents = []
    lines = result.stdout.split('\n')
    in_file_list = False
    
    for line in lines:
        line = line.strip()
        # 检查是否进入文件列表部分
        if line.startswith('-----') and not in_file_list:
            in_file_list = True
            continue
        
        # 如果已经进入文件列表部分，再次遇到分隔线表示结束
        if line.startswith('-----') and in_file_list:
            break
        
        # 如果在文件列表部分，解析文件信息
        if in_file_list and line and not line.startswith('7-Zip') and not line.startswith('Scanning') and not line.startswith('Listing') and not line.startswith('Path') and not line.startswith('Type') and not line.startswith('Physical'):
            # 7z输出格式：日期 时间  属性        大小  压缩大小  名称
            # 示例：2025-10-03 18:47:54 .....        303          303  0000008C-00000000-454D4.TAGSET
            parts = line.split()
            if len(parts) >= 6:
                try:
                    # 尝试解析大小（第5个元素）
                    size = 0
                    if parts[4].isdigit():
                        size = int(parts[4])
                    
                    # 文件名是第6个元素及之后的所有内容
                    name = ' '.join(parts[5:])
                    
                    # 检查是否是目录（属性中包含D）
                    is_dir = 'D' in parts[3] if len(parts) > 3 else name.endswith('/')
                    
                    file_info = {
                        "name": name,
                        "size": size,
                        "compressed_size": size,  # ISO通常不压缩
                        "date": f"{parts[0]} {parts[1]}" if len(parts) > 1 else None,
                        "is_dir": is_dir
                    }
                    contents.append(file_info)
                except (ValueError, IndexError):
                    # 如果解析失败，跳过该行
                    continue
    
    return contents

def _list_iso_with_lsar(archive_path, progress_callback=None):
    """使用lsar列出ISO内容，专门处理ISO格式"""
    try:
        lsar_tool = _get_cli_tool("lsar")
    except FileNotFoundError:
        raise RuntimeError("No listing tool available for ISO format")
    
    cmd = [lsar_tool, "-l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"ISO listing failed: {result.stderr}")
    
    # 解析lsar输出
    contents = []
    lines = result.stdout.split('\n')
    
    # 跳过标题行，找到数据开始位置
    data_start = False
    for line in lines:
        line = line.strip()
        
        # 跳过空行和标题
        if not line:
            continue
            
        # 检查是否是标题行
        if line.startswith('Flags') or line.startswith('=====') or line.startswith('ISO 9660'):
            continue
            
        # 检查是否是数据行（以数字开头）
        if line and line[0].isdigit():
            # lsar输出格式：序号. 标志  文件大小  比率  模式  日期  时间  名称
            # 示例：0. -----         303  -576%  ----  2025-10-03 18:47  0000008C-00000000-454D4.TAGSET
            parts = line.split()
            if len(parts) >= 8:
                try:
                    # 尝试解析大小（第3个元素）
                    size = 0
                    if parts[2].isdigit():
                        size = int(parts[2])
                    
                    # 文件名是第8个元素及之后的所有内容
                    name = ' '.join(parts[7:])
                    
                    # 检查是否是目录（根据名称判断）
                    is_dir = name.endswith('/')
                    
                    file_info = {
                        "name": name,
                        "size": size,
                        "compressed_size": size,  # ISO通常不压缩
                        "date": f"{parts[5]} {parts[6]}" if len(parts) > 6 else None,
                        "is_dir": is_dir
                    }
                    contents.append(file_info)
                except (ValueError, IndexError):
                    # 如果解析失败，跳过该行
                    continue
    
    return contents

def _list_with_lsar(archive_path, progress_callback=None):
    """使用lsar作为终极备用方案列出内容"""
    try:
        lsar_tool = _get_cli_tool("lsar")
    except FileNotFoundError:
        raise RuntimeError("No listing tool available for this format")
    
    cmd = [lsar_tool, "-l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"Listing failed: {result.stderr}")
    
    # 解析lsar输出
    contents = []
    lines = result.stdout.split('\n')
    for line in lines:
        if line.strip() and ':' in line:
            key, value = line.split(':', 1)
            if key.strip() == "Path":
                file_info = {
                    "name": value.strip(),
                    "size": 0,
                    "compressed_size": 0,
                    "date": None,
                    "is_dir": value.strip().endswith('/')
                }
                contents.append(file_info)
    
    return contents

def add_to_archive(archive_path, file_to_add_path, progress_callback=None):
    """
    Add a file to an existing archive file.

    Args:
        archive_path (str): Path to the existing archive file.
        file_to_add_path (str): Path to the file to add.
        progress_callback (function): Optional callback for progress updates.
    """
    try:
        archive_format = _get_archive_type(archive_path)
        if not archive_format:
            raise ValueError(f"Unknown archive format for adding: {archive_path}")

        if progress_callback:
            progress_callback(f"Adding file to {archive_format} archive...", 0)
        
        # 根据格式选择处理方式
        if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]:
            # 使用Python内置库
            _add_with_python(archive_path, file_to_add_path, archive_format, progress_callback)
        elif archive_format in ["rar"]:
            # 使用CLI工具
            _add_rar_with_cli(archive_path, file_to_add_path, progress_callback)
        elif archive_format in ["7z"]:
            # 使用7zz CLI工具
            _add_7z_with_cli(archive_path, file_to_add_path, progress_callback)
        else:
            # 其他格式不支持添加文件
            raise ValueError(f"Adding files to {archive_format} format is not supported")

        if progress_callback:
            progress_callback(f"File added to archive: {file_to_add_path}", 100)
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error adding to archive: {str(e)}", -1)
        return False

def _add_with_python(archive_path, file_to_add_path, archive_format, progress_callback=None):
    """使用Python内置库添加文件"""
    if archive_format == "zip":
        with zipfile.ZipFile(archive_path, 'a') as zipf:
            file_name = os.path.basename(file_to_add_path)
            zipf.write(file_to_add_path, file_name)
    
    elif archive_format.startswith("tar"):
        # 正确的tarfile模式参数 - 使用写入模式而不是追加模式
        if archive_format == "tar":
            mode = "w"
        elif archive_format == "tar.gz":
            mode = "w:gz"
        elif archive_format == "tar.bz2":
            mode = "w:bz2"
        elif archive_format == "tar.xz":
            mode = "w:xz"
        else:
            mode = "w"
            
        # 对于tar文件，需要重新创建整个归档
        # 先读取现有内容，然后添加新文件
        existing_files = []
        if os.path.exists(archive_path):
            try:
                with tarfile.open(archive_path, 'r') as tarf:
                    existing_files = tarf.getnames()
            except:
                existing_files = []
        
        # 重新创建归档，包含现有文件和新文件
        with tarfile.open(archive_path, mode) as tarf:
            # 添加现有文件
            for existing_file in existing_files:
                tarf.add(existing_file, arcname=existing_file)
            # 添加新文件
            file_name = os.path.basename(file_to_add_path)
            tarf.add(file_to_add_path, arcname=file_name)
    
    if progress_callback:
        progress_callback("File added", 100)

def _add_rar_with_cli(archive_path, file_to_add_path, progress_callback=None):
    """使用rar CLI工具添加文件到RAR"""
    try:
        rar_tool = _get_cli_tool("rar", arch_specific=True)
    except FileNotFoundError:
        raise RuntimeError("RAR tool not available for adding files")
    
    cmd = [rar_tool, "a", archive_path, file_to_add_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR add failed: {result.stderr}")

def _add_7z_with_cli(archive_path, file_to_add_path, progress_callback=None):
    """使用7zz CLI工具添加文件到7z"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        raise RuntimeError("7z tool not available for adding files")
    
    cmd = [sevenz_tool, "a", archive_path, file_to_add_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z add failed: {result.stderr}")

# 测试函数
def test_archive_functions():
    """测试归档功能"""
    import tempfile
    import os
    
    print("=== Testing Archive Functions ===")
    
    # 创建测试文件
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Hello Archive Test")
        
        # 测试ZIP格式
        print("\n--- Testing ZIP format ---")
        zip_file = os.path.join(temp_dir, "test.zip")
        try:
            success = create_archive(zip_file, [test_file], "zip")
            print(f"ZIP creation: {'success' if success else 'failed'}")
            
            if success:
                contents = list_archive_contents(zip_file)
                print(f"ZIP contents: {len(contents)} items")
                
                extract_dir = os.path.join(temp_dir, "extracted_zip")
                success = extract_archive(zip_file, extract_dir)
                print(f"ZIP extraction: {'success' if success else 'failed'}")
        except Exception as e:
            print(f"ZIP test error: {e}")
        
        # 测试TAR.GZ格式
        print("\n--- Testing TAR.GZ format ---")
        tar_gz_file = os.path.join(temp_dir, "test.tar.gz")
        try:
            success = create_archive(tar_gz_file, [test_file], "tar.gz")
            print(f"TAR.GZ creation: {'success' if success else 'failed'}")
            
            if success:
                contents = list_archive_contents(tar_gz_file)
                print(f"TAR.GZ contents: {len(contents)} items")
                
                extract_dir = os.path.join(temp_dir, "extracted_tar_gz")
                success = extract_archive(tar_gz_file, extract_dir)
                print(f"TAR.GZ extraction: {'success' if success else 'failed'}")
        except Exception as e:
            print(f"TAR.GZ test error: {e}")
        
        # 测试RAR格式（如果可用）
        print("\n--- Testing RAR format ---")
        rar_file = os.path.join(temp_dir, "test.rar")
        try:
            success = create_archive(rar_file, [test_file], "rar")
            print(f"RAR creation: {'success' if success else 'failed'}")
            
            if success:
                contents = list_archive_contents(rar_file)
                print(f"RAR contents: {len(contents)} items")
                
                extract_dir = os.path.join(temp_dir, "extracted_rar")
                success = extract_archive(rar_file, extract_dir)
                print(f"RAR extraction: {'success' if success else 'failed'}")
        except Exception as e:
            print(f"RAR test error: {e}")
        
        # 测试7z格式（如果可用）
        print("\n--- Testing 7z format ---")
        sevenz_file = os.path.join(temp_dir, "test.7z")
        try:
            success = create_archive(sevenz_file, [test_file], "7z")
            print(f"7z creation: {'success' if success else 'failed'}")
            
            if success:
                contents = list_archive_contents(sevenz_file)
                print(f"7z contents: {len(contents)} items")
                
                extract_dir = os.path.join(temp_dir, "extracted_7z")
                success = extract_archive(sevenz_file, extract_dir)
                print(f"7z extraction: {'success' if success else 'failed'}")
        except Exception as e:
            print(f"7z test error: {e}")
        
        print("\n=== Archive Functions Test Complete ===")

if __name__ == "__main__":
    test_archive_functions()