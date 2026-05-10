#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System-level notification module for Converter application
Supports macOS, Windows, and Linux platforms
"""

import platform
import subprocess
import sys


def send_notification(title, message):
    """Send system-level notification
    
    Args:
        title (str): Notification title
        message (str): Notification content
    """
    system = platform.system()
    
    try:
        if system == "Darwin":
            # macOS: Use terminal-notifier or osascript
            try:
                # Try terminal-notifier first (if installed)
                subprocess.run([
                    "terminal-notifier",
                    "-title", title,
                    "-message", message,
                    "-appIcon", "Terminal"
                ], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to osascript (built-in)
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        
        elif system == "Windows":
            # Windows: Use win10toast if available, otherwise fallback
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=5)
            except ImportError:
                # Fallback to Windows PowerShell
                script = f'''Add-Type -AssemblyName System.Windows.Forms; 
                [System.Windows.Forms.MessageBox]::Show("{message}", "{title}", 
                [System.Windows.Forms.MessageBoxButtons]::OK, 
                [System.Windows.Forms.MessageBoxIcon]::Information)'''
                subprocess.run(["powershell", "-Command", script], check=True, capture_output=True)
        
        elif system == "Linux":
            # Linux: Use notify-send (most desktop environments)
            subprocess.run([
                "notify-send",
                "-a", "Converter",
                title,
                message
            ], check=True, capture_output=True)
        
        else:
            # Unsupported platform
            print(f"[Notification] {title}: {message}")
    
    except subprocess.CalledProcessError as e:
        # Log error but don't crash the application
        print(f"Failed to send notification: {e}")
    except Exception as e:
        # Catch all other exceptions
        print(f"Unexpected error sending notification: {e}")


if __name__ == "__main__":
    # Test notification functionality
    send_notification("Test Notification", "This is a test notification from Converter")
