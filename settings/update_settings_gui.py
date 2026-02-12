# -*- coding: utf-8 -*-
"""
Update Settings GUI Widget for Converter application
"""

import sys
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QSettings, Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
from UIkit import *
from darkdetect import isDark
from update.update_manager import UpdateManager
from update.download_update import download_and_apply_update
from UIWindow.utils import getSystemAccentColor
from con import CON


class CheckUpdateThread(QThread):
    check_finished = Signal(dict)
    
    def __init__(self, update_manager, include_prerelease, prerelease_type=None):
        super().__init__()
        self.update_manager = update_manager
        self.include_prerelease = include_prerelease
        self.prerelease_type = prerelease_type
    
    def run(self):
        try:
            result = self.update_manager.check_for_updates(self.include_prerelease, self.prerelease_type)
            self.check_finished.emit(result)
        except Exception as e:
            self.check_finished.emit({"status": "error", "message": str(e)})


class DownloadThread(QThread):
    progress_updated = Signal(dict)
    finished = Signal(dict)
    
    def __init__(self, download_url, version, include_prerelease=False):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self.include_prerelease = include_prerelease
        self.is_cancelled = False
        self.progress_callback = None
        self.downloader = None
        
    def run(self):
        try:
            print(f"DownloadThread started, is_cancelled: {self.is_cancelled}")
            
            if self.is_cancelled:
                print("DownloadThread: cancelled before download")
                result = {
                    "status": "cancelled",
                    "message": "Download cancelled by user"
                }
                self.finished.emit(result)
                return
            
            def progress_callback(progress, downloaded, total_size):
                if not self.is_cancelled:
                    progress_data = {
                        "progress": progress,
                        "downloaded": downloaded,
                        "total": total_size
                    }
                    self.progress_updated.emit(progress_data)
            
            self.progress_callback = progress_callback
            
            update_info = {
                "download_url": self.download_url,
                "latest_version": self.version
            }
            
            from update.download_update import UpdateDownloader
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="update_")
            
            try:
                self.downloader = UpdateDownloader(
                    download_url=self.download_url,
                    target_directory=temp_dir,
                    max_threads=64
                )
                
                print("DownloadThread: starting download")
                result = self.downloader.download_update(self.version, progress_callback)
                print(f"DownloadThread: download completed with status: {result.get('status')}")
                
                if result.get("status") == "cancelled":
                    print("DownloadThread: result status is cancelled")
                    self.finished.emit(result)
                    return
                
                if self.is_cancelled or (self.downloader and hasattr(self.downloader, '_cancelled') and self.downloader._cancelled):
                    print("DownloadThread: cancelled during download")
                    result = {
                        "status": "cancelled",
                        "message": "Download cancelled by user",
                        "temp_dir": temp_dir
                    }
                    self.finished.emit(result)
                    return
                    
                if self.is_cancelled:
                    print("DownloadThread: cancelled after download")
                    result = {
                        "status": "cancelled",
                        "message": "Download cancelled by user",
                        "temp_dir": temp_dir
                    }
                    self.finished.emit(result)
                    return
                
                result["downloader"] = self.downloader
                result["temp_dir"] = temp_dir
                print("DownloadThread: emitting success result")
                self.finished.emit(result)
                
            except Exception as e:
                print(f"DownloadThread exception: {e}")
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except Exception as cleanup_error:
                    print(f"Failed to clean up temp directory: {cleanup_error}")
                
                error_result = {
                    "status": "error",
                    "message": f"Download failed: {str(e)}"
                }
                self.finished.emit(error_result)
            
        except Exception as e:
            print(f"DownloadThread outer exception: {e}")
            error_result = {
                "status": "error",
                "message": f"Thread initialization failed: {str(e)}"
            }
            self.finished.emit(error_result)
    
    def cancel(self):
        """Cancel download"""
        print("DownloadThread: cancel() called")
        self.is_cancelled = True
        
        if self.downloader:
            print("DownloadThread: cancelling downloader")
            self.downloader.cancel()
            import time
            time.sleep(0.1)
        
        self.quit()
        
        if not self.wait(1000):
            print("Warning: DownloadThread did not stop within 1 second, forcing termination")
            self.terminate()
            self.wait(500)


class UpdateSettingsWidget(QWidget):
    """Update settings widget using qfluentwidgets SettingCard components"""
    
    __version__ = "2.1.0A11"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_manager = UpdateManager(self.__version__)
        self.check_thread = None
        self.download_thread = None
        self.current_update_info = None
        
        self._detect_current_version_type()
        self.setup_ui()
        self.load_settings()
        self.connect_signals()
    
    def setup_ui(self):
        """Setup UI layout"""
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
        self.update_group = SettingCardGroup("Update Configuration", scroll_content)
        
        # Determine available channels based on version type
        available_channels = ["Stable"]
        if self.is_internal_version:
            if self.is_alpha_version:
                available_channels = ["Stable", "Alpha"]
                print("Alpha version: only showing Alpha channel")
            elif self.is_deepdev_version:
                available_channels = ["Stable", "Deepdev"]
                print("Deepdev version: only showing Deepdev channel")
        else:
            available_channels = ["Stable", "RC (Release Candidate)", "Beta", "Deepdev", "Alpha"]
       
        channel_layout = QHBoxLayout()
        channel_label = BodyLabel("Update Channel:")
        channel_label.setFixedWidth(120)
        self.channel_combo = ComboBox()
        self.channel_combo.addItems(available_channels)
        self.channel_combo.setFixedWidth(250)
        channel_layout.addWidget(channel_label)
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addStretch()
        self.update_group.vBoxLayout.addLayout(channel_layout)
        
        channel_info = CaptionLabel("Select update channel to receive updates from")
        self.update_group.vBoxLayout.addWidget(channel_info)
        
        # Create check for updates card
        self.check_update_card = PrimaryPushSettingCard(
            "Check for Updates",
            FluentIcon.SYNC,
            "Check for new updates"
        )
        self.check_update_card.clicked.connect(self.check_for_updates)
        
        # Create download update card (initially disabled)
        self.download_update_card = PrimaryPushSettingCard(
            "Download Update",
            FluentIcon.DOWNLOAD,
            "Download and install latest update"
        )
        self.download_update_card.clicked.connect(self.download_update)
        self.download_update_card.setEnabled(False)
        
        # Create restart application card (initially disabled)
        self.restart_card = PrimaryPushSettingCard(
            "Restart Application",
            FluentIcon.SYNC,
            "Restart to apply update"
        )
        self.restart_card.clicked.connect(self.restart_application)
        self.restart_card.setEnabled(False)
        
        # Add cards to group
        self.update_group.addSettingCards([
            self.check_update_card,
            self.download_update_card,
            self.restart_card
        ])
        
        # Add update status and progress to group
        self.update_status_label = BodyLabel("Ready to check for updates.")
        self.update_status_label.setWordWrap(True)
        self.update_group.vBoxLayout.addWidget(self.update_status_label)
        
        # Release content browser
        self.release_content_browser = TextBrowser()
        self.release_content_browser.setMinimumHeight(150)
        self.release_content_browser.setVisible(False)
        self.update_group.vBoxLayout.addWidget(self.release_content_browser)
        
        # Progress bars
        self.progress_bar = IndeterminateProgressBar()
        self.progress_bar.setVisible(False)
        self.update_group.vBoxLayout.addWidget(self.progress_bar)
        
        self.download_progress_bar = ProgressBar()
        self.download_progress_bar.setRange(0, 100)
        self.download_progress_bar.setValue(0)
        self.download_progress_bar.setVisible(False)
        self.update_group.vBoxLayout.addWidget(self.download_progress_bar)
        
        # Progress label
        self.progress_label = BodyLabel("0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.progress_label.setFont(font)
        self.progress_label.setVisible(False)
        self.update_group.vBoxLayout.addWidget(self.progress_label)
        
        # Add groups to scroll layout
        scroll_layout.addWidget(self.update_group)
        scroll_layout.addStretch()
        
        # Set scroll content
        self.scroll_area.setWidget(scroll_content)
        
        # Add scroll area to main layout
        main_layout.addWidget(self.scroll_area)
    
    def connect_signals(self):
        """Connect signals"""
        self.channel_combo.currentIndexChanged.connect(self.on_update_channel_changed)
    
    def _detect_current_version_type(self):
        """Detect current version type"""
        try:
            version_info = self.update_manager._parse_version(self.__version__)
            _, _, _, current_tag, _ = version_info
            
            self.is_alpha_version = (current_tag == 'A')
            self.is_deepdev_version = (current_tag == 'D')
            self.is_internal_version = self.is_alpha_version or self.is_deepdev_version
            
            if self.is_internal_version:
                print(f"Detected internal version: {self.__version__} (tag: {current_tag})")
            
        except Exception as e:
            print(f"Version detection failed: {e}")
            self.is_internal_version = False
            self.is_alpha_version = False
            self.is_deepdev_version = False
    
    def load_settings(self):
        """Load settings from QSettings"""
        settings = QSettings("MyCompany", "ConverterApp")
        prerelease_type = settings.value("update/prerelease_type", "stable", type=str)
        
        type_index = 0
        if prerelease_type == "rc":
            type_index = 1
        elif prerelease_type == "beta":
            type_index = 2
        elif prerelease_type == "deepdev":
            type_index = 3
        elif prerelease_type == "alpha":
            type_index = 4
        
        self.channel_combo.setCurrentIndex(type_index)
    
    def save_settings(self):
        """Save settings to QSettings"""
        try:
            prerelease_type = "stable"
            
            current_index = self.channel_combo.currentIndex()
            if current_index == 1:
                prerelease_type = "rc"
            elif current_index == 2:
                prerelease_type = "beta"
            elif current_index == 3:
                prerelease_type = "deepdev"
            elif current_index == 4:
                prerelease_type = "alpha"
            
            settings = QSettings("MyCompany", "ConverterApp")
            settings.setValue("update/prerelease_type", prerelease_type)
            settings.sync()
            
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def on_update_channel_changed(self, index):
        """Handle update channel change"""
        self.save_settings()
    
    def _get_update_check_params(self):
        """Get update check parameters"""
        prerelease_type = "stable"
        
        current_index = self.channel_combo.currentIndex()
        current_text = self.channel_combo.currentText()
        
        if self.is_internal_version:
            if self.is_alpha_version:
                if current_index == 1:
                    prerelease_type = "alpha"
            elif self.is_deepdev_version:
                if current_index == 1:
                    prerelease_type = "deepdev"
        else:
            if current_index == 1:
                prerelease_type = "rc"
            elif current_index == 2:
                prerelease_type = "beta"
            elif current_index == 3:
                prerelease_type = "deepdev"
            elif current_index == 4:
                prerelease_type = "alpha"
        
        include_prerelease = (prerelease_type != "stable")
        
        return include_prerelease, prerelease_type if include_prerelease else None
    
    def check_for_updates(self):
        """Check for updates"""
        self.update_status_label.setText("Checking for updates...")
        setThemeColor(getSystemAccentColor(), save=False)
        self.check_update_card.setEnabled(False)
        
        self.release_content_browser.setVisible(False)
        self.download_update_card.setEnabled(False)
        self.restart_card.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.resume()
        self.progress_bar.start()
        
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        include_prerelease, prerelease_type = self._get_update_check_params()
        self.save_settings()
        
        self.check_thread = CheckUpdateThread(self.update_manager, include_prerelease, prerelease_type if include_prerelease else None)
        self.check_thread.check_finished.connect(self.on_check_finished)
        self.check_thread.start()
    
    def on_check_finished(self, result):
        """Handle check finished"""
        if result["status"] == "update_available":
            version_type = ""
            if "version_info" in result:
                version_tuple = result["version_info"]
                version_type = self.update_manager.get_version_type_name(version_tuple)
                if version_type and version_type != "Stable":
                    version_type = f" ({version_type})"
            
            self.update_status_label.setText(f"✅ {result['message']}\n\nVersion: {result['latest_version']}{version_type}")
            self.download_update_card.setEnabled(True)
            self.current_update_info = result
            
            if result.get("release_body"):
                self.release_content_browser.setMarkdown(result["release_body"])
                self.release_content_browser.setVisible(True)
            else:
                self.release_content_browser.setVisible(False)
        elif result["status"] == "error":
            self.update_status_label.setText(f"❌ Check failed: {result['message']}")
            self.download_update_card.setEnabled(False)
            self.release_content_browser.setVisible(False)
        else:
            self.update_status_label.setText(f"ℹ️ {result['message']}")
            self.download_update_card.setEnabled(False)
            self.release_content_browser.setVisible(False)
        
        self.progress_bar.pause()
        self.progress_bar.setVisible(False)
        self.check_update_card.setEnabled(True)
    
    def download_update(self):
        """Download update"""
        if hasattr(self, 'current_update_info'):
            self.download_update_card.setEnabled(False)
            self.check_update_card.setEnabled(False)
            
            self.release_content_browser.setVisible(False)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.start()
            self.download_progress_bar.setVisible(False)
            self.update_status_label.setText("Download in progress...")
            
            self.progress_label.setText("0%")
            self.progress_label.setVisible(True)
            
            download_url = self.current_update_info.get("download_url")
            latest_version = self.current_update_info.get("latest_version")
            
            include_prerelease, prerelease_type = self._get_update_check_params()
            
            if hasattr(self, '_download_start_time'):
                delattr(self, '_download_start_time')
            if hasattr(self, '_last_downloaded'):
                delattr(self, '_last_downloaded')
            if hasattr(self, '_last_time'):
                delattr(self, '_last_time')
            
            self.download_thread = DownloadThread(download_url, latest_version, include_prerelease)
            self.download_thread.progress_updated.connect(self.on_progress_updated)
            self.download_thread.finished.connect(self.on_download_finished)
            self.download_thread.start()
            
            self.download_update_card.setText("Cancel Download")
            self.download_update_card.setEnabled(True)
            self.download_update_card.clicked.disconnect()
            self.download_update_card.clicked.connect(self.cancel_download)
    
    def cancel_download(self):
        """Cancel download"""
        if hasattr(self, 'download_thread') and self.download_thread is not None and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_update_card.setEnabled(False)
            self.update_status_label.setText("Cancelling download...")
            
            def check_thread_stopped():
                if self.download_thread is None:
                    return
                    
                if not self.download_thread.isRunning():
                    self.show_cancelled_state()
                else:
                    QTimer.singleShot(500, check_thread_stopped)
            
            QTimer.singleShot(500, check_thread_stopped)
    
    def show_cancelled_state(self):
        """Show cancelled state"""
        self.update_status_label.setText("Download cancelled")
        self.progress_bar.setVisible(False)
        self.download_progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.check_update_card.setEnabled(True)
        self.download_update_card.setText("Download Update")
        self.download_update_card.clicked.disconnect()
        self.download_update_card.clicked.connect(self.download_update)
    
    def on_progress_updated(self, progress_data):
        """Handle progress update"""
        if not progress_data:
            return
        
        progress = progress_data.get("progress", 0)
        downloaded = progress_data.get("downloaded", 0)
        total = progress_data.get("total", 0)
        
        self.download_progress_bar.setVisible(True)
        self.download_progress_bar.setValue(int(progress))
        
        if total > 0:
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.progress_label.setText(f"{progress:.1f}% - {downloaded_mb:.1f} MB / {total_mb:.1f} MB")
        else:
            self.progress_label.setText(f"{progress:.1f}%")
    
    def on_download_finished(self, result):
        """Handle download finished"""
        self.progress_bar.setVisible(False)
        self.download_progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        if result["status"] == "success":
            self.update_status_label.setText("✅ Download completed successfully!")
            self.restart_card.setEnabled(True)
            self.check_update_card.setEnabled(True)
            self.download_update_card.setText("Download Update")
            self.download_update_card.clicked.disconnect()
            self.download_update_card.clicked.connect(self.download_update)
        elif result["status"] == "cancelled":
            self.show_cancelled_state()
        else:
            self.update_status_label.setText(f"❌ Download failed: {result.get('message', 'Unknown error')}")
            self.check_update_card.setEnabled(True)
            self.download_update_card.setText("Download Update")
            self.download_update_card.clicked.disconnect()
            self.download_update_card.clicked.connect(self.download_update)
    
    def restart_application(self):
        """Restart application"""
        self.update_status_label.setText("Restarting application...")
        
        import subprocess
        import sys
        
        try:
            subprocess.Popen([sys.executable] + sys.argv)
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        except Exception as e:
            self.update_status_label.setText(f"Failed to restart: {e}")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    widget = UpdateSettingsWidget()
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec())
