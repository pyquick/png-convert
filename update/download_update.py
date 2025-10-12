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
# Remove incompatible reconfigure calls for TextIO compatibility
class UpdateDownloader:
    def __init__(self, download_url: str, target_directory: str, progress_callback=None):
        """
        Initialize the update downloader
        
        Args:
            download_url: URL of the GitHub release page
            target_directory: Target directory for downloaded files
            progress_callback: Progress callback function
        """
        self.download_url = download_url
        self.target_directory = target_directory
        self.temp_dir = tempfile.mkdtemp(prefix="update_")
        self.progress_callback = progress_callback
    
    def _extract_download_url(self, tag_name: str) -> Optional[str]:
        """
        Get the actual download URL from GitHub API
        
        Args:
            tag_name: Version tag name (e.g., v2.0.0)
            
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
    
    def download_update(self, tag_name: str) -> Dict[str, Any]:
        """
        Download and extract update files
        
        Args:
            tag_name: Version tag name (e.g., v2.0.0)
            
        Returns:
            dict: Dictionary containing download status and information
        """
        try:
            # Extract the actual download URL
            actual_download_url = self._extract_download_url(tag_name)
            if not actual_download_url:
                return {
                    "status": "error",
                    "message": "Unable to extract download link"
                }
            
            print(f"Starting to download update file: {actual_download_url}")
            
            # Download file to temporary directory
            zip_path = os.path.join(self.temp_dir, "update.zip")
            
            # Add retry mechanism for SSL errors
            for attempt in range(3):
                try:
                    response = requests.get(actual_download_url, stream=True, timeout=30)
                    response.raise_for_status()
                    break  # Exit retry loop on success
                except requests.exceptions.SSLError as ssl_error:
                    if attempt == 2:  # Last attempt
                        raise ssl_error
                    print(f"SSL error (attempt {attempt + 1}/3): {ssl_error}")
                    time.sleep(2)  # Wait 2 seconds before retry
                except requests.exceptions.RequestException as e:
                    if attempt == 2:  # Last attempt
                        raise e
                    print(f"Network error (attempt {attempt + 1}/3): {e}")
                    time.sleep(2)  # Wait 2 seconds before retry
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Display download progress
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            print(f"Download progress: {progress}% ({downloaded}/{total_size} bytes)",end="\r")
                            # Call progress callback function, passing progress, downloaded size and total size
                            if self.progress_callback:
                                self.progress_callback(progress, downloaded, total_size)
            
            print("Download completed, starting extraction...")
            
            # Extract files
            self._extract_zip(zip_path)
            
            # Apply update
            self._apply_update()
            
            return {
                "status": "success",
                "message": "Update downloaded and applied successfully",
                "temp_dir": self.temp_dir
            }
            
        except requests.exceptions.RequestException as e:
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
    
    def _extract_zip(self, zip_path: str):
        """Extract zip file to temporary directory"""
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
        
        print("✅ Update preparation completed, update will be applied to /Applications directory on restart")
    
    def cleanup(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"Temporary files cleaned up: {self.temp_dir}")


def download_and_apply_update(update_info: Dict[str, Any], target_directory: str, progress_callback=None) -> Dict[str, Any]:
    """
    Convenience function to download and apply updates
    
    Args:
        update_info: Update information dictionary returned by UpdateManager
        target_directory: Target installation directory
        progress_callback: Progress callback function
        
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
    
    downloader = UpdateDownloader(download_url, target_directory, progress_callback)
    
    try:
        result = downloader.download_update(latest_version)
        # Add downloader object to result for cleanup by caller when appropriate
        result["downloader"] = downloader
        return result
    except Exception as e:
        # Clean up immediately if an exception occurs
        downloader.cleanup()
        return {
            "status": "error",
            "message": f"Error occurred during download: {e}"
        }


if __name__ == "__main__":
    # Test code
    test_info = {
        "download_url": "https://github.com/pyquick/converter/releases/tag/v2.0.0",
        "latest_version": "2.0.0"
    }
    
    result = download_and_apply_update(test_info, "./test_update")
    print(f"Test result: {result}")