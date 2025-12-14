"""
General Settings Widget
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QLineEdit)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QIntValidator
from qfluentwidgets import *
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.security import encrypt_pat, decrypt_pat
from con import CON
class GeneralSettingsWidget(QWidget):
    """General settings widget"""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("intsant", "converter")
        self.pat_input = None  # Initialize PAT input field reference
        self.setup_ui()
        self.load_settings()
        self.connect_signals()
    
    def setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        
        
        
        # Image Converter settings group
        image_converter_group = QGroupBox("Image Converter Settings")
        image_converter_layout = QVBoxLayout(image_converter_group)
        
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
        
        # Task mode setting
        self.task_mode_check = CheckBox("Enable Task Mode")
        self.task_mode_check.setChecked(False)
        behavior_layout.addWidget(self.task_mode_check)
        behavior_layout.addSpacing(10)
        
        image_converter_layout.addWidget(behavior_group)
        image_converter_layout.addStretch()
        
        # GitHub Settings Group
        github_group = QGroupBox("GitHub Settings")
        github_layout = QVBoxLayout()
        
        # GitHub PAT Settings
        pat_layout = QHBoxLayout()
        pat_label = QLabel("GitHub PAT (Personal Access Token):")
        self.pat_input = PasswordLineEdit()
        self.pat_input.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        self.pat_input.setClearButtonEnabled(True)
        self.pat_input.setFixedHeight(33)
        setCustomStyleSheet(self.pat_input,"PasswordLineEdit{ border-radius: 16px; }","PasswordLineEdit{ border-radius: 16px; }")
        pat_layout.addWidget(pat_label)
        pat_layout.addWidget(self.pat_input)
        github_layout.addLayout(pat_layout)
        
        # PAT Info
        pat_info = QLabel("Used for GitHub API access, recommend only 'repo' permission")
        pat_info.setStyleSheet("color: #666; font-size: 11px;")
        github_layout.addWidget(pat_info)
        self.qss_debug = """PushButton{ border-radius: 12px; }"""
        # PAT Test Button
        test_pat_btn = PushButton("Test PAT")
        setCustomStyleSheet(test_pat_btn,self.qss_debug,self.qss_debug)
        test_pat_btn.clicked.connect(self.test_pat)
        github_layout.addWidget(test_pat_btn)
        
        github_group.setLayout(github_layout)
        main_layout.addWidget(github_group)
        main_layout.addWidget(image_converter_group)
        main_layout.addStretch()
    
    def connect_signals(self):
        """Connect signals for auto-save"""
        # Image converter settings signals
        self.auto_preview_check.stateChanged.connect(self.on_settings_changed)
        self.remember_path_check.stateChanged.connect(self.on_settings_changed)
        self.completion_notify_check.stateChanged.connect(self.on_settings_changed)
        self.task_mode_check.stateChanged.connect(self.on_settings_changed)
        
        # Placeholder for future general settings signals
        pass
    
    def on_settings_changed(self):
        """Emit settings changed signal and save settings"""
        self.save_settings()
        self.settings_changed.emit()
    
    def load_settings(self):
        """Load settings from QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Image converter settings
        self.auto_preview_check.setChecked(settings.value("image_converter/auto_preview", True, type=bool))
        self.remember_path_check.setChecked(settings.value("image_converter/remember_path", True, type=bool))
        self.completion_notify_check.setChecked(settings.value("image_converter/completion_notify", True, type=bool))
        
        # Task mode setting
        self.task_mode_check.setChecked(settings.value("task_mode", False, type=bool))
        
        # GitHub PAT settings
        encrypted_pat = settings.value("general/github_pat", "", type=str)
        if encrypted_pat:
            decrypted_pat = decrypt_pat(encrypted_pat)
            self.pat_input.setText(decrypted_pat)
    
    def save_settings(self):
        """Save settings to QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        
        # Image converter settings
        settings.setValue("image_converter/auto_preview", self.auto_preview_check.isChecked())
        settings.setValue("image_converter/remember_path", self.remember_path_check.isChecked())
        settings.setValue("image_converter/completion_notify", self.completion_notify_check.isChecked())
        
        # Task mode setting
        settings.setValue("task_mode", self.task_mode_check.isChecked())
        
        # GitHub PAT settings
        pat_text = self.pat_input.text().strip()
        if pat_text:
            encrypted_pat = encrypt_pat(pat_text)
            settings.setValue("general/github_pat", encrypted_pat)
        else:
            settings.setValue("general/github_pat", "")

    def test_pat(self):
        """Test GitHub PAT validity"""
        pat = self.pat_input.text().strip()
        if not pat:
            PopupTeachingTip.create(
                target=self.pat_input,
                icon=InfoBarIcon.WARNING,
                title='Warning',
                content='Please enter GitHub PAT first',
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        try:
            import requests
            # Test PAT API endpoint
            response = requests.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {pat}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get("login", "Unknown")
                PopupTeachingTip.create(
                    target=self.pat_input,
                    icon=InfoBarIcon.SUCCESS,
                    title='Success',
                    content=f'PAT verified! Associated user: {username}',
                    isClosable=True,
                    tailPosition=TeachingTipTailPosition.TOP,
                    duration=3000,
                    parent=self
                )
            elif response.status_code == 401:
                PopupTeachingTip.create(
                    target=self.pat_input,
                    icon=InfoBarIcon.ERROR,
                    title='Error',
                    content='PAT invalid or expired',
                    isClosable=True,
                    tailPosition=TeachingTipTailPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
                PopupTeachingTip.create(
                    target=self.pat_input,
                    icon=InfoBarIcon.ERROR,
                    title='Error',
                    content=f'PAT verification failed (status code: {response.status_code})',
                    isClosable=True,
                    tailPosition=TeachingTipTailPosition.TOP,
                    duration=3000,
                    parent=self
                )
        
        except requests.exceptions.RequestException as e:
            PopupTeachingTip.create(
                target=self.pat_input,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content=f'Network error: {str(e)}',
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                duration=3000,
                parent=self
            )
        except Exception as e:
            PopupTeachingTip.create(
                target=self.pat_input,
                icon=InfoBarIcon.ERROR,
                title='Error',
                content=f'Test failed: {str(e)}',
                isClosable=True,
                tailPosition=TeachingTipTailPosition.TOP,
                    duration=3000,
                    parent=self
                )


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    widget = GeneralSettingsWidget()
    widget.show()
    sys.exit(app.exec())