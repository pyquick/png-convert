# -*- coding: utf-8 -*-
import sys
import os
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QApplication, QFrame
from PySide6.QtCore import QSettings, Qt, QThread, Signal, QTimer, QMutex, QMutexLocker
from UIkit import (
    SettingCardGroup, SettingCard, SwitchSettingCard,
    CaptionLabel, StrongBodyLabel, TextBrowser,
    ProgressBar, ComboBox, InfoBar, InfoBarPosition, FluentIcon,
    CardWidget, IconWidget, PrimaryPushButton,
    ExpandGroupSettingCard, SimpleExpandGroupSettingCard,ScrollArea
)
from update.update_manager import UpdateManager
from UIWindow.utils import getSystemAccentColor
from UIkit import setThemeColor


class CheckUpdateThread(QThread):
    check_finished = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, update_manager, include_prerelease, prerelease_type=None):
        super().__init__()
        self.update_manager = update_manager
        self.include_prerelease = include_prerelease
        self.prerelease_type = prerelease_type
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled:
                self.check_finished.emit({"status": "cancelled"})
                return
            result = self.update_manager.check_for_updates(self.include_prerelease, self.prerelease_type)
            if self._is_cancelled:
                self.check_finished.emit({"status": "cancelled"})
                return
            self.check_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.check_finished.emit({"status": "error", "message": str(e)})

    def cancel(self):
        self._is_cancelled = True


class DownloadThread(QThread):
    progress_updated = Signal(dict)
    finished = Signal(dict)

    def __init__(self, download_url, version, max_threads=64):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self.max_threads = max_threads
        self._cancelled = False
        self._mutex = QMutex()
        self.downloader = None

    def run(self):
        try:
            with QMutexLocker(self._mutex):
                if self._cancelled:
                    self._emit_cancelled()
                    return

            from update.download_update import UpdateDownloader
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="converter_update_")

            try:
                with QMutexLocker(self._mutex):
                    if self._cancelled:
                        self._cleanup(temp_dir)
                        self._emit_cancelled()
                        return

                self.downloader = UpdateDownloader(
                    download_url=self.download_url,
                    target_directory=temp_dir,
                    max_threads=self.max_threads
                )

                def progress_callback(progress, downloaded, total_size):
                    with QMutexLocker(self._mutex):
                        if self._cancelled:
                            return False
                    self.progress_updated.emit({"progress": progress, "downloaded": downloaded, "total": total_size})
                    return True

                result = self.downloader.download_update(self.version, progress_callback)

                with QMutexLocker(self._mutex):
                    if self._cancelled:
                        self._cleanup(temp_dir)
                        self._emit_cancelled()
                        return

                if result.get("status") == "success":
                    result["temp_dir"] = temp_dir
                    result["downloader"] = self.downloader

                self.finished.emit(result)

            except Exception as e:
                self._cleanup(temp_dir)
                raise e

        except Exception as e:
            self.finished.emit({"status": "error", "message": str(e)})

    def _cleanup(self, temp_dir):
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _emit_cancelled(self):
        self.finished.emit({"status": "cancelled", "message": "Download cancelled by user"})

    def cancel(self):
        with QMutexLocker(self._mutex):
            self._cancelled = True
        if self.downloader:
            self.downloader.cancel()
        if not self.wait(3000):
            self.terminate()
            self.wait(1000)


class UpdateSettingsWidget(ScrollArea):
    __version__ = "2.1.0A11"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_manager = UpdateManager(self.__version__)
        self.check_thread = None
        self.download_thread = None
        self.current_update_info = None
        self._is_checking = False
        self._is_downloading = False

        self._detect_current_version_type()
        self.setup_ui()
        self.load_settings()
        self.connect_signals()

    def setup_ui(self):
        self.setObjectName("updateScrollWidget")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._view = QFrame(self)
        self._view.setObjectName("updateScrollView")
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_layout = QVBoxLayout(self._view)
        self.scroll_layout.setContentsMargins(30, 30, 30, 30)
        self.scroll_layout.setSpacing(20)
        self.setWidget(self._view)

        # 1. Top banner
        self._create_update_banner()
        self.scroll_layout.addWidget(self.update_banner)

        # 2. Center status card (product info + download progress)
        self._create_status_card()
        self.scroll_layout.addWidget(self.status_card)

        # 3. More Options group
        self._create_more_options()
        self.scroll_layout.addWidget(self.more_options_group)

        # 4. Release Notes (collapsible, at bottom)
        self.release_notes_card = SimpleExpandGroupSettingCard(
            FluentIcon.DOCUMENT,
            "Release Notes",
            "What's new in this version",
            parent=self._view
        )
        self.release_content_browser = TextBrowser()
        self.release_content_browser.setMinimumHeight(200)
        self.release_notes_card.addGroupWidget(self.release_content_browser)
        self.release_notes_card.setVisible(False)
        self.scroll_layout.addWidget(self.release_notes_card)

        self.scroll_layout.addStretch()

    def _create_update_banner(self):
        self.update_banner = CardWidget()
        layout = QHBoxLayout(self.update_banner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        icon_widget = IconWidget(FluentIcon.SYNC)
        icon_widget.setFixedSize(48, 48)
        layout.addWidget(icon_widget)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.banner_status_title = StrongBodyLabel("Ready to check for updates")
        channel_label = self._get_channel_display()
        self.banner_version_label = CaptionLabel(f"v{self.__version__}  ·  {channel_label}")
        text_layout.addWidget(self.banner_status_title)
        text_layout.addWidget(self.banner_version_label)
        layout.addLayout(text_layout, 1)

        self.check_btn = PrimaryPushButton("Check for Updates")
        self.check_btn.clicked.connect(self.check_for_updates)
        layout.addWidget(self.check_btn)

    def _create_status_card(self):
        """Center card: product/version on left, download status on right"""
        self.status_card = CardWidget()
        self.status_card.setVisible(False)
        layout = QHBoxLayout(self.status_card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # Left: product + version
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)
        self.status_product_label = StrongBodyLabel("Converter")
        self.status_version_label = CaptionLabel(f"v{self.__version__}")
        left_layout.addWidget(self.status_product_label)
        left_layout.addWidget(self.status_version_label)
        layout.addLayout(left_layout, 1)

        # Right: download progress (percentage + state text)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_percent_label = StrongBodyLabel("0%")
        self.status_percent_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.status_state_label = CaptionLabel("Downloading")
        self.status_state_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.status_progress_bar = ProgressBar()
        self.status_progress_bar.setRange(0, 100)
        self.status_progress_bar.setValue(0)
        self.status_progress_bar.setFixedWidth(160)
        right_layout.addWidget(self.status_percent_label)
        right_layout.addWidget(self.status_state_label)
        right_layout.addWidget(self.status_progress_bar)
        layout.addLayout(right_layout)

    @staticmethod
    def _relax_card_height(card):
        """Remove rigid fixed height on SettingCard so text is not clipped"""
        card.setMinimumHeight(card.minimumHeight())
        card.setMaximumHeight(16777215)

    def _create_more_options(self):
        """More Options section: StrongBodyLabel title + cards at top level"""
        self.more_options_group = SettingCardGroup("More Options", self)

        # --- Update Channel ---
        available_channels = self._get_available_channels()
        self.channel_combo = ComboBox()
        self.channel_combo.addItems(available_channels)
        channel_card = SettingCard(FluentIcon.SYNC, "Update Channel",
                                   "Select which update channel to check",
                                   parent=self.more_options_group)
        channel_card.hBoxLayout.addWidget(self.channel_combo, 0, Qt.AlignmentFlag.AlignRight)
        channel_card.hBoxLayout.addSpacing(16)
        self._relax_card_height(channel_card)
        self.more_options_group.addSettingCard(channel_card)

        # --- Pause Updates ---
        self.pause_combo = ComboBox()
        self.pause_combo.addItems(["Not paused", "Pause for 1 week", "Pause for 2 weeks", "Pause for 3 weeks"])
        pause_card = SettingCard(FluentIcon.PAUSE, "Pause Updates",
                                 "Temporarily pause automatic update checks",
                                 parent=self.more_options_group)
        pause_card.hBoxLayout.addWidget(self.pause_combo, 0, Qt.AlignmentFlag.AlignRight)
        pause_card.hBoxLayout.addSpacing(16)
        self._relax_card_height(pause_card)
        self.more_options_group.addSettingCard(pause_card)

        # --- Download Update ---
        self.download_update_card = SettingCard(FluentIcon.DOWNLOAD, "Download Update",
                                                "Download the latest available update",
                                                parent=self.more_options_group)
        self.download_btn = PrimaryPushButton("Download")
        self.download_btn.clicked.connect(self._handle_download_click)
        self.download_btn.setEnabled(False)
        self.download_update_card.hBoxLayout.addWidget(self.download_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.download_update_card.hBoxLayout.addSpacing(16)
        self._relax_card_height(self.download_update_card)
        self.more_options_group.addSettingCard(self.download_update_card)

        # --- Restart ---
        self.restart_card = SettingCard(FluentIcon.SYNC, "Restart Application",
                                        "Restart to apply the downloaded update",
                                        parent=self.more_options_group)
        self.restart_btn = PrimaryPushButton("Restart")
        self.restart_btn.clicked.connect(self.restart_application)
        self.restart_btn.setEnabled(False)
        self.restart_card.hBoxLayout.addWidget(self.restart_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.restart_card.hBoxLayout.addSpacing(16)
        self._relax_card_height(self.restart_card)
        self.more_options_group.addSettingCard(self.restart_card)

        # --- Update History ---
        self.history_card = SimpleExpandGroupSettingCard(
            FluentIcon.HISTORY, "Update History", "View previously installed updates",
            parent=self.more_options_group)
        self.history_browser = TextBrowser()
        self.history_browser.setFixedHeight(200)
        self.history_browser.setPlainText("No update history available.")
        self.history_card.addGroupWidget(self.history_browser)
        self.more_options_group.addSettingCard(self.history_card)

        # --- Advanced Options ---
        self.advanced_card = ExpandGroupSettingCard(
            FluentIcon.DEVELOPER_TOOLS, "Advanced Options",
            "Configure automatic update behavior",
            parent=self.more_options_group)
        self.auto_install_switch = SwitchSettingCard(
            FluentIcon.DOWNLOAD, "Install After Download",
            "Automatically install update when download completes",
            parent=self.advanced_card)
        self.auto_check_switch = SwitchSettingCard(
            FluentIcon.SYNC, "Auto Check for Updates",
            "Automatically check for updates on startup",
            parent=self.advanced_card)
        self._relax_card_height(self.auto_install_switch)
        self._relax_card_height(self.auto_check_switch)
        self.advanced_card.addGroupWidget(self.auto_install_switch)
        self.advanced_card.addGroupWidget(self.auto_check_switch)
        self.more_options_group.addSettingCard(self.advanced_card)

    def _get_available_channels(self):
        if self.is_internal_version:
            if self.is_alpha_version:
                return ["Stable", "Alpha"]
            elif self.is_deepdev_version:
                return ["Stable", "Deepdev"]
        return ["Stable", "RC (Release Candidate)", "Beta", "Deepdev", "Alpha"]

    def _get_channel_display(self):
        if self.is_alpha_version:
            return "Alpha"
        elif self.is_deepdev_version:
            return "Deepdev"
        return "Stable"

    def connect_signals(self):
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)

    def _detect_current_version_type(self):
        try:
            version_info = self.update_manager._parse_version(self.__version__)
            _, _, _, current_tag, _ = version_info
            self.is_alpha_version = (current_tag == 'A')
            self.is_deepdev_version = (current_tag == 'D')
            self.is_internal_version = self.is_alpha_version or self.is_deepdev_version
        except Exception:
            self.is_internal_version = False
            self.is_alpha_version = False
            self.is_deepdev_version = False

    def load_settings(self):
        settings = QSettings("MyCompany", "ConverterApp")
        prerelease_type = settings.value("update/prerelease_type", "stable", type=str)
        channel_map = {"stable": 0, "rc": 1, "beta": 2, "deepdev": 3, "alpha": 4}
        self.channel_combo.blockSignals(True)
        self.channel_combo.setCurrentIndex(channel_map.get(prerelease_type, 0))
        self.channel_combo.blockSignals(False)

        auto_install = settings.value("update/auto_install", False, type=bool)
        auto_check = settings.value("update/auto_check", True, type=bool)
        self.auto_install_switch.setChecked(auto_install)
        self.auto_check_switch.setChecked(auto_check)

        pause_weeks = settings.value("update/pause_weeks", 0, type=int)
        self.pause_combo.setCurrentIndex(min(pause_weeks, 3))

    def save_settings(self):
        try:
            type_map = {0: "stable", 1: "rc", 2: "beta", 3: "deepdev", 4: "alpha"}
            prerelease_type = type_map.get(self.channel_combo.currentIndex(), "stable")
            settings = QSettings("MyCompany", "ConverterApp")
            settings.setValue("update/prerelease_type", prerelease_type)
            settings.setValue("update/auto_install", self.auto_install_switch.isChecked())
            settings.setValue("update/auto_check", self.auto_check_switch.isChecked())
            settings.setValue("update/pause_weeks", self.pause_combo.currentIndex())
            settings.sync()
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _on_channel_changed(self, index):
        self.save_settings()

    def _get_update_check_params(self):
        prerelease_type = "stable"
        current_index = self.channel_combo.currentIndex()
        if self.is_internal_version:
            if self.is_alpha_version and current_index == 1:
                prerelease_type = "alpha"
            elif self.is_deepdev_version and current_index == 1:
                prerelease_type = "deepdev"
        else:
            type_map = {1: "rc", 2: "beta", 3: "deepdev", 4: "alpha"}
            prerelease_type = type_map.get(current_index, "stable")
        include_prerelease = (prerelease_type != "stable")
        return include_prerelease, prerelease_type if include_prerelease else None

    def _set_ui_busy(self, checking=False, downloading=False):
        self._is_checking = checking
        self._is_downloading = downloading
        self.check_btn.setEnabled(not checking and not downloading)
        self.channel_combo.setEnabled(not checking and not downloading)
        self.check_btn.setText("Checking..." if checking else "Check for Updates")

    def _reset_ui_after_operation(self):
        self._set_ui_busy(False, False)
        self.status_card.setVisible(False)

    def check_for_updates(self):
        if self._is_checking:
            return

        self._set_ui_busy(checking=True)
        setThemeColor(getSystemAccentColor(), save=False)

        self.download_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        self.release_notes_card.setVisible(False)
        self.release_notes_card.setExpand(False)
        self.banner_status_title.setText("Checking for updates…")

        QApplication.processEvents()

        include_prerelease, prerelease_type = self._get_update_check_params()
        self.save_settings()

        if self.check_thread and self.check_thread.isRunning():
            self.check_thread.cancel()
            self.check_thread.wait(1000)

        self.check_thread = CheckUpdateThread(self.update_manager, include_prerelease, prerelease_type)
        self.check_thread.check_finished.connect(self._on_check_finished)
        self.check_thread.error_occurred.connect(self._on_check_error)
        self.check_thread.start()

    def _on_check_error(self, error_msg):
        self._reset_ui_after_operation()
        self._show_error("Check Failed", f"Failed to check for updates: {error_msg}")

    def _on_check_finished(self, result):
        self._reset_ui_after_operation()
        status = result.get("status")

        if status == "update_available":
            latest = result['latest_version']
            version_type = ""
            if "version_info" in result:
                vt = self.update_manager.get_version_type_name(result["version_info"])
                if vt and vt != "Stable":
                    version_type = f" ({vt})"

            self.banner_status_title.setText(f"Update available: {latest}")
            self.download_btn.setEnabled(True)
            self.current_update_info = result

            if result.get("release_body"):
                self.release_content_browser.setMarkdown(result["release_body"])
                self.release_notes_card.setVisible(True)
                self.release_notes_card.setExpand(True)

            self._show_success("Update Available", f"Version {latest}{version_type} is available.")

        elif status == "error":
            self.banner_status_title.setText("Could not check for updates")
            self._show_error("Check Failed", result.get('message', 'Unknown error'))

        elif status == "cancelled":
            self.banner_status_title.setText("Ready to check for updates")

        else:
            self.banner_status_title.setText("You're up to date")
            self.download_btn.setEnabled(False)
            self.release_notes_card.setVisible(False)
            self._show_info("Up to Date", "You are using the latest version.")

    def _handle_download_click(self):
        if self._is_downloading:
            self.cancel_download()
        else:
            self.download_update()

    def download_update(self):
        if not self.current_update_info or self._is_downloading:
            return

        self._set_ui_busy(downloading=True)
        self.release_notes_card.setVisible(False)
        self.release_notes_card.setExpand(False)

        # Show status card
        self.status_card.setVisible(True)
        self.status_version_label.setText(f"v{self.__version__}  →  v{self.current_update_info.get('latest_version', '')}")
        self.status_percent_label.setText("0%")
        self.status_state_label.setText("Downloading")
        self.status_progress_bar.setValue(0)

        self.banner_status_title.setText("Downloading update…")
        self.download_btn.setText("Cancel")

        download_url = self.current_update_info.get("download_url")
        latest_version = self.current_update_info.get("latest_version")

        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait(2000)

        self.download_thread = DownloadThread(download_url, latest_version)
        self.download_thread.progress_updated.connect(self._on_progress_updated)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.start()

    def cancel_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_btn.setEnabled(False)
            self.download_thread.cancel()

            def check_stopped():
                if self.download_thread and not self.download_thread.isRunning():
                    self._show_cancelled_state()
                else:
                    QTimer.singleShot(500, check_stopped)

            QTimer.singleShot(500, check_stopped)

    def _show_cancelled_state(self):
        self._reset_ui_after_operation()
        self.banner_status_title.setText("Download cancelled")
        self.download_btn.setText("Download")
        self.download_btn.setEnabled(True)
        self._show_info("Cancelled", "Download was cancelled.")

    def _on_progress_updated(self, progress_data):
        if not progress_data:
            return
        progress = progress_data.get("progress", 0)
        self.status_progress_bar.setValue(int(progress))
        self.status_percent_label.setText(f"{progress:.0f}%")
        self.status_state_label.setText("Downloading")

    def _on_download_finished(self, result):
        self._reset_ui_after_operation()
        self.download_btn.setText("Download")
        status = result.get("status")

        if status == "success":
            self.banner_status_title.setText("Ready to restart")
            self.restart_btn.setEnabled(True)
            self._show_success("Download Complete", "Update downloaded. Restart to apply.")

        elif status == "cancelled":
            self._show_cancelled_state()

        else:
            self.banner_status_title.setText("Download failed")
            self._show_error("Download Failed", result.get("message", "Unknown error"))

    def restart_application(self):
        import subprocess
        try:
            subprocess.Popen([sys.executable] + sys.argv)
            QApplication.instance().quit()
        except Exception as e:
            self._show_error("Restart Failed", str(e))

    def _show_success(self, title, content):
        InfoBar.success(title=title, content=content, orient=Qt.Orientation.Horizontal,
                        isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self)

    def _show_error(self, title, content):
        InfoBar.error(title=title, content=content, orient=Qt.Orientation.Horizontal,
                      isClosable=True, position=InfoBarPosition.TOP, duration=5000, parent=self)

    def _show_info(self, title, content):
        InfoBar.info(title=title, content=content, orient=Qt.Orientation.Horizontal,
                     isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self)

    def closeEvent(self, event):
        if self.check_thread and self.check_thread.isRunning():
            self.check_thread.cancel()
            self.check_thread.wait(1000)
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait(2000)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = UpdateSettingsWidget()
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec())
