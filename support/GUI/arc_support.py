#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Archive Manager GUI Support Module

This module provides GUI components and worker classes for archive management.
"""

import os
import sys
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from UIkit import *

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from support.archive_manager import create_archive, extract_archive, add_to_archive, list_archive_contents, batch_extract_archives
from support.password_detector import PasswordDetector


# ==================== Worker Classes ====================

class CreateZipWorker(QObject):
    """Worker for creating archives"""
    finished = Signal()
    progress_updated = Signal(str, int)
    conversion_error = Signal(str)
    canceled = Signal()

    def __init__(self, output_path, sources, archive_format, password=None):
        super().__init__()
        self.output_path = output_path
        self.sources = sources
        self.archive_format = archive_format
        self.password = password
        self.is_stopped = False

    def stop(self):
        """Stop the archive creation process"""
        self.is_stopped = True
        self.progress_updated.emit("Canceling archive creation...", 0)

    def run(self):
        try:
            if not self.output_path:
                raise ValueError("Output path is empty")
            if not self.sources:
                raise ValueError("No source files specified")
            if not self.archive_format:
                raise ValueError("Archive format is not specified")

            for source in self.sources:
                if not os.path.exists(source):
                    raise ValueError(f"Source file does not exist: {source}")

            def progress_callback(message, percentage):
                if self.is_stopped:
                    raise RuntimeError("Archive creation canceled by user")
                self.progress_updated.emit(message, percentage)

            create_archive(self.output_path, self.sources, self.archive_format, progress_callback, self.password)
            if not self.is_stopped:
                self.finished.emit()
            else:
                self.canceled.emit()
        except RuntimeError as e:
            if "canceled" in str(e).lower():
                self.canceled.emit()
            else:
                self.conversion_error.emit(str(e))
        except ValueError as e:
            self.conversion_error.emit(f"Input error: {str(e)}")
        except FileNotFoundError as e:
            self.conversion_error.emit(f"File not found: {str(e)}")
        except PermissionError as e:
            self.conversion_error.emit(f"Permission denied: {str(e)}")
        except OSError as e:
            self.conversion_error.emit(f"System error: {str(e)}")
        except NotImplementedError as e:
            self.conversion_error.emit(str(e))
        except Exception as e:
            if self.is_stopped:
                self.canceled.emit()
            else:
                import traceback
                error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
                self.conversion_error.emit(error_msg)


class ExtractZipWorker(QObject):
    """Worker for extracting archives"""
    finished = Signal()
    progress_updated = Signal(str, int)
    conversion_error = Signal(str)
    password_required = Signal(str)
    canceled = Signal()

    def __init__(self, zip_path, dest_path, password=None):
        super().__init__()
        self.archive_path = zip_path
        self.extract_to = dest_path
        self.password = password
        self.is_stopped = False

    def stop(self):
        """Stop the archive extraction process"""
        self.is_stopped = True
        self.progress_updated.emit("Canceling archive extraction...", 0)

    def run(self):
        try:
            def progress_callback(message, percentage):
                if self.is_stopped:
                    raise RuntimeError("Archive extraction canceled by user")
                self.progress_updated.emit(message, percentage)

            extract_archive(self.archive_path, self.extract_to, progress_callback, self.password)
            if not self.is_stopped:
                self.finished.emit()
            else:
                self.canceled.emit()
        except RuntimeError as e:
            if "canceled" in str(e).lower():
                self.canceled.emit()
            else:
                if "password" in str(e).lower() or "encrypted" in str(e).lower():
                    self.password_required.emit(str(e))
                else:
                    self.conversion_error.emit(str(e))
        except Exception as e:
            if self.is_stopped:
                self.canceled.emit()
            else:
                self.conversion_error.emit(str(e))


class AddToZipWorker(QObject):
    """Worker for adding files to archives"""
    finished = Signal()
    progress_updated = Signal(str, int)
    conversion_error = Signal(str)
    canceled = Signal()

    def __init__(self, zip_path, file_paths):
        super().__init__()
        self.archive_path = zip_path
        self.files_to_add = file_paths if isinstance(file_paths, list) else [file_paths]
        self.is_stopped = False

    def stop(self):
        """Stop the add to archive process"""
        self.is_stopped = True
        self.progress_updated.emit("Canceling add to archive...", 0)

    def run(self):
        try:
            total_files = len(self.files_to_add)
            for i, file_path in enumerate(self.files_to_add):
                if self.is_stopped:
                    raise RuntimeError("Add to archive canceled by user")

                self.progress_updated.emit(f"Adding file {i+1}/{total_files}: {os.path.basename(file_path)}", (i/total_files)*100)
                add_to_archive(self.archive_path, file_path, None)

            if not self.is_stopped:
                self.progress_updated.emit(f"Added {total_files} files to archive", 100)
                self.finished.emit()
            else:
                self.canceled.emit()
        except RuntimeError as e:
            if "canceled" in str(e).lower():
                self.canceled.emit()
            else:
                self.conversion_error.emit(str(e))
        except NotImplementedError as e:
            self.conversion_error.emit(str(e))
        except Exception as e:
            if self.is_stopped:
                self.canceled.emit()
            else:
                self.conversion_error.emit(str(e))


class ListZipContentsWorker(QObject):
    """Worker for listing archive contents"""
    finished = Signal(list)
    conversion_error = Signal(str)
    password_required = Signal(str)
    canceled = Signal()

    def __init__(self, zip_path, password=None):
        super().__init__()
        self.archive_path = zip_path
        self.password = password
        self.result = None
        self.is_stopped = False

    def stop(self):
        """Stop the list contents process"""
        self.is_stopped = True

    def run(self):
        try:
            if self.is_stopped:
                self.canceled.emit()
                return

            contents = list_archive_contents(self.archive_path, password=self.password)

            if not self.is_stopped:
                self.result = contents
                self.finished.emit(contents)
            else:
                self.canceled.emit()
        except RuntimeError as e:
            if not self.is_stopped:
                if "password" in str(e).lower() or "encrypted" in str(e).lower():
                    self.password_required.emit(str(e))
                else:
                    self.conversion_error.emit(str(e))
            else:
                self.canceled.emit()
        except Exception as e:
            if not self.is_stopped:
                self.conversion_error.emit(str(e))
            else:
                self.canceled.emit()


class BatchExtractWorker(QObject):
    """Worker for batch archive extraction"""
    finished = Signal(int, int, list, list)  # success_count, failed_count, success_files, failed_files
    progress_updated = Signal(int, int, str, int, int)  # processed_count, total_count, current_file, success_count, failed_count
    conversion_error = Signal(str)
    individual_progress = Signal(str, str, int)  # archive_name, message, percentage
    status_updated = Signal(str)
    canceled = Signal()

    def __init__(self, archive_paths, dest_folder, create_subfolders=True, overwrite_files=False, parent_gui=None):
        super().__init__()
        self.archive_paths = archive_paths
        self.dest_folder = dest_folder
        self.create_subfolders = create_subfolders
        self.overwrite_files = overwrite_files
        self.is_stopped = False
        self.parent_gui = parent_gui

        self.success_count = 0
        self.failed_count = 0
        self.success_files = []
        self.failed_files = []

    def stop(self):
        """Stop the batch extraction process"""
        self.is_stopped = True
        self.status_updated.emit("Stopping batch extraction...")

    def run(self):
        try:
            if not self.archive_paths:
                raise ValueError("No archive files to extract")

            if not self.dest_folder:
                raise ValueError("Destination folder is not specified")

            if not os.path.exists(self.dest_folder):
                try:
                    os.makedirs(self.dest_folder, exist_ok=True)
                except Exception as e:
                    raise ValueError(f"Failed to create destination folder: {str(e)}")

            password_detector = PasswordDetector()

            self.success_count = 0
            self.failed_count = 0
            self.success_files = []
            self.failed_files = []

            total_files = len(self.archive_paths)
            self.status_updated.emit(f"Starting batch extraction of {total_files} archive(s)...")

            def progress_callback(current, total, current_file=""):
                if self.is_stopped:
                    return

                if isinstance(current, str):
                    message = current
                    progress_percent = total
                    archive_name = os.path.basename(current_file) if current_file else ""
                    self.individual_progress.emit(archive_name, message, int(progress_percent))
                else:
                    current_val = int(current) if isinstance(current, (int, float)) else 0
                    total_val = int(total) if isinstance(total, (int, float)) else total_files

                    if isinstance(current, int) and 1 <= current <= total_files:
                        current_file_path = self.archive_paths[current - 1]
                    else:
                        current_file_path = str(current_file) if current_file else ""

                    overall_progress = (current_val / total_val * 100) if total_val > 0 else 0
                    self.progress_updated.emit(current_val, total_val, current_file_path, self.success_count, self.failed_count)

            def password_callback(archive_path, format_name, is_protected):
                if self.is_stopped:
                    return None
                if self.parent_gui and hasattr(self.parent_gui, 'request_password'):
                    try:
                        return self.parent_gui.request_password(archive_path, format_name, is_protected)
                    except Exception as e:
                        self.conversion_error.emit(f"Error requesting password: {str(e)}")
                        return None
                return None

            def error_callback(archive_path, error_message):
                self.failed_count += 1
                self.failed_files.append((archive_path, error_message))
                self.conversion_error.emit(f"Error processing {os.path.basename(archive_path)}: {error_message}")
                processed = self.success_count + self.failed_count
                self.progress_updated.emit(processed, total_files, archive_path, self.success_count, self.failed_count)

            options = {
                'create_subfolders': self.create_subfolders,
                'overwrite_existing': self.overwrite_files,
                'progress_callback': progress_callback if not self.is_stopped else None,
                'password_callback': password_callback if not self.is_stopped else None,
                'password_detector': password_detector,
                'error_callback': error_callback
            }

            if self.is_stopped:
                self.status_updated.emit("Batch extraction stopped by user")
                self.finished.emit(self.success_count, self.failed_count, self.success_files, self.failed_files)
                return

            result = batch_extract_archives(
                self.archive_paths,
                self.dest_folder,
                **options
            )

            if not self.is_stopped:
                self.success_count = result.get('success_count', self.success_count)
                self.failed_count = result.get('error_count', self.failed_count)

                self.status_updated.emit(f"Batch extraction completed: {self.success_count} successful, {self.failed_count} failed")
                self.finished.emit(self.success_count, self.failed_count, self.success_files, self.failed_files)
            else:
                self.status_updated.emit("Batch extraction stopped by user")
                self.canceled.emit()
                self.finished.emit(self.success_count, self.failed_count, self.success_files, self.failed_files)

        except ValueError as e:
            error_msg = f"Input error: {str(e)}"
            self.conversion_error.emit(error_msg)
            self.status_updated.emit(f"Batch extraction failed: {error_msg}")
            self.finished.emit(0, total_files if 'total_files' in locals() else 0, [], self.archive_paths)
        except RuntimeError as e:
            error_msg = str(e)
            self.conversion_error.emit(error_msg)
            self.status_updated.emit(f"Batch extraction failed: {error_msg}")
            self.finished.emit(0, total_files if 'total_files' in locals() else 0, [], self.archive_paths)
        except Exception as e:
            import traceback
            error_msg = f"Unexpected error during batch extraction: {str(e)}\n{traceback.format_exc()}"
            self.conversion_error.emit(error_msg)
            self.status_updated.emit(f"Batch extraction failed: {error_msg}")
            self.finished.emit(0, total_files if 'total_files' in locals() else 0, [], self.archive_paths)


# ==================== GUI Components ====================

class BatchDropZoneWidget(QFrame):
    """Custom widget for drag and drop archive file selection"""
    files_dropped = Signal(list)

    def __init__(self, placeholder_text="Drag archive files here or click to browse", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setFixedHeight(100)
        self.setMinimumWidth(200)
        self.is_dark_mode = False

        self.supported_formats = {
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.cab', '.iso', '.arj', '.ace', '.lzh', '.lha'
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

        self.text_label = QLabel(placeholder_text)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("color: #666; font-size: 12px;")
        self.text_label.setWordWrap(True)

        layout.addWidget(icon_container)
        layout.addWidget(self.text_label)

        self.drag_over = False
        self.mousePressEvent = self.browse_files
        self._apply_light_theme_style()

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
            "Select Archive Files",
            "",
            "Archive Files (*.zip *.rar *.7z *.tar *.gz *.bz2 *.xz *.cab *.iso *.arj *.ace *.lzh *.lha);;All Files (*)"
        )
        if file_paths:
            self.files_dropped.emit(file_paths)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
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

        if files:
            self.files_dropped.emit(files)

    def _is_supported_archive_file(self, file_path):
        if not file_path:
            return False
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.supported_formats

    def _set_drag_over_style(self, has_supported=True):
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

        self.setFixedHeight(100)
        if current_width > 0:
            self.setMinimumWidth(current_width)

        self.drag_over = True

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
            if total_files == supported_files:
                self.text_label.setText(f"Release to add {supported_files} archive file(s)")
            else:
                self.text_label.setText(f"Release to add {supported_files} archive file(s)\n({total_files - supported_files} unsupported file(s) will be ignored)")