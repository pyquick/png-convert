# -*- coding: utf-8 -*-
import requests
import re
import locale
from typing import Optional
from PySide6.QtCore import QSettings

class UpdateManager:
    def __init__(self, current_version: str):
        self.current_version = self._parse_version(current_version)

    def _parse_version(self, version_str: str) -> tuple:
        # Handles versions like 2.1.0A11 and pre-release like 2.1.0A11RC1, 2.1.0A11A1, 2.1.0A11D1, 2.1.0A11RC1
        parts = version_str.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid version string: {version_str}")

        major = int(parts[0])
        minor = int(parts[1])
        
        patch_part = parts[2]
        # Support Alpha(A), Deepdev(D), Beta(B), RC, Stable formats
        match = re.match(r'^(\d+)([a-zA-Z]*)(\d*)$', patch_part)
        
        if not match:
            raise ValueError(f"Invalid patch format in version string: {patch_part}")

        num_str, tag, pre_num_str = match.groups()
        patch = int(num_str)
        
        if tag:
            pre_release_tag = tag.upper()  # Convert to uppercase for uniform handling
            pre_release_num = int(pre_num_str) if pre_num_str else 0
            
            # Verify if tag is a supported type
            supported_tags = ['A', 'D', 'B', 'RC']
            if pre_release_tag not in supported_tags:
                # If unsupported tag, treat as regular pre-release version
                pre_release_tag = pre_release_tag.lower()
            
            return (major, minor, patch, pre_release_tag, pre_release_num)
        else:
            # For stable releases, use empty string
            return (major, minor, patch, '', 0)

    def check_for_updates(self, include_prerelease: bool, prerelease_type: Optional[str] = None) -> dict:
        try:
            from con import CON
            repo_owner = "pyquick"
            repo_name = "converter"
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
            headers = CON.headers.copy()
            
            # Read PAT settings
            settings = QSettings("pyquick", "converter")
            encrypted_pat = settings.value("general/github_pat", "", type=str)
            
            # If PAT exists, add to headers
            if encrypted_pat:
                try:
                    import os, sys
                    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from utils.security import decrypt_pat
                    pat = decrypt_pat(encrypted_pat)
                    if pat:
                        headers["Authorization"] = f"token {pat}"
                except Exception:
                    pass
            
            response = requests.get(url, timeout=10, headers=headers)
            response.encoding = 'utf-8'
            response.raise_for_status()
            all_releases = response.json()

            latest_suitable_release = None
            latest_suitable_version = (0, 0, 0, '', 0)

            for release in all_releases:
                is_prerelease = release.get("prerelease", False)
                tag_name = release.get("tag_name", "0.0.0").lstrip('vV')

                if not tag_name:
                    continue
                
                if is_prerelease and not include_prerelease:
                    continue
                
                # If pre-release type is specified, filter accordingly
                if include_prerelease and prerelease_type:
                    # Parse release version tag
                    try:
                        release_version_info = self._parse_version(tag_name)
                        _, _, _, release_tag, _ = release_version_info
                        
                        # Build mapping from pre-release type name to tag letter
                        prerelease_type_map = {
                            'beta': 'B',
                            'alpha': 'A', 
                            'deepdev': 'D',
                            'rc': 'RC'
                        }
                        
                        # Convert user input pre-release type to corresponding tag letter
                        expected_tag = prerelease_type_map.get(prerelease_type.lower(), prerelease_type.upper())
                        
                        # Case-insensitive comparison to avoid case mismatch issues
                        if release_tag.upper() != expected_tag.upper():
                            continue
                    except ValueError:
                        continue
                
                try:
                    release_version = self._parse_version(tag_name)
                except ValueError:
                    continue

                # Compare versions using a custom comparison function
                if self._compare_versions(release_version, latest_suitable_version) > 0:
                    latest_suitable_version = release_version
                    latest_suitable_release = release
            
            if latest_suitable_release and self._compare_versions(latest_suitable_version, self.current_version) > 0:
                latest_version_str = latest_suitable_release.get("tag_name", "0.0.0").lstrip('vV')
                return {
                    "status": "update_available",
                    "message": f"New version available: {latest_version_str}!",
                    "download_url": latest_suitable_release.get('html_url', ''),
                    "latest_version": latest_version_str,
                    "release_body": latest_suitable_release.get('body', ''),
                    "version_info": latest_suitable_version  # Add version info for UI display
                }
            elif latest_suitable_release and self._compare_versions(latest_suitable_version, self.current_version) <= 0:
                return {
                    "status": "latest",
                    "message": f"You are running the latest version ({self._parse_version_to_str(self.current_version)}).",
                    "latest_version": self._parse_version_to_str(self.current_version)
                }
            else:
                return {
                    "status": "no_updates",
                    "message": "No suitable updates found.",
                    "latest_version": "N/A"
                }

        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"Update check failed: {e}"}
        except ValueError as e:
            return {"status": "error", "message": f"Version parsing failed: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    
    def _compare_versions(self, version1: tuple, version2: tuple) -> int:
        """Custom version comparison function with proper pre-release priority"""
        major1, minor1, patch1, tag1, pre_num1 = version1
        major2, minor2, patch2, tag2, pre_num2 = version2
        
        # Compare major version
        if major1 != major2:
            return 1 if major1 > major2 else -1
        
        # Compare minor version
        if minor1 != minor2:
            return 1 if minor1 > minor2 else -1
        
        # Compare patch version
        if patch1 != patch2:
            return 1 if patch1 > patch2 else -1
        
        # Compare tags - stable releases (empty tag) are greater than pre-releases
        if tag1 == '' and tag2 != '':
            return 1
        elif tag1 != '' and tag2 == '':
            return -1
        elif tag1 != tag2:
            # Pre-release version priority: Stable > RC > Beta > Deepdev > Alpha
            priority = {'RC': 4, 'B': 3, 'D': 2, 'A': 1}
            priority1 = priority.get(tag1, 0)
            priority2 = priority.get(tag2, 0)
            
            if priority1 != priority2:
                return 1 if priority1 > priority2 else -1
            else:
                # If same priority, compare alphabetically
                return 1 if tag1 > tag2 else -1
        
        # Compare pre-release numbers
        if pre_num1 != pre_num2:
            return 1 if pre_num1 > pre_num2 else -1
        
        return 0

    def _parse_version_to_str(self, version_tuple: tuple) -> str:
        major, minor, patch, tag, pre_num = version_tuple
        if tag == '':
            return f"{major}.{minor}.{patch}"
        else:
            # Convert tag back to original format
            tag_map = {'A': 'A', 'D': 'D', 'B': 'B', 'RC': 'RC'}
            display_tag = tag_map.get(tag, tag)
            
            # If pre_num is 0, it might have been something like 'beta' without a number
            if pre_num == 0:
                return f"{major}.{minor}.{patch}{display_tag}"
            return f"{major}.{minor}.{patch}{display_tag}{pre_num}"
    
    def get_version_type_name(self, version_info: tuple | str) -> str:
        """Get friendly name for version type"""
        # Support passing tuple or single tag
        if isinstance(version_info, tuple):
            _, _, _, tag, _ = version_info
        else:
            tag = version_info
        
        type_names = {
            '': 'Stable',
            'RC': 'Release Candidate',
            'B': 'Beta',
            'D': 'Deepdev',
            'A': 'Alpha'
        }
        return type_names.get(tag, f"Unknown ({tag})")
    
    def get_github_pat(self) -> str:
        """Get GitHub PAT
        
        Returns:
            str: Decrypted PAT, returns empty string if not set
        """
        try:
            settings = QSettings("pyquick", "converter")
            encrypted_pat = settings.value("general/github_pat", "", type=str)
            if encrypted_pat:
                import os, sys
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from utils.security import decrypt_pat
                return decrypt_pat(encrypted_pat)
        except Exception as e:
            print(f"Failed to get PAT: {e}")
        return ""
