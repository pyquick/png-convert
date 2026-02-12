from PySide6.QtWidgets import QTreeView
from PySide6.QtCore import Qt, Signal
from UIkit import TreeView, FluentIcon


class DraggableTreeView(TreeView):
    """
    可复用 TreeView 组件
    - 内部拖动（排序 / 改父子）
    - 与数据模型完全解耦
    - 支持文件拖放到文件的检测
    """

    # Signal emitted when a file is dropped onto another file
    file_dropped_on_file = Signal(str, str)  # source_name, target_name

    def __init__(self, parent=None):
        super().__init__(parent)

        # 启动拖放
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Store dragged item info
        self._dragged_index = None

    def set_tree_model(self, model):
        """
        由外部传入 Model
        """
        self.setModel(model)
        self.expandAll()

    def startDrag(self, supportedActions):
        """Store the dragged index when drag starts"""
        indexes = self.selectedIndexes()
        if indexes:
            self._dragged_index = indexes[0]
        super().startDrag(supportedActions)

    def _restore_icons(self, parent_item=None):
        """Restore icons for all items after drag operation"""
        if not self.model():
            return

        if parent_item is None:
            parent_item = self.model().invisibleRootItem()

        row_count = parent_item.rowCount()
        for row in range(row_count):
            item = parent_item.child(row, 0)
            if item:
                # Get item data
                is_dir = item.data(Qt.ItemDataRole.UserRole + 3)
                item_type = item.data(Qt.ItemDataRole.UserRole + 2)
                name = item.text()

                # Restore icon based on item type
                if is_dir:
                    item.setIcon(FluentIcon.FOLDER.qicon())
                else:
                    # Restore file icon based on extension
                    item.setIcon(self._get_file_icon(name))

                # Recursively restore children
                if item.rowCount() > 0:
                    self._restore_icons(item)

    def _get_file_icon(self, name):
        """Get icon for file based on extension"""
        import os
        ext = os.path.splitext(name.lower())[1]

        # Image files
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico', '.icns', '.svg', '.heic', '.heif', '.avif', '.jxl']:
            return FluentIcon.PHOTO.qicon()
        # Video files
        if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']:
            return FluentIcon.VIDEO.qicon()
        # Audio files
        if ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']:
            return FluentIcon.MUSIC.qicon()
        # Archive files
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.lzma', '.cab', '.iso']:
            return FluentIcon.ZIP_FOLDER.qicon()
        # Code files
        if ext in ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.ts']:
            return FluentIcon.CODE.qicon()
        # Document files
        if ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt']:
            return FluentIcon.DOCUMENT.qicon()

        # Default
        return FluentIcon.DOCUMENT.qicon()

    def dropEvent(self, event):
        """Handle drop event with file-on-file detection"""
        if not self.model():
            super().dropEvent(event)
            return

        # Get the drop position
        pos = event.position().toPoint()
        index = self.indexAt(pos)

        if index.isValid() and self._dragged_index and self._dragged_index.isValid():
            # Get source and target items
            source_item = self.model().itemFromIndex(self._dragged_index)
            target_item = self.model().itemFromIndex(index)

            if source_item and target_item:
                # Get item data
                source_is_dir = source_item.data(Qt.ItemDataRole.UserRole + 3)
                target_is_dir = target_item.data(Qt.ItemDataRole.UserRole + 3)
                source_name = source_item.text()
                target_name = target_item.text()

                # Check if both are files (not directories) and different items
                if (source_is_dir is not True and target_is_dir is not True and
                    source_item is not target_item):
                    # File dropped on file - emit signal and don't perform default drop
                    self.file_dropped_on_file.emit(source_name, target_name)
                    event.acceptProposedAction()
                    self._dragged_index = None
                    return

        # Perform default drop behavior for other cases
        self._dragged_index = None
        super().dropEvent(event)

        # Restore icons after drop
        self._restore_icons()
        self.expandAll()
