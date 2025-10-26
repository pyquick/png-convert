# -*- coding: utf-8 -*-

from concurrent.futures import thread
from importlib import reload
import sys
import os
import threading
import time
target="com.pyquick.converter"
from patch import enable
enable(target)
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
    QDialog
)
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPalette
from PySide6.QtCore import QSize, Qt, QSettings, QPropertyAnimation, QEasingCurve, QTimer
import multiprocessing
from qfluentwidgets import Theme, setTheme,qconfig,SystemThemeListener
 # Keep for freeze_support, but remove direct Process usage
from settings.update_settings_gui import UpdateDialog
from settings.settings_gui import SettingsDialog
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

class IconButtonsWindow(QWidget):
    
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
        self.setWindowTitle("Converter")
        # Load theme setting immediately
        self.settings = QSettings("MyCompany", "ConverterApp")
        self.theme_setting = self.settings.value("theme", 0, type=int)
        self.themeListener = SystemThemeListener(self)
        
        self.path= os.path.dirname(os.path.abspath(__file__))
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

        self.init_ui()
        setTheme(Theme.AUTO)
        self.themeListener.start()
        qconfig.themeChanged.connect(self._onThemeChanged)
        # Apply theme based on settings or initial system detection
        self._apply_system_theme_from_settings() 
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止监听器线程
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
        # Create main layout
        main_layout = QVBoxLayout()
        
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

        # Set the main layout for the window
        self.setLayout(main_layout)

    def show_settings(self):
        settings_dialog = SettingsDialog(self)
        self._settings_dialog = settings_dialog  # Save dialog reference
        settings_dialog.show() # Use show() instead of exec() to keep dialog non-modal

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
        from qfluentwidgets import IndeterminateProgressBar
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
        from qfluentwidgets import IndeterminateProgressBar
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
        main_window = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, IconButtonsWindow):
                main_window = widget
                break
        
        if main_window:
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
        main_window = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, IconButtonsWindow):
                main_window = widget
                break
        
        if main_window:
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
    window = IconButtonsWindow(q_app=app)
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