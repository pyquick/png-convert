#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PNG to ICNS Converter with PySide6

This script provides a graphical interface for converting PNG images to ICNS format.
"""

import platform
import sys
import os
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSpinBox, QListWidget,
    QFileDialog, QMessageBox, QTabWidget, QGroupBox, QSizePolicy,
     QTreeWidgetItem, QFrame,QListWidgetItem
)
from PySide6.QtGui import QPixmap, QIcon, QFont, QImage, QPalette
from PySide6.QtCore import Qt, QSize, Signal, QObject, QThread
from PySide6.QtCore import QSettings
from darkdetect import isDark
import qfluentwidgets
from support.toggle import theme_manager
from qfluentwidgets import *
# Add the current directory to Python path to import convert module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from support import convert
from support.GUI.image_support import DropZoneWidget, DirectoryDropLineEdit, PreviewTab, ThumbnailGridWidget

from con import CON

class ConversionWorker(QObject):
    finished = Signal()
    progress_updated = Signal(str, int)
    conversion_error = Signal(str)

    def __init__(self, input_path, output_path, output_format, min_size_param=None, max_size_param=None, quality_param=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.output_format = output_format
        self.quality = int(quality_param) if quality_param is not None else 85
        self.qss=CON.qss
        if output_format == "icns":
            self.min_size = int(min_size_param) if min_size_param is not None else 16
            self.max_size = int(max_size_param) if max_size_param is not None else None # Keep None for convert.py
        else:
            self.min_size = None # Not relevant for non-icns
            self.max_size = None # Not relevant for non-icns
        

    def run(self):
        try:
            if self.output_format == "icns":
                # For icns format, use positional arguments with correct order
                convert.convert_image(
                    self.input_path,
                    self.output_path,
                    self.output_format,
                    int(self.min_size) if self.min_size is not None else 16, # Explicit conversion to int
                    int(self.max_size) if self.max_size is not None else None, # Explicit conversion to int
                    quality=self.quality,
                    progress_callback=self._update_progress_callback
                )
            else:
                # For non-icns formats, use keyword arguments for clarity and to avoid parameter order issues
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

    def _update_progress_callback(self, message, percentage):
        self.progress_updated.emit(message, percentage)


class BatchConversionWorker(QObject):
    finished = Signal()
    progress_updated = Signal(int, int, str, int)  # current_index, total_count, current_file, percentage
    file_processed = Signal(str, bool, str)  # filename, success, error_message
    batch_error = Signal(str)
    total_progress_updated = Signal(int)  # overall progress percentage

    def __init__(self, input_paths, output_dir, output_format, min_size_param=None, max_size_param=None, quality_param=None, 
                 preserve_folder_structure=False, prefix="", suffix=""):
        super().__init__()
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.output_format = output_format
        self.quality = int(quality_param) if quality_param is not None else 85
        self.is_cancelled = False
        self.preserve_folder_structure = preserve_folder_structure
        self.prefix = prefix
        self.suffix = suffix
        
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
                # Get all directories
                directories = [os.path.dirname(path) for path in self.input_paths]
                if directories:
                    # Find common parent directory
                    common_parent = os.path.commonpath(directories)
            
            # Calculate optimal number of threads (use CPU cores * 2 for I/O bound tasks)
            max_workers = min(16, os.cpu_count() * 2)
            
            # Track processed files and progress
            processed_files = 0
            
            # Create a list to hold conversion tasks
            conversion_tasks = []
            
            # Prepare all conversion tasks
            for i, input_path in enumerate(self.input_paths):
                filename = os.path.basename(input_path)
                name_without_ext = os.path.splitext(filename)[0]
                
                # Apply prefix and suffix
                output_filename = f"{self.prefix}{name_without_ext}{self.suffix}.{self.output_format.lower()}"
                
                # Determine output path based on folder structure option
                if self.preserve_folder_structure and common_parent:
                    # Get relative path from common parent
                    relative_dir = os.path.relpath(os.path.dirname(input_path), common_parent)
                    output_path = os.path.join(self.output_dir, relative_dir, output_filename)
                    # Create directories if they don't exist
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                else:
                    # Create "converted" subdirectory in the output directory
                    converted_dir = os.path.join(self.output_dir, "converted")
                    os.makedirs(converted_dir, exist_ok=True)
                    output_path = os.path.join(converted_dir, output_filename)
                
                # Add to conversion tasks
                conversion_tasks.append({
                    'index': i,
                    'input_path': input_path,
                    'output_path': output_path,
                    'filename': filename,
                    'total_files': total_files
                })
            
            # Use ThreadPoolExecutor for concurrent conversion
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
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
                        # Continue with other tasks instead of failing completely
                
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
                        # Signal that this file was processed
                        self.file_processed.emit(task['filename'], success, message if not success else "")
                    except Exception as e:
                        # Signal that this file failed
                        error_msg = f"Error processing {task['filename']}: {str(e)}"
                        self.file_processed.emit(task['filename'], False, error_msg)
                        print(f"[ERROR] BatchConversionWorker: {error_msg}")
                    
                    # Update processed count and overall progress
                    processed_files += 1
                    overall_progress = int((processed_files / total_files) * 100)
                    self.total_progress_updated.emit(overall_progress)
            
            # Final progress update
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
        
        # Update file-specific progress
        self.progress_updated.emit(task['index']+1, task['total_files'], task['filename'], 0)
        
        # Create a progress callback for this specific file
        def progress_callback(message, percentage):
            # Update the file-specific progress
            self.progress_updated.emit(task['index']+1, task['total_files'], task['filename'], percentage)
        
        # Perform the conversion
        if self.output_format == "icns":
            success, message = convert.convert_image(
                task['input_path'],
                task['output_path'],
                self.output_format,
                int(self.min_size) if self.min_size is not None else 16,
                int(self.max_size) if self.max_size is not None else None,
                quality=self.quality,
                progress_callback=progress_callback
            )
        else:
            # For non-icns formats, use keyword arguments for clarity and to avoid parameter order issues
            success, message = convert.convert_image(
                input_path=task['input_path'],
                output_path=task['output_path'],
                output_format=self.output_format,
                quality=self.quality,
                progress_callback=progress_callback
            )
        
        return success, message


class ICNSConverterGUI(QMainWindow):

    def _load_qss_file(self, filename):
        """Load QSS content from external file"""
        qss_path = os.path.join(os.path.dirname(__file__), 'qss', filename)
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: QSS file not found: {qss_path}")
            return ""
        except Exception as e:
            print(f"Error loading QSS file {qss_path}: {e}")
            return ""

    @property
    def LIGHT_QSS(self):
        """Load light theme QSS from external file"""
        return self._load_qss_file('converter_light.qss')

    @property
    def DARK_QSS(self):
        """Load dark theme QSS from external file"""
        return self._load_qss_file('converter_dark.qss')

    def __init__(self, initial_dark_mode=False):
        super().__init__()
        self.setWindowTitle("Image Converter")
        self.setGeometry(200, 200, 1000, 1000)
        self.setMinimumSize(1200, 400)
        #self.layout().setSizeConstraint(QLayout.SetFixedSize)
        self.init_variables()
        self.setup_ui()
        self.center_window()

        # Apply initial theme
        self._apply_theme(initial_dark_mode)
        
        # Connect to theme change signal for real-time theme switching
        self.theme_changed = False
        self.listener=SystemThemeListener(self)
        self.listener.start()
        qconfig.themeChanged.connect(self._onThemeChanged)
        # Load settings AFTER UI setup to ensure they override defaults
        self.load_settings()
        
    def _onThemeChanged(self):
        """Theme change handling"""
        
        setTheme(Theme.AUTO)
        
        
    def closeEvent(self, e):
        # Stop listener thread
        self.listener.terminate()
        self.listener.deleteLater()
        super().closeEvent(e)

    def _apply_theme(self, is_dark_mode):
        if is_dark_mode:
            self.setStyleSheet(self.DARK_QSS)
        else:
            self.setStyleSheet(self.LIGHT_QSS)
            
        # Update DropZoneWidget theme if it exists
        if hasattr(self, 'drop_zone') and self.drop_zone:
            self.drop_zone.set_theme(is_dark_mode)
            
        # Update success view theme if it exists and is visible
        if hasattr(self, 'success_widget') and self.success_widget and self.success_widget.isVisible():
            self._apply_success_theme()
            
    def load_settings(self):
        """Load settings from QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Load image converter settings
        self.min_size = settings.value("image_converter/min_size", 16, type=int)
        self.max_size = settings.value("image_converter/max_size", 1024, type=int)
        self.output_format = settings.value("image_converter/output_format", "icns", type=str)
        
        # Load image processing options
        self.keep_aspect_ratio = settings.value("image_converter/keep_aspect_ratio", True, type=bool)
        self.auto_crop = settings.value("image_converter/auto_crop", False, type=bool)
        self.quality = settings.value("image_converter/quality", 85, type=int)
        
        # Load advanced options
        self.icns_method = settings.value("image_converter/icns_method", "iconutil (Recommended)")
        self.overwrite_confirm = settings.value("image_converter/overwrite_confirm", True, type=bool)
        
        # Load interface behavior settings
        auto_preview_val = settings.value("image_converter/auto_preview", True, type=bool)
        remember_path_val = settings.value("image_converter/remember_path", True, type=bool)
        completion_notify_val = settings.value("image_converter/completion_notify", True, type=bool)
        
        self.auto_preview = bool(auto_preview_val) if auto_preview_val is not None else True
        self.remember_path = bool(remember_path_val) if remember_path_val is not None else True
        self.completion_notify = bool(completion_notify_val) if completion_notify_val is not None else True
        
        # Load remembered paths if setting is enabled
        if self.remember_path:
            input_dir_val = settings.value("image_converter/last_input_dir", "", type=str)
            output_dir_val = settings.value("image_converter/last_output_dir", "", type=str)
            self.last_input_dir = str(input_dir_val) if input_dir_val is not None else ""
            self.last_output_dir = str(output_dir_val) if output_dir_val is not None else ""
        
        # Update UI with loaded settings
        if hasattr(self, 'min_spin') and isinstance(self.min_size, (int, str)):
            self.min_spin.setValue(int(self.min_size))
        if hasattr(self, 'max_spin') and isinstance(self.max_size, (int, str)):
            self.max_spin.setValue(int(self.max_size))
        if hasattr(self, 'format_combo') and self.output_format:
            self.format_combo.setCurrentText(str(self.output_format))
        if hasattr(self, 'keep_aspect_check'):
            self.keep_aspect_check.setChecked(bool(self.keep_aspect_ratio))
        if hasattr(self, 'auto_crop_check'):
            self.auto_crop_check.setChecked(bool(self.auto_crop))
        if hasattr(self, 'quality_slider') and isinstance(self.quality, (int, str)):
            self.quality_slider.setValue(int(self.quality))
            self.quality_label.setText(str(self.quality))
        if hasattr(self, 'icns_method_combo') and self.icns_method:
            self.icns_method_combo.setCurrentText(str(self.icns_method))
        if hasattr(self, 'overwrite_confirm_check'):
            self.overwrite_confirm_check.setChecked(bool(self.overwrite_confirm))
        
        print(f"Settings loaded: min_size={self.min_size}, max_size={self.max_size}, output_format={self.output_format}")
        
    def save_settings(self):
        """Save settings to QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Save image converter settings
        settings.setValue("image_converter/min_size", self.min_size)
        settings.setValue("image_converter/max_size", self.max_size)
        settings.setValue("image_converter/output_format", self.output_format)
        
        # Save image processing options
        settings.setValue("image_converter/keep_aspect_ratio", self.keep_aspect_ratio)
        settings.setValue("image_converter/auto_crop", self.auto_crop)
        settings.setValue("image_converter/quality", self.quality)
        
        # Save advanced options
        settings.setValue("image_converter/icns_method", self.icns_method)
        settings.setValue("image_converter/overwrite_confirm", self.overwrite_confirm)
        
        # Save interface behavior settings
        settings.setValue("image_converter/auto_preview", self.auto_preview)
        settings.setValue("image_converter/remember_path", self.remember_path)
        settings.setValue("image_converter/completion_notify", self.completion_notify)
        
        # Save remembered paths if setting is enabled
        if self.remember_path:
            if hasattr(self, 'last_input_dir'):
                settings.setValue("image_converter/last_input_dir", self.last_input_dir)
            if hasattr(self, 'last_output_dir'):
                settings.setValue("image_converter/last_output_dir", self.last_output_dir)
        
        print(f"Settings saved: min_size={self.min_size}, max_size={self.max_size}, output_format={self.output_format}")
        
    def init_variables(self, reset_all=False):
        """初始化或重置所有变量
        
        Args:
            reset_all (bool): If True, reset all variables including interface behavior settings.
                             If False, only reset basic variables (preserves loaded settings).
        """
        self.input_path = ""
        self.output_path = ""
        self.min_size = 16
        self.max_size = 1024
        self.converting = False
        self.current_view = "main"
        self.output_format = "icns"  # Default output format
        
        # Image processing options
        self.keep_aspect_ratio = True
        self.auto_crop = False
        self.quality = 85
        
        # Advanced options
        self.icns_method = "iconutil (Recommended)"
        self.overwrite_confirm = True
        
        # Batch conversion variables
        self.batch_files = []
        self.batch_converting = False
        self.batch_worker = None
        self.batch_thread = None
        self.batch_current_index = 0
        self.batch_current_file = ""
        self.batch_success_count = 0
        self.batch_failed_count = 0
        self.batch_canceled = False
        self.batch_results = []  # Store conversion results
        
        # Only reset interface behavior settings if explicitly requested
        if reset_all or not hasattr(self, 'auto_preview'):
            # Interface behavior settings - prioritize reading from launcher settings
            self._load_launcher_settings_for_interface()
        
        # History tracking
        if not hasattr(self, 'conversion_history'):
            self.conversion_history = []
    
    def _load_launcher_settings_for_interface(self):
        """Load interface behavior settings from launcher settings (QSettings) with fallback to defaults"""
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("MyCompany", "ConverterApp")
            
            # Read launcher settings for interface behavior
            # These settings might be managed by the launcher/settings dialog
            
            # Priority 1: Try to read from image_converter specific settings
            auto_preview_val = settings.value("image_converter/auto_preview", None)
            remember_path_val = settings.value("image_converter/remember_path", None)
            completion_notify_val = settings.value("image_converter/completion_notify", None)
            
            # Priority 2: If image_converter settings don't exist, check for global launcher settings
            if auto_preview_val is None:
                # Check if there's a global auto_preview setting from launcher
                auto_preview_val = settings.value("auto_preview", True)
            
            if remember_path_val is None:
                # Check if there's a global remember_path setting from launcher
                remember_path_val = settings.value("remember_path", True)
                
            if completion_notify_val is None:
                # Check if there's a global completion_notify setting from launcher
                completion_notify_val = settings.value("completion_notify", True)
            
            # Apply settings with proper type conversion
            self.auto_preview = bool(auto_preview_val) if auto_preview_val is not None else True
            self.remember_path = bool(remember_path_val) if remember_path_val is not None else True
            self.completion_notify = bool(completion_notify_val) if completion_notify_val is not None else True
            
            # Also check for other launcher-managed settings that might affect interface
            # Theme setting (for potential interface adjustments)
            theme_setting = settings.value("theme", 0, type=int)
            if hasattr(self, '_launcher_theme_setting'):
                self._launcher_theme_setting = theme_setting
            
            # Debug setting (for potential debug interface elements)
            debug_enabled = settings.value("debug_enabled", False, type=bool)
            if hasattr(self, '_launcher_debug_enabled'):
                self._launcher_debug_enabled = debug_enabled
                
            print(f"Loaded launcher settings: auto_preview={self.auto_preview}, remember_path={self.remember_path}, completion_notify={self.completion_notify}")
            
        except Exception as e:
            # Fallback to hardcoded defaults if settings loading fails
            print(f"Warning: Failed to load launcher settings, using defaults: {e}")
            self.auto_preview = True
            self.remember_path = True
            self.completion_notify = True
        
    def setup_ui(self):
        """Setup initial UI"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)

        self.create_widgets()
        self.create_success_view()
        self.create_batch_success_view()
        self.create_history_tab()
        self.show_main_view()
        
    def create_widgets(self):
        """Create the main conversion interface"""
        # Title
        title_label = QLabel("Image Format Converter")
        title_font = QFont()
        title_font.setPointSize(title_label.font().pointSize() + 8)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # Create tab widget for main content and history
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Connect tab change signal for animation effect
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Main converter tab
        self.converter_tab = QWidget()
        self.tab_widget.addTab(self.converter_tab, "Signle Converter")
        
        # Setup main converter content
        self.setup_converter_tab()
        
        # Batch converter tab
        self.batch_converter_tab = QWidget()
        self.tab_widget.addTab(self.batch_converter_tab, "Batch Converter")
        
        # Setup batch converter content
        self.setup_batch_converter_tab()
        
        # Preview tab - for image preview functionality
        self.preview_tab = PreviewTab()
        self.tab_widget.addTab(self.preview_tab, "Preview")
        
        # Connect drop signals to update preview tab
        self._connect_preview_signals()
        
    def _connect_preview_signals(self):
        """Connect signals to update preview tab"""
        # Connect drop zone signals to preview tab
        self.drop_zone.filesDropped.connect(self.preview_tab.show_multiple_previews)
        self.drop_zone.folderDropped.connect(self.preview_tab.show_multiple_previews)
        
        # Connect input text change to preview tab
        self.input_text.textChanged.connect(self.on_input_text_changed)
        
    def on_input_text_changed(self):
        """Handle input text change to update preview"""
        input_path = self.input_text.text().strip()
        if input_path and os.path.exists(input_path):
            # Single file change
            self.preview_tab.show_single_preview(input_path)
        else:
            # Clear preview if invalid path
            self.preview_tab.clear_previews()
        
    def setup_converter_tab(self):
        """Setup the main converter tab content"""
        converter_layout = QVBoxLayout(self.converter_tab)

        # Main content area: Left Panel (Input/Output) and Right Side (Options/Preview)
        main_content_h_layout = QHBoxLayout()
        main_content_h_layout.setSpacing(20) # Increased spacing between left and right sections
        converter_layout.addLayout(main_content_h_layout)

        # Left Panel: Merged Input/Output File Selection
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(15) # Spacing between input and output sections
        main_content_h_layout.addWidget(left_panel, 1) # Give left panel some stretch

        # Merged File Operations Group Box
        file_ops_group_box = QGroupBox("File Operations")
        file_ops_group_layout = QVBoxLayout(file_ops_group_box)
        file_ops_group_layout.setContentsMargins(10, 25, 10, 10)
        file_ops_group_layout.setSpacing(10)
        left_layout.addWidget(file_ops_group_box)

        # Input File Selection (inside merged group box)
        input_layout = QHBoxLayout()
        input_label = QLabel("Input File:")
        self.input_text = LineEdit()
        # self.input_text.setReadOnly(True)  # 允许用户手动输入路径
        input_button = PushButton("Browse...")
        # Apply custom style to input button
        setCustomStyleSheet(input_button, CON.qss, CON.qss)
        setCustomStyleSheet(self.input_text, CON.qss_line, CON.qss_line)
        input_button.clicked.connect(self.on_browse_input)

        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_text, 1) # Give text field more stretch
        input_layout.addWidget(input_button)
        file_ops_group_layout.addLayout(input_layout)

        # Output File Selection (inside merged group box)
        output_layout = QHBoxLayout()
        output_label = QLabel("Output File:")
        self.output_text = LineEdit()
        # self.output_text.setReadOnly(True)  # 允许用户手动输入路径
        output_button = PushButton("Browse...")
        # Apply custom style to output button
        setCustomStyleSheet(output_button, CON.qss, CON.qss)
        setCustomStyleSheet(self.output_text, CON.qss_line, CON.qss_line)
        output_button.clicked.connect(self.on_browse_output)

        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_text, 1) # Give text field more stretch
        output_layout.addWidget(output_button)
        file_ops_group_layout.addLayout(output_layout)

        # Add stretch to left layout to push content to top
        left_layout.addStretch(1)

        # Right Side: Image Info, Conversion Options, Progress, Convert Button
        right_side_v_layout = QVBoxLayout()
        right_side_v_layout.setContentsMargins(15, 15, 15, 15) # Add margins to the right side overall
        right_side_v_layout.setSpacing(15) # Spacing between groups on the right side
        main_content_h_layout.addLayout(right_side_v_layout, 1) # Give right side some stretch

        # Image Info
        info_group_box = QGroupBox("Image Information")
        info_group_layout = QVBoxLayout(info_group_box)
        info_group_layout.setContentsMargins(10, 25, 10, 10)
        right_side_v_layout.addWidget(info_group_box, 0) # No stretch for info, compact
        self.qss_lie="""LineEdit{ border-radius: 15px; }"""
        self.info_text = LineEdit()
        setCustomStyleSheet(self.info_text, self.qss_lie, self.qss_lie)
        self.info_text.setText("No image selected")
        self.info_text.setReadOnly(True)  # 不允许用户手动输入信息
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_group_layout.addWidget(self.info_text)

        # Conversion Options with TreeWidget for better organization
        options_group_box = QGroupBox("Conversion Options")
        options_group_layout = QVBoxLayout(options_group_box)
        options_group_layout.setContentsMargins(10, 10, 10, 10) # Reset margins for options group
        options_group_box.setMinimumSize(250,500)
        right_side_v_layout.addWidget(options_group_box, 8)  # Give even more stretch to options
        
        # Create scroll area for TreeWidget
        scroll_area = ScrollArea()
        scroll_area.setWidgetResizable(True)
        #scroll_area.setMinimumSize(90,90)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # 使用更灵活的高度设置，允许根据内容自动调整
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Create TreeWidget for organized settings
        self.options_tree = TreeWidget()
        self.options_tree.setHeaderHidden(True)
        self.options_tree.setRootIsDecorated(True)
        self.options_tree.setIndentation(20)
        # Remove height restrictions to allow natural expansion
        
        # Add TreeWidget to scroll area
        scroll_area.setWidget(self.options_tree)
        options_group_layout.addWidget(scroll_area)
        
        # Setup tree structure
        self._setup_options_tree()
        # Progress Area (moved to bottom)
        progress_group_box = QGroupBox("Process")
        progress_group_layout = QVBoxLayout(progress_group_box)
        progress_group_layout.setContentsMargins(10, 25, 10, 10)
        left_layout.addWidget(progress_group_box, 0) # No stretch for progress, compact

        self.progress_label = QLabel("Ready")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        progress_group_layout.addWidget(self.progress_label)
        progress_group_layout.addWidget(self.progress)
        # Convert Button (moved before Progress) - Replace with PrimaryPushButton and apply custom style
        self.convert_button = PrimaryPushButton("Convert to ICNS")
        self.convert_button.setFixedSize(180, 40)
        font = self.convert_button.font()
        font.setPointSize(font.pointSize() + 1)
        font.setBold(True)
        self.convert_button.setFont(font)
        # Apply custom style to convert button
        setCustomStyleSheet(self.convert_button, CON.qss, CON.qss)
        self.convert_button.clicked.connect(self.on_start_conversion)
        left_layout.addWidget(self.convert_button, 0, Qt.AlignmentFlag.AlignCenter)

        

        # Add a stretch to the right_side_v_layout to push content to top
        right_side_v_layout.addStretch(1)

        # Add final stretch to main horizontal layout if needed, to push content to top-left
        # main_content_h_layout.addStretch(1) # This stretch is handled by the left/right panel stretches

        # Add a stretch to the converter layout to push everything to the top
        converter_layout.addStretch(1)
    
    def setup_batch_converter_tab(self):
        """Setup the batch converter tab content"""
        batch_layout = QVBoxLayout(self.batch_converter_tab)

        # Title for batch converter
        batch_title_label = QLabel("Batch Image Converter")
        batch_title_font = QFont()
        batch_title_font.setPointSize(batch_title_label.font().pointSize() + 6)
        batch_title_font.setBold(True)
        batch_title_label.setFont(batch_title_font)
        batch_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        batch_layout.addWidget(batch_title_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # Create horizontal layout for main content
        main_batch_h_layout = QHBoxLayout()
        main_batch_h_layout.setSpacing(20)
        batch_layout.addLayout(main_batch_h_layout)

        # Left Panel: File Selection and Preview
        left_batch_panel = QWidget()
        left_batch_layout = QVBoxLayout(left_batch_panel)
        left_batch_layout.setContentsMargins(15, 15, 15, 15)
        left_batch_layout.setSpacing(15)
        main_batch_h_layout.addWidget(left_batch_panel, 1)

        # Drop zone for files and folders
        drop_group_box = QGroupBox("File Selection")
        drop_group_layout = QVBoxLayout(drop_group_box)
        drop_group_layout.setContentsMargins(10, 25, 10, 10)
        drop_group_layout.setSpacing(15)
        left_batch_layout.addWidget(drop_group_box)

        # Drop zone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.setFixedHeight(160)
        drop_group_layout.addWidget(self.drop_zone)
        
        # Browse button for manual file selection
        browse_file_layout = QHBoxLayout()
        self.browse_file_button = PushButton("Browse...")
        self.browse_file_button.setText("Browse...")
        setCustomStyleSheet(self.browse_file_button, CON.qss, CON.qss)
        self.browse_file_button.clicked.connect(self.on_browse_batch_input)
        
        browse_file_layout.addStretch()
        browse_file_layout.addWidget(self.browse_file_button)
        drop_group_layout.addLayout(browse_file_layout)
        
        # Connect drop signals
        self.drop_zone.filesDropped.connect(self.on_batch_files_dropped)
        self.drop_zone.folderDropped.connect(self.on_batch_folder_dropped)

        # Output Directory Selection (moved here)
        output_dir_group_box = QGroupBox("Output Directory")
        output_dir_group_layout = QVBoxLayout(output_dir_group_box)
        output_dir_group_layout.setContentsMargins(10, 25, 10, 10)
        output_dir_group_layout.setSpacing(10)
        left_batch_layout.addWidget(output_dir_group_box, 0)
        
        # Batch output directory layout with drag-drop support
        batch_output_layout = QHBoxLayout()
        batch_output_label = QLabel("📁 Output Directory:")
        self.batch_output_text = DirectoryDropLineEdit()  # 使用新的拖拽支持输入框
        self.batch_output_text.setPlaceholderText("Same as input files directory")
        setCustomStyleSheet(self.batch_output_text, CON.qss_line, CON.qss_line)
        
        batch_output_button = PushButton("Browse...")
        setCustomStyleSheet(batch_output_button, CON.qss, CON.qss)
        batch_output_button.clicked.connect(self.on_browse_batch_output)
        
        batch_output_layout.addWidget(batch_output_label)
        batch_output_layout.addWidget(self.batch_output_text, 1)
        batch_output_layout.addWidget(batch_output_button)
        output_dir_group_layout.addLayout(batch_output_layout)

        # File list with remove functionality
        file_list_group_box = QGroupBox("Selected Files")
        file_list_group_layout = QVBoxLayout(file_list_group_box)
        file_list_group_layout.setContentsMargins(10, 25, 10, 10)
        left_batch_layout.addWidget(file_list_group_box, 1)

        # File list with scroll area
        file_scroll_area = ScrollArea()
        file_scroll_area.setWidgetResizable(True)
        file_scroll_area.setMinimumHeight(200)
        file_scroll_area.setMaximumHeight(300)
        
        self.file_list_widget = ListWidget()
        file_scroll_area.setWidget(self.file_list_widget)
        file_list_group_layout.addWidget(file_scroll_area)

        # File management buttons
        file_mgmt_layout = QHBoxLayout()
        self.clear_files_btn = PushButton("Clear All")
        self.remove_selected_btn = PushButton("Remove Selected")
        setCustomStyleSheet(self.clear_files_btn, CON.qss, CON.qss)
        setCustomStyleSheet(self.remove_selected_btn, CON.qss, CON.qss)
        
        self.clear_files_btn.clicked.connect(self.clear_batch_files)
        self.remove_selected_btn.clicked.connect(self.remove_selected_files)
        
        file_mgmt_layout.addWidget(self.clear_files_btn)
        file_mgmt_layout.addWidget(self.remove_selected_btn)
        file_list_group_layout.addLayout(file_mgmt_layout)

        # Preview area removed - now in dedicated Preview tab

        # Right Panel: Options and Progress
        right_batch_panel = QWidget()
        right_batch_layout = QVBoxLayout(right_batch_panel)
        right_batch_layout.setContentsMargins(15, 15, 15, 15)
        right_batch_layout.setSpacing(15)
        main_batch_h_layout.addWidget(right_batch_panel, 1)

        # Batch options (reusing existing options tree)
        options_group_box = QGroupBox("Conversion Options")
        options_group_layout = QVBoxLayout(options_group_box)
        options_group_layout.setContentsMargins(10, 25, 10, 10)
        right_batch_layout.addWidget(options_group_box, 10)

        # Create scroll area for options
        batch_scroll_area = ScrollArea()
        batch_scroll_area.setWidgetResizable(True)
        # 使用更灵活的尺寸策略
        batch_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.batch_options_tree = TreeWidget()
        self.batch_options_tree.setHeaderHidden(True)
        self.batch_options_tree.setRootIsDecorated(True)
        self.batch_options_tree.setIndentation(20)
        
        batch_scroll_area.setWidget(self.batch_options_tree)
        options_group_layout.addWidget(batch_scroll_area)

        # Setup batch options tree (reuse existing option structure)
        self._setup_batch_options_tree()

        # Batch Progress & Results section
        progress_results_group_box = QGroupBox("Batch Progress & Results")
        progress_results_layout = QVBoxLayout(progress_results_group_box)
        progress_results_layout.setContentsMargins(10, 25, 10, 10)
        progress_results_layout.setSpacing(15)
        right_batch_layout.addWidget(progress_results_group_box, 2)

        # Overall progress
        self.batch_progress_label = QLabel("Ready")
        self.batch_progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_progress = ProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)

        progress_results_layout.addWidget(self.batch_progress_label)
        progress_results_layout.addWidget(self.batch_progress)

        # Current file progress
        self.current_file_label = QLabel("No file processing")
        self.current_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_file_progress = ProgressBar()
        self.current_file_progress.setRange(0, 100)
        self.current_file_progress.setValue(0)

        progress_results_layout.addWidget(self.current_file_label)
        progress_results_layout.addWidget(self.current_file_progress)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        progress_results_layout.addWidget(separator)

        # Results display with statistics
        results_layout = QVBoxLayout()
        results_layout.setSpacing(10)
        
        # Statistics
        stats_layout = QHBoxLayout()
        self.success_count_label = QLabel("Success: 0")
        self.failed_count_label = QLabel("Failed: 0")
        self.total_count_label = QLabel("Total: 0")
        stats_layout.addWidget(self.success_count_label)
        stats_layout.addWidget(self.failed_count_label)
        stats_layout.addWidget(self.total_count_label)
        stats_layout.addStretch(1)
        results_layout.addLayout(stats_layout)

        # Results list with scroll
        results_scroll_area = ScrollArea()
        results_scroll_area.setWidgetResizable(True)
        results_scroll_area.setMinimumHeight(150)
        
        self.results_list_widget = ListWidget()
        results_scroll_area.setWidget(self.results_list_widget)
        results_layout.addWidget(results_scroll_area)

        progress_results_layout.addLayout(results_layout)

        # Batch control buttons
        batch_control_layout = QHBoxLayout()
        self.start_batch_btn = PrimaryPushButton("Start Batch Conversion")
        self.stop_batch_btn = PushButton("Stop")
        self.stop_batch_btn.setEnabled(False)
        
        setCustomStyleSheet(self.start_batch_btn, CON.qss, CON.qss)
        setCustomStyleSheet(self.stop_batch_btn, CON.qss, CON.qss)
        
        self.start_batch_btn.clicked.connect(self.start_batch_conversion)
        self.stop_batch_btn.clicked.connect(self.stop_batch_conversion)
        
        batch_control_layout.addWidget(self.start_batch_btn)
        batch_control_layout.addWidget(self.stop_batch_btn)
        right_batch_layout.addLayout(batch_control_layout)

        # Add stretch to push content to top
        right_batch_layout.addStretch(1)

        # Add stretch to push content to top-left
        batch_layout.addStretch(1)

        # Initialize batch variables
        self.batch_files = []
        self.batch_converting = False
        
    def _setup_batch_options_tree(self):
        """Setup the TreeWidget with organized settings for batch conversion (same structure as single conversion)"""
        # Clear existing items
        self.batch_options_tree.clear()
        
        # Create main categories with icons for better visual hierarchy (same as single conversion)
        basic_item = QTreeWidgetItem(["📋 Basic Options"])
        processing_item = QTreeWidgetItem(["🎨 Image Processing"])
        output_item = QTreeWidgetItem(["📤 Output Options"])
        advanced_item = QTreeWidgetItem(["⚙️ Advanced Settings"])
        
        # Add to tree
        self.batch_options_tree.addTopLevelItem(basic_item)
        self.batch_options_tree.addTopLevelItem(processing_item)
        self.batch_options_tree.addTopLevelItem(output_item)
        self.batch_options_tree.addTopLevelItem(advanced_item)
        
        # Set font for categories to make them stand out (same as single conversion)
        bold_font = self.batch_options_tree.font()
        bold_font.setBold(True)
        bold_font.setPointSize(bold_font.pointSize() + 1)
        
        basic_item.setFont(0, bold_font)
        processing_item.setFont(0, bold_font)
        output_item.setFont(0, bold_font)
        advanced_item.setFont(0, bold_font)
        
        # Set background colors for categories (same as single conversion)
        basic_item.setBackground(0, QColor(240, 248, 255, 80))  # Light blue
        processing_item.setBackground(0, QColor(240, 255, 240, 80))  # Light green
        output_item.setBackground(0, QColor(255, 250, 205, 80))  # Light yellow
        advanced_item.setBackground(0, QColor(255, 248, 240, 80))  # Light orange
        
        # Basic Options (same structure as single conversion)
        self._create_batch_basic_options(basic_item)
        
        # Processing Options (same structure as single conversion)
        self._create_batch_processing_options(processing_item)
        
        # Output Options (new)
        self._create_batch_output_options(output_item)
        
        # Advanced Options (same structure as single conversion)
        self._create_batch_advanced_options(advanced_item)
        
        # Set expansion state (same as single conversion)
        basic_item.setExpanded(True)
        processing_item.setExpanded(True)
        output_item.setExpanded(True)
        advanced_item.setExpanded(False)  # Hidden by default
        
        # Connect tree signals (same as single conversion)
        self.batch_options_tree.itemExpanded.connect(self._on_batch_tree_item_expanded)
        self.batch_options_tree.itemCollapsed.connect(self._on_batch_tree_item_collapsed)
    
    def _create_batch_basic_options(self, parent_item):
        """Create basic options widgets for batch conversion with responsive layout"""
        # Output Format
        format_widget = QWidget()
        # 使用更灵活的尺寸策略
        format_widget.setMinimumHeight(55)
        format_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        format_layout = QHBoxLayout(format_widget)
        format_layout.setContentsMargins(5, 8, 5, 8)
        
        format_label = QLabel("🗂️ Output Format:")
        format_label.setMinimumWidth(120)  # Ensure consistent width for labels
        
        self.batch_format_combo = ModelComboBox()
        self.batch_format_combo.addItems(convert.SUPPORTED_FORMATS)
        self.batch_format_combo.currentIndexChanged.connect(self.on_batch_format_change)
        setCustomStyleSheet(self.batch_format_combo, CON.qss_combo, CON.qss_combo)
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.batch_format_combo, 1)  # Give combo box more stretch
        
        format_item = QTreeWidgetItem()
        parent_item.addChild(format_item)
        self.batch_options_tree.setItemWidget(format_item, 0, format_widget)
        
        # Size Options (grouped in a sub-item)
        size_item = QTreeWidgetItem(["📏 Size Options"])
        parent_item.addChild(size_item)
        
        # Minimum Size
        min_size_widget = QWidget()
        min_size_layout = QHBoxLayout(min_size_widget)
        min_size_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        # 使用更灵活的尺寸策略
        min_size_widget.setMinimumHeight(45)
        min_size_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        min_size_label = QLabel("Min Size:")
        min_size_label.setMinimumWidth(80)
        self.batch_min_spin = SpinBox()
        setCustomStyleSheet(self.batch_min_spin, CON.qss_spin, CON.qss_spin)
        self.batch_min_spin.setRange(16, 512)
        self.batch_min_spin.setValue(self.min_size)
        self.batch_min_spin.setSuffix(" px")  # Add unit suffix
        self.batch_min_spin.valueChanged.connect(self.on_batch_min_size_change)
        
        min_size_layout.addWidget(min_size_label)
        min_size_layout.addWidget(self.batch_min_spin, 1)
        
        min_size_sub_item = QTreeWidgetItem()
        size_item.addChild(min_size_sub_item)
        self.batch_options_tree.setItemWidget(min_size_sub_item, 0, min_size_widget)
        
        # Maximum Size
        max_size_widget = QWidget()
        max_size_layout = QHBoxLayout(max_size_widget)
        max_size_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        # 使用更灵活的尺寸策略
        max_size_widget.setMinimumHeight(45)
        max_size_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        max_size_label = QLabel("Max Size:")
        max_size_label.setMinimumWidth(80)
        self.batch_max_spin = SpinBox()
        setCustomStyleSheet(self.batch_max_spin, CON.qss_spin, CON.qss_spin)
        self.batch_max_spin.setRange(32, 1024)
        self.batch_max_spin.setValue(self.max_size)
        self.batch_max_spin.setSuffix(" px")  # Add unit suffix
        self.batch_max_spin.valueChanged.connect(self.on_batch_max_size_change)
        
        max_size_layout.addWidget(max_size_label)
        max_size_layout.addWidget(self.batch_max_spin, 1)
        
        max_size_sub_item = QTreeWidgetItem()
        size_item.addChild(max_size_sub_item)
        self.batch_options_tree.setItemWidget(max_size_sub_item, 0, max_size_widget)
        
        # Auto-detect button (also indented)
        auto_widget = QWidget()
        auto_layout = QHBoxLayout(auto_widget)
        auto_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        # 使用更灵活的尺寸策略
        auto_widget.setMinimumHeight(40)
        auto_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        self.batch_auto_button = PrimaryPushButton("🔍 Auto-detect Max Size")
        setCustomStyleSheet(self.batch_auto_button, CON.qss_debug, CON.qss_debug)
        self.batch_auto_button.clicked.connect(self.on_batch_auto_detect)
        auto_layout.addWidget(self.batch_auto_button)
        
        auto_sub_item = QTreeWidgetItem()
        size_item.addChild(auto_sub_item)
        self.batch_options_tree.setItemWidget(auto_sub_item, 0, auto_widget)
        
        # Expand size options by default
        size_item.setExpanded(True)
    
    def _create_batch_processing_options(self, parent_item):
        """Create image processing options widgets for batch conversion (same as single conversion)"""
        # Keep aspect ratio
        aspect_widget = QWidget()
        aspect_layout = QHBoxLayout(aspect_widget)
        aspect_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        aspect_widget.setMinimumHeight(45)
        aspect_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.batch_keep_aspect_check = CheckBox("📐 Maintain original aspect ratio")
        self.batch_keep_aspect_check.setChecked(self.keep_aspect_ratio)
        self.batch_keep_aspect_check.stateChanged.connect(self.on_batch_keep_aspect_changed)
        aspect_layout.addWidget(self.batch_keep_aspect_check)
        
        aspect_item = QTreeWidgetItem()
        parent_item.addChild(aspect_item)
        self.batch_options_tree.setItemWidget(aspect_item, 0, aspect_widget)
        
        # Auto crop
        crop_widget = QWidget()
        crop_layout = QHBoxLayout(crop_widget)
        crop_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        crop_widget.setMinimumHeight(45)
        crop_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.batch_auto_crop_check = CheckBox("✂️ Auto-crop non-square to square")
        self.batch_auto_crop_check.setChecked(self.auto_crop)
        self.batch_auto_crop_check.stateChanged.connect(self.on_batch_auto_crop_changed)
        crop_layout.addWidget(self.batch_auto_crop_check)
        crop_item = QTreeWidgetItem()
        parent_item.addChild(crop_item)
        self.batch_options_tree.setItemWidget(crop_item, 0, crop_widget)
        
        # Quality slider
        quality_widget = QWidget()
        quality_layout = QHBoxLayout(quality_widget)
        quality_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        quality_widget.setMinimumHeight(55)
        quality_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        quality_label = QLabel("🎨 Quality:")
        quality_label.setMinimumWidth(100)  # Ensure consistent width for labels
        quality_layout.addWidget(quality_label)
        
        self.batch_quality_slider = Slider(Qt.Orientation.Horizontal)
        self.batch_quality_slider.setRange(1, 100)
        self.batch_quality_slider.setValue(self.quality)
        self.batch_quality_slider.valueChanged.connect(self.on_batch_quality_changed)
        quality_layout.addWidget(self.batch_quality_slider, 1)  # Give slider more stretch
        
        self.batch_quality_label = QLabel(str(self.quality))
        self.batch_quality_label.setMinimumWidth(30)  # Ensure consistent width for label
        quality_layout.addWidget(self.batch_quality_label)
        
        quality_item = QTreeWidgetItem()
        parent_item.addChild(quality_item)
        self.batch_options_tree.setItemWidget(quality_item, 0, quality_widget)
    
    def _create_batch_output_options(self, parent_item):
        """Create batch output options widgets"""
        # Output Structure options
        output_structure_item = QTreeWidgetItem(["📁 Output Structure Options"])
        parent_item.addChild(output_structure_item)
        
        # Preserve folder structure
        preserve_folder_widget = QWidget()
        preserve_folder_layout = QHBoxLayout(preserve_folder_widget)
        preserve_folder_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        # 使用更灵活的尺寸策略
        preserve_folder_widget.setMinimumHeight(45)
        preserve_folder_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        self.batch_preserve_folder_check = CheckBox("Preserve original folder structure")
        self.batch_preserve_folder_check.setChecked(False)
        preserve_folder_layout.addWidget(self.batch_preserve_folder_check)
        
        preserve_folder_sub_item = QTreeWidgetItem()
        output_structure_item.addChild(preserve_folder_sub_item)
        self.batch_options_tree.setItemWidget(preserve_folder_sub_item, 0, preserve_folder_widget)
        
        # Filename modification options
        filename_mod_item = QTreeWidgetItem(["📝 Filename Modification"])
        parent_item.addChild(filename_mod_item)
        
        # Prefix
        prefix_widget = QWidget()
        prefix_layout = QHBoxLayout(prefix_widget)
        prefix_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        # 使用更灵活的尺寸策略
        prefix_widget.setMinimumHeight(45)
        prefix_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        prefix_label = QLabel("Prefix:")
        prefix_label.setMinimumWidth(80)
        self.batch_prefix_edit = LineEdit()
        self.batch_prefix_edit.setPlaceholderText("Add prefix to filenames")
        prefix_layout.addWidget(prefix_label)
        prefix_layout.addWidget(self.batch_prefix_edit, 1)
        
        prefix_sub_item = QTreeWidgetItem()
        filename_mod_item.addChild(prefix_sub_item)
        self.batch_options_tree.setItemWidget(prefix_sub_item, 0, prefix_widget)
        
        # Suffix
        suffix_widget = QWidget()
        suffix_layout = QHBoxLayout(suffix_widget)
        suffix_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        # 使用更灵活的尺寸策略
        suffix_widget.setMinimumHeight(45)
        suffix_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        suffix_label = QLabel("Suffix:")
        suffix_label.setMinimumWidth(80)
        self.batch_suffix_edit = LineEdit()
        self.batch_suffix_edit.setPlaceholderText("Add suffix to filenames")
        suffix_layout.addWidget(suffix_label)
        suffix_layout.addWidget(self.batch_suffix_edit, 1)
        
        suffix_sub_item = QTreeWidgetItem()
        filename_mod_item.addChild(suffix_sub_item)
        self.batch_options_tree.setItemWidget(suffix_sub_item, 0, suffix_widget)
        
        # Expand output structure options by default
        output_structure_item.setExpanded(True)
        filename_mod_item.setExpanded(True)
    
    def _create_batch_advanced_options(self, parent_item):
        """Create advanced options widgets for batch conversion (same as single conversion)"""
        # ICNS method
        method_widget = QWidget()
        method_layout = QHBoxLayout(method_widget)
        method_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        method_widget.setMinimumHeight(55)
        method_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        method_label = QLabel("⚙️ ICNS method:")
        method_label.setMinimumWidth(120)  # Ensure consistent width for labels
        method_layout.addWidget(method_label)
        
        self.batch_icns_method_combo = ModelComboBox()
        self.batch_icns_method_combo.addItems(["iconutil (Recommended)", "Pillow Fallback"])
        self.batch_icns_method_combo.setCurrentText(self.icns_method)
        self.batch_icns_method_combo.currentTextChanged.connect(self.on_batch_icns_method_changed)
        setCustomStyleSheet(self.batch_icns_method_combo, CON.qss_combo, CON.qss_combo)
        method_layout.addWidget(self.batch_icns_method_combo, 1)  # Give combo box more stretch
        
        method_item = QTreeWidgetItem()
        parent_item.addChild(method_item)
        self.batch_options_tree.setItemWidget(method_item, 0, method_widget)
        
        # Overwrite confirmation
        overwrite_widget = QWidget()
        overwrite_layout = QHBoxLayout(overwrite_widget)
        overwrite_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        overwrite_widget.setMinimumHeight(45)
        overwrite_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.batch_overwrite_confirm_check = CheckBox("⚠️ Confirm before overwriting files")
        self.batch_overwrite_confirm_check.setChecked(self.overwrite_confirm)
        self.batch_overwrite_confirm_check.stateChanged.connect(self.on_batch_overwrite_confirm_changed)
        overwrite_layout.addWidget(self.batch_overwrite_confirm_check)
        
        overwrite_item = QTreeWidgetItem()
        parent_item.addChild(overwrite_item)
        self.batch_options_tree.setItemWidget(overwrite_item, 0, overwrite_widget)
        
    def _update_batch_basic_options(self):
        """Update batch basic options display"""
        # Find and update the basic options item
        basic_item = self.batch_options_tree.topLevelItem(0)
        if basic_item and basic_item.text(0) == "Basic Options":
            basic_item.setText(0, f"Basic Options (Min: {self.batch_min_spin.value()}px, Max: {self.batch_max_spin.value()}px, Format: {self.batch_format_combo.currentText()})")
    
    def create_history_tab(self):
        """Create the history tab for conversion history"""
        if not self.remember_path:
            # If remember_path is disabled, remove history tab if it exists
            if hasattr(self, 'history_tab') and self.history_tab:
                tab_index = self.tab_widget.indexOf(self.history_tab)
                if tab_index != -1:
                    self.tab_widget.removeTab(tab_index)
                self.history_tab = None
            return
            
        # Only create history tab if it doesn't already exist
        if hasattr(self, 'history_tab') and self.history_tab:
            # History tab already exists, just update its content
            self.load_conversion_history()
            return
            
        # Create history tab
        self.history_tab = QWidget()
        self.tab_widget.addTab(self.history_tab, "History")
        
        history_layout = QVBoxLayout(self.history_tab)
        history_layout.setContentsMargins(15, 15, 15, 15)
        history_layout.setSpacing(15)
        
        # History title
        history_title = QLabel("Conversion History")
        title_font = QFont()
        title_font.setPointSize(history_title.font().pointSize() + 4)
        title_font.setBold(True)
        history_title.setFont(title_font)
        history_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        history_layout.addWidget(history_title)
        
        # Clear history button (moved up)
        clear_history_btn = PushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_conversion_history)
        setCustomStyleSheet(clear_history_btn, CON.qss, CON.qss)
        history_layout.addWidget(clear_history_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        # History list
        self.history_list = ListWidget()
        history_layout.addWidget(self.history_list)
        
        # Load existing history
        self.load_conversion_history()
    
    def add_to_history(self, input_file: str, output_file: str, format_type: str):
        """Add a conversion to history"""
        if not self.remember_path:
            return
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        history_item = {
            'timestamp': timestamp,
            'input': input_file,
            'output': output_file,
            'format': format_type
        }
        
        self.conversion_history.append(history_item)
        
        # Keep only last 50 items
        if len(self.conversion_history) > 50:
            self.conversion_history = self.conversion_history[-50:]
            
        self.save_conversion_history()
        self.update_history_display()
    
    def load_conversion_history(self):
        """Load conversion history from settings"""
        if not self.remember_path:
            return
            
        settings = QSettings("MyCompany", "ConverterApp")
        history_size = settings.beginReadArray("conversion_history")
        
        self.conversion_history = []
        for i in range(history_size):
            settings.setArrayIndex(i)
            item = {
                'timestamp': settings.value("timestamp", ""),
                'input': settings.value("input", ""),
                'output': settings.value("output", ""),
                'format': settings.value("format", "")
            }
            self.conversion_history.append(item)
        
        settings.endArray()
        self.update_history_display()
    
    def save_conversion_history(self):
        """Save conversion history to settings"""
        if not self.remember_path:
            return
            
        settings = QSettings("MyCompany", "ConverterApp")
        settings.beginWriteArray("conversion_history")
        
        for i, item in enumerate(self.conversion_history):
            settings.setArrayIndex(i)
            settings.setValue("timestamp", item['timestamp'])
            settings.setValue("input", item['input'])
            settings.setValue("output", item['output'])
            settings.setValue("format", item['format'])
        
        settings.endArray()
    
    def update_history_display(self):
        """Update the history list display"""
        if not hasattr(self, 'history_list'):
            return
            
        self.history_list.clear()
        
        for item in reversed(self.conversion_history):  # Show newest first
            display_text = f"{item['timestamp']} - {os.path.basename(item['input'])} → {item['format'].upper()}"
            list_item = QListWidgetItem(display_text)
            list_item.setToolTip(f"Input: {item['input']}\nOutput: {item['output']}")
            self.history_list.addItem(list_item)
    
    def clear_conversion_history(self):
        """Clear all conversion history with confirmation popup"""
        # Show confirmation popup
        self._show_clear_history_popup()
    
    def _show_clear_history_popup(self):
        """Show popup to confirm clearing history"""
        from qfluentwidgets import MessageBox, FluentIcon
        
        # Create confirmation dialog
        box = MessageBox(
            title='Clear History Confirmation',
            content='Are you sure you want to clear all conversion history? This action cannot be undone.',
            parent=self
        )
        box.yesButton.setText('Clear History')
        box.cancelButton.setText('Cancel')
        
        if box.exec():
            # User confirmed, clear history
            self._confirm_clear_history()
    
    def _confirm_clear_history(self):
        """Actually clear the history after confirmation"""
        self.conversion_history = []
        self.save_conversion_history()
        self.update_history_display()
        
        # Show success info bar
        from qfluentwidgets import InfoBar, InfoBarPosition, FluentIcon
        InfoBar.success(
            title='History Cleared',
            content='All conversion history has been successfully cleared.',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _setup_options_tree(self):
        """Setup the TreeWidget with organized settings"""
        # Clear existing items
        self.options_tree.clear()
        
        # Create main categories with icons for better visual hierarchy
        basic_item = QTreeWidgetItem(["📋 Basic Options"])
        processing_item = QTreeWidgetItem(["🎨 Image Processing"])
        advanced_item = QTreeWidgetItem(["⚙️ Advanced Settings"])
        
        # Add to tree
        self.options_tree.addTopLevelItem(basic_item)
        self.options_tree.addTopLevelItem(processing_item)
        self.options_tree.addTopLevelItem(advanced_item)
        
        # Set font for categories to make them stand out
        bold_font = self.options_tree.font()
        bold_font.setBold(True)
        bold_font.setPointSize(bold_font.pointSize() + 1)
        
        basic_item.setFont(0, bold_font)
        processing_item.setFont(0, bold_font)
        advanced_item.setFont(0, bold_font)
        
        # Set background colors for categories
        basic_item.setBackground(0, QColor(240, 248, 255, 80))  # Light blue
        processing_item.setBackground(0, QColor(240, 255, 240, 80))  # Light green
        advanced_item.setBackground(0, QColor(255, 248, 240, 80))  # Light orange
        
        # Basic Options
        self._create_basic_options(basic_item)
        
        # Processing Options
        self._create_processing_options(processing_item)
        
        # Advanced Options (initially collapsed)
        self._create_advanced_options(advanced_item)
        
        # Set expansion state
        basic_item.setExpanded(True)
        processing_item.setExpanded(True)
        advanced_item.setExpanded(False)  # Hidden by default
        
        # Connect tree signals
        self.options_tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.options_tree.itemCollapsed.connect(self._on_tree_item_collapsed)
    
    def _create_basic_options(self, parent_item):
        """Create basic options widgets with responsive layout"""
        # Output Format
        format_widget = QWidget()
        # 使用更灵活的尺寸策略而不是固定最小尺寸
        format_widget.setMinimumHeight(55)
        format_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        format_layout = QHBoxLayout(format_widget)
        format_layout.setContentsMargins(5, 8, 5, 8)
        
        format_label = QLabel("🗂️ Output Format:")
        format_label.setMinimumWidth(120)  # Ensure consistent width for labels
        
        self.format_combo = ModelComboBox()
        self.format_combo.addItems(convert.SUPPORTED_FORMATS)
        self.format_combo.currentIndexChanged.connect(self.on_format_change)
        setCustomStyleSheet(self.format_combo, CON.qss_combo, CON.qss_combo)
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo, 1)  # Give combo box more stretch
        
        format_item = QTreeWidgetItem()
        parent_item.addChild(format_item)
        self.options_tree.setItemWidget(format_item, 0, format_widget)
        
        # Size Options (grouped in a sub-item)
        size_item = QTreeWidgetItem(["📏 Size Options"])
        parent_item.addChild(size_item)
        
        # Minimum Size
        min_size_widget = QWidget()
        min_size_layout = QHBoxLayout(min_size_widget)
        min_size_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        min_size_widget.setMinimumSize(300, 45)
        
        min_size_label = QLabel("Min Size:")
        min_size_label.setMinimumWidth(80)
        self.min_spin = SpinBox()
        setCustomStyleSheet(self.min_spin, CON.qss_spin, CON.qss_spin)
        self.min_spin.setRange(16, 512)
        self.min_spin.setSuffix(" px")  # Add unit suffix
        self.min_spin.valueChanged.connect(self.on_min_size_change)
        
        min_size_layout.addWidget(min_size_label)
        min_size_layout.addWidget(self.min_spin, 1)
        
        min_size_sub_item = QTreeWidgetItem()
        size_item.addChild(min_size_sub_item)
        self.options_tree.setItemWidget(min_size_sub_item, 0, min_size_widget)
        
        # Maximum Size
        max_size_widget = QWidget()
        max_size_layout = QHBoxLayout(max_size_widget)
        max_size_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        max_size_widget.setMinimumSize(300, 45)
        
        max_size_label = QLabel("Max Size:")
        max_size_label.setMinimumWidth(80)
        self.max_spin = SpinBox()
        setCustomStyleSheet(self.max_spin, CON.qss_spin, CON.qss_spin)
        self.max_spin.setRange(32, 1024)
        self.max_spin.setSuffix(" px")  # Add unit suffix
        self.max_spin.valueChanged.connect(self.on_max_size_change)
        
        max_size_layout.addWidget(max_size_label)
        max_size_layout.addWidget(self.max_spin, 1)
        
        max_size_sub_item = QTreeWidgetItem()
        size_item.addChild(max_size_sub_item)
        self.options_tree.setItemWidget(max_size_sub_item, 0, max_size_widget)
        
        # Auto-detect button (also indented)
        auto_widget = QWidget()
        auto_layout = QHBoxLayout(auto_widget)
        auto_layout.setContentsMargins(25, 5, 5, 5)  # Indent for sub-item
        auto_widget.setMinimumSize(300, 40)
        
        self.auto_button = PrimaryPushButton("🔍 Auto-detect Max Size")
        setCustomStyleSheet(self.auto_button, CON.qss_debug, CON.qss_debug)
        self.auto_button.clicked.connect(self.on_auto_detect)
        auto_layout.addWidget(self.auto_button)
        
        auto_sub_item = QTreeWidgetItem()
        size_item.addChild(auto_sub_item)
        self.options_tree.setItemWidget(auto_sub_item, 0, auto_widget)
        
        # Expand size options by default
        size_item.setExpanded(True)
    
    def _create_processing_options(self, parent_item):
        """Create image processing options widgets with responsive layout"""
        # Keep aspect ratio
        aspect_widget = QWidget()
        aspect_layout = QHBoxLayout(aspect_widget)
        aspect_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        aspect_widget.setMinimumHeight(45)
        aspect_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.keep_aspect_check = CheckBox("📐 Maintain original aspect ratio")
        self.keep_aspect_check.stateChanged.connect(self.on_keep_aspect_changed)
        aspect_layout.addWidget(self.keep_aspect_check)
        
        aspect_item = QTreeWidgetItem()
        parent_item.addChild(aspect_item)
        self.options_tree.setItemWidget(aspect_item, 0, aspect_widget)
        
        # Auto crop
        crop_widget = QWidget()
        crop_layout = QHBoxLayout(crop_widget)
        crop_layout.setContentsMargins(5, 8, 5, 8)
        crop_widget.setMinimumSize(300, 45)
        self.auto_crop_check = CheckBox("✂️ Auto-crop non-square to square")
        self.auto_crop_check.stateChanged.connect(self.on_auto_crop_changed)
        crop_layout.addWidget(self.auto_crop_check)
        crop_item = QTreeWidgetItem()
        parent_item.addChild(crop_item)
        self.options_tree.setItemWidget(crop_item, 0, crop_widget)
        
        # Quality slider
        quality_widget = QWidget()
        quality_layout = QHBoxLayout(quality_widget)
        quality_layout.setContentsMargins(5, 8, 5, 8)
        quality_widget.setMinimumSize(300, 55)
        quality_label = QLabel("🎨 Quality:")
        quality_label.setMinimumWidth(100)  # Ensure consistent width for labels
        quality_layout.addWidget(quality_label)
        
        self.quality_slider = Slider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(85)
        self.quality_slider.valueChanged.connect(self.on_quality_changed)
        quality_layout.addWidget(self.quality_slider, 1)  # Give slider more stretch
        
        self.quality_label = QLabel("85")
        self.quality_label.setMinimumWidth(30)  # Ensure consistent width for label
        quality_layout.addWidget(self.quality_label)
        
        quality_item = QTreeWidgetItem()
        parent_item.addChild(quality_item)
        self.options_tree.setItemWidget(quality_item, 0, quality_widget)
    
    def _create_advanced_options(self, parent_item):
        """Create advanced settings widgets with responsive layout"""
        # ICNS method selection
        method_widget = QWidget()
        method_layout = QHBoxLayout(method_widget)
        method_layout.setContentsMargins(5, 8, 5, 8)
        # 使用更灵活的尺寸策略
        method_widget.setMinimumHeight(55)
        method_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        method_label = QLabel("⚙️ ICNS method:")
        method_label.setMinimumWidth(120)  # Ensure consistent width for labels
        method_layout.addWidget(method_label)
        
        self.icns_method_combo = ModelComboBox()
        self.icns_method_combo.addItems(["iconutil (Recommended)", "Pillow Fallback"])
        self.icns_method_combo.currentTextChanged.connect(self.on_icns_method_changed)
        setCustomStyleSheet(self.icns_method_combo, CON.qss_combo, CON.qss_combo)
        method_layout.addWidget(self.icns_method_combo, 1)  # Give combo box more stretch
        
        method_item = QTreeWidgetItem()
        parent_item.addChild(method_item)
        self.options_tree.setItemWidget(method_item, 0, method_widget)
        
        # Overwrite confirmation
        overwrite_widget = QWidget()
        overwrite_layout = QHBoxLayout(overwrite_widget)
        overwrite_layout.setContentsMargins(5, 8, 5, 8)
        overwrite_widget.setMinimumSize(300, 45)
        self.overwrite_confirm_check = CheckBox("⚠️ Confirm before overwriting files")
        self.overwrite_confirm_check.stateChanged.connect(self.on_overwrite_confirm_changed)
        overwrite_layout.addWidget(self.overwrite_confirm_check)
        
        overwrite_item = QTreeWidgetItem()
        parent_item.addChild(overwrite_item)
        self.options_tree.setItemWidget(overwrite_item, 0, overwrite_widget)
    
    def on_tab_changed(self, index):
        """Handle tab change without animation"""
        # Simply store the previous tab index and return
        self._previous_tab_index = index
    
    def _on_tree_item_expanded(self, item):
        """Handle tree item expansion"""
        # Optional: Add any logic when items are expanded
        pass
    
    def _on_tree_item_collapsed(self, item):
        """Handle tree item collapse"""
        # Optional: Add any logic when items are collapsed
        pass

    def create_success_view(self):
        # Create success widget as a top-level overlay
        self.success_widget = QWidget(self)
        self.success_widget.setObjectName("success_overlay")
        
        # Set it to cover the entire window
        self.success_widget.setGeometry(self.rect())
        
        # Create layout for success widget
        self.success_layout = QVBoxLayout(self.success_widget)
        self.success_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a semi-transparent overlay background
        overlay = QWidget()
        overlay.setObjectName("success_overlay")
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        
        center_panel = QWidget()
        center_panel.setObjectName("success_center_panel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(50, 50, 50, 50) # Increased margins
        center_layout.setSpacing(20)
        
        # Add stretch to center the panel vertically
        overlay_layout.addStretch()
        overlay_layout.addWidget(center_panel, 0, Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch()
        
        self.success_layout.addWidget(overlay)

        center_layout.addStretch()

        title = QLabel("Conversion Successful!")
        font = title.font()
        font.setPointSize(font.pointSize() + 8) # Larger title
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("success_title_label")
        center_layout.addWidget(title)

        checkmark = QLabel("✓")
        checkmark_font = checkmark.font()
        checkmark_font.setPointSize(checkmark_font.pointSize() + 30) # Larger checkmark
        checkmark_font.setBold(True)
        checkmark.setFont(checkmark_font)
        checkmark.setObjectName("success_checkmark_label")
        checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(checkmark)

        msg = QLabel(f"Your {str(self.output_format).upper()} file has been created successfully!")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setObjectName("success_message_label") # Object name for QSS
        center_layout.addWidget(msg)

        # Conditionally show "Open Converted File" button based on auto_preview setting
        if not self.auto_preview:
            open_btn = PrimaryPushButton("Open Converted File")
            open_btn.clicked.connect(self.on_open_converted_file)
            open_btn.setFixedSize(200, 45) # Larger buttons
            open_btn.setObjectName("open_converted_file_button") # Object name for QSS
            # Apply custom style to open button
            setCustomStyleSheet(open_btn, CON.qss, CON.qss)
            center_layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignCenter)

        return_btn = PushButton("Return to Converter")
        return_btn.clicked.connect(self.show_main_view)
        return_btn.setFixedSize(200, 45) # Larger buttons
        return_btn.setObjectName("return_to_converter_button") # Object name for QSS
        # Apply custom style to return button
        setCustomStyleSheet(return_btn, CON.qss, CON.qss)
        center_layout.addWidget(return_btn, 0, Qt.AlignmentFlag.AlignCenter)

        center_layout.addStretch()

        self.success_widget.hide() # Initially hidden

    def create_batch_success_view(self):
        """Create a specialized batch conversion success view"""
        # Create batch success widget as a top-level overlay
        self.batch_success_widget = QWidget(self)
        self.batch_success_widget.setObjectName("success_overlay")
        
        # Set it to cover the entire window
        self.batch_success_widget.setGeometry(self.rect())
        
        # Create layout for batch success widget
        self.batch_success_layout = QVBoxLayout(self.batch_success_widget)
        self.batch_success_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a semi-transparent overlay background
        overlay = QWidget()
        overlay.setObjectName("success_overlay")
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        
        center_panel = QWidget()
        center_panel.setObjectName("success_center_panel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(50, 50, 50, 50) # Increased margins
        center_layout.setSpacing(20)
        
        # Add stretch to center the panel vertically
        overlay_layout.addStretch()
        overlay_layout.addWidget(center_panel, 0, Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch()
        
        self.batch_success_layout.addWidget(overlay)

        center_layout.addStretch()

        # Batch success title
        title = QLabel("Batch Conversion Complete!")
        font = title.font()
        font.setPointSize(font.pointSize() + 8) # Larger title
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("success_title_label")
        center_layout.addWidget(title)

        # Batch checkmark with check symbol
        checkmark = QLabel("✓")
        checkmark_font = checkmark.font()
        checkmark_font.setPointSize(checkmark_font.pointSize() + 30) # Larger checkmark
        checkmark_font.setBold(True)
        checkmark.setFont(checkmark_font)
        checkmark.setObjectName("success_checkmark_label")
        checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(checkmark)

        # Dynamic message - will be updated with actual batch stats
        self.batch_success_message = QLabel("Processing batch conversion results...")
        self.batch_success_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_success_message.setObjectName("success_message_label")
        center_layout.addWidget(self.batch_success_message)

        # Batch statistics display
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setSpacing(10)
        
        self.batch_file_count_label = QLabel("Files Processed: 0")
        self.batch_file_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_file_count_label.setObjectName("batch_file_count_label")
        stats_layout.addWidget(self.batch_file_count_label)
        
        self.batch_success_count_label = QLabel("Successfully Converted: 0")
        self.batch_success_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_success_count_label.setObjectName("batch_success_count_label")
        stats_layout.addWidget(self.batch_success_count_label)
        
        self.batch_failed_count_label = QLabel("Failed Conversions: 0")
        self.batch_failed_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_failed_count_label.setObjectName("batch_failed_count_label")
        stats_layout.addWidget(self.batch_failed_count_label)
        
        self.batch_output_dir_label = QLabel("Output Directory: ")
        self.batch_output_dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_output_dir_label.setWordWrap(True)
        self.batch_output_dir_label.setObjectName("batch_output_dir_label")
        stats_layout.addWidget(self.batch_output_dir_label)
        
        center_layout.addWidget(stats_widget)

        # Button layout
        button_layout = QHBoxLayout()
        
        # Open output folder button
        open_folder_btn = PrimaryPushButton("Open Output Folder")
        open_folder_btn.clicked.connect(self.on_open_batch_output_folder)
        open_folder_btn.setFixedSize(200, 45) # Larger buttons
        open_folder_btn.setObjectName("open_converted_file_button") # Object name for QSS
        setCustomStyleSheet(open_folder_btn, CON.qss, CON.qss)
        button_layout.addWidget(open_folder_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Return to converter button
        return_btn = PushButton("Return to Converter")
        return_btn.clicked.connect(self.show_main_view)
        return_btn.setFixedSize(200, 45) # Larger buttons
        return_btn.setObjectName("return_to_converter_button") # Object name for QSS
        setCustomStyleSheet(return_btn, CON.qss, CON.qss)
        button_layout.addWidget(return_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        center_layout.addLayout(button_layout)
        center_layout.addStretch()

        self.batch_success_widget.hide() # Initially hidden

    def show_batch_success_view(self, total_files=0, success_count=0, failed_count=0, output_dir="", format_name="PNG"):
        """Show the batch success view with dynamic statistics"""
        # Update the batch success widget geometry to match the window
        self.batch_success_widget.setGeometry(self.rect())
        
        # Update dynamic content
        if hasattr(self, 'batch_success_message'):
            if failed_count == 0:
                self.batch_success_message.setText(f"All {total_files} {format_name.upper()} files converted successfully!")
            elif success_count == 0:
                self.batch_success_message.setText(f"Batch conversion failed: {failed_count} files could not be converted")
            else:
                self.batch_success_message.setText(f"Batch conversion completed: {success_count}/{total_files} files converted successfully")
        
        if hasattr(self, 'batch_file_count_label'):
            self.batch_file_count_label.setText(f"Files Processed: {total_files}")
        
        if hasattr(self, 'batch_success_count_label'):
            self.batch_success_count_label.setText(f"Successfully Converted: {success_count}")
        
        if hasattr(self, 'batch_failed_count_label'):
            if failed_count > 0:
                self.batch_failed_count_label.setText(f"Failed Conversions: {failed_count}")
                self.batch_failed_count_label.show()
            else:
                # Hide failed count when it's 0
                self.batch_failed_count_label.hide()
        
        if hasattr(self, 'batch_output_dir_label'):
            self.batch_output_dir_label.setText(f"Output Directory: {output_dir}")
        
        # Show the batch success widget as an overlay
        self.batch_success_widget.show()
        self.batch_success_widget.raise_()  # Bring to front
        
        # Apply theme-specific styles
        self._apply_success_theme()

    def on_open_batch_output_folder(self):
        """Open the batch output folder in the file explorer"""
        output_dir = self.output_dir_input.text().strip()
        if output_dir and os.path.exists(output_dir):
            try:
                if sys.platform == "win32":
                    os.startfile(output_dir)
                elif sys.platform == "darwin":
                    subprocess.run(["open", output_dir])
                else:  # Linux and other POSIX systems
                    subprocess.run(["xdg-open", output_dir])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")
        else:
            QMessageBox.warning(self, "Error", "Output directory not found")

    def _set_placeholder_preview(self):
        """Set placeholder text in the preview tab"""
        # Clear existing previews and show default info
        self.preview_tab.clear_previews()


    def on_browse_input(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Image files (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.ico *.icns);;All files (*.*)")
        
        # Remember last path if setting is enabled
        if self.remember_path and hasattr(self, 'last_input_dir') and self.last_input_dir:
            file_dialog.setDirectory(str(self.last_input_dir))
            
        if file_dialog.exec():
            self.input_path = file_dialog.selectedFiles()[0]
            self.input_text.setText(self.input_path)
            
            # Remember the directory for next time if setting is enabled
            if self.remember_path:
                self.last_input_dir = os.path.dirname(self.input_path)
                
            self.auto_set_output()
            
            # Show preview if auto_preview setting is enabled
            if self.auto_preview:
                self.show_preview()
                
            self.update_image_info()
            
    def on_browse_output(self):
        system=platform.system()
        if "Darwin" in system.lower():
            wildcard_map = {
                "icns": "ICNS files (*.icns)",
                "jpg": "JPEG files (*.jpg)",
                "jpeg": "JPEG files (*.jpeg)",
                "webp": "WebP files (*.webp)",
                "bmp": "BMP files (*.bmp)",
                "gif": "GIF files (*.gif)",
                "tiff": "TIFF files (*.tiff)",
                "ico": "ICO files (*.ico)",
                "png": "PNG files (*.png)",
            }
        else:
            wildcard_map = {
                "jpg": "JPEG files (*.jpg)",
                "jpeg": "JPEG files (*.jpeg)",
                "webp": "WebP files (*.webp)",
                "bmp": "BMP files (*.bmp)",
                "gif": "GIF files (*.gif)",
                "tiff": "TIFF files (*.tiff)",
                "ico": "ICO files (*.ico)",
                "png": "PNG files (*.png)",
            }
        default_filter = wildcard_map.get(str(self.output_format), "All files (*.*)")
        
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave) # Corrected enum
        file_dialog.setNameFilter(f"{default_filter};;All files (*.*)")
        file_dialog.setDefaultSuffix(str(self.output_format))
        
        # Remember last path if setting is enabled
        if self.remember_path and hasattr(self, 'last_output_dir') and self.last_output_dir:
            file_dialog.setDirectory(str(self.last_output_dir))

        if file_dialog.exec():
            self.output_path = file_dialog.selectedFiles()[0]
            expected_extension = '.' + str(self.output_format)
            if not self.output_path.lower().endswith(expected_extension):
                self.output_path += expected_extension
            self.output_text.setText(self.output_path)
            
            # Remember the directory for next time if setting is enabled
            if self.remember_path:
                self.last_output_dir = os.path.dirname(self.output_path)

    def on_browse_batch_input(self):
        """Browse for batch input files"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Supported Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.ico *.tiff);;All Files (*)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        
        # Use last directory if available
        if hasattr(self, 'last_batch_input_dir') and self.last_batch_input_dir:
            file_dialog.setDirectory(self.last_batch_input_dir)
        
        if file_dialog.exec() == QFileDialog.DialogCode.Accept:
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                # Remember this directory for future use
                self.last_batch_input_dir = os.path.dirname(selected_files[0])
                
                # Add files to batch file list
                for file_path in selected_files:
                    self._add_file_to_batch_list(file_path)
    
    def on_browse_batch_output(self):
        """Browse for batch output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Batch Conversion",
            self.batch_output_text.text() if self.batch_output_text.text() else os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if directory:
            self.batch_output_text.setText(directory)
            # Remember this directory for future use
            self.last_batch_output_dir = directory
            
    def on_format_change(self, index):
        self.output_format = self.format_combo.currentText().lower()
        self.auto_set_output()
        self.save_settings()
        
        if self.output_format == "png":
            self.convert_button.setText("Convert to PNG")
        else:
            self.convert_button.setText(f"Convert to {self.output_format.upper()}")
        
        enable_size_options = (self.output_format == "icns")
        self.min_spin.setEnabled(enable_size_options)
        self.max_spin.setEnabled(enable_size_options)
        self.auto_button.setEnabled(enable_size_options)
        
    def on_batch_format_change(self, index):
        """Handle format change in batch conversion"""
        batch_output_format = self.batch_format_combo.currentText().lower()
        
        # Enable/disable auto-detect button based on format
        if hasattr(self, 'batch_use_auto_detect'):
            if batch_output_format in ['png', 'jpg', 'jpeg', 'webp']:
                self.batch_use_auto_detect.setEnabled(True)
            else:
                self.batch_use_auto_detect.setEnabled(False)
                self.batch_use_auto_detect.setChecked(False)
        
        # Enable/disable min/max spin boxes based on format
        if hasattr(self, 'batch_min_spin') and hasattr(self, 'batch_max_spin'):
            enable_size_options = (batch_output_format == "icns")
            self.batch_min_spin.setEnabled(enable_size_options)
            self.batch_max_spin.setEnabled(enable_size_options)
        
    def auto_set_output(self):
        if self.input_path:
            base_name = os.path.splitext(os.path.basename(self.input_path))[0]
            output_file = os.path.join(os.path.dirname(self.input_path), f"{base_name}.{self.output_format}")
            self.output_path = output_file
            self.output_text.setText(output_file)
            
    def update_image_info(self):
        if self.input_path and os.path.exists(self.input_path):
            try:
                width, height = convert.get_image_info(self.input_path)
                self.info_text.setText(f"Dimensions: {width}x{height}px")
                self.max_size = min(width, height)
                self.max_spin.setValue(self.max_size)
            except Exception as e:
                self.info_text.setText(f"Error reading image: {str(e)}")
        else:
            self.info_text.setText("No image selected")
            
    def on_auto_detect(self):
        if self.input_path and os.path.exists(self.input_path):
            try:
                width, height = convert.get_image_info(self.input_path)
                self.max_size = min(width, height)
                self.max_spin.setValue(self.max_size)
                self.status_bar.showMessage(f"Max size auto-detected: {self.max_size}")
            except Exception as e:
                PopupTeachingTip.create(
                    target=self.auto_button,
                    icon=InfoBarIcon.ERROR,
                    title='ERROR',
                    content=f"Could not detect image size: {str(e)}",
                    isClosable=True,
                    tailPosition=TeachingTipTailPosition.LEFT_BOTTOM,
                    duration=10000,
                    parent=self
                )
                
        else:
            PopupTeachingTip.create(
                    target=self.auto_button,
                    icon=InfoBarIcon.WARNING,
                    title='Warning',
                    content="Please select an input file first.",
                    isClosable=True,
                    tailPosition=TeachingTipTailPosition.RIGHT_BOTTOM,
                    duration=2000,
                    parent=self
            )
            
            
    def show_preview(self):
        """Show preview in the preview tab"""
        if self.input_path and os.path.exists(self.input_path):
            try:
                # Use the preview_tab to display the single preview
                self.preview_tab.show_single_preview(self.input_path)
                img = Image.open(self.input_path)
                self.status_bar.showMessage(f"Loaded: {os.path.basename(self.input_path)} ({img.size[0]}x{img.size[1]})")
            except Exception as e:
                self.status_bar.showMessage("Preview error")
        else:
            self.preview_tab.clear_previews()
            self.status_bar.showMessage("Ready")
            
    def on_min_size_change(self, value):
        self.min_size = value
        self.save_settings()
        
    def on_max_size_change(self, value):
        self.max_size = value
        self.save_settings()
        
    # New signal handlers for image processing and advanced options
    def on_keep_aspect_changed(self, state):
        self.keep_aspect_ratio = bool(state)
        self.save_settings()
        
    def on_auto_crop_changed(self, state):
        self.auto_crop = bool(state)
        self.save_settings()
        
    def on_quality_changed(self, value):
        self.quality = value
        self.quality_label.setText(str(value))
        self.save_settings()
        
    def on_batch_auto_detect(self):
        """Handle auto-detect in batch conversion"""
        # For batch conversion, auto-detect would typically operate on the first file
        # or show a message that this feature is not applicable for batch conversion
        PopupTeachingTip.create(
            target=self.batch_auto_button,
            icon=InfoBarIcon.WARNING,
            title='Notice',
            content="Auto-detect is not available for batch conversion. Size limits will apply to all files.",
            isClosable=True,
            tailPosition=TeachingTipTailPosition.TOP,
            duration=3000,
            parent=self
        )
        
    def on_icns_method_changed(self, text):
        self.icns_method = text
        self.save_settings()
        
    def on_overwrite_confirm_changed(self, state):
        self.overwrite_confirm = bool(state)
        self.save_settings()
        
    # Batch conversion event handlers (mirroring single conversion handlers)
    def on_batch_min_size_change(self, value):
        if hasattr(self, 'batch_min_size'):
            self.batch_min_size = value
            
    def on_batch_max_size_change(self, value):
        if hasattr(self, 'batch_max_size'):
            self.batch_max_size = value
            
    def on_batch_quality_changed(self, value):
        if hasattr(self, 'batch_quality'):
            self.batch_quality = value
            
    def on_batch_icns_method_changed(self, text):
        if hasattr(self, 'batch_icns_method'):
            self.batch_icns_method = text
            
    def on_batch_overwrite_confirm_changed(self, state):
        if hasattr(self, 'batch_overwrite_confirm'):
            self.batch_overwrite_confirm = bool(state)
            
    def on_batch_keep_aspect_changed(self, state):
        if hasattr(self, 'batch_keep_aspect_ratio'):
            self.batch_keep_aspect_ratio = bool(state)
            
    def on_batch_auto_crop_changed(self, state):
        if hasattr(self, 'batch_auto_crop'):
            self.batch_auto_crop = bool(state)
            
    def _on_batch_tree_item_expanded(self, item):
        """Handle batch tree item expansion"""
        pass  # Could be enhanced for batch-specific behavior
        
    def _on_batch_tree_item_collapsed(self, item):
        """Handle batch tree item collapse"""
        pass  # Could be enhanced for batch-specific behavior
    
    def on_interface_setting_changed(self):
        """Handle changes to interface behavior settings"""
        # This method will be called when settings are changed from the settings dialog
        # Reload the settings and update the UI accordingly
        self.load_settings()
        
        # Update history tab visibility only when remember_path setting actually changes
        self.create_history_tab()
        
        # If auto_preview setting changed, update preview behavior
        if hasattr(self, 'input_path') and self.input_path and self.auto_preview:
            self.show_preview()
    
    def dragEnterEvent(self, event):
        """Handle drag enter events for image files"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # Check if any URL is a valid image file
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if os.path.isfile(file_path):
                        # Check if it's an image file
                        image_extensions = ['.icns','.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.ico', '.webp']
                        if any(file_path.lower().endswith(ext) for ext in image_extensions):
                            event.acceptProposedAction()
                            return
            event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Handle drop events for image files"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            image_files = []
            
            # Collect all valid image files
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if os.path.isfile(file_path):
                        # Check if it's an image file
                        image_extensions = ['.icns','.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.ico', '.webp']
                        if any(file_path.lower().endswith(ext) for ext in image_extensions):
                            image_files.append(file_path)
            
            if image_files:
                # Use the first image file
                self.input_path = image_files[0]
                self.input_text.setText(self.input_path)
                
                # Remember the directory for next time if setting is enabled
                if self.remember_path:
                    self.last_input_dir = os.path.dirname(self.input_path)
                
                self.auto_set_output()
                
                # Show preview if auto_preview setting is enabled
                if self.auto_preview:
                    self.show_preview()
                
                self.update_image_info()
                
                # Show success message
                self.status_bar.showMessage(f"Loaded {len(image_files)} image(s) via drag & drop")
                
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
            
    def on_start_conversion(self):
        if self.converting:
            return
            
        if not self.input_path:
            PopupTeachingTip.create(
                target=self.convert_button,
                icon=InfoBarIcon.ERROR,
                title='ERROR',
                content=f"Please select an input image file.",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=2000,
                parent=self
            )
            return

        if not self.output_path:
            PopupTeachingTip.create(
                target=self.convert_button,
                icon=InfoBarIcon.ERROR,
                title='ERROR',
                content=f"Please specify an output {str(self.output_format).upper()} file.",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,  
                duration=2000,
                parent=self
            )
            return
            
        if not os.path.exists(self.input_path):
            PopupTeachingTip.create(
                target=self.convert_button,
                icon=InfoBarIcon.ERROR,
                title='ERROR',
                content=f"Input file does not exist.",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        self.converting = True
        self.convert_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress_label.setText("Starting conversion...")
        
        self._worker = ConversionWorker(
            self.input_path, self.output_path, self.output_format,
            self.min_size, # Always pass integer values
            self.max_size,  # Always pass integer values
            self.quality  # Pass image quality parameter
        )
        self._thread = QThread() 
        self._worker.moveToThread(self._thread)
        
        self._worker.finished.connect(self.on_conversion_finished)
        self._worker.progress_updated.connect(self.update_progress)
        self._worker.conversion_error.connect(self.on_conversion_error)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def on_conversion_finished(self):
        self.converting = False
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        
        # Add to history if remember_path is enabled
        if self.remember_path:
            self.add_to_history(self.input_path, self.output_path, str(self.output_format))
        
        # Show top success notification
        InfoBar.success(
            title='Conversion Successful',
            content=f"Your {str(self.output_format).upper()} file has been created successfully!",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # Auto-open file if auto_preview is enabled
        if self.auto_preview:
            self.on_open_converted_file()
        
        # Show completion notification based on settings
        if self.completion_notify:
            self.show_success_view()
        else:
            # If completion notification is disabled, just show a simple status message
            self.convert_button.setEnabled(True)
            self.progress.setValue(100)
            self.progress_label.setText("Conversion completed successfully!")
            self.status_bar.showMessage(f"Conversion completed: {os.path.basename(self.output_path)}")
        
        # Auto-reset after conversion completion
        self._reset_after_conversion()
        
    def _reset_after_conversion(self):
        """Reset conversion state after completion to prepare for next conversion"""
        # Only reset variables if remember_path is disabled
        if not self.remember_path:
            # Reset all variables when remember_path is disabled
            self.init_variables(reset_all=True)
            
            # Reset UI elements
            if hasattr(self, 'input_text'):
                self.input_text.clear()
            if hasattr(self, 'output_text'):
                self.output_text.clear()
            if hasattr(self, 'info_text'):
                self.info_text.setText("No image selected")
            if hasattr(self, 'preview_tab'):
                self.preview_tab.clear_previews()  # Clear previews when returning to main view
    
    def on_conversion_error(self, error_message):
        self.converting = False
        self.convert_button.setEnabled(True)
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        PopupTeachingTip.create(
            target=self.convert_button,
            icon=InfoBarIcon.ERROR,
            title='ERROR',
            content=f"Conversion Failed,{error_message}",
            isClosable=True,
            tailPosition=TeachingTipTailPosition.TOP,
            duration=2000,
            parent=self
        )
        self.progress_label.setText("Conversion Failed")

    # Batch conversion callback methods
    def on_batch_files_dropped(self, file_paths):
        """Handle multiple files dropped in the batch converter"""
        # Filter only supported image files
        supported_formats = ('.png', '.jpg', '.jpeg', '.webp', '.ico', '.tiff', '.tif', '.icns', '.bmp', '.gif', '.svg', '.heic', '.heif', '.avif', '.jxl', '.pdf', '.eps', '.dds', '.exr')
        new_files = []
        
        for file_path in file_paths:
            if os.path.splitext(file_path.lower())[1] in supported_formats:
                new_files.append(file_path)
        
        if new_files:
            self.batch_files.extend(new_files)
            self.update_batch_file_list()
            # Update preview tab with multiple previews
            self.preview_tab.show_multiple_previews(new_files)
            self.update_batch_statistics()
            
    def on_batch_folder_dropped(self, folder_path):
        """Handle folder dropped in the batch converter"""
        # Scan folder for supported image files
        supported_formats = ('.png', '.jpg', '.jpeg', '.webp', '.ico', '.tiff', '.tif', '.icns', '.bmp', '.gif', '.svg', '.heic', '.heif', '.avif', '.jxl', '.pdf', '.eps', '.dds', '.exr')
        found_files = []
        
        try:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in supported_formats):
                        file_path = os.path.join(root, file)
                        found_files.append(file_path)
        except Exception as e:
            PopupTeachingTip.create(
                target=self.drop_zone,
                icon=InfoBarIcon.ERROR,
                title='ERROR',
                content=f"Cannot scan folder: {str(e)}",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        if found_files:
            self.batch_files.extend(found_files)
            self.update_batch_file_list()
            # Update preview tab with multiple previews from folder
            self.preview_tab.show_multiple_previews(found_files)
            self.update_batch_statistics()
            
            PopupTeachingTip.create(
                target=self.drop_zone,
                icon=InfoBarIcon.SUCCESS,
                title='SUCCESS',
                content=f"Added {len(found_files)} files from folder: {os.path.basename(folder_path)}",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            PopupTeachingTip.create(
                target=self.drop_zone,
                icon=InfoBarIcon.WARNING,
                title='WARNING',
                content="No supported image files found in the folder",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=3000,
                parent=self
            )
            
    def update_batch_file_list(self):
        """Update the file list widget with current batch files"""
        self.file_list_widget.clear()
        for file_path in self.batch_files:
            item = QListWidgetItem(os.path.basename(file_path))
            item.setToolTip(file_path)
            self.file_list_widget.addItem(item)
            
    def update_batch_statistics(self):
        """Update batch conversion statistics"""
        total_count = len(self.batch_files)
        self.total_count_label.setText(f"Total: {total_count}")
        
    def clear_batch_files(self):
        """Clear all batch files"""
        self.batch_files.clear()
        self.update_batch_file_list()
        # Clear preview tab
        self.preview_tab.clear_previews()
        self.update_batch_statistics()
        self.clear_batch_results()
        
    def remove_selected_files(self):
        """Remove selected files from batch"""
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items:
            return
            
        # Get indices of selected items
        indices = []
        for item in selected_items:
            indices.append(self.file_list_widget.row(item))
        
        # Sort indices in descending order to remove from end
        indices.sort(reverse=True)
        
        # Remove files from batch_files list
        for index in indices:
            if 0 <= index < len(self.batch_files):
                del self.batch_files[index]
                
        self.update_batch_file_list()
        # Update preview tab with remaining files
        self.preview_tab.show_multiple_previews(self.batch_files)
        self.update_batch_statistics()
        
    def start_batch_conversion(self):
        """Start batch conversion process"""
        if not self.batch_files:
            PopupTeachingTip.create(
                target=self.start_batch_btn,
                icon=InfoBarIcon.WARNING,
                title='WARNING',
                content="Please select files to convert",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # Get current conversion options
        options = self._get_batch_conversion_options()
        if not options:
            return
            
        # Start batch conversion in background thread
        self.batch_converting = True
        self.start_batch_btn.setEnabled(False)
        self.stop_batch_btn.setEnabled(True)
        
        # Reset progress and results
        self.batch_progress.setValue(0)
        self.current_file_progress.setValue(0)
        self.clear_batch_results()
        
        # Start batch conversion thread
        self.batch_thread = QThread()
        self.batch_worker = BatchConversionWorker(
            self.batch_files,
            self.get_batch_output_directory(),
            options['output_format'],
            min_size_param=options['min_size'],
            max_size_param=options['max_size'],
            quality_param=options['quality'],
            preserve_folder_structure=options['preserve_folder_structure'],
            prefix=options['prefix'],
            suffix=options['suffix']
        )
        self.batch_worker.moveToThread(self.batch_thread)
        
        # Connect signals
        self.batch_worker.total_progress_updated.connect(self.on_batch_progress)
        self.batch_worker.progress_updated.connect(self.on_batch_file_progress)
        self.batch_worker.file_processed.connect(self.on_batch_file_processed)
        self.batch_worker.finished.connect(self.on_batch_finished)
        self.batch_worker.batch_error.connect(self.on_batch_error)
        
        # Start the thread
        self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_thread.start()
        
    def stop_batch_conversion(self):
        """Stop batch conversion process"""
        if hasattr(self, 'batch_worker') and self.batch_converting:
            self.batch_worker.cancel()
            self.on_batch_stopped()
            
    def on_batch_stopped(self):
        """Handle batch conversion stopped"""
        self.batch_converting = False
        self.start_batch_btn.setEnabled(True)
        self.stop_batch_btn.setEnabled(False)
        self.batch_progress_label.setText("Stopped")
        self.current_file_label.setText("No file processing")
        
        # Clean up thread
        if hasattr(self, 'batch_thread') and self.batch_thread.isRunning():
            self.batch_thread.quit()
            self.batch_thread.wait()
            
    def on_batch_progress(self, overall_progress, message=None):
        """Update batch overall progress"""
        self.batch_progress.setValue(overall_progress)
        if message:
            self.batch_progress_label.setText(message)
        else:
            self.batch_progress_label.setText(f"Overall progress: {overall_progress}%")
        
    def on_batch_file_progress(self, current_index, total_count, current_file, percentage):
        """Update current file progress"""
        self.current_file_progress.setValue(percentage)
        self.current_file_label.setText(f"Processing {current_file} ({current_index}/{total_count})")
        
    def on_batch_file_processed(self, filename, success, error_message):
        """Handle individual file processing result"""
        if success:
            item_text = f"✓ {filename}"
            item = QListWidgetItem(item_text)
            item.setForeground(Qt.green)
        else:
            item_text = f"✗ {filename}: {error_message}"
            item = QListWidgetItem(item_text)
            item.setForeground(Qt.red)
        
        self.results_list_widget.addItem(item)
        
    def on_batch_finished(self):
        """Handle batch conversion finished"""
        self.batch_converting = False
        self.start_batch_btn.setEnabled(True)
        self.stop_batch_btn.setEnabled(False)
        
        # Clean up thread
        if hasattr(self, 'batch_thread') and self.batch_thread.isRunning():
            self.batch_thread.quit()
            self.batch_thread.wait()
            
        # Get statistics from results list
        success_count = 0
        failed_count = 0
        
        for i in range(self.results_list_widget.count()):
            item = self.results_list_widget.item(i)
            if item:
                if "✓" in item.text():
                    success_count += 1
                else:
                    failed_count += 1
        
        self.success_count_label.setText(f"Success: {success_count}")
        self.failed_count_label.setText(f"Failed: {failed_count}")
        
        # Update statistics label
        total_files = success_count + failed_count
        self.batch_progress_label.setText(f"Completed: {total_files} files")
            
        # Get output directory path
        output_dir = self.get_batch_output_directory()
            
        # Show batch success view (even if there were some failures, we still show the results)
        self.show_batch_success_view(
            total_files=total_files,
            success_count=success_count,
            failed_count=failed_count,
            output_dir=output_dir,
            format_name=self.batch_format_combo.currentText()
        )
        
        # Auto-reset after batch conversion completion
        self._reset_batch_after_conversion()
            
    def _reset_batch_after_conversion(self):
        """Reset batch conversion state after completion to prepare for next conversion"""
        # Clear file list and results
        self.clear_batch_files()
        self.clear_batch_results()
        
        # Reset progress bars
        self.batch_progress.setValue(0)
        self.current_file_progress.setValue(0)
        self.batch_progress_label.setText("Ready for new conversion")
        self.current_file_label.setText("No file processing")
        
        # Clear preview tab
        if hasattr(self, 'preview_tab'):
            self.preview_tab.clear_previews()
    
    def on_batch_error(self, error_message):
        """Handle batch conversion error"""
        self.batch_converting = False
        self.start_batch_btn.setEnabled(True)
        self.stop_batch_btn.setEnabled(False)
        
        PopupTeachingTip.create(
            target=self.start_batch_btn,
            icon=InfoBarIcon.ERROR,
            title='ERROR',
            content=f"Batch conversion failed: {error_message}",
            isClosable=True,
            tailPosition=TeachingTipTailPosition.TOP,
            duration=5000,
            parent=self
        )
        
        # Clean up thread
        if hasattr(self, 'batch_thread') and self.batch_thread.isRunning():
            self.batch_thread.quit()
            self.batch_thread.wait()
            
    def clear_batch_results(self):
        """Clear batch conversion results"""
        self.results_list_widget.clear()
        self.success_count_label.setText("Success: 0")
        self.failed_count_label.setText("Failed: 0")
        
    def _get_batch_conversion_options(self):
        """Get conversion options from batch options tree (same structure as single conversion)"""
        try:
            options = {
                'output_format': self.batch_format_combo.currentText(),
                'min_size': self.batch_min_spin.value(),
                'max_size': self.batch_max_spin.value(),
                'use_auto_detect': getattr(self, 'batch_use_auto_detect', False),
                'keep_aspect_ratio': self.batch_keep_aspect_check.isChecked(),
                'auto_crop': self.batch_auto_crop_check.isChecked(),
                'quality': self.batch_quality_slider.value(),
                'icns_method': self.batch_icns_method_combo.currentText(),
                'overwrite_confirm': self.batch_overwrite_confirm_check.isChecked(),
                'preserve_folder_structure': self.batch_preserve_folder_check.isChecked() if hasattr(self, 'batch_preserve_folder_check') else False,
                'prefix': self.batch_prefix_edit.text().strip() if hasattr(self, 'batch_prefix_edit') else "",
                'suffix': self.batch_suffix_edit.text().strip() if hasattr(self, 'batch_suffix_edit') else ""
            }
            return options
        except Exception as e:
            PopupTeachingTip.create(
                target=self.batch_options_tree,
                icon=InfoBarIcon.ERROR,
                title='ERROR',
                content=f"Invalid conversion options: {str(e)}",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=3000,
                parent=self
            )
            return None
            
    def get_output_directory(self):
        """Get output directory for batch conversion"""
        if hasattr(self, 'output_text') and self.output_text.text():
            return self.output_text.text()
        else:
            # Default to current directory if no output path set
            return os.path.dirname(self.input_text.text()) if hasattr(self, 'input_text') and self.input_text.text() else os.getcwd()

    def get_batch_output_directory(self):
        """Get output directory for batch conversion"""
        if hasattr(self, 'batch_output_text') and self.batch_output_text.text():
            return self.batch_output_text.text()
        elif hasattr(self, 'output_text') and self.output_text.text():
            # Fall back to single conversion output directory
            return self.output_text.text()
        else:
            # Default to current directory if no output path set
            return os.getcwd()

    def show_success_view(self):
        # Update the success widget geometry to match the window
        self.success_widget.setGeometry(self.rect())
        # Show the success widget as an overlay
        self.success_widget.show()
        self.success_widget.raise_()  # Bring to front
        # Update success message based on current output format
        msg_label = self.success_widget.findChild(QLabel, "success_message_label")
        if msg_label:
            msg_label.setText(f"Your {str(self.output_format).upper()} file has been created successfully!")
        # Apply theme-specific styles
        self._apply_success_theme()


    def on_open_converted_file(self):
        if self.output_path and os.path.exists(self.output_path):
            try:
                if sys.platform == "win32":
                    os.startfile(self.output_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", self.output_path])
                else:  # Linux and other POSIX systems
                    subprocess.run(["xdg-open", self.output_path])
            except Exception as e:
                PopupTeachingTip.create(
                    target=self.convert_button,
                    icon=InfoBarIcon.ERROR,
                    title='ERROR',
                    content=f"Conversion Failed:\n,{e}",
                    isClosable=True,
                    tailPosition=TeachingTipTailPosition.TOP,
                    duration=2000,
                    parent=self
                )
        else:
           
            PopupTeachingTip.create(
                target=self.convert_button,
                icon=InfoBarIcon.ERROR,
                title='ERROR',
                content=f"Conversion Failed: Cannot find the converted file.",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=2000,
                parent=self
            )

    def show_main_view(self):
        # Hide the success widget if it's shown
        if hasattr(self, 'success_widget'):
            self.success_widget.hide()
        
        # Hide the batch success widget if it's shown
        if hasattr(self, 'batch_success_widget'):
            self.batch_success_widget.hide()
        
        # Reset conversion state when returning to main view
        self._reset_after_conversion()
        
        # Always reset these UI elements regardless of remember_path setting
        if hasattr(self, 'min_spin'):
            self.min_spin.setValue(16)
        if hasattr(self, 'max_spin'):
            self.max_spin.setValue(1024)
        if hasattr(self, 'format_combo'):
            self.format_combo.setCurrentText("icns")
        # Reset tree state
        if hasattr(self, 'options_tree'):
            self.options_tree.collapseAll()
            # Expand basic categories but keep advanced collapsed
            if self.options_tree.topLevelItemCount() >= 3:
                item0 = self.options_tree.topLevelItem(0)
                item1 = self.options_tree.topLevelItem(1)
                item2 = self.options_tree.topLevelItem(2)
                if item0:
                    item0.setExpanded(True)  # Basic Options
                if item1:
                    item1.setExpanded(True)  # Image Processing
                if item2:
                    item2.setExpanded(False)  # Advanced Settings
        # The on_format_change also handles enabling/disabling min/max spin boxes and auto-detect button
        if hasattr(self, 'format_combo'):
            self.on_format_change(self.format_combo.currentIndex()) # Explicitly call to set initial state
        if hasattr(self, 'progress'):
            self.progress.setValue(0)
        if hasattr(self, 'progress_label'):
            self.progress_label.setText("Ready")
        if hasattr(self, 'convert_button'):
            self.convert_button.setEnabled(True)
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage("Ready")
        
        # Only update history tab visibility if it's the first time or remember_path setting changed
        if not hasattr(self, '_history_tab_initialized'):
            self.create_history_tab()
            self._history_tab_initialized = True

            
    def update_progress(self, message, percentage):
        self.progress_label.setText(message)
        self.progress.setValue(percentage)

    def center_window(self):
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
    def _apply_success_theme(self):
        """Apply theme-specific styles to success view elements"""
        # Get current theme from CON
        try:
            from support.toggle import CON
            is_dark_mode = CON.theme_system == "dark"
        except:
            # Fallback to system detection if CON is not available
            from PySide6.QtWidgets import QApplication as QApp
            app = QApp.instance()
            from support.toggle import theme_manager
            theme_manager.start()
            if app and hasattr(app, 'palette'):
                is_dark_mode = app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5
            else:
                # Default to light theme if we can't determine
                is_dark_mode = False
        
        # Find all relevant widgets in success view
        title_label = self.success_widget.findChild(QLabel, "success_title_label")
        checkmark_label = self.success_widget.findChild(QLabel, "success_checkmark_label")
        message_label = self.success_widget.findChild(QLabel, "success_message_label")
        
        if is_dark_mode:
            # Dark theme styles
            if title_label:
                title_label.setStyleSheet("color: #28a745; font-size: 24px;")
            if checkmark_label:
                checkmark_label.setStyleSheet("color: #28a745;")
            if message_label:
                message_label.setStyleSheet("color: #aaaaaa; font-size: 16px;")
        else:
            # Light theme styles
            if title_label:
                title_label.setStyleSheet("color: #28a745; font-size: 24px;")
            if checkmark_label:
                checkmark_label.setStyleSheet("color: #28a745;")
            if message_label:
                message_label.setStyleSheet("color: #555555; font-size: 16px;")
        
    def resizeEvent(self, event):
        """Handle window resize events to ensure success overlay covers the entire window"""
        super().resizeEvent(event)
        # Update the success widget geometry when the window is resized
        if hasattr(self, 'success_widget') and self.success_widget:
            self.success_widget.setGeometry(self.rect())
        # Update the batch success widget geometry when the window is resized
        if hasattr(self, 'batch_success_widget') and self.batch_success_widget:
            self.batch_success_widget.setGeometry(self.rect())


class ICNSConverterApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        setTheme(Theme.AUTO)
        from PySide6.QtWidgets import QApplication as QApp
        app = QApp.instance()
        from support.toggle import theme_manager
        theme_manager.start()
        if app and hasattr(app, 'palette'):
            initial_dark_mode = app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5
        else:
            # Default to light theme if we can't determine
            initial_dark_mode = False
        self.window = ICNSConverterGUI(
            initial_dark_mode=initial_dark_mode
        ) # Pass initial dark mode state to GUI
        self.window.show()

        # Connect to palette changes for real-time theme switching
        from PySide6.QtWidgets import QApplication as QApp
        app = QApp.instance()
        if app and hasattr(app, 'paletteChanged'):
            app.paletteChanged.connect(self._on_palette_changed)

    def _on_palette_changed(self):
        from PySide6.QtWidgets import QApplication as QApp
        app = QApp.instance()
        if app and hasattr(app, 'palette'):
            is_dark_mode = app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5
            self.window._apply_theme(is_dark_mode)
            
            # Also update success view theme if it's visible
            if hasattr(self.window, 'success_widget') and self.window.success_widget and self.window.success_widget.isVisible():
                self.window._apply_success_theme()
        else:
            # Fallback to light theme if we can't determine
            self.window._apply_theme(False)
            if hasattr(self.window, 'success_widget') and self.window.success_widget and self.window.success_widget.isVisible():
                self.window._apply_success_theme()
        

    def MainLoop(self):
        app = QApplication.instance()
        if app:
            sys.exit(app.exec())
        else:
            # Fallback exit if app instance is not available
            sys.exit(1)


if __name__ == "__main__":
    app_runner = ICNSConverterApp()
    app_runner.MainLoop()
