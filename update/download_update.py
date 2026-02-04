# -*- coding: utf-8 -*-
import requests
import os
import tempfile
import zipfile
import shutil
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
# Remove incompatible reconfigure calls for TextIO compatibility
class UpdateDownloader:
    def __init__(self, download_url: str, target_directory: str, progress_callback=None, max_threads=64):
        """
        Initialize the update downloader
        
        Args:
            download_url: URL of the GitHub release page
            target_directory: Target directory for downloaded files
            progress_callback: Progress callback function
            max_threads: Maximum number of threads for download (default: 16)
        """
        self.download_url = download_url
        self.target_directory = target_directory
        self.temp_dir = tempfile.mkdtemp(prefix="update_")
        self.progress_callback = progress_callback
        self.max_threads = max_threads
        self._download_lock = threading.Lock()
        self._downloaded_bytes = 0
        self._total_size = 0
        self._cancelled = False
        self._executor = None  # Thread pool executor reference
    
    def cancel(self):
        """Cancel the download"""
        with self._download_lock:
            self._cancelled = True
            # Force shutdown the thread pool if it exists
            if self._executor is not None:
                self._executor.shutdown(wait=False)
    
    def _extract_download_url(self, tag_name: str) -> Optional[str]:
        """
        Get the actual download URL from GitHub API
        
        Args:
            tag_name: Version tag name (e.g., v2.1.0A9)
            
        Returns:
            str: Actual zip file download URL, returns None if extraction fails
        """
        try:
            # Get platform architecture
            import platform
            machine = platform.machine().lower()
            if "arm" in machine:
                platform_str = "arm64"
            elif "x86_64" in machine:
                platform_str = "intel"
            else:
                platform_str = "intel"
            
            # Use GitHub API to get release information
            api_url = f"https://api.github.com/repos/pyquick/Converter/releases/tags/{tag_name}"
            response = requests.get(api_url, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code != 200:
                print(f"GitHub API request failed: {api_url} (status code: {response.status_code})")
                # Fallback to manually constructed URL
                download_url = f"https://github.com/pyquick/Converter/releases/download/{tag_name}/Converter_{platform_str}_darwin.zip"
                return download_url
            
            release_data = response.json()
            assets = release_data.get("assets", [])
            
            # Find files matching the platform
            expected_filename = f"Converter_{platform_str}_darwin.zip"
            for asset in assets:
                if asset.get("name") == expected_filename:
                    download_url = asset.get("browser_download_url")
                    if download_url:
                        print(f"Found matching download file: {expected_filename}")
                        return download_url
            
            # If no matching file is found, fallback to manually constructed URL
            print(f"No matching file found {expected_filename}, using manually constructed URL")
            download_url = f"https://github.com/pyquick/Converter/releases/download/{tag_name}/Converter_{platform_str}_darwin.zip"
            
            # Verify if URL is valid - use GET request as HEAD requests might be handled differently by CDN
            try:
                get_response = requests.get(download_url, timeout=10, stream=True)
                if get_response.status_code == 200:
                    return download_url
                else:
                    print(f"Invalid download URL: {download_url} (status code: {get_response.status_code})")
                    return None
            except requests.exceptions.RequestException:
                # If GET request fails, still return URL and let download process handle the error
                return download_url
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to extract download URL: {e}")
            # Fallback to manually constructed URL on error
            import platform
            machine = platform.machine().lower()
            if "arm" in machine:
                platform_str = "arm64"
            elif "x86_64" in machine:
                platform_str = "intel"
            else:
                platform_str = "intel"
            
            download_url = f"https://github.com/pyquick/Converter/releases/download/{tag_name}/Converter_{platform_str}_darwin.zip"
            return download_url
    
    def download_update(self, tag_name: str, progress_callback=None) -> Dict[str, Any]:
        """
        Download and extract update files
        
        Args:
            tag_name: Version tag name (e.g., v2.1.0A9)
            progress_callback: Progress callback function
            
        Returns:
            dict: Dictionary containing download status and information
        """
        try:
            # Check if download is cancelled before starting
            with self._download_lock:
                if self._cancelled:
                    return {
                        "status": "cancelled",
                        "message": "Download was cancelled by user"
                    }
            
            # Extract the actual download URL
            actual_download_url = self._extract_download_url(tag_name)
            if not actual_download_url:
                return {
                    "status": "error",
                    "message": "Unable to extract download link"
                }
            
            print(f"Starting to download update file: {actual_download_url}")
            self.progress_callback = progress_callback
            
            # Download file to temporary directory
            zip_path = os.path.join(self.temp_dir, "update.zip")
            
            # Add retry mechanism for SSL errors
            for attempt in range(3):
                # Check if download is cancelled
                with self._download_lock:
                    if self._cancelled:
                        return {
                            "status": "cancelled",
                            "message": "Download was cancelled by user"
                        }
                
                try:
                    # Try multi-threaded download first
                    try:
                        total_size = self._download_with_threads(actual_download_url, zip_path)
                        # Check if download was cancelled during the process
                        with self._download_lock:
                            if self._cancelled:
                                return {
                                    "status": "cancelled",
                                    "message": "Download was cancelled by user"
                                }
                        print(f"Multi-threaded download completed, total size: {total_size} bytes")
                    except Exception as e:
                        if "Download cancelled" in str(e):
                            # Re-raise cancellation exception
                            raise e
                        print(f"Multi-threaded download failed, falling back to single-threaded: {e}")
                        total_size = self._download_single_threaded(actual_download_url, zip_path)
                        # Check if download was cancelled during the process
                        with self._download_lock:
                            if self._cancelled:
                                return {
                                    "status": "cancelled",
                                    "message": "Download was cancelled by user"
                                }
                        print(f"Single-threaded download completed, total size: {total_size} bytes")
                    break  # Exit retry loop on success
                except requests.exceptions.SSLError as ssl_error:
                    # Check if download was cancelled
                    with self._download_lock:
                        if self._cancelled:
                            return {
                                "status": "cancelled",
                                "message": "Download was cancelled by user"
                            }
                    
                    if attempt == 2:  # Last attempt
                        raise ssl_error
                    print(f"SSL error (attempt {attempt + 1}/3): {ssl_error}")
                    time.sleep(2)  # Wait 2 seconds before retry
                except Exception as e:
                    # Check if download was cancelled
                    with self._download_lock:
                        if self._cancelled:
                            return {
                                "status": "cancelled",
                                "message": "Download was cancelled by user"
                            }
                    
                    if "Download cancelled" in str(e):
                        return {
                            "status": "cancelled",
                            "message": "Download was cancelled by user"
                        }
                    
                    if attempt == 2:  # Last attempt
                        raise e
                    print(f"Network error (attempt {attempt + 1}/3): {e}")
                    time.sleep(2)  # Wait 2 seconds before retry
            
            # Check if download was cancelled during the process
            with self._download_lock:
                if self._cancelled:
                    return {
                        "status": "cancelled",
                        "message": "Download was cancelled by user"
                    }
            
            print("Download completed, starting extraction...")
            
            # Extract files
            self._extract_zip(zip_path)
            
            return {
                "status": "success",
                "message": "Update downloaded and extracted successfully",
                "temp_dir": self.temp_dir
            }
            
        except Exception as e:
            # Check if download was cancelled
            with self._download_lock:
                if self._cancelled:
                    return {
                        "status": "cancelled",
                        "message": "Download was cancelled by user"
                    }
            
            # Ensure error messages handle non-ASCII characters correctly
            try:
                error_message = str(e)
                return {
                    "status": "error",
                    "message": f"Download failed: {error_message}"
                }
            except:
                return {
                    "status": "error",
                    "message": "Encoding error occurred during download"
                }
        except Exception as e:
            # Ensure error messages handle non-ASCII characters correctly
            try:
                error_message = str(e)
                return {
                    "status": "error", 
                    "message": f"Error occurred during update: {error_message}"
                }
            except:
                return {
                    "status": "error",
                    "message": "Encoding error occurred while processing update"
                }
    
    def _download_chunk(self, url, start_byte, end_byte, chunk_path, chunk_index):
        """Download a specific chunk of the file"""
        # Check if download is cancelled
        with self._download_lock:
            if self._cancelled:
                return chunk_path, "Download cancelled"
        
        headers = {'Range': f'bytes={start_byte}-{end_byte}'}
        
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(chunk_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # Check if download is cancelled
                    with self._download_lock:
                        if self._cancelled:
                            return chunk_path, "Download cancelled"
                    
                    if chunk:
                        f.write(chunk)
                        
                        # Update progress with thread safety
                        with self._download_lock:
                            if self._cancelled:
                                return chunk_path, "Download cancelled"
                            self._downloaded_bytes += len(chunk)
                            if self._total_size > 0 and self.progress_callback:
                                progress = int((self._downloaded_bytes / self._total_size) * 100)
                                self.progress_callback(progress, self._downloaded_bytes, self._total_size)
            
            return chunk_path, None
        except Exception as e:
            return chunk_path, str(e)
    
    def _download_with_threads(self, url, file_path):
        """Download file using multiple threads"""
        # Get file size
        try:
            response = requests.head(url, timeout=10)
            response.raise_for_status()
            file_size = int(response.headers.get('content-length', 0))
        except:
            # If HEAD request fails, fall back to single-threaded download
            return self._download_single_threaded(url, file_path)
        
        if file_size == 0:
            # If size is unknown, fall back to single-threaded download
            return self._download_single_threaded(url, file_path)
        
        # Check if download is cancelled before starting
        with self._download_lock:
            if self._cancelled:
                return 0
        
        self._total_size = file_size
        self._downloaded_bytes = 0
        
        # Initialize progress callback with total size
        if self.progress_callback:
            self.progress_callback(0, 0, file_size)
        
        # Calculate chunk size
        chunk_size = math.ceil(file_size / self.max_threads)
        chunks = []
        
        # Create temporary directory for chunks
        chunks_dir = os.path.join(self.temp_dir, "chunks")
        os.makedirs(chunks_dir, exist_ok=True)
        
        # Prepare chunks
        for i in range(self.max_threads):
            start = i * chunk_size
            end = min((i + 1) * chunk_size - 1, file_size - 1)
            if start >= file_size:
                break
                
            chunk_path = os.path.join(chunks_dir, f"chunk_{i}")
            chunks.append((start, end, chunk_path, i))
        
        # Download chunks using thread pool
        try:
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                # Save executor reference for cancellation
                with self._download_lock:
                    self._executor = executor
                
                futures = []
                for start, end, chunk_path, i in chunks:
                    future = executor.submit(self._download_chunk, url, start, end, chunk_path, i)
                    futures.append(future)
                
                # Wait for all downloads to complete
                errors = []
                for future in as_completed(futures):
                    # Check if download is cancelled
                    with self._download_lock:
                        if self._cancelled:
                            # Cancel remaining futures
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            raise Exception("Download cancelled")
                    
                    chunk_path, error = future.result()
                    if error:
                        errors.append(f"Error downloading {chunk_path}: {error}")
                
                # Check for errors
                if errors:
                    raise Exception(f"Multi-threaded download failed: {'; '.join(errors)}")
                
                # Check if download was cancelled
                with self._download_lock:
                    if self._cancelled:
                        raise Exception("Download cancelled")
        
        finally:
            # Clear executor reference
            with self._download_lock:
                self._executor = None
        
        # Merge chunks
        with self._download_lock:
            if self._cancelled:
                return 0
        
        with open(file_path, 'wb') as outfile:
            for i in range(len(chunks)):
                # Check if download is cancelled during merge
                with self._download_lock:
                    if self._cancelled:
                        return 0
                
                chunk_path = os.path.join(chunks_dir, f"chunk_{i}")
                if os.path.exists(chunk_path):
                    with open(chunk_path, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
        
        # Clean up chunks
        shutil.rmtree(chunks_dir)
        
        return file_size
    
    def _download_single_threaded(self, url, file_path):
        """Fallback single-threaded download method"""
        # Check if download is cancelled
        with self._download_lock:
            if self._cancelled:
                return 0
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # Initialize progress callback with total size
            if self.progress_callback:
                self.progress_callback(0, 0, total_size)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # Check if download is cancelled
                    with self._download_lock:
                        if self._cancelled:
                            response.close()  # Close the connection
                            return downloaded
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Display download progress
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            if self.progress_callback:
                                self.progress_callback(progress, downloaded, total_size)
            
            return total_size
        except Exception as e:
            # Check if download was cancelled
            with self._download_lock:
                if self._cancelled:
                    return 0
            # Re-raise the exception if not cancelled
            raise e
    
    def _extract_zip(self, zip_path: str):
        """Extract zip file to temporary directory"""
        with self._download_lock:
            if self._cancelled:
                raise Exception("Download cancelled")
        
        with zipfile.ZipFile(zip_path, 'r', metadata_encoding='utf-8') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        print(f"Files extracted to: {self.temp_dir}")
    
    def _apply_update(self):
        """Apply update - Prepare update script and restart script, apply update to /Applications directory"""
        # Find the extracted main directory
        extracted_items = os.listdir(self.temp_dir)
        
        # Check if there are .app files directly in the temporary directory
        app_files = [f for f in extracted_items if f.endswith('.app') and os.path.isdir(os.path.join(self.temp_dir, f))]
        
        if app_files:
            # If there are .app files, use the temporary directory directly as source directory
            source_dir = self.temp_dir
        else:
            # Otherwise look for subdirectories
            extracted_dirs = [d for d in extracted_items 
                             if os.path.isdir(os.path.join(self.temp_dir, d))]
            
            if not extracted_dirs:
                # If no subdirectories, use the temporary directory directly as source directory
                source_dir = self.temp_dir
            else:
                # If there are subdirectories, use the first subdirectory
                source_dir = os.path.join(self.temp_dir, extracted_dirs[0])
        
        # Create target directory (for storing update scripts)
        target_com_dir = os.path.expanduser("~/.converter/update/com")
        os.makedirs(target_com_dir, exist_ok=True)
        
        # Copy update files to a temporary location that will be used by the update script
        temp_update_dir = os.path.join(tempfile.gettempdir(), "converter_update")
        if os.path.exists(temp_update_dir):
            shutil.rmtree(temp_update_dir)
        shutil.copytree(source_dir, temp_update_dir)
        
        # Copy update_apply.command script to target directory
        script_source = os.path.join(os.path.dirname(__file__), "update_apply.command")
        script_target = os.path.join(target_com_dir, "update_apply.command")
        
        if os.path.exists(script_source):
            shutil.copy2(script_source, script_target)
            # Set script execution permissions
            os.chmod(script_target, 0o755)
            print(f"✅ Update script copied to: {script_target}")
        else:
            print(f"❌ Update script does not exist: {script_source}")
        
        # Copy restart.command script to target directory
        restart_script_source = os.path.join(os.path.dirname(__file__), "restart.command")
        restart_script_target = os.path.join(target_com_dir, "restart.command")
        
        if os.path.exists(restart_script_source):
            shutil.copy2(restart_script_source, restart_script_target)
            # Set script execution permissions
            os.chmod(restart_script_target, 0o755)
            print(f"✅ Restart script copied to: {restart_script_target}")
        else:
            print(f"❌ Restart script does not exist: {restart_script_source}")
        
        # Create a launcher script that will ensure the app is fully terminated before applying update
        launcher_script = os.path.join(target_com_dir, "update_launcher.command")
        with open(launcher_script, 'w') as f:
            f.write(f"""#!/bin/bash

# Update Launcher Script - Ensures app is fully terminated before applying update

echo "🔄 Preparing to apply update..."

# Kill any running Converter processes
echo "🔄 Terminating any running Converter processes..."
pkill -f "Converter.app" 2>/dev/null || true
pkill -f "Converter" 2>/dev/null || true

# Wait a bit to ensure processes are fully terminated
echo "⏳ Waiting for processes to fully terminate..."
sleep 3

# Check if processes are still running and force kill if needed
if pgrep -f "Converter.app" > /dev/null || pgrep -f "Converter" > /dev/null; then
    echo "🔄 Force terminating remaining processes..."
    pkill -9 -f "Converter.app" 2>/dev/null || true
    pkill -9 -f "Converter" 2>/dev/null || true
    sleep 2
fi

# Execute the update apply script with the temporary update directory
echo "🚀 Applying update from: {temp_update_dir}"
"{script_target}" "{temp_update_dir}"

# Execute the restart script
echo "🔄 Restarting application..."
"{restart_script_target}"

echo "✅ Update process completed"
""")
        
        # Set script execution permissions
        os.chmod(launcher_script, 0o755)
        print(f"✅ Update launcher script created at: {launcher_script}")
        
        print("✅ Update preparation completed, update will be applied after the application terminates")
        
        return launcher_script
    
    def _create_launcher_script(self):
        """Create a launcher script that will ensure the app is fully terminated before applying update"""
        # Create target directory (for storing update scripts)
        target_com_dir = os.path.expanduser("~/.converter/update/com")
        os.makedirs(target_com_dir, exist_ok=True)
        
        # Copy update files to a temporary location that will be used by the update script
        temp_update_dir = os.path.join(tempfile.gettempdir(), "converter_update")
        if os.path.exists(temp_update_dir):
            shutil.rmtree(temp_update_dir)
        shutil.copytree(self.temp_dir, temp_update_dir)
        
        # Copy update_apply.command script to target directory
        script_source = os.path.join(os.path.dirname(__file__), "update_apply.command")
        script_target = os.path.join(target_com_dir, "update_apply.command")
        
        if os.path.exists(script_source):
            shutil.copy2(script_source, script_target)
            # Set script execution permissions
            os.chmod(script_target, 0o755)
            print(f"✅ Update script copied to: {script_target}")
        else:
            print(f"❌ Update script does not exist: {script_source}")
        
        # Copy restart.command script to target directory
        restart_script_source = os.path.join(os.path.dirname(__file__), "restart.command")
        restart_script_target = os.path.join(target_com_dir, "restart.command")
        
        if os.path.exists(restart_script_source):
            shutil.copy2(restart_script_source, restart_script_target)
            # Set script execution permissions
            os.chmod(restart_script_target, 0o755)
            print(f"✅ Restart script copied to: {restart_script_target}")
        else:
            print(f"❌ Restart script does not exist: {restart_script_source}")
        
        # Create a launcher script that will ensure the app is fully terminated before applying update
        launcher_script = os.path.join(target_com_dir, "update_launcher.command")
        with open(launcher_script, 'w') as f:
            f.write(f"""#!/bin/bash

# Update Launcher Script - Ensures app is fully terminated before applying update

echo "🔄 Preparing to apply update..."

# Kill any running Converter processes
echo "🔄 Terminating any running Converter processes..."
pkill -f "Converter.app" 2>/dev/null || true
pkill -f "Converter" 2>/dev/null || true

# Wait a bit to ensure processes are fully terminated
echo "⏳ Waiting for processes to fully terminate..."
sleep 3

# Check if processes are still running and force kill if needed
if pgrep -f "Converter.app" > /dev/null || pgrep -f "Converter" > /dev/null; then
    echo "🔄 Force terminating remaining processes..."
    pkill -9 -f "Converter.app" 2>/dev/null || true
    pkill -9 -f "Converter" 2>/dev/null || true
    sleep 2
fi

# Execute the update apply script with the temporary update directory
echo "🚀 Applying update from: {temp_update_dir}"
"{script_target}" "{temp_update_dir}"

# Execute the restart script
echo "🔄 Restarting application..."
"{restart_script_target}"

echo "✅ Update process completed"
""")
        
        # Set script execution permissions
        os.chmod(launcher_script, 0o755)
        print(f"✅ Update launcher script created at: {launcher_script}")
        
        print("✅ Update preparation completed, update will be applied after the application terminates")
        
        return launcher_script
    
    def cleanup(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"Temporary files cleaned up: {self.temp_dir}")


def download_and_apply_update(update_info: Dict[str, Any], progress_callback=None, downloader=None) -> Dict[str, Any]:
    """
    Convenience function to download and apply updates
    
    Args:
        update_info: Update information dictionary returned by UpdateManager
        progress_callback: Progress callback function
        downloader: Optional UpdateDownloader instance to use
        
    Returns:
        dict: Download result (contains downloader object for subsequent cleanup)
    """
    download_url = update_info.get("download_url", "")
    latest_version = update_info.get("latest_version", "")
    
    if not download_url or not latest_version:
        return {
            "status": "error",
            "message": "Missing necessary URL or version number in update information"
        }
    
    # Use provided downloader or create a new one
    if downloader is None:
        # Create target directory for update
        target_directory = tempfile.mkdtemp(prefix="converter_update_")
        downloader = UpdateDownloader(download_url, target_directory)
        created_downloader = True
    else:
        created_downloader = False
    
    try:
        result = downloader.download_update(latest_version, progress_callback)
        
        if result["status"] == "success":
            # Start the launcher script in a new process
            import subprocess
            import sys
            
            # Create a new launcher script that will ensure the app is fully terminated before applying update
            launcher_script = downloader._create_launcher_script()
            
            print("🚀 Starting update process...")
            try:
                # Use subprocess.Popen to start the launcher script in a new process
                subprocess.Popen(['open', launcher_script], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
                
                # Exit the current application to allow the update to proceed
                print("✅ Update process started, exiting application...")
                sys.exit(0)
                
            except Exception as e:
                print(f"❌ Failed to start update process: {e}")
                result["status"] = "error"
                result["message"] = f"Failed to start update process: {e}"
                # Clean up if we created the downloader and update failed
                if created_downloader:
                    downloader.cleanup()
                return result
        
        # Add downloader object to result for cleanup by caller when appropriate
        result["downloader"] = downloader
        result["created_downloader"] = created_downloader
        return result
    except Exception as e:
        # Clean up immediately if an exception occurs
        if created_downloader:
            downloader.cleanup()
        return {
            "status": "error",
            "message": f"Error occurred during download: {e}"
        }


if __name__ == "__main__":
    # Test code
    test_info = {
        "download_url": "https://github.com/pyquick/converter/releases/tag/v2.1.0A9",
        "latest_version": "2.1.0A9"
    }
    
    result = download_and_apply_update(test_info, "./test_update")
    print(f"Test result: {result}")