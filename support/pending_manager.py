"""
Pending File Manager Module

This module provides a clean separation between data model and view logic
for managing pending files in the archive tool.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path


@dataclass
class PendingFile:
    """Represents a pending file to be added to archive"""
    path: str  # Absolute path to the file on disk
    target: str = ""  # Target path in archive (e.g., "folder/file.txt")
    deleted: bool = False  # Marked for deletion
    
    @property
    def name(self) -> str:
        """Get file name from path"""
        return os.path.basename(self.path)
    
    @property
    def size(self) -> int:
        """Get file size"""
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0
    
    @property
    def is_dir(self) -> bool:
        """Check if path is a directory"""
        return os.path.isdir(self.path)
    
    @property
    def target_folder(self) -> str:
        """Get target folder path (empty string if at root)"""
        if not self.target:
            return ""
        parts = self.target.strip('/').split('/')
        if len(parts) > 1:
            return '/'.join(parts[:-1])
        return ""
    
    @property
    def target_name(self) -> str:
        """Get target file name"""
        if not self.target:
            return self.name
        parts = self.target.strip('/').split('/')
        return parts[-1] if parts else self.name
    
    def get_full_target_path(self) -> str:
        """Get full target path including folder"""
        if self.target:
            return self.target
        return self.name


@dataclass
class FolderNode:
    """Represents a folder in the tree structure"""
    name: str
    path: str  # Full path (e.g., "folder/subfolder")
    is_existing: bool = False  # True if from existing archive
    children: List['FolderNode'] = field(default_factory=list)
    files: List[PendingFile] = field(default_factory=list)
    
    def find_or_create_child(self, name: str, is_existing: bool = False) -> 'FolderNode':
        """Find existing child folder or create new one"""
        for child in self.children:
            if child.name == name:
                return child
        
        # Create new folder
        new_path = f"{self.path}/{name}" if self.path else name
        new_folder = FolderNode(name=name, path=new_path, is_existing=is_existing)
        self.children.append(new_folder)
        return new_folder
    
    def get_all_files_recursive(self) -> List[PendingFile]:
        """Get all files in this folder and subfolders"""
        result = list(self.files)
        for child in self.children:
            result.extend(child.get_all_files_recursive())
        return result
    
    def remove_empty_folders(self) -> bool:
        """Remove empty folder nodes, return True if this folder is empty"""
        # Recursively clean children
        self.children = [c for c in self.children if not c.remove_empty_folders()]
        
        # Check if this folder should be removed
        # Keep if it has files or non-empty children
        return len(self.files) == 0 and len(self.children) == 0 and not self.is_existing


class PendingFileManager:
    """
    Manages pending files with clean separation from view logic.
    
    Responsibilities:
    - Store pending file data
    - Track deleted files
    - Build folder structure
    - Provide data for view updates
    """
    
    def __init__(self):
        self._files: List[PendingFile] = []
        self._deleted_targets: Set[str] = set()
    
    def add_file(self, file_path: str, target: str = "") -> PendingFile:
        """Add a new pending file"""
        file_obj = PendingFile(path=file_path, target=target)
        self._files.append(file_obj)
        return file_obj
    
    def add_files(self, file_paths: List[str], target: str = "") -> List[PendingFile]:
        """Add multiple pending files"""
        result = []
        for path in file_paths:
            if os.path.exists(path):
                result.append(self.add_file(path, target))
        return result
    
    def mark_deleted(self, target_path: str) -> bool:
        """
        Mark a file or folder as deleted.
        target_path can be:
        - "filename" - file at root
        - "folder/filename" - file in folder
        - "folder/" - entire folder
        """
        target_path = target_path.strip('/')
        
        # Mark all matching files as deleted
        found = False
        for file in self._files:
            if self._matches_target(file, target_path):
                file.deleted = True
                self._deleted_targets.add(file.get_full_target_path())
                found = True
        
        return found
    
    def _matches_target(self, file: PendingFile, target_path: str) -> bool:
        """Check if file matches the target path for deletion"""
        file_target = file.get_full_target_path()
        
        # Direct match
        if file_target == target_path or file_target == target_path.lstrip('/'):
            return True
        
        # Check if file is inside a deleted folder
        if target_path.endswith('/'):
            folder_path = target_path.rstrip('/')
            if file_target.startswith(folder_path + '/'):
                return True
        
        # Check basename match for root-level files
        if '/' not in target_path and file.name == target_path:
            return True
        
        return False
    
    def get_active_files(self) -> List[PendingFile]:
        """Get all non-deleted files"""
        return [f for f in self._files if not f.deleted]
    
    def get_deleted_files(self) -> List[PendingFile]:
        """Get all deleted files"""
        return [f for f in self._files if f.deleted]
    
    def clear(self):
        """Clear all pending files"""
        self._files.clear()
        self._deleted_targets.clear()
    
    def clear_deleted(self):
        """Permanently remove deleted files from the list"""
        self._files = [f for f in self._files if not f.deleted]
        self._deleted_targets.clear()
    
    def update_file_target(self, file_path: str, new_target: str) -> bool:
        """Update target path for a file"""
        for file in self._files:
            if file.path == file_path and not file.deleted:
                file.target = new_target
                return True
        return False

    def update_file_target_by_basename(self, basename: str, new_target: str) -> bool:
        """Update target path for a file by its basename"""
        found = False
        for file in self._files:
            if file.name == basename and not file.deleted:
                file.target = new_target
                found = True
        return found
    
    def build_folder_structure(self, existing_folders: List[str] = None) -> FolderNode:
        """
        Build complete folder structure from pending files.
        
        Args:
            existing_folders: List of existing folder paths from archive
        
        Returns:
            Root FolderNode containing all folders and files
        """
        root = FolderNode(name="", path="", is_existing=True)
        
        # Create existing folder structure
        if existing_folders:
            for folder_path in existing_folders:
                self._ensure_folder_exists(root, folder_path, is_existing=True)
        
        # Add pending files to structure
        for file in self.get_active_files():
            folder_path = file.target_folder
            
            # Find or create target folder
            if folder_path:
                folder = self._ensure_folder_exists(root, folder_path, is_existing=False)
            else:
                folder = root
            
            # Add file to folder
            folder.files.append(file)
        
        # Clean up empty non-existing folders
        root.remove_empty_folders()
        
        return root
    
    def _ensure_folder_exists(self, root: FolderNode, folder_path: str, is_existing: bool = False) -> FolderNode:
        """Ensure folder path exists in tree, creating if necessary"""
        parts = folder_path.strip('/').split('/')
        current = root
        
        current_path = ""
        for part in parts:
            if not part:
                continue
            
            current_path = f"{current_path}/{part}" if current_path else part
            
            # Check if child exists
            existing_child = None
            for child in current.children:
                if child.name == part:
                    existing_child = child
                    break
            
            if existing_child:
                current = existing_child
                # Mark as existing if it is
                if is_existing:
                    existing_child.is_existing = True
            else:
                # Create new folder
                new_folder = FolderNode(name=part, path=current_path, is_existing=is_existing)
                current.children.append(new_folder)
                current = new_folder
        
        return current
    
    def get_all_targets(self) -> List[str]:
        """Get all target paths for active files"""
        return [f.get_full_target_path() for f in self.get_active_files()]
    
    def is_empty(self) -> bool:
        """Check if there are no active pending files"""
        return len(self.get_active_files()) == 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about pending files"""
        active = self.get_active_files()
        return {
            'total': len(self._files),
            'active': len(active),
            'deleted': len(self.get_deleted_files()),
            'total_size': sum(f.size for f in active)
        }
