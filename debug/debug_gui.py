# -*- coding: utf-8 -*-
"""
Debug Settings GUI Widget for Converter application
"""

import os
import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont

from UIkit import (
    SettingCardGroup, SwitchSettingCard, PushSettingCard, PrimaryPushSettingCard,
    FluentIcon, BodyLabel, CaptionLabel, TextBrowser, InfoBar, InfoBarPosition,
    setCustomStyleSheet, HeaderCardWidget, SingleDirectionScrollArea
)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'support'))
from support.debug_logger import DebugLogger


class DebugStatusCard(HeaderCardWidget):
    """Debug status card using HeaderCardWidget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('Debug Status')
        
        from UIkit import IconWidget, HyperlinkLabel
        
        # Create status icon
        self.statusIcon = IconWidget(FluentIcon.INFO, self)
        self.statusIcon.setFixedSize(16, 16)
        
        # Create status label
        self.statusLabel = BodyLabel('Debug mode is currently disabled.', self)
        
        # Create detail button
        self.detailButton = HyperlinkLabel('View Logs', self)
        self.detailButton.clicked.connect(self.view_logs)
        
        # Setup layout
        self.vBoxLayout = QVBoxLayout()
        self.hBoxLayout = QHBoxLayout()
        
        self.hBoxLayout.setSpacing(10)
        self.vBoxLayout.setSpacing(16)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        
        self.hBoxLayout.addWidget(self.statusIcon)
        self.hBoxLayout.addWidget(self.statusLabel)
        self.vBoxLayout.addLayout(self.hBoxLayout)
        self.vBoxLayout.addWidget(self.detailButton)
        
        self.viewLayout.addLayout(self.vBoxLayout)
        
        self.update_status(False, False)
    
    def update_status(self, debug_enabled, enhanced_logging):
        """Update status display based on debug settings"""
        if debug_enabled:
            from UIkit import InfoBarIcon
            self.statusIcon.setIcon(InfoBarIcon.SUCCESS)
            status_text = " Debug mode is ENABLED"
            if enhanced_logging:
                status_text += " with enhanced logging"
            status_text += ". All debug output is being logged to ~/.converter/log/"
            self.statusLabel.setStyleSheet("""
                BodyLabel {
                    color: #155724;
                }
            """)
        else:
            self.statusIcon.setIcon(FluentIcon.INFO)
            status_text = "Debug mode is DISABLED. Only basic console output will be shown."
            self.statusLabel.setStyleSheet("""
                BodyLabel {
                    color: #6c757d;
                }
            """)
        
        self.statusLabel.setText(status_text)
    
    def view_logs(self):
        """View log directory"""
        log_dir = os.path.expanduser("~/.converter/log")
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        try:
            if sys.platform == "darwin":  # macOS
                os.system(f"open '{log_dir}'")
            elif sys.platform == "win32":  # Windows
                os.system(f"explorer '{log_dir}'")
            else:  # Linux
                os.system(f"xdg-open '{log_dir}'")
        except Exception as e:
            print(f"Failed to open log directory: {e}")


class DebugSettingsWidget(QWidget):
    """Debug settings widget using UIkit SettingCard components"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.debug_logger = DebugLogger()
        self.settings = QSettings("MyCompany", "ConverterApp")
        self.setup_ui()
        self.connect_signals()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area
        self.scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.enableTransparentBackground()
        
        # Create scroll content widget
        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(20)
        
        # Create setting card groups
        self.debug_group = SettingCardGroup("Debug Configuration", scroll_content)
        self.log_group = SettingCardGroup("Log Management", scroll_content)
        
        # Create debug setting cards
        self.debug_enabled_card = SwitchSettingCard(
            FluentIcon.DEVELOPER_TOOLS,
            "Enable Debug Mode",
            "Enable debug logging for troubleshooting",
            parent=self.debug_group
        )
        
        self.enhanced_logging_card = SwitchSettingCard(
            FluentIcon.DOCUMENT,
            "Enhanced Logging",
            "Include module information in debug output",
            parent=self.debug_group
        )
        
        # Create log management cards
        self.test_debug_card = PrimaryPushSettingCard(
            "Test Debug Output",
            FluentIcon.CODE,
            "Generate test debug messages"
        )
        self.test_debug_card.clicked.connect(self.test_debug_output)
        
        self.view_logs_card = PushSettingCard(
            "View Log Directory",
            FluentIcon.FOLDER,
            "Open log folder in file explorer"
        )
        self.view_logs_card.clicked.connect(self.view_log_directory)
        
        self.clear_logs_card = PushSettingCard(
            "Clear Logs",
            FluentIcon.DELETE,
            "Remove all log files"
        )
        self.clear_logs_card.clicked.connect(self.clear_logs)
        
        # Add cards to groups
        self.debug_group.addSettingCards([
            self.debug_enabled_card,
            self.enhanced_logging_card
        ])
        
        self.log_group.addSettingCards([
            self.test_debug_card,
            self.view_logs_card,
            self.clear_logs_card
        ])
        
        # Add log info and preview to log group
        log_info_label = CaptionLabel("Log files are stored in ~/.converter/log/")
        self.log_group.vBoxLayout.addWidget(log_info_label)
        
        # Debug status card
        self.debug_status_card = DebugStatusCard(scroll_content)
        
        # Log preview area
        self.log_preview_browser = TextBrowser()
        self.log_preview_browser.setMinimumHeight(150)
        self.log_preview_browser.setPlaceholderText("Log preview will appear here when debug mode is enabled...")
        self.log_group.vBoxLayout.addWidget(self.log_preview_browser)
        
        # Add groups to scroll layout
        scroll_layout.addWidget(self.debug_group)
        scroll_layout.addWidget(self.debug_status_card)
        scroll_layout.addWidget(self.log_group)
        scroll_layout.addStretch()
        
        # Set scroll content
        self.scroll_area.setWidget(scroll_content)
        
        # Add scroll area to main layout
        main_layout.addWidget(self.scroll_area)
    
    def connect_signals(self):
        """Connect signals for auto-save"""
        self.debug_enabled_card.checkedChanged.connect(self.on_debug_setting_changed)
        self.enhanced_logging_card.checkedChanged.connect(self.on_enhanced_logging_changed)
    
    def load_settings(self):
        """Load current debug settings"""
        self.debug_enabled_card.setChecked(bool(self.settings.value("debug_enabled", False, type=bool)))
        self.enhanced_logging_card.setChecked(bool(self.settings.value("enhanced_logging", True, type=bool)))
        
        # Disable enhanced logging checkbox if debug mode is not enabled
        self.enhanced_logging_card.setEnabled(self.debug_enabled_card.isChecked())
        
        self.update_status_label()
    
    def update_status_label(self):
        """Update the status label based on current settings"""
        debug_enabled = self.debug_enabled_card.isChecked()
        enhanced_logging = self.enhanced_logging_card.isChecked()
        
        self.debug_status_card.update_status(debug_enabled, enhanced_logging)
    
    def test_debug_output(self):
        """Test debug output functionality"""
        self.debug_logger.log_debug("This is a test debug message from Debug Settings GUI")
        self.debug_logger.log_info("This is a test info message from Debug Settings GUI")
        
        # Update log preview
        log_dir = os.path.expanduser("~/.converter/log")
        if os.path.exists(log_dir):
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            if log_files:
                latest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
                log_path = os.path.join(log_dir, latest_log)
                
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Show last 10 lines
                        lines = content.strip().split('\n')
                        preview = '\n'.join(lines[-10:]) if len(lines) > 10 else content
                        self.log_preview_browser.setPlainText(preview)
                except Exception as e:
                    self.log_preview_browser.setPlainText(f"Error reading log file: {e}")
    
    def view_log_directory(self):
        """Open log directory in file explorer"""
        log_dir = os.path.expanduser("~/.converter/log")
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        try:
            if sys.platform == "darwin":  # macOS
                os.system(f"open '{log_dir}'")
            elif sys.platform == "win32":  # Windows
                os.system(f"explorer '{log_dir}'")
            else:  # Linux
                os.system(f"xdg-open '{log_dir}'")
        except Exception as e:
            self.debug_logger.log_error(f"Failed to open log directory: {e}")
    
    def clear_logs(self):
        """Clear all log files"""
        log_dir = os.path.expanduser("~/.converter/log")
        
        if os.path.exists(log_dir):
            try:
                for file in os.listdir(log_dir):
                    if file.endswith('.log'):
                        os.remove(os.path.join(log_dir, file))
                
                self.log_preview_browser.setPlainText("All log files have been cleared.")
                self.debug_logger.log_info("Log files cleared via GUI")
                
            except Exception as e:
                self.log_preview_browser.setPlainText(f"Error clearing logs: {e}")
                print(f"ERROR: Failed to clear logs: {e}")
        else:
            self.log_preview_browser.setPlainText("Log directory does not exist.")
    
    def on_debug_setting_changed(self):
        """Handle debug setting change and trigger auto-save"""
        debug_enabled = self.debug_enabled_card.isChecked()
        self.settings.setValue("debug_enabled", debug_enabled)
        self.settings.sync()
        
        # Enable/disable enhanced logging checkbox based on debug mode
        self.enhanced_logging_card.setEnabled(debug_enabled)
        
        # If debug mode is disabled, also disable enhanced logging
        if not debug_enabled:
            self.enhanced_logging_card.setChecked(False)
            self.settings.setValue("enhanced_logging", False)
            self.settings.sync()
        
        # Reinitialize debug logger with new settings
        self.debug_logger = DebugLogger()
        
        self.update_status_label()
        
        if debug_enabled:
            self.debug_logger.log_info("Debug mode enabled via GUI (auto-save)")
        else:
            self.debug_logger.log_info("Debug mode disabled via GUI (auto-save)")
    
    def on_enhanced_logging_changed(self):
        """Handle enhanced logging setting change and trigger auto-save"""
        enhanced_logging = self.enhanced_logging_card.isChecked()
        self.settings.setValue("enhanced_logging", enhanced_logging)
        self.settings.sync()
        
        self.update_status_label()
        
        if enhanced_logging:
            self.debug_logger.log_info("Enhanced logging enabled via GUI (auto-save)")
        else:
            self.debug_logger.log_info("Enhanced logging disabled via GUI (auto-save)")


if __name__ == "__main__":
    """Standalone test"""
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    widget = DebugSettingsWidget()
    widget.resize(800, 600)
    widget.show()
    
    sys.exit(app.exec())
