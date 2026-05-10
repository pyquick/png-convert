# -*- coding: utf-8 -*-
"""
Password Input Dialog for Archive Manager
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt, Signal
from UIkit import (
    PasswordLineEdit, PrimaryPushButton, 
    MessageBoxBase, SubtitleLabel, BodyLabel, setCustomStyleSheet, InfoBar, InfoBarPosition
)
from PySide6.QtGui import QFont
from con import CON


class PasswordDialog(MessageBoxBase):
    """Custom password input dialog using MessageBoxBase"""
    
    def __init__(self, parent=None, title="Password Required", content="Please enter the password:", error_message=""):
        super().__init__(parent)
        self.password = ""
        self.error_message = error_message
        self.setup_ui(title, content)
        #self.apply_custom_style()
    
    def setup_ui(self, title, content):
        """Setup the dialog UI"""
        self.setWindowTitle(title)
        
        # Add title
        self.titleLabel = SubtitleLabel(title)
        self.viewLayout.addWidget(self.titleLabel)
        
        # Add content text
        self.contentLabel = BodyLabel(content)
        self.viewLayout.addWidget(self.contentLabel)
        
        # Add error message only if it's not empty
        self.errorLabel = None
        if self.error_message and self.error_message.strip():
            self.errorLabel = BodyLabel(self.error_message)
            self.errorLabel.setStyleSheet("color: red; font-weight: bold;")
            self.viewLayout.addWidget(self.errorLabel)
        
        # Add password input
        self.password_line_edit = PasswordLineEdit()
        self.password_line_edit.setPlaceholderText("Enter password...")
        self.password_line_edit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.password_line_edit)
        
        # Set the minimum width for the dialog
        self.widget.setMinimumWidth(400)
        
        # Connect signals
        self.password_line_edit.returnPressed.connect(self.on_ok_clicked)
        
        # Set focus to password input
        self.password_line_edit.setFocus()
        
        # Add OK and Cancel buttons to button layout
        self.yesButton.setText("OK")
        self.cancelButton.setText("Cancel")
    
    def set_error_message(self, message):
        """Set or update the error message"""
        self.error_message = message
        
        # Remove existing error label if it exists
        for i in reversed(range(self.viewLayout.count())):
            item = self.viewLayout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel) and hasattr(self, 'errorLabel') and item.widget() == self.errorLabel:
                self.viewLayout.removeItem(item)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                break
        
        # Add new error label if message is not empty
        if message:
            self.errorLabel = BodyLabel(message)
            self.errorLabel.setStyleSheet("color: red; font-weight: bold;")
            # Insert after content label
            for i in range(self.viewLayout.count()):
                item = self.viewLayout.itemAt(i)
                if item and item.widget() == self.contentLabel:
                    self.viewLayout.insertWidget(i + 1, self.errorLabel)
                    break

    def get_password(self):
        """Get the entered password"""
        return self.password
    
    def exec(self):
        """Override exec to handle password input"""
        result = super().exec()
        if result == 1:  # Accepted
            self.password = self.password_line_edit.text()
            if not self.password:
                # If password is empty, treat as cancelled
                return 0
        return result
    
    def on_ok_clicked(self):
        """Handle OK button click"""
        self.password = self.password_line_edit.text()
        if self.password:
            self.accept()
        else:
            # Shake the dialog to indicate empty password
            from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
            animation = QPropertyAnimation(self, b"pos")
            animation.setDuration(100)
            animation.setLoopCount(4)
            animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            
            original_pos = self.pos()
            animation.setStartValue(original_pos)
            animation.setEndValue(original_pos + QPoint(10, 0))
            animation.start()
            
            # Reset position after animation
            animation.finished.connect(lambda: self.move(original_pos))


class SimplePasswordDialog(QDialog):
    """Simple password dialog as fallback if MessageBoxBase is not available"""
    
    def __init__(self, parent=None, title="Password Required", content="Please enter the password:", error_message=""):
        super().__init__(parent)
        self.password = ""
        self.error_message = error_message
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 220)  # Increased height to accommodate error message
        self.setup_ui(content)
        #self.apply_custom_style()
    
    def setup_ui(self, content):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Add content text
        self.content_label = QLabel(content)
        self.content_label.setWordWrap(True)
        layout.addWidget(self.content_label)
        
        # Add error message only if it's not empty
        self.error_label = None
        if self.error_message and self.error_message.strip():
            self.error_label = QLabel(self.error_message)
            self.error_label.setWordWrap(True)
            self.error_label.setStyleSheet("color: red; font-weight: bold;")
            layout.addWidget(self.error_label)
        
        # Add password input
        self.password_line_edit = PasswordLineEdit()
        self.password_line_edit.setPlaceholderText("Enter password...")
        self.password_line_edit.setClearButtonEnabled(True)
        layout.addWidget(self.password_line_edit)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = PrimaryPushButton("OK")
        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.ok_button.setFixedWidth(100)
        
        self.cancel_button = PrimaryPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setFixedWidth(100)
        
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.password_line_edit.returnPressed.connect(self.on_ok_clicked)
        
        # Set focus to password input
        self.password_line_edit.setFocus()
    
    def set_error_message(self, message):
        """Set or update the error message"""
        self.error_message = message
        
        # Remove existing error label if it exists
        if hasattr(self, 'error_label') and self.error_label:
            layout = self.layout()
            if layout:
                layout.removeWidget(self.error_label)
                self.error_label.deleteLater()
                self.error_label = None
        
        # Add new error label if message is not empty
        if message:
            self.error_label = QLabel(message)
            self.error_label.setWordWrap(True)
            self.error_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Insert after content label
            layout = self.layout()
            if layout:
                # Simply add the error label to the layout (will appear after content label)
                layout.addWidget(self.error_label)
    def get_password(self):
        """Get the entered password"""
        return self.password
    
    def exec(self):
        """Override exec to handle password input"""
        result = super().exec()
        if result == 1:  # Accepted
            self.password = self.password_line_edit.text()
            if not self.password:
                # If password is empty, treat as cancelled
                return 0
        return result
    
    def on_ok_clicked(self):
        """Handle OK button click"""
        self.password = self.password_line_edit.text()
        if self.password:
            self.accept()
        else:
            # Shake the dialog to indicate empty password
            from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
            animation = QPropertyAnimation(self, b"pos")
            animation.setDuration(100)
            animation.setLoopCount(4)
            animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            
            original_pos = self.pos()
            animation.setStartValue(original_pos)
            animation.setEndValue(original_pos + QPoint(10, 0))
            animation.start()
            
            # Reset position after animation
            animation.finished.connect(lambda: self.move(original_pos))


def get_password(parent=None, title="Password Required", content="Please enter the password:", error_message="", max_attempts=3):
    """
    Function to get password from user with retry functionality
    
    Args:
        parent: Parent widget
        title: Dialog title - always set to "Enter Password"
        content: Dialog content message
        error_message: Error message to display (ignored, always shows neutral message)
        max_attempts: Maximum number of password attempts
    
    Returns:
        Password string if successful, None if cancelled or max attempts reached
    """
    attempts = 0
    
    # Always use "Enter Password" as title, regardless of what's passed
    title = "Enter Password"
    
    while attempts < max_attempts:
        try:
            # Always create a new dialog with neutral message, ignoring error_message
            dialog = PasswordDialog(parent, title, content, "")
            result = dialog.exec()
                
            if result == 1:  # Accepted
                password = dialog.get_password()
                if password:  # Only return if password is not empty
                    return password
                else:
                    # Empty password, treat as retry
                    attempts += 1
                    if attempts < max_attempts:
                        # Use neutral message instead of error message
                        content = "Please enter the password:"
                    else:
                        content = "Maximum password attempts reached."
            else:  # Cancelled
                return None
        except:
            # Fallback to simple dialog
            simple_dialog = SimplePasswordDialog(parent, title, content, "")
            result = simple_dialog.exec()
                
            if result == 1:  # Accepted
                password = simple_dialog.get_password()
                if password:  # Only return if password is not empty
                    return password
                else:
                    # Empty password, treat as retry
                    attempts += 1
                    if attempts < max_attempts:
                        # Use neutral message instead of error message
                        content = "Please enter the password:"
                    else:
                        content = "Maximum password attempts reached."
            else:  # Cancelled
                return None
    
    return None