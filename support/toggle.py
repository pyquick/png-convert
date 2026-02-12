from termios import INPCK
from PySide6.QtWidgets import QWidget
import darkdetect
from UIkit import setTheme, setThemeColor, Theme
from UIWindow import QMainWindow
from UIWindow.utils import getSystemAccentColor
from darkdetect import isDark
from PySide6.QtCore import QThread, QTimer
import threading
import time
from con import CON
import weakref
import platform
from typing import Optional, Tuple
import gc

# Create a lock to protect access to CON object
_con_lock = threading.Lock()
from UIkit import *

class ThemeManager(QObject):
    def __init__(self):
        super().__init__()
        setTheme(Theme.AUTO)
        # Timer: check every 1 second
        
        setThemeColor(getSystemAccentColor(), save=False)
        self.current_theme = "dark"
        self.last_accent_color = None
        self.running = True
        self.system_theme_thread = None
        self.app_theme_thread = None
        self.accent_color_thread = None
        self.last_color_hex = None
        
    def check_accent_color(self):
        """Detect system accent color"""
        color = getSystemAccentColor()
        color_hex = color.name()

        if color_hex != self.last_color_hex:
            self.last_color_hex = color_hex
            color_dict = {
                "r": color.red(),
                "g": color.green(),
                "b": color.blue(),
                "a": color.alpha(),
                "hex": color_hex
            }
            self.on_color_change(color_dict)
    def on_color_change(self, color_dict):
        """Triggered when system accent color changes"""
        setThemeColor(getSystemAccentColor(), save=False)
        print("System accent color changed:", color_dict)
    def start(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_accent_color)
        self.timer.start(100)
    def stop(self):
        pass
        
    


# Create global theme manager instance
theme_manager = ThemeManager()
