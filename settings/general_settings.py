"""
General Settings Widget
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Signal, QSettings
from qfluentwidgets import (
    SettingCardGroup, SwitchSettingCard, PushSettingCard, PrimaryPushSettingCard,
    FluentIcon, BodyLabel, CaptionLabel, PasswordLineEdit, InfoBar, InfoBarPosition,
    setCustomStyleSheet, ExpandGroupSettingCard, SingleDirectionScrollArea
)
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.security import encrypt_pat, decrypt_pat


class GitHubSettingCard(ExpandGroupSettingCard):
    """GitHub PAT settings card using ExpandGroupSettingCard"""
    
    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.GITHUB,
            "GitHub Settings",
            "Configure GitHub Personal Access Token for API access",
            parent
        )
        
        from qfluentwidgets import ComboBox, PushButton
        
        self.pat_input = PasswordLineEdit()
        self.pat_input.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        self.pat_input.setClearButtonEnabled(True)
        self.pat_input.setFixedHeight(40)
        setCustomStyleSheet(self.pat_input, "PasswordLineEdit{ border-radius: 16px; }", "PasswordLineEdit{ border-radius: 16px; }")
        
        self.test_button = PushButton("Test PAT")
        self.test_button.setFixedWidth(135)
        self.test_button.setFixedHeight(46)
        self.test_button.clicked.connect(self.test_pat)
        
        self.permission_combo = ComboBox()
        self.permission_combo.addItems(["repo", "public_repo", "repo:status", "repo_deployment"])
        self.permission_combo.setFixedWidth(135)
        self.permission_combo.setFixedHeight(46)
        self.permission_combo.setCurrentText("repo")
        
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)
        
        self.addGroup(
            FluentIcon.SAVE,
            "Personal Access Token",
            "Enter your GitHub PAT for API access",
            self.pat_input
        )
        self.addGroup(
            FluentIcon.CHECKBOX,
            "Recommended Permission",
            "Select the permission scope for your PAT",
            self.permission_combo
        )
        self.addGroup(
            FluentIcon.EDIT,
            "Test Connection",
            "Verify your PAT is valid",
            self.test_button
        )
    
    def test_pat(self):
        """Test GitHub PAT validity"""
        pat = self.pat_input.text().strip()
        if not pat:
            InfoBar.warning(
                title='Warning',
                content='Please enter GitHub PAT first',
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        try:
            import requests
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
                InfoBar.success(
                    title='Success',
                    content=f'PAT verified! Associated user: {username}',
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            elif response.status_code == 401:
                InfoBar.error(
                    title='Error',
                    content='PAT invalid or expired',
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title='Error',
                    content=f'PAT verification failed (status code: {response.status_code})',
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
        
        except requests.exceptions.RequestException as e:
            InfoBar.error(
                title='Error',
                content=f'Network error: {str(e)}',
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title='Error',
                content=f'Test failed: {str(e)}',
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def get_pat(self):
        """Get current PAT text"""
        return self.pat_input.text().strip()
    
    def set_pat(self, pat):
        """Set PAT text"""
        self.pat_input.setText(pat)
    
    def get_permission(self):
        """Get selected permission"""
        return self.permission_combo.currentText()
    
    def set_permission(self, permission):
        """Set permission"""
        self.permission_combo.setCurrentText(permission)


class GeneralSettingsWidget(QWidget):
    """General settings widget using qfluentwidgets SettingCard components"""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("MyCompany", "ConverterApp")
        self.setup_ui()
        self.connect_signals()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.enableTransparentBackground()
        
        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(20)
        
        self.behavior_group = SettingCardGroup("Interface Behavior", scroll_content)
        
        self.auto_preview_card = SwitchSettingCard(
            FluentIcon.VIEW,
            "Auto-show preview",
            "Automatically show preview after selecting file",
            parent=self.behavior_group
        )
        
        self.remember_path_card = SwitchSettingCard(
            FluentIcon.HISTORY,
            "Remember paths",
            "Remember last selected input/output paths",
            parent=self.behavior_group
        )
        
        self.completion_notify_card = SwitchSettingCard(
            FluentIcon.COMPLETED,
            "Completion notification",
            "Show success notification after conversion",
            parent=self.behavior_group
        )
        
        self.task_mode_card = SwitchSettingCard(
            FluentIcon.SETTING,
            "Task Mode",
            "Enable task queue for batch processing",
            parent=self.behavior_group
        )
        
        self.github_card = GitHubSettingCard(scroll_content)
        
        self.behavior_group.addSettingCards([
            self.auto_preview_card,
            self.remember_path_card,
            self.completion_notify_card,
            self.task_mode_card
        ])
        
        scroll_layout.addWidget(self.behavior_group)
        scroll_layout.addWidget(self.github_card)
        scroll_layout.addStretch()
        
        self.scroll_area.setWidget(scroll_content)
        
        main_layout.addWidget(self.scroll_area)
    
    def connect_signals(self):
        """Connect signals for auto-save"""
        self.auto_preview_card.checkedChanged.connect(self.on_settings_changed)
        self.remember_path_card.checkedChanged.connect(self.on_settings_changed)
        self.completion_notify_card.checkedChanged.connect(self.on_settings_changed)
        self.task_mode_card.checkedChanged.connect(self.on_settings_changed)
        
        # Connect GitHub settings signals
        self.github_card.pat_input.textChanged.connect(self.on_settings_changed)
        self.github_card.permission_combo.currentTextChanged.connect(self.on_settings_changed)
    
    def on_settings_changed(self):
        """Emit settings changed signal and save settings"""
        self.save_settings()
        self.settings_changed.emit()
    
    def load_settings(self):
        """Load settings from QSettings"""
        # Block signals during loading to prevent auto-save
        self.auto_preview_card.blockSignals(True)
        self.remember_path_card.blockSignals(True)
        self.completion_notify_card.blockSignals(True)
        self.task_mode_card.blockSignals(True)
        self.github_card.pat_input.blockSignals(True)
        self.github_card.permission_combo.blockSignals(True)
        
        self.auto_preview_card.setChecked(bool(self.settings.value("image_converter/auto_preview", True, type=bool)))
        self.remember_path_card.setChecked(bool(self.settings.value("image_converter/remember_path", True, type=bool)))
        self.completion_notify_card.setChecked(bool(self.settings.value("image_converter/completion_notify", True, type=bool)))
        self.task_mode_card.setChecked(bool(self.settings.value("task_mode", False, type=bool)))
        
        encrypted_pat = self.settings.value("general/github_pat", "", type=str)
        if encrypted_pat:
            decrypted_pat = decrypt_pat(str(encrypted_pat))
            self.github_card.set_pat(decrypted_pat)
        
        permission = self.settings.value("general/github_permission", "repo", type=str)
        self.github_card.set_permission(str(permission))
        
        # Unblock signals after loading
        self.auto_preview_card.blockSignals(False)
        self.remember_path_card.blockSignals(False)
        self.completion_notify_card.blockSignals(False)
        self.task_mode_card.blockSignals(False)
        self.github_card.pat_input.blockSignals(False)
        self.github_card.permission_combo.blockSignals(False)
    
    def save_settings(self):
        """Save settings to QSettings"""
        self.settings.setValue("image_converter/auto_preview", self.auto_preview_card.isChecked())
        self.settings.setValue("image_converter/remember_path", self.remember_path_card.isChecked())
        self.settings.setValue("image_converter/completion_notify", self.completion_notify_card.isChecked())
        self.settings.setValue("task_mode", self.task_mode_card.isChecked())
        
        pat_text = self.github_card.get_pat()
        if pat_text:
            encrypted_pat = encrypt_pat(pat_text)
            self.settings.setValue("general/github_pat", encrypted_pat)
        else:
            self.settings.setValue("general/github_pat", "")
        
        self.settings.setValue("general/github_permission", self.github_card.get_permission())


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    widget = GeneralSettingsWidget()
    widget.show()
    sys.exit(app.exec())
