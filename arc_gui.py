import os
import sys
import subprocess
import shutil
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt, QTimer, QUrl, QObject, QSize, QSettings, QModelIndex, QMimeData
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QLineEdit, QTextEdit, QProgressBar,
                               QTabWidget, QWidget, QGroupBox, QListWidget, QListWidgetItem,
                               QFileDialog, QCheckBox, QComboBox, QFrame, QMessageBox, QMenu,
                               QTreeWidgetItem, QStackedWidget, QAbstractItemView)
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QPixmap, QColor
from UIkit import *

# Import DraggableTreeView
from draggable.drag_tree_view import DraggableTreeView

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
from support.pending_manager import PendingFileManager, PendingFile, FolderNode
from support.archive_tree_model import ArchiveTreeModel
from password_dialog import PasswordDialog, SimplePasswordDialog

# Remove the problematic reconfigure calls
# sys.stdout.reconfigure(encoding='utf-8')
# sys.stderr.reconfigure(encoding='utf-8')
# --- Worker Classes are now imported from support.GUI.arc_support ---

class CreateFolderMessageBox(MessageBoxBase):
    """Custom message box for creating new folder when dropping file on file"""

    def __init__(self, source_name, target_name, parent=None):
        super().__init__(parent)
        self.folder_name = ""

        self.titleLabel = SubtitleLabel(self.tr('Create New Folder'))
        self.infoLabel = CaptionLabel(self.tr(f'Move "{source_name}" and "{target_name}" into new folder:'))
        self.folderLineEdit = LineEdit()
        self.folderLineEdit.setPlaceholderText(self.tr('Enter folder name'))
        self.folderLineEdit.setClearButtonEnabled(True)

        # Add widgets to view layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.folderLineEdit)

        # Set minimum width
        self.widget.setMinimumWidth(400)

        # Update button text
        self.yesButton.setText(self.tr('Create & Move'))
        self.cancelButton.setText(self.tr('Cancel'))

    def validate(self):
        """Validate folder name"""
        folder_name = self.folderLineEdit.text().strip()
        if not folder_name:
            return False
        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in folder_name:
                return False
        self.folder_name = folder_name
        return True


class ConflictResolveMessageBox(MessageBoxBase):
    """Custom message box for resolving file conflicts"""

    def __init__(self, file_name, existing_path, parent=None):
        super().__init__(parent)
        self.result_action = None

        self.titleLabel = SubtitleLabel(self.tr('File Conflict'))
        self.infoLabel = CaptionLabel(self.tr(f'File "{file_name}" conflicts with existing file at:\n{existing_path}'))

        # Add widgets to view layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)

        # Set minimum width
        self.widget.setMinimumWidth(450)

        # Update button text
        self.yesButton.setText(self.tr('Overwrite'))
        self.cancelButton.setText(self.tr('Skip'))

    def get_result(self):
        return self.result_action


class ArchiveTreeItem:
    """Tree item data class for archive contents and pending files"""
    def __init__(self, name, size, item_type, path, is_dir=False, parent=None):
        self.name = name
        self.size = size
        self.item_type = item_type  # 'existing' or 'pending'
        self.path = path
        self.is_dir = is_dir
        self.parent = parent
        self.children = []
        self.row = 0
        
    def add_child(self, child):
        child.parent = self
        child.row = len(self.children)
        self.children.append(child)
        return child
    
    def get_full_path(self):
        """Get full path for the item"""
        if self.parent and self.parent.parent:  # Not root
            parent_path = self.parent.get_full_path()
            if parent_path:
                return f"{parent_path}/{self.name}"
            return self.name
        return self.name



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

    def _get_file_icon(self, filename, is_dir=False):
        """Get FluentIcon for file based on extension or type"""
        if is_dir:
            return FluentIcon.FOLDER
        
        ext = os.path.splitext(filename.lower())[1]
        
        # Image files
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico', '.icns', '.svg', '.heic', '.heif', '.avif', '.jxl']:
            return FluentIcon.PHOTO
        
        # Video files
        if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']:
            return FluentIcon.VIDEO
        
        # Audio files
        if ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']:
            return FluentIcon.MUSIC
        
        # Archive files
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.lzma', '.cab', '.iso']:
            return FluentIcon.ZIP_FOLDER
        
        # Code files
        if ext in ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.ts']:
            return FluentIcon.CODE
        
        # Document files
        if ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt']:
            return FluentIcon.DOCUMENT
        
        # Spreadsheet files
        if ext in ['.xls', '.xlsx', '.csv', '.ods']:
            return FluentIcon.FONT
        
        # Presentation files
        if ext in ['.ppt', '.pptx', '.odp']:
            return FluentIcon.MEDIA
        
        # Executable files
        if ext in ['.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.app', '.bat', '.sh']:
            return FluentIcon.PLAY
        
        # Default
        return FluentIcon.DOCUMENT

    def _format_file_size(self, size):
        """Format file size to human readable string"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _build_tree_structure(self, contents):
        """Build tree structure from archive contents"""
        # Create root node
        root = QTreeWidgetItem(self.contents_tree)
        root.setText(0, "Archive Root")
        root.setIcon(0, FluentIcon.ZIP_FOLDER.qicon())
        root.setExpanded(True)
        
        # Dictionary to store folder nodes
        folder_nodes = {"": root}
        
        # Sort contents by path
        sorted_contents = sorted(contents, key=lambda x: x.get("name", ""))
        
        for item in sorted_contents:
            if not isinstance(item, dict) or "name" not in item:
                continue
            
            name = item["name"]
            size = item.get("size", 0)
            is_dir = item.get("is_dir", False)
            modified = item.get("modified", "")
            
            # Split path into components
            path_parts = name.split("/")
            
            # Get parent path and file name
            if is_dir:
                # For directories, the full path is the directory
                parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                current_name = path_parts[-1] if path_parts else name
            else:
                # For files
                parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                current_name = path_parts[-1] if path_parts else name
            
            # Get or create parent node
            if parent_path not in folder_nodes:
                # Create parent folder nodes recursively
                self._create_parent_nodes(folder_nodes, parent_path, root)
            
            parent_node = folder_nodes.get(parent_path, root)
            
            # Create node
            node = QTreeWidgetItem(parent_node)
            node.setText(0, current_name)
            
            if is_dir:
                node.setText(1, "<DIR>")
                node.setIcon(0, FluentIcon.FOLDER.qicon())
                # Store folder node for potential children
                current_path = name if name.endswith("/") else name + "/"
                folder_nodes[current_path.rstrip("/")] = node
            else:
                node.setText(1, self._format_file_size(size))
                icon = self._get_file_icon(current_name, is_dir=False)
                node.setIcon(0, icon.qicon())
            
            # Set modified time
            if modified:
                node.setText(2, str(modified))
        
        return root

    def _create_parent_nodes(self, folder_nodes, parent_path, root):
        """Create parent folder nodes recursively"""
        if not parent_path or parent_path in folder_nodes:
            return
        
        parts = parent_path.split("/")
        current_path = ""
        
        for i, part in enumerate(parts):
            if not part:
                continue
            
            if current_path:
                current_path += "/" + part
            else:
                current_path = part
            
            if current_path not in folder_nodes:
                # Find parent node
                if i == 0:
                    parent_node = root
                else:
                    parent_node = folder_nodes.get("/".join(parts[:i]), root)
                
                # Create folder node
                node = QTreeWidgetItem(parent_node)
                node.setText(0, part)
                node.setText(1, "<DIR>")
                node.setIcon(0, FluentIcon.FOLDER.qicon())
                folder_nodes[current_path] = node

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
        tab_sizer.setSpacing(15)
        tab_sizer.setContentsMargins(20, 20, 20, 20)
        
        # Create Archive Tab with icon
        self.notebook.addTab(tab_panel, "Create Archive")
        self.notebook.setTabIcon(self.notebook.count() - 1, FluentIcon.ADD.qicon())

        # === Output Section ===
        output_card = CardWidget()
        output_card.setBorderRadius(12)
        output_card.setBorderRadius(12)
        output_card.setBorderRadius(12)
        output_layout = QVBoxLayout(output_card)
        output_layout.setSpacing(10)
        
        # Header with icon
        output_header = QHBoxLayout()
        output_icon = IconWidget(FluentIcon.SAVE)
        output_icon.setFixedSize(20, 20)
        output_header.addWidget(output_icon)
        output_title = StrongBodyLabel("Output Archive File")
        output_header.addWidget(output_title)
        output_header.addStretch()
        output_layout.addLayout(output_header)
        
        # Output path input
        output_input_layout = QHBoxLayout()
        self.create_output_text = LineEdit()
        self.create_output_text.setPlaceholderText("Select output archive file path...")
        setCustomStyleSheet(self.create_output_text, CON.qss_line, CON.qss_line)
        output_input_layout.addWidget(self.create_output_text, 1)
        
        output_button = PushButton("Browse")
        output_button.setIcon(FluentIcon.FOLDER.qicon())
        output_button.clicked.connect(self.browse_create_output)
        output_input_layout.addWidget(output_button)
        output_layout.addLayout(output_input_layout)
        
        # Archive Format Selection
        format_layout = QHBoxLayout()
        format_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        format_icon.setFixedSize(18, 18)
        format_layout.addWidget(format_icon)
        format_label = BodyLabel("Archive Format:")
        format_layout.addWidget(format_label)
        
        self.create_format_combo = ModelComboBox()
        creation_formats = []
        for fmt in SUPPORTED_ARCHIVE_FORMATS:
            if fmt != 'tgz':
                creation_formats.append(fmt.upper())
        self.create_format_combo.addItems(creation_formats)
        self.create_format_combo.setCurrentText("ZIP")
        setCustomStyleSheet(self.create_format_combo, CON.qss_combo, CON.qss_combo)
        format_layout.addWidget(self.create_format_combo, 1)
        format_layout.addStretch()
        output_layout.addLayout(format_layout)
        
        tab_sizer.addWidget(output_card)

        # === Source Files Section ===
        sources_card = CardWidget()
        sources_card.setBorderRadius(12)
        sources_card.setBorderRadius(12)
        sources_card.setBorderRadius(12)
        sources_layout = QVBoxLayout(sources_card)
        sources_layout.setSpacing(10)
        
        # Header with icon
        sources_header = QHBoxLayout()
        sources_icon = IconWidget(FluentIcon.FOLDER)
        sources_icon.setFixedSize(20, 20)
        sources_header.addWidget(sources_icon)
        sources_title = StrongBodyLabel("Source Files / Directories")
        sources_header.addWidget(sources_title)
        sources_header.addStretch()
        sources_layout.addLayout(sources_header)
        
        # File list
        self.sources_listbox = ListWidget()
        self.sources_listbox.setMinimumHeight(200)
        self.sources_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        sources_layout.addWidget(self.sources_listbox, 1)
        
        # Action buttons
        button_sizer = QHBoxLayout()
        button_sizer.setSpacing(10)
        
        add_files_button = PushButton("Add Files")
        add_files_button.setIcon(FluentIcon.DOCUMENT.qicon())
        add_files_button.clicked.connect(self.add_source_files)
        button_sizer.addWidget(add_files_button)
        
        add_folder_button = PushButton("Add Folder")
        add_folder_button.setIcon(FluentIcon.FOLDER_ADD.qicon())
        add_folder_button.clicked.connect(self.add_source_folder)
        button_sizer.addWidget(add_folder_button)
        
        remove_button = PushButton("Remove Selected")
        remove_button.setIcon(FluentIcon.REMOVE.qicon())
        remove_button.clicked.connect(self.remove_source)
        button_sizer.addWidget(remove_button)
        button_sizer.addStretch()
        
        sources_layout.addLayout(button_sizer)
        tab_sizer.addWidget(sources_card, 1)

        # === Progress Section ===
        progress_card = CardWidget()
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setSpacing(8)
        
        self.create_progress_label = BodyLabel("")
        progress_layout.addWidget(self.create_progress_label)
        
        self.create_progress = ProgressBar()
        self.create_progress.setRange(0, 100)
        self.create_progress.setValue(0)
        progress_layout.addWidget(self.create_progress)
        
        tab_sizer.addWidget(progress_card)

        # === Action Buttons ===
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)
        action_layout.addStretch()
        
        self.create_cancel_button = PushButton("Cancel")
        self.create_cancel_button.setIcon(FluentIcon.CANCEL.qicon())
        self.create_cancel_button.clicked.connect(self.cancel_create_archive)
        self.create_cancel_button.setEnabled(False)
        action_layout.addWidget(self.create_cancel_button)
        
        self.create_button = PrimaryPushButton("Create Archive")
        self.create_button.setIcon(FluentIcon.ADD.qicon())
        self.create_button.clicked.connect(self.start_create_archive)
        action_layout.addWidget(self.create_button)
        
        tab_sizer.addLayout(action_layout)
        tab_sizer.addStretch(1)

    def create_extract_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        tab_sizer.setSpacing(15)
        tab_sizer.setContentsMargins(20, 20, 20, 20)
        
        # Extract Archive Tab with icon
        self.notebook.addTab(tab_panel, "Extract Archive")
        self.notebook.setTabIcon(self.notebook.count() - 1, FluentIcon.ZIP_FOLDER.qicon())

        # Tab selector for single/batch extract
        self.extract_tab_widget = QTabWidget()
        tab_sizer.addWidget(self.extract_tab_widget)

        # Single Extract Tab
        self.create_single_extract_tab()
        
        # Batch Extract Tab  
        self.create_batch_extract_tab()
        
        tab_sizer.addStretch(1)

    def create_single_extract_tab(self):
        """Create single archive extraction tab"""
        single_panel = QWidget()
        single_sizer = QVBoxLayout(single_panel)
        single_sizer.setSpacing(15)
        single_sizer.setContentsMargins(15, 15, 15, 15)

        # === Archive File Section ===
        archive_card = CardWidget()
        archive_card.setBorderRadius(12)
        archive_card.setBorderRadius(12)
        archive_card.setBorderRadius(12)
        archive_layout = QVBoxLayout(archive_card)
        archive_layout.setSpacing(10)
        
        # Header with icon
        archive_header = QHBoxLayout()
        archive_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        archive_icon.setFixedSize(20, 20)
        archive_header.addWidget(archive_icon)
        archive_title = StrongBodyLabel("Archive File to Extract")
        archive_header.addWidget(archive_title)
        archive_header.addStretch()
        archive_layout.addLayout(archive_header)
        
        # Archive path input
        archive_input_layout = QHBoxLayout()
        self.extract_zip_text = LineEdit()
        self.extract_zip_text.setPlaceholderText("Select archive file to extract...")
        setCustomStyleSheet(self.extract_zip_text, CON.qss_line, CON.qss_line)
        archive_input_layout.addWidget(self.extract_zip_text, 1)
        
        zip_button = PushButton("Browse")
        zip_button.setIcon(FluentIcon.FOLDER.qicon())
        zip_button.clicked.connect(self.browse_extract_archive)
        archive_input_layout.addWidget(zip_button)
        archive_layout.addLayout(archive_input_layout)
        
        single_sizer.addWidget(archive_card)

        # === Destination Section ===
        dest_card = CardWidget()
        dest_card.setBorderRadius(12)
        dest_card.setBorderRadius(12)
        dest_card.setBorderRadius(12)
        dest_layout = QVBoxLayout(dest_card)
        dest_layout.setSpacing(10)
        
        # Header with icon
        dest_header = QHBoxLayout()
        dest_icon = IconWidget(FluentIcon.DOWNLOAD)
        dest_icon.setFixedSize(20, 20)
        dest_header.addWidget(dest_icon)
        dest_title = StrongBodyLabel("Destination Folder")
        dest_header.addWidget(dest_title)
        dest_header.addStretch()
        dest_layout.addLayout(dest_header)
        
        # Destination path input
        dest_input_layout = QHBoxLayout()
        self.extract_dest_text = LineEdit()
        self.extract_dest_text.setPlaceholderText("Select destination folder...")
        setCustomStyleSheet(self.extract_dest_text, CON.qss_line, CON.qss_line)
        dest_input_layout.addWidget(self.extract_dest_text, 1)
        
        dest_button = PushButton("Browse")
        dest_button.setIcon(FluentIcon.FOLDER.qicon())
        dest_button.clicked.connect(self.browse_extract_dest)
        dest_input_layout.addWidget(dest_button)
        dest_layout.addLayout(dest_input_layout)
        
        single_sizer.addWidget(dest_card)

        # === Password Status Section ===
        status_card = CardWidget()
        status_card.setBorderRadius(12)
        status_card.setBorderRadius(12)
        status_card.setBorderRadius(12)
        status_layout = QHBoxLayout(status_card)
        status_layout.setSpacing(10)
        
        status_icon = IconWidget(FluentIcon.INFO)
        status_icon.setFixedSize(18, 18)
        status_layout.addWidget(status_icon)
        
        self.extract_password_status_label = BodyLabel("Archive Status: Unknown")
        status_layout.addWidget(self.extract_password_status_label)
        
        self.extract_password_status_icon = QLabel()
        self.extract_password_status_icon.setFixedSize(16, 16)
        status_layout.addWidget(self.extract_password_status_icon)
        status_layout.addStretch()
        
        single_sizer.addWidget(status_card)
        
        # === Progress Section ===
        progress_card = CardWidget()
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setSpacing(8)
        
        self.extract_progress_label = BodyLabel("")
        progress_layout.addWidget(self.extract_progress_label)
        
        self.extract_progress = ProgressBar()
        self.extract_progress.setRange(0, 100)
        self.extract_progress.setValue(0)
        progress_layout.addWidget(self.extract_progress)
        
        single_sizer.addWidget(progress_card)

        # === Action Buttons ===
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)
        action_layout.addStretch()
        
        self.extract_cancel_button = PushButton("Cancel")
        self.extract_cancel_button.setIcon(FluentIcon.CANCEL.qicon())
        self.extract_cancel_button.clicked.connect(self.cancel_extract_archive)
        self.extract_cancel_button.setEnabled(False)
        action_layout.addWidget(self.extract_cancel_button)
        
        self.extract_button = PrimaryPushButton("Extract Archive")
        self.extract_button.setIcon(FluentIcon.ZIP_FOLDER.qicon())
        self.extract_button.clicked.connect(self.start_extract_archive)
        action_layout.addWidget(self.extract_button)
        
        single_sizer.addLayout(action_layout)
        single_sizer.addStretch(1)
        
        self.extract_tab_widget.addTab(single_panel, "Single Extract")

    def create_batch_extract_tab(self):
        """Create batch archive extraction tab"""
        batch_panel = QWidget()
        main_layout = QHBoxLayout(batch_panel)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Left side - File management and selection
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        
        # === File Selection Card ===
        file_card = CardWidget()
        file_card.setBorderRadius(12)
        file_card.setBorderRadius(12)
        file_card.setBorderRadius(12)
        file_layout = QVBoxLayout(file_card)
        file_layout.setSpacing(10)
        
        # Header with icon
        file_header = QHBoxLayout()
        file_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        file_icon.setFixedSize(20, 20)
        file_header.addWidget(file_icon)
        file_title = StrongBodyLabel("Batch Archive Files")
        file_header.addWidget(file_title)
        file_header.addStretch()
        file_layout.addLayout(file_header)
        
        # Drag and drop area
        self.batch_drop_area = BatchDropZoneWidget("Drag archive files here\nor click to browse")
        file_layout.addWidget(self.batch_drop_area)
        
        # File list
        self.batch_files_listbox = ListWidget()
        self.batch_files_listbox.setMinimumHeight(200)
        self.batch_files_listbox.setMinimumWidth(300)
        file_layout.addWidget(self.batch_files_listbox, 1)
        
        # File management buttons
        file_buttons_layout = QHBoxLayout()
        file_buttons_layout.setSpacing(10)
        
        self.batch_add_files_btn = PushButton("Add Files")
        self.batch_add_files_btn.setIcon(FluentIcon.DOCUMENT.qicon())
        self.batch_add_files_btn.clicked.connect(self.browse_batch_archive_files)
        file_buttons_layout.addWidget(self.batch_add_files_btn)
        
        self.batch_remove_files_btn = PushButton("Remove Selected")
        self.batch_remove_files_btn.setIcon(FluentIcon.REMOVE.qicon())
        self.batch_remove_files_btn.clicked.connect(self.remove_selected_batch_files)
        file_buttons_layout.addWidget(self.batch_remove_files_btn)
        
        self.batch_clear_files_btn = PushButton("Clear All")
        self.batch_clear_files_btn.setIcon(FluentIcon.DELETE.qicon())
        self.batch_clear_files_btn.clicked.connect(self.clear_batch_files)
        file_buttons_layout.addWidget(self.batch_clear_files_btn)
        
        file_buttons_layout.addStretch()
        file_layout.addLayout(file_buttons_layout)
        
        left_layout.addWidget(file_card, 1)
        
        # Right side - Configuration and progress
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)
        
        # === Destination Card ===
        dest_card = CardWidget()
        dest_card.setBorderRadius(12)
        dest_card.setBorderRadius(12)
        dest_card.setBorderRadius(12)
        dest_layout = QVBoxLayout(dest_card)
        dest_layout.setSpacing(10)
        
        # Header with icon
        dest_header = QHBoxLayout()
        dest_icon = IconWidget(FluentIcon.DOWNLOAD)
        dest_icon.setFixedSize(20, 20)
        dest_header.addWidget(dest_icon)
        dest_title = StrongBodyLabel("Destination Folder")
        dest_header.addWidget(dest_title)
        dest_header.addStretch()
        dest_layout.addLayout(dest_header)
        
        # Destination path input
        dest_input_layout = QHBoxLayout()
        self.batch_extract_dest_text = LineEdit()
        self.batch_extract_dest_text.setPlaceholderText("Select destination folder...")
        setCustomStyleSheet(self.batch_extract_dest_text, CON.qss_line, CON.qss_line)
        dest_input_layout.addWidget(self.batch_extract_dest_text, 1)
        
        batch_dest_button = PushButton("Browse")
        batch_dest_button.setIcon(FluentIcon.FOLDER.qicon())
        batch_dest_button.clicked.connect(self.browse_batch_extract_dest)
        dest_input_layout.addWidget(batch_dest_button)
        dest_layout.addLayout(dest_input_layout)
        
        right_layout.addWidget(dest_card)
        
        # === Options Card ===
        options_card = CardWidget()
        options_card.setBorderRadius(12)
        options_card.setBorderRadius(12)
        options_card.setBorderRadius(12)
        options_layout = QVBoxLayout(options_card)
        options_layout.setSpacing(10)
        
        # Header with icon
        options_header = QHBoxLayout()
        options_icon = IconWidget(FluentIcon.SETTING)
        options_icon.setFixedSize(20, 20)
        options_header.addWidget(options_icon)
        options_title = StrongBodyLabel("Extract Options")
        options_header.addWidget(options_title)
        options_header.addStretch()
        options_layout.addLayout(options_header)
        
        # Options
        self.batch_create_subfolders_check = CheckBox("Create subfolder for each archive")
        self.batch_create_subfolders_check.setChecked(True)
        options_layout.addWidget(self.batch_create_subfolders_check)
        
        self.batch_overwrite_files_check = CheckBox("Overwrite existing files")
        self.batch_overwrite_files_check.setChecked(False)
        options_layout.addWidget(self.batch_overwrite_files_check)
        
        self.batch_skip_existing_files_check = CheckBox("Skip existing files")
        self.batch_skip_existing_files_check.setChecked(False)
        options_layout.addWidget(self.batch_skip_existing_files_check)
        
        # Overwrite strategy
        strategy_layout = QHBoxLayout()
        strategy_icon = IconWidget(FluentIcon.FILTER)
        strategy_icon.setFixedSize(16, 16)
        strategy_layout.addWidget(strategy_icon)
        strategy_layout.addWidget(BodyLabel("Overwrite Strategy:"))
        
        self.overwrite_strategy_combo = ModelComboBox()
        self.overwrite_strategy_combo.addItems([
            "Overwrite all",
            "Skip existing",
            "Rename new",
            "Overwrite if newer"
        ])
        setCustomStyleSheet(self.overwrite_strategy_combo, CON.qss_combo_2, CON.qss_combo_2)
        strategy_layout.addWidget(self.overwrite_strategy_combo, 1)
        options_layout.addLayout(strategy_layout)
        
        right_layout.addWidget(options_card)
        
        # === Progress Card ===
        progress_card = CardWidget()
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setSpacing(10)
        
        # Header with icon
        progress_header = QHBoxLayout()
        progress_icon = IconWidget(FluentIcon.INFO)
        progress_icon.setFixedSize(20, 20)
        progress_header.addWidget(progress_icon)
        progress_title = StrongBodyLabel("Progress & Statistics")
        progress_header.addWidget(progress_title)
        progress_header.addStretch()
        progress_layout.addLayout(progress_header)
        
        # Progress label
        self.batch_progress_label = BodyLabel("Ready to extract archives")
        self.batch_progress_label.setWordWrap(True)
        progress_layout.addWidget(self.batch_progress_label)
        
        # Progress bar
        self.batch_progress = ProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        progress_layout.addWidget(self.batch_progress)
        
        # Statistics in a grid layout
        stats_widget = QWidget()
        stats_layout = QGridLayout(stats_widget)
        stats_layout.setSpacing(10)
        
        self.batch_total_count_label = BodyLabel("Total Archives:")
        self.batch_total_count_value = BodyLabel("0")
        stats_layout.addWidget(self.batch_total_count_label, 0, 0)
        stats_layout.addWidget(self.batch_total_count_value, 0, 1)
        
        self.batch_success_count_label = BodyLabel("Successful:")
        self.batch_success_count_value = BodyLabel("0")
        stats_layout.addWidget(self.batch_success_count_label, 1, 0)
        stats_layout.addWidget(self.batch_success_count_value, 1, 1)
        
        self.batch_failed_count_label = BodyLabel("Failed:")
        self.batch_failed_count_value = BodyLabel("0")
        stats_layout.addWidget(self.batch_failed_count_label, 2, 0)
        stats_layout.addWidget(self.batch_failed_count_value, 2, 1)
        
        progress_layout.addWidget(stats_widget)
        right_layout.addWidget(progress_card)
        
        # === Control Buttons ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()
        
        self.batch_stop_btn = PushButton("Stop")
        self.batch_stop_btn.setIcon(FluentIcon.CANCEL.qicon())
        self.batch_stop_btn.clicked.connect(self.stop_batch_extract)
        self.batch_stop_btn.setEnabled(False)
        button_layout.addWidget(self.batch_stop_btn)
        
        self.batch_start_btn = PrimaryPushButton("Start Extract")
        self.batch_start_btn.setIcon(FluentIcon.ZIP_FOLDER.qicon())
        self.batch_start_btn.clicked.connect(self.start_batch_extract)
        button_layout.addWidget(self.batch_start_btn)
        
        right_layout.addLayout(button_layout)
        right_layout.addStretch(1)
        
        # Add panels to main layout with proportional sizing
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 2)
        
        self.extract_tab_widget.addTab(batch_panel, "Batch Extract")
        self.extract_tab_widget.setTabIcon(self.extract_tab_widget.count() - 1, FluentIcon.FOLDER_ADD.qicon())

        # Connect drop area signals
        self.batch_drop_area.files_dropped.connect(self.on_batch_files_dropped)

    def create_add_tab(self):
        """Create Add to Archive tab with merged Archives view and Options"""
        tab_panel = QWidget()
        main_layout = QVBoxLayout(tab_panel)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Add to Archive Tab with icon
        self.notebook.addTab(tab_panel, "Add to Archive")
        self.notebook.setTabIcon(self.notebook.count() - 1, FluentIcon.FOLDER_ADD.qicon())

        # === Archive Selection Section ===
        archive_card = CardWidget()
        archive_card.setBorderRadius(12)
        archive_card.setBorderRadius(12)
        archive_card.setBorderRadius(12)
        archive_layout = QVBoxLayout(archive_card)
        archive_layout.setSpacing(10)
        
        # Header with icon
        archive_header = QHBoxLayout()
        archive_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        archive_icon.setFixedSize(20, 20)
        archive_header.addWidget(archive_icon)
        archive_title = StrongBodyLabel("Target Archive")
        archive_header.addWidget(archive_title)
        archive_header.addStretch()
        archive_layout.addLayout(archive_header)
        
        # Archive path input
        archive_input_layout = QHBoxLayout()
        self.add_zip_text = LineEdit()
        self.add_zip_text.setPlaceholderText("Select archive file to add files to...")
        setCustomStyleSheet(self.add_zip_text, CON.qss_line, CON.qss_line)
        self.add_zip_text.textChanged.connect(self._on_add_archive_path_changed)
        archive_input_layout.addWidget(self.add_zip_text, 1)
        
        zip_button = PushButton("Browse")
        zip_button.setIcon(FluentIcon.FOLDER.qicon())
        zip_button.clicked.connect(self.browse_add_archive)
        archive_input_layout.addWidget(zip_button)
        archive_layout.addLayout(archive_input_layout)
        
        main_layout.addWidget(archive_card)

        # === Pivot Navigation (2 tabs only) ===
        pivot_container = QWidget()
        pivot_layout = QVBoxLayout(pivot_container)
        pivot_layout.setSpacing(10)
        pivot_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Pivot
        self.add_pivot = Pivot()
        pivot_layout.addWidget(self.add_pivot, 0, Qt.AlignmentFlag.AlignHCenter)
        
        # Create StackedWidget for pages
        self.add_stacked_widget = QStackedWidget()
        pivot_layout.addWidget(self.add_stacked_widget, 1)
        
        # --- Page 1: Archives (Merged view) ---
        archives_page = QWidget()
        archives_page.setObjectName("archivesPage")
        archives_layout = QVBoxLayout(archives_page)
        archives_layout.setSpacing(10)
        archives_layout.setContentsMargins(0, 0, 0, 0)
        
        # Target path display
        target_path_layout = QHBoxLayout()
        target_path_layout.addWidget(BodyLabel("Target Folder:"))
        self.add_target_path_label = LineEdit()
        self.add_target_path_label.setPlaceholderText("/ (root)")
        self.add_target_path_label.setReadOnly(True)
        setCustomStyleSheet(self.add_target_path_label, CON.qss_line, CON.qss_line)
        target_path_layout.addWidget(self.add_target_path_label, 1)
        
        set_root_btn = PushButton("Root")
        set_root_btn.setToolTip("Set target to root directory")
        set_root_btn.clicked.connect(self.set_add_target_root)
        target_path_layout.addWidget(set_root_btn)
        archives_layout.addLayout(target_path_layout)
        
        # Unified tree widget (archive contents + pending files)
        self.add_unified_tree = DraggableTreeView()
        self.add_unified_tree_model = ArchiveTreeModel(self)
        self.add_unified_tree.setModel(self.add_unified_tree_model)
        
        # Set column widths - Name column wider to accommodate longer filenames
        self.add_unified_tree.setColumnWidth(0, 500)
        self.add_unified_tree.setColumnWidth(1, 100)
        self.add_unified_tree.setColumnWidth(2, 100)
        self.add_unified_tree.setColumnWidth(3, 200)
        self.add_unified_tree.setMinimumHeight(300)
        
        # Connect signals
        self.add_unified_tree.clicked.connect(self._on_unified_tree_item_clicked)
        self.add_unified_tree.file_dropped_on_file.connect(self._on_file_dropped_on_file)

        # Apply QSS styling
        self._apply_tree_drag_style()
        
        archives_layout.addWidget(self.add_unified_tree, 1)
        
        # Operation buttons
        buttons_layout = QHBoxLayout()
        
        insert_file_btn = PushButton("Insert Files")
        insert_file_btn.setIcon(FluentIcon.DOCUMENT.qicon())
        insert_file_btn.clicked.connect(self._insert_files_to_archive)
        buttons_layout.addWidget(insert_file_btn)
        
        insert_folder_btn = PushButton("Insert Folder")
        insert_folder_btn.setIcon(FluentIcon.FOLDER_ADD.qicon())
        insert_folder_btn.clicked.connect(self._insert_folder_to_archive)
        buttons_layout.addWidget(insert_folder_btn)
        
        buttons_layout.addSpacing(20)
        
        remove_btn = PushButton("Remove")
        remove_btn.setIcon(FluentIcon.REMOVE.qicon())
        remove_btn.clicked.connect(self._remove_pending_file)
        buttons_layout.addWidget(remove_btn)
        
        clear_btn = PushButton("Clear New")
        clear_btn.setIcon(FluentIcon.DELETE.qicon())
        clear_btn.clicked.connect(self._clear_pending_files)
        buttons_layout.addWidget(clear_btn)
        
        buttons_layout.addStretch()
        
        refresh_btn = PushButton("Refresh")
        refresh_btn.setIcon(FluentIcon.SYNC.qicon())
        refresh_btn.clicked.connect(self._refresh_unified_tree)
        buttons_layout.addWidget(refresh_btn)
        
        archives_layout.addLayout(buttons_layout)
        
        # Legend using QFluentWidgets labels
        legend_layout = QHBoxLayout()
        
        legend_existing = CaptionLabel("● Existing")
        # Set color: black for light theme, white for dark theme
        legend_existing.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))
        legend_layout.addWidget(legend_existing)
        
        legend_new = CaptionLabel("● New (Pending)")
        # Set green color for both themes
        legend_new.setTextColor(QColor(40, 167, 69), QColor(40, 167, 69))
        legend_layout.addWidget(legend_new)
        
        legend_layout.addStretch()
        archives_layout.addLayout(legend_layout)
        
        self.add_stacked_widget.addWidget(archives_page)
        
        # --- Page 2: Options ---
        options_page = QWidget()
        options_page.setObjectName("optionsPage")
        options_layout = QVBoxLayout(options_page)
        options_layout.setSpacing(15)
        options_layout.setContentsMargins(0, 0, 0, 0)
        
        # Options Card
        options_card = CardWidget()
        options_card.setBorderRadius(12)
        options_card.setBorderRadius(12)
        options_card.setBorderRadius(12)
        options_card_layout = QVBoxLayout(options_card)
        options_card_layout.setSpacing(15)
        
        # Compression level
        compression_layout = QVBoxLayout()
        compression_header = QHBoxLayout()
        compression_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        compression_icon.setFixedSize(18, 18)
        compression_header.addWidget(compression_icon)
        compression_header.addWidget(BodyLabel("Compression Level"))
        compression_header.addStretch()
        compression_layout.addLayout(compression_header)
        
        self.add_compression_combo = ModelComboBox()
        self.add_compression_combo.addItems([
            "Store (no compression)",
            "Fast",
            "Normal",
            "Best (maximum compression)"
        ])
        self.add_compression_combo.setCurrentIndex(2)
        setCustomStyleSheet(self.add_compression_combo, CON.qss_combo, CON.qss_combo)
        compression_layout.addWidget(self.add_compression_combo)
        options_card_layout.addLayout(compression_layout)
        
        # Overwrite strategy
        overwrite_layout = QVBoxLayout()
        overwrite_header = QHBoxLayout()
        overwrite_icon = IconWidget(FluentIcon.FILTER)
        overwrite_icon.setFixedSize(18, 18)
        overwrite_header.addWidget(overwrite_icon)
        overwrite_header.addWidget(BodyLabel("If file exists"))
        overwrite_header.addStretch()
        overwrite_layout.addLayout(overwrite_header)
        
        self.add_overwrite_combo = ModelComboBox()
        self.add_overwrite_combo.addItems([
            "Overwrite",
            "Skip",
            "Rename new file"
        ])
        setCustomStyleSheet(self.add_overwrite_combo, CON.qss_combo, CON.qss_combo)
        overwrite_layout.addWidget(self.add_overwrite_combo)
        options_card_layout.addLayout(overwrite_layout)
        
        # Path handling
        path_layout = QVBoxLayout()
        path_header = QHBoxLayout()
        path_icon = IconWidget(FluentIcon.FOLDER)
        path_icon.setFixedSize(18, 18)
        path_header.addWidget(path_icon)
        path_header.addWidget(BodyLabel("Path handling"))
        path_header.addStretch()
        path_layout.addLayout(path_header)
        
        self.add_path_combo = ModelComboBox()
        self.add_path_combo.addItems([
            "Preserve full path",
            "Filename only",
            "Custom prefix..."
        ])
        setCustomStyleSheet(self.add_path_combo, CON.qss_combo, CON.qss_combo)
        path_layout.addWidget(self.add_path_combo)
        
        self.add_custom_prefix = LineEdit()
        self.add_custom_prefix.setPlaceholderText("Enter custom path prefix...")
        self.add_custom_prefix.setEnabled(False)
        setCustomStyleSheet(self.add_custom_prefix, CON.qss_line, CON.qss_line)
        path_layout.addWidget(self.add_custom_prefix)
        options_card_layout.addLayout(path_layout)
        
        self.add_path_combo.currentIndexChanged.connect(
            lambda idx: self.add_custom_prefix.setEnabled(idx == 2)
        )
        
        options_layout.addWidget(options_card)
        
        # Progress Card
        progress_card = CardWidget()
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_card.setBorderRadius(12)
        progress_card_layout = QVBoxLayout(progress_card)
        progress_card_layout.setSpacing(10)
        
        progress_header = QHBoxLayout()
        progress_icon = IconWidget(FluentIcon.INFO)
        progress_icon.setFixedSize(18, 18)
        progress_header.addWidget(progress_icon)
        progress_header.addWidget(BodyLabel("Progress"))
        progress_header.addStretch()
        progress_card_layout.addLayout(progress_header)
        
        self.add_progress_label = BodyLabel("Ready")
        progress_card_layout.addWidget(self.add_progress_label)
        
        self.add_progress = ProgressBar()
        self.add_progress.setRange(0, 100)
        self.add_progress.setValue(0)
        progress_card_layout.addWidget(self.add_progress)
        
        options_layout.addWidget(progress_card)
        
        # Action buttons
        action_buttons = QHBoxLayout()
        action_buttons.addStretch()
        
        self.add_cancel_button = PushButton("Cancel")
        self.add_cancel_button.setIcon(FluentIcon.CANCEL.qicon())
        self.add_cancel_button.clicked.connect(self.cancel_add_to_archive)
        self.add_cancel_button.setEnabled(False)
        action_buttons.addWidget(self.add_cancel_button)
        
        self.add_button = PrimaryPushButton("Add to Archive")
        self.add_button.setIcon(FluentIcon.ADD.qicon())
        self.add_button.clicked.connect(self.start_add_to_archive)
        action_buttons.addWidget(self.add_button)
        options_layout.addLayout(action_buttons)
        
        options_layout.addStretch()
        self.add_stacked_widget.addWidget(options_page)
        
        main_layout.addWidget(pivot_container, 1)
        
        # Setup Pivot items (only 2 tabs)
        self.add_pivot.addItem(
            routeKey="archivesPage",
            text="Archives",
            onClick=lambda: self.add_stacked_widget.setCurrentWidget(archives_page),
            icon=FluentIcon.FOLDER
        )
        self.add_pivot.addItem(
            routeKey="optionsPage",
            text="Options",
            onClick=lambda: self.add_stacked_widget.setCurrentWidget(options_page),
            icon=FluentIcon.SETTING
        )
        
        # Connect stacked widget change to pivot
        self.add_stacked_widget.currentChanged.connect(self._on_add_page_changed)
        
        # Set default page
        self.add_stacked_widget.setCurrentIndex(0)
        self.add_pivot.setCurrentItem("archivesPage")
        
        # Initialize pending file manager
        self._pending_manager = PendingFileManager()

    def _on_add_page_changed(self, index):
        """Handle page change in Add to Archive tab"""
        widget = self.add_stacked_widget.widget(index)
        if widget:
            self.add_pivot.setCurrentItem(widget.objectName())

    def _apply_tree_drag_style(self):
        """Apply QSS styling for tree widget drag and drop"""
        # Check if dark mode
        bg_color = self.palette().color(QPalette.ColorRole.Window)
        is_dark = bg_color.lightness() < 128
        
        if is_dark:
            # Dark mode styles
            self.add_unified_tree.setStyleSheet("""
                QTreeWidget {
                    border: 1px solid #555555;
                    border-radius: 8px;
                    background-color: #2d2d2d;
                    outline: none;
                    color: #ffffff;
                }
                QTreeWidget::item {
                    padding: 6px;
                    border-radius: 6px;
                    min-height: 28px;
                    margin: 2px 4px;
                    color: #ffffff;
                }
                QTreeWidget::item:selected {
                    background-color: #0d6efd;
                    color: #ffffff;
                }
                QTreeWidget::item:hover {
                    background-color: #3d3d3d;
                }
                QTreeWidget::item:selected:hover {
                    background-color: #0b5ed7;
                }
                QTreeWidget QHeaderView::section {
                    background-color: #3d3d3d;
                    color: #ffffff;
                    padding: 6px;
                    border: none;
                }
            """)
        else:
            # Light mode styles
            self.add_unified_tree.setStyleSheet("""
                QTreeWidget {
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    outline: none;
                    color: #212529;
                }
                QTreeWidget::item {
                    padding: 6px;
                    border-radius: 6px;
                    min-height: 28px;
                    margin: 2px 4px;
                    color: #212529;
                }
                QTreeWidget::item:selected {
                    background-color: #0d6efd;
                    color: #ffffff;
                }
                QTreeWidget::item:hover {
                    background-color: #e9ecef;
                }
                QTreeWidget::item:selected:hover {
                    background-color: #0b5ed7;
                }
                QTreeWidget QHeaderView::section {
                    background-color: #e9ecef;
                    color: #212529;
                    padding: 6px;
                    border: none;
                }
            """)

    def create_list_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        tab_sizer.setSpacing(15)
        tab_sizer.setContentsMargins(20, 20, 20, 20)
        
        # List Contents Tab with icon
        self.notebook.addTab(tab_panel, "List Contents")
        self.notebook.setTabIcon(self.notebook.count() - 1, FluentIcon.VIEW.qicon())

        # === Archive File Section ===
        archive_card = CardWidget()
        archive_card.setBorderRadius(12)
        archive_card.setBorderRadius(12)
        archive_card.setBorderRadius(12)
        archive_layout = QVBoxLayout(archive_card)
        archive_layout.setSpacing(10)
        
        # Header with icon
        archive_header = QHBoxLayout()
        archive_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        archive_icon.setFixedSize(20, 20)
        archive_header.addWidget(archive_icon)
        archive_title = StrongBodyLabel("Archive File")
        archive_header.addWidget(archive_title)
        archive_header.addStretch()
        archive_layout.addLayout(archive_header)
        
        # Archive path input
        archive_input_layout = QHBoxLayout()
        self.list_zip_text = LineEdit()
        self.list_zip_text.setPlaceholderText("Select archive file to list contents...")
        setCustomStyleSheet(self.list_zip_text, CON.qss_line, CON.qss_line)
        archive_input_layout.addWidget(self.list_zip_text, 1)
        
        zip_button = PushButton("Browse")
        zip_button.setIcon(FluentIcon.FOLDER.qicon())
        zip_button.clicked.connect(self.browse_list_archive)
        archive_input_layout.addWidget(zip_button)
        archive_layout.addLayout(archive_input_layout)
        
        tab_sizer.addWidget(archive_card)
        
        # === Password Status Section ===
        status_card = CardWidget()
        status_card.setBorderRadius(12)
        status_card.setBorderRadius(12)
        status_card.setBorderRadius(12)
        status_layout = QHBoxLayout(status_card)
        status_layout.setSpacing(10)
        
        status_icon = IconWidget(FluentIcon.INFO)
        status_icon.setFixedSize(18, 18)
        status_layout.addWidget(status_icon)
        
        self.password_status_label = BodyLabel("Archive Status: Unknown")
        status_layout.addWidget(self.password_status_label)
        
        self.password_status_icon = QLabel()
        self.password_status_icon.setFixedSize(16, 16)
        status_layout.addWidget(self.password_status_icon)
        status_layout.addStretch()
        
        tab_sizer.addWidget(status_card)
        
        # === Archive Contents Section ===
        contents_card = CardWidget()
        contents_card.setBorderRadius(12)
        contents_card.setBorderRadius(12)
        contents_card.setBorderRadius(12)
        contents_layout = QVBoxLayout(contents_card)
        contents_layout.setSpacing(10)
        
        # Header with icon
        contents_header = QHBoxLayout()
        contents_icon = IconWidget(FluentIcon.VIEW)
        contents_icon.setFixedSize(20, 20)
        contents_header.addWidget(contents_icon)
        contents_title = StrongBodyLabel("Archive Contents")
        contents_header.addWidget(contents_title)
        contents_header.addStretch()
        contents_layout.addLayout(contents_header)
        
        # Contents tree widget
        self.contents_tree = TreeWidget()
        self.contents_tree.setMinimumHeight(300)
        self.contents_tree.setHeaderLabels(["Name", "Size", "Modified"])
        self.contents_tree.setColumnWidth(0, 400)
        self.contents_tree.setColumnWidth(1, 100)
        self.contents_tree.setColumnWidth(2, 150)
        self.contents_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        contents_layout.addWidget(self.contents_tree, 1)
        
        tab_sizer.addWidget(contents_card, 2)

        # === Action Buttons ===
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)
        action_layout.addStretch()
        
        self.list_cancel_button = PushButton("Cancel")
        self.list_cancel_button.setIcon(FluentIcon.CANCEL.qicon())
        self.list_cancel_button.clicked.connect(self.cancel_list_archive_contents)
        self.list_cancel_button.setEnabled(False)
        action_layout.addWidget(self.list_cancel_button)
        
        self.list_button = PrimaryPushButton("List Contents")
        self.list_button.setIcon(FluentIcon.VIEW.qicon())
        self.list_button.clicked.connect(self.start_list_archive_contents)
        action_layout.addWidget(self.list_button)
        
        tab_sizer.addLayout(action_layout)
        tab_sizer.addStretch(1)


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
            "Cancel Operation",
            f"Are you sure you want to cancel the current {operation_name} operation?",
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
        # Use forced thread cleanup method
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
        # Use forced thread cleanup method
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
        if self.confirm_cancel("Archive Creation"):
            self.log_cancel("Create Archive")
            # Stop the worker
            if self.create_zip_worker:
                self.create_zip_worker.stop()
        
    def on_create_archive_canceled(self):
        """Handle archive creation canceled"""
        # Use forced thread cleanup method
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
        """Force cleanup archive creation thread to ensure complete termination"""
        # Reset button states
        self.create_button.setEnabled(True)
        self.create_cancel_button.setEnabled(False)
        
        if self.create_zip_worker_thread:
            if self.create_zip_worker_thread.isRunning():
                # First try to exit normally
                self.create_zip_worker_thread.quit()
                if not self.create_zip_worker_thread.wait(500):  # Wait 0.5 seconds
                    # If normal exit fails, force terminate
                    self.create_zip_worker_thread.terminate()
                    if not self.create_zip_worker_thread.wait(500):  # 再Wait 0.5 seconds
                        # 如果终止也失败，尝试杀死线程
                        self.create_zip_worker_thread.kill()
                        self.create_zip_worker_thread.wait(500)  # Wait 0.5 seconds
            
            # Delete thread object
            self.create_zip_worker_thread.deleteLater()
            self.create_zip_worker_thread = None
        
        if self.create_zip_worker:
            # Delete worker object
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

        # Clean up any existing old threads
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
        # Ensure thread is properly cleaned up
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
            
            # Loop prompting user for password until correct password is entered or cancelled
            while True:
                # Prompt for password again with neutral title and message
                from password_dialog import get_password
                password = get_password(self, "Enter Password", 
                                      f"Please enter the password for '{os.path.basename(self.extract_zip_path)}':",
                                      "")  # Always use empty error message
                if password:
                    # Force terminate previous thread
                    self._force_cleanup_thread()
                    
                    # Retry extraction with new password
                    self.extract_progress_label.setText("Retrying archive extraction...")
                    self.extract_progress.setValue(0)
                    
                    # Create new worker thread
                    self.extract_zip_worker = ExtractZipWorker(self.extract_zip_path, self.extract_dest_path, password)
                    self.extract_zip_worker_thread = QThread()
                    self.extract_zip_worker.moveToThread(self.extract_zip_worker_thread)
                    
                    # Connect signals including canceled signal
                    self.extract_zip_worker.canceled.connect(self.on_extract_archive_canceled)

                    # Connect signals
                    self.extract_zip_worker.finished.connect(self.on_extract_archive_finished)
                    self.extract_zip_worker.progress_updated.connect(self.update_extract_progress)
                    self.extract_zip_worker.conversion_error.connect(self.on_extract_archive_error)
                    self.extract_zip_worker.password_required.connect(self.on_extract_archive_error)
                    self.extract_zip_worker_thread.started.connect(self.extract_zip_worker.run)
                    
                    # Start thread
                    self.extract_zip_worker_thread.start()
                    return
                else:
                    # User cancelled password entry
                    # Force terminate previous thread
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
        
        # For non-password errors, ensure thread is properly cleaned up
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
        if self.confirm_cancel("Archive Extraction"):
            self.log_cancel("Extract Archive")
            # Stop the worker
            if self.extract_zip_worker:
                self.extract_zip_worker.stop()
        
    def on_extract_archive_canceled(self):
        """Handle archive extraction canceled"""
        # Use forced thread cleanup method
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
        """Force cleanup thread to ensure complete termination"""
        # Reset button states
        self.extract_button.setEnabled(True)
        self.extract_cancel_button.setEnabled(False)
        
        if self.extract_zip_worker_thread:
            if self.extract_zip_worker_thread.isRunning():
                # First try to exit normally
                self.extract_zip_worker_thread.quit()
                if not self.extract_zip_worker_thread.wait(500):  # Wait 0.5 seconds
                    # If normal exit fails, force terminate
                    self.extract_zip_worker_thread.terminate()
                    if not self.extract_zip_worker_thread.wait(500):  # 再Wait 0.5 seconds
                        # 如果终止也失败，尝试杀死线程
                        self.extract_zip_worker_thread.kill()
                        self.extract_zip_worker_thread.wait(500)  # Wait 0.5 seconds
            
            # Delete thread object
            self.extract_zip_worker_thread.deleteLater()
            self.extract_zip_worker_thread = None
        
        if self.extract_zip_worker:
            # Delete worker object
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

    # --- Add to Archive Helper Methods ---
    def _on_add_archive_path_changed(self, text):
        """Handle archive path change - refresh preview"""
        if text and os.path.exists(text):
            self.add_zip_path = text
            self._refresh_unified_tree()

    def _refresh_unified_tree(self):
        """Refresh unified tree with archive contents and pending files using Model/View"""
        # Clear the model first
        self.add_unified_tree_model.clear()
        self.add_unified_tree_model.setHorizontalHeaderLabels(["Name", "Size", "Type", "Path"])

        # Re-apply column widths after clearing model
        self.add_unified_tree.setColumnWidth(0, 500)
        self.add_unified_tree.setColumnWidth(1, 100)
        self.add_unified_tree.setColumnWidth(2, 100)
        self.add_unified_tree.setColumnWidth(3, 200)

        # Add archive existing contents (excluding deleted items)
        if self.add_zip_path and os.path.exists(self.add_zip_path):
            try:
                contents = list_archive_contents(self.add_zip_path)
                if contents:
                    # Filter out deleted items
                    if hasattr(self, '_files_to_delete') and self._files_to_delete:
                        contents = [c for c in contents if c.get('name') not in self._files_to_delete]
                    self.add_unified_tree_model.add_existing_items(contents)
            except Exception as e:
                print(f"Error loading archive contents: {e}")

        # Add pending files (in green)
        self._refresh_pending_files_in_tree()

        # Expand all nodes to show the structure
        self.add_unified_tree.expandAll()

    def _refresh_tree_view(self):
        """Refresh the entire tree view"""
        self._refresh_unified_tree()

    def _refresh_pending_files_in_tree(self):
        """Add pending files to unified tree model using new architecture"""
        # Get existing folders from archive
        existing_folders = []
        if self.add_zip_path and os.path.exists(self.add_zip_path):
            try:
                contents = list_archive_contents(self.add_zip_path)
                for item in contents:
                    if item.get('is_dir'):
                        existing_folders.append(item.get('name', ''))
            except Exception:
                pass

        # Build folder structure from pending manager
        root_node = self._pending_manager.build_folder_structure(existing_folders)

        # Add pending items to tree model
        self.add_unified_tree_model.add_pending_items_from_manager(root_node)

    def _insert_files_to_archive(self):
        """Insert files to archive (browse dialog)"""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("All files (*.*)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self._add_pending_files(selected_files)

    def _insert_folder_to_archive(self):
        """Insert folder to archive (browse dialog)"""
        folder_dialog = QFileDialog(self)
        folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
        folder_dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if folder_dialog.exec():
            selected_folders = folder_dialog.selectedFiles()
            if selected_folders:
                self._add_pending_files(selected_folders)

    def _add_pending_files(self, file_paths):
        """Add files to pending list and refresh tree"""
        target = self.add_target_path if hasattr(self, 'add_target_path') else ""

        for file_path in file_paths:
            if os.path.exists(file_path):
                self._pending_manager.add_file(file_path, target)

        # Refresh tree view
        self._refresh_tree_view()

    def _remove_pending_file(self):
        """Remove selected file/folder from tree"""
        current_index = self.add_unified_tree.currentIndex()
        if not current_index.isValid():
            return

        item = self.add_unified_tree_model.itemFromIndex(current_index)
        if not item:
            return

        item_type = item.data(Qt.ItemDataRole.UserRole + 2)
        is_dir = item.data(Qt.ItemDataRole.UserRole + 3)
        item_path = item.data(Qt.ItemDataRole.UserRole + 1)
        item_name = item.text()

        # Initialize deletion tracking for existing files
        if not hasattr(self, '_files_to_delete'):
            self._files_to_delete = set()

        if item_type == "pending":
            # Handle pending items - mark for deletion in manager
            if is_dir:
                # It's a folder - mark entire folder as deleted
                folder_path = item_path.strip('/') if item_path else item_name
                self._pending_manager.mark_deleted(folder_path + '/')
            else:
                # Mark single file for deletion
                full_path = item_path.strip('/') if item_path else item_name
                self._pending_manager.mark_deleted(full_path)

        elif item_type == "existing":
            # Handle existing items
            if is_dir:
                files_in_folder = self._collect_files_from_tree_folder(item)
                for f in files_in_folder:
                    self._files_to_delete.add(f)
            else:
                self._files_to_delete.add(item_path)

        # Refresh tree view
        self._refresh_tree_view()

    def _collect_files_in_folder(self, folder_item, files_list):
        """Recursively collect all file names in a pending folder"""
        row_count = folder_item.rowCount()
        for row in range(row_count):
            child = folder_item.child(row, 0)
            if child:
                child_is_dir = child.data(Qt.ItemDataRole.UserRole + 3)
                if child_is_dir:
                    # Recursively collect from subfolder
                    self._collect_files_in_folder(child, files_list)
                else:
                    # Add file name to list
                    files_list.append(child.text())

    def _collect_files_from_tree_folder(self, folder_item):
        """Recursively collect all file paths from a folder in the tree model"""
        files_list = []
        row_count = folder_item.rowCount()
        for row in range(row_count):
            child = folder_item.child(row, 0)
            if child:
                child_is_dir = child.data(Qt.ItemDataRole.UserRole + 3)
                child_path = child.data(Qt.ItemDataRole.UserRole + 1)
                if child_is_dir:
                    # Recursively collect from subfolder
                    files_list.extend(self._collect_files_from_tree_folder(child))
                elif child_path:
                    # Add file path to list
                    files_list.append(child_path)
        return files_list

    def _clear_pending_files(self):
        """Clear all pending files"""
        self._pending_manager.clear()
        self._refresh_unified_tree()

    def _on_unified_tree_item_clicked(self, index):
        """Handle unified tree item click"""
        if not index.isValid():
            return
        
        # For QStandardItemModel, use itemFromIndex instead of internalPointer
        item = self.add_unified_tree_model.itemFromIndex(index)
        if not item:
            return
        
        # Get item data from UserRole
        item_type = item.data(Qt.ItemDataRole.UserRole + 2)
        is_dir = item.data(Qt.ItemDataRole.UserRole + 3)
        path = item.data(Qt.ItemDataRole.UserRole + 1)
        
        if item_type == "existing":
            # For existing items, set target path if it's a folder
            if is_dir:
                self.add_target_path = path
                self.add_target_path_label.setText(f"/{path}")
    
    def _on_add_files_dropped(self, files):
        """Handle files dropped to add drop area"""
        if not hasattr(self, 'add_file_path'):
            self.add_file_path = []
        if not isinstance(self.add_file_path, list):
            self.add_file_path = []
        self.add_file_path.extend(files)
        self.update_add_files_list(self.add_file_path)

    def _on_file_dropped_on_file(self, source_name, target_name):
        """Handle when a file is dropped onto another file in the tree"""
        print(f"[_on_file_dropped_on_file] Called with {source_name} -> {target_name}")

        # Show CreateFolderMessageBox dialog
        dialog = CreateFolderMessageBox(source_name, target_name, self)

        result = dialog.exec()
        print(f"[_on_file_dropped_on_file] Dialog result: {result}")

        if result:
            # User confirmed - create folder and move files
            folder_name = dialog.folder_name
            print(f"[_on_file_dropped_on_file] Folder name: {folder_name}")
            if folder_name:
                # Update the tree model directly without full refresh
                self._create_folder_and_move_files(source_name, target_name, folder_name)

                self._show_info_bar(
                    title='Folder Created',
                    content=f'Created folder "{folder_name}" and moved files into it',
                    duration=2000
                )
        else:
            print(f"[_on_file_dropped_on_file] Dialog cancelled or validation failed")

    def _create_folder_and_move_files(self, source_name, target_name, folder_name):
        """Create a new folder and move files into it"""
        # Update pending manager with new folder structure
        self._pending_manager.update_file_target_by_basename(source_name, f"{folder_name}/{source_name}")
        self._pending_manager.update_file_target_by_basename(target_name, f"{folder_name}/{target_name}")

        # Refresh tree view
        self._refresh_tree_view()

        # Expand the new folder
        self.add_unified_tree.expandAll()

    def browse_add_folder(self):
        """Browse for folder to add to archive"""
        folder_dialog = QFileDialog(self)
        folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
        folder_dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if folder_dialog.exec():
            selected_folders = folder_dialog.selectedFiles()
            if selected_folders:
                if not hasattr(self, 'add_file_path'):
                    self.add_file_path = []
                if not isinstance(self.add_file_path, list):
                    self.add_file_path = []
                self.add_file_path.extend(selected_folders)
                self.update_add_files_list(self.add_file_path)

    def remove_add_file(self):
        """Remove selected file from add list"""
        current_item = self.add_files_tree.currentItem()
        if current_item:
            index = self.add_files_tree.indexOfTopLevelItem(current_item)
            self.add_files_tree.takeTopLevelItem(index)
            # Update internal list
            if hasattr(self, 'add_file_path') and isinstance(self.add_file_path, list):
                if index < len(self.add_file_path):
                    self.add_file_path.pop(index)

    def clear_add_files(self):
        """Clear all files from add list"""
        self.add_files_tree.clear()
        self.add_file_path = []

    def refresh_add_archive_preview(self):
        """Refresh archive contents preview"""
        if not self.add_zip_path or not os.path.exists(self.add_zip_path):
            self.add_archive_tree.clear()
            return
        try:
            contents = list_archive_contents(self.add_zip_path)
            self.add_archive_tree.clear()
            if contents:
                self._build_add_archive_tree(contents)
        except Exception as e:
            print(f"Error loading archive preview: {e}")
            self.add_archive_tree.clear()

    def _build_add_archive_tree(self, contents):
        """Build tree structure for archive preview"""
        folder_nodes = {"": self.add_archive_tree}
        sorted_contents = sorted(contents, key=lambda x: x.get("name", ""))
        for item in sorted_contents:
            if not isinstance(item, dict) or "name" not in item:
                continue
            name = item["name"]
            size = item.get("size", 0)
            is_dir = item.get("is_dir", False)
            path_parts = name.split("/")
            if is_dir:
                parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                current_name = path_parts[-1] if path_parts else name
            else:
                parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                current_name = path_parts[-1] if path_parts else name
            if parent_path not in folder_nodes:
                self._create_add_archive_parent_nodes(folder_nodes, parent_path)
            parent_node = folder_nodes.get(parent_path, self.add_archive_tree)
            node = QTreeWidgetItem(parent_node)
            node.setText(0, current_name)
            if is_dir:
                node.setText(1, "<DIR>")
                node.setIcon(0, FluentIcon.FOLDER.qicon())
                current_path = name if name.endswith("/") else name + "/"
                folder_nodes[current_path.rstrip("/")] = node
            else:
                node.setText(1, self._format_file_size(size))
                icon = self._get_file_icon(current_name, is_dir=False)
                node.setIcon(0, icon.qicon())

    def _create_add_archive_parent_nodes(self, folder_nodes, parent_path):
        """Create parent folder nodes for archive preview"""
        if not parent_path or parent_path in folder_nodes:
            return
        parts = parent_path.split("/")
        current_path = ""
        for i, part in enumerate(parts):
            if not part:
                continue
            if current_path:
                current_path += "/" + part
            else:
                current_path = part
            if current_path not in folder_nodes:
                if i == 0:
                    parent_node = self.add_archive_tree
                else:
                    parent_node = folder_nodes.get("/".join(parts[:i]), self.add_archive_tree)
                node = QTreeWidgetItem(parent_node)
                node.setText(0, part)
                node.setText(1, "<DIR>")
                node.setIcon(0, FluentIcon.FOLDER.qicon())
                folder_nodes[current_path] = node

    def _on_add_archive_item_clicked(self, item):
        """Handle archive tree item click - set target path"""
        # Build full path from item
        path_parts = []
        current = item
        while current:
            path_parts.insert(0, current.text(0))
            current = current.parent()
        full_path = "/".join(path_parts)
        # Check if it's a directory
        if item.text(1) == "<DIR>":
            self.add_target_path = full_path
            self.add_target_path_label.setText(f"/{full_path}")
        else:
            # For files, use parent directory
            parent = item.parent()
            if parent:
                self._on_add_archive_item_clicked(parent)

    def set_add_target_root(self):
        """Set target path to root"""
        self.add_target_path = ""
        self.add_target_path_label.setText("/ (root)")

    def update_add_files_list(self, files):
        """Update the files to add tree"""
        self.add_files_tree.clear()
        if not files:
            return
        for file_path in files:
            if not os.path.exists(file_path):
                continue
            item = QTreeWidgetItem(self.add_files_tree)
            item.setText(0, os.path.basename(file_path))
            if os.path.isdir(file_path):
                item.setText(1, "<DIR>")
                item.setIcon(0, FluentIcon.FOLDER.qicon())
                # Calculate total size
                total_size = 0
                for root, dirs, filenames in os.walk(file_path):
                    for f in filenames:
                        fp = os.path.join(root, f)
                        if os.path.exists(fp):
                            total_size += os.path.getsize(fp)
                item.setText(1, self._format_file_size(total_size))
            else:
                size = os.path.getsize(file_path)
                item.setText(1, self._format_file_size(size))
                icon = self._get_file_icon(file_path, is_dir=False)
                item.setIcon(0, icon.qicon())
            # Set target path
            target = self.add_target_path if hasattr(self, 'add_target_path') else ""
            item.setText(2, f"/{target}" if target else "/")

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

        # Use pending manager instead of _pending_files
        if self._pending_manager.is_empty():
            self._show_popup(
                target=self.add_unified_tree,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content='Please specify files to add to the archive',
                duration=2000
            )
            return

        archive_format = Path(self.add_zip_path).suffix.lower().lstrip('.')
        # RAR format is now supported through external rar command
        # No need to show error message

        # Check for conflicts before starting
        if hasattr(self, 'add_unified_tree'):
            # Get existing archive contents
            existing_contents = []
            if self.add_zip_path and os.path.exists(self.add_zip_path):
                try:
                    existing_contents = list_archive_contents(self.add_zip_path)
                except Exception as e:
                    print(f"Error loading archive contents for conflict check: {e}")

            # Convert pending files to old format for conflict check
            pending_files_old_format = []
            for f in self._pending_manager.get_active_files():
                pending_files_old_format.append({
                    'path': f.path,
                    'target': f.target
                })

            # Check for conflicts with existing files
            conflicts = self.add_unified_tree.check_file_conflicts(pending_files_old_format, existing_contents)
            if conflicts:
                # Show conflict dialog
                conflict_names = [os.path.basename(c['pending_file']['path']) for c in conflicts]
                msg = MessageBox(
                    self.tr('File Conflicts Detected'),
                    self.tr(f'The following files conflict with existing archive contents:\n' +
                           '\n'.join(conflict_names[:5]) +
                           (f'\n... and {len(conflict_names) - 5} more' if len(conflict_names) > 5 else '') +
                           '\n\nDo you want to overwrite existing files?'),
                    self
                )
                msg.yesButton.setText(self.tr('Overwrite'))
                msg.cancelButton.setText(self.tr('Cancel'))
                if not msg.exec():
                    return  # User cancelled

            # Check for conflicts among pending files themselves
            pending_conflicts = self.add_unified_tree.check_pending_conflicts(pending_files_old_format)
            if pending_conflicts:
                conflict_info = []
                for c in pending_conflicts:
                    file1 = os.path.basename(c['file1']['path'])
                    file2 = os.path.basename(c['file2']['path'])
                    path = c['common_path']
                    conflict_info.append(f'  • "{file1}" and "{file2}" → {path}')

                msg = MessageBox(
                    self.tr('Duplicate Target Paths'),
                    self.tr(f'Multiple files have the same target path:\n' +
                           '\n'.join(conflict_info[:5]) +
                           (f'\n... and {len(conflict_info) - 5} more' if len(conflict_info) > 5 else '') +
                           '\n\nPlease resolve conflicts before adding to archive.'),
                    self
                )
                msg.yesButton.setText(self.tr('OK'))
                msg.cancelButton.hide()
                msg.exec()
                return  # Cannot proceed with conflicts

        self.add_progress_label.setText("Starting archive file addition...")
        self.add_progress.setValue(0)

        # Enable cancel button and disable add button during operation
        self.add_button.setEnabled(False)
        self.add_cancel_button.setEnabled(True)

        # Get file paths from pending manager
        active_files = self._pending_manager.get_active_files()
        file_paths = [f.path for f in active_files]

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
        # Use forced thread cleanup method
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
        # Use forced thread cleanup method
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
        if self.confirm_cancel("Add to Archive"):
            self.log_cancel("Add to Archive")
            # Stop the worker
            if self.add_to_zip_worker:
                self.add_to_zip_worker.stop()
        
    def on_add_to_archive_canceled(self):
        """Handle add to archive canceled"""
        # Use forced thread cleanup method
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
        """强制清理Add to Archive的线程，确保完全终止"""
        # Reset button states
        self.add_button.setEnabled(True)
        self.add_cancel_button.setEnabled(False)
        
        if self.add_to_zip_worker_thread:
            if self.add_to_zip_worker_thread.isRunning():
                # First try to exit normally
                self.add_to_zip_worker_thread.quit()
                if not self.add_to_zip_worker_thread.wait(500):  # Wait 0.5 seconds
                    # If normal exit fails, force terminate
                    self.add_to_zip_worker_thread.terminate()
                    if not self.add_to_zip_worker_thread.wait(500):  # 再Wait 0.5 seconds
                        # 如果终止也失败，尝试杀死线程
                        self.add_to_zip_worker_thread.kill()
                        self.add_to_zip_worker_thread.wait(500)  # Wait 0.5 seconds
            
            # Delete thread object
            self.add_to_zip_worker_thread.deleteLater()
            self.add_to_zip_worker_thread = None
        
        if self.add_to_zip_worker:
            # Delete worker object
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

        self.contents_tree.clear()
        item = QTreeWidgetItem(self.contents_tree)
        item.setText(0, "Listing contents...")
        item.setIcon(0, FluentIcon.INFO.qicon())
        
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
        # Use forced thread cleanup method
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
        
        # Clear tree widget
        self.contents_tree.clear()
        
        # Reset password protection status
        self.is_password_protected = False
        
        if contents:
            print(f"[DEBUG] update_contents_list: Processing {len(contents)} items")
            
            # Build tree structure
            self._build_tree_structure(contents)
            
            # Expand root node
            root = self.contents_tree.topLevelItem(0)
            if root:
                root.setExpanded(True)
            
            # Update password status based on successful listing
            self.update_password_status_list(self.is_password_protected, "Contents Listed Successfully")
            
            self._show_info_bar(
                title='Success',
                content=f'Archive contents listed successfully! ({len(contents)} items)',
                duration=2000
            )
        else:
            print("[DEBUG] update_contents_list: No contents found")
            
            # Show empty message in tree
            empty_item = QTreeWidgetItem(self.contents_tree)
            empty_item.setText(0, "No contents found or invalid archive.")
            empty_item.setIcon(0, FluentIcon.INFO.qicon())
            
            # Update password status for no contents found
            self.update_password_status_list(False, "No Contents Found")
            
            self._show_popup(
                target=self.contents_tree,
                icon=InfoBarIcon.WARNING,
                title='Warning',
                content='No contents found or invalid archive.',
                duration=2000
            )

    def on_password_required(self, error_message):
        # Use forced thread cleanup method
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
                self.contents_tree.clear()
                item = QTreeWidgetItem(self.contents_tree)
                item.setText(0, "Retrying with password...")
                item.setIcon(0, FluentIcon.INFO.qicon())
                
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
                    target=self.contents_tree,
                    icon=InfoBarIcon.WARNING,
                    title='Password Required',
                    content='Password entry cancelled. Contents cannot be listed.',
                    duration=3000
                )
                self.contents_tree.clear()
                item = QTreeWidgetItem(self.contents_tree)
                item.setText(0, "Password protected archive - contents cannot be listed")
                item.setIcon(0, FluentIcon.INFO.qicon())
        except ImportError:
            # Fallback if password dialog is not available
            self._show_popup(
                target=self.contents_listbox,
                icon=InfoBarIcon.WARNING,
                title='Password Required',
                content=f'This archive is password protected: {str(error_message)}',
                duration=3000
            )
            self.contents_tree.clear()
            item = QTreeWidgetItem(self.contents_tree)
        item.setText(0, "Password protected archive - contents cannot be listed")
        item.setIcon(0, FluentIcon.INFO.qicon())

    def on_list_archive_error(self, error_message):
        # Use forced thread cleanup method
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
        self.contents_tree.clear()
        item = QTreeWidgetItem(self.contents_tree)
        item.setText(0, "Error listing contents.")
        item.setIcon(0, FluentIcon.INFO.qicon())
        
        # Update password status for other errors
        self.update_password_status_list(False, "Error Listing Contents")
    
    def cancel_list_archive_contents(self):
        """Cancel the list archive contents process"""
        if self.confirm_cancel("List Contents"):
            self.log_cancel("List Contents")
            # Stop the worker
            if self.list_zip_worker:
                self.list_zip_worker.stop()
        
    def on_list_archive_canceled(self):
        """Handle list archive contents canceled"""
        # Use forced thread cleanup method
        self._force_cleanup_list_thread()
        
        # Update listbox and status
        self.contents_tree.clear()
        item = QTreeWidgetItem(self.contents_tree)
        item.setText(0, "List contents canceled")
        item.setIcon(0, FluentIcon.INFO.qicon())
        
        # Show cancel notification
        self._show_info_bar(
            title='Canceled',
            content='List contents canceled by user',
            duration=2000
        )
    
    def _force_cleanup_list_thread(self):
        """Force cleanup list archive contents thread to ensure complete termination"""
        # Reset button states
        self.list_button.setEnabled(True)
        self.list_cancel_button.setEnabled(False)
        
        if self.list_zip_worker_thread:
            if self.list_zip_worker_thread.isRunning():
                # First try to exit normally
                self.list_zip_worker_thread.quit()
                if not self.list_zip_worker_thread.wait(500):  # Wait 0.5 seconds
                    # If normal exit fails, force terminate
                    self.list_zip_worker_thread.terminate()
                    if not self.list_zip_worker_thread.wait(500):  # 再Wait 0.5 seconds
                        # 如果终止也失败，尝试杀死线程
                        self.list_zip_worker_thread.kill()
                        self.list_zip_worker_thread.wait(500)  # Wait 0.5 seconds
            
            # Delete thread object
            self.list_zip_worker_thread.deleteLater()
            self.list_zip_worker_thread = None
        
        if self.list_zip_worker:
            # Delete worker object
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
                        
                        # Add files to pending list using new unified tree
                        self._add_pending_files(files_to_add)
                        
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