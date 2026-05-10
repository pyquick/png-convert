"""
Image Converter Settings Widget
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from UIkit import *

class ImageConverterSettingsWidget(QWidget):
    """Image Converter settings widget"""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()
        self.connect_signals()
    
    def setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
       
        
        # Interface behavior settings
        behavior_group = QGroupBox("Interface Behavior Settings")
        behavior_layout = QVBoxLayout(behavior_group)
        
        self.auto_preview_check = CheckBox("Auto-show preview after selecting file")
        behavior_layout.addWidget(self.auto_preview_check)
        behavior_layout.addSpacing(10)
        self.remember_path_check = CheckBox("Remember last selected input/output paths")
        behavior_layout.addWidget(self.remember_path_check)
        behavior_layout.addSpacing(10)
        self.completion_notify_check = CheckBox("Show success notification after conversion")
        behavior_layout.addWidget(self.completion_notify_check)
        behavior_layout.addSpacing(10)
        main_layout.addWidget(behavior_group)
        
        main_layout.addStretch()
    
    def connect_signals(self):
        """Connect signals for auto-save"""
        
        self.auto_preview_check.stateChanged.connect(self.on_settings_changed)
        self.remember_path_check.stateChanged.connect(self.on_settings_changed)
        self.completion_notify_check.stateChanged.connect(self.on_settings_changed)
    
    def on_settings_changed(self):
        """Emit settings changed signal and save settings"""
        self.save_settings()
        self.settings_changed.emit()
    
    def load_settings(self):
        """Load settings from QSettings"""
        from PySide6.QtCore import QSettings
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Default output format
        
        
        # Interface behavior
        self.auto_preview_check.setChecked(settings.value("image_converter/auto_preview", True, type=bool))
        self.remember_path_check.setChecked(settings.value("image_converter/remember_path", True, type=bool))
        self.completion_notify_check.setChecked(settings.value("image_converter/completion_notify", True, type=bool))
    
    def save_settings(self):
        """Save settings to QSettings"""
        from PySide6.QtCore import QSettings
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Default output format
        
        
        # Interface behavior
        settings.setValue("image_converter/auto_preview", self.auto_preview_check.isChecked())
        settings.setValue("image_converter/remember_path", self.remember_path_check.isChecked())
        settings.setValue("image_converter/completion_notify", self.completion_notify_check.isChecked())


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    widget = ImageConverterSettingsWidget()
    widget.show()
    sys.exit(app.exec())