#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QWidget,
 QFileDialog
)
from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor
from PySide6.QtCore import Qt, QSize, Signal
from UIkit import *


class DropZoneWidget(QFrame):
    """Custom widget for drag and drop file/folder selection with support for all image formats"""
    filesDropped = Signal(list)  # Signal for multiple files dropped
    folderDropped = Signal(str)  # Signal for folder dropped
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setFixedHeight(100)   # 设置固定高度防止缩小
        self.setMinimumWidth(200)  # 设置最小宽度
        self.is_dark_mode = False  # Track current theme mode
        
        # Define supported image formats
        self.supported_formats = {
            # Common formats
            '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.ico', '.icns',
            # Web formats
            '.webp', '.svg', 
            # High efficiency formats
            '.heic', '.heif', '.avif', '.jxl',
            # Other formats
            '.pdf', '.eps', '.dds', '.exr'
        }
        
        # 设置初始状态变量
        self.is_dark_mode = False  # 初始化为浅色主题
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置内边距防止内容紧贴边框
        
        self.icon_label = QLabel("📁")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 24px;")
        
        self.text_label = QLabel("Drag files or folders here\n(Supports: PNG, JPG, JPEG, BMP, GIF, TIFF, ICO, ICNS, WebP, SVG, HEIC, HEIF, AVIF, JXL, PDF, EPS, DDS, EXR)")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("color: #666; font-size: 12px;")
        self.text_label.setWordWrap(True)
        
        # 应用初始浅色主题样式（在组件创建之后）
        self._apply_light_theme_style()
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        
        self.drag_over = False
        
        # Click to browse
        self.mousePressEvent = self.browse_files
        
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
            "Select Image Files",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.ico *.webp);;All Files (*)"
        )
        if file_paths:
            self.filesDropped.emit(file_paths)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Check if any of the dragged items are supported formats
            has_supported_files = False
            total_files = 0
            supported_files = 0
            has_folders = False
            
            for url in event.mimeData().urls():
                if hasattr(url, 'toLocalFile'):
                    path = url.toLocalFile()
                else:
                    path = url.path() if hasattr(url, 'path') else ""
                
                if path and os.path.isfile(path):
                    total_files += 1
                    if self._is_supported_image_file(path):
                        supported_files += 1
                elif path and os.path.isdir(path):
                    total_files += 1
                    has_folders = True  # Folders count as one item
            
            # Accept if there are supported image files or folders
            if supported_files > 0 or has_folders:
                self._set_drag_over_style(True)
                event.acceptProposedAction()
                self._update_text_label(total_files, supported_files, True)
            else:
                # Show rejection style
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
        folders = []
        rejected_files = []
        
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                folders.append(path)
            elif os.path.isfile(path):
                if self._is_supported_image_file(path):
                    files.append(path)
                else:
                    rejected_files.append(path)
                    
        # Emit signals for valid items
        if folders:
            # For now, emit first folder (can be extended for multiple folders)
            self.folderDropped.emit(folders[0])
            
        if files:
            self.filesDropped.emit(files)
            
        # Show result message
        if rejected_files:
            self._show_rejected_files_message(rejected_files)
        
    def _is_supported_image_file(self, file_path):
        """Check if the file has a supported image format extension"""
        if not file_path:
            return False
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.supported_formats
        
    def _set_drag_over_style(self, has_supported=True):
        """Set style for drag over state"""
        # Ensure fixed size is maintained during style changes
        current_width = self.width()
        
        if has_supported:
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
            self.drag_over = True
        else:
            if self.is_dark_mode:
                self.setStyleSheet("""
                    QFrame {
                        border: 2px solid #007acc;
                        border-radius: 10px;
                        background-color: #1e3a5f;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QFrame {
                        border: 2px solid #007acc;
                        border-radius: 10px;
                        background-color: #e6f3ff;
                    }
                """)
        
        # Restore fixed size after style change
        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)
            
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
            if supported_files > 0:
                if total_files == supported_files:
                    self.text_label.setText(f"Release to add {supported_files} image file(s)\n(Supported formats: {len(self.supported_formats)} types)")
                else:
                    self.text_label.setText(f"Release to add {supported_files} image file(s)\n({total_files - supported_files} unsupported file(s) will be ignored)")
            else:
                # Check if we're dealing with folders
                # If total_files is 1 and supported_files is 0, it's likely a folder
                if total_files == 1:
                    self.text_label.setText("Release to process folder\n(Folder will be scanned for image files)")
                else:
                    self.text_label.setText("Release to process folders\n(Folders will be scanned for image files)")
        else:
            self.text_label.setText("Drag image files or folders here")
            
    def _show_rejected_files_message(self, rejected_files):
        """Show message about rejected files"""
        if rejected_files:
            rejected_names = [os.path.basename(f) for f in rejected_files[:3]]  # Show first 3
            if len(rejected_files) > 3:
                rejected_names.append(f"and {len(rejected_files) - 3} more...")
            
            # You can add a tooltip or status message here
            print(f"Rejected {len(rejected_files)} unsupported file(s): {', '.join(rejected_names)}")


class DirectoryDropLineEdit(LineEdit):
    """支持文件夹拖拽的输出路径输入框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Drag folder here or click Browse...")
        
    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # 检查是否包含文件夹
            has_folder = False
            for url in urls:
                if hasattr(url, 'toLocalFile'):
                    file_path = url.toLocalFile()
                    if file_path and os.path.isdir(file_path):
                        has_folder = True
                        break
                elif hasattr(url, 'path') and os.path.isdir(url.path()):
                    has_folder = True
                    break
            
            if has_folder:
                event.acceptProposedAction()
                self.setStyleSheet("""
                    LineEdit {
                        border: 2px solid #28a745;
                        border-radius: 4px;
                        background-color: #f0fff0;
                    }
                """)
                return
        event.ignore()
        
    def dragLeaveEvent(self, event):
        """处理拖拽离开事件"""
        self.setStyleSheet("")
        
    def dragMoveEvent(self, event):
        """处理拖拽移动事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # 检查是否包含文件夹
            has_folder = False
            for url in urls:
                if hasattr(url, 'toLocalFile'):
                    file_path = url.toLocalFile()
                    if file_path and os.path.isdir(file_path):
                        has_folder = True
                        break
                elif hasattr(url, 'path') and os.path.isdir(url.path()):
                    has_folder = True
                    break
            
            if has_folder:
                event.acceptProposedAction()
                return
        event.ignore()
        
    def dropEvent(self, event):
        """处理放置事件"""
        self.setStyleSheet("")
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if hasattr(url, 'toLocalFile'):
                    file_path = url.toLocalFile()
                    if file_path and os.path.isdir(file_path):
                        self.setText(file_path)
                        # 发射信号表示路径已设置
                        self.editingFinished.emit()
                        event.acceptProposedAction()
                        return
                elif hasattr(url, 'path') and os.path.isdir(url.path()):
                    file_path = url.path()
                    self.setText(file_path)
                    self.editingFinished.emit()
                    event.acceptProposedAction()
                    return
        event.ignore()


class PreviewTab(QWidget):
    """独立的预览标签页，支持单张和多张图片预览"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_previews = []  # 当前显示的预览图片
        self.setup_ui()
        
    def setup_ui(self):
        """设置预览标签页界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("Preview")
        title_font = QFont()
        title_font.setPointSize(title_label.font().pointSize() + 4)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignHCenter)
        
        # 信息标签
        self.info_label = QLabel("Drag image files to the tab above for preview")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.info_label, 0, Qt.AlignmentFlag.AlignHCenter)
        
        # 滚动区域用于显示多个预览
        scroll_area = ScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMinimumHeight(400)
        
        # 预览容器
        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_layout.setSpacing(20)
        
        scroll_area.setWidget(self.preview_container)
        layout.addWidget(scroll_area)
        
        
        
        
        
        
    def show_single_preview(self, file_path):
        """显示单张图片预览"""
        self.clear_previews()
        self._create_single_preview_widget(file_path)
        self._update_info_label(1, [file_path])
        
    def show_multiple_previews(self, file_paths):
        """显示多张图片预览"""
        self.clear_previews()
        
        # Filter out folders and only process files
        valid_files = []
        for file_path in file_paths:
            if os.path.isfile(file_path):
                valid_files.append(file_path)
                self._create_single_preview_widget(file_path)
            else:
                # Skip folders, they will be handled differently
                print(f"Skipping folder: {file_path}")
            
        self._update_info_label(len(valid_files), valid_files)
        
    def clear_previews(self):
        """清除所有预览"""
        # 清除现有的预览widget
        for i in reversed(range(self.preview_layout.count())):
            child = self.preview_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
                child.deleteLater()
        
        self.current_previews = []
        
    def _create_single_preview_widget(self, file_path):
        """为单张图片创建预览widget"""
        if not os.path.exists(file_path):
            return
        
        # Skip folders, they are not image files
        if os.path.isdir(file_path):
            print(f"Skipping folder preview: {file_path}")
            return
            
        # 创建单个预览的容器
        preview_widget = QWidget()
        preview_widget.setFixedSize(300, 320)  # 固定大小
        preview_widget.setStyleSheet("""
            QWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
            QWidget:hover {
                border-color: #007acc;
                background-color: #f8f9fa;
            }
        """)
        
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        preview_layout.setSpacing(10)
        
        # 图片显示区域
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setFixedSize(280, 220)
        image_label.setStyleSheet("border: 1px solid #eee; border-radius: 4px; background-color: #f5f5f5;")
        
        # 加载并显示图片
        if self._can_load_image(file_path):
            pixmap = None
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    # 缩放图片以适应显示区域
                    scaled_pixmap = pixmap.scaled(
                        270, 210, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    image_label.setPixmap(scaled_pixmap)
                else:
                    self._set_thumbnail_placeholder(image_label, file_path)
            except Exception as e:
                print(f"Error loading preview for {file_path}: {e}")
                self._set_thumbnail_placeholder(image_label, file_path)
        else:
            self._set_thumbnail_placeholder(image_label, file_path)
            
        preview_layout.addWidget(image_label, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 文件信息
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        # 文件名
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setStyleSheet("font-weight: bold; color: #333;")
        filename_label.setWordWrap(True)
        
        # 文件大小
        try:
            file_size = os.path.getsize(file_path)
            size_text = self._format_file_size(file_size)
        except:
            size_text = "Unknown size"
            
        size_label = QLabel(size_text)
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_label.setStyleSheet("color: #666; font-size: 11px;")
        
        info_layout.addWidget(filename_label)
        info_layout.addWidget(size_label)
        preview_layout.addWidget(info_widget)
        
        # 添加到容器
        self.preview_layout.addWidget(preview_widget, 0, Qt.AlignmentFlag.AlignCenter)
        self.current_previews.append((file_path, preview_widget))
        
    def _can_load_image(self, file_path):
        """检查是否能直接加载图片"""
        if not file_path:
            return False
            
        _, ext = os.path.splitext(file_path.lower())
        direct_load_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.ico', '.icns', '.webp'}
        
        return ext in direct_load_formats
        
    def _set_thumbnail_placeholder(self, label, file_path):
        """设置缩略图占位符"""
        _, ext = os.path.splitext(file_path.lower())
        
        # 格式图标映射
        format_icons = {
            '.svg': '🖼️',
            '.pdf': '📄',
            '.eps': '📄',
            '.heic': '📱',
            '.heif': '📱',
            '.avif': '🖼️',
            '.jxl': '🖼️',
            '.dds': '🎮',
            '.exr': '🎬'
        }
        
        icon = format_icons.get(ext, '📷')
        
        # 创建占位符
        placeholder_pixmap = QPixmap(270, 210)
        placeholder_pixmap.fill(QColor('#f5f5f5'))
        
        painter = QPainter(placeholder_pixmap)
        painter.setPen(QColor('#999'))
        painter.setFont(QFont('Arial', 48))
        
        # 绘制图标
        painter.drawText(placeholder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon)
        
        # 绘制格式信息
        painter.setFont(QFont('Arial', 12))
        painter.drawText(
            QRect(0, 170, 270, 40), 
            Qt.AlignmentFlag.AlignCenter, 
            f"{ext.upper()[1:]} Format"
        )
        
        painter.end()
        
        label.setPixmap(placeholder_pixmap)
        
        # 设置tooltip
        label.setToolTip(f"Preview not available - {ext.upper()[1:]} Format\nWill show converted result")
        
    def _format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
            
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
        
    def _update_info_label(self, count, file_paths):
        """更新信息标签"""
        if count == 0:
            self.info_label.setText("Drag image files to the tab above for preview")
            self.info_label.setStyleSheet("color: #666; font-style: italic;")
        elif count == 1:
            filename = os.path.basename(file_paths[0])
            self.info_label.setText(f"Previewing: {filename}")
            self.info_label.setStyleSheet("color: #007acc; font-weight: bold;")
        else:
            self.info_label.setText(f"Previewing {count} images")
            self.info_label.setStyleSheet("color: #28a745; font-weight: bold;")


class ThumbnailGridWidget(QWidget):
    """Custom widget for displaying thumbnail grid of batch files"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.thumbnails = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.scroll_area = ScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(200)
        
        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QVBoxLayout(self.thumbnail_container)
        
        self.scroll_area.setWidget(self.thumbnail_container)
        layout.addWidget(self.scroll_area)
        
        # Placeholder text
        placeholder_label = QLabel("No files selected")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: #999; font-style: italic;")
        self.thumbnail_layout.addWidget(placeholder_label)
        
    def add_thumbnails(self, file_paths):
        """Add thumbnails for the given file paths"""
        # Clear existing thumbnails
        self.clear_thumbnails()
        
        # Define supported image formats
        supported_formats = {'.png', '.jpg', '.jpeg', '.webp', '.ico', '.bmp', '.tiff', '.tif', '.gif', '.svg', '.psd'}
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    _, ext = os.path.splitext(file_path.lower())
                    
                    if ext in supported_formats:
                        thumbnail = self.create_thumbnail_widget(file_path, ext)
                        self.thumbnail_layout.addWidget(thumbnail)
                        self.thumbnails.append(thumbnail)
                    else:
                        # Create placeholder for unsupported formats
                        thumbnail = self.create_unsupported_thumbnail(file_path, ext)
                        self.thumbnail_layout.addWidget(thumbnail)
                        self.thumbnails.append(thumbnail)
            except Exception as e:
                print(f"Error creating thumbnail for {file_path}: {e}")
                
        # Remove placeholder if thumbnails were added
        if self.thumbnails:
            for i in range(self.thumbnail_layout.count()):
                item = self.thumbnail_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QLabel):
                    if item.widget().text() == "No files selected":
                        widget = item.widget()
                        self.thumbnail_layout.removeWidget(widget)
                        widget.deleteLater()
                        break
                        
    def create_thumbnail_widget(self, file_path, file_ext):
        """Create a thumbnail widget for a single file"""
        container = QWidget()
        container.setMaximumHeight(80)
        container.setStyleSheet("""
            QWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                margin: 2px;
                padding: 5px;
            }
            QWidget:hover {
                border-color: #007acc;
                background-color: #f5f5f5;
            }
        """)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Thumbnail image or icon
        thumbnail_label = QLabel()
        thumbnail_label.setFixedSize(60, 60)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Try to load image for supported formats
        if self._can_load_image(file_ext):
            pixmap = None
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, 
                                                 Qt.TransformationMode.SmoothTransformation)
                    thumbnail_label.setPixmap(scaled_pixmap)
                else:
                    self._set_thumbnail_placeholder(thumbnail_label, file_ext, "Load Error")
            except Exception as e:
                print(f"Error loading image {file_path}: {e}")
                self._set_thumbnail_placeholder(thumbnail_label, file_ext, "Error")
        else:
            self._set_thumbnail_placeholder(thumbnail_label, file_ext)
        
        # File info
        info_layout = QVBoxLayout()
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        
        # Get file size
        try:
            size_bytes = os.path.getsize(file_path)
            size_str = self.format_file_size(size_bytes)
        except:
            size_str = "Unknown size"
            
        size_label = QLabel(f"Size: {size_str}")
        size_label.setStyleSheet("color: #666; font-size: 10px;")
        
        info_layout.addWidget(filename_label)
        info_layout.addWidget(size_label)
        info_layout.addStretch()
        
        layout.addWidget(thumbnail_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        
        return container
    
    def create_unsupported_thumbnail(self, file_path, file_ext):
        """Create a thumbnail widget for unsupported file formats"""
        container = QWidget()
        container.setMaximumHeight(80)
        container.setStyleSheet("""
            QWidget {
                border: 1px dashed #ccc;
                border-radius: 5px;
                margin: 2px;
                padding: 5px;
                background-color: #f9f9f9;
            }
            QWidget:hover {
                border-color: #999;
                background-color: #f0f0f0;
            }
        """)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Icon for unsupported format
        icon_label = QLabel()
        icon_label.setFixedSize(60, 60)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_thumbnail_placeholder(icon_label, file_ext, show_format=True)
        
        # File info
        info_layout = QVBoxLayout()
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #666;")
        
        # Get file size
        try:
            size_bytes = os.path.getsize(file_path)
            size_str = self.format_file_size(size_bytes)
        except:
            size_str = "Unknown size"
            
        size_label = QLabel(f"Size: {size_str}")
        size_label.setStyleSheet("color: #999; font-size: 10px;")
        
        info_layout.addWidget(filename_label)
        info_layout.addWidget(size_label)
        info_layout.addStretch()
        
        layout.addWidget(icon_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        
        return container
    
    def _can_load_image(self, file_ext):
        """Check if the file extension can be loaded as an image by Qt"""
        # Qt supports most common formats, but some require plugins
        loadable_formats = {'.png', '.jpg', '.jpeg', '.webp', '.ico', '.bmp', '.tif', '.tiff', '.gif'}
        return file_ext.lower() in loadable_formats
    
    def _set_thumbnail_placeholder(self, label, file_ext, error_text=None, show_format=False):
        """Set placeholder text and style for thumbnail label"""
        if error_text:
            # Error state
            label.setText(error_text)
            label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: #ffe6e6;
                    color: #dc3545;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
        elif show_format:
            # Show format information for unsupported but recognized formats
            format_name = file_ext.upper()[1:] if file_ext.startswith('.') else file_ext.upper()
            icon_map = {
                'SVG': '🎨',
                'PSD': '🎨',
                'BMP': '🖼️',
                'TIFF': '🖼️',
                'TIF': '🖼️',
                'GIF': '🖼️',
                'PNG': '🖼️',
                'JPG': '🖼️',
                'JPEG': '🖼️',
                'WEBP': '🖼️',
                'ICO': '🖼️'
            }
            icon = icon_map.get(format_name, '📄')
            label.setText(f"{icon}\n{format_name}")
            label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: #f5f5f5;
                    color: #666;
                    font-size: 8px;
                    font-weight: bold;
                    text-align: center;
                }
            """)
        else:
            # Generic file icon
            label.setText("📄")
            label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: #f5f5f5;
                    color: #666;
                    font-size: 24px;
                }
            """)
        
    def clear_thumbnails(self):
        """Clear all thumbnails"""
        # Remove all thumbnail widgets
        for thumbnail in self.thumbnails:
            if thumbnail and thumbnail.parent():
                thumbnail.setParent(None)
                thumbnail.deleteLater()
        
        self.thumbnails.clear()
        
        # Add placeholder back
        placeholder_label = QLabel("No files selected")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: #999; font-style: italic;")
        self.thumbnail_layout.addWidget(placeholder_label)
        
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
