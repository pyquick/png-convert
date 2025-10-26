# -*- coding: utf-8 -*-
"""
Settings Dialog for Converter Application

This module contains the settings dialog interface with theme support and 
real-time settings management.
"""

import os
import threading
import time
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QStackedWidget
)
from PySide6.QtGui import QPalette
from PySide6.QtCore import Qt, QSettings, QPropertyAnimation, QEasingCurve, Signal, Slot
from qfluentwidgets import SegmentedWidget, setCustomStyleSheet
from .update_settings_gui import UpdateDialog
from con import CON

class SettingsDialog(QDialog):
    # Define signal for inter-thread communication
    update_status_signal = Signal(str, bool)
    
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window # Store reference to the main window
        self.setWindowTitle("Settings")
        
        # Connect signals
        self.update_status_signal.connect(self._update_status_label)
        
        self.init_ui()
        self.load_settings()
        self._apply_theme_from_parent() # Apply theme based on parent's current theme
        self._connect_settings_signals() # Connect settings signals for real-time saving

        # Animation for showing the dialog
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(250) # Duration in milliseconds
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event):
        # Start animation when the dialog is shown
        self.animation.start()
        super().showEvent(event)

    def _apply_theme_from_parent(self):
        if self.parent_window:
            # Get parent window's theme setting instead of judging by system palette
            theme_setting = self.parent_window.settings.value("theme", 0, type=int)
            if theme_setting == 0: # System Default
                # Only use system palette when System Default is selected
                is_dark_mode = self.parent_window.palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5
                self.apply_theme(is_dark_mode)
            elif theme_setting == 1: # Light Mode
                self.apply_theme(False)
            else: # Dark Mode
                self.apply_theme(True)
    
    def _load_settings_qss_file(self, filename):
        """Load QSS content from external settings file"""
        qss_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'qss', filename)
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: Settings QSS file not found: {qss_path}")
            return ""
        except Exception as e:
            print(f"Error loading settings QSS file {qss_path}: {e}")
            return ""

    @property
    def SETTINGS_LIGHT_QSS(self):
        """Load light theme QSS from external file"""
        return self._load_settings_qss_file('settings_light.qss')

    @property
    def SETTINGS_DARK_QSS(self):
        """Load dark theme QSS from external file"""
        return self._load_settings_qss_file('settings_dark.qss')

    def apply_theme(self, is_dark_mode):
        if is_dark_mode:
            self.setStyleSheet(self.SETTINGS_DARK_QSS)
        else:
            self.setStyleSheet(self.SETTINGS_LIGHT_QSS)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Create SegmentedWidget and QStackedWidget
        self.segmented_widget = SegmentedWidget(self)
        setCustomStyleSheet(self.segmented_widget, CON.qss_seg,CON.qss_seg)
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
        
        self.update_group = UpdateDialog()
        self.update_group.setObjectName("update_group")
        update_layout.addWidget(self.update_group)
        update_layout.addStretch()
        
        self.stacked_widget.addWidget(update_page)
        
        # Image Converter settings have been merged into General settings
        # No separate Image Converter page needed
        
        # Add tab items
        self.add_sub_interface(general_page, "general_page", "General")
        self.add_sub_interface(debug_page, "debug_page", "Debug")
        self.add_sub_interface(update_page, "update_page", "Update")
        
        # Connect signals and initialize current page
        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)
        self.stacked_widget.setCurrentIndex(0)
        self.segmented_widget.setCurrentItem("general_page")
        
        # Add to main layout
        main_layout.addWidget(self.segmented_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(self.stacked_widget)

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
        
        # Image converter settings are now handled by the general widget
        # No separate image converter widget exists anymore
        
        # Connect theme settings from parent window if available
        if self.parent_window and hasattr(self.parent_window, 'settings'):
            # Theme changes are handled by the parent window's auto-save mechanism
            pass
    
    def on_settings_changed(self):
        """Handle any settings change and trigger auto-save"""
        self.save_settings_async()
    
    @Slot(str, bool)
    def _update_status_label(self, text, visible):
        """Safe update status label slot function - removed functionality"""
        pass
    
    def _notify_image_converter_settings_changed(self):
        """Notify any open image converter windows about settings changes"""
        # This method can be used to notify image converter instances
        # about settings changes if needed in the future
        pass
    
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
        thread = threading.Thread(target=save_thread)
        thread.daemon = True
        thread.start()
        
        # Apply theme changes immediately
        if self.parent_window:
            self.parent_window._apply_system_theme_from_settings()
    
    def accept(self):
        """Override accept method to save settings without closing dialog"""
        self.save_settings_async()
    
    def reject(self):
        """Override reject method to save settings and close dialog"""
        self.save_settings_async()
        super().reject()