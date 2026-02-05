import os
import sys
import subprocess
import shutil
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt, QTimer, QUrl, QObject, QSize, QSettings
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QLineEdit, QTextEdit, QProgressBar,
                               QTabWidget, QWidget, QGroupBox, QListWidget, QListWidgetItem,
                               QFileDialog, QCheckBox, QComboBox, QFrame, QMessageBox, QMenu)
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QPixmap
from UIkit import *

from con import CON
from support.toggle import ThemeManager
from support.GUI.arc_support import (
    BatchDropZoneWidget,
    CreateZipWorker, ExtractZipWorker, AddToZipWorker,
    ListZipContentsWorker, BatchExtractWorker
)

# Add the current directory to Python path to import convertzip module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from support.archive_manager import create_archive, extract_archive, add_to_archive, list_archive_contents, SUPPORTED_ARCHIVE_FORMATS, batch_extract_archives
from support.password_detector import PasswordDetector
from password_dialog import PasswordDialog, SimplePasswordDialog

# Remove the problematic reconfigure calls
# sys.stdout.reconfigure(encoding='utf-8')
# sys.stderr.reconfigure(encoding='utf-8')
# --- Worker Classes are now imported from support.GUI.arc_support ---

class ZipGUI(QMainWindow):

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
    
    def _show_popup(self, target, icon, title, content, duration=2000):
        """Display popup and print message to console"""
        print(f"[{title}] {content}")  # Print message to console
        PopupTeachingTip.create(
            target=target,
            icon=icon,
            title=title,
            content=content,
            isClosable=True,
            tailPosition=TeachingTipTailPosition.TOP,
            duration=duration,
            parent=self
        )
    
    def _show_info_bar(self, title, content, icon=InfoBarIcon.SUCCESS, duration=2000):
        """Display info bar and print message to console"""
        print(f"[{title}] {content}")  # Print message to console
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=self
        )

    @property
    def LIGHT_QSS(self):
        """Load light theme QSS from external file"""
        return self._load_qss_file('zip_light.qss')

    @property
    def DARK_QSS(self):
        """Load dark theme QSS from external file"""
        return self._load_qss_file('zip_dark.qss')

    def __init__(self, initial_dark_mode=False):
        super().__init__()
        self.setWindowTitle("Archive File Processing Tool")
        self.setGeometry(200, 200, 1200, 900)
        self.setMinimumSize(1200, 900)
        
        # Enable drag and drop for the main window
        self.setAcceptDrops(True)
        
        self.themeListener = SystemThemeListener(self)
        self.init_variables()
        
        
        
        
        self.setup_ui()
        self._apply_theme(initial_dark_mode)
        self.center_window() # Center the window after UI setup
        self.qss_combo=CON.qss_combo
        setTheme(Theme.AUTO)
        self.themeListener.start()
        qconfig.themeChanged.connect(self._onThemeChanged)
        
        # Load settings
        self.load_settings()
    
    def closeEvent(self, event):
        """Window close event"""
        # Stop all worker threads
        self._stop_all_workers()

        # Stop listener thread
        if hasattr(self, 'themeListener'):
            self.themeListener.terminate()
            self.themeListener.deleteLater()
        super().closeEvent(event)

    def _stop_all_workers(self):
        """Stop all running worker threads"""
        # Stop create archive worker
        if hasattr(self, 'create_zip_worker') and self.create_zip_worker:
            try:
                self.create_zip_worker.stop()
            except:
                pass
        if hasattr(self, 'create_zip_worker_thread') and self.create_zip_worker_thread:
            try:
                if self.create_zip_worker_thread.isRunning():
                    self.create_zip_worker_thread.quit()
                    self.create_zip_worker_thread.wait(1000)
            except:
                pass

        # Stop extract archive worker
        if hasattr(self, 'extract_zip_worker') and self.extract_zip_worker:
            try:
                self.extract_zip_worker.stop()
            except:
                pass
        if hasattr(self, 'extract_zip_worker_thread') and self.extract_zip_worker_thread:
            try:
                if self.extract_zip_worker_thread.isRunning():
                    self.extract_zip_worker_thread.quit()
                    self.extract_zip_worker_thread.wait(1000)
            except:
                pass

        # Stop add to archive worker
        if hasattr(self, 'add_to_zip_worker') and self.add_to_zip_worker:
            try:
                self.add_to_zip_worker.stop()
            except:
                pass
        if hasattr(self, 'add_to_zip_worker_thread') and self.add_to_zip_worker_thread:
            try:
                if self.add_to_zip_worker_thread.isRunning():
                    self.add_to_zip_worker_thread.quit()
                    self.add_to_zip_worker_thread.wait(1000)
            except:
                pass

        # Stop list contents worker
        if hasattr(self, 'list_zip_worker') and self.list_zip_worker:
            try:
                self.list_zip_worker.stop()
            except:
                pass
        if hasattr(self, 'list_zip_worker_thread') and self.list_zip_worker_thread:
            try:
                if self.list_zip_worker_thread.isRunning():
                    self.list_zip_worker_thread.quit()
                    self.list_zip_worker_thread.wait(1000)
            except:
                pass

        # Stop batch extract worker
        if hasattr(self, 'batch_extract_worker') and self.batch_extract_worker:
            try:
                self.batch_extract_worker.stop()
            except:
                pass
        if hasattr(self, 'batch_extract_worker_thread') and self.batch_extract_worker_thread:
            try:
                if self.batch_extract_worker_thread.isRunning():
                    self.batch_extract_worker_thread.quit()
                    self.batch_extract_worker_thread.wait(1000)
            except:
                pass
    def _onThemeChanged(self, theme: Theme):
        """Theme change handling"""
        # Update interface to respond to theme changes
        is_dark_mode = theme == Theme.DARK
        
        # Update drag and drop area theme
        if hasattr(self, 'batch_drop_area'):
            self.batch_drop_area.set_theme(is_dark_mode)
        
        self.update()
        setTheme(Theme.AUTO)
    def init_variables(self):
        # Variables for Create ZIP tab
        self.create_sources = []
        self.create_output_path = ""
        self.create_archive_format = "zip" # Default to zip
        self.create_zip_worker_thread = None # Renamed to generic for clarity
        self.create_zip_worker = None # Renamed to generic for clarity
        
        # Variables for Extract ZIP tab
        self.extract_zip_path = ""
        self.extract_dest_path = ""
        self.extract_zip_worker_thread = None # Renamed to generic for clarity
        self.extract_zip_worker = None # Renamed to generic for clarity
        
        # Variables for Batch Extract tab
        self.batch_extract_files = []
        self.batch_extract_dest_path = ""
        self.batch_extract_worker = None
        self.batch_extract_worker_thread = None
        self.batch_extract_running = False
        self.batch_extract_success_count = 0
        self.batch_extract_failed_count = 0
        self.batch_extract_password = None
        
        # Variables for Add to ZIP tab
        self.add_zip_path = ""
        self.add_file_path = ""
        self.add_to_zip_worker_thread = None # Renamed to generic for clarity
        self.add_to_zip_worker = None # Renamed to generic for clarity
        
        # Variables for List Contents tab
        self.list_zip_path = ""
        self.list_zip_worker_thread = None # Renamed to generic for clarity
        self.list_zip_worker = None # Renamed to generic for clarity
        
        # Password protection status for archive contents
        self.is_password_protected = False
        self._current_password = None
        self._password_dialog = None

    def request_password(self, archive_path, format_name, is_protected):
        """Request password from user for a protected archive"""
        archive_name = os.path.basename(archive_path)
        title = "Password Required"
        
        if is_protected:
            content = f"The archive '{archive_name}' ({format_name.upper()}) is password protected.\nPlease enter the password:"
        else:
            content = f"Enter password for archive '{archive_name}' ({format_name.upper()}):"
        
        # Create and show password dialog
        self._password_dialog = PasswordDialog(
            parent=self,
            title=title,
            content=content,
            error_message=""
        )
        
        # Show dialog and get result
        if self._password_dialog.exec() == PasswordDialog.DialogCode.Accepted:
            password = self._password_dialog.get_password()
            self._password_dialog = None
            return password
        else:
            # User canceled
            self._password_dialog = None
            return None
    
    
    
    def setup_ui(self):
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)

        # Initialize status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        self.notebook = QTabWidget(self.main_widget)
        self.main_layout.addWidget(self.notebook, 1) # Add notebook with stretch
        
        self.create_create_tab()
        self.create_extract_tab()
        self.create_add_tab()
        self.create_list_tab()
        
        # Connect tab change event
        self.notebook.currentChanged.connect(self.on_tab_changed)
        
        # Add a stretch to the main_layout to push everything to the top
        self.main_layout.addStretch(1)
        
        # Apply custom stylesheets to all buttons after UI creation
        self.apply_custom_styles()

    def _apply_theme(self, is_dark_mode):
        if is_dark_mode:
            self.setStyleSheet(self.DARK_QSS)
        else:
            self.setStyleSheet(self.LIGHT_QSS)
            
        # Update drag and drop area theme
        if hasattr(self, 'batch_drop_area'):
            self.batch_drop_area.set_theme(is_dark_mode)

    def _apply_system_theme(self, is_dark_mode):
        self._apply_theme(is_dark_mode)
    
    def load_settings(self):
        """Load settings from QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Load task mode setting
        self.task_mode = settings.value("task_mode", False, type=bool)
    
    def save_settings(self):
        """Save settings to QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Task mode setting removed - now controlled globally
        
        settings.sync()

    def center_window(self):
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
    def apply_custom_styles(self):
        """Apply custom stylesheets to all buttons after UI creation"""
        try:
            # Find all PushButton and PrimaryPushButton widgets and apply custom styles
            for button in self.findChildren(PushButton):
                setCustomStyleSheet(button, CON.qss, CON.qss)
            for button in self.findChildren(PrimaryPushButton):
                setCustomStyleSheet(button, CON.qss, CON.qss)
        except Exception as e:
            print(f"Warning: Could not apply custom stylesheets: {e}")

    # --- Tab creation methods (to be implemented with PySide6 widgets) ---
    def create_create_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        self.notebook.addTab(tab_panel, "Create Archive") # Changed tab title

        # Output file selection with ScrollArea inside GroupBox
        output_box = QGroupBox("Output Archive File") # Changed group box title
        output_box.setMinimumHeight(200)  # Set minimum height
        output_box_sizer = QVBoxLayout(output_box)
        
        # Create ScrollArea inside GroupBox
        output_scroll_area = ScrollArea()
        output_scroll_area.setWidgetResizable(True)
        output_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        output_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        
        self.create_output_text = LineEdit()
        setCustomStyleSheet(self.create_output_text, CON.qss_line, CON.qss_line)
        # self.create_output_text.setReadOnly(True)  # Allow users to manually input path
        content_layout.addWidget(self.create_output_text, 1)
        output_button = PushButton("Browse...")
        output_button.clicked.connect(self.browse_create_output)
        content_layout.addWidget(output_button)
        
        # Set content widget to ScrollArea
        output_scroll_area.setWidget(content_widget)
        
        # Add ScrollArea to GroupBox layout
        output_box_sizer.addWidget(output_scroll_area)
        
        # Add GroupBox to main layout
        tab_sizer.addWidget(output_box)

        # Archive Format Selection (new)
        format_layout = QHBoxLayout()
        format_label = QLabel("Archive Format:")
        self.create_format_combo = ModelComboBox()
        # Filter formats to only allow creation of supported types
        creation_formats = []
        for fmt in SUPPORTED_ARCHIVE_FORMATS:
            if fmt != 'tgz':
                creation_formats.append(fmt.upper())
        
        self.create_format_combo.addItems(creation_formats)
        self.create_format_combo.setCurrentText("ZIP")
        setCustomStyleSheet(self.create_format_combo, CON.qss_combo, CON.qss_combo)
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.create_format_combo, 1)
        tab_sizer.addLayout(format_layout)

        # Source files list with ScrollArea inside GroupBox
        sources_box = QGroupBox("Source Files/Directories")
        sources_box.setMinimumHeight(200)  # Set minimum height
        sources_box_sizer = QVBoxLayout(sources_box)
        
        # Create ScrollArea inside GroupBox
        sources_scroll_area = ScrollArea()
        sources_scroll_area.setWidgetResizable(True)
        sources_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sources_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        self.sources_listbox = ListWidget()
        self.sources_listbox.setMinimumHeight(280)  # Set minimum height
        content_layout.addWidget(self.sources_listbox, 1)  # Increase stretch weight
        # Set right-click to immediately select
        self.sources_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Context menu functionality removed
        # self.sources_listbox.customContextMenuRequested.connect(self.show_sources_context_menu)
        
        # Buttons to add/remove sources
        button_sizer = QHBoxLayout()
        add_files_button = PushButton("Add Files...")
        add_files_button.clicked.connect(self.add_source_files)
        button_sizer.addWidget(add_files_button)
        
        add_folder_button = PushButton("Add Folder...")
        add_folder_button.clicked.connect(self.add_source_folder)
        button_sizer.addWidget(add_folder_button)
        
        remove_button = PushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_source)
        button_sizer.addWidget(remove_button)
        button_sizer.addStretch(1) # Push buttons to left
        
        content_layout.addLayout(button_sizer)
        
        # Set content widget to ScrollArea
        sources_scroll_area.setWidget(content_widget)
        
        # Add ScrollArea to GroupBox layout
        sources_box_sizer.addWidget(sources_scroll_area)
        
        # Add GroupBox to main layout
        tab_sizer.addWidget(sources_box, 1) # Give sources box more stretch

        # Task mode control removed - now controlled globally
        
        # Progress bar
        self.create_progress_label = QLabel("")
        tab_sizer.addWidget(self.create_progress_label)
        
        self.create_progress = ProgressBar()
        self.create_progress.setRange(0, 100)
        self.create_progress.setValue(0)
        tab_sizer.addWidget(self.create_progress)

        # Create button layout with cancel button
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Create button
        self.create_button = PrimaryPushButton("Create Archive") # Changed button text
        self.create_button.clicked.connect(self.start_create_archive) # Changed signal
        button_layout.addWidget(self.create_button)
        
        # Cancel button
        self.create_cancel_button = PushButton("Cancel")
        self.create_cancel_button.clicked.connect(self.cancel_create_archive)
        self.create_cancel_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.create_cancel_button)
        
        # Create a container widget to center the button layout
        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.addStretch()
        button_container_layout.addLayout(button_layout)
        button_container_layout.addStretch()
        tab_sizer.addWidget(button_container)
        
        tab_sizer.addStretch(1) # Push content to top

    def create_extract_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        self.notebook.addTab(tab_panel, "Extract Archive") # Changed tab title

        # Tab selector for single/batch extract
        self.extract_tab_widget = QTabWidget()
        tab_sizer.addWidget(self.extract_tab_widget)

        # Single Extract Tab
        self.create_single_extract_tab()
        
        # Batch Extract Tab  
        self.create_batch_extract_tab()
        
        tab_sizer.addStretch(1) # Push content to top

    def create_single_extract_tab(self):
        """Create single archive extraction tab"""
        single_panel = QWidget()
        single_sizer = QVBoxLayout(single_panel)

        # Archive file selection with ScrollArea inside GroupBox (changed title)
        zip_box = QGroupBox("Archive File to Extract")
        zip_box.setMinimumHeight(200)  # Set minimum height
        zip_box_sizer = QVBoxLayout(zip_box)

        # Create ScrollArea inside GroupBox
        zip_scroll_area = ScrollArea()
        zip_scroll_area.setWidgetResizable(True)
        zip_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        zip_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        
        self.extract_zip_text = LineEdit()
        setCustomStyleSheet(self.extract_zip_text, CON.qss_line, CON.qss_line)
        # self.extract_zip_text.setReadOnly(True)  # Allow users to manually input path
        content_layout.addWidget(self.extract_zip_text, 1)
        zip_button = PushButton("Browse...")
        zip_button.clicked.connect(self.browse_extract_archive) # Changed signal
        content_layout.addWidget(zip_button)
        
        # Set content widget to ScrollArea
        zip_scroll_area.setWidget(content_widget)
        
        # Add ScrollArea to GroupBox layout
        zip_box_sizer.addWidget(zip_scroll_area)
        
        # Add GroupBox to main layout
        single_sizer.addWidget(zip_box)

        # Destination folder selection with ScrollArea inside GroupBox
        dest_box = QGroupBox("Destination Folder")
        dest_box.setMinimumHeight(200)  # Set minimum height
        dest_box_sizer = QVBoxLayout(dest_box)

        # Create ScrollArea inside GroupBox
        dest_scroll_area = ScrollArea()
        dest_scroll_area.setWidgetResizable(True)
        dest_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        dest_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        
        self.extract_dest_text = LineEdit()
        setCustomStyleSheet(self.extract_dest_text, CON.qss_line, CON.qss_line)
        # self.extract_dest_text.setReadOnly(True)  # Allow users to manually input path
        content_layout.addWidget(self.extract_dest_text, 1)
        dest_button = PushButton("Browse...")
        dest_button.clicked.connect(self.browse_extract_dest)
        content_layout.addWidget(dest_button)
        
        # Set content widget to ScrollArea
        dest_scroll_area.setWidget(content_widget)
        
        # Add ScrollArea to GroupBox layout
        dest_box_sizer.addWidget(dest_scroll_area)
        
        # Add GroupBox to main layout
        single_sizer.addWidget(dest_box)

        # Password status indicator
        password_status_box = QHBoxLayout()
        self.extract_password_status_label = QLabel("Archive Status: Unknown")
        self.extract_password_status_icon = QLabel()
        self.extract_password_status_icon.setFixedSize(16, 16)
        password_status_box.addWidget(self.extract_password_status_label)
        password_status_box.addWidget(self.extract_password_status_icon)
        password_status_box.addStretch()
        single_sizer.addLayout(password_status_box)
        
        # Progress bar
        self.extract_progress_label = QLabel("")
        single_sizer.addWidget(self.extract_progress_label)
        
        self.extract_progress = ProgressBar()
        self.extract_progress.setRange(0, 100)
        self.extract_progress.setValue(0)
        single_sizer.addWidget(self.extract_progress)

        # Extract button layout with cancel button
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Extract button
        self.extract_button = PrimaryPushButton("Extract Archive") # Changed button text
        self.extract_button.clicked.connect(self.start_extract_archive) # Changed signal
        button_layout.addWidget(self.extract_button)
        
        # Cancel button
        self.extract_cancel_button = PushButton("Cancel")
        self.extract_cancel_button.clicked.connect(self.cancel_extract_archive)
        self.extract_cancel_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.extract_cancel_button)
        
        # Create a container widget to center the button layout
        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.addStretch()
        button_container_layout.addLayout(button_layout)
        button_container_layout.addStretch()
        single_sizer.addWidget(button_container)
        
        self.extract_tab_widget.addTab(single_panel, "Single Extract")

    def create_batch_extract_tab(self):
        """Create batch archive extraction tab"""
        batch_panel = QWidget()
        main_layout = QHBoxLayout(batch_panel)
        
        # Left side - File management and selection
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # File selection group with ScrollArea inside GroupBox
        file_group = QGroupBox("Batch Archive Files")
        file_group.setMinimumHeight(200)  # Set minimum height
        file_group_layout = QVBoxLayout(file_group)
        
        # Create ScrollArea inside GroupBox
        file_scroll_area = ScrollArea()
        file_scroll_area.setWidgetResizable(True)
        file_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        file_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        file_content_widget = QWidget()
        file_content_layout = QVBoxLayout(file_content_widget)
        
        # Drag and drop area
        self.batch_drop_area = BatchDropZoneWidget("Drag archive files here\nor click to browse")
        file_content_layout.addWidget(self.batch_drop_area)
        
        # File list
        self.batch_files_listbox = ListWidget()
        self.batch_files_listbox.setMinimumHeight(200)
        self.batch_files_listbox.setMinimumWidth(300)
        file_content_layout.addWidget(self.batch_files_listbox)
        
        # File management buttons
        file_buttons_layout = QHBoxLayout()
        
        self.batch_add_files_btn = PushButton("Add Files")
        self.batch_add_files_btn.setMinimumWidth(80)
        self.batch_add_files_btn.clicked.connect(self.browse_batch_archive_files)
        file_buttons_layout.addWidget(self.batch_add_files_btn)
        
        self.batch_remove_files_btn = PushButton("Remove Selected")
        self.batch_remove_files_btn.setMinimumWidth(100)
        self.batch_remove_files_btn.clicked.connect(self.remove_selected_batch_files)
        file_buttons_layout.addWidget(self.batch_remove_files_btn)
        
        self.batch_clear_files_btn = PushButton("Clear All")
        self.batch_clear_files_btn.setMinimumWidth(80)
        self.batch_clear_files_btn.clicked.connect(self.clear_batch_files)
        file_buttons_layout.addWidget(self.batch_clear_files_btn)
        
        file_buttons_layout.addStretch()
        file_content_layout.addLayout(file_buttons_layout)
        
        # Set content widget to ScrollArea
        file_scroll_area.setWidget(file_content_widget)
        
        # Add ScrollArea to GroupBox layout
        file_group_layout.addWidget(file_scroll_area)
        
        left_layout.addWidget(file_group)
        left_layout.addStretch(1)
        
        # Right side - Configuration and progress
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Destination folder group with ScrollArea inside GroupBox
        dest_group = QGroupBox("Destination Folder")
        dest_group.setMinimumHeight(200)  # Set minimum height
        dest_group_layout = QVBoxLayout(dest_group)
        
        # Create ScrollArea inside GroupBox
        dest_scroll_area = ScrollArea()
        dest_scroll_area.setWidgetResizable(True)
        dest_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        dest_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        dest_content_widget = QWidget()
        dest_content_layout = QVBoxLayout(dest_content_widget)
        
        dest_layout = QHBoxLayout()
        self.batch_extract_dest_text = LineEdit()
        setCustomStyleSheet(self.batch_extract_dest_text, CON.qss_line, CON.qss_line)
        dest_layout.addWidget(self.batch_extract_dest_text, 1)
        
        batch_dest_button = PushButton("Browse...")
        batch_dest_button.setMinimumWidth(70)
        batch_dest_button.clicked.connect(self.browse_batch_extract_dest)
        dest_layout.addWidget(batch_dest_button)
        
        dest_content_layout.addLayout(dest_layout)
        
        # Set content widget to ScrollArea
        dest_scroll_area.setWidget(dest_content_widget)
        
        # Add ScrollArea to GroupBox layout
        dest_group_layout.addWidget(dest_scroll_area)
        
        right_layout.addWidget(dest_group)
        
        # Options group with ScrollArea inside GroupBox
        options_group = QGroupBox("Extract Options")
        options_group.setMinimumHeight(200)  # Set minimum height
        options_group_layout = QVBoxLayout(options_group)
        
        # Create ScrollArea inside GroupBox
        options_scroll_area = ScrollArea()
        options_scroll_area.setWidgetResizable(True)
        options_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        options_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        options_content_widget = QWidget()
        options_content_layout = QVBoxLayout(options_content_widget)
        
        options_layout = QHBoxLayout()
        
        # Left options column
        left_options = QVBoxLayout()
        self.batch_create_subfolders_check = CheckBox("Create subfolder for each archive")
        self.batch_create_subfolders_check.setChecked(True)
        left_options.addWidget(self.batch_create_subfolders_check)
        
        # Overwrite options
        self.batch_overwrite_files_check = CheckBox("Overwrite existing files")
        self.batch_overwrite_files_check.setChecked(False)
        left_options.addWidget(self.batch_overwrite_files_check)
        
        # Skip existing files option
        self.batch_skip_existing_files_check = CheckBox("Skip existing files")
        self.batch_skip_existing_files_check.setChecked(False)
        left_options.addWidget(self.batch_skip_existing_files_check)
        
        # Overwrite strategy options
        self.overwrite_strategy_combo = ModelComboBox()
        self.overwrite_strategy_combo.addItems([
            "Overwrite all",
            "Skip existing",
            "Rename new",
            "Overwrite if newer"
        ])
        self.overwrite_strategy_combo.setMinimumHeight(30)
        setCustomStyleSheet(self.overwrite_strategy_combo, CON.qss_combo_2, CON.qss_combo_2)
        left_options.addWidget(QLabel("Overwrite Strategy:"))
        
        left_options.addWidget(self.overwrite_strategy_combo)
        
        options_layout.addLayout(left_options)
        options_layout.addStretch(1)
        
        options_content_layout.addLayout(options_layout)
        
        # Set content widget to ScrollArea
        options_scroll_area.setWidget(options_content_widget)
        
        # Add ScrollArea to GroupBox layout
        options_group_layout.addWidget(options_scroll_area)
        
        right_layout.addWidget(options_group)
        
        # Progress group with ScrollArea inside GroupBox
        progress_group = QGroupBox("Progress & Statistics")
        progress_group.setMinimumHeight(200)  # Set minimum height
        progress_group_layout = QVBoxLayout(progress_group)
        
        # Create ScrollArea inside GroupBox
        progress_scroll_area = ScrollArea()
        progress_scroll_area.setWidgetResizable(True)
        progress_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        progress_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        progress_content_widget = QWidget()
        progress_content_layout = QVBoxLayout(progress_content_widget)
        
        # Progress label
        self.batch_progress_label = QLabel("Ready to extract archives")
        self.batch_progress_label.setWordWrap(True)
        progress_content_layout.addWidget(self.batch_progress_label)
        
        # Progress bar
        self.batch_progress = ProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        progress_content_layout.addWidget(self.batch_progress)
        
        # Statistics in a grid layout
        stats_widget = QWidget()
        stats_layout = QGridLayout(stats_widget)
        stats_layout.setSpacing(10)
        
        # Statistics labels
        self.batch_total_count_label = QLabel("Total Archives:")
        self.batch_total_count_value = QLabel("0")
        stats_layout.addWidget(self.batch_total_count_label, 0, 0)
        stats_layout.addWidget(self.batch_total_count_value, 0, 1)
        
        self.batch_success_count_label = QLabel("Successful:")
        self.batch_success_count_value = QLabel("0")
        stats_layout.addWidget(self.batch_success_count_label, 1, 0)
        stats_layout.addWidget(self.batch_success_count_value, 1, 1)
        
        self.batch_failed_count_label = QLabel("Failed:")
        self.batch_failed_count_value = QLabel("0")
        stats_layout.addWidget(self.batch_failed_count_label, 2, 0)
        stats_layout.addWidget(self.batch_failed_count_value, 2, 1)
        
        progress_content_layout.addWidget(stats_widget)
        
        # Set content widget to ScrollArea
        progress_scroll_area.setWidget(progress_content_widget)
        
        # Add ScrollArea to GroupBox layout
        progress_group_layout.addWidget(progress_scroll_area)
        
        right_layout.addWidget(progress_group)
        
        # Control buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setSpacing(10)
        
        self.batch_start_btn = PrimaryPushButton("Start Extract")
        self.batch_start_btn.setMinimumWidth(100)
        self.batch_start_btn.clicked.connect(self.start_batch_extract)
        button_layout.addWidget(self.batch_start_btn)
        
        self.batch_stop_btn = PushButton("Stop")
        self.batch_stop_btn.setMinimumWidth(60)
        self.batch_stop_btn.clicked.connect(self.stop_batch_extract)
        self.batch_stop_btn.setEnabled(False)
        button_layout.addWidget(self.batch_stop_btn)
        
        button_layout.addStretch(1)
        right_layout.addWidget(button_widget)
        
        # Add panels to main layout with proportional sizing
        main_layout.addWidget(left_panel, 2)  # 2/4 of width for file management
        main_layout.addWidget(right_panel, 2)  # 2/4 of width for options and progress - equal width for both panels
        
        self.extract_tab_widget.addTab(batch_panel, "Batch Extract")

        # Connect drop area signals
        self.batch_drop_area.files_dropped.connect(self.on_batch_files_dropped)

    def create_add_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        self.notebook.addTab(tab_panel, "Add to Archive") # Changed tab title

        # Existing Archive file selection with ScrollArea inside GroupBox
        zip_box = QGroupBox("Existing Archive File") # Changed group box title
        zip_box.setMinimumHeight(200)  # Set minimum height
        zip_box_sizer = QVBoxLayout(zip_box)
        
        # Create ScrollArea inside GroupBox
        zip_scroll_area = ScrollArea()
        zip_scroll_area.setWidgetResizable(True)
        zip_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        zip_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        zip_content_widget = QWidget()
        zip_content_layout = QHBoxLayout(zip_content_widget)

        self.add_zip_text = LineEdit()
        setCustomStyleSheet(self.add_zip_text, CON.qss_line, CON.qss_line)
        # self.add_zip_text.setReadOnly(True)  # Allow users to manually input path
        zip_content_layout.addWidget(self.add_zip_text, 1)
        zip_button = PushButton("Browse...")

        zip_button.clicked.connect(self.browse_add_archive) # Changed signal
        zip_content_layout.addWidget(zip_button)
        
        # Set content widget to ScrollArea
        zip_scroll_area.setWidget(zip_content_widget)
        
        # Add ScrollArea to GroupBox layout
        zip_box_sizer.addWidget(zip_scroll_area)
        
        tab_sizer.addWidget(zip_box)

        # File to add selection with ScrollArea inside GroupBox
        file_box = QGroupBox("Files to Add")
        file_box.setMinimumHeight(200)  # Set minimum height
        file_box_sizer = QVBoxLayout(file_box)
        
        # Create ScrollArea inside GroupBox
        file_scroll_area = ScrollArea()
        file_scroll_area.setWidgetResizable(True)
        file_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        file_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        file_content_widget = QWidget()
        file_content_layout = QVBoxLayout(file_content_widget)

        # File list for multiple files (always visible)
        self.add_files_listbox = ListWidget()
        self.add_files_listbox.setMinimumHeight(150)
        self.add_files_listbox.setVisible(True)  # Always visible
        file_content_layout.addWidget(self.add_files_listbox)
        
        # Browse button
        file_button = PushButton("Browse...")
        file_button.clicked.connect(self.browse_add_file)
        file_content_layout.addWidget(file_button)
        
        # Set content widget to ScrollArea
        file_scroll_area.setWidget(file_content_widget)
        
        # Add ScrollArea to GroupBox layout
        file_box_sizer.addWidget(file_scroll_area)
        
        tab_sizer.addWidget(file_box)

        # Progress bar
        self.add_progress_label = QLabel("")
        tab_sizer.addWidget(self.add_progress_label)
        
        self.add_progress = ProgressBar()
        self.add_progress.setRange(0, 100)
        self.add_progress.setValue(0)
        tab_sizer.addWidget(self.add_progress)

        # Add button layout with cancel button
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Add button
        self.add_button = PrimaryPushButton("Add to Archive") # Changed button text
        self.add_button.clicked.connect(self.start_add_to_archive) # Changed signal
        button_layout.addWidget(self.add_button)
        
        # Cancel button
        self.add_cancel_button = PushButton("Cancel")
        self.add_cancel_button.clicked.connect(self.cancel_add_to_archive)
        self.add_cancel_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.add_cancel_button)
        
        # Create a container widget to center the button layout
        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.addStretch()
        button_container_layout.addLayout(button_layout)
        button_container_layout.addStretch()
        tab_sizer.addWidget(button_container)
        
        tab_sizer.addStretch(1) # Push content to top

    def create_list_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        self.notebook.addTab(tab_panel, "List Contents")

        # Archive file selection with ScrollArea inside GroupBox (changed title)
        zip_box = QGroupBox("Archive File")
        zip_box.setMinimumHeight(200)  # Set minimum height
        zip_box_sizer = QVBoxLayout(zip_box)
        
        # Create ScrollArea inside GroupBox
        zip_scroll_area = ScrollArea()
        zip_scroll_area.setWidgetResizable(True)
        zip_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        zip_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        zip_content_widget = QWidget()
        zip_content_layout = QHBoxLayout(zip_content_widget)
        
        self.list_zip_text = LineEdit()
        setCustomStyleSheet(self.list_zip_text, CON.qss_line, CON.qss_line)
        # self.list_zip_text.setReadOnly(True)  # Allow users to manually input path
        zip_content_layout.addWidget(self.list_zip_text, 1)
        zip_button = PushButton("Browse...")

        zip_button.clicked.connect(self.browse_list_archive) # Changed signal
        zip_content_layout.addWidget(zip_button)
        
        # Set content widget to ScrollArea
        zip_scroll_area.setWidget(zip_content_widget)
        
        # Add ScrollArea to GroupBox layout
        zip_box_sizer.addWidget(zip_scroll_area)
        
        tab_sizer.addWidget(zip_box)
        
        # Password status indicator
        password_status_box = QHBoxLayout()
        self.password_status_label = QLabel("Archive Status: Unknown")
        self.password_status_icon = QLabel()
        self.password_status_icon.setFixedSize(16, 16)
        password_status_box.addWidget(self.password_status_label)
        password_status_box.addWidget(self.password_status_icon)
        password_status_box.addStretch()
        tab_sizer.addLayout(password_status_box)
        
        # Listbox for contents with ScrollArea inside GroupBox
        contents_box = QGroupBox("Archive Contents") # Changed group box title
        contents_box.setMinimumHeight(200)  # Set minimum height
        contents_box_sizer = QVBoxLayout(contents_box)
        
        # Create ScrollArea inside GroupBox
        contents_scroll_area = ScrollArea()
        contents_scroll_area.setWidgetResizable(True)
        contents_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        contents_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget for ScrollArea
        contents_content_widget = QWidget()
        contents_content_layout = QVBoxLayout(contents_content_widget)

        self.contents_listbox = ListWidget()
        self.contents_listbox.setMinimumHeight(250)  # Set larger minimum height
        self.contents_listbox.setDragEnabled(True)  # Enable drag functionality
        contents_content_layout.addWidget(self.contents_listbox, 3)  # Increase stretch weight
        # Set right-click menu
        self.contents_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Context menu functionality removed
        # self.contents_listbox.customContextMenuRequested.connect(self.show_contents_context_menu)
        
        # Set content widget to ScrollArea
        contents_scroll_area.setWidget(contents_content_widget)
        
        # Add ScrollArea to GroupBox layout
        contents_box_sizer.addWidget(contents_scroll_area)
        
        tab_sizer.addWidget(contents_box, 2) # Give contents group box more stretch

        # List button layout with cancel button
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # List button
        self.list_button = PrimaryPushButton("List Contents")
        self.list_button.clicked.connect(self.start_list_archive_contents) # Changed signal
        button_layout.addWidget(self.list_button)
        
        # Cancel button
        self.list_cancel_button = PushButton("Cancel")
        self.list_cancel_button.clicked.connect(self.cancel_list_archive_contents)
        self.list_cancel_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.list_cancel_button)
        
        # Create a container widget to center the button layout
        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.addStretch()
        button_container_layout.addLayout(button_layout)
        button_container_layout.addStretch()
        tab_sizer.addWidget(button_container)
        
        tab_sizer.addStretch(1) # Push content to top

    # --- Event handlers (converted to PySide6) ---
    def update_password_status(self, is_protected, status_text=None, tab="list"):
        """Update the password status indicator with improved visual feedback
        
        Args:
            is_protected: Whether the archive is password protected
            status_text: Optional custom status text
            tab: Which tab to update ('list' or 'extract')
        """
        # Update the password protection status attribute
        self.is_password_protected = is_protected
        
        # Determine which label and icon to update based on the tab
        if tab == "list":
            status_label = getattr(self, 'password_status_label', None)
            status_icon = getattr(self, 'password_status_icon', None)
        elif tab == "extract":
            status_label = getattr(self, 'extract_password_status_label', None)
            status_icon = getattr(self, 'extract_password_status_icon', None)
        else:
            return  # Invalid tab specified
            
        if not status_label or not status_icon:
            return  # UI elements not available
            
        if is_protected:
            status_label.setText("Archive Status: Password Protected")
            # Set icon to locked - use our new SVG icon
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "lock.svg")
            if os.path.exists(icon_path):
                try:
                    # Use SVG icon with proper scaling
                    pixmap = QPixmap(icon_path)
                    scaled_pixmap = pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    status_icon.setPixmap(scaled_pixmap)
                    # Set a tooltip for additional information
                    status_icon.setToolTip("This archive is password protected")
                except:
                    # Fallback to text indicator if GUI is not available
                    status_icon.setText("🔒")
                    status_icon.setToolTip("This archive is password protected")
            else:
                # Fallback to text indicator if icon not available
                status_icon.setText("🔒")
                status_icon.setToolTip("This archive is password protected")
            
            # Set label style to indicate password protection
            status_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        else:
            if status_text:
                status_label.setText(f"Archive Status: {status_text}")
            else:
                status_label.setText("Archive Status: No Password Protection")
            
            # Set icon to unlocked - use our new SVG icon
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "unlock.svg")
            if os.path.exists(icon_path):
                try:
                    # Use SVG icon with proper scaling
                    pixmap = QPixmap(icon_path)
                    scaled_pixmap = pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    status_icon.setPixmap(scaled_pixmap)
                    # Set a tooltip for additional information
                    status_icon.setToolTip("This archive is not password protected")
                except:
                    # Fallback to text indicator if GUI is not available
                    status_icon.setText("🔓")
                    status_icon.setToolTip("This archive is not password protected")
            else:
                # Fallback to text indicator if icon not available
                status_icon.setText("🔓")
                status_icon.setToolTip("This archive is not password protected")
            
            # Reset label style to normal
            status_label.setStyleSheet("color: #27ae60; font-weight: normal;")
    
    def update_password_status_list(self, is_protected, status_text=None):
        """Convenience method to update password status in the List tab"""
        self.update_password_status(is_protected, status_text, "list")
    
    def update_password_status_extract(self, is_protected, status_text=None):
        """Convenience method to update password status in the Extract tab"""
        self.update_password_status(is_protected, status_text, "extract")
    
    def update_archive_status(self, status_text, is_success=True):
        """Update the archive status indicator with visual feedback
        
        Args:
            status_text: Status text to display
            is_success: Whether the operation was successful
        """
        # Update the create progress label with the status
        if hasattr(self, 'create_progress_label'):
            self.create_progress_label.setText(status_text)
            
            # Set style based on success/failure
            if is_success:
                self.create_progress_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.create_progress_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                
            # Reset style after a delay
            QTimer.singleShot(5000, lambda: self.create_progress_label.setStyleSheet(""))
    
    def _verify_password_strength(self, password):
        """Verify password strength for archive creation
        
        Args:
            password: Password to verify
            
        Returns:
            bool: True if password meets minimum requirements, False otherwise
        """
        if not password:
            return False
        
        # Basic password strength check
        if len(password) < 6:
            return False
        
        # Password is considered valid for archive creation
        # We don't need to verify it against an existing archive since we're creating a new one
        return True
    
    def confirm_cancel(self, operation_name):
        """Show confirmation dialog for canceling an operation
        
        Args:
            operation_name: Name of the operation being canceled
            
        Returns:
            bool: True if user confirmed cancel, False otherwise
        """
        reply = QMessageBox.question(
            self,
            "取消操作",
            f"确定要取消当前的{operation_name}操作吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def log_cancel(self, operation_type):
        """Log a cancel operation
        
        Args:
            operation_type: Type of operation that was canceled
        """
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [CANCEL] {operation_type} operation canceled by user")
    
    def on_tab_changed(self, index):
        """Handle tab change without animation"""
        # Simply store the previous tab index and return
        self._previous_tab_index = index

    
    

    def browse_create_output(self):
        file_dialog = QFileDialog(self)
        selected_format = self.create_archive_format
        # Generate wildcard for creation, excluding formats not supported for creation
        creation_formats = [f.upper() for f in SUPPORTED_ARCHIVE_FORMATS if f != 'tgz']
        wildcard_parts = [f"{fmt} files (*.{fmt.lower()})" for fmt in creation_formats]
        wildcard = ";;".join(wildcard_parts) + ";;All files (*.*)"
        
        file_dialog.setNameFilter(wildcard)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix(selected_format)
        if file_dialog.exec():
            self.create_output_path = file_dialog.selectedFiles()[0]
            if not self.create_output_path.lower().endswith(f".{selected_format}"):
                self.create_output_path += f".{selected_format}"
            self.create_output_text.setText(self.create_output_path)

    def add_source_files(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("All files (*.*)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if file_dialog.exec():
            paths = file_dialog.selectedFiles()
            for path in paths:
                if path not in self.create_sources:
                    self.create_sources.append(path)
                    self.sources_listbox.addItem(path)

    def add_source_folder(self):
        dir_dialog = QFileDialog(self)
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if dir_dialog.exec():
            folder_path = dir_dialog.selectedFiles()[0]
            if folder_path not in self.create_sources:
                self.create_sources.append(folder_path)
                self.sources_listbox.addItem(f"[FOLDER] {folder_path}")

    def remove_source(self):
        """Remove selected source files"""
        if not self.sources_listbox.selectedIndexes():
            self._show_popup(
                target=self.sources_listbox,
                icon=InfoBarIcon.WARNING,
                title='Warning',
                content='Please select items to remove first',
                duration=3000
            )
            return

        # Get selected rows
        selected_rows = sorted(set(index.row() for index in self.sources_listbox.selectedIndexes()), reverse=True)
        
        # Remove from back to front to avoid index changes
        for row in selected_rows:
            self.sources_listbox.takeItem(row)
            if row < len(self.create_sources):
                self.create_sources.pop(row)
        
        # Show removal success message
        self._show_info_bar(
            icon=InfoBarIcon.SUCCESS,
            title='Removal Successful',
            content=f'Removed {len(selected_rows)} items',
            duration=2000
        )

    def update_create_progress(self, message, progress):
        # Update both progress bar and label
        self.create_progress_label.setText(message)
        print(f"[Create Progress] {message}")  # Print progress information to console
        if progress >= 0:
            self.create_progress.setValue(int(progress))

    def start_create_archive(self):
        # Check if output file is specified
        if not self.create_output_path:
            self._show_popup(
                target=self.create_output_text,
                icon=InfoBarIcon.WARNING,
                title='Warning',
                content='Please specify output file path',
                duration=3000
            )
            return

        # Check if source files are added
        if not self.create_sources:
            self._show_popup(
                target=self.sources_listbox,
                icon=InfoBarIcon.WARNING,
                title='Warning',
                content='Please add files or folders to compress',
                duration=3000
            )
            return
        # RAR format is now supported through external rar command
        # No need to show error message

        # Check if password protection is needed
        password = None
        max_password_attempts = 3
        password_attempt = 0
        
        if self.create_archive_format in ['zip', 'rar', '7z']:
            # Ask user if they want to add password protection
            from UIkit import MessageBox, FluentIcon
            box = MessageBox(
                'Password Protection',
                f'Do you want to add password protection to the {self.create_archive_format.upper()} archive?',
                self
            )
            box.yesButton.setText('Yes, add password')
            box.cancelButton.setText('No, create without password')
            
            if box.exec():
                # User wants to add password protection
                while password_attempt < max_password_attempts:
                    password_attempt += 1
                    from password_dialog import get_password
                    
                    prompt_text = f"Enter password for the {self.create_archive_format.upper()} archive:"
                    if password_attempt >=2:
                        prompt_text = f"Password verification failed. Please try again ({password_attempt}/{max_password_attempts}):"
                    
                    password = get_password(self, "Set Password", prompt_text)
                    
                    if not password:
                        # User cancelled password entry
                        self._show_popup(
                            target=self.create_progress,
                            icon=InfoBarIcon.WARNING,
                            title='Cancelled',
                            content='Archive creation cancelled.',
                            duration=2000
                        )
                        return
                    
                    # Verify password by creating a small test archive
                    if self._verify_password_strength(password):
                        # Password is valid, break the loop
                        break
                    else:
                        # Password is too weak or invalid
                        if password_attempt >= max_password_attempts:
                            self._show_popup(
                                target=self.create_progress,
                                icon=InfoBarIcon.ERROR,
                                title='Password Verification Failed',
                                content=f'Failed to verify password after {max_password_attempts} attempts. Archive creation cancelled.',
                                duration=3000
                            )
                            return
                        else:
                            self._show_popup(
                                target=self.create_progress,
                                icon=InfoBarIcon.WARNING,
                                title='Weak Password',
                                content='Please enter a stronger password (at least 6 characters).',
                                duration=2000
                            )
                            password = None  # Reset password to try again

        self.create_progress_label.setText("Starting archive creation...")
        self.create_progress.setValue(0)
        
        # Enable cancel button and disable create button during operation
        self.create_button.setEnabled(False)
        self.create_cancel_button.setEnabled(True)
        
        self.create_zip_worker = CreateZipWorker(self.create_output_path, self.create_sources, self.create_archive_format, password)
        self.create_zip_worker_thread = QThread()
        self.create_zip_worker.moveToThread(self.create_zip_worker_thread)

        self.create_zip_worker.finished.connect(self.on_create_archive_finished)
        self.create_zip_worker.progress_updated.connect(self.update_create_progress)
        self.create_zip_worker.conversion_error.connect(self.on_create_archive_error)
        self.create_zip_worker.canceled.connect(self.on_create_archive_canceled)
        self.create_zip_worker_thread.started.connect(self.create_zip_worker.run)
        self.create_zip_worker_thread.start()

    def on_create_archive_finished(self):
        # 使用强制线程清理方法
        self._force_cleanup_create_thread()

        # Update archive status
        archive_info = f"Archive created successfully: {os.path.basename(self.create_output_path)}"
        if self.create_zip_worker and hasattr(self.create_zip_worker, 'password') and self.create_zip_worker.password:
            archive_info += " (Password Protected)"

        # Show success notifications
        # Show success notification at the top
        self._show_info_bar(
            title='Success',
            content=archive_info,
            duration=2000
        )

        # Update archive status display
        self.update_archive_status(archive_info, True)

    def on_create_archive_error(self, error_message):
        # 使用强制线程清理方法
        self._force_cleanup_create_thread()

        # Update archive status
        archive_info = f"Archive creation failed: {str(error_message)}"

        # Show error notifications
        self._show_popup(
            target=self.create_progress,
            icon=InfoBarIcon.ERROR,
            title='Error',
            content=f'Error creating archive: {str(error_message)}',
            duration=3000
        )
        self.create_progress_label.setText("Archive creation failed.")

        # Update archive status display
        self.update_archive_status(archive_info, False)
    
    def cancel_create_archive(self):
        """Cancel the archive creation process"""
        if self.confirm_cancel("归档创建"):
            self.log_cancel("Create Archive")
            # Stop the worker
            if self.create_zip_worker:
                self.create_zip_worker.stop()
        
    def on_create_archive_canceled(self):
        """Handle archive creation canceled"""
        # 使用强制线程清理方法
        self._force_cleanup_create_thread()
        
        # Reset button states
        self.create_button.setEnabled(True)
        self.create_cancel_button.setEnabled(False)
        
        # Update progress and status
        self.create_progress.setValue(0)
        self.create_progress_label.setText("Archive creation canceled")
        
        # Show cancel notification
        self._show_info_bar(
            title='Canceled',
            content='Archive creation canceled by user',
            duration=2000
        )
        
        # Update archive status display
        self.update_archive_status("Archive creation canceled", False)
    
    def _force_cleanup_create_thread(self):
        """强制清理创建归档的线程，确保完全终止"""
        # Reset button states
        self.create_button.setEnabled(True)
        self.create_cancel_button.setEnabled(False)
        
        if self.create_zip_worker_thread:
            if self.create_zip_worker_thread.isRunning():
                # 先尝试正常退出
                self.create_zip_worker_thread.quit()
                if not self.create_zip_worker_thread.wait(500):  # 等待0.5秒
                    # 如果正常退出失败，强制终止
                    self.create_zip_worker_thread.terminate()
                    if not self.create_zip_worker_thread.wait(500):  # 再等待0.5秒
                        # 如果终止也失败，尝试杀死线程
                        self.create_zip_worker_thread.kill()
                        self.create_zip_worker_thread.wait(500)  # 等待0.5秒
            
            # 删除线程对象
            self.create_zip_worker_thread.deleteLater()
            self.create_zip_worker_thread = None
        
        if self.create_zip_worker:
            # 删除worker对象
            self.create_zip_worker.deleteLater()
            self.create_zip_worker = None


    def browse_extract_archive(self):
        file_dialog = QFileDialog(self)
        wildcard_parts = [f"{fmt.upper()} files (*.{fmt})" for fmt in SUPPORTED_ARCHIVE_FORMATS]
        wildcard = ";;".join(wildcard_parts) + ";;All files (*.*)"
        file_dialog.setNameFilter(wildcard)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if file_dialog.exec():
            self.extract_zip_path = file_dialog.selectedFiles()[0]
            self.extract_zip_text.setText(self.extract_zip_path)
            # Auto-detect password protection using the new PasswordDetector
            try:
                from support.password_detector import password_detector
                detection_result = password_detector.is_password_protected(self.extract_zip_path)
                if detection_result['is_protected']:
                    self.update_password_status_extract(True, f"Password Protected ({detection_result['format']})")
                    self.is_password_protected = True
                else:
                    self.update_password_status_extract(False, f"No Password Protection ({detection_result['format']})")
                    self.is_password_protected = False
            except Exception as e:
                print(f"Warning: Could not detect password protection: {e}")
                self.update_password_status_extract(False, "Archive Selected")
                self.is_password_protected = False
            # Auto-configure output directory to the file's parent directory
            self.auto_set_extract_dest_from_file(self.extract_zip_path)

    def browse_extract_dest(self):
        dir_dialog = QFileDialog(self)
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if dir_dialog.exec():
            self.extract_dest_path = dir_dialog.selectedFiles()[0]
            self.extract_dest_text.setText(self.extract_dest_path)

    def browse_batch_extract_dest(self):
        """Browse for batch extraction destination folder"""
        dir_dialog = QFileDialog(self)
        dir_dialog.setFileMode(QFileDialog.FileMode.Directory)
        dir_dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if dir_dialog.exec():
            self.batch_extract_dest_path = dir_dialog.selectedFiles()[0]
            self.batch_extract_dest_text.setText(self.batch_extract_dest_path)

    def browse_batch_archive_files(self):
        """Browse for archive files to batch extract"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilters([
            "Archive files (*.zip *.rar *.7z *.tar *.gz *.bz2 *.xz *.tar.gz *.tar.bz2 *.tar.xz *.tgz *.tbz2)",
            "All files (*)"
        ])
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            self.add_batch_files(file_paths)

    def add_batch_files(self, file_paths):
        """Add files to batch list"""
        supported_formats = ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2')
        
        for file_path in file_paths:
            # Check if file is a supported archive format
            if os.path.splitext(file_path.lower())[1] in supported_formats:
                # Avoid duplicates
                if file_path not in [self.batch_files_listbox.item(i).toolTip() for i in range(self.batch_files_listbox.count())]:
                    item = QListWidgetItem(os.path.basename(file_path))
                    item.setToolTip(file_path)
                    self.batch_files_listbox.addItem(item)
        
        self.update_batch_stats()

    def remove_selected_batch_files(self):
        """Remove selected files from batch list"""
        selected_items = self.batch_files_listbox.selectedItems()
        if not selected_items:
            return
            
        # Remove items in reverse order to maintain correct indices
        indices = []
        for item in selected_items:
            indices.append(self.batch_files_listbox.row(item))
        
        indices.sort(reverse=True)
        
        for index in indices:
            self.batch_files_listbox.takeItem(index)
        
        self.update_batch_stats()

    def clear_batch_files(self):
        """Clear all files from batch list"""
        self.batch_files_listbox.clear()
        self.update_batch_stats()

    def get_batch_archive_files(self):
        """Get list of all archive files in batch list"""
        file_paths = []
        for i in range(self.batch_files_listbox.count()):
            item = self.batch_files_listbox.item(i)
            file_paths.append(item.toolTip())
        return file_paths

    def on_batch_files_dropped(self, file_paths):
        """Handle files dropped in batch area"""
        self.add_batch_files(file_paths)

    def update_batch_stats(self):
        """Update batch statistics display"""
        total_count = self.batch_files_listbox.count()
        self.batch_total_count_label.setText(f"Total: {total_count}")
        self.batch_success_count_label.setText("Success: 0")
        self.batch_failed_count_label.setText("Failed: 0")

    def start_batch_extract(self):
        """Start batch extraction process"""
        file_paths = self.get_batch_archive_files()
        
        if not file_paths:
            self._show_popup(
                target=self.batch_start_btn,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please add archive files to extract',
                duration=2000
            )
            return

        if not self.batch_extract_dest_path:
            self._show_popup(
                target=self.batch_extract_dest_text,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please specify the extraction destination folder',
                duration=2000
            )
            return

        # Validate destination folder
        if not os.path.exists(self.batch_extract_dest_path):
            try:
                os.makedirs(self.batch_extract_dest_path, exist_ok=True)
            except Exception as e:
                self._show_popup(
                    target=self.batch_start_btn,
                    icon=InfoBarIcon.ERROR,
                    title='Error',
                    content=f'Failed to create destination folder: {str(e)}',
                    duration=2000
                )
                return

        # Create batch extract options
        create_subfolders = self.batch_create_subfolders_check.isChecked()
        
        # Get overwrite strategy
        overwrite_strategy = self.overwrite_strategy_combo.currentText()
        
        # Determine overwrite behavior based on strategy
        if overwrite_strategy == "Overwrite all":
            overwrite_files = True
            skip_existing = False
        elif overwrite_strategy == "Skip existing":
            overwrite_files = False
            skip_existing = True
        elif overwrite_strategy == "Rename new":
            overwrite_files = False
            skip_existing = False
            # Note: Rename new functionality would need to be implemented in the archive_manager
        elif overwrite_strategy == "Overwrite if newer":
            overwrite_files = True
            skip_existing = False
            # Note: Overwrite if newer functionality would need to be implemented in the archive_manager
        else:
            # Default behavior
            overwrite_files = self.batch_overwrite_files_check.isChecked()
            skip_existing = self.batch_skip_existing_files_check.isChecked()
        
        # Reset progress and statistics
        self.batch_progress.setValue(0)
        self.update_batch_stats()
        self.batch_progress_label.setText("Preparing for batch extraction...")
        
        # Disable start button and enable stop button
        self.batch_start_btn.setEnabled(False)
        self.batch_stop_btn.setEnabled(True)
        
        # Create and start batch worker
        self.batch_extract_worker = BatchExtractWorker(
            file_paths, 
            self.batch_extract_dest_path, 
            create_subfolders, 
            overwrite_files,
            parent_gui=self  # Pass reference to main GUI for password dialogs
        )
        self.batch_extract_worker_thread = QThread()
        self.batch_extract_worker.moveToThread(self.batch_extract_worker_thread)
        
        # Connect signals
        self.batch_extract_worker.finished.connect(self.on_batch_extract_finished)
        self.batch_extract_worker.progress_updated.connect(self.on_batch_extract_progress)
        self.batch_extract_worker.conversion_error.connect(self.on_batch_extract_error)
        self.batch_extract_worker.individual_progress.connect(self.on_batch_individual_progress)
        self.batch_extract_worker.status_updated.connect(self.on_batch_status_updated)
        self.batch_extract_worker_thread.started.connect(self.batch_extract_worker.run)
        self.batch_extract_worker_thread.start()

    def stop_batch_extract(self):
        """Stop batch extraction process"""
        if hasattr(self, 'batch_extract_worker'):
            self.batch_extract_worker.stop()
            self.batch_progress_label.setText("Stopping batch extraction...")
            # Disable stop button to prevent multiple stops
            self.batch_stop_btn.setEnabled(False)
            # Start a timer to check if thread has stopped after a timeout
            QTimer.singleShot(2000, self._check_batch_thread_status)
        
    def _check_batch_thread_status(self):
        """Check if batch thread has stopped after timeout"""
        if hasattr(self, 'batch_extract_worker_thread') and self.batch_extract_worker_thread.isRunning():
            # Thread is still running, try to force stop
            self.batch_progress_label.setText("Force stopping batch extraction...")
            self._force_stop_batch_thread()
            self.on_batch_extract_stopped()
        
    def _force_stop_batch_thread(self):
        """Force stop batch extraction thread"""
        if hasattr(self, 'batch_extract_worker_thread') and self.batch_extract_worker_thread.isRunning():
            try:
                # Try to quit gracefully first
                self.batch_extract_worker_thread.quit()
                if not self.batch_extract_worker_thread.wait(1000):  # Wait 1 second
                    # If graceful quit fails, terminate
                    self.batch_extract_worker_thread.terminate()
                    self.batch_extract_worker_thread.wait(1000)  # Wait another second
            except Exception as e:
                print(f"Error stopping batch thread: {str(e)}")
        
    def on_batch_extract_stopped(self):
        """Handle batch extraction stopped by user"""
        self.batch_progress_label.setText("Batch extraction stopped by user")
        self._cleanup_batch_thread()
        # Update UI
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)
        
    def _cleanup_batch_thread(self):
        """Clean up batch extraction thread and worker resources"""
        # Clean up worker thread
        if hasattr(self, 'batch_extract_worker_thread'):
            if self.batch_extract_worker_thread.isRunning():
                try:
                    self.batch_extract_worker_thread.quit()
                    self.batch_extract_worker_thread.wait(1000)
                except Exception as e:
                    print(f"Error cleaning up batch thread: {str(e)}")
            
            # Delete thread object
            self.batch_extract_worker_thread.deleteLater()
            delattr(self, 'batch_extract_worker_thread')
        
        # Clean up worker
        if hasattr(self, 'batch_extract_worker'):
            # Delete worker object
            self.batch_extract_worker.deleteLater()
            delattr(self, 'batch_extract_worker')

    def on_batch_extract_progress(self, processed_count, total_count, current_file, success_count, failed_count):
        """Handle batch extraction progress update"""
        progress_percentage = int((processed_count / total_count) * 100)
        self.batch_progress.setValue(progress_percentage)
        
        # Update statistics
        self.batch_total_count_value.setText(str(total_count))
        self.batch_success_count_value.setText(str(success_count))
        self.batch_failed_count_value.setText(str(failed_count))
        
        # Update progress label with more detailed information
        current_file_name = os.path.basename(current_file) if current_file else ""
        self.batch_progress_label.setText(f"Processing: {current_file_name} ({processed_count}/{total_count}) - {progress_percentage}%")
    
    def on_batch_individual_progress(self, archive_name, message, progress):
        """Handle individual archive extraction progress"""
        # Update status bar with individual file progress
        self.status_bar.showMessage(f"Extracting {archive_name}: {message} - {progress}%")
    
    def on_batch_status_updated(self, status_message):
        """Handle batch extraction status updates"""
        # Update status bar with general status messages
        self.status_bar.showMessage(status_message)

    def on_batch_extract_finished(self, success_count, failed_count, success_files=None, failed_files=None):
        """Handle batch extraction finished"""
        # Clean up thread
        self._cleanup_batch_thread()
        
        # Update final statistics
        total_count = success_count + failed_count
        self.batch_total_count_value.setText(str(total_count))
        self.batch_success_count_value.setText(str(success_count))
        self.batch_failed_count_value.setText(str(failed_count))
        
        # Re-enable start button and disable stop button
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)
        
        # Show completion message with detailed results
        result_message = f"Batch extraction completed: {success_count} successful, {failed_count} failed"
        self.batch_progress_label.setText(result_message)
        
        # Show appropriate message based on results
        if failed_count == 0:
            self._show_info_bar(
                title='Success',
                content=f'All {total_count} archives extracted successfully!',
                duration=3000
            )
        elif success_count == 0:
            self._show_popup(
                target=self.batch_progress,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content=f'Failed to extract all {total_count} archives.',
                duration=3000
            )
            # Show detailed failures if available
            if failed_files:
                self._show_batch_extract_failures(failed_files)
        else:
            self._show_info_bar(
                title='Partially Complete',
                content=f'Extracted {success_count} out of {total_count} archives successfully.',
                duration=3000
            )
            # Show detailed failures if available
            if failed_files:
                self._show_batch_extract_failures(failed_files)
        
        # Clear status bar
        self.status_bar.clearMessage()
    
    def _show_batch_extract_failures(self, failed_files):
        """Show detailed information about failed extractions"""
        from UIkit import MessageBox
        
        # Create detailed failure message
        failure_details = "Failed to extract the following archives:\n\n"
        for file_path, error_msg in failed_files[:10]:  # Show first 10 failures
            file_name = os.path.basename(file_path)
            failure_details += f"• {file_name}: {error_msg}\n"
        
        if len(failed_files) > 10:
            failure_details += f"\n... and {len(failed_files) - 10} more failures."
        
        # Show message box with failure details
        msg_box = MessageBox(
            'Batch Extraction Failures',
            failure_details,
            self
        )
        msg_box.yesButton.setText('OK')
        msg_box.exec()
        
    def _force_cleanup_batch_thread(self):
        """Deprecated method, use _cleanup_batch_thread instead"""
        self._cleanup_batch_thread()

    def on_batch_extract_error(self, error_message):
        """Handle batch extraction error"""
        # Clean up thread
        self._force_cleanup_batch_thread()
        
        # Re-enable start button and disable stop button
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)
        
        self._show_popup(
            target=self.batch_progress,
            icon=InfoBarIcon.ERROR,
            title='Error',
            content=f'Batch extraction error: {str(error_message)}',
            duration=3000
        )

    def on_batch_extract_stopped(self):
        """Handle batch extraction stopped by user"""
        # Clean up thread
        self._force_cleanup_batch_thread()
        
        # Re-enable start button and disable stop button
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)
        
        self.batch_progress_label.setText("Stopped")
        
        self._show_popup(
            target=self.batch_progress,
            icon=InfoBarIcon.WARNING,
            title='Stopped',
            content='Batch extraction stopped by user.',
            duration=2000
        )

    def _force_cleanup_batch_thread(self):
        """Force cleanup batch extraction thread"""
        if hasattr(self, 'batch_extract_worker_thread') and self.batch_extract_worker_thread.isRunning():
            self.batch_extract_worker_thread.quit()
            self.batch_extract_worker_thread.wait()

    def reset_batch_ui(self):
        """Reset batch extraction UI to initial state"""
        self.batch_files_listbox.clear()
        self.batch_extract_dest_path = ""
        self.batch_extract_dest_text.setText("Select destination folder...")
        self.batch_create_subfolders_check.setChecked(True)
        self.batch_overwrite_files_check.setChecked(False)
        self.batch_progress.setValue(0)
        self.update_batch_stats()
        self.batch_progress_label.setText("Ready")

    def auto_set_extract_dest_from_file(self, file_path):
        """Automatically set the extract destination to the file's parent directory"""
        try:
            parent_dir = os.path.dirname(file_path)
            if parent_dir and os.path.exists(parent_dir):
                self.extract_dest_path = parent_dir
                self.extract_dest_text.setText(self.extract_dest_path)
        except Exception as e:
            print(f"Warning: Could not auto-set extract destination: {e}")

    def update_extract_progress(self, message, progress):
        # Update both progress bar and label
        self.extract_progress_label.setText(message)
        print(f"[Extract Progress] {message}")  # Print progress information to console
        if progress >= 0:
            self.extract_progress.setValue(int(progress))

    def start_extract_archive(self):
        if not self.extract_zip_path:
            self._show_popup(
                target=self.extract_zip_text,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please specify the archive file to extract',
                duration=2000
            )
            return
        if not self.extract_dest_path:
            self._show_popup(
                target=self.extract_dest_text,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please specify the extraction destination folder',
                duration=2000
            )
            return

        # 清理可能存在的旧线程
        self._force_cleanup_thread()

        self.extract_progress_label.setText("Starting archive extraction...")
        self.extract_progress.setValue(0)
        
        # Enable cancel button and disable extract button during operation
        self.extract_button.setEnabled(False)
        self.extract_cancel_button.setEnabled(True)

        # Check if archive is password protected by attempting to list contents first
        try:
            list_archive_contents(self.extract_zip_path)
            # If listing succeeds without password, proceed without password
            password = None
            # Update password status to indicate no password protection
            self.is_password_protected = False
            self.update_password_status_extract(False, "No Password Protection")
        except RuntimeError as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                # Archive is password protected, prompt for password
                # Update password status to indicate password protection
                self.is_password_protected = True
                self.update_password_status_extract(True, "Password Required")
                from password_dialog import get_password
                password = get_password(self, "Enter Password", 
                                      f"The archive '{os.path.basename(self.extract_zip_path)}' is password protected.\nPlease enter the password:",
                                      "")  # Explicitly pass empty error message for first attempt

                if not password:
                    # User cancelled password entry
                    self._show_popup(
                        target=self.extract_progress,
                        icon=InfoBarIcon.WARNING,
                        title='Cancelled',
                        content='Archive extraction cancelled.',
                        duration=2000
                    )
                    return
            else:
                # Different error, proceed without password
                password = None
                # Update password status to indicate no password protection
                self.is_password_protected = False
                self.update_password_status_extract(False, "No Password Protection")
        except Exception:
            # Unexpected error, proceed without password
            password = None
            # Update password status to indicate unknown status
            self.is_password_protected = False
            self.update_password_status_extract(False, "Archive Status Unknown")

        self.extract_zip_worker = ExtractZipWorker(self.extract_zip_path, self.extract_dest_path, password)
        self.extract_zip_worker_thread = QThread()
        self.extract_zip_worker.moveToThread(self.extract_zip_worker_thread)

        self.extract_zip_worker.finished.connect(self.on_extract_archive_finished)
        self.extract_zip_worker.progress_updated.connect(self.update_extract_progress)
        self.extract_zip_worker.conversion_error.connect(self.on_extract_archive_error)
        self.extract_zip_worker.password_required.connect(self.on_extract_archive_error)
        self.extract_zip_worker.canceled.connect(self.on_extract_archive_canceled)
        self.extract_zip_worker_thread.started.connect(self.extract_zip_worker.run)
        self.extract_zip_worker_thread.start()

    def on_extract_archive_finished(self):
        # 确保线程被正确清理
        self._force_cleanup_thread()
        
        # Update password status to indicate successful extraction
        # Always set is_protected to False for successful extraction, regardless of initial state
        self.update_password_status_extract(False, "Extraction Successful")
        
        # Show success notification at the top
        self._show_info_bar(
            title='Success',
            content='Archive extracted successfully!',
            duration=2000
        )

    def on_extract_archive_error(self, error_message):
        # Check if error is due to incorrect password
        error_msg_lower = str(error_message).lower()
        is_password_error = (
            "password" in error_msg_lower and (
                "incorrect" in error_msg_lower or 
                "wrong" in error_msg_lower or
                "bad" in error_msg_lower or
                "invalid" in error_msg_lower or
                "failed" in error_msg_lower
            )
        ) or (
            "bad password" in error_msg_lower or
            "authentication failed" in error_msg_lower or
            "password required" in error_msg_lower
        )
        
        if is_password_error:
            # Update password status to indicate password required (not incorrect)
            self.update_password_status_extract(True, "Password Required")
            
            # 循环提示用户输入密码，直到输入正确的密码或取消
            while True:
                # Prompt for password again with neutral title and message
                from password_dialog import get_password
                password = get_password(self, "Enter Password", 
                                      f"Please enter the password for '{os.path.basename(self.extract_zip_path)}':",
                                      "")  # Always use empty error message
                if password:
                    # 强制终止之前的线程
                    self._force_cleanup_thread()
                    
                    # Retry extraction with new password
                    self.extract_progress_label.setText("Retrying archive extraction...")
                    self.extract_progress.setValue(0)
                    
                    # 创建新的工作线程
                    self.extract_zip_worker = ExtractZipWorker(self.extract_zip_path, self.extract_dest_path, password)
                    self.extract_zip_worker_thread = QThread()
                    self.extract_zip_worker.moveToThread(self.extract_zip_worker_thread)
                    
                    # Connect signals including canceled signal
                    self.extract_zip_worker.canceled.connect(self.on_extract_archive_canceled)

                    # 连接信号
                    self.extract_zip_worker.finished.connect(self.on_extract_archive_finished)
                    self.extract_zip_worker.progress_updated.connect(self.update_extract_progress)
                    self.extract_zip_worker.conversion_error.connect(self.on_extract_archive_error)
                    self.extract_zip_worker.password_required.connect(self.on_extract_archive_error)
                    self.extract_zip_worker_thread.started.connect(self.extract_zip_worker.run)
                    
                    # 启动线程
                    self.extract_zip_worker_thread.start()
                    return
                else:
                    # User cancelled password entry
                    # 强制终止之前的线程
                    self._force_cleanup_thread()
                    
                    self._show_popup(
                        target=self.extract_progress,
                        icon=InfoBarIcon.WARNING,
                        title='Cancelled',
                        content='Archive extraction cancelled.',
                        duration=2000
                    )
                    self.extract_progress_label.setText("Archive extraction cancelled.")
                    return
        
        # 对于非密码错误，确保线程被正确清理
        self._force_cleanup_thread()
        
        # Show error message for other types of errors
        # Update password status to indicate extraction error
        self.update_password_status_extract(False, "Extraction Error")
        
        self._show_popup(
            target=self.extract_progress,
            icon=InfoBarIcon.ERROR,
            title='Error',
            content=f'Error extracting archive: {str(error_message)}',
            duration=3000
        )
        self.extract_progress_label.setText("Archive extraction failed.")
    
    def cancel_extract_archive(self):
        """Cancel the archive extraction process"""
        if self.confirm_cancel("归档解压"):
            self.log_cancel("Extract Archive")
            # Stop the worker
            if self.extract_zip_worker:
                self.extract_zip_worker.stop()
        
    def on_extract_archive_canceled(self):
        """Handle archive extraction canceled"""
        # 使用强制线程清理方法
        self._force_cleanup_thread()
        
        # Update progress and status
        self.extract_progress.setValue(0)
        self.extract_progress_label.setText("Archive extraction canceled")
        
        # Show cancel notification
        self._show_info_bar(
            title='Canceled',
            content='Archive extraction canceled by user',
            duration=2000
        )
        
        # Update password status to indicate unknown status
        self.is_password_protected = False
        self.update_password_status_extract(False, "Archive Status Unknown")
    
    def _force_cleanup_thread(self):
        """强制清理线程，确保完全终止"""
        # Reset button states
        self.extract_button.setEnabled(True)
        self.extract_cancel_button.setEnabled(False)
        
        if self.extract_zip_worker_thread:
            if self.extract_zip_worker_thread.isRunning():
                # 先尝试正常退出
                self.extract_zip_worker_thread.quit()
                if not self.extract_zip_worker_thread.wait(500):  # 等待0.5秒
                    # 如果正常退出失败，强制终止
                    self.extract_zip_worker_thread.terminate()
                    if not self.extract_zip_worker_thread.wait(500):  # 再等待0.5秒
                        # 如果终止也失败，尝试杀死线程
                        self.extract_zip_worker_thread.kill()
                        self.extract_zip_worker_thread.wait(500)  # 等待0.5秒
            
            # 删除线程对象
            self.extract_zip_worker_thread.deleteLater()
            self.extract_zip_worker_thread = None
        
        if self.extract_zip_worker:
            # 删除worker对象
            self.extract_zip_worker.deleteLater()
            self.extract_zip_worker = None


    def browse_add_archive(self):
        file_dialog = QFileDialog(self)
        wildcard_parts = [f"{fmt.upper()} files (*.{fmt})" for fmt in SUPPORTED_ARCHIVE_FORMATS]
        wildcard = ";;".join(wildcard_parts) + ";;All files (*.*)"
        file_dialog.setNameFilter(wildcard)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if file_dialog.exec():
            self.add_zip_path = file_dialog.selectedFiles()[0]
            self.add_zip_text.setText(self.add_zip_path)
            # Auto-detect password protection using the new PasswordDetector
            try:
                from support.password_detector import password_detector
                detection_result = password_detector.is_password_protected(self.add_zip_path)
                if detection_result['is_protected']:
                    self.is_password_protected = True
                    print(f"Archive is password protected ({detection_result['format']})")
                else:
                    self.is_password_protected = False
                    print(f"Archive has no password protection ({detection_result['format']})")
            except Exception as e:
                print(f"Warning: Could not detect password protection: {e}")
                self.is_password_protected = False

    def browse_add_file(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("All files (*.*)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                # Store files as list
                self.add_file_path = selected_files
                
                # Update the UI display
                self.update_add_files_list(selected_files)

    def update_add_progress(self, message, progress):
        # Update both progress bar and label
        self.add_progress_label.setText(message)
        print(f"[Add Progress] {message}")  # Print progress information to console
        if progress >= 0:
            self.add_progress.setValue(int(progress))

    def start_add_to_archive(self):
        if not self.add_zip_path:
            self._show_popup(
                target=self.add_zip_text,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please specify an existing archive file to add files to',
                duration=2000
            )
            return
        if not self.add_file_path:
            self._show_popup(
                target=self.add_files_listbox,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please specify files to add to the archive',
                duration=2000
            )
            return
        archive_format = Path(self.add_zip_path).suffix.lower().lstrip('.')
        # RAR format is now supported through external rar command
        # No need to show error message

        self.add_progress_label.setText("Starting archive file addition...")
        self.add_progress.setValue(0)
        
        # Enable cancel button and disable add button during operation
        self.add_button.setEnabled(False)
        self.add_cancel_button.setEnabled(True)

        # Handle multiple files - split by semicolon if contains multiple paths
        if isinstance(self.add_file_path, list):
            # Direct list of files (from drag and drop)
            file_paths = self.add_file_path
        elif ';' in self.add_file_path:
            # Semicolon-separated paths from browse dialog
            file_paths = [path.strip() for path in self.add_file_path.split(';') if path.strip()]
        else:
            # Single file path
            file_paths = [self.add_file_path.strip()]

        self.add_to_zip_worker = AddToZipWorker(self.add_zip_path, file_paths)
        self.add_to_zip_worker_thread = QThread()
        self.add_to_zip_worker.moveToThread(self.add_to_zip_worker_thread)

        self.add_to_zip_worker.finished.connect(self.on_add_to_archive_finished)
        self.add_to_zip_worker.progress_updated.connect(self.update_add_progress)
        self.add_to_zip_worker.finished.connect(self.on_add_to_archive_finished)
        self.add_to_zip_worker.canceled.connect(self.on_add_to_archive_canceled)
        self.add_to_zip_worker_thread.started.connect(self.add_to_zip_worker.run)
        self.add_to_zip_worker_thread.start()

    def on_add_to_archive_finished(self):
        # 使用强制线程清理方法
        self._force_cleanup_add_thread()
        
        # Count number of files added
        file_count = 1
        if self.add_to_zip_worker and hasattr(self.add_to_zip_worker, 'files_to_add'):
            if isinstance(self.add_to_zip_worker.files_to_add, list):
                file_count = len(self.add_to_zip_worker.files_to_add)
        file_text = "files" if file_count > 1 else "file"
        
        # Show success notification at the top
        self._show_info_bar(
            title='Success',
            content=f'{file_count} {file_text} added to archive successfully!',
            duration=2000
        )

    def on_add_to_archive_error(self, error_message):
        # 使用强制线程清理方法
        self._force_cleanup_add_thread()
        
        self._show_popup(
            target=self.add_progress,
            icon=InfoBarIcon.ERROR,
            title='Error',
            content=f'Error adding file to archive: {str(error_message)}',
            duration=3000
        )
        self.add_progress_label.setText("Archive file addition failed.")
    
    def cancel_add_to_archive(self):
        """Cancel the add to archive process"""
        if self.confirm_cancel("添加到归档"):
            self.log_cancel("Add to Archive")
            # Stop the worker
            if self.add_to_zip_worker:
                self.add_to_zip_worker.stop()
        
    def on_add_to_archive_canceled(self):
        """Handle add to archive canceled"""
        # 使用强制线程清理方法
        self._force_cleanup_add_thread()
        
        # Update progress and status
        self.add_progress.setValue(0)
        self.add_progress_label.setText("Add to archive canceled")
        
        # Show cancel notification
        self._show_info_bar(
            title='Canceled',
            content='Add to archive canceled by user',
            duration=2000
        )
    
    def _force_cleanup_add_thread(self):
        """强制清理添加到归档的线程，确保完全终止"""
        # Reset button states
        self.add_button.setEnabled(True)
        self.add_cancel_button.setEnabled(False)
        
        if self.add_to_zip_worker_thread:
            if self.add_to_zip_worker_thread.isRunning():
                # 先尝试正常退出
                self.add_to_zip_worker_thread.quit()
                if not self.add_to_zip_worker_thread.wait(500):  # 等待0.5秒
                    # 如果正常退出失败，强制终止
                    self.add_to_zip_worker_thread.terminate()
                    if not self.add_to_zip_worker_thread.wait(500):  # 再等待0.5秒
                        # 如果终止也失败，尝试杀死线程
                        self.add_to_zip_worker_thread.kill()
                        self.add_to_zip_worker_thread.wait(500)  # 等待0.5秒
            
            # 删除线程对象
            self.add_to_zip_worker_thread.deleteLater()
            self.add_to_zip_worker_thread = None
        
        if self.add_to_zip_worker:
            # 删除worker对象
            self.add_to_zip_worker.deleteLater()
            self.add_to_zip_worker = None

    def update_add_files_list(self, files):
        """Update the add files list display"""
        if not hasattr(self, 'add_files_listbox'):
            return
            
        self.add_files_listbox.clear()
        
        # Always display the file list
        for file_path in files:
            self.add_files_listbox.addItem(os.path.basename(file_path))

    def browse_list_archive(self):
        file_dialog = QFileDialog(self)
        wildcard_parts = [f"{fmt.upper()} files (*.{fmt})" for fmt in SUPPORTED_ARCHIVE_FORMATS]
        wildcard = ";;".join(wildcard_parts) + ";;All files (*.*)"
        file_dialog.setNameFilter(wildcard)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if file_dialog.exec():
            self.list_zip_path = file_dialog.selectedFiles()[0]
            self.list_zip_text.setText(self.list_zip_path)
            # Auto-detect password protection using the new PasswordDetector
            try:
                from support.password_detector import password_detector
                detection_result = password_detector.is_password_protected(self.list_zip_path)
                if detection_result['is_protected']:
                    self.update_password_status_list(True, f"Password Protected ({detection_result['format']})")
                    self.is_password_protected = True
                else:
                    self.update_password_status_list(False, f"No Password Protection ({detection_result['format']})")
                    self.is_password_protected = False
            except Exception as e:
                print(f"Warning: Could not detect password protection: {e}")
                self.update_password_status_list(False, "Archive Selected")
                self.is_password_protected = False
            # Clear any stored password for the previous archive
            if hasattr(self, '_current_password'):
                delattr(self, '_current_password')
            self.start_list_archive_contents() # Automatically list contents after selecting file

    def show_source_context_menu(self, position):
        """Show right-click menu for source files list - functionality removed"""
        pass

    def show_contents_context_menu(self, position):
        """Show right-click menu for archive contents list - functionality removed"""
        pass

    def start_list_archive_contents(self):
        if not self.list_zip_path:
            self._show_popup(
                target=self.list_zip_text,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please select an archive file to list contents.',
                duration=2000
            )
            return

        self.contents_listbox.clear()
        self.contents_listbox.addItem("Listing contents...")
        
        # Enable cancel button and disable list button during operation
        self.list_button.setEnabled(False)
        self.list_cancel_button.setEnabled(True)

        # Reset password protection status
        self.is_password_protected = False
        
        # First try to list contents without password
        # This will work for password-protected archives after our modifications
        password = None
        
        self.list_zip_worker = ListZipContentsWorker(self.list_zip_path, password=password)
        self.list_zip_worker_thread = QThread()
        self.list_zip_worker.moveToThread(self.list_zip_worker_thread)

        self.list_zip_worker.finished.connect(self.on_list_zip_finished)
        self.list_zip_worker.conversion_error.connect(self.on_list_archive_error)
        self.list_zip_worker.password_required.connect(self.on_password_required)
        self.list_zip_worker.canceled.connect(self.on_list_archive_canceled)
        self.list_zip_worker_thread.started.connect(self.list_zip_worker.run)
        self.list_zip_worker_thread.start()

    def on_list_zip_finished(self, contents):
        """Handle successful completion of listing zip contents"""
        # 使用强制线程清理方法
        self._force_cleanup_list_thread()
        
        # Update password status for successful listing
        if hasattr(self, '_current_password') and self._current_password:
            self.update_password_status_list(True, "Password Verified")
        else:
            self.update_password_status_list(False, "No Password")
        
        # Call the original update_contents_list function
        self.update_contents_list(contents)

    def update_contents_list(self, contents):
        print(f"[DEBUG] update_contents_list: Received {len(contents) if contents else 0} items")
        if self.list_zip_worker_thread and self.list_zip_worker_thread.isRunning():
            self.list_zip_worker_thread.quit()
            self.list_zip_worker_thread.wait()
        self.contents_listbox.clear()
        # Reset password protection status
        self.is_password_protected = False
        if contents:
            print(f"[DEBUG] update_contents_list: Processing {len(contents)} items")
            for item in contents:
                # Format display contents information
                if isinstance(item, dict) and "name" in item:
                    name = item["name"]
                    size = item.get("size", 0)
                    is_dir = item.get("is_dir", False)
                    
                    if is_dir:
                        display_text = f"{name} <DIR>"
                    else:
                        # Format file size
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size // 1024} KB"
                        elif size < 1024 * 1024 * 1024:
                            size_str = f"{size // (1024 * 1024)} MB"
                        else:
                            size_str = f"{size // (1024 * 1024 * 1024)} GB"
                        display_text = f"{name} ({size_str})"
                    
                    self.contents_listbox.addItem(display_text)
                else:
                    # If item is not a dictionary, directly add
                    self.contents_listbox.addItem(str(item))
            
            # Update password status based on successful listing
            self.update_password_status_list(self.is_password_protected, "Contents Listed Successfully")
            
            self._show_info_bar(
                title='Success',
                content='Archive contents listed successfully!',
                duration=2000
            )
        else:
            print("[DEBUG] update_contents_list: No contents found")
            self.contents_listbox.addItem("No contents found or invalid archive.")
            
            # Update password status for no contents found
            self.update_password_status_list(False, "No Contents Found")
            
            self._show_popup(
                target=self.contents_listbox,
                icon=InfoBarIcon.WARNING,
                title='Warning',
                content='No contents found or invalid archive.',
                duration=2000
            )

    def on_password_required(self, error_message):
        # 使用强制线程清理方法
        self._force_cleanup_list_thread()
        
        # Set password protection status
        self.is_password_protected = True
        
        # Update password status display
        self.update_password_status_list(True, "Password Required")
        
        # Import password dialog
        try:
            from password_dialog import get_password
            
            # Get password from user
            password = get_password(
                parent=self,
                title="Password Required",
                content="This archive is password protected. Please enter the password:",
                error_message=""  # Explicitly pass empty error message for first attempt
            )
            
            if password:
                # Store the password for this archive
                self._current_password = password
                
                # Retry listing contents with password
                self.contents_listbox.clear()
                self.contents_listbox.addItem("Retrying with password...")
                
                # Create new worker with password
                self.list_zip_worker = ListZipContentsWorker(self.list_zip_path, password=password)
                self.list_zip_worker_thread = QThread()
                self.list_zip_worker.moveToThread(self.list_zip_worker_thread)

                self.list_zip_worker.finished.connect(self.on_list_zip_finished)
                self.list_zip_worker.conversion_error.connect(self.on_list_archive_error)
                self.list_zip_worker.password_required.connect(self.on_password_required)
                self.list_zip_worker_thread.started.connect(self.list_zip_worker.run)
                self.list_zip_worker_thread.start()
            else:
                # User cancelled password entry
                self._show_popup(
                    target=self.contents_listbox,
                    icon=InfoBarIcon.WARNING,
                    title='Password Required',
                    content='Password entry cancelled. Contents cannot be listed.',
                    duration=3000
                )
                self.contents_listbox.clear()
                self.contents_listbox.addItem("Password protected archive - contents cannot be listed")
        except ImportError:
            # Fallback if password dialog is not available
            self._show_popup(
                target=self.contents_listbox,
                icon=InfoBarIcon.WARNING,
                title='Password Required',
                content=f'This archive is password protected: {str(error_message)}',
                duration=3000
            )
            self.contents_listbox.clear()
            self.contents_listbox.addItem("Password protected archive - contents cannot be listed")

    def on_list_archive_error(self, error_message):
        # 使用强制线程清理方法
        self._force_cleanup_list_thread()
            
        # Check if this is a password error
        error_str = str(error_message).lower()
        if "password" in error_str and ("incorrect" in error_str or "required" in error_str or "invalid" in error_str):
            # Handle password errors
            self.is_password_protected = True
            
            # Update password status for password error
            self.update_password_status_list(True, "Password Error")
            
            # If we already have a password, it was incorrect
            if hasattr(self, '_current_password') and self._current_password:
                # Clear the incorrect password
                self._current_password = None
                
                # Show error message
                self._show_popup(
                    target=self.contents_listbox,
                    icon=InfoBarIcon.ERROR,
                    title='Incorrect Password',
                    content='The password you entered is incorrect. Please try again.',
                    duration=3000
                )
                
                # Ask for password again
                self.on_password_required(error_message)
                return
            else:
                # No password provided yet, ask for one
                self.on_password_required(error_message)
                return
        
        # Handle other types of errors
        self._show_popup(
            target=self.contents_listbox,
            icon=InfoBarIcon.ERROR,
            title='Error',
            content=f'Error listing archive contents: {str(error_message)}',
            duration=3000
        )
        self.contents_listbox.clear()
        self.contents_listbox.addItem("Error listing contents.")
        
        # Update password status for other errors
        self.update_password_status_list(False, "Error Listing Contents")
    
    def cancel_list_archive_contents(self):
        """Cancel the list archive contents process"""
        if self.confirm_cancel("列出内容"):
            self.log_cancel("List Contents")
            # Stop the worker
            if self.list_zip_worker:
                self.list_zip_worker.stop()
        
    def on_list_archive_canceled(self):
        """Handle list archive contents canceled"""
        # 使用强制线程清理方法
        self._force_cleanup_list_thread()
        
        # Update listbox and status
        self.contents_listbox.clear()
        self.contents_listbox.addItem("List contents canceled")
        
        # Show cancel notification
        self._show_info_bar(
            title='Canceled',
            content='List contents canceled by user',
            duration=2000
        )
    
    def _force_cleanup_list_thread(self):
        """强制清理列出归档内容的线程，确保完全终止"""
        # Reset button states
        self.list_button.setEnabled(True)
        self.list_cancel_button.setEnabled(False)
        
        if self.list_zip_worker_thread:
            if self.list_zip_worker_thread.isRunning():
                # 先尝试正常退出
                self.list_zip_worker_thread.quit()
                if not self.list_zip_worker_thread.wait(500):  # 等待0.5秒
                    # 如果正常退出失败，强制终止
                    self.list_zip_worker_thread.terminate()
                    if not self.list_zip_worker_thread.wait(500):  # 再等待0.5秒
                        # 如果终止也失败，尝试杀死线程
                        self.list_zip_worker_thread.kill()
                        self.list_zip_worker_thread.wait(500)  # 等待0.5秒
            
            # 删除线程对象
            self.list_zip_worker_thread.deleteLater()
            self.list_zip_worker_thread = None
        
        if self.list_zip_worker:
            # 删除worker对象
            self.list_zip_worker.deleteLater()
            self.list_zip_worker = None

    # --- Drag and Drop Event Handlers ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                current_tab = self.notebook.currentIndex()
                
                # Handle Add to Archive tab specially - support multiple files and folders
                if current_tab == 2:  # Add to Archive tab
                    # Accept if we have at least one valid file or folder
                    valid_items = []
                    for url in urls:
                        file_path = url.toLocalFile()
                        if os.path.isfile(file_path):
                            # Check if it's a supported archive format (for existing archive)
                            file_ext = Path(file_path).suffix.lower().lstrip('.')
                            if file_ext in SUPPORTED_ARCHIVE_FORMATS:
                                valid_items.append(file_path)
                            else:
                                # Accept regular files to add to archive
                                valid_items.append(file_path)
                        elif os.path.isdir(file_path):
                            # Accept folders to add to archive
                            valid_items.append(file_path)
                    
                    if valid_items:
                        event.acceptProposedAction()
                        return
                else:
                     # For other tabs, handle based on current tab
                     if current_tab == 0:  # Create Archive tab - accept any files/folders
                         # Accept if we have at least one valid file or folder
                         valid_items = []
                         for url in urls:
                             file_path = url.toLocalFile()
                             if os.path.exists(file_path):
                                 valid_items.append(file_path)
                         
                         if valid_items:
                             event.acceptProposedAction()
                             return
                     elif len(urls) == 1:  # Extract and List Contents tabs - only accept single archive files
                         file_path = urls[0].toLocalFile()
                         if os.path.isfile(file_path):
                             # Check if it's a supported archive format
                             file_ext = Path(file_path).suffix.lower().lstrip('.')
                             if file_ext in SUPPORTED_ARCHIVE_FORMATS:
                                 event.acceptProposedAction()
                                 return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop events"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                # Get current tab index
                current_tab = self.notebook.currentIndex()
                
                if current_tab == 2:  # Add to Archive tab
                    # Handle multiple files and folders for Add to Archive
                    archive_files = []
                    files_to_add = []
                    
                    # Get current archive file if already set
                    current_archive = self.add_zip_text.text()
                    
                    # Process all dropped items
                    for url in urls:
                        item_path = url.toLocalFile()
                        
                        if os.path.isfile(item_path):
                            file_ext = Path(item_path).suffix.lower().lstrip('.')
                            if file_ext in SUPPORTED_ARCHIVE_FORMATS:
                                # Archive file handling
                                if not current_archive and not archive_files:
                                    # No archive set yet, this becomes the target archive
                                    archive_files.append(item_path)
                                else:
                                    # Archive already exists, treat this as file to add
                                    files_to_add.append(item_path)
                            else:
                                # Regular files are added to the list
                                files_to_add.append(item_path)
                        elif os.path.isdir(item_path):
                            # Folders are added to the list
                            files_to_add.append(item_path)
                    
                    # If we found a new archive file, set it as the target
                    if archive_files:
                        self.add_zip_text.setText(archive_files[0])
                        current_archive = archive_files[0]
                    
                    # If we have files to add, update the UI
                    if files_to_add:
                        # Merge with existing files
                        existing_files = getattr(self, 'add_file_path', [])
                        if isinstance(existing_files, str):
                            existing_files = [existing_files]
                        all_files = existing_files + files_to_add
                        
                        # Remove duplicates while preserving order
                        seen = set()
                        unique_files = []
                        for f in all_files:
                            if f not in seen:
                                seen.add(f)
                                unique_files.append(f)
                        
                        self.add_file_path = unique_files
                        self.update_add_files_list(unique_files)
                        
                        # Show success message
                        self._show_info_bar(
                            title='Files added',
                            content=f'Added {len(files_to_add)} items to add list',
                            duration=2000
                        )
                    elif archive_files:
                        # Only archive file was dropped
                        self._show_info_bar(
                            title='Archive file set',
                            content=f'Set {os.path.basename(archive_files[0])} as target archive',
                            duration=2000
                        )
                    
                    event.acceptProposedAction()
                    return
                
                else:
                    # For other tabs, handle based on current tab
                    if current_tab == 0:  # Create Archive tab
                        # Add all files to source files list
                        for url in urls:
                            file_path = url.toLocalFile()
                            if os.path.exists(file_path) and file_path not in self.create_sources:
                                self.create_sources.append(file_path)
                                if os.path.isdir(file_path):
                                    self.sources_listbox.addItem(f"[FOLDER] {file_path}")
                                else:
                                    self.sources_listbox.addItem(file_path)
                        event.acceptProposedAction()
                        self._show_info_bar(
                            title='Files Added',
                            content=f'Added {len(urls)} items to source list',
                            duration=2000
                        )
                        return
                    elif len(urls) == 1:  # Extract and List Contents tabs - only handle single archive files
                        file_path = urls[0].toLocalFile()
                        if os.path.isfile(file_path):
                            # Check if it's a supported archive format
                            file_ext = Path(file_path).suffix.lower().lstrip('.')
                            if file_ext in SUPPORTED_ARCHIVE_FORMATS:
                                if current_tab == 1:  # Extract Archive tab
                                    # Switch to Extract tab and set the file
                                    self.extract_zip_path = file_path
                                    self.extract_zip_text.setText(file_path)
                                    # Auto-configure output directory
                                    self.auto_set_extract_dest_from_file(file_path)
                                    event.acceptProposedAction()
                                    self._show_info_bar(
                                        title='File Added',
                                        content=f'Archive file set: {os.path.basename(file_path)}',
                                        duration=2000
                                    )
                                    
                                elif current_tab == 3:  # List Contents tab
                                    # Set as archive file and automatically list contents
                                    self.list_zip_path = file_path
                                    self.list_zip_text.setText(file_path)
                                    # Automatically list contents
                                    QTimer.singleShot(100, self.start_list_archive_contents)
                                    event.acceptProposedAction()
                                    self._show_info_bar(
                                        title='File Added',
                                        content=f'Archive file set: {os.path.basename(file_path)}',
                                        duration=2000
                                    )
                                
                                return
        event.ignore()


class ZipAppRunner: # Renamed to avoid conflict with QApp
    def __init__(self):
        self.app = QApplication(sys.argv)
        from support.toggle import theme_manager
        theme_manager.start()
        setTheme(Theme.AUTO)
        self.window = ZipGUI(initial_dark_mode=self.app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5)
        self.window.show()
        self.app.paletteChanged.connect(lambda: self.window._apply_system_theme(self.app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5))

    def MainLoop(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app_runner = ZipAppRunner()
    app_runner.MainLoop()