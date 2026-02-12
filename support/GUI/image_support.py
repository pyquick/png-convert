#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Converter GUI Support Module

This module provides GUI components and worker classes for image conversion.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QWidget,
    QFileDialog
)
from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor
from PySide6.QtCore import Qt, QSize, Signal

# Import FluentIcon and IconWidget
from UIkit import FluentIcon, IconWidget

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Converter import FIF
from UIkit import *
from support import convert


# ==================== Worker Classes ====================

class ConversionWorker(QObject):
    """Worker for single image conversion"""
    finished = Signal()
    progress_updated = Signal(str, int)
    conversion_error = Signal(str)

    def __init__(self, input_path, output_path, output_format, min_size_param=None, max_size_param=None, quality_param=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.output_format = output_format
        self.quality = int(quality_param) if quality_param is not None else 85
        if output_format == "icns":
            self.min_size = int(min_size_param) if min_size_param is not None else 16
            self.max_size = int(max_size_param) if max_size_param is not None else None
        else:
            self.min_size = None
            self.max_size = None

    def run(self):
        try:
            if self.output_format == "icns":
                convert.convert_image(
                    self.input_path,
                    self.output_path,
                    self.output_format,
                    int(self.min_size) if self.min_size is not None else 16,
                    int(self.max_size) if self.max_size is not None else None,
                    quality=self.quality,
                    progress_callback=self._update_progress_callback
                )
            else:
                convert.convert_image(
                    input_path=self.input_path,
                    output_path=self.output_path,
                    output_format=self.output_format,
                    quality=self.quality,
                    progress_callback=self._update_progress_callback
                )
            self.finished.emit()
        except Exception as e:
            error_msg = f"Conversion error: {str(e)}"
            self.conversion_error.emit(error_msg)
            print(f"[ERROR] ConversionWorker: {error_msg}")

    def _update_progress_callback(self, *args):
        """Handle variable number of arguments from progress_callback"""
        if len(args) == 2:
            message, percentage = args
        elif len(args) == 3:
            if isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)):
                current, total, message = args
                percentage = int((current / total) * 100) if total > 0 else 0
            else:
                message, percentage, _ = args
        else:
            message = "Processing..." if args else "Unknown progress"
            percentage = 0
        self.progress_updated.emit(message, percentage)


class BatchConversionWorker(QObject):
    """Worker for batch image conversion"""
    finished = Signal()
    progress_updated = Signal(int, int, str, int)  # current_index, total_count, current_file, percentage
    file_processed = Signal(str, str, str, bool, str)  # filename, input_path, output_path, success, error_message
    batch_error = Signal(str)
    total_progress_updated = Signal(int)

    def __init__(self, input_paths, output_dir, output_format, min_size_param=None, max_size_param=None, quality_param=None,
                 preserve_folder_structure=False, prefix="", suffix="", auto_detect_max_size=False):
        super().__init__()
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.output_format = output_format
        self.quality = int(quality_param) if quality_param is not None else 85
        self.is_cancelled = False
        self.preserve_folder_structure = preserve_folder_structure
        self.prefix = prefix
        self.suffix = suffix
        self.auto_detect_max_size = auto_detect_max_size

        if output_format == "icns":
            self.min_size = int(min_size_param) if min_size_param is not None else 16
            self.max_size = int(max_size_param) if max_size_param is not None else None
        else:
            self.min_size = None
            self.max_size = None

    def cancel(self):
        """Cancel the batch conversion process"""
        self.is_cancelled = True

    def run(self):
        try:
            total_files = len(self.input_paths)
            if total_files == 0:
                self.finished.emit()
                return

            # Get common parent directory if preserving folder structure
            common_parent = None
            if self.preserve_folder_structure and self.input_paths:
                directories = [os.path.dirname(path) for path in self.input_paths]
                if directories:
                    common_parent = os.path.commonpath(directories)

            # Calculate optimal number of threads
            max_workers = min(16, os.cpu_count() * 2)
            processed_files = 0
            conversion_tasks = []

            # Prepare all conversion tasks
            for i, input_path in enumerate(self.input_paths):
                filename = os.path.basename(input_path)
                name_without_ext = os.path.splitext(filename)[0]
                output_filename = f"{self.prefix}{name_without_ext}{self.suffix}.{self.output_format.lower()}"

                if self.preserve_folder_structure and common_parent:
                    relative_dir = os.path.relpath(os.path.dirname(input_path), common_parent)
                    output_path = os.path.join(self.output_dir, relative_dir, output_filename)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                else:
                    converted_dir = os.path.join(self.output_dir, "converted")
                    os.makedirs(converted_dir, exist_ok=True)
                    output_path = os.path.join(converted_dir, output_filename)

                conversion_tasks.append({
                    'index': i,
                    'input_path': input_path,
                    'output_path': output_path,
                    'filename': filename,
                    'total_files': total_files
                })

            # Use ThreadPoolExecutor for concurrent conversion
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {}
                for task in conversion_tasks:
                    if self.is_cancelled:
                        error_msg = "Batch conversion was cancelled"
                        self.batch_error.emit(error_msg)
                        print(f"[ERROR] BatchConversionWorker: {error_msg}")
                        return

                    try:
                        future = executor.submit(self._convert_single_file, task)
                        future_to_task[future] = task
                    except Exception as e:
                        error_msg = f"Error submitting task for {task['filename']}: {str(e)}"
                        self.batch_error.emit(error_msg)
                        print(f"[ERROR] BatchConversionWorker: {error_msg}")

                # Process completed tasks
                for future in as_completed(future_to_task):
                    if self.is_cancelled:
                        error_msg = "Batch conversion was cancelled"
                        self.batch_error.emit(error_msg)
                        print(f"[ERROR] BatchConversionWorker: {error_msg}")
                        executor.shutdown(wait=False, cancel_futures=True)
                        return

                    task = future_to_task[future]
                    try:
                        success, message = future.result()
                        self.file_processed.emit(task['filename'], task['input_path'], task['output_path'], success, message if not success else "")
                    except Exception as e:
                        error_msg = f"Error processing {task['filename']}: {str(e)}"
                        self.file_processed.emit(task['filename'], task['input_path'], task['output_path'], False, error_msg)
                        print(f"[ERROR] BatchConversionWorker: {error_msg}")

                    processed_files += 1
                    overall_progress = int((processed_files / total_files) * 100)
                    self.total_progress_updated.emit(overall_progress)

            self.total_progress_updated.emit(100)
            self.finished.emit()

        except Exception as e:
            error_msg = f"Batch conversion error: {str(e)}"
            self.batch_error.emit(error_msg)
            print(f"[ERROR] BatchConversionWorker: {error_msg}")

    def _convert_single_file(self, task):
        """Convert a single file (thread-safe)"""
        if self.is_cancelled:
            raise Exception("Batch conversion was cancelled")

        self.progress_updated.emit(task['index']+1, task['total_files'], task['filename'], 0)

        def progress_callback(*args):
            if len(args) == 2:
                message, percentage = args
            elif len(args) == 3:
                if isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)):
                    current, total, message = args
                    percentage = int((current / total) * 100) if total > 0 else 0
                else:
                    message, percentage, _ = args
            else:
                message = "Processing..." if args else "Unknown progress"
                percentage = 0
            self.progress_updated.emit(task['index']+1, task['total_files'], task['filename'], percentage)

        if self.output_format == "icns":
            current_max_size = int(self.max_size) if self.max_size is not None else None
            if self.auto_detect_max_size:
                try:
                    width, height = convert.get_image_info(task['input_path'])
                    current_max_size = min(width, height)
                except Exception as e:
                    print(f"[WARNING] Failed to auto-detect max size for {task['filename']}: {str(e)}")
                    current_max_size = int(self.max_size) if self.max_size is not None else None

            success, message = convert.convert_image(
                task['input_path'],
                task['output_path'],
                self.output_format,
                int(self.min_size) if self.min_size is not None else 16,
                current_max_size,
                quality=self.quality,
                progress_callback=progress_callback
            )
        else:
            success, message = convert.convert_image(
                input_path=task['input_path'],
                output_path=task['output_path'],
                output_format=self.output_format,
                quality=self.quality,
                progress_callback=progress_callback
            )

        return success, message


# ==================== GUI Components ====================

class DropZoneWidget(QFrame):
    """Custom widget for drag and drop file/folder selection with support for all image formats"""
    filesDropped = Signal(list)  # Signal for multiple files dropped
    folderDropped = Signal(str)  # Signal for folder dropped

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setFixedHeight(100)
        self.setMinimumWidth(200)
        self.is_dark_mode = False

        self.supported_formats = {
            '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.ico', '.icns',
            '.webp', '.svg', '.heic', '.heif', '.avif', '.jxl', '.pdf', '.eps', '.dds', '.exr'
        }

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create a container for the icon to center it
        icon_container = QWidget()
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = IconWidget(FluentIcon.FOLDER)
        self.icon_label.setFixedSize(32, 32)
        icon_layout.addWidget(self.icon_label)

        self.text_label = QLabel("Drag files or folders here\n(Supports: PNG, JPG, JPEG, BMP, GIF, TIFF, ICO, ICNS, WebP, SVG, HEIC, HEIF, AVIF, JXL, PDF, EPS, DDS, EXR)")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("color: #666; font-size: 12px;")
        self.text_label.setWordWrap(True)

        self._apply_light_theme_style()

        layout.addWidget(icon_container)
        layout.addWidget(self.text_label)

        self.drag_over = False
        self.mousePressEvent = self.browse_files

    def sizeHint(self):
        return super().sizeHint()

    def minimumSizeHint(self):
        return QSize(200, 100)

    def set_theme(self, is_dark_mode):
        self.is_dark_mode = is_dark_mode
        if self.is_dark_mode:
            self._apply_dark_theme_style()
        else:
            self._apply_light_theme_style()

    def _apply_light_theme_style(self):
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
                    has_folders = True

            if supported_files > 0 or has_folders:
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

        if folders:
            self.folderDropped.emit(folders[0])
        if files:
            self.filesDropped.emit(files)
        if rejected_files:
            self._show_rejected_files_message(rejected_files)

    def _is_supported_image_file(self, file_path):
        if not file_path:
            return False
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.supported_formats

    def _set_drag_over_style(self, has_supported=True):
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

        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)

    def _set_reject_style(self):
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

        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)

    def _reset_style(self):
        current_width = self.width()

        if self.is_dark_mode:
            self._apply_dark_theme_style()
        else:
            self._apply_light_theme_style()

        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)

        self.drag_over = False

    def _update_text_label(self, total_files, supported_files, has_supported):
        if has_supported:
            if supported_files > 0:
                if total_files == supported_files:
                    self.text_label.setText(f"Release to add {supported_files} image file(s)\n(Supported formats: {len(self.supported_formats)} types)")
                else:
                    self.text_label.setText(f"Release to add {supported_files} image file(s)\n({total_files - supported_files} unsupported file(s) will be ignored)")
            else:
                if total_files == 1:
                    self.text_label.setText("Release to process folder\n(Folder will be scanned for image files)")
                else:
                    self.text_label.setText("Release to process folders\n(Folders will be scanned for image files)")
        else:
            self.text_label.setText("Drag image files or folders here")

    def _show_rejected_files_message(self, rejected_files):
        if rejected_files:
            rejected_names = [os.path.basename(f) for f in rejected_files[:3]]
            if len(rejected_files) > 3:
                rejected_names.append(f"and {len(rejected_files) - 3} more...")
            print(f"Rejected {len(rejected_files)} unsupported file(s): {', '.join(rejected_names)}")


class DirectoryDropLineEdit(LineEdit):
    """Support folder drag and drop for output path input"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Drag folder here or click Browse...")
        self._original_style = None
        self._is_drag_over = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
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
                # Save original style on first drag enter
                if not self._is_drag_over:
                    self._original_style = self.styleSheet()
                    self._is_drag_over = True
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
        # Restore original style
        if self._is_drag_over:
            self.setStyleSheet(self._original_style if self._original_style else "")
            self._is_drag_over = False

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
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
        # Restore original style before processing drop
        if self._is_drag_over:
            self.setStyleSheet(self._original_style if self._original_style else "")
            self._is_drag_over = False

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if hasattr(url, 'toLocalFile'):
                    file_path = url.toLocalFile()
                    if file_path and os.path.isdir(file_path):
                        self.setText(file_path)
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
    """Preview tab supporting single and multiple image previews"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_previews = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        title_label = QLabel("Preview")
        title_font = QFont()
        title_font.setPointSize(title_label.font().pointSize() + 4)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.info_label = QLabel("Drag image files to the tab above for preview")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.info_label, 0, Qt.AlignmentFlag.AlignHCenter)

        scroll_area = ScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMinimumHeight(400)

        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_layout.setSpacing(20)

        scroll_area.setWidget(self.preview_container)
        layout.addWidget(scroll_area)

    def show_single_preview(self, file_path):
        self.clear_previews()
        self._create_single_preview_widget(file_path)
        self._update_info_label(1, [file_path])

    def show_multiple_previews(self, file_paths):
        self.clear_previews()

        valid_files = []
        for file_path in file_paths:
            if os.path.isfile(file_path):
                valid_files.append(file_path)
                self._create_single_preview_widget(file_path)
            else:
                print(f"Skipping folder: {file_path}")

        self._update_info_label(len(valid_files), valid_files)

    def clear_previews(self):
        for i in reversed(range(self.preview_layout.count())):
            child = self.preview_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
                child.deleteLater()

        self.current_previews = []

    def _create_single_preview_widget(self, file_path):
        if not os.path.exists(file_path):
            return

        if os.path.isdir(file_path):
            print(f"Skipping folder preview: {file_path}")
            return

        preview_widget = QWidget()
        preview_widget.setFixedSize(300, 320)
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

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setFixedSize(280, 220)
        image_label.setStyleSheet("border: 1px solid #eee; border-radius: 4px; background-color: #f5f5f5;")

        if self._can_load_image(file_path):
            pixmap = None
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
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

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setStyleSheet("font-weight: bold; color: #333;")
        filename_label.setWordWrap(True)

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

        self.preview_layout.addWidget(preview_widget, 0, Qt.AlignmentFlag.AlignCenter)
        self.current_previews.append((file_path, preview_widget))

    def _can_load_image(self, file_path):
        if not file_path:
            return False

        _, ext = os.path.splitext(file_path.lower())
        direct_load_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.ico', '.icns', '.webp'}

        return ext in direct_load_formats

    def _set_thumbnail_placeholder(self, label, file_path):
        _, ext = os.path.splitext(file_path.lower())

        format_icons = {
            '.svg': '��️',
            '.pdf': '��',
            '.eps': '��',
            '.heic': '��',
            '.heif': '��',
            '.avif': '��️',
            '.jxl': '��️',
            '.dds': '��',
            '.exr': '��'
        }

        icon = format_icons.get(ext, '��')

        placeholder_pixmap = QPixmap(270, 210)
        placeholder_pixmap.fill(QColor('#f5f5f5'))

        painter = QPainter(placeholder_pixmap)
        painter.setPen(QColor('#999'))
        painter.setFont(QFont('Arial', 48))

        painter.drawText(placeholder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon)

        painter.setFont(QFont('Arial', 12))
        painter.drawText(
            QRect(0, 170, 270, 40),
            Qt.AlignmentFlag.AlignCenter,
            f"{ext.upper()[1:]} Format"
        )

        painter.end()

        label.setPixmap(placeholder_pixmap)
        label.setToolTip(f"Preview not available - {ext.upper()[1:]} Format\nWill show converted result")

    def _format_file_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"

    def _update_info_label(self, count, file_paths):
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
    """Thumbnail grid widget for batch files"""
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

        placeholder_label = QLabel("No files selected")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: #999; font-style: italic;")
        self.thumbnail_layout.addWidget(placeholder_label)

    def add_thumbnails(self, file_paths):
        self.clear_thumbnails()

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
                        thumbnail = self.create_unsupported_thumbnail(file_path, ext)
                        self.thumbnail_layout.addWidget(thumbnail)
                        self.thumbnails.append(thumbnail)
            except Exception as e:
                print(f"Error creating thumbnail for {file_path}: {e}")

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

        thumbnail_label = QLabel()
        thumbnail_label.setFixedSize(60, 60)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

        info_layout = QVBoxLayout()
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setStyleSheet("font-weight: bold; font-size: 12px;")

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

        icon_label = QLabel()
        icon_label.setFixedSize(60, 60)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_thumbnail_placeholder(icon_label, file_ext, show_format=True)

        info_layout = QVBoxLayout()
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #666;")

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
        loadable_formats = {'.png', '.jpg', '.jpeg', '.webp', '.ico', '.bmp', '.tif', '.tiff', '.gif'}
        return file_ext.lower() in loadable_formats

    def _set_thumbnail_placeholder(self, label, file_ext, error_text=None, show_format=False):
        if error_text:
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
            format_name = file_ext.upper()[1:] if file_ext.startswith('.') else file_ext.upper()
            icon_map = {
                'SVG': '��',
                'PSD': '��',
                'BMP': '��️',
                'TIFF': '��️',
                'TIF': '��️',
                'GIF': '��️',
                'PNG': '��️',
                'JPG': '��️',
                'JPEG': '��️',
                'WEBP': '��️',
                'ICO': '��️'
            }
            icon = icon_map.get(format_name, '��')
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
            label.setText("��")
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
        for thumbnail in self.thumbnails:
            if thumbnail and thumbnail.parent():
                thumbnail.setParent(None)
                thumbnail.deleteLater()

        self.thumbnails.clear()

        placeholder_label = QLabel("No files selected")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: #999; font-style: italic;")
        self.thumbnail_layout.addWidget(placeholder_label)

    def format_file_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"