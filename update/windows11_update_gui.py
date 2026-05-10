# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QApplication, QFrame, QLabel
from PySide6.QtCore import QSettings, Qt, QThread, Signal, QTimer, QMutex, QMutexLocker
from PySide6.QtGui import QFont
from UIkit import (
    SettingCardGroup, SettingCard, SwitchSettingCard,
    CaptionLabel, StrongBodyLabel, BodyLabel, TextBrowser,
    ProgressBar, ComboBox, InfoBar, InfoBarPosition, FluentIcon,
    CardWidget, IconWidget, PrimaryPushButton, PushButton,
    SimpleExpandGroupSettingCard, ScrollArea, HyperlinkButton
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


class Windows11UpdateWidget(ScrollArea):
    __version__ = "2.1.0A11"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_manager = UpdateManager(self.__version__)
        self.check_thread = None
        self.download_thread = None
        self.current_update_info = None
        self._is_checking = False
        self._is_downloading = False
        self.last_check_time = None

        self._detect_current_version_type()
        self.setup_ui()
        self.load_settings()
        self.connect_signals()
        self._load_last_check_time()

    def setup_ui(self):
        self.setObjectName("win11UpdateWidget")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._view = QFrame(self)
        self._view.setObjectName("win11UpdateView")
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self.main_layout = QVBoxLayout(self._view)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(24)
        self.setWidget(self._view)

        self._create_top_status_area()
        self._create_update_notification_card()
        self._create_more_options()

        self.main_layout.addStretch()

    def _create_top_status_area(self):
        """顶部状态区域: 大图标 + 状态文字 + 检查按钮"""
        top_card = CardWidget()
        layout = QHBoxLayout(top_card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # 左侧: 图标 + 状态文字
        left_layout = QHBoxLayout()
        left_layout.setSpacing(20)

        self.status_icon = IconWidget(FluentIcon.SYNC)
        self.status_icon.setFixedSize(64, 64)
        left_layout.addWidget(self.status_icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        self.status_title = QLabel("Converter Update")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        self.status_title.setFont(title_font)

        self.status_subtitle = QLabel("You're up to date")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        self.status_subtitle.setFont(subtitle_font)

        self.last_check_label = CaptionLabel("Last checked: Never")

        text_layout.addWidget(self.status_title)
        text_layout.addWidget(self.status_subtitle)
        text_layout.addWidget(self.last_check_label)

        left_layout.addLayout(text_layout)
        layout.addLayout(left_layout, 1)

        # 右侧: 检查按钮
        self.check_btn = PrimaryPushButton("Check for updates")
        self.check_btn.setFixedHeight(40)
        self.check_btn.clicked.connect(self.check_for_updates)
        layout.addWidget(self.check_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.main_layout.addWidget(top_card)

    def _create_update_notification_card(self):
        """更新通知卡片: 仅在有更新时显示"""
        self.update_notification_card = CardWidget()
        self.update_notification_card.setVisible(False)

        layout = QHBoxLayout(self.update_notification_card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 左侧: 信息图标 + 文字
        info_icon = IconWidget(FluentIcon.INFO)
        info_icon.setFixedSize(24, 24)
        layout.addWidget(info_icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.update_version_label = StrongBodyLabel("Converter version 2.1.0A12 is available.")
        self.update_link = HyperlinkButton("", "See what's in this update")
        self.update_link.clicked.connect(self._show_release_notes)

        text_layout.addWidget(self.update_version_label)
        text_layout.addWidget(self.update_link)
        layout.addLayout(text_layout, 1)

        # 右侧: 下载按钮 + 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.download_install_btn = PrimaryPushButton("Download & install")
        self.download_install_btn.clicked.connect(self.download_update)
        self.download_install_btn.setFixedHeight(32)

        self.close_notification_btn = PushButton(FluentIcon.CLOSE, "")
        self.close_notification_btn.setFixedSize(32, 32)
        self.close_notification_btn.clicked.connect(lambda: self.update_notification_card.setVisible(False))

        btn_layout.addWidget(self.download_install_btn)
        btn_layout.addWidget(self.close_notification_btn)
        layout.addLayout(btn_layout)

        self.main_layout.addWidget(self.update_notification_card)

    def _create_more_options(self):
        """More Options 区域"""
        self.more_options_group = SettingCardGroup("More options", self._view)

        # Pause updates
        self.pause_card = SettingCard(FluentIcon.PAUSE, "Pause updates", "")
        self.pause_combo = ComboBox()
        self.pause_combo.addItems(["Pause for 1 week", "Pause for 2 weeks", "Pause for 3 weeks"])
        self.pause_card.hBoxLayout.addWidget(self.pause_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.pause_card.hBoxLayout.addSpacing(16)
        self.more_options_group.addSettingCard(self.pause_card)

        # Update history
        self.history_card = SimpleExpandGroupSettingCard(
            FluentIcon.HISTORY, "Update history", "", parent=self.more_options_group)
        self.history_browser = TextBrowser()
        self.history_browser.setFixedHeight(180)
        self.history_browser.setPlainText("No update history available.")
        self.history_card.addGroupWidget(self.history_browser)
        self.more_options_group.addSettingCard(self.history_card)

        # Advanced options
        self.advanced_card = SimpleExpandGroupSettingCard(
            FluentIcon.DEVELOPER_TOOLS, "Advanced options",
            "Delivery optimization, optional updates, active hours, other update settings",
            parent=self.more_options_group)

        advanced_content = QFrame()
        advanced_layout = QVBoxLayout(advanced_content)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)

        self.auto_check_switch = SwitchSettingCard(
            FluentIcon.SYNC, "Auto check for updates",
            "Automatically check for updates on startup")
        self.auto_install_switch = SwitchSettingCard(
            FluentIcon.DOWNLOAD, "Auto install after download",
            "Automatically install update when download completes")

        channel_card = SettingCard(FluentIcon.SYNC, "Update channel", "Select which update channel to check")
        self.channel_combo = ComboBox()
        self.channel_combo.addItems(self._get_available_channels())
        channel_card.hBoxLayout.addWidget(self.channel_combo, 0, Qt.AlignmentFlag.AlignRight)
        channel_card.hBoxLayout.addSpacing(16)

        advanced_layout.addWidget(self.auto_check_switch)
        advanced_layout.addWidget(self.auto_install_switch)
        advanced_layout.addWidget(channel_card)

        self.advanced_card.addGroupWidget(advanced_content)
        self.more_options_group.addSettingCard(self.advanced_card)

        self.main_layout.addWidget(self.more_options_group)

    def _get_available_channels(self):
        if self.is_internal_version:
            if self.is_alpha_version:
                return ["Stable", "Alpha"]
            elif self.is_deepdev_version:
                return ["Stable", "Deepdev"]
        return ["Stable", "RC", "Beta", "Deepdev", "Alpha"]

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

    def connect_signals(self):
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        self.auto_check_switch.checkedChanged.connect(self.save_settings)
        self.auto_install_switch.checkedChanged.connect(self.save_settings)
        self.pause_combo.currentIndexChanged.connect(self.save_settings)

    def load_settings(self):
        settings = QSettings("pyquick", "converter")
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
        self.pause_combo.setCurrentIndex(min(pause_weeks, 2))

    def save_settings(self):
        try:
            type_map = {0: "stable", 1: "rc", 2: "beta", 3: "deepdev", 4: "alpha"}
            prerelease_type = type_map.get(self.channel_combo.currentIndex(), "stable")
            settings = QSettings("pyquick", "converter")
            settings.setValue("update/prerelease_type", prerelease_type)
            settings.setValue("update/auto_install", self.auto_install_switch.isChecked())
            settings.setValue("update/auto_check", self.auto_check_switch.isChecked())
            settings.setValue("update/pause_weeks", self.pause_combo.currentIndex())
            settings.sync()
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _on_channel_changed(self, index):
        self.save_settings()

    def _load_last_check_time(self):
        settings = QSettings("pyquick", "converter")
        last_check = settings.value("update/last_check_time", "", type=str)
        if last_check:
            try:
                dt = datetime.fromisoformat(last_check)
                self._update_last_check_label(dt)
            except:
                pass

    def _save_last_check_time(self):
        settings = QSettings("pyquick", "converter")
        settings.setValue("update/last_check_time", datetime.now().isoformat())
        settings.sync()

    def _update_last_check_label(self, dt=None):
        if dt is None:
            dt = datetime.now()
        self.last_check_time = dt
        time_str = dt.strftime("Today, %I:%M %p")
        self.last_check_label.setText(f"Last checked: {time_str}")

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

    def check_for_updates(self):
        if self._is_checking:
            return

        self._is_checking = True
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking...")
        self.status_subtitle.setText("Checking for updates...")
        setThemeColor(getSystemAccentColor(), save=False)

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
        self._is_checking = False
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for updates")
        self.status_subtitle.setText("Could not check for updates")
        self._show_error("Check Failed", f"Failed to check for updates: {error_msg}")

    def _on_check_finished(self, result):
        self._is_checking = False
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for updates")
        self._update_last_check_label()
        self._save_last_check_time()

        status = result.get("status")

        if status == "update_available":
            latest = result['latest_version']
            self.status_subtitle.setText(f"Update available: {latest}")
            self.current_update_info = result

            version_type = ""
            if "version_info" in result:
                vt = self.update_manager.get_version_type_name(result["version_info"])
                if vt and vt != "Stable":
                    version_type = f" ({vt})"

            self.update_version_label.setText(f"Converter version {latest}{version_type} is available.")
            self.update_link.setUrl(result.get("download_url", ""))
            self.update_notification_card.setVisible(True)

            self._show_success("Update Available", f"Version {latest}{version_type} is available.")

        elif status == "error":
            self.status_subtitle.setText("Could not check for updates")
            self._show_error("Check Failed", result.get('message', 'Unknown error'))

        elif status == "cancelled":
            self.status_subtitle.setText("You're up to date")

        else:
            self.status_subtitle.setText("You're up to date")
            self.update_notification_card.setVisible(False)
            self._show_info("Up to Date", "You are using the latest version.")

    def download_update(self):
        if not self.current_update_info or self._is_downloading:
            return

        self._is_downloading = True
        self.download_install_btn.setText("Downloading...")
        self.download_install_btn.setEnabled(False)
        self.status_subtitle.setText("Downloading update...")

        download_url = self.current_update_info.get("download_url")
        latest_version = self.current_update_info.get("latest_version")

        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait(2000)

        self.download_thread = DownloadThread(download_url, latest_version)
        self.download_thread.progress_updated.connect(self._on_progress_updated)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.start()

    def _on_progress_updated(self, progress_data):
        if not progress_data:
            return
        progress = progress_data.get("progress", 0)
        self.status_subtitle.setText(f"Downloading update... {progress:.0f}%")

    def _on_download_finished(self, result):
        self._is_downloading = False
        self.download_install_btn.setText("Download & install")
        self.download_install_btn.setEnabled(True)

        status = result.get("status")

        if status == "success":
            self.status_subtitle.setText("Ready to install")
            self.update_notification_card.setVisible(False)
            self._show_success("Download Complete", "Update downloaded. Restart to apply.")
            if self.auto_install_switch.isChecked():
                QTimer.singleShot(1000, self.restart_application)

        elif status == "cancelled":
            self.status_subtitle.setText("Download cancelled")
            self._show_info("Cancelled", "Download was cancelled.")

        else:
            self.status_subtitle.setText("Download failed")
            self._show_error("Download Failed", result.get("message", "Unknown error"))

    def _show_release_notes(self):
        if self.current_update_info and self.current_update_info.get("release_body"):
            from PySide6.QtWidgets import QDialog, QVBoxLayout
            dialog = QDialog(self)
            dialog.setWindowTitle("Release Notes")
            dialog.resize(600, 400)
            layout = QVBoxLayout(dialog)
            browser = TextBrowser()
            browser.setMarkdown(self.current_update_info["release_body"])
            layout.addWidget(browser)
            dialog.exec()

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
    widget = Windows11UpdateWidget()
    widget.resize(900, 700)
    widget.show()
    sys.exit(app.exec())

