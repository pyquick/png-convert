# -*- coding: utf-8 -*-
"""
Debug Settings GUI Widget for Converter application
"""

import os
import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QCheckBox, QGroupBox, QSpacerItem, QSizePolicy,
    QPushButton, QTextBrowser
)
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont
from qfluentwidgets import (
    CheckBox, TextBrowser, IndeterminateProgressBar,
    ProgressBar, PrimaryPushButton
)

import sys
import os
from qfluentwidgets import *
# Add support directory to path for debug_logger import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'support'))
from support.debug_logger import DebugLogger


class DebugSettingsWidget(QWidget):
    """Debug Settings GUI Widget"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Debug Settings")
        self.debug_logger = DebugLogger()
        self.settings = QSettings("MyCompany", "ConverterApp")
        
        self.init_ui()
        self.load_settings()
        self.connect_auto_save_signals()

    def init_ui(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        # Debug Settings Group
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QVBoxLayout()
        debug_layout.setContentsMargins(25, 25, 25, 25)
        debug_layout.setSpacing(20)
        
        # Add top spacing
        debug_layout.addSpacerItem(QSpacerItem(0, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        
        # Debug Mode Toggle
        self.debug_enabled_checkbox = CheckBox("Enable Debug Mode")
        self.debug_enabled_checkbox.setMinimumHeight(60)
        # Signal connection will be done in connect_auto_save_signals
        debug_layout.addWidget(self.debug_enabled_checkbox)
        
        # Enhanced Logging
        self.enhanced_logging_checkbox = CheckBox("Enable Enhanced Logging (with module info)")
        self.enhanced_logging_checkbox.setMinimumHeight(60)
        # Signal connection will be done in connect_auto_save_signals
        debug_layout.addWidget(self.enhanced_logging_checkbox)
        
        # Log File Info
        log_info_layout = QHBoxLayout()
        log_info_layout.addWidget(QLabel("Log Directory:"))
        self.log_dir_label = QLabel("~/.converter/log/")
        self.log_dir_label.setWordWrap(True)
        self.log_dir_label.setStyleSheet("QLabel { color: #666; }")  
        log_info_layout.addWidget(self.log_dir_label)
        log_info_layout.addStretch()
        debug_layout.addLayout(log_info_layout)
        
        # Status Label
        self.status_label = QLabel("Debug mode is currently disabled.")
        self.status_label.setMinimumHeight(60)
        self.status_label.setMinimumWidth(550)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            QLabel { 
                padding: 8px; 
                background-color: #f8f9fa; 
                border-radius: 16px; 
                border: 1px solid #e9ecef;
            }
        """)
        debug_layout.addWidget(self.status_label)
        
        # Log Preview Area
        self.log_preview_browser = TextBrowser()
        self.log_preview_browser.setMinimumHeight(150)
        self.log_preview_browser.setPlaceholderText("Log preview will appear here when debug mode is enabled...")
        debug_layout.addWidget(self.log_preview_browser)
        
        # Buttons Container
        button_container = QHBoxLayout()
        button_container.setSpacing(15)
        from con import CON
        # Test Debug Button
        self.test_debug_button = PrimaryPushButton("Test Debug Output")
        setCustomStyleSheet(self.test_debug_button, CON.qss_debug, CON.qss_debug)
        self.test_debug_button.setFixedSize(180, 60)
        self.test_debug_button.clicked.connect(self.test_debug_output)
        
        # View Logs Button
        self.view_logs_button = PrimaryPushButton("View Log Directory")
        self.view_logs_button.setFixedSize(180, 60)
        setCustomStyleSheet(self.view_logs_button, CON.qss_debug, CON.qss_debug)
        self.view_logs_button.clicked.connect(self.view_log_directory)
        
        # Clear Logs Button
        self.clear_logs_button = PrimaryPushButton("Clear Logs")
        self.clear_logs_button.setFixedSize(180, 60)
        setCustomStyleSheet(self.clear_logs_button, CON.qss_debug, CON.qss_debug)
        self.clear_logs_button.clicked.connect(self.clear_logs)
        
        button_container.addStretch()
        button_container.addWidget(self.test_debug_button)
        button_container.addWidget(self.view_logs_button)
        button_container.addWidget(self.clear_logs_button)
        button_container.addStretch()
        debug_layout.addLayout(button_container)
        
        # Add bottom spacing
        debug_layout.addSpacerItem(QSpacerItem(0, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        
        debug_group.setLayout(debug_layout)
        main_layout.addWidget(debug_group)
        
        self.setLayout(main_layout)
        
        # Set button fonts
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.test_debug_button.setFont(font)
        self.view_logs_button.setFont(font)
        self.clear_logs_button.setFont(font)

    def load_settings(self):
        """Load current debug settings"""
        debug_enabled = bool(self.settings.value("debug_enabled", False, type=bool))
        enhanced_logging = bool(self.settings.value("enhanced_logging", True, type=bool))
        
        self.debug_enabled_checkbox.setChecked(debug_enabled)
        self.enhanced_logging_checkbox.setChecked(enhanced_logging)
        
        # Disable enhanced logging checkbox if debug mode is not enabled
        self.enhanced_logging_checkbox.setEnabled(debug_enabled)
        
        self.update_status_label()

    def update_status_label(self):
        """Update the status label based on current settings"""
        debug_enabled = self.debug_enabled_checkbox.isChecked()
        enhanced_logging = self.enhanced_logging_checkbox.isChecked()
        
        if debug_enabled:
            status_text = "✓ Debug mode is ENABLED"
            if enhanced_logging:
                status_text += " with enhanced logging"
            status_text += ". All debug output is being logged to ~/.converter/log/"
            self.status_label.setStyleSheet("""
                QLabel { 
                    padding: 8px; 
                    background-color: #e8f5e8; 
                    border-radius: 16px; 
                    border: 1px solid #d4edda;
                    color: #155724;
                }
            """)
        else:
            status_text = "Debug mode is DISABLED. Only basic console output will be shown."
            self.status_label.setStyleSheet("""
                QLabel { 
                    padding: 8px; 
                    background-color: #f8f9fa; 
                    border-radius: 16px; 
                    border: 1px solid #e9ecef;
                    color: #6c757d;
                }
            """)
        
        self.status_label.setText(status_text)



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
        """Open the log directory in file explorer"""
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
                # Use print instead of log_error to avoid potential recursion
                print(f"ERROR: Failed to clear logs: {e}")
        else:
            self.log_preview_browser.setPlainText("Log directory does not exist.")
    
    def connect_auto_save_signals(self):
        """Connect all UI controls to auto-save functionality"""
        # Connect checkboxes to auto-save - the toggle methods already call auto_save_settings
        # But we also add a direct connection to ensure the signal is triggered
        self.debug_enabled_checkbox.stateChanged.connect(self.on_debug_setting_changed)
        self.enhanced_logging_checkbox.stateChanged.connect(self.on_enhanced_logging_changed)
    
    def on_debug_setting_changed(self):
        """Handle debug setting change and trigger auto-save"""
        debug_enabled = self.debug_enabled_checkbox.isChecked()
        self.settings.setValue("debug_enabled", debug_enabled)
        self.settings.sync()
        
        # Enable/disable enhanced logging checkbox based on debug mode
        self.enhanced_logging_checkbox.setEnabled(debug_enabled)
        
        # If debug mode is disabled, also disable enhanced logging
        if not debug_enabled:
            self.enhanced_logging_checkbox.setChecked(False)
            self.settings.setValue("enhanced_logging", False)
            self.settings.sync()
        
        # Reinitialize debug logger with new settings
        self.debug_logger = DebugLogger()
        
        self.update_status_label()
        
        if debug_enabled:
            self.debug_logger.log_info("Debug mode enabled via GUI (auto-save)")
        else:
            self.debug_logger.log_info("Debug mode disabled via GUI (auto-save)")
        
        # Emit auto-save signal to parent if exists
        self.auto_save_settings()
    
    def on_enhanced_logging_changed(self):
        """Handle enhanced logging setting change and trigger auto-save"""
        enhanced_logging = self.enhanced_logging_checkbox.isChecked()
        self.settings.setValue("enhanced_logging", enhanced_logging)
        self.settings.sync()
        
        self.update_status_label()
        
        if enhanced_logging:
            self.debug_logger.log_info("Enhanced logging enabled via GUI (auto-save)")
        else:
            self.debug_logger.log_info("Enhanced logging disabled via GUI (auto-save)")
        
        # Emit auto-save signal to parent if exists
        self.auto_save_settings()
    
    def auto_save_settings(self):
        """Auto-save settings"""
        try:
            # Force sync settings to disk
            self.settings.sync()
        except Exception as e:
            print(f"Error in auto_save_settings: {e}")


if __name__ == "__main__":
    """Standalone test"""
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    widget = DebugSettingsWidget()
    widget.resize(800, 600)
    widget.show()
    
    sys.exit(app.exec())