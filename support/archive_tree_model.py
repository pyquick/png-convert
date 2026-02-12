"""
Archive Tree Model Module

A clean tree model implementation for archive contents with support for
both existing archive files and pending new files.
"""

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QBrush
from typing import List, Optional, Dict, Any
import os

from support.pending_manager import PendingFileManager, FolderNode, PendingFile


class ArchiveTreeModel(QStandardItemModel):
    """
    Tree model for archive contents.
    
    Features:
    - Separate storage for existing and pending items
    - Automatic folder structure management
    - Clean refresh mechanism
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Name", "Size", "Type", "Path"])
        
        # Reference to pending file manager
        self._pending_manager: Optional[PendingFileManager] = None
        
        # Store existing items separately
        self._existing_data: List[Dict[str, Any]] = []
    
    def set_pending_manager(self, manager: PendingFileManager):
        """Set the pending file manager"""
        self._pending_manager = manager
    
    def set_existing_contents(self, contents: List[Dict[str, Any]]):
        """Store existing archive contents"""
        self._existing_data = contents

    def add_existing_items(self, contents: List[Dict[str, Any]]):
        """Add existing archive contents to tree (public method)"""
        self._existing_data = contents
        root = self.invisibleRootItem()
        self._add_existing_items(root)

    def refresh(self):
        """
        Refresh the entire tree view.
        This is the main entry point for updating the view.
        """
        self.blockSignals(True)
        try:
            self.clear()
            self.setHorizontalHeaderLabels(["Name", "Size", "Type", "Path"])
            
            root = self.invisibleRootItem()
            
            # Add existing items
            self._add_existing_items(root)
            
            # Add pending items
            if self._pending_manager:
                self._add_pending_items(root)
        finally:
            self.blockSignals(False)
            self.layoutChanged.emit()
    
    def _add_existing_items(self, root: QStandardItem):
        """Add existing archive contents to tree"""
        if not self._existing_data:
            return
        
        # Build folder structure
        folder_nodes: Dict[str, QStandardItem] = {"": root}
        
        for item_data in self._existing_data:
            if not isinstance(item_data, dict) or "name" not in item_data:
                continue
            
            name = item_data["name"]
            size = item_data.get("size", 0)
            is_dir = item_data.get("is_dir", False)
            
            path_parts = name.split("/")
            
            if is_dir:
                # Handle folder paths that may end with '/'
                clean_name = name.rstrip('/')
                path_parts = clean_name.split("/")
                parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                current_name = path_parts[-1] if path_parts else name
                
                parent_node = folder_nodes.get(parent_path, root)
                row_items = self._create_row(
                    name=current_name,
                    size="<DIR>",
                    item_type="existing",
                    path=clean_name,
                    is_dir=True
                )
                parent_node.appendRow(row_items)
                
                folder_nodes[clean_name] = row_items[0]
            else:
                parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                current_name = path_parts[-1] if path_parts else name
                
                parent_node = folder_nodes.get(parent_path, root)
                row_items = self._create_row(
                    name=current_name,
                    size=self._format_size(size),
                    item_type="existing",
                    path=name,
                    is_dir=False
                )
                parent_node.appendRow(row_items)
    
    def _add_pending_items(self, root: QStandardItem):
        """Add pending files to tree using folder structure from manager"""
        if not self._pending_manager or self._pending_manager.is_empty():
            return
        
        # Get existing folder paths
        existing_folders = self._extract_folder_paths()
        
        # Build folder structure
        folder_structure = self._pending_manager.build_folder_structure(existing_folders)
        
        # Add to tree
        self._add_folder_node(root, folder_structure)
    
    def _extract_folder_paths(self) -> List[str]:
        """Extract folder paths from existing data"""
        folders = []
        for item in self._existing_data:
            if isinstance(item, dict) and item.get("is_dir", False):
                name = item.get("name", "")
                if name:
                    folders.append(name.rstrip("/"))
        return folders
    
    def _add_folder_node(self, parent: QStandardItem, folder: FolderNode):
        """Recursively add folder and its contents to tree"""
        # If this is the root folder, add directly to parent
        if folder.path == "":
            current_parent = parent
        else:
            # Create folder item
            row_items = self._create_row(
                name=folder.name,
                size="<DIR>",
                item_type="pending",
                path=f"/{folder.path}" if folder.path else "/",
                is_dir=True
            )
            parent.appendRow(row_items)
            current_parent = row_items[0]
        
        # Add files in this folder
        for file in folder.files:
            row_items = self._create_row(
                name=file.target_name,
                size=self._format_size(file.size),
                item_type="pending",
                path=f"/{file.get_full_target_path()}" if file.get_full_target_path() else "/",
                is_dir=False
            )
            current_parent.appendRow(row_items)
        
        # Recursively add subfolders
        for child in folder.children:
            self._add_folder_node(current_parent, child)
    
    def _create_row(self, name: str, size: str, item_type: str, path: str, is_dir: bool) -> List[QStandardItem]:
        """Create a row of items for the tree"""
        # Name column
        name_item = QStandardItem(name)
        name_item.setData(path, Qt.ItemDataRole.UserRole + 1)
        name_item.setData(item_type, Qt.ItemDataRole.UserRole + 2)
        name_item.setData(is_dir, Qt.ItemDataRole.UserRole + 3)
        
        # Size column
        size_item = QStandardItem(size)
        
        # Type column
        if is_dir:
            type_text = "Folder"
        elif item_type == "existing":
            type_text = "File"
        else:
            type_text = "New File"
        type_item = QStandardItem(type_text)
        
        # Path column
        path_item = QStandardItem(path)
        
        # Apply green color for pending items
        if item_type == "pending":
            green_brush = QBrush(QColor(40, 167, 69))
            name_item.setForeground(green_brush)
            size_item.setForeground(green_brush)
            type_item.setForeground(green_brush)
            path_item.setForeground(green_brush)
        
        return [name_item, size_item, type_item, path_item]
    
    def _format_size(self, size: int) -> str:
        """Format file size for display"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
    
    def get_item_info(self, index: QModelIndex) -> Optional[Dict[str, Any]]:
        """Get item information at index"""
        if not index.isValid():
            return None
        
        item = self.itemFromIndex(index)
        if not item:
            return None
        
        return {
            'name': item.text(),
            'path': item.data(Qt.ItemDataRole.UserRole + 1),
            'type': item.data(Qt.ItemDataRole.UserRole + 2),
            'is_dir': item.data(Qt.ItemDataRole.UserRole + 3)
        }
    
    def find_item_by_path(self, path: str, parent: Optional[QStandardItem] = None) -> Optional[QStandardItem]:
        """Find item by its path"""
        if parent is None:
            parent = self.invisibleRootItem()
        
        for row in range(parent.rowCount()):
            item = parent.child(row, 0)
            if not item:
                continue
            
            item_path = item.data(Qt.ItemDataRole.UserRole + 1)
            if item_path == path:
                return item
            
            # Search in children
            if item.rowCount() > 0:
                result = self.find_item_by_path(path, item)
                if result:
                    return result
        
        return None

    def add_pending_items_from_manager(self, root_node: FolderNode):
        """Add pending items from FolderNode structure"""
        root = self.invisibleRootItem()
        self._add_folder_node_recursive(root, root_node)
    
    def _add_folder_node_recursive(self, parent: QStandardItem, folder: FolderNode):
        """Recursively add folder and its contents"""
        # If this is the root folder, add directly to parent
        if folder.path == "":
            current_parent = parent
        else:
            # Create folder item
            row_items = self._create_row(
                name=folder.name,
                size="<DIR>",
                item_type="pending",
                path=f"/{folder.path}" if folder.path else "/",
                is_dir=True
            )
            parent.appendRow(row_items)
            current_parent = row_items[0]
        
        # Add files in this folder
        for file in folder.files:
            row_items = self._create_row(
                name=file.target_name,
                size=self._format_size(file.size),
                item_type="pending",
                path=f"/{file.get_full_target_path()}" if file.get_full_target_path() else "/",
                is_dir=False
            )
            current_parent.appendRow(row_items)
        
        # Recursively add subfolders
        for child in folder.children:
            self._add_folder_node_recursive(current_parent, child)
