import os
import sys
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

def _run_command_with_timeout(cmd, timeout=2, progress_callback=None, cwd=None):
    """Run command with timeout limit"""
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        
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
        
        # For password-protected ZIP files, use CLI tool
        if archive_format == "zip" and password:
            if progress_callback:
                progress_callback(f"Creating password-protected ZIP file with CLI tool...", 10)
            
            # Use CLI tool for password-protected ZIP files
            success = _create_zip_with_cli(output_path, source_paths, progress_callback, password)
            if not success:
                raise RuntimeError(f"Failed to create password-protected ZIP archive")
        else:
            # Select processing method based on format
            if progress_callback:
                progress_callback(f"Creating {archive_format} archive...", 40)
            
            success = False
            if archive_format == "zip":
                # Use CLI tool for ZIP creation
                success = _create_zip_with_cli(output_path, source_paths, progress_callback, password)
            elif archive_format in ["tar", "tar.gz", "tar.bz2", "tar.xz", "zipx"]:
                # Use CLI tool for processing
                success = _create_tar_with_cli(output_path, source_paths, archive_format, progress_callback)
            elif archive_format in ["bz2", "xz", "lzma", "gz"]:
                # These formats can only compress single files, so need to create tar first, then compress
                success = _create_single_file_compression(output_path, source_paths, archive_format, progress_callback)
            elif archive_format == "cab":
                # Use cabextract related tools for CAB creation
                success = _create_cab_with_cli(output_path, source_paths, progress_callback)
            elif archive_format in ["arj", "lzh"]:
                # Use unar/lsar for processing
                success = _create_with_unar(output_path, source_paths, archive_format, progress_callback)
            elif archive_format == "rar":
                # Use rar CLI tool
                success = _create_rar_with_cli(output_path, source_paths, progress_callback, password)
            elif archive_format == "7z":
                # Use 7zz CLI tool
                success = _create_7z_with_cli(output_path, source_paths, progress_callback, password)
            elif archive_format == "iso":
                # Use system command
                success = _create_iso_with_system(output_path, source_paths, progress_callback)
            else:
                raise ValueError(f"Unsupported archive format for creation: {archive_format}")
            
            if not success:
                raise RuntimeError(f"Failed to create {archive_format} archive")

        if progress_callback:
            progress_callback(f"Archive created: {output_path}", 100)
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating archive: {str(e)}", -1)
        return False



def _create_single_file_compression(output_path, source_paths, compression_format, progress_callback=None):
    """
    Create single file compression format (bz2, xz, lzma, gz)
    These formats can only compress single files, so need to create tar first, then compress
    """
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Step 1: Create tar file using tar command
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            tar_path = os.path.join(temp_dir, f"{base_name}.tar")
            
            if progress_callback:
                progress_callback(f"Creating intermediate tar file...", 30)
            
            # Build tar command
            cmd = ["tar", "-c", "-f", tar_path]
            
            # Process source paths
            if len(source_paths) == 1:
                source_path = source_paths[0]
                if os.path.isdir(source_path):
                    # For directories, add directory contents
                    work_dir = os.path.dirname(source_path) or "."
                    rel_path = os.path.basename(source_path)
                    cmd.append(rel_path)
                else:
                    # For files, use directory containing the file
                    work_dir = os.path.dirname(source_path) or "."
                    rel_path = os.path.basename(source_path)
                    cmd.append(rel_path)
            else:
                # Multiple sources - use parent directory as working directory
                work_dir = os.path.commonpath([os.path.dirname(p) if os.path.isfile(p) else p for p in source_paths])
                for source_path in source_paths:
                    if os.path.isfile(source_path):
                        cmd.append(os.path.basename(source_path))
                    elif os.path.isdir(source_path):
                        cmd.append(os.path.basename(source_path))
            
            # Run tar command
            result = _run_command_with_timeout(cmd, cwd=work_dir, timeout=30)
            
            if result.returncode != 0:
                raise RuntimeError(f"tar creation failed: {result.stderr}")
            
            if not os.path.exists(tar_path):
                raise RuntimeError("Failed to create intermediate tar file")
            
            # Step 2: Compress tar file using appropriate command
            if progress_callback:
                progress_callback(f"Compressing tar file with {compression_format}...", 60)
            
            # Build compression command based on format
            if compression_format == "gz":
                try:
                    gzip_tool = _get_cli_tool("gzip")
                    cmd = [gzip_tool, "-c", tar_path]
                except FileNotFoundError:
                    # Fallback to system gzip
                    cmd = ["gzip", "-c", tar_path]
                output_file = open(output_path, "wb")
                result = subprocess.run(cmd, stdout=output_file, stderr=subprocess.PIPE)
                output_file.close()
            elif compression_format == "bz2":
                try:
                    bzip2_tool = _get_cli_tool("bzip2")
                    cmd = [bzip2_tool, "-c", tar_path]
                except FileNotFoundError:
                    # Fallback to system bzip2
                    cmd = ["bzip2", "-c", tar_path]
                output_file = open(output_path, "wb")
                result = subprocess.run(cmd, stdout=output_file, stderr=subprocess.PIPE)
                output_file.close()
            elif compression_format == "xz":
                try:
                    xz_tool = _get_cli_tool("xz")
                    cmd = [xz_tool, "-c", tar_path]
                    output_file = open(output_path, "wb")
                    result = subprocess.run(cmd, stdout=output_file, stderr=subprocess.PIPE)
                    output_file.close()
                except FileNotFoundError:
                    # Fallback to 7zz tool
                    try:
                        sevenz_tool = _get_cli_tool("7zz")
                        cmd = [sevenz_tool, "a", "-txz", output_path, tar_path]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                    except FileNotFoundError:
                        # Final fallback to system xz
                        cmd = ["xz", "-c", tar_path]
                        output_file = open(output_path, "wb")
                        result = subprocess.run(cmd, stdout=output_file, stderr=subprocess.PIPE)
                        output_file.close()
            elif compression_format == "lzma":
                # Use Python's lzma module directly
                try:
                    import lzma
                    with open(tar_path, 'rb') as f_in:
                        with lzma.open(output_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    # Create a dummy successful result
                    class DummyResult:
                        def __init__(self):
                            self.returncode = 0
                            self.stderr = ""
                    result = DummyResult()
                except Exception as e:
                    raise RuntimeError(f"Failed to create LZMA archive: {str(e)}")
            else:
                raise ValueError(f"Unsupported compression format: {compression_format}")
            
            if result.returncode != 0:
                raise RuntimeError(f"Compression failed: {result.stderr}")
            
            if progress_callback:
                progress_callback(f"{compression_format} archive created", 90)
                
            return True
        finally:
            shutil.rmtree(temp_dir)
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating {compression_format} archive: {str(e)}", -1)
        return False

def _create_zip_with_cli(output_path, source_paths, progress_callback=None, password=None):
    """Create ZIP file using zip CLI tool"""
    try:
        zip_tool = _get_cli_tool("zip")
    except FileNotFoundError:
        # If zip tool is not found, raise an error instead of falling back to patool
        raise RuntimeError("zip tool not found. Please install zip command-line tool")
    
    # Build zip command - use working directory approach
    temp_dir = None  # Initialize temp_dir to None
    if len(source_paths) == 1:
        # Single source - can use directly
        source_path = source_paths[0]
        if os.path.isdir(source_path):
            # For directories, use relative path from parent directory
            work_dir = os.path.dirname(source_path) or "."
            rel_path = os.path.basename(source_path)
        else:
            # For files, use directory containing the file
            work_dir = os.path.dirname(source_path) or "."
            rel_path = os.path.basename(source_path)
    else:
        # Multiple sources - create temporary directory approach
        temp_dir = tempfile.mkdtemp()
        work_dir = temp_dir
        rel_paths = []
        
        try:
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    dest_path = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copy2(source_path, dest_path)
                    rel_paths.append(os.path.basename(source_path))
                elif os.path.isdir(source_path):
                    dest_path = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copytree(source_path, dest_path)
                    rel_paths.append(os.path.basename(source_path))
        except Exception:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise
        
        source_paths = rel_paths
    
    try:
        cmd = [zip_tool, "-r"]
        if password:
            cmd.extend(["-P", password])
        cmd.append(output_path)
        cmd.extend(source_paths if len(source_paths) > 1 else [rel_path])
        
        # Ensure output path is absolute
        output_path_abs = os.path.abspath(output_path)
        cmd[cmd.index(output_path)] = output_path_abs
        
        if progress_callback:
            progress_callback(f"Creating ZIP archive with CLI tool...", 50)
        
        result = _run_command_with_timeout(cmd, cwd=work_dir, timeout=500000, progress_callback=progress_callback)
        
        if result.returncode != 0:
            raise RuntimeError(f"ZIP creation failed: {result.stderr}")
        
        if progress_callback:
            progress_callback(f"ZIP archive created successfully", 90)
        
        return True
    finally:
        # Clean up temporary directory if it was created
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def _create_cab_with_cli(output_path, source_paths, progress_callback=None):
    """Create CAB archive file using gcab tool"""
    # Use project's built-in gcab tool directly
    gcab_tool = os.path.join(CLI_BASE_PATH, "Universal", "gcab")
    
    if not os.path.exists(gcab_tool):
        raise RuntimeError(f"Built-in gcab tool not found at {gcab_tool}")
    
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
                progress_callback(f"Copying files for CAB archive...", progress)
        
        if not copied_files:
            raise ValueError("No valid source files found")
        
        # Build gcab command for CAB format
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
                progress_callback("CAB archive created successfully", 100)
                
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
    
    # Build rar command - use working directory approach
    temp_dir = None  # Initialize temp_dir to None
    if len(source_paths) == 1:
        # Single source - can use directly
        source_path = source_paths[0]
        if os.path.isdir(source_path):
            # For directories, use relative path from parent directory
            work_dir = os.path.dirname(source_path) or "."
            rel_path = os.path.basename(source_path)
        else:
            # For files, use directory containing the file
            work_dir = os.path.dirname(source_path) or "."
            rel_path = os.path.basename(source_path)
    else:
        # Multiple sources - create temporary directory approach
        temp_dir = tempfile.mkdtemp()
        work_dir = temp_dir
        rel_paths = []
        
        try:
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    dest_path = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copy2(source_path, dest_path)
                    rel_paths.append(os.path.basename(source_path))
                elif os.path.isdir(source_path):
                    dest_path = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copytree(source_path, dest_path)
                    rel_paths.append(os.path.basename(source_path))
        except Exception:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise
        
        source_paths = rel_paths
    
    try:
        cmd = [rar_tool, "a", "-r"]
        if password:
            cmd.extend(["-p" + password, "-y"])
        else:
            cmd.append("-y")
        cmd.append(output_path)
        cmd.extend(source_paths if len(source_paths) > 1 else [rel_path])
        
        # Ensure output path is absolute
        output_path_abs = os.path.abspath(output_path)
        cmd[cmd.index(output_path)] = output_path_abs
        
        result = _run_command_with_timeout(cmd, cwd=work_dir, timeout=500000, progress_callback=progress_callback)
        
        if result.returncode != 0:
            raise RuntimeError(f"RAR creation failed: {result.stderr}")
        
        return True
    finally:
        # Clean up temporary directory if it was created
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def _create_tar_with_cli(output_path, source_paths, archive_format, progress_callback=None, password=None):
    """Create tar file using system tar command"""
    try:
        if progress_callback:
            progress_callback(f"Creating {archive_format} archive with tar command...", 0)
        
        # Ensure output path is absolute
        output_path_abs = os.path.abspath(output_path)
        
        # Build tar command based on format
        cmd = ["tar", "-c"]
        
        # Add compression options based on format
        if archive_format == "tar.gz" or archive_format == "tgz":
            cmd.append("-z")
        elif archive_format == "tar.bz2" or archive_format == "tbz2":
            cmd.append("-j")
        elif archive_format == "tar.xz" or archive_format == "txz":
            cmd.append("-J")
        
        # Add output file option
        cmd.extend(["-f", output_path_abs])
        
        # Handle password protection for zipx format
        if archive_format == "zipx" and password:
            # For zipx, we'll create a standard zip with password protection
            return _create_zip_with_cli(output_path, source_paths, progress_callback, password)
        
        # Process source paths
        if len(source_paths) == 1:
            source_path = source_paths[0]
            if os.path.isdir(source_path):
                # For directories, add directory contents
                work_dir = os.path.dirname(source_path) or "."
                rel_path = os.path.basename(source_path)
                cmd.append(rel_path)
            else:
                # For files, use directory containing the file
                work_dir = os.path.dirname(source_path) or "."
                rel_path = os.path.basename(source_path)
                cmd.append(rel_path)
        else:
            # Multiple sources - use parent directory as working directory
            work_dir = os.path.commonpath([os.path.dirname(p) if os.path.isfile(p) else p for p in source_paths])
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    cmd.append(os.path.basename(source_path))
                elif os.path.isdir(source_path):
                    cmd.append(os.path.basename(source_path))
        
        if progress_callback:
            progress_callback(f"Running tar command for {archive_format}...", 50)
        
        # Run tar command
        result = _run_command_with_timeout(cmd, cwd=work_dir, timeout=30, progress_callback=progress_callback)
        
        if result.returncode != 0:
            raise RuntimeError(f"tar creation failed: {result.stderr}")
        
        # Handle zipx format (rename tar to zipx)
        if archive_format == "zipx":
            temp_path = output_path_abs + ".tmp"
            os.rename(output_path_abs, temp_path)
            os.rename(temp_path, output_path)
        
        if progress_callback:
            progress_callback(f"{archive_format} archive created successfully", 100)
        
        return True
    
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error creating {archive_format} archive: {str(e)}", -1)
        return False

def _create_7z_with_cli(output_path, source_paths, progress_callback=None, password=None):
    """Create 7z file using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        # Fallback: Use unar/lsar
        _create_with_unar(output_path, source_paths, "7z", progress_callback)
        return True
    
    # Build 7z command - use working directory approach
    temp_dir = None  # Initialize temp_dir to None
    if len(source_paths) == 1:
        # Single source - can use directly
        source_path = source_paths[0]
        if os.path.isdir(source_path):
            # For directories, use relative path from parent directory
            work_dir = os.path.dirname(source_path) or "."
            rel_path = os.path.basename(source_path)
        else:
            # For files, use directory containing the file
            work_dir = os.path.dirname(source_path) or "."
            rel_path = os.path.basename(source_path)
    else:
        # Multiple sources - create temporary directory approach
        temp_dir = tempfile.mkdtemp()
        work_dir = temp_dir
        rel_paths = []
        
        try:
            for source_path in source_paths:
                if os.path.isfile(source_path):
                    dest_path = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copy2(source_path, dest_path)
                    rel_paths.append(os.path.basename(source_path))
                elif os.path.isdir(source_path):
                    dest_path = os.path.join(temp_dir, os.path.basename(source_path))
                    shutil.copytree(source_path, dest_path)
                    rel_paths.append(os.path.basename(source_path))
        except Exception:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise
        
        source_paths = rel_paths
    
    try:
        cmd = [sevenz_tool, "a"]
        if password:
            cmd.extend(["-p" + password, "-y"])
        else:
            cmd.append("-y")
        cmd.append(output_path)
        cmd.extend(source_paths if len(source_paths) > 1 else [rel_path])
        
        # Ensure output path is absolute
        output_path_abs = os.path.abspath(output_path)
        cmd[cmd.index(output_path)] = output_path_abs
        
        result = _run_command_with_timeout(cmd, cwd=work_dir, timeout=500000, progress_callback=progress_callback)
        
        if result.returncode != 0:
            raise RuntimeError(f"7z creation failed: {result.stderr}")
        
        return True
    finally:
        # Clean up temporary directory if it was created
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def _create_iso_with_system(output_path, source_paths, progress_callback=None):
    """Create ISO file using system command"""
    if len(source_paths) != 1 or not os.path.isdir(source_paths[0]):
        raise ValueError("ISO format only supports creating from a single directory")
    
    source_dir = source_paths[0]
    
    # Ensure output path is absolute
    output_path_abs = os.path.abspath(output_path)
    
    # Try using hdiutil (macOS)
    if platform.system() == "Darwin":
        cmd = ["hdiutil", "makehybrid", "-o", output_path_abs, "-hfs", "-iso", "-joliet", source_dir]
    else:
        # Other systems use mkisofs
        cmd = ["mkisofs", "-o", output_path_abs, "-J", "-R", source_dir]
    
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
            # Use unar directly for zipx format
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
                # Check if exception message contains password-related keywords
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
        
        # Add execute permissions for extracted executable files
        try:
            _set_executable_permissions(extract_to, progress_callback)
            if progress_callback:
                progress_callback("Executable permissions set", 100)
        except Exception as e:
            # Permission setting failure should not affect extraction result, just log warning
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
                                # 清理绝对路径，防止解压到系统目录
                                if file_name.startswith('/') or file_name.startswith('./'):
                                    # 将绝对路径转换为相对路径
                                    file_name = os.path.relpath(file_name, '/')
                                    if file_name == '.':
                                        continue  # 跳过当前目录引用
                                
                                # 防止路径遍历攻击（../）
                                if '..' in file_name.split(os.sep):
                                    # 跳过包含父目录引用的路径
                                    continue
                                
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
                    # 清理绝对路径，防止解压到系统目录
                    if file_name.startswith('/') or file_name.startswith('./'):
                        # 将绝对路径转换为相对路径
                        file_name = os.path.relpath(file_name, '/')
                        if file_name == '.':
                            continue  # 跳过当前目录引用
                    
                    # 防止路径遍历攻击（../）
                    if '..' in file_name.split(os.sep):
                        # 跳过包含父目录引用的路径
                        continue
                    
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
        
        # 检查解压后的目录中是否包含系统目录
        if progress_callback:
            try:
                # 检查解压后的目录中是否包含系统目录
                for root, dirs, files in os.walk(extract_to):
                    for dir_name in dirs:
                        # 检查是否是系统目录
                        if dir_name.lower() in ['bin', 'sbin', 'usr', 'etc', 'var', 'sys', 'proc', 'dev', 'boot', 'lib', 'lib64', 'opt', 'run', 'srv', 'tmp']:
                            full_path = os.path.join(root, dir_name)
                            progress_callback(f"警告: 检测到系统目录 {full_path}", 50)
            except Exception as e:
                # 忽略检查过程中的错误
                pass
    
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
        
        # 检查解压后的目录中是否包含系统目录
        if progress_callback:
            try:
                # 检查解压后的目录中是否包含系统目录
                for root, dirs, files in os.walk(extract_to):
                    for dir_name in dirs:
                        # 检查是否是系统目录
                        if dir_name.lower() in ['bin', 'sbin', 'usr', 'etc', 'var', 'sys', 'proc', 'dev', 'boot', 'lib', 'lib64', 'opt', 'run', 'srv', 'tmp']:
                            full_path = os.path.join(root, dir_name)
                            progress_callback(f"警告: 检测到系统目录 {full_path}", 50)
            except Exception as e:
                # 忽略检查过程中的错误
                pass
    
    elif archive_format in ["bz2", "xz", "lzma"]:
        # Single file compression format
        import bz2
        import lzma
        import tarfile
        
        # First, decompress the file to a temporary tar file
        temp_tar = os.path.join(extract_to, os.path.basename(archive_path).rsplit('.', 1)[0] + '.tar')
        
        try:
            if archive_format == "bz2":
                with bz2.open(archive_path, 'rb') as f_in:
                    with open(temp_tar, 'wb') as f_out:
                        # Use binary mode for reading and writing
                        while True:
                            chunk = f_in.read(8192)
                            if not chunk:
                                break
                            f_out.write(chunk)
            else:
                with lzma.open(archive_path, 'rb') as f_in:
                    with open(temp_tar, 'wb') as f_out:
                        # Use binary mode for reading and writing
                        while True:
                            chunk = f_in.read(8192)
                            if not chunk:
                                break
                            f_out.write(chunk)
            
            # Now extract the tar file
            with tarfile.open(temp_tar, 'r') as tarf:
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
            
            # Clean up the temporary tar file
            os.remove(temp_tar)
            
        except Exception as e:
            # Clean up the temporary tar file if it exists
            if os.path.exists(temp_tar):
                os.remove(temp_tar)
            raise e
        
        if progress_callback:
            progress_callback(f"Extracted {archive_format} archive", 100)



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
    
    # 检查并警告潜在的绝对路径解压问题
    if os.path.exists(extract_to):
        # 检查解压目录中是否包含系统目录
        for item in os.listdir(extract_to):
            item_path = os.path.join(extract_to, item)
            if os.path.isdir(item_path):
                # 检查是否是常见的系统目录
                if item in ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'sys', 'proc', 'dev']:
                    if progress_callback:
                        progress_callback(f"Warning: System directory '{item}' was extracted. This may indicate absolute paths in the archive.", -1)

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
    
    # 检查并警告潜在的绝对路径解压问题
    if os.path.exists(extract_to):
        # 检查解压目录中是否包含系统目录
        for item in os.listdir(extract_to):
            item_path = os.path.join(extract_to, item)
            if os.path.isdir(item_path):
                # 检查是否是常见的系统目录
                if item in ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'sys', 'proc', 'dev']:
                    if progress_callback:
                        progress_callback(f"Warning: System directory '{item}' was extracted. This may indicate absolute paths in the archive.", -1)
    
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
            
            # 检查并警告潜在的绝对路径解压问题
            if os.path.exists(extract_to):
                # 检查解压目录中是否包含系统目录
                for item in os.listdir(extract_to):
                    item_path = os.path.join(extract_to, item)
                    if os.path.isdir(item_path):
                        # 检查是否是常见的系统目录
                        if item in ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'sys', 'proc', 'dev']:
                            if progress_callback:
                                progress_callback(f"Warning: System directory '{item}' was extracted. This may indicate absolute paths in the archive.", -1)
            
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
                
                # 检查并警告潜在的绝对路径解压问题
                if os.path.exists(extract_to):
                    # 检查解压目录中是否包含系统目录
                    for item in os.listdir(extract_to):
                        item_path = os.path.join(extract_to, item)
                        if os.path.isdir(item_path):
                            # 检查是否是常见的系统目录
                            if item in ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'sys', 'proc', 'dev']:
                                if progress_callback:
                                    progress_callback(f"Warning: System directory '{item}' was extracted. This may indicate absolute paths in the archive.", -1)
                
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
            
            # 检查并警告潜在的绝对路径解压问题
            if os.path.exists(extract_to):
                # 检查解压目录中是否包含系统目录
                for item in os.listdir(extract_to):
                    item_path = os.path.join(extract_to, item)
                    if os.path.isdir(item_path):
                        # 检查是否是常见的系统目录
                        if item in ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'sys', 'proc', 'dev']:
                            if progress_callback:
                                progress_callback(f"Warning: System directory '{item}' was extracted. This may indicate absolute paths in the archive.", -1)
            
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
    
    # 检查并警告潜在的绝对路径解压问题
    if os.path.exists(extract_to):
        # 检查解压目录中是否包含系统目录
        for item in os.listdir(extract_to):
            item_path = os.path.join(extract_to, item)
            if os.path.isdir(item_path):
                # 检查是否是常见的系统目录
                if item in ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'sys', 'proc', 'dev']:
                    if progress_callback:
                        progress_callback(f"Warning: System directory '{item}' was extracted. This may indicate absolute paths in the archive.", -1)

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
    
    # 即使unar命令成功执行，也需要检查解压结果，防止创建系统目录
    # 检查是否创建了var目录或其他系统目录
    system_dirs = ['var', 'etc', 'usr', 'bin', 'sbin', 'lib', 'tmp', 'dev', 'proc', 'sys']
    for root, dirs, files in os.walk(extract_to):
        for dir_name in dirs:
            if dir_name in system_dirs:
                # 如果发现系统目录，需要检查是否是绝对路径导致的问题
                full_path = os.path.join(root, dir_name)
                rel_path = os.path.relpath(full_path, extract_to)
                # 如果是直接在解压根目录下创建的系统目录，可能是绝对路径问题
                if os.path.dirname(rel_path) == '' and dir_name in ['var', 'tmp']:
                    print(f"Warning: Detected potential system directory extraction: {rel_path}")
    
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

def add_to_archive(archive_path, file_to_add_path, progress_callback=None, target_path=None):
    """
    Add a file to an existing archive file.

    Args:
        archive_path (str): Path to the existing archive file.
        file_to_add_path (str): Path to the file to add.
        progress_callback (function): Optional callback for progress updates.
        target_path (str): Optional target path within archive (e.g., "folder/subfolder").
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
            _add_with_python(archive_path, file_to_add_path, archive_format, progress_callback, target_path)
        elif archive_format in ["rar"]:
            # Use CLI tool
            _add_rar_with_cli(archive_path, file_to_add_path, progress_callback, target_path)
        elif archive_format in ["7z"]:
            # Use 7zz CLI tool
            _add_7z_with_cli(archive_path, file_to_add_path, progress_callback, target_path)
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

def _add_with_python(archive_path, file_to_add_path, archive_format, progress_callback=None, target_path=None):
    """Add file using Python built-in libraries"""
    # Determine arcname (path within archive)
    if target_path:
        arcname = os.path.join(target_path, os.path.basename(file_to_add_path)).replace("\\", "/")
    else:
        arcname = os.path.basename(file_to_add_path)
    
    if archive_format == "zip":
        with zipfile.ZipFile(archive_path, 'a') as zipf:
            zipf.write(file_to_add_path, arcname)
    
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
            # Add new file with target path
            tarf.add(file_to_add_path, arcname=arcname)
    
    if progress_callback:
        progress_callback("File added", 100)

def _add_rar_with_cli(archive_path, file_to_add_path, progress_callback=None, target_path=None):
    """Add file to RAR using rar CLI tool"""
    try:
        rar_tool = _get_cli_tool("rar", arch_specific=True)
    except FileNotFoundError:
        raise RuntimeError("RAR tool not available for adding files")
    
    cmd = [rar_tool, "a"]
    if target_path:
        cmd.extend(["-ap", target_path])
    cmd.extend([archive_path, file_to_add_path])
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"RAR add failed: {result.stderr}")

def _add_7z_with_cli(archive_path, file_to_add_path, progress_callback=None, target_path=None):
    """Add file to 7z using 7zz CLI tool"""
    try:
        sevenz_tool = _get_cli_tool("7zz")
    except FileNotFoundError:
        raise RuntimeError("7z tool not available for adding files")
    
    cmd = [sevenz_tool, "a"]
    if target_path:
        # 7z uses -w for working directory, but for target path we need to use the full path in the file spec
        # or use the -spf option to preserve full paths
        full_target = os.path.join(target_path, os.path.basename(file_to_add_path))
        cmd.extend([archive_path, full_target])
    else:
        cmd.extend([archive_path, file_to_add_path])
    result = _run_command_with_timeout(cmd, timeout=2, progress_callback=progress_callback)
    
    if result.returncode != 0:
        raise RuntimeError(f"7z add failed: {result.stderr}")

# Test function
def batch_extract_archives(archive_paths, extract_to_base, progress_callback=None, password=None, 
                           overwrite_existing=False, create_subfolders=True, error_callback=None,
                           password_callback=None, password_detector=None):
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
        password_callback (function): Optional callback to request password from user (archive_path, format, is_protected).
        password_detector (PasswordDetector): Optional password detector instance for checking protected archives.
        
    Returns:
        dict: Results dictionary with 'success_count', 'error_count', 'results' list.
    """
    results = {
        'success_count': 0,
        'error_count': 0,
        'results': []
    }
    
    # 初始化密码检测器
    if password_detector is None:
        try:
            from password_detector import PasswordDetector
            password_detector = PasswordDetector()
        except ImportError:
            password_detector = None
    
    # 缓存密码避免重复询问
    password_cache = {}
    
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
            
            # 检测密码保护状态
            current_password = password
            if password_detector and password_callback:
                try:
                    detection_result = password_detector.is_password_protected(archive_path)
                    if detection_result['is_protected']:
                        archive_format = detection_result.get('format', 'unknown')
                        
                        # 检查是否已有该格式的密码
                        if archive_format not in password_cache:
                            # 询问用户输入密码
                            if progress_callback:
                                progress_callback(f"检测到密码保护的 {archive_format.upper()} 文件: {os.path.basename(archive_path)}", 
                                                (i / total_archives) * 100)
                            
                            requested_password = password_callback(archive_path, archive_format, True)
                            if requested_password:
                                password_cache[archive_format] = requested_password
                                current_password = requested_password
                            else:
                                # 用户取消操作
                                results['error_count'] += 1
                                error_msg = "用户取消密码输入"
                                if error_callback:
                                    error_callback(archive_path, error_msg)
                                results['results'].append({
                                    'archive_path': archive_path,
                                    'extract_to': archive_extract_to,
                                    'status': 'cancelled',
                                    'error': error_msg
                                })
                                continue
                        else:
                            current_password = password_cache[archive_format]
                    elif detection_result.get('error'):
                        # 检测出错，但仍然尝试正常解压
                        if error_callback:
                            error_callback(archive_path, f"密码检测失败: {detection_result['error']}")
                except Exception as e:
                    # 密码检测失败，继续尝试正常解压
                    if error_callback:
                        error_callback(archive_path, f"密码检测出错: {str(e)}")
            
            # Create individual progress callback for this archive
            def archive_progress(message, percent):
                if progress_callback:
                    # Combine overall progress with archive-specific progress
                    archive_progress_value = (i + percent/100) / total_archives * 100
                    progress_callback(f"{os.path.basename(archive_path)}: {message}", archive_progress_value)
            
            # Extract the archive
            success = extract_archive(archive_path, archive_extract_to, 
                                    progress_callback=archive_progress, password=current_password)
            
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
        progress_callback(results['success_count'], total_archives, f"Batch extraction complete: {results['success_count']}/{total_archives} successful")
    
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
    Add execute permissions for extracted executable files
    
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


# ==================== Enhanced Test Suite ====================

def run_comprehensive_tests():
    """Run comprehensive tests for all archive operations"""
    import tempfile
    import os
    
    print("=" * 70)
    print("Archive Manager - Comprehensive Test Suite")
    print("=" * 70)
    
    test_results = {
        'passed': 0,
        'failed': 0,
        'tests': []
    }
    
    def record_test(name, success, message=""):
        status = "PASS" if success else "FAIL"
        test_results['tests'].append((name, success, message))
        if success:
            test_results['passed'] += 1
            print(f"  [{status}] {name}")
        else:
            test_results['failed'] += 1
            print(f"  [{status}] {name}: {message}")
    
    # Create temporary directory for tests
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\n[Test Environment]")
        print(f"  Temp directory: {tmpdir}")
        
        # Create test files
        test_files = []
        for i in range(3):
            test_file = os.path.join(tmpdir, f"test_file_{i+1}.txt")
            with open(test_file, 'w') as f:
                f.write(f"Test content {i+1}\n" * 100)
            test_files.append(test_file)
        
        print(f"  Created {len(test_files)} test files")
        
        # Test 1: ZIP Create
        print("\n[Archive Creation Tests]")
        zip_path = os.path.join(tmpdir, "test.zip")
        try:
            create_archive(zip_path, test_files, 'zip', None, None)
            record_test("ZIP Creation", os.path.exists(zip_path), 
                       f"Size: {os.path.getsize(zip_path)} bytes" if os.path.exists(zip_path) else "File not created")
        except Exception as e:
            record_test("ZIP Creation", False, str(e))
        
        # Test 2: TAR.GZ Create
        tar_gz_path = os.path.join(tmpdir, "test.tar.gz")
        try:
            create_archive(tar_gz_path, test_files, 'tar.gz', None, None)
            record_test("TAR.GZ Creation", os.path.exists(tar_gz_path),
                       f"Size: {os.path.getsize(tar_gz_path)} bytes" if os.path.exists(tar_gz_path) else "File not created")
        except Exception as e:
            record_test("TAR.GZ Creation", False, str(e))
        
        # Test 3: 7z Create
        seven_z_path = os.path.join(tmpdir, "test.7z")
        try:
            create_archive(seven_z_path, test_files, '7z', None, None)
            record_test("7z Creation", os.path.exists(seven_z_path),
                       f"Size: {os.path.getsize(seven_z_path)} bytes" if os.path.exists(seven_z_path) else "File not created")
        except Exception as e:
            record_test("7z Creation", False, str(e))
        
        # Test 4: ZIP Extract
        print("\n[Archive Extraction Tests]")
        extract_dir = os.path.join(tmpdir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        try:
            extract_archive(zip_path, extract_dir, None, None)
            extracted_files = os.listdir(extract_dir)
            record_test("ZIP Extraction", len(extracted_files) == len(test_files),
                       f"Extracted {len(extracted_files)} files")
        except Exception as e:
            record_test("ZIP Extraction", False, str(e))
        
        # Test 5: List Contents
        print("\n[List Contents Tests]")
        try:
            contents = list_archive_contents(zip_path, None)
            record_test("List ZIP Contents", len(contents) == len(test_files),
                       f"Found {len(contents)} items")
        except Exception as e:
            record_test("List ZIP Contents", False, str(e))
        
        # Test 6: Add to Archive
        print("\n[Add to Archive Tests]")
        new_file = os.path.join(tmpdir, "new_file.txt")
        with open(new_file, 'w') as f:
            f.write("New file content\n")
        
        try:
            add_to_archive(zip_path, new_file, None)
            contents = list_archive_contents(zip_path, None)
            record_test("Add to ZIP", len(contents) == len(test_files) + 1,
                       f"Archive now has {len(contents)} items")
        except Exception as e:
            record_test("Add to ZIP", False, str(e))
        
        # Test 7: Password Protected 7z
        print("\n[Password Protection Tests]")
        password = "test123"
        protected_path = os.path.join(tmpdir, "protected.7z")
        
        try:
            # Try to create with password (may not be supported by all backends)
            create_archive(protected_path, test_files, '7z', None, password)
            record_test("Password-Protected 7z Creation", os.path.exists(protected_path),
                       "Created with password" if os.path.exists(protected_path) else "Failed")
            
            # Try to extract with password
            if os.path.exists(protected_path):
                protected_extract = os.path.join(tmpdir, "protected_extract")
                os.makedirs(protected_extract, exist_ok=True)
                extract_archive(protected_path, protected_extract, None, password)
                extracted = os.listdir(protected_extract)
                record_test("Password-Protected 7z Extraction", len(extracted) == len(test_files),
                           f"Extracted {len(extracted)} files")
        except Exception as e:
            record_test("Password-Protected 7z", False, str(e))
        
        # Test 8: Batch Extract
        print("\n[Batch Operations Tests]")
        batch_dir = os.path.join(tmpdir, "batch")
        os.makedirs(batch_dir, exist_ok=True)
        
        # Create multiple archives
        archives = []
        for i in range(3):
            arc_path = os.path.join(batch_dir, f"archive_{i+1}.zip")
            try:
                create_archive(arc_path, test_files, 'zip', None, None)
                archives.append(arc_path)
            except:
                pass
        
        try:
            batch_result = batch_extract_archives(
                archives,
                os.path.join(tmpdir, "batch_extracted"),
                create_subfolders=True,
                overwrite_existing=True
            )
            record_test("Batch Extract", batch_result.get('error_count', 0) == 0,
                       f"Success: {batch_result.get('success_count', 0)}, Failed: {batch_result.get('error_count', 0)}")
        except Exception as e:
            record_test("Batch Extract", False, str(e))
        
        # Test 9: Archive Type Detection
        print("\n[Archive Type Detection Tests]")
        test_cases = [
            (zip_path, "zip"),
            (tar_gz_path, "tar.gz"),
            (seven_z_path, "7z"),
        ]
        
        for file_path, expected_type in test_cases:
            try:
                detected = _get_archive_type(file_path)
                record_test(f"Detect {expected_type.upper()}", detected == expected_type,
                           f"Detected: {detected}")
            except Exception as e:
                record_test(f"Detect {expected_type.upper()}", False, str(e))
    
    # Print Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    total = test_results['passed'] + test_results['failed']
    print(f"  Total:  {total}")
    print(f"  Passed: {test_results['passed']}")
    print(f"  Failed: {test_results['failed']}")
    print(f"  Rate:   {test_results['passed']/total*100:.1f}%" if total > 0 else "  Rate:   N/A")
    print("=" * 70)
    
    return test_results['failed'] == 0


# ==================== CLI Interface ====================

def cli_progress_callback(message, percentage):
    """CLI progress callback"""
    if percentage >= 0:
        print(f"[{percentage:3d}%] {message}")
    else:
        print(f"[INFO] {message}")


def cli_main():
    """Command Line Interface for archive_manager"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Archive Manager CLI - Create and extract archive files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show help (default)
  python archive_manager.py
  
  # Run comprehensive tests
  python archive_manager.py test
  
  # Create archive
  python archive_manager.py create -s file1.txt file2.txt -o output.zip -f zip
  
  # Extract archive
  python archive_manager.py extract -a archive.zip -d ./output
  
  # Batch extract
  python archive_manager.py batch-extract -a *.zip -d ./output
  
  # List contents
  python archive_manager.py list -a archive.zip
  
  # Add files to archive
  python archive_manager.py add -a archive.zip -s newfile.txt
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run comprehensive tests')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create an archive')
    create_parser.add_argument('-s', '--sources', nargs='+', required=True,
                              help='Source files/directories to archive')
    create_parser.add_argument('-o', '--output', required=True,
                              help='Output archive path')
    create_parser.add_argument('-f', '--format', default='zip',
                              choices=SUPPORTED_ARCHIVE_FORMATS,
                              help='Archive format (default: zip)')
    create_parser.add_argument('-p', '--password',
                              help='Password for encrypted archive')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract an archive')
    extract_parser.add_argument('-a', '--archive', required=True,
                               help='Archive file to extract')
    extract_parser.add_argument('-d', '--dest', required=True,
                               help='Destination directory')
    extract_parser.add_argument('-p', '--password',
                               help='Password for encrypted archive')
    
    # Batch extract command
    batch_parser = subparsers.add_parser('batch-extract', help='Batch extract archives')
    batch_parser.add_argument('-a', '--archives', nargs='+', required=True,
                             help='Archive files to extract')
    batch_parser.add_argument('-d', '--dest', required=True,
                             help='Destination directory')
    batch_parser.add_argument('--subfolders', action='store_true',
                             help='Create subfolders for each archive')
    batch_parser.add_argument('--overwrite', action='store_true',
                             help='Overwrite existing files')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List archive contents')
    list_parser.add_argument('-a', '--archive', required=True,
                            help='Archive file to list')
    list_parser.add_argument('-p', '--password',
                            help='Password for encrypted archive')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add files to archive')
    add_parser.add_argument('-a', '--archive', required=True,
                           help='Archive file to add to')
    add_parser.add_argument('-s', '--sources', nargs='+', required=True,
                           help='Files to add')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show supported formats')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == 'test':
            success = run_comprehensive_tests()
            return 0 if success else 1
            
        elif args.command == 'create':
            print(f"Creating archive: {args.output}")
            print(f"Format: {args.format}")
            print(f"Sources: {', '.join(args.sources)}")
            if args.password:
                print("Password protection: Yes")
            
            create_archive(args.output, args.sources, args.format, 
                          cli_progress_callback, args.password)
            print(f"\n[SUCCESS] Archive created: {args.output}")
            return 0
            
        elif args.command == 'extract':
            print(f"Extracting: {args.archive}")
            print(f"Destination: {args.dest}")
            
            extract_archive(args.archive, args.dest, cli_progress_callback, args.password)
            print(f"\n[SUCCESS] Archive extracted to: {args.dest}")
            return 0
            
        elif args.command == 'batch-extract':
            print(f"Batch extracting {len(args.archives)} archives")
            print(f"Destination: {args.dest}")
            
            def batch_progress(current, total, current_file=""):
                if isinstance(current, str):
                    print(f"[INFO] {current}")
                else:
                    pct = int((current / total) * 100) if total > 0 else 0
                    print(f"[{pct:3d}%] Processing {current}/{total}: {os.path.basename(str(current_file))}")
            
            result = batch_extract_archives(
                args.archives,
                args.dest,
                progress_callback=batch_progress,
                create_subfolders=args.subfolders,
                overwrite_existing=args.overwrite
            )
            
            print(f"\n[SUCCESS] Batch extraction complete:")
            print(f"  Success: {result.get('success_count', 0)}")
            print(f"  Failed: {result.get('error_count', 0)}")
            print(f"  Skipped: {result.get('skipped_count', 0)}")
            return 0
            
        elif args.command == 'list':
            print(f"Listing contents of: {args.archive}")
            contents = list_archive_contents(args.archive, args.password)
            
            print(f"\nArchive contents ({len(contents)} items):")
            print("-" * 60)
            for item in contents:
                if isinstance(item, dict):
                    name = item.get('name', 'Unknown')
                    size = item.get('size', 0)
                    is_dir = item.get('is_dir', False)
                    type_str = "DIR" if is_dir else "FILE"
                    size_str = f"{size:>10} bytes" if not is_dir else ""
                    print(f"[{type_str:4}] {name:50} {size_str}")
                else:
                    print(f"       {item}")
            return 0
            
        elif args.command == 'add':
            print(f"Adding files to: {args.archive}")
            print(f"Files: {', '.join(args.sources)}")
            
            for source in args.sources:
                add_to_archive(args.archive, source, cli_progress_callback)
            
            print(f"\n[SUCCESS] Files added to archive")
            return 0
            
        elif args.command == 'info':
            print("Archive Manager - Supported Formats")
            print("=" * 60)
            print("Supported archive formats:")
            for fmt in SUPPORTED_ARCHIVE_FORMATS:
                print(f"  - {fmt}")
            print("\nCLI Tools:")
            cli_tools = ['7z', 'unar', 'tar', 'zip', 'unzip']
            for tool in cli_tools:
                tool_path = os.path.join(CLI_BASE_PATH, tool)
                exists = os.path.exists(tool_path)
                status = "✓" if exists else "✗"
                print(f"  {status} {tool}")
            return 0
            
    except Exception as e:
        print(f"\n[ERROR] {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Default to CLI mode (shows help if no arguments)
    cli_main()