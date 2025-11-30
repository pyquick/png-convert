import os
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QFileDialog
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QPixmap


class BatchDropZoneWidget(QFrame):
    """Custom widget for drag and drop archive file selection"""
    files_dropped = Signal(list)  # Signal for multiple archive files dropped
    
    def __init__(self, placeholder_text="Drag archive files here or click to browse", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)  # 增加到100确保足够空间
        self.setFixedHeight(100)   # 设置固定高度防止缩小
        self.setMinimumWidth(200)  # 设置最小宽度
        self.is_dark_mode = False  # Track current theme mode
        
        # Define supported archive formats
        self.supported_formats = {
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.cab', '.iso', '.arj', '.ace', '.lzh', '.lha'
        }
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置内边距防止内容紧贴边框
        
        self.icon_label = QLabel("📁")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 20px;")
        
        self.text_label = QLabel(placeholder_text)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("color: #666; font-size: 12px;")
        self.text_label.setWordWrap(True)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        
        self.drag_over = False
        
        # Click to browse
        self.mousePressEvent = self.browse_files
        
        # Apply initial light theme style after all widgets are created
        self._apply_light_theme_style()
        
    def sizeHint(self):
        """Return fixed size hint to prevent resizing"""
        return super().sizeHint()
        
    def minimumSizeHint(self):
        """Return minimum size hint to prevent shrinking"""
        return QSize(200, 100)
        
    def set_theme(self, is_dark_mode):
        """Update the theme of the drag and drop area"""
        self.is_dark_mode = is_dark_mode
        if self.is_dark_mode:
            self._apply_dark_theme_style()
        else:
            self._apply_light_theme_style()
            
    def _apply_light_theme_style(self):
        """Apply light theme styles"""
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f9f9f9;
            }
            QFrame:hover {
                border-color: #007acc;
                background-color: #f0f8ff;
            }
            QFrame:drop {
                border-color: #28a745;
                background-color: #f0fff0;
            }
        """)
        self.text_label.setStyleSheet("color: #666; font-size: 12px;")
        
    def _apply_dark_theme_style(self):
        """Apply dark theme styles"""
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #555;
                border-radius: 10px;
                background-color: #2d2d2d;
            }
            QFrame:hover {
                border-color: #007acc;
                background-color: #1e3a5f;
            }
            QFrame:drop {
                border-color: #28a745;
                background-color: #1a2f1a;
            }
        """)
        self.text_label.setStyleSheet("color: #aaa; font-size: 12px;")
        
    def browse_files(self, event):
        """Open file browser when clicked"""
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            "Select Archive Files",
            "",
            "Archive Files (*.zip *.rar *.7z *.tar *.gz *.bz2 *.xz *.cab *.iso *.arj *.ace *.lzh *.lha);;All Files (*)"
        )
        if file_paths:
            self.files_dropped.emit(file_paths)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Check if any of the dragged items are supported archive formats
            has_supported_files = False
            total_files = 0
            supported_files = 0
            
            for url in event.mimeData().urls():
                if hasattr(url, 'toLocalFile'):
                    path = url.toLocalFile()
                else:
                    path = url.path() if hasattr(url, 'path') else ""
                
                if path and os.path.isfile(path):
                    total_files += 1
                    if self._is_supported_archive_file(path):
                        supported_files += 1
            
            # Accept if there are supported archive files
            if supported_files > 0:
                self._set_drag_over_style(True)
                event.acceptProposedAction()
                self._update_text_label(total_files, supported_files, True)
            else:
                self._set_reject_style()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        self._reset_style()
        
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            self._set_drag_over_style(True)
            event.acceptProposedAction()
        else:
            event.ignore()
        
    def dropEvent(self, event):
        self._reset_style()
        
        files = []
        
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and self._is_supported_archive_file(path):
                files.append(path)
                    
        # Emit signal for valid archive files
        if files:
            self.files_dropped.emit(files)
            
    def _is_supported_archive_file(self, file_path):
        """Check if the file has a supported archive format extension"""
        if not file_path:
            return False
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.supported_formats
        
    def _set_drag_over_style(self, has_supported=True):
        """Set style for drag over state"""
        # Ensure fixed size is maintained during style changes
        current_width = self.width()
        current_height = self.height()
        
        if self.is_dark_mode:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #28a745;
                    border-radius: 10px;
                    background-color: #1a2f1a;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #28a745;
                    border-radius: 10px;
                    background-color: #f0fff0;
                }
            """)
        
        # Restore fixed size after style change
        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)
            
        self.drag_over = True
            
    def _set_reject_style(self):
        """Set style for rejected drag items"""
        # Ensure fixed size is maintained during style changes
        current_width = self.width()
        
        if self.is_dark_mode:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #dc3545;
                    border-radius: 10px;
                    background-color: #2a1a1a;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #dc3545;
                    border-radius: 10px;
                    background-color: #fff5f5;
                }
            """)
        
        # Restore fixed size after style change
        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)
        
    def _reset_style(self):
        """Reset to default style"""
        # Ensure fixed size is maintained during style changes
        current_width = self.width()
        
        if self.is_dark_mode:
            self._apply_dark_theme_style()
        else:
            self._apply_light_theme_style()
        
        # Restore fixed size after style change
        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)
            
        self.drag_over = False
        
    def _update_text_label(self, total_files, supported_files, has_supported):
        """Update the text label during drag operations"""
        if has_supported:
            if total_files == supported_files:
                self.text_label.setText(f"Release to add {supported_files} archive file(s)")
            else:
                self.text_label.setText(f"Release to add {supported_files} archive file(s)\n({total_files - supported_files} unsupported file(s) will be ignored)")
