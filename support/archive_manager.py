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

# CLI tool path
CLI_BASE_PATH = os.path.join(os.path.dirname(__file__), "CLI", "Darwin")

def _get_archive_type(file_path):
    """Determines the archive type based on file extension and magic bytes."""
    file_path_str = str(file_path).lower()
    
    # First try to detect actual format through file header
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(26)  # Read more bytes to identify various formats
            
        # ZIP file header: PK (0x504B)
        if magic.startswith(b'PK'):
            # Further check if it's ZIPX format
            if len(magic) >= 4 and magic[2:4] == b'\x07\x08':
                return "zipx"
            return "zip"
            
        # RAR file header: Rar! (0x526172211A0700) or Rar! (0x526172211A070100)
        if magic.startswith(b'Rar!'):
            return "rar"
            
        # 7z file header: 7z (0x377ABCAF271C)
        if magic.startswith(b'7z\xBC\xAF\x27\x1C'):
            return "7z"
            
        # CAB file header: MSCF (0x4D534346)
        if magic.startswith(b'MSCF'):
            return "cab"
            
        # ARJ file header: Identifier at offset 0-1 is 0x60EA
        if len(magic) >= 2 and magic[:2] == b'\xea\x60':
            return "arj"
            
        # TAR file header: Usually has "ustar" identifier at offset 257
        if len(magic) >= 26:
            # Read more bytes again to detect TAR
            with open(file_path, 'rb') as f:
                f.seek(257)
                tar_magic = f.read(5)
            if tar_magic == b'ustar':
                return "tar"
                
        # ISO file header: Usually starts with "CD001" at offset 32769 (ISO 9660)
        if len(magic) >= 6:
            with open(file_path, 'rb') as f:
                f.seek(32769)
                iso_header = f.read(5)
            if iso_header == b'CD001':
                return "iso"
                
        # LZMA/XZ format: Check LZMA magic number
        if len(magic) >= 6 and magic[:6] == b'\xfd7zXZ\x00':
            return "xz"
            
        # BZ2 format: BZh
        if len(magic) >= 3 and magic[:3] == b'BZh':
            return "bz2"
            
        # GZIP format: \x1f\x8b
        if len(magic) >= 2 and magic[:2] == b'\x1f\x8b':
            return "tar.gz"
            
        # LZMA format (without XZ container)
        if len(magic) >= 5 and magic[:5] == b'\x5d\x00\x00\x80\x00':
            return "lzma"
    except (IOError, OSError):
        # If file reading fails, fall back to extension detection
        pass
    
    # If file header detection fails, fall back to extension detection
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
    """Run command with timeout limit"""
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
    """Get CLI tool path"""
    # First try to find the tool in system PATH
    import shutil
    tool_path = shutil.which(tool_name)
    if tool_path:
        return tool_path
    
    # If not found in PATH, try CLI_BASE_PATH
    if arch_specific:
        # Select tool based on architecture
        arch = platform.machine()
        if arch == "arm64":
            arch_dir = "AppleSi"
        else:
            arch_dir = "Intel"
        tool_path = os.path.join(CLI_BASE_PATH, arch_dir, tool_name)
    else:
        # Use universal tool
        tool_path = os.path.join(CLI_BASE_PATH, "Universal", tool_name)
    
    if os.path.exists(tool_path):
        return tool_path
    else:
        raise FileNotFoundError(f"CLI tool not found: {tool_path}")

def _create_password_protected_zip(output_path, source_paths, password, progress_callback=None):
    """
    Create a password-protected ZIP file directly from source paths without using a wrapper directory.
    
    Args:
        output_path (str): Path to the output ZIP file.
        source_paths (list): List of file/directory paths to include in the ZIP.
        password (str): Password for the ZIP file.
        progress_callback (function): Optional callback for progress updates.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        if progress_callback:
            progress_callback("Creating password-protected ZIP with pyzipper...", 20)
        
        # Try using pyzipper library first (AES encryption support)
        try:
            import pyzipper
            
            # Create a ZIP file with AES encryption
            with pyzipper.AESZipFile(
                output_path,
                'w',
                compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES
            ) as zf:
                zf.setpassword(password.encode('utf-8'))
                
                # Track added files to avoid duplicates
                added_files = set()
                
                # Count total files for progress tracking
                total_files = _count_files_in_sources(source_paths)
                processed_files = 0
                
                # Add each source path to the ZIP
                for source_path in source_paths:
                    if os.path.isfile(source_path):
                        # Skip the output file itself if it's in the source directory
                        if os.path.abspath(source_path) == os.path.abspath(output_path):
                            continue
                        # For files, add with just the filename
                        arcname = os.path.basename(source_path)
                        if arcname not in added_files:
                            zf.write(source_path, arcname)
                            added_files.add(arcname)
                            processed_files += 1
                    elif os.path.isdir(source_path):
                        # For directories, add recursively with relative paths
                        for root, dirs, files in os.walk(source_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                # Skip the output file itself if it's in the source directory
                                if os.path.abspath(file_path) == os.path.abspath(output_path):
                                    continue
                                # Calculate relative path from source_path (not its parent)
                                rel_path = os.path.relpath(file_path, source_path)
                                if rel_path not in added_files:
                                    zf.write(file_path, rel_path)
                                    added_files.add(rel_path)
                                    processed_files += 1
                    
                    # Update progress
                    if progress_callback and total_files > 0:
                        progress = 20 + min(70, (processed_files / total_files) * 70)
                        progress_callback(f"Adding files to ZIP... ({processed_files}/{total_files})", progress)
                
                if progress_callback:
                    progress_callback("Finalizing ZIP file...", 90)
            
            if progress_callback:
                progress_callback("Password-protected ZIP created successfully with pyzipper", 100)
            return True
            
        except ImportError:
            # pyzipper not available, try with standard zipfile
            if progress_callback:
                progress_callback("pyzipper not available, using standard zipfile...", 30)
            
            import zipfile
            
            with zipfile.ZipFile(
                output_path,
                'w',
                compression=zipfile.ZIP_DEFLATED
            ) as zf:
                # Track added files to avoid duplicates
                added_files = set()
                
                # Count total files for progress tracking
                total_files = _count_files_in_sources(source_paths)
                processed_files = 0
                
                # Add each source path to the ZIP
                for source_path in source_paths:
                    if os.path.isfile(source_path):
                        # Skip the output file itself if it's in the source directory
                        if os.path.abspath(source_path) == os.path.abspath(output_path):
                            continue
                        # For files, add with just the filename
                        arcname = os.path.basename(source_path)
                        if arcname not in added_files:
                            zf.write(source_path, arcname)
                            added_files.add(arcname)
                            processed_files += 1
                    elif os.path.isdir(source_path):
                        # For directories, add recursively with relative paths
                        for root, dirs, files in os.walk(source_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                # Skip the output file itself if it's in the source directory
                                if os.path.abspath(file_path) == os.path.abspath(output_path):
                                    continue
                                # Calculate relative path from source_path (not its parent)
                                rel_path = os.path.relpath(file_path, source_path)
                                if rel_path not in added_files:
                                    zf.write(file_path, rel_path)
                                    added_files.add(rel_path)
                                    processed_files += 1
                    
                    # Update progress
                    if progress_callback and total_files > 0:
                        progress = 30 + min(60, (processed_files / total_files) * 60)
                        progress_callback(f"Adding files to ZIP... ({processed_files}/{total_files})", progress)
                
                if progress_callback:
                    progress_callback("Finalizing ZIP file...", 90)
            
            # Note: Standard zipfile doesn't support password protection directly
            # We'll need to use a different approach or inform the user
            if progress_callback:
                progress_callback("Warning: Standard zipfile doesn't support password protection", 100)
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error creating password-protected ZIP: {str(e)}", -1)
            return False
            
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error in password-protected ZIP creation: {str(e)}", -1)
        return False


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

def create_archive(output_path, source_paths, archive_format, progress_callback=None, password=None):
    """
    Create an archive file from the specified source paths.

    Args:
        output_path (str): Path to the output archive file.
        source_paths (list): List of file/directory paths to include in the archive.
        archive_format (str): The format of the archive to create.
        progress_callback (function): Optional callback for progress updates.
        password (str): Optional password for password-protected archives.
    """
    try:
        # Validate input parameters
        if not output_path:
            raise ValueError("Output path is empty")
        if not source_paths:
            raise ValueError("No source paths specified")
        if not archive_format:
            raise ValueError("Archive format is not specified")
        
        # Check if source files exist
        for source_path in source_paths:
            if not os.path.exists(source_path):
                raise ValueError(f"Source file does not exist: {source_path}")
        
        if progress_callback:
            progress_callback(f"Starting {archive_format} archive creation...", 0)
        
        # For password-protected ZIP files, use direct processing without wrapper directory
        if archive_format == "zip" and password:
            if progress_callback:
                progress_callback(f"Creating password-protected ZIP file directly...", 10)
            
            # Use a specialized function for password-protected ZIP files
            success = _create_password_protected_zip(output_path, source_paths, password, progress_callback)
            if not success:
                raise RuntimeError(f"Failed to create password-protected ZIP archive")
        else:
            # Create a temporary directory with the archive name (without extension)
            archive_name = os.path.splitext(os.path.basename(output_path))[0]
            temp_dir = tempfile.mkdtemp()
            wrapper_dir = os.path.join(temp_dir, archive_name)
            
            # Ensure the wrapper directory doesn't already exist
            if os.path.exists(wrapper_dir):
                shutil.rmtree(wrapper_dir)
            os.makedirs(wrapper_dir)
            
            try:
                # Copy all source files to the wrapper directory
                total_files = _count_files_in_sources(source_paths)
                copied_files = 0
                
                for source_path in source_paths:
                    if os.path.isfile(source_path):
                        shutil.copy2(source_path, wrapper_dir)
                        copied_files += 1
                    elif os.path.isdir(source_path):
                        # For directories, recursively copy and count files
                        dest_dir = os.path.join(wrapper_dir, os.path.basename(source_path))
                        shutil.copytree(source_path, dest_dir)
                        # Count files in directory
                        for root, dirs, files in os.walk(source_path):
                            copied_files += len(files)
                    
                    # Update progress - copy phase accounts for 40%
                    if progress_callback and total_files > 0:
                        progress = min(40, (copied_files / total_files) * 40)
                        progress_callback(f"Copying files to wrapper directory... ({copied_files}/{total_files})", progress)
                
                # Use wrapper directory as source path
                wrapped_source_path = wrapper_dir
                
                # Select processing method based on format
                if progress_callback:
                    progress_callback(f"Creating {archive_format} archive...", 40)
                    
                success = False
                if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "zipx"]:
                    # Use patool for processing
                    success = _create_with_patool(output_path, [wrapped_source_path], archive_format, progress_callback, password)
                elif archive_format in ["bz2", "xz", "lzma", "gz"]:
                    # These formats can only compress single files, so need to create tar first, then compress
                    success = _create_single_file_compression(output_path, [wrapped_source_path], archive_format, progress_callback)
                elif archive_format == "cab":
                    # Use cabextract related tools for CAB creation
                    success = _create_cab_with_cli(output_path, [wrapped_source_path], progress_callback)
                elif archive_format in ["arj", "lzh"]:
                    # Use unar/lsar for processing
                    success = _create_with_unar(output_path, [wrapped_source_path], archive_format, progress_callback)
                elif archive_format == "rar":
                    # Use rar CLI tool
                    success = _create_rar_with_cli(output_path, [wrapped_source_path], progress_callback, password)
                elif archive_format == "7z":
                    # Use 7zz CLI tool
                    success = _create_7z_with_cli(output_path, [wrapped_source_path], progress_callback, password)
                elif archive_format == "iso":
                    # Use system command
                    success = _create_iso_with_system(output_path, [wrapped_source_path], progress_callback)
                else:
                    raise ValueError(f"Unsupported archive format for creation: {archive_format}")
                
                if not success:
                    raise RuntimeError(f"Failed to create {archive_format} archive")

            finally:
                # Clean up temporary directory
                shutil.rmtree(temp_dir)

        if progress_callback:
            progress_callback(f"Archive created: {output_path}", 100)
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating archive: {str(e)}", -1)
        return False

def _create_with_patool(output_path, source_paths, archive_format, progress_callback=None, password=None):
    """Create archive file using patool"""
    import subprocess
    try:
        import patoolib
    except ImportError:
        raise ImportError("patool is required for this format. Install with: pip install patool")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Copy all source files to temporary directory
        for source_path in source_paths:
            if os.path.isfile(source_path):
                shutil.copy2(source_path, temp_dir)
            elif os.path.isdir(source_path):
                dest_dir = os.path.join(temp_dir, os.path.basename(source_path))
                # Ensure the destination directory doesn't already exist
                if os.path.exists(dest_dir):
                    shutil.rmtree(dest_dir)
                shutil.copytree(source_path, dest_dir)
        
        # Use patool to create archive - fix path issues, use full paths
        temp_files = []
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            temp_files.append(item_path)
        
        if not temp_files:
            raise ValueError("No files found to archive")
            
        if progress_callback:
            progress_callback(f"Creating {archive_format} archive with patool...", 50)
        
        # Add debug information
        if progress_callback:
            progress_callback(f"Output path: {output_path}", 55)
            progress_callback(f"Temp files: {temp_files}", 60)
        
        # For ZIP format with password, use Python's zipfile module
        if archive_format == "zip" and password:
            if progress_callback:
                progress_callback(f"Creating password-protected ZIP file...", 65)
            
            password_success = False
            
            # First try to use zip command if available (most compatible)
            zip_tool = _get_cli_tool("zip")
            if zip_tool:
                if progress_callback:
                    progress_callback(f"Trying to create password-protected ZIP with zip command...", 70)
                
                # Create a temporary directory for zip to work with
                temp_zip_dir = tempfile.mkdtemp()
                try:
                    # Ensure output file doesn't exist
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    
                    # Copy files to temp directory
                    for file_path in temp_files:
                        if os.path.isfile(file_path):
                            shutil.copy2(file_path, temp_zip_dir)
                        elif os.path.isdir(file_path):
                            dest_dir = os.path.join(temp_zip_dir, os.path.basename(file_path))
                            shutil.copytree(file_path, dest_dir)
                    
                    # Create password-protected ZIP with zip command
                    cmd = [zip_tool, "-r", "-P", password, output_path, "."]
                    result = subprocess.run(cmd, cwd=temp_zip_dir, capture_output=True, text=True)
                    
                    # Check if the command succeeded (return code 0) and the output file exists
                    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        password_success = True
                        if progress_callback:
                            progress_callback(f"Password-protected ZIP created with zip command", 85)
                    else:
                        if progress_callback:
                            progress_callback(f"Failed to create password-protected ZIP with zip command: return code {result.returncode}", 75)
                finally:
                    shutil.rmtree(temp_zip_dir)
            else:
                if progress_callback:
                    progress_callback(f"zip command not available, trying pyzipper...", 75)
            
            # If zip command failed, try to use pyzipper
            if not password_success:
                try:
                    import pyzipper
                    if progress_callback:
                        progress_callback(f"Creating password-protected ZIP with pyzipper...", 70)
                    
                    # Create a password-protected ZIP with pyzipper
                    with pyzipper.AESZipFile(output_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                        zf.setpassword(password.encode())
                        for file_path in temp_files:
                            if os.path.isfile(file_path):
                                # 只使用文件名，不包含路径
                                zf.write(file_path, os.path.basename(file_path))
                            elif os.path.isdir(file_path):
                                # 对于目录，递归添加所有文件，保留目录结构
                                for root, dirs, files in os.walk(file_path):
                                    for file in files:
                                        file_full_path = os.path.join(root, file)
                                        # 计算相对于目录的路径，保留子目录结构
                                        arcname = os.path.relpath(file_full_path, file_path)
                                        zf.write(file_full_path, arcname)
                    
                    password_success = True
                    if progress_callback:
                        progress_callback(f"Password-protected ZIP created with pyzipper", 85)
                        
                except ImportError:
                    if progress_callback:
                        progress_callback(f"pyzipper not available, trying 7zz...", 75)
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Failed to create password-protected ZIP with pyzipper: {str(e)}", 75)
            
            # If pyzipper failed, try to use 7zz
            if not password_success:
                sevenz_tool = _get_cli_tool("7zz")
                if sevenz_tool:
                    if progress_callback:
                        progress_callback(f"Trying to create password-protected ZIP with 7zz...", 75)
                    
                    # Create a temporary directory for 7zz to work with
                    temp_7z_dir = tempfile.mkdtemp()
                    try:
                        # Copy files to temp directory
                        for file_path in temp_files:
                            if os.path.isfile(file_path):
                                shutil.copy2(file_path, temp_7z_dir)
                            elif os.path.isdir(file_path):
                                dest_dir = os.path.join(temp_7z_dir, os.path.basename(file_path))
                                shutil.copytree(file_path, dest_dir)
                        
                        # Create password-protected ZIP with 7zz
                        cmd = [sevenz_tool, "a", f"-p{password}", "-y", output_path, os.path.join(temp_7z_dir, "*")]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            password_success = True
                            if progress_callback:
                                progress_callback(f"Password-protected ZIP created with 7zz", 85)
                        else:
                            if progress_callback:
                                progress_callback(f"Failed to create password-protected ZIP with 7zz: {result.stderr}", 80)
                    finally:
                        shutil.rmtree(temp_7z_dir)
                else:
                    if progress_callback:
                        progress_callback(f"7zz not available", 75)
            
            # If pyzipper and 7zz both failed, we'll fall back to standard ZIP without password
            if not password_success:
                if progress_callback:
                    progress_callback(f"All password protection methods failed", 75)
            
            # If all methods failed, create a non-password-protected ZIP
            if not password_success:
                if progress_callback:
                    progress_callback(f"Warning: Could not create password-protected ZIP, creating standard ZIP", 75)
                
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file_path in temp_files:
                        if os.path.isfile(file_path):
                            # 只使用文件名，不包含路径
                            zf.write(file_path, os.path.basename(file_path))
                        elif os.path.isdir(file_path):
                            # 对于目录，递归添加所有文件，保留目录结构
                            for root, dirs, files in os.walk(file_path):
                                for file in files:
                                    file_full_path = os.path.join(root, file)
                                    # 计算相对于目录的路径，保留子目录结构
                                    arcname = os.path.relpath(file_full_path, file_path)
                                    zf.write(file_full_path, arcname)
                
                if progress_callback:
                    progress_callback(f"Standard ZIP created (no password protection)", 85)
            
            if progress_callback:
                progress_callback(f"ZIP archive created", 90)
        else:
            # Try different patool calling methods
            try:
                # Method 1: Directly pass file paths
                patoolib.create_archive(output_path, temp_files)
            except Exception as e1:
                # Method 2: Switch to temporary directory and use relative paths
                try:
                    original_cwd = os.getcwd()
                    os.chdir(temp_dir)
                    rel_files = [os.path.basename(f) for f in temp_files]
                    patoolib.create_archive(output_path, rel_files)
                    os.chdir(original_cwd)
                except Exception as e2:
                    os.chdir(original_cwd)
                    
                    # Method 3: Use full paths and patool's --verbose option
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
    Create single file compression format (bz2, xz, lzma)
    These formats can only compress single files, so need to create tar first, then compress
    """
    try:
        import patoolib
    except ImportError:
        raise ImportError("patool is required for this format. Install with: pip install patool")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Step 1: Create tar file
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        tar_path = os.path.join(temp_dir, f"{base_name}.tar")
        
        if progress_callback:
            progress_callback(f"Creating intermediate tar file...", 50)
        
        # Create tar file
        patoolib.create_archive(tar_path, source_paths)
        
        if not os.path.exists(tar_path):
            raise RuntimeError("Failed to create intermediate tar file")
        
        # Step 2: Compress tar file
        if progress_callback:
            progress_callback(f"Compressing tar file with {compression_format}...", 70)
        
        # Use patool to compress tar file
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
    """Create CAB archive file using gcab tool"""
    try:
        gcab_tool = _get_cli_tool("gcab")
    except FileNotFoundError:
        # Try to get gcab from system path
        gcab_tool = shutil.which("gcab")
        if not gcab_tool:
            raise RuntimeError("gcab tool not found. Please install with: brew install gcab")
    
    # Create temporary directory for source files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy all source files to temporary directory
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
                # For directories, recursively copy
                dest_dir = Path(temp_dir) / source.name
                # Ensure the destination directory doesn't already exist
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                shutil.copytree(source, dest_dir)
                copied_files.append(dest_dir)
            
            # Update progress
            if progress_callback:
                progress = (i + 1) / len(source_paths) * 50  # First half of progress for copying files
                progress_callback(progress)
        
        if not copied_files:
            raise ValueError("No valid source files found")
        
        # Build gcab command
        cmd = [gcab_tool, "-c", "-n", output_path]
        cmd.extend([str(f) for f in copied_files])
        
        # Execute command
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            # Update final progress
            if progress_callback:
                progress_callback(100)
                
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create CAB archive: {e.stderr}")

def _create_rar_with_cli(output_path, source_paths, progress_callback=None, password=None):
    """Create RAR file using rar CLI tool"""
    try:
        rar_tool = _get_cli_tool("rar", arch_specific=True)
    except FileNotFoundError:
        # Fallback: Use unar/lsar
        return _create_with_unar(output_path, source_paths, "rar", progress_callback)
    
    # Build rar command
    cmd = [rar_tool, "a", "-r"]
    if password:
        cmd.extend(["-p" + password, "-y"])
    else:
        cmd.append("-y")
    cmd.append(output_path)
    cmd.extend(source_paths)
    
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR creation failed: {result.stderr}")
    
    return True

def _create_7z_with_cli(output_path, source_paths, progress_callback=None, password=None):
    """Create 7z file using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # Fallback: Use unar/lsar
        _create_with_unar(output_path, source_paths, "7z", progress_callback)
        return True
    
    cmd = [sevenz_tool, "a"]
    if password:
        cmd.extend(["-p" + password, "-y"])
    else:
        cmd.append("-y")
    cmd.append(output_path)
    cmd.extend(source_paths)
    
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z creation failed: {result.stderr}")
    
    return True

def _create_iso_with_system(output_path, source_paths, progress_callback=None):
    """Create ISO file using system command"""
    if len(source_paths) != 1 or not os.path.isdir(source_paths[0]):
        raise ValueError("ISO format only supports creating from a single directory")
    
    source_dir = source_paths[0]
    
    # Try using hdiutil (macOS)
    if platform.system() == "Darwin":
        cmd = ["hdiutil", "makehybrid", "-o", output_path, "-hfs", "-iso", "-joliet", source_dir]
    else:
        # Other systems use mkisofs
        cmd = ["mkisofs", "-o", output_path, "-J", "-R", source_dir]
    
    result = _run_command_with_timeout(cmd, timeout=60, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"ISO creation failed: {result.stderr}")
    
    return True

def _create_arj_with_isar(output_path, source_paths, progress_callback=None):
    """Create ARJ archive using Isar tool"""
    try:
        # Try to get Isar tool
        isar_tool = _get_cli_tool("isar")
    except FileNotFoundError:
        # If Isar is not available, try using arj tool
        try:
            isar_tool = _get_cli_tool("arj")
        except FileNotFoundError:
            # If neither is available, fallback to 7z format
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
        
        # Create temporary directory for file processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy all source files to temporary directory
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    shutil.copy2(source_path, temp_dir)
                elif os.path.isdir(source_path):
                    # If it's a directory, recursively copy
                    dest_dir = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copytree(source_path, dest_dir)
            
            # Build Isar command
            # Isar command format: isar a -r [archive.arj] [files...]
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
    """Create archive using unar supported format"""
    try:
        # Check if it's ARJ format, if so try using Isar tool
        if format_name == "arj":
            return _create_arj_with_isar(output_path, source_paths, progress_callback)
        
        # For other unar supported formats, create 7z file and modify extension
        if format_name == "lzh":
            # Create 7z file and modify extension
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

def extract_archive(archive_path, extract_to, progress_callback=None, password=None):
    """
    Extract an archive file to the specified directory.

    Args:
        archive_path (str): Path to the archive file to extract.
        extract_to (str): Directory to extract files to.
        progress_callback (function): Optional callback for progress updates.
        password (str): Optional password for encrypted archives.
    """
    try:
        archive_format = _get_archive_type(archive_path)
        if not archive_format:
            raise ValueError(f"Unknown archive format for extraction: {archive_path}")

        os.makedirs(extract_to, exist_ok=True)

        if progress_callback:
            progress_callback(f"Starting {archive_format} extraction...", 0)
        
        # Select processing method based on format - prioritize dedicated tools, use unar as ultimate fallback
        if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "bz2", "xz", "lzma"]:
            # Use Python built-in libraries (most stable)
            try:
                _extract_with_python(archive_path, extract_to, archive_format, progress_callback, password)
            except RuntimeError as e:
                # For password-related errors, don't use fallback, re-raise exception directly
                if "password" in str(e).lower():
                    raise
                # Use unar as fallback on failure
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
            except Exception:
                # Use unar as fallback on failure
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
        elif archive_format in ["zipx"]:
            # Use patool, fallback to unar on failure
            try:
                _extract_with_patool(archive_path, extract_to, progress_callback, password)
            except Exception:
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
        elif archive_format == "cab":
            # Prioritize using cabextract tool to extract CAB files
            try:
                _extract_cab_with_cabextract(archive_path, extract_to, progress_callback, password)
            except Exception:
                # Fallback: Use unar
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
        elif archive_format in ["arj", "lzh"]:
            # These formats are well supported by unar, prioritize using unar
            _extract_with_unar(archive_path, extract_to, progress_callback, password)
        elif archive_format == "rar":
            # Use unrar CLI tool, fallback to unar on failure
            try:
                _extract_rar_with_cli(archive_path, extract_to, progress_callback, password)
            except RuntimeError as e:
                # For password-related errors, don't use fallback, re-raise exception directly
                if "password" in str(e).lower():
                    raise
                # Use unar as fallback on failure
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
            except Exception as e:
                # 检查异常信息是否包含密码相关关键词
                error_msg = str(e).lower()
                password_error_keywords = [
                    "password", "encrypted", "authentication", "incorrect", 
                    "wrong", "bad", "required", "data error", "crc error"
                ]
                if any(keyword in error_msg for keyword in password_error_keywords):
                    raise RuntimeError(f"Password required for encrypted RAR file: {str(e)}")
                # Use unar as fallback on failure
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
        elif archive_format == "7z":
            # Use 7zz CLI tool, fallback to unar on failure
            try:
                _extract_7z_with_cli(archive_path, extract_to, progress_callback, password)
            except RuntimeError as e:
                # For password-related errors, don't use fallback, re-raise exception directly
                if "password" in str(e).lower():
                    raise
                # Use unar as fallback on failure
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
            except Exception:
                # Use unar as fallback on failure
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
        elif archive_format == "iso":
            # Use system command, fallback to unar on failure
            try:
                _extract_iso_with_system(archive_path, extract_to, progress_callback)
            except Exception:
                _extract_with_unar(archive_path, extract_to, progress_callback, password)
        else:
            # Unknown format, use unar as ultimate fallback
            _extract_with_unar(archive_path, extract_to, progress_callback, password)

        if progress_callback:
            progress_callback(f"Archive extracted to: {extract_to}", 100)
        
        # 为解压出的可执行文件添加执行权限
        try:
            _set_executable_permissions(extract_to, progress_callback)
            if progress_callback:
                progress_callback("Executable permissions set", 100)
        except Exception as e:
            # 权限设置失败不应该影响解压结果，只是记录警告
            if progress_callback:
                progress_callback(f"Warning: Failed to set executable permissions: {str(e)}", 90)
        
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error extracting archive: {str(e)}", -1)
        # For password-related errors, re-raise exception
        if "password" in str(e).lower():
            raise
        return False

def _extract_with_python(archive_path, extract_to, archive_format, progress_callback=None, password=None):
    """Extract using Python built-in libraries"""
    if archive_format == "zip":
        # 只有当密码为None时才需要检查，空字符串应该被当作无密码处理
        # 空密码检查 - 只有当ZIP文件确实需要密码时才报错
        # First try with pyzipper for AES encrypted ZIPs
        if password and password.strip():  # 只有当密码非空且非空白时才使用
            try:
                import pyzipper
                try:
                    with pyzipper.AESZipFile(archive_path, 'r') as zipf:
                        zipf.setpassword(password.encode())
                        file_list = zipf.namelist()
                        total_files = len(file_list)
                        for i, file_name in enumerate(file_list):
                            try:
                                zipf.extract(file_name, extract_to)
                            except (RuntimeError, pyzipper.BadZipFile) as e:
                                error_msg = str(e).lower()
                                # 检查更多可能的密码错误关键词
                                password_error_keywords = [
                                    "bad password", "password required", "wrong password", 
                                    "authentication failed", "invalid password", "incorrect password",
                                    "wrong pass", "bad pass", "data error", "crc error"
                                ]
                                if any(keyword in error_msg for keyword in password_error_keywords):
                                    raise RuntimeError("Incorrect password for encrypted ZIP file")
                                raise
                            if progress_callback:
                                progress = ((i + 1) / total_files) * 100
                                progress_callback(f"Extracting {file_name}", progress)
                        return
                except (RuntimeError, pyzipper.BadZipFile) as e:
                    error_msg = str(e).lower()
                    password_error_keywords = [
                        "bad password", "password required", "wrong password", 
                        "authentication failed", "invalid password", "incorrect password",
                        "wrong pass", "bad pass", "data error", "crc error"
                    ]
                    if any(keyword in error_msg for keyword in password_error_keywords):
                        raise RuntimeError("Incorrect password for encrypted ZIP file")
                    # If not a password error, fall back to standard zipfile
            except ImportError:
                # pyzipper not available, fall back to standard zipfile
                pass
        
        # Standard zipfile handling
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            # Check if zip is password protected
            is_encrypted = any(info.flag_bits & 0x1 for info in zipf.infolist())
            
            # If the zip is encrypted but no password is provided, raise an error
            if is_encrypted and not password:
                raise RuntimeError("Password required for encrypted ZIP file")
            
            # If password is provided, set it
            if password and password.strip():  # 只有当密码非空且非空白时才使用
                try:
                    zipf.setpassword(password.encode())
                except:
                    raise RuntimeError("Incorrect password for encrypted ZIP file")
            
            file_list = zipf.namelist()
            total_files = len(file_list)
            for i, file_name in enumerate(file_list):
                try:
                    # 保留压缩包的目录结构
                    if file_name.endswith('/'):
                        # 如果是目录，创建完整路径
                        dir_path = os.path.join(extract_to, file_name.rstrip('/'))
                        if dir_path and dir_path != extract_to:  # 确保不是空路径或根目录
                            os.makedirs(dir_path, exist_ok=True)
                    else:
                        # 如果是文件，直接解压，保留路径结构
                        zipf.extract(file_name, extract_to)
                except (RuntimeError, zipfile.BadZipFile) as e:
                    error_msg = str(e).lower()
                    # 检查更多可能的密码错误关键词
                    password_error_keywords = [
                        "bad password", "password required", "wrong password", 
                        "authentication failed", "invalid password", "incorrect password",
                        "wrong pass", "bad pass", "data error", "crc error"
                    ]
                    if any(keyword in error_msg for keyword in password_error_keywords):
                        raise RuntimeError("Incorrect password for encrypted ZIP file")
                    raise
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
                # 保留TAR文件的目录结构，但清理绝对路径
                if member.name.startswith('/') or member.name.startswith('./'):
                    # 将绝对路径转换为相对路径，但保留目录结构
                    member.name = os.path.relpath(member.name, '/')
                    if member.name == '.':
                        member.name = os.path.basename(member.name)
                tarf.extract(member, extract_to)
                if progress_callback:
                    progress = ((i + 1) / total_members) * 100
                    progress_callback(f"Extracting {member.name}", progress)
    
    elif archive_format in ["bz2", "xz", "lzma"]:
        # Single file compression format
        import bz2
        import lzma
        
        output_file = os.path.join(extract_to, os.path.basename(archive_path).rsplit('.', 1)[0])
        
        if archive_format == "bz2":
            with bz2.open(archive_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    # Use binary mode for reading and writing
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        else:
            with lzma.open(archive_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    # Use binary mode for reading and writing
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        
        if progress_callback:
            progress_callback(f"Extracted {output_file}", 100)

def _extract_with_patool(archive_path, extract_to, progress_callback=None, password=None):
    """Extract using patool"""
    try:
        import patoolib
    except ImportError:
        raise ImportError("patool is required for this format")
    
    # patoolib doesn't directly support password, so we'll use unar for password-protected archives
    if password:
        _extract_with_unar(archive_path, extract_to, progress_callback, password)
        return
    
    patoolib.extract_archive(archive_path, outdir=extract_to)
    
    if progress_callback:
        progress_callback("Archive extracted", 100)

def _extract_rar_with_cli(archive_path, extract_to, progress_callback=None, password=None):
    """Extract RAR file using unrar CLI tool"""
    try:
        unrar_tool = _get_cli_tool("unrar", arch_specific=True)
    except FileNotFoundError:
        # Ultimate fallback: Use unar
        _extract_with_unar(archive_path, extract_to, progress_callback, password)
        return
    
    # 空密码检查
    if password == "":
        raise RuntimeError("Empty password not allowed for encrypted RAR file")
    
    cmd = [unrar_tool, "x", archive_path, extract_to + "/"]  # 保留目录结构
    if password:
        cmd.extend(["-p" + password, "-y"])  # Add password and assume yes for all queries
    else:
        cmd.append("-y")  # Assume yes for all queries
    
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        error_msg = result.stderr.lower()
        # 检查更多可能的密码错误关键词
        password_error_keywords = [
            "password incorrect", "wrong password", "bad password", 
            "authentication failed", "invalid password", "password required",
            "incorrect password", "wrong pass", "bad pass", "data error",
            "crc error", "headers error", "checksum error"
        ]
        
        if password and any(keyword in error_msg for keyword in password_error_keywords):
            raise RuntimeError("Incorrect password for encrypted RAR file")
        elif not password and any(keyword in error_msg for keyword in ["password", "encrypted", "authentication"]):
            raise RuntimeError("Password required for encrypted RAR file")
        elif not password and any(keyword in error_msg for keyword in password_error_keywords):
            # 如果没有提供密码，但错误信息包含密码错误关键词，说明需要密码
            raise RuntimeError("Password required for encrypted RAR file")
        raise RuntimeError(f"RAR extraction failed: {result.stderr}")
    else:
        # 即使unrar返回成功，我们也需要检查是否真的解压了文件
        # 有时unrar会返回成功但实际上没有解压任何文件（例如需要密码时）
        if not password:
            # 检查解压目录是否为空
            if not os.path.exists(extract_to) or not os.listdir(extract_to):
                raise RuntimeError("Password required for encrypted RAR file")
            
            # 检查解压的文件是否有效
            # 有时加密文件会被解压但内容为空或损坏
            extracted_files = []
            for root, dirs, files in os.walk(extract_to):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 检查文件是否为空
                    if os.path.getsize(file_path) > 0:
                        extracted_files.append(file_path)
            
            if not extracted_files:
                raise RuntimeError("Password required for encrypted RAR file")

def _extract_7z_with_cli(archive_path, extract_to, progress_callback=None, password=None):
    """Extract 7z file using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # Fallback: Use unar
        return _extract_with_unar(archive_path, extract_to, progress_callback, password)
    
    # 空密码检查
    if password == "":
        raise RuntimeError("Empty password not allowed for encrypted 7Z file")
    
    # 首先尝试测试文件是否需要密码
    test_cmd = [sevenz_tool, "t", archive_path]
    if password:
        test_cmd.extend(["-p" + password])
    else:
        test_cmd.append("-y")
    
    try:
        test_result = _run_command_with_timeout(test_cmd, timeout=5)
        # 如果测试失败且没有提供密码，检查是否需要密码
        if test_result.returncode != 0 and not password:
            error_msg = test_result.stderr.lower()
            if any(keyword in error_msg for keyword in ["password", "encrypted", "authentication"]):
                raise RuntimeError("Password required for encrypted 7Z file")
    except RuntimeError as e:
        if "timed out" in str(e).lower() and not password:
            # 如果超时且没有提供密码，可能是在等待密码输入
            raise RuntimeError("Password required for encrypted 7Z file")
        raise
    
    # 执行实际解压
    cmd = [sevenz_tool, "x", archive_path, f"-o{extract_to}"]  # 使用x命令保留目录结构
    if password:
        cmd.extend(["-p" + password, "-y"])  # Add password and assume yes for all queries
    else:
        cmd.append("-y")  # Assume yes for all queries
    
    result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
    
    if result.returncode != 0:
        error_msg = result.stderr.lower()
        # 检查更多可能的密码错误关键词
        password_error_keywords = [
            "password incorrect", "wrong password", "bad password", 
            "authentication failed", "invalid password", "password required",
            "incorrect password", "wrong pass", "bad pass", "data error",
            "crc error", "headers error", "unsupported method", "wrong password?"
        ]
        
        if password and any(keyword in error_msg for keyword in password_error_keywords):
            raise RuntimeError("Incorrect password for encrypted 7Z file")
        elif not password and any(keyword in error_msg for keyword in ["password", "encrypted", "authentication"]):
            raise RuntimeError("Password required for encrypted 7Z file")
        raise RuntimeError(f"7z extraction failed: {result.stderr}")
    
    return True

def _extract_iso_with_system(archive_path, extract_to, progress_callback=None):
    """Extract ISO file using system command"""
    if platform.system() == "Darwin":
        # macOS system, prioritize using hdiutil
        try:
            if progress_callback:
                progress_callback("Mounting ISO with hdiutil...", 0)
            
            # Mount ISO file
            cmd = ["hdiutil", "attach", archive_path]
            result = _run_command_with_timeout(cmd, timeout=10, progress_callback=progress_callback)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to mount ISO: {result.stderr}")
            
            # Parse mount point
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
            
            # Use rsync to copy files, preserving permissions and timestamps
            cmd = ["rsync", "-a", f"{mount_point}/", extract_to + "/"]
            result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
            
            # Unmount ISO
            cmd = ["hdiutil", "detach", mount_point]
            try:
                _run_command_with_timeout(cmd, timeout=5, progress_callback=progress_callback)
            except RuntimeError as e:
                # If unmount fails, log warning but don't interrupt process
                if progress_callback:
                    progress_callback(f"Warning: Failed to unmount ISO: {str(e)}", 90)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to copy files from ISO: {result.stderr}")
            
            if progress_callback:
                progress_callback("ISO extracted successfully", 100)
            
            return True
            
        except Exception as e:
            # If hdiutil fails, try using 7z as fallback
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
        # Other systems, use 7z
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

def _extract_cab_with_cabextract(archive_path, extract_to, progress_callback=None, password=None):
    """Extract CAB file using cabextract tool"""
    try:
        cabextract_tool = _get_cli_tool("cabextract")
    except FileNotFoundError:
        # Fallback: Use unar
        return _extract_with_unar(archive_path, extract_to, progress_callback, password)
    
    cmd = [cabextract_tool, "-d", extract_to]
    if password:
        # cabextract doesn't support password directly, fallback to unar
        return _extract_with_unar(archive_path, extract_to, progress_callback, password)
    cmd.append(archive_path)
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"CAB extraction failed: {result.stderr}")

def _extract_with_unar(archive_path, extract_to, progress_callback=None, password=None):
    """Use unar as ultimate fallback"""
    try:
        unar_tool = _get_cli_tool("unar")
    except FileNotFoundError:
        raise RuntimeError("No extraction tool available for this format")
    
    # 确保所有参数都有效，避免传递nil值给unar
    if not archive_path or not os.path.exists(archive_path):
        raise RuntimeError(f"Archive file not found or invalid: {archive_path}")
    
    if not extract_to:
        raise RuntimeError("Extract directory cannot be empty")
    
    # 确保输出目录存在
    os.makedirs(extract_to, exist_ok=True)
    
    cmd = [unar_tool, "-o", extract_to]
    # 只有当密码不为空、不为None且不为空白字符串时才添加密码参数
    if password is not None and password.strip():
        cmd.extend(["-p", password])
    cmd.append(archive_path)
    
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        error_msg = result.stderr.lower() + " " + result.stdout.lower()
        if password and ("password incorrect" in error_msg or "wrong password" in error_msg or "bad password" in error_msg or "authentication failed" in error_msg):
            raise RuntimeError("Incorrect password for encrypted archive")
        elif not password and any(keyword in error_msg for keyword in ["password", "encrypted", "authentication", "required", "requires a password"]):
            raise RuntimeError("Password required for encrypted archive")
        raise RuntimeError(f"Extraction failed: {result.stderr}")
    
    # 即使命令成功执行，也需要检查是否真的解压了文件
    if not password:
        # 检查解压目录是否为空
        extracted_files = []
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                extracted_files.append(os.path.join(root, file))
        
        if not extracted_files:
            raise RuntimeError("Password required for encrypted archive")
        
        # 检查解压的文件是否有效（非空）
        invalid_files = 0
        for file_path in extracted_files:
            try:
                if os.path.getsize(file_path) == 0:
                    invalid_files += 1
            except OSError:
                invalid_files += 1
        
        # 如果所有文件都是空的，可能是加密文件但没有提供密码
        if invalid_files == len(extracted_files) and len(extracted_files) > 0:
            raise RuntimeError("Password required for encrypted archive")

def list_archive_contents(archive_path, progress_callback=None, password=None):
    """
    List the contents of an archive file.

    Args:
        archive_path (str): Path to the archive file.
        progress_callback (function): Optional callback for progress updates.
        password (str): Optional password for encrypted archives.

    Returns:
        list: List of dictionaries containing file information.
    """
    try:
        # Check if file exists
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive file not found: {archive_path}")
        
        # Check if file is empty
        if os.path.getsize(archive_path) == 0:
            raise ValueError(f"Archive file is empty: {archive_path}")
        
        archive_format = _get_archive_type(archive_path)
        if not archive_format:
            raise ValueError(f"Unknown archive format: {archive_path}")

        if progress_callback:
            progress_callback(f"Listing {archive_format} contents...", 0)
        
        # Select processing method based on format - prioritize dedicated tools, use lsar as ultimate fallback
        if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "bz2", "xz", "lzma", "zipx"]:
            # Use Python built-in libraries (most stable)
            try:
                contents = _list_with_python(archive_path, archive_format, progress_callback, password)
            except RuntimeError as e:
                # For password-related errors, don't use fallback, re-raise exception directly
                if "password" in str(e).lower():
                    raise
                # For other errors, use lsar as fallback
                if progress_callback:
                    progress_callback(f"Python listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback, password)
            except Exception as e:
                # Use lsar as fallback when failed
                if progress_callback:
                    progress_callback(f"Python listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback, password)
        elif archive_format in ["rar"]:
            # Use unrar CLI tool, use lsar when failed
            try:
                contents = _list_rar_with_cli(archive_path, progress_callback, password)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"RAR listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback, password)
        elif archive_format in ["7z"]:
            # Use 7zz CLI tool, use lsar when failed
            try:
                contents = _list_7z_with_cli(archive_path, progress_callback, password)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"7z listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback, password)
        elif archive_format == "cab":
            # Prioritize using cabextract tool to list CAB file contents
            try:
                contents = _list_cab_with_cabextract(archive_path, progress_callback)
            except Exception as e:
                # Fallback: Use lsar
                if progress_callback:
                    progress_callback(f"CAB listing failed, trying lsar: {str(e)}", 50)
                contents = _list_with_lsar(archive_path, progress_callback, password)
        elif archive_format in ["arj", "lzh"]:
            # lsar supports these formats well, prioritize using lsar
            contents = _list_with_lsar(archive_path, progress_callback, password)
        elif archive_format == "iso":
            # ISO format uses 7zz tool to list contents
            try:
                contents = _list_iso_with_7z(archive_path, progress_callback)
            except Exception as e:
                # Fallback: Use lsar
                if progress_callback:
                    progress_callback(f"7z ISO listing failed, trying lsar: {str(e)}", 50)
                contents = _list_iso_with_lsar(archive_path, progress_callback)
        else:
            # Unknown format, use lsar as ultimate fallback
            if progress_callback:
                progress_callback(f"Unknown format {archive_format}, trying lsar", 50)
            contents = _list_with_lsar(archive_path, progress_callback, password)

        if progress_callback:
            progress_callback("Contents listed", 100)
        
        return contents

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error listing archive contents: {str(e)}", -1)
        raise  # Re-raise exception for caller to handle

def _list_with_python(archive_path, archive_format, progress_callback=None, password=None):
    """List contents using Python built-in libraries"""
    contents = []
    
    if archive_format == "zip" or archive_format == "zipx":
        # First try with pyzipper for AES encrypted ZIPs
        if password:
            try:
                import pyzipper
                try:
                    with pyzipper.AESZipFile(archive_path, 'r') as zipf:
                        zipf.setpassword(password.encode())
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
                        return contents
                except (RuntimeError, pyzipper.BadZipFile) as e:
                    if "Bad password" in str(e) or "password required" in str(e).lower():
                        raise RuntimeError("Incorrect password for encrypted ZIP file")
                    # If not a password error, fall back to standard zipfile
            except ImportError:
                # pyzipper not available, fall back to standard zipfile
                pass
        
        # Standard zipfile handling
        try:
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                # Check if zip is password protected
                is_encrypted = any(info.flag_bits & 0x1 for info in zipf.infolist())
                
                # If password is provided, set it
                if password:
                    try:
                        zipf.setpassword(password.encode())
                    except:
                        raise RuntimeError("Incorrect password for encrypted ZIP file")
                
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
        except (RuntimeError, zipfile.BadZipFile) as e:
            if "Bad password" in str(e) or "password required" in str(e).lower():
                raise RuntimeError("Incorrect password for encrypted ZIP file")
            raise
    
    elif archive_format.startswith("tar") or archive_format in ["bz2", "xz", "lzma"]:
        mode = "r"
        if archive_format == "tar.gz":
            mode = "r:gz"
        elif archive_format == "tar.bz2":
            mode = "r:bz2"
        elif archive_format == "tar.xz":
            mode = "r:xz"
        elif archive_format == "bz2":
            # Handle single bz2 file
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
            # Handle single xz file
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
            # Handle single lzma file
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

def _list_rar_with_cli(archive_path, progress_callback=None, password=None):
    """List RAR contents using unrar CLI tool"""
    try:
        unrar_tool = _get_cli_tool("unrar", arch_specific=True)
    except FileNotFoundError:
        # Ultimate fallback: Use lsar
        return _list_with_lsar(archive_path, progress_callback, password)
    
    cmd = [unrar_tool, "l", archive_path]
    if password:
        cmd.extend(["-p" + password])
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        # If password is provided and failed, try without password
        if password and any(keyword in result.stderr.lower() for keyword in ["password", "incorrect", "wrong"]):
            if progress_callback:
                progress_callback("Password failed, trying without password", 50)
            cmd = [unrar_tool, "l", archive_path]
            result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
            if result.returncode != 0:
                raise RuntimeError(f"RAR listing failed: {result.stderr}")
        else:
            raise RuntimeError(f"RAR listing failed: {result.stderr}")
    
    # Parse output
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

def _list_7z_with_cli(archive_path, progress_callback=None, password=None):
    """List 7z contents using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # Fallback: Use lsar
        return _list_with_lsar(archive_path, progress_callback, password)
    
    cmd = [sevenz_tool, "l", archive_path]
    if password:
        cmd.extend(["-p" + password])
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        # If password is provided and failed, try without password
        if password and any(keyword in result.stderr.lower() for keyword in ["password", "incorrect", "wrong", "data error"]):
            if progress_callback:
                progress_callback("Password failed, trying without password", 50)
            cmd = [sevenz_tool, "l", archive_path]
            result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
            if result.returncode != 0:
                raise RuntimeError(f"7z listing failed: {result.stderr}")
        else:
            raise RuntimeError(f"7z listing failed: {result.stderr}")
    
    # Parse output
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
    """List CAB file contents using cabextract tool"""
    try:
        cabextract_tool = _get_cli_tool("cabextract")
    except FileNotFoundError:
        # Fallback: Use lsar
        return _list_with_lsar(archive_path, progress_callback)
    
    cmd = [cabextract_tool, "-l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"CAB listing failed: {result.stderr}")
    
    # Parse cabextract output
    contents = []
    lines = result.stdout.split('\n')
    for line in lines:
        line = line.strip()
        # Skip header lines and empty lines
        if (line and not line.startswith('Viewing cabinet:') and 
            not line.startswith('File size') and not line.startswith('-----------') and 
            not line.startswith('All done')):
            # Parse format: file size | date time | file name
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
                            "is_dir": False  # CAB files don't support directories
                        }
                        contents.append(file_info)
                    except ValueError:
                        # If parsing fails, skip this line
                        continue
    
    return contents

def _list_iso_with_7z(archive_path, progress_callback=None):
    """List ISO contents using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # Fallback: Use lsar
        return _list_iso_with_lsar(archive_path, progress_callback)
    
    cmd = [sevenz_tool, "l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"ISO listing failed: {result.stderr}")
    
    # Parse 7z output
    contents = []
    lines = result.stdout.split('\n')
    in_file_list = False
    
    for line in lines:
        line = line.strip()
        # Check if entering file list section
        if line.startswith('-----') and not in_file_list:
            in_file_list = True
            continue
        
        # If already in file list section, encountering separator again means end
        if line.startswith('-----') and in_file_list:
            break
        
        # If in file list section, parse file information
        if in_file_list and line and not line.startswith('7-Zip') and not line.startswith('Scanning') and not line.startswith('Listing') and not line.startswith('Path') and not line.startswith('Type') and not line.startswith('Physical'):
            # 7z output format: date time attribute size compressed_size name
            # Example: 2025-10-03 18:47:54 .....        303          303  0000008C-00000000-454D4.TAGSET
            parts = line.split()
            if len(parts) >= 6:
                try:
                    # Try to parse size (5th element)
                    size = 0
                    if parts[4].isdigit():
                        size = int(parts[4])
                    
                    # File name is 6th element and all content after
                    name = ' '.join(parts[5:])
                    
                    # Check if it's a directory (contains D in attributes)
                    is_dir = 'D' in parts[3] if len(parts) > 3 else name.endswith('/')
                    
                    file_info = {
                        "name": name,
                        "size": size,
                        "compressed_size": size,  # ISO usually doesn't compress
                        "date": f"{parts[0]} {parts[1]}" if len(parts) > 1 else None,
                        "is_dir": is_dir
                    }
                    contents.append(file_info)
                except (ValueError, IndexError):
                    # If parsing fails, skip this line
                    continue
    
    return contents

def _list_iso_with_lsar(archive_path, progress_callback=None):
    """List ISO contents using lsar, specifically for ISO format"""
    try:
        lsar_tool = _get_cli_tool("lsar")
    except FileNotFoundError:
        raise RuntimeError("No listing tool available for ISO format")
    
    cmd = [lsar_tool, "-l", archive_path]
    result = _run_command_with_timeout(cmd, timeout=30, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"ISO listing failed: {result.stderr}")
    
    # Parse lsar output
    contents = []
    lines = result.stdout.split('\n')
    
    # Skip header lines, find data start position
    data_start = False
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and headers
        if not line:
            continue
            
        # Check if it's a header line
        if line.startswith('Flags') or line.startswith('=====') or line.startswith('ISO 9660'):
            continue
            
        # Check if it's a data line (starts with a number)
        if line and line[0].isdigit():
            # lsar output format: sequence. flag file_size ratio mode date time name
            # Example: 0. -----         303  -576%  ----  2025-10-03 18:47  0000008C-00000000-454D4.TAGSET
            parts = line.split()
            if len(parts) >= 8:
                try:
                    # Try to parse size (3rd element)
                    size = 0
                    if parts[2].isdigit():
                        size = int(parts[2])
                    
                    # File name is 8th element and all content after
                    name = ' '.join(parts[7:])
                    
                    # Check if it's a directory (based on name)
                    is_dir = name.endswith('/')
                    
                    file_info = {
                        "name": name,
                        "size": size,
                        "compressed_size": size,  # ISO usually doesn't compress
                        "date": f"{parts[5]} {parts[6]}" if len(parts) > 6 else None,
                        "is_dir": is_dir
                    }
                    contents.append(file_info)
                except (ValueError, IndexError):
                    # If parsing fails, skip this line
                    continue
    
    return contents

def _list_with_lsar(archive_path, progress_callback=None, password=None):
    """Use lsar as ultimate fallback to list contents"""
    try:
        lsar_tool = _get_cli_tool("lsar")
    except FileNotFoundError:
        # If lsar is not available, raise a more specific error for password-protected archives
        if password is None:
            # We can't determine if the archive is password protected without lsar
            # But we should raise an error to indicate the limitation
            raise RuntimeError("Listing tool not available - cannot determine if archive is password protected")
        else:
            # If we have a password, we can't verify it without lsar
            raise RuntimeError("Listing tool not available - cannot verify password for encrypted archive")
    
    cmd = [lsar_tool, "-l", archive_path]
    if password:
        cmd.extend(["-p", password])
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        # Check if this is a password-related error
        error_str = result.stderr.lower() if result.stderr else ""
        if "password" in error_str or "encrypted" in error_str or "authentication" in error_str:
            if password:
                # If password was provided and failed, try without password
                if progress_callback:
                    progress_callback("Password failed, trying without password", 50)
                cmd = [lsar_tool, "-l", archive_path]
                result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
                if result.returncode != 0:
                    raise RuntimeError(f"Listing failed: {result.stderr}")
            else:
                # Try without password first
                if progress_callback:
                    progress_callback("Archive may be password protected, trying without password", 50)
                cmd = [lsar_tool, "-l", archive_path]
                result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
                if result.returncode != 0:
                    raise RuntimeError("Password required for encrypted archive")
        else:
            raise RuntimeError(f"Listing failed: {result.stderr}")
    
    # Parse lsar output
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
        
        # Select processing method based on format
        if archive_format in ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]:
            # Use Python built-in libraries
            _add_with_python(archive_path, file_to_add_path, archive_format, progress_callback)
        elif archive_format in ["rar"]:
            # Use CLI tool
            _add_rar_with_cli(archive_path, file_to_add_path, progress_callback)
        elif archive_format in ["7z"]:
            # Use 7zz CLI tool
            _add_7z_with_cli(archive_path, file_to_add_path, progress_callback)
        else:
            # Other formats don't support adding files
            raise ValueError(f"Adding files to {archive_format} format is not supported")

        if progress_callback:
            progress_callback(f"File added to archive: {file_to_add_path}", 100)
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error adding to archive: {str(e)}", -1)
        return False

def _add_with_python(archive_path, file_to_add_path, archive_format, progress_callback=None):
    """Add file using Python built-in libraries"""
    if archive_format == "zip":
        with zipfile.ZipFile(archive_path, 'a') as zipf:
            file_name = os.path.basename(file_to_add_path)
            zipf.write(file_to_add_path, file_name)
    
    elif archive_format.startswith("tar"):
        # Correct tarfile mode parameter - use write mode instead of append mode
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
            
        # For tar files, need to recreate the entire archive
        # First read existing content, then add new file
        existing_files = []
        if os.path.exists(archive_path):
            try:
                with tarfile.open(archive_path, 'r') as tarf:
                    existing_files = tarf.getnames()
            except:
                existing_files = []
        
        # Recreate archive, including existing files and new file
        with tarfile.open(archive_path, mode) as tarf:
            # Add existing files
            for existing_file in existing_files:
                tarf.add(existing_file, arcname=existing_file)
            # Add new file
            file_name = os.path.basename(file_to_add_path)
            tarf.add(file_to_add_path, arcname=file_name)
    
    if progress_callback:
        progress_callback("File added", 100)

def _add_rar_with_cli(archive_path, file_to_add_path, progress_callback=None):
    """Add file to RAR using rar CLI tool"""
    try:
        rar_tool = _get_cli_tool("rar", arch_specific=True)
    except FileNotFoundError:
        raise RuntimeError("RAR tool not available for adding files")
    
    cmd = [rar_tool, "a", archive_path, file_to_add_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR add failed: {result.stderr}")

def _add_7z_with_cli(archive_path, file_to_add_path, progress_callback=None):
    """Add file to 7z using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        raise RuntimeError("7z tool not available for adding files")
    
    cmd = [sevenz_tool, "a", archive_path, file_to_add_path]
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z add failed: {result.stderr}")

# Test function
def batch_extract_archives(archive_paths, extract_to_base, progress_callback=None, password=None, 
                           overwrite_existing=False, create_subfolders=True, error_callback=None):
    """
    Extract multiple archive files in batch.
    
    Args:
        archive_paths (list): List of paths to archive files to extract.
        extract_to_base (str): Base directory to extract all archives to.
        progress_callback (function): Optional callback for overall progress updates (filename, progress).
        password (str): Optional password for encrypted archives.
        overwrite_existing (bool): Whether to overwrite existing files.
        create_subfolders (bool): Whether to create subfolders for each archive.
        error_callback (function): Optional callback for individual file error updates (filename, error).
        
    Returns:
        dict: Results dictionary with 'success_count', 'error_count', 'results' list.
    """
    results = {
        'success_count': 0,
        'error_count': 0,
        'results': []
    }
    
    total_archives = len(archive_paths)
    
    for i, archive_path in enumerate(archive_paths):
        try:
            # Calculate overall progress
            if progress_callback:
                overall_progress = (i / total_archives) * 100
                progress_callback(f"Processing {i+1}/{total_archives}: {os.path.basename(archive_path)}", overall_progress)
            
            # Determine extraction directory for this archive
            if create_subfolders:
                # Create subfolder named after archive (without extension)
                archive_name = os.path.splitext(os.path.basename(archive_path))[0]
                archive_extract_to = os.path.join(extract_to_base, archive_name)
            else:
                # Extract directly to base directory
                archive_extract_to = extract_to_base
            
            os.makedirs(archive_extract_to, exist_ok=True)
            
            # Create individual progress callback for this archive
            def archive_progress(message, percent):
                if progress_callback:
                    # Combine overall progress with archive-specific progress
                    archive_progress_value = (i + percent/100) / total_archives * 100
                    progress_callback(f"{os.path.basename(archive_path)}: {message}", archive_progress_value)
            
            # Extract the archive
            success = extract_archive(archive_path, archive_extract_to, 
                                    progress_callback=archive_progress, password=password)
            
            if success:
                results['success_count'] += 1
                results['results'].append({
                    'archive_path': archive_path,
                    'extract_to': archive_extract_to,
                    'status': 'success',
                    'error': None
                })
            else:
                results['error_count'] += 1
                error_msg = f"Extraction failed"
                if error_callback:
                    error_callback(archive_path, error_msg)
                results['results'].append({
                    'archive_path': archive_path,
                    'extract_to': archive_extract_to,
                    'status': 'error',
                    'error': error_msg
                })
                
        except Exception as e:
            results['error_count'] += 1
            error_msg = str(e)
            if error_callback:
                error_callback(archive_path, error_msg)
            results['results'].append({
                'archive_path': archive_path,
                'extract_to': archive_extract_to if 'archive_extract_to' in locals() else extract_to_base,
                'status': 'error',
                'error': error_msg
            })
    
    # Final progress update
    if progress_callback:
        progress_callback(f"Batch extraction complete: {results['success_count']}/{total_archives} successful", 100)
    
    return results

def test_archive_functions():
    """Test archive functions"""
    import tempfile
    import os
    
    print("=== Testing Archive Functions ===")
    
    # Create test file
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Hello Archive Test")
        
        # Test ZIP format
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
        
        # Test TAR.GZ format
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
        
        # Test RAR format (if available)
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
        
        # Test 7z format (if available)
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

def _set_executable_permissions(extract_to, progress_callback=None):
    """
    为解压出的可执行文件添加执行权限
    
    Args:
        extract_to (str): 解压目标目录
        progress_callback (function): 可选的进度回调函数
    """
    import stat
    import re
    
    # 定义可执行文件的常见扩展名
    executable_extensions = {
        '.sh', '.bash', '.zsh', '.fish', '.cmd', '.bat',  # Shell脚本
        '.py', '.pl', '.rb', '.php', '.js', '.ts',        # 脚本语言
        '.exe', '.app', '.bin', '.com',                   # 可执行文件
        '.run', '.install', '.setup'                      # 安装程序
    }
    
    # 需要检查shebang的文件扩展名
    script_extensions = {'.sh', '.bash', '.zsh', '.fish', '.py', '.pl', '.rb', '.php', '.js', '.ts'}
    
    executable_files = []
    
    def check_file_executable(file_path):
        """检查文件是否可能是可执行文件"""
        # 检查文件扩展名
        _, ext = os.path.splitext(file_path.lower())
        if ext in executable_extensions:
            return True
        
        # 对于没有后缀名的文件，直接返回True
        if not ext:
            return True
        
        # 检查shebang行（对于脚本文件）
        if ext in script_extensions:
            try:
                with open(file_path, 'rb') as f:
                    first_line = f.readline(100)  # 读取前100字节
                    if first_line.startswith(b'#!'):
                        return True
            except (IOError, UnicodeDecodeError):
                # 如果无法读取文件，跳过
                pass
        
        return False
    
    # 遍历解压目录中的所有文件
    for root, dirs, files in os.walk(extract_to):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            
            # 跳过隐藏文件和系统文件
            if file_name.startswith('.') or file_name in ['.DS_Store', 'Thumbs.db']:
                continue
                
            try:
                if check_file_executable(file_path):
                    # 添加执行权限 (755: rwxr-xr-x)
                    current_stat = os.stat(file_path)
                    os.chmod(file_path, current_stat.st_mode | stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    executable_files.append(file_path)
                    
                    if progress_callback:
                        progress_callback(f"Set executable permission: {file_name}", -1)  # -1表示不更新总体进度
                    
            except (OSError, IOError) as e:
                # 权限设置失败，记录但不影响解压
                if progress_callback:
                    progress_callback(f"Warning: Failed to set permission for {file_name}: {str(e)}", -1)
    
    if progress_callback and executable_files:
        progress_callback(f"Set executable permissions for {len(executable_files)} files", -1)

if __name__ == "__main__":
    test_archive_functions()