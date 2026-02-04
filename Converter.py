# -*- coding: utf-8 -*-

from concurrent.futures import thread
from importlib import reload
import sys
import os
import threading
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpacerItem,
    QGridLayout,
    QSizePolicy,
    QGroupBox,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFrame,
    QStackedWidget
)
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPalette, QColor
from PySide6.QtCore import QSize, Qt, QSettings, QPropertyAnimation, QEasingCurve, QTimer, Signal
import multiprocessing
from UIkit import (
    HeaderCardWidget, ImageLabel, Theme, setTheme, qconfig, SystemThemeListener,
    FluentWindow, NavigationItemPosition,
    CardWidget, PushButton, PrimaryPushButton, IconWidget,
    BodyLabel, CaptionLabel, SubtitleLabel, TitleLabel, LargeTitleLabel,
    FluentIcon as FIF, setFont, TransparentToolButton, SegmentedWidget,
    setCustomStyleSheet, ElevatedCardWidget, ProgressBar, FlowLayout,
    ScrollArea
)
from UIkit.components.widgets.card_widget import SimpleCardWidget
from settings.settings_gui import SettingsDialog
from patch import enable
enable("com.pyquick.converter")
from con import CON # Import CON instance for theme settings
# Encoding settings have been moved to debug_logger for handling
# --- Helper function to create placeholder icons ---
# Since we cannot directly generate .icns files, we create PNG files as examples.
# Please place the AppIcon.icns and zip.icns files in the same directory as this script.
def create_placeholder_icon(path: str, color: str, text: str):
    """Create a simple PNG placeholder icon if the icon file does not exist."""
    if not os.path.exists(path):
        pixmap = QPixmap(128, 128)
        pixmap.fill(color)
        painter = QPainter(pixmap)
        painter.setPen("white")
        font = painter.font()
        font.setPointSize(48)
        
        painter.setFont(font)
        # Qt.AlignCenter is enum value 1
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        pixmap.save(path)
        print(f"Note: '{path}' not found. A placeholder icon has been created.")
        return True
    # If it's an .icns file, use it directly
    elif path.endswith(".icns") and os.path.exists(path):
        return True
    # If a non-.icns placeholder file exists, consider it successful
    elif not path.endswith(".icns") and os.path.exists(path):
        return True
    return False


class AppCard(CardWidget):
    """Application card widget"""
    
    def __init__(self, icon_path, title, content, app_type, parent=None):
        super().__init__(parent)
        self.title = title
        self.content = content
        self.app_type = app_type
        self.icon_path = icon_path
        self.icon_widget = ImageLabel(icon_path, self)
        self.title_label = BodyLabel(self.title, self)
        self.content_label = CaptionLabel(self.content, self)
        self.icon_widget.scaledToHeight(68)
        self.icon_widget.setFixedSize(48, 48) 
        self.content_label.setTextColor(QColor("#606060"), QColor("#d2d2d2"))
        self.setFixedHeight(73)
        self.h_box_layout = QHBoxLayout(self)
        self.v_box_layout = QVBoxLayout()
       
       
        # Configure layouts
        self.h_box_layout.setContentsMargins(20, 11, 11, 11)
        self.h_box_layout.setSpacing(15)
        self.v_box_layout.setContentsMargins(0, 0, 0, 0)
        self.v_box_layout.setSpacing(0)


        self.open_button = PrimaryPushButton('Open', self)
        self.open_button.setFixedWidth(120)
        self.more_button = TransparentToolButton(FIF.MORE, self)
        self.more_button.setFixedSize(32, 32)

        # Add components to layouts
        self.h_box_layout.addWidget(self.icon_widget)
        
        self.v_box_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.v_box_layout.addWidget(self.content_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.h_box_layout.addLayout(self.v_box_layout)
        
        self.h_box_layout.addStretch(1)
        self.h_box_layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignRight)
        self.h_box_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignRight)
        
        self.open_button.clicked.connect(self.on_open_clicked)
    
    
    def on_open_clicked(self):
        """Handle open button clicked event"""
        if self.app_type == 'image':
            run_image_app()
        elif self.app_type == 'arc':
            run_zip_app()


class HomeInterface(QFrame):
    """Home interface showing app cards"""
    
    def __init__(self, icon_paths, parent=None):
        super().__init__(parent)
        self.icon_paths = icon_paths
        self.setObjectName("home_interface")
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components"""
        # Layouts
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 35, 40, 35)
        main_layout.setSpacing(25)
        
        # Title
        title_label = LargeTitleLabel("Converter")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Image Converter card
        image_card = AppCard(
            icon_path=self.icon_paths['app_icon_path'],
            title="Image Converter",
            content="Convert PNG images to ICNS format for macOS applications",
            app_type="image"
        )
        image_card.setBorderRadius(35)
        main_layout.addWidget(image_card)

        # Archive Converter card
        archive_card = AppCard(
            icon_path=self.icon_paths['zip_icon_path'],
            title="Archive Converter",
            content="Create and extract ZIP, RAR, and 7Z archive files",
            app_type="arc"
        )
        main_layout.addWidget(archive_card)
        archive_card.setBorderRadius(35)
        
        # Add stretch to push content to top
        main_layout.addStretch(1)


class SettingsInterface(QFrame):
    """Settings interface"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_interface")
        self.init_ui()
        self.load_settings()
        self._connect_settings_signals()
    
    def init_ui(self):
        """Initialize UI components"""
        # Layouts
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Create SegmentedWidget and QStackedWidget
        self.segmented_widget = SegmentedWidget(self)
        setCustomStyleSheet(self.segmented_widget, CON.qss_seg, CON.qss_seg)
        self.stacked_widget = QStackedWidget(self)
        
        # General page
        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(15, 15, 15, 15)
        general_layout.setSpacing(15)
        
        from settings.general_settings import GeneralSettingsWidget
        self.general_widget = GeneralSettingsWidget()
        self.general_widget.setObjectName("general_widget")
        general_layout.addWidget(self.general_widget)
        general_layout.addStretch()
        
        self.stacked_widget.addWidget(general_page)
        
        # Debug page
        debug_page = QWidget()
        debug_layout = QVBoxLayout(debug_page)
        debug_layout.setContentsMargins(15, 15, 15, 15)
        debug_layout.setSpacing(15)
        
        from debug.debug_gui import DebugSettingsWidget
        self.debug_widget = DebugSettingsWidget()
        self.debug_widget.setObjectName("debug_widget")
        debug_layout.addWidget(self.debug_widget)
        debug_layout.addStretch()
        
        self.stacked_widget.addWidget(debug_page)
        
        # Update page
        update_page = QWidget()
        update_layout = QVBoxLayout(update_page)
        update_layout.setContentsMargins(15, 15, 15, 15)
        update_layout.setSpacing(15)
        
        from settings.update_settings_gui import UpdateSettingsWidget
        self.update_group = UpdateSettingsWidget()
        self.update_group.setObjectName("update_group")
        update_layout.addWidget(self.update_group)
        update_layout.addStretch()
        
        self.stacked_widget.addWidget(update_page)
        
        # Add tab items
        self.add_sub_interface(general_page, "general_page", "General")
        self.add_sub_interface(debug_page, "debug_page", "Debug")
        self.add_sub_interface(update_page, "update_page", "Update")
        
        # Connect tab change signal
        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)
        self.stacked_widget.setCurrentIndex(0)
        self.segmented_widget.setCurrentItem("general_page")
        
        # Add to main layout
        main_layout.addWidget(self.segmented_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(self.stacked_widget, 1)
    
    def add_sub_interface(self, widget: QWidget, object_name: str, text: str):
        """Add sub-page to SegmentedWidget and QStackedWidget"""
        widget.setObjectName(object_name)
        self.segmented_widget.addItem(
            routeKey=object_name,
            text=text,
            onClick=lambda: self.stacked_widget.setCurrentWidget(widget)
        )
    
    def on_current_index_changed(self, index):
        """Handle current page change"""
        widget = self.stacked_widget.widget(index)
        if widget:
            self.segmented_widget.setCurrentItem(widget.objectName())
    
    def load_settings(self):
        """Load settings from QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        # Theme settings - always set to System Default (index 0)
        settings.setValue("theme", 0) # Force save System Default
        
        # Load General settings (includes Image Converter settings)
        if hasattr(self, 'general_widget'):
            self.general_widget.load_settings()
        
        # Debug settings are now handled by the DebugSettingsWidget itself
    
    def _connect_settings_signals(self):
        """Connect all settings controls' signals to real-time saving"""
        # Connect general widget settings
        if hasattr(self, 'general_widget'):
            self.general_widget.settings_changed.connect(self.on_settings_changed)
        
        # Connect debug widget auto-save signals (already handled in DebugSettingsWidget)
        # Debug settings are now handled by the DebugSettingsWidget itself
        
        # Connect update dialog settings
        # Update settings related signal connections have been removed, handled internally by UpdateDialog
    
    def on_settings_changed(self):
        """Handle any settings change and trigger auto-save"""
        self.save_settings_async()
    
    def save_settings_async(self):
        """Asynchronously save settings in a separate thread"""
        def save_thread():
            settings = QSettings("MyCompany", "ConverterApp")
            # Theme settings - always System Default
            settings.setValue("theme", 0)
            
            # Save General settings
            if hasattr(self, 'general_widget'):
                self.general_widget.save_settings()
            
            # Debug settings are now handled by the DebugSettingsWidget itself
            
            # Image converter settings are now saved by the general widget
            # No separate image converter widget exists anymore
            
            settings.sync() # Ensure settings are written to disk
        
        # Start separate thread to execute save operation
        threading.Thread(target=save_thread).start()


class MainWindow(FluentWindow):
    """Main application window"""
    
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
        return self._load_qss_file('launcher_light.qss')

    @property
    def DARK_QSS(self):
        """Load dark theme QSS from external file"""
        return self._load_qss_file('launcher_dark.qss')

    
    def __init__(self, q_app: QApplication):
        super().__init__()
        self._q_app = q_app # Store QApplication instance
        self.settings = QSettings("MyCompany", "ConverterApp")
        self.theme_setting = self.settings.value("theme", 0, type=int)
        self.themeListener = SystemThemeListener(self)
        
        self.path = os.path.dirname(os.path.abspath(__file__))
        # Define paths for icon files
        self.app_icon_path = os.path.join(self.path,"AppIcon.png")
        self.appd_icon_path = os.path.join(self.path,"AppIcond.png")
        self.zip_icon_path = os.path.join(self.path,"zip.png")
        self.zipd_icon_path = os.path.join(self.path,"zipd.png")

        # Check if icon files exist and create placeholders if needed
        if not os.path.exists(self.app_icon_path):
            print("Note: AppIcon.png file not found. Will try to create a PNG placeholder icon.")
            create_placeholder_icon(self.app_icon_path, "dodgerblue", "App")
        if not os.path.exists(self.appd_icon_path):
            print("Note: AppIcond.png file not found. Will try to create a PNG placeholder icon.")
            create_placeholder_icon(self.appd_icon_path, "darkblue", "AppD") # Changed placeholder color for dark mode app icon
        
        if not os.path.exists(self.zip_icon_path):
            print("Note: zip.png file not found. Will try to create a PNG placeholder icon.")
            create_placeholder_icon(self.zip_icon_path, "gray", "Zip")

        if not os.path.exists(self.zipd_icon_path):
            print("Note: zipd.png file not found. Will try to create a PNG placeholder icon.")
            create_placeholder_icon(self.zipd_icon_path, "dimgray", "ZipD")

        # Icon paths dictionary for home interface
        self.icon_paths = {
            'app_icon_path': self.app_icon_path,
            'appd_icon_path': self.appd_icon_path,
            'zip_icon_path': self.zip_icon_path,
            'zipd_icon_path': self.zipd_icon_path
        }
        
        # Initialize interfaces
        self.init_interfaces()
        
        # Initialize window
        self.init_window()
        self.init_navigation()
        
        # Apply theme
        setTheme(Theme.AUTO)
        self.themeListener.start()
        qconfig.themeChanged.connect(self._onThemeChanged)
        self._apply_system_theme_from_settings()
    
    def init_interfaces(self):
        """Initialize sub-interfaces"""
        # Create home interface with app cards
        self.home_interface = HomeInterface(self.icon_paths)
        
        # Create settings interface
        self.settings_interface = SettingsInterface()
    
    def init_window(self):
        """Initialize window properties"""
        self.setWindowTitle("Converter")
        self.setWindowIcon(QIcon(self.app_icon_path))
        self.resize(900, 700)
    
    def init_navigation(self):
        """Initialize navigation items"""
        self.addSubInterface(
            self.home_interface, 
            FIF.HOME, 
            'Home'
        )
        
        self.addSubInterface(
            self.settings_interface, 
            FIF.SETTING, 
            'Settings',
            NavigationItemPosition.BOTTOM
        )
    def closeEvent(self, event):
        """窗口关闭事件"""
        # Check if task mode is enabled and if any sub-windows are open
        task_mode_enabled = self.settings.value("task_mode", False, type=bool)
        if task_mode_enabled:
            has_open_windows = False
            # Get all top level widgets
            for widget in self._q_app.topLevelWidgets():
                # Check if there are any image or arc windows open
                if widget is not self:
                    window_title = widget.windowTitle()
                    if "Image Converter" in window_title or "Archive File Processing Tool" in window_title:
                        has_open_windows = True
                        break
            
            if has_open_windows:
                # Show modal dialog explaining why closing is not allowed
                QMessageBox.information(
                    self,
                    "Cannot Close",
                    "Task Mode is enabled and sub-windows are open. Please close all sub-windows first.",
                    QMessageBox.StandardButton.Ok
                )
                event.ignore()
                return
        
        # Stop listener thread
        if hasattr(self, 'themeListener'):
            self.themeListener.terminate()
            self.themeListener.deleteLater()
        super().closeEvent(event)
    def _onThemeChanged(self, theme: Theme):
        """主题变化处理"""
        # 更新界面以响应主题变化
        self.update()
        setTheme(Theme.AUTO)
    def _apply_system_theme(self, is_dark_mode): # This method will now be primarily for paletteChanged signal
        # Only apply system theme if setting is System Default
        if self.settings.value("theme", 0, type=int) == 0:
            self._apply_theme(is_dark_mode)

    def _apply_system_theme_from_settings(self):
        theme_setting = self.settings.value("theme", 0, type=int)
        if self._q_app:
            if theme_setting == 0: # System Default
                is_dark_mode = self._q_app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5
                self._apply_theme(is_dark_mode)
           

    def _apply_theme(self, is_dark_mode):
        if is_dark_mode:
            self.setStyleSheet(self.DARK_QSS)
            if hasattr(self, 'button_zip'):
                self.button_zip.setIcon(QIcon(self.zipd_icon_path))
            if hasattr(self, 'button_app'):
                self.button_app.setIcon(QIcon(self.appd_icon_path))
        else:
            self.setStyleSheet(self.LIGHT_QSS)
            if hasattr(self, 'button_zip'):
                self.button_zip.setIcon(QIcon(self.zip_icon_path))
            if hasattr(self, 'button_app'):
                self.button_app.setIcon(QIcon(self.app_icon_path))
        
        # Notify all sub-widgets to update theme
        self.update_sub_widgets_theme(is_dark_mode)
    
    def update_sub_widgets_theme(self, is_dark_mode):
        """Notify all sub-widgets to update theme"""
        # Update settings dialog theme (if already created)
        if hasattr(self, '_settings_dialog') and self._settings_dialog:
            self._settings_dialog.apply_theme(is_dark_mode)
    
    def init_ui(self):
        # Create main horizontal layout for sidebar and content
        main_horizontal_layout = QHBoxLayout()
        
        # --- Task Sidebar ---
        # Create sidebar widget
        from UIkit import PushButton, setCustomStyleSheet
        
        # Keep using QWidget as the container
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setObjectName("sidebar_widget")
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        
        # Sidebar title
        sidebar_title = QLabel("Task Manager")
        sidebar_title.setObjectName("sidebar_title")
        sidebar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(sidebar_title)
        
        # Task list
        self.task_list = QListWidget()
        self.task_list.setObjectName("task_list")
        from con import CON
        setCustomStyleSheet(self.task_list, CON.qss_combo, CON.qss_combo)
        self.sidebar_layout.addWidget(self.task_list)
        
        # Sidebar control buttons
        sidebar_controls = QHBoxLayout()
        
        # Clear completed tasks button
        self.clear_tasks_button = PushButton("Clear Completed")
        self.clear_tasks_button.setObjectName("clear_tasks_button")
        self.clear_tasks_button.setIconSize(QSize(16, 16))
        setCustomStyleSheet(self.clear_tasks_button, CON.qss, CON.qss)
        sidebar_controls.addWidget(self.clear_tasks_button)
        
        # Collapse/Expand button
        self.toggle_sidebar_button = PushButton("Collapse")
        self.toggle_sidebar_button.setObjectName("toggle_sidebar_button")
        self.toggle_sidebar_button.setIconSize(QSize(16, 16))
        self.toggle_sidebar_button.clicked.connect(self.toggle_sidebar)
        setCustomStyleSheet(self.toggle_sidebar_button, CON.qss, CON.qss)
        sidebar_controls.addWidget(self.toggle_sidebar_button)
        
        self.sidebar_layout.addLayout(sidebar_controls)
        
        # Add sidebar to main horizontal layout
        self.sidebar_widget.setFixedWidth(250)
        main_horizontal_layout.addWidget(self.sidebar_widget)
        
        # --- Main Content ---
        # Create main content widget with vertical layout
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        
        main_layout.setSpacing(25)  # Increased spacing for better visual separation
        main_layout.setContentsMargins(40, 35, 40, 35)  # Better margins
        
        # Add title
        title_label = QLabel("Converter")
        title_label.setObjectName("title_label")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # --- Image Converter Group ---
        image_group = QGroupBox("Image Converter")
        image_group.setObjectName("image_group")
        image_layout = QVBoxLayout(image_group)
        image_layout.setSpacing(10)
        image_layout.setContentsMargins(15, 15, 15, 15)
        
        # Image Converter Button
        app_icon = QIcon(self.app_icon_path)
        self.button_app = QPushButton("Image Converter")
        self.button_app.setObjectName("button_app")
        self.button_app.setIcon(app_icon)
        self.button_app.setIconSize(QSize(40, 40))  # Consistent icon size
        self.button_app.setMinimumHeight(55)  # Consistent height
        self.button_app.clicked.connect(run_image_app)
        
        # Center the button
        app_button_layout = QHBoxLayout()
        app_button_layout.addStretch()
        app_button_layout.addWidget(self.button_app)
        app_button_layout.addStretch()
        image_layout.addLayout(app_button_layout)
        
        # Description for Image Converter - moved below button
        image_desc = QLabel("Convert PNG images to ICNS format for macOS applications")
        image_desc.setObjectName("description_label")
        image_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_desc.setWordWrap(True)
        image_layout.addWidget(image_desc)
        
        main_layout.addWidget(image_group)

        # --- Archive Converter Group ---
        archive_group = QGroupBox("Archive Converter")
        archive_group.setObjectName("archive_group")
        archive_layout = QVBoxLayout(archive_group)
        archive_layout.setSpacing(10)
        archive_layout.setContentsMargins(15, 15, 15, 15)
        
        # Archive Converter Button
        zip_icon = QIcon(self.zip_icon_path)
        self.button_zip = QPushButton(" Archive Converter")
        self.button_zip.setObjectName("button_zip")
        self.button_zip.setIcon(zip_icon)
        self.button_zip.setIconSize(QSize(40, 40))  # Consistent icon size
        self.button_zip.setMinimumHeight(55)  # Consistent height
        self.button_zip.clicked.connect(run_zip_app)
        
        # Center the button
        zip_button_layout = QHBoxLayout()
        zip_button_layout.addStretch()
        zip_button_layout.addWidget(self.button_zip)
        zip_button_layout.addStretch()
        archive_layout.addLayout(zip_button_layout)
        
        # Description for Archive Converter - moved below button
        archive_desc = QLabel("Create and extract ZIP, RAR, and 7Z archive files")
        archive_desc.setObjectName("description_label")
        archive_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        archive_desc.setWordWrap(True)
        archive_layout.addWidget(archive_desc)
        
        main_layout.addWidget(archive_group)
        
        # Add vertical space
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Settings button - positioned below zip button
        settings_button = QPushButton(QIcon.fromTheme("preferences-system"), " Settings")
        settings_button.setObjectName("settings_button")
        settings_button.setIconSize(QSize(20, 20))
        settings_button.clicked.connect(self.show_settings)

        settings_button_layout = QHBoxLayout()
        settings_button_layout.addStretch()
        settings_button_layout.addWidget(settings_button)
        settings_button_layout.addStretch()
        main_layout.addLayout(settings_button_layout)
        
        # Add content widget to main horizontal layout
        main_horizontal_layout.addWidget(content_widget, 1)  # Give content stretch priority
        
        # Add task count indicator (visible when sidebar is collapsed)
        self.task_count_indicator = QLabel("0")
        self.task_count_indicator.setObjectName("task_count_indicator")
        self.task_count_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.task_count_indicator.setStyleSheet("""
            background-color: #0078d4;
            color: white;
            border-radius: 12px;
            padding: 5px 10px;
            font-weight: bold;
        """)
        self.task_count_indicator.setFixedSize(30, 30)
        self.task_count_indicator.hide()  # Initially hidden
        
        # Set the main horizontal layout for the window
        self.setLayout(main_horizontal_layout)

    def show_settings(self):
        settings_dialog = SettingsDialog(self)
        self._settings_dialog = settings_dialog  # Save dialog reference
        settings_dialog.show() # Use show() instead of exec() to keep dialog non-modal
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        if self.sidebar_widget.isVisible():
            # Hide sidebar and show task count indicator
            self.sidebar_widget.hide()
            self.task_count_indicator.show()
            self.toggle_sidebar_button.setText("Expand")
        else:
            # Show sidebar and hide task count indicator
            self.sidebar_widget.show()
            self.task_count_indicator.hide()
            self.toggle_sidebar_button.setText("Collapse")

class AnimatedAppDialog(QDialog):
    def __init__(self, parent=None, app_type=""):
        super().__init__(parent)
        self.app_type = app_type
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)  # Non-modal
        
        # Animation for showing the dialog
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(250)  # Duration in milliseconds
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Animation for closing the dialog
        self.close_animation = QPropertyAnimation(self, b"windowOpacity")
        self.close_animation.setDuration(200)
        self.close_animation.setStartValue(1.0)
        self.close_animation.setEndValue(0.0)
        self.close_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.close_animation.finished.connect(self._finish_close)
        
        self._should_close = False
        
    def showEvent(self, event):
        # Start animation when the dialog is shown
        self.animation.start()
        super().showEvent(event)
        # Start the external app after animation
        QTimer.singleShot(300, self.start_external_app)
        
    def closeEvent(self, event):
        if not self._should_close:
            event.ignore()
            self.close_animation.start()
        else:
            super().closeEvent(event)
            
    def _finish_close(self):
        self._should_close = True
        self.close()
        
    def start_external_app(self):
        """Start the external app in a separate process"""
        try:
            if self.app_type == "image":
                multiprocessing.Process(target=run_image).start()
            elif self.app_type == "zip":
                multiprocessing.Process(target=run_zip).start()
        except Exception as e:
            print(f"Error starting {self.app_type} app: {e}")
        finally:
            # Close the animation dialog after starting the external app
            QTimer.singleShot(1000, self.close)

class ImageAppDialog(AnimatedAppDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "image")
        self.setFixedSize(400, 200)
        self.center_on_screen()
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title = QLabel("Image Converter")
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Starting...")
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # Loading indicator
        from UIkit import IndeterminateProgressBar
        progress = IndeterminateProgressBar()
        layout.addWidget(progress)
        
    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )

class ZipAppDialog(AnimatedAppDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "zip")
        self.setFixedSize(400, 200)
        self.center_on_screen()
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title = QLabel("Archive Manager")
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Starting...")
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # Loading indicator
        from UIkit import IndeterminateProgressBar
        progress = IndeterminateProgressBar()
        layout.addWidget(progress)
        
    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )

def run_zip():
    from arc_gui import ZipAppRunner
    app_runner = ZipAppRunner()
    app_runner.MainLoop()
def run_image():
    from image_converter import ICNSConverterApp
    app_runner = ICNSConverterApp()
    app_runner.MainLoop()
def run_image_app():
    """Run the image converter app with animation"""
    try:
        # Get the main window instance
        app = QApplication.instance()
        if app is None:
            return
        main_window = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, MainWindow):
                main_window = widget
                break
        
        if main_window:
            # Check if task mode is enabled
            task_mode_enabled = main_window.settings.value("task_mode", False, type=bool)
            
            if task_mode_enabled:
                # In task mode, run directly in the same process
                run_image()
            else:
                # Create and show the animation dialog
                dialog = ImageAppDialog(main_window)
                dialog.show()
        else:
            # Fallback to multiprocessing if no main window found
            multiprocessing.Process(target=run_image).start()
            
    except Exception as e:
        print(f"Error running image app: {e}")
        # Fallback to multiprocessing
        multiprocessing.Process(target=run_image).start()

def run_zip_app():
    """Run the archive manager app with animation"""
    try:
        # Get the main window instance
        app = QApplication.instance()
        if app is None:
            return
        main_window = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, MainWindow):
                main_window = widget
                break
        
        if main_window:
            # Check if task mode is enabled
            task_mode_enabled = main_window.settings.value("task_mode", False, type=bool)
            
            if task_mode_enabled:
                # In task mode, run directly in the same process
                run_zip()
            else:
                # Create and show the animation dialog
                dialog = ZipAppDialog(main_window)
                dialog.show()
        else:
            # Fallback to multiprocessing if no main window found
            multiprocessing.Process(target=run_zip).start()
            
    except Exception as e:
        print(f"Error running zip app: {e}")
        # Fallback to multiprocessing
        multiprocessing.Process(target=run_zip).start()



if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    
    # Initialize debug logger
    try:
        from support.debug_logger import debug_logger
        debug_logger.setup_logger()
        if debug_logger.is_debug_enabled():
            print("Debug mode enabled - logging to ~/.converter/log")
    except Exception as e:
        print(f"Failed to initialize debug logger: {e}")
    
    from support.toggle import theme_manager
    theme_manager.start()
    setTheme(Theme.AUTO)
    window = MainWindow(q_app=app)
    window.show()
    # Connect to palette changes for real-time theme switching ONLY if setting is System Default
    app.paletteChanged.connect(lambda: window._apply_system_theme(app.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5))
    exit_code = app.exec()
    
    # Cleanup debug logger
    try:
        from support.debug_logger import debug_logger
        debug_logger.restore_output()
    except:
        pass
    
    theme_manager.stop()
    sys.exit(exit_code)