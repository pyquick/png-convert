# -*- coding: utf-8 -*-
#Please do not change import
from concurrent.futures import thread
import multiprocessing
import sys
import os
import threading

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QGroupBox,
    QSpacerItem,
    QSizePolicy,
    QProgressBar,
    QMessageBox,
    QAbstractButton
)
from PySide6.QtCore import QSettings, Qt, QThread, Signal, QTimer, QTimer
from PySide6.QtGui import QFont
from darkdetect import isDark
from update.update_manager import UpdateManager
from update.download_update import download_and_apply_update
from qframelesswindow.utils import getSystemAccentColor
from qfluentwidgets import *
import time
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
        self.downloader = None  # Initialize downloader attribute
        
    def run(self):
        try:
            print(f"DownloadThread started, is_cancelled: {self.is_cancelled}")
            
            # Check if cancelled before starting download
            if self.is_cancelled:
                print("DownloadThread: cancelled before download")
                result = {
                    "status": "cancelled",
                    "message": "Download cancelled by user"
                }
                self.finished.emit(result)
                return
            
            # Create a simple progress callback that emits signals
            def progress_callback(progress, downloaded, total_size):
                if not self.is_cancelled:
                    progress_data = {
                        "progress": progress,
                        "downloaded": downloaded,
                        "total": total_size
                    }
                    self.progress_updated.emit(progress_data)
            
            # Set the progress callback
            self.progress_callback = progress_callback
            
            # Create update info dictionary
            update_info = {
                "download_url": self.download_url,
                "latest_version": self.version
            }
            
            # Create UpdateDownloader instance for cancellation
            from update.download_update import UpdateDownloader
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="update_")
            
            try:
                self.downloader = UpdateDownloader(
                    download_url=self.download_url,
                    target_directory=temp_dir,
                    max_threads=64  # Use 64 threads
                )
                
                # Download update only (don't apply it)
                print("DownloadThread: starting download")
                result = self.downloader.download_update(self.version, progress_callback)
                print(f"DownloadThread: download completed with status: {result.get('status')}")
                
                # Check if the download was cancelled
                if result.get("status") == "cancelled":
                    print("DownloadThread: result status is cancelled")
                    self.finished.emit(result)
                    return
                
                # Check if cancelled during download
                if self.is_cancelled or (self.downloader and hasattr(self.downloader, '_cancelled') and self.downloader._cancelled):
                    print("DownloadThread: cancelled during download")
                    result = {
                        "status": "cancelled",
                        "message": "Download cancelled by user",
                        "temp_dir": temp_dir
                    }
                    self.finished.emit(result)
                    return
                    
                # Check again if cancelled
                if self.is_cancelled:
                    print("DownloadThread: cancelled after download")
                    result = {
                        "status": "cancelled",
                        "message": "Download cancelled by user",
                        "temp_dir": temp_dir
                    }
                    self.finished.emit(result)
                    return
                
                # Add downloader to result for cleanup
                result["downloader"] = self.downloader
                result["temp_dir"] = temp_dir
                print("DownloadThread: emitting success result")
                self.finished.emit(result)
                
            except Exception as e:
                print(f"DownloadThread exception: {e}")
                error_result = {
                    "status": "error",
                    "message": f"Download failed: {str(e)}",
                    "temp_dir": temp_dir
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
        """Cancel the download"""
        print("DownloadThread: cancel() called")
        self.is_cancelled = True
        
        # Cancel the downloader
        if self.downloader:
            print("DownloadThread: cancelling downloader")
            self.downloader.cancel()
            # Wait a moment to ensure cancellation is complete
            import time
            time.sleep(0.1)
        
        # Request thread exit
        self.quit()
        
        # Wait for thread to completely stop
        if not self.wait(1000):  # Wait up to 1 second
            print("Warning: DownloadThread did not stop within 1 second, forcing termination")
            self.terminate()
            self.wait(500)  # Wait another 500ms to ensure termination is complete

class UpdateDialog(QWidget):
    __version__ = "2.0.0B8" 

    def __init__(self):
        super().__init__()
        # Remove SystemThemeListener to avoid thread issues
        # self.themeListener = SystemThemeListener(self)
       
       
        self.setWindowTitle("Update Settings")
        self.update_manager = UpdateManager(self.__version__)
        self.check_thread = None
        self.download_thread = None
       
        # Detect current version type
        self._detect_current_version_type()
        
        self.init_ui()
        self.load_settings()
        self.connect_auto_save_signals()
       
    def _detect_current_version_type(self):
        """检测当前版本类型，如果是Alpha或Deepdev版本，则限制可用通道"""
        try:
            # 解析当前版本
            version_info = self.update_manager._parse_version(self.__version__)
            _, _, _, current_tag, _ = version_info
            
            # 检查是否为Alpha或Deepdev版本
            self.is_alpha_version = (current_tag == 'A')
            self.is_deepdev_version = (current_tag == 'D')
            self.is_internal_version = self.is_alpha_version or self.is_deepdev_version
            
            if self.is_internal_version:
                print(f"检测到内部版本: {self.__version__} (标签: {current_tag})")
            
        except Exception as e:
            print(f"版本检测失败: {e}")
            self.is_internal_version = False
            self.is_alpha_version = False
            self.is_deepdev_version = False
    

    def init_ui(self):
       
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        update_group = QGroupBox("Update Settings")
        update_layout = QVBoxLayout()
        update_layout.setContentsMargins(25, 25, 25, 25)
        update_layout.setSpacing(20)
        
        # 添加顶部间距
        update_layout.addSpacerItem(QSpacerItem(0, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        
        # 添加版本类型选择器
        prerelease_container = QHBoxLayout()
        prerelease_container.setSpacing(10)
        
        self.prerelease_type_label = QLabel("Update channel:")
        prerelease_container.addWidget(self.prerelease_type_label)
        
        self.prerelease_type_combo = ModelComboBox()
        setCustomStyleSheet(self.prerelease_type_combo,CON.qss_combo_2,CON.qss_combo_2)
        # 根据版本类型设置可用通道
        if self.is_internal_version:
            # 内部版本只显示对应的通道和稳定版
            if self.is_alpha_version:
                self.prerelease_type_combo.addItems([ "Alpha"])
                print("Alpha版本：只显示Alpha通道")
            elif self.is_deepdev_version:
                self.prerelease_type_combo.addItems(["Deepdev"])
                print("Deepdev版本：只显示Deepdev通道")
        else:
            # 普通版本显示所有通道
            self.prerelease_type_combo.addItems(["Stable", "RC (Release Candidate)", "Beta", "Deepdev", "Alpha"])
        
        self.prerelease_type_combo.setFixedWidth(200)
        prerelease_container.addWidget(self.prerelease_type_combo)
        
        prerelease_container.addStretch()
        update_layout.addLayout(prerelease_container)
        
        self.update_status_label = QLabel("Ready to check for updates.")
        self.update_status_label.setMinimumHeight(60)
        self.update_status_label.setMinimumWidth(550)
        self.update_status_label.setWordWrap(True)
        #self.update_status_label.setStyleSheet("QLabel { padding: 8px; background-color: #f8f9fa; border-radius: 5px; }")
        update_layout.addWidget(self.update_status_label)
        
        # 更新内容显示区域
        self.release_content_browser = TextBrowser()
        self.release_content_browser.setMinimumHeight(150)
        self.release_content_browser.setVisible(False)
        update_layout.addWidget(self.release_content_browser)
        
        # 下载进度条
        self.progress_bar = IndeterminateProgressBar()
        self.progress_bar.setVisible(False)
        update_layout.addWidget(self.progress_bar)
        
        # 实际下载进度条
        self.download_progress_bar = ProgressBar()
        self.download_progress_bar.setRange(0, 100)
        self.download_progress_bar.setValue(0)
        self.download_progress_bar.setVisible(False)
        update_layout.addWidget(self.download_progress_bar)
        
        # 进度标签（显示百分比、下载大小、速度等信息）
        self.progress_label = QLabel("0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.progress_label.setFont(font)
        self.progress_label.setVisible(False)
        update_layout.addWidget(self.progress_label)
        
        # 按钮容器
        button_container = QHBoxLayout()
        button_container.setSpacing(15)
        
        self.update_button = PrimaryPushButton("Check for Updates")
        self.update_button.setFixedSize(180, 60)
        setCustomStyleSheet(self.update_button, CON.qss_debug, CON.qss_debug)
        self.update_button.clicked.connect(self.check_for_updates)
        
        self.download_button =PrimaryPushButton("Download Update")
        self.download_button.setFixedSize(180, 60)
        setCustomStyleSheet(self.download_button, CON.qss_debug, CON.qss_debug)
        self.download_button.clicked.connect(self.download_update)
        self.download_button.setVisible(False)
        self.download_button.setEnabled(False)
        
        self.restart_button = PrimaryPushButton("Restart Application")
        self.restart_button.setFixedSize(180, 60)
        setCustomStyleSheet(self.restart_button, CON.qss_debug, CON.qss_debug)
        self.restart_button.clicked.connect(self.restart_application)
        self.restart_button.setVisible(False)
        self.restart_button.setEnabled(False)
        
        button_container.addStretch()
        button_container.addWidget(self.update_button)
        button_container.addWidget(self.download_button)
        button_container.addWidget(self.restart_button)
        button_container.addStretch()
        update_layout.addLayout(button_container)
        
        # 添加底部间距
        update_layout.addSpacerItem(QSpacerItem(0, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        
        update_group.setLayout(update_layout)
        main_layout.addWidget(update_group)
        
        self.setLayout(main_layout)

    
        
        # 设置按钮字体
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.update_button.setFont(font)
        self.download_button.setFont(font)
        self.restart_button.setFont(font)
        
        # 设置标签字体
        label_font = QFont()
        label_font.setPointSize(11)
        self.update_status_label.setFont(label_font)
        
        # 设置标签字体
        label_font = QFont()
        label_font.setPointSize(11)
        self.prerelease_type_label.setFont(label_font)
       
       
       
         

    def load_settings(self):
        settings = QSettings("MyCompany", "ConverterApp")
        prerelease_type = settings.value("update/prerelease_type", "stable", type=str)
        # 设置版本类型选择器
        type_index = 0  # 默认为 "Stable"
        if prerelease_type == "rc":
            type_index = 1
        elif prerelease_type == "beta":
            type_index = 2
        elif prerelease_type == "deepdev":
            type_index = 3
        elif prerelease_type == "alpha":
            type_index = 4
        self.prerelease_type_combo.setCurrentIndex(type_index)

    def save_settings(self):
        """保存设置"""
        try:
            # 保存更新通道设置
            prerelease_type = "stable"  # 默认
            
            # 根据选择的索引确定类型
            current_index = self.prerelease_type_combo.currentIndex()
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
    
    def connect_auto_save_signals(self):
        """Connect UI controls to auto-save functionality"""
        # Connect combo box to auto-save
        self.prerelease_type_combo.currentIndexChanged.connect(self.on_update_channel_changed)
    
    def auto_save_settings(self):
        """Auto-save settings immediately upon change"""
        try:
            # Save settings immediately
            self.save_settings()
        except Exception as e:
            print(f"Error in auto_save_settings: {e}")
    
    def on_update_channel_changed(self, index):
        """处理更新通道选择变化"""
        # 自动保存设置
        self.auto_save_settings()
    
    def _get_update_check_params(self):
        """获取更新检查参数"""
        prerelease_type = "stable"  # 默认稳定版
        
        current_index = self.prerelease_type_combo.currentIndex()
        current_text = self.prerelease_type_combo.currentText()
        
        # 根据版本类型调整索引映射
        if self.is_internal_version:
            if self.is_alpha_version:
                # Alpha版本：索引0=Stable, 索引1=Alpha
                if current_index == 1:
                    prerelease_type = "alpha"
            elif self.is_deepdev_version:
                # Deepdev版本：索引0=Stable, 索引1=Deepdev
                if current_index == 1:
                    prerelease_type = "deepdev"
        else:
            # 普通版本：标准索引映射
            if current_index == 1:
                prerelease_type = "rc"
            elif current_index == 2:
                prerelease_type = "beta"
            elif current_index == 3:
                prerelease_type = "deepdev"
            elif current_index == 4:
                prerelease_type = "alpha"
        
        # 根据通道类型决定是否包含预发布版本
        include_prerelease = (prerelease_type != "stable")
        
        return include_prerelease, prerelease_type if include_prerelease else None

    def check_for_updates(self):
        """检查更新"""
        self.update_status_label.setText("Checking for updates...")
        setThemeColor(getSystemAccentColor(), save=False)
        self.update_button.setEnabled(False)
        
        # 隐藏TextBrowser、下载按钮和重启按钮
        self.release_content_browser.setVisible(False)
        self.download_button.setVisible(False)
        self.restart_button.setVisible(False)
        
        # 显示进度条并设置主题色
        self.progress_bar.setVisible(True)
        self.progress_bar.resume()
        self.progress_bar.start()
        QApplication.processEvents()  # 确保界面更新
        
        # 获取更新检查参数
        include_prerelease, prerelease_type = self._get_update_check_params()
        
        # Auto-save settings immediately when checking for updates
        self.auto_save_settings()
        
        # 启动检查更新线程
        self.check_thread = CheckUpdateThread(self.update_manager, include_prerelease, prerelease_type if include_prerelease else None)
        self.check_thread.check_finished.connect(self.on_check_finished)
        self.check_thread.start()
    
    def on_check_finished(self, result):
        if result["status"] == "update_available":
            # 获取版本类型信息
            version_type = ""
            if "version_info" in result:
                version_tuple = result["version_info"]
                version_type = self.update_manager.get_version_type_name(version_tuple)
                if version_type and version_type != "Stable":
                    version_type = f" ({version_type})"
            
            self.update_status_label.setText(f"✅ {result['message']}\n\nVersion: {result['latest_version']}{version_type}")
            self.download_button.setVisible(True)
            self.download_button.setEnabled(True)
            self.current_update_info = result
            
            # 显示更新内容
            if result.get("release_body"):
                self.release_content_browser.setMarkdown(result["release_body"])
                self.release_content_browser.setVisible(True)
            else:
                self.release_content_browser.setVisible(False)
        elif result["status"] == "error":
            self.update_status_label.setText(f"❌ Check failed: {result['message']}")
            self.download_button.setVisible(False)
            self.release_content_browser.setVisible(False)
        else:
            self.update_status_label.setText(f"ℹ️ {result['message']}")
            self.download_button.setVisible(False)
            self.release_content_browser.setVisible(False)
        
        self.progress_bar.pause()
        self.progress_bar.setVisible(False)
        self.update_button.setEnabled(True)
    
    def download_update(self):
        if hasattr(self, 'current_update_info'):
            self.download_button.setEnabled(False)
            self.update_button.setEnabled(False)
            
            # 隐藏TextBrowser
            self.release_content_browser.setVisible(False)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.start()
            self.download_progress_bar.setVisible(False)
            self.update_status_label.setText("Download in progress...")
            
            # 显示进度标签
            self.progress_label.setText("0%")
            self.progress_label.setVisible(True)
            
            # 获取下载URL和版本信息
            download_url = self.current_update_info.get("download_url")
            latest_version = self.current_update_info.get("latest_version")
            
            # 获取预发布设置
            include_prerelease, prerelease_type = self._get_update_check_params()
            
            # 重置下载计时器
            if hasattr(self, '_download_start_time'):
                delattr(self, '_download_start_time')
            if hasattr(self, '_last_downloaded'):
                delattr(self, '_last_downloaded')
            if hasattr(self, '_last_time'):
                delattr(self, '_last_time')
            
            # 使用新的DownloadThread类
            self.download_thread = DownloadThread(download_url, latest_version, include_prerelease)
            self.download_thread.progress_updated.connect(self.on_progress_updated)
            self.download_thread.finished.connect(self.on_download_finished)
            self.download_thread.start()
            
            # 将下载按钮改为取消按钮
            self.download_button.setText("Cancel Download")
            self.download_button.setEnabled(True)
            self.download_button.clicked.disconnect()
            self.download_button.clicked.connect(self.cancel_download)
    
    def cancel_download(self):
        """取消下载"""
        if hasattr(self, 'download_thread') and self.download_thread is not None and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_button.setEnabled(False)
            self.update_status_label.setText("Cancelling download...")
            
            # 设置一个定时器来检查线程是否已停止
            def check_thread_stopped():
                # 检查线程是否已停止
                if self.download_thread is None:
                    # 线程已被清理，直接返回
                    return
                    
                if not self.download_thread.isRunning():
                    # 线程已停止，显示取消状态
                    self.show_cancelled_state()
                else:
                    # 线程仍在运行，继续等待
                    QTimer.singleShot(500, check_thread_stopped)
            
            # 开始检查线程状态
            QTimer.singleShot(500, check_thread_stopped)
    
    def start_swing_animation(self):
        """启动左右摆动动画"""
        pass
    
    def update_swing_animation(self):
        """更新摆动动画"""
        pass
    
    def on_progress_updated(self, progress_data):
        """处理下载进度更新"""
        if not progress_data:
            return
            
        # 从progress_data中获取进度信息
        progress = progress_data.get("progress", 0)
        downloaded_bytes = progress_data.get("downloaded", 0)
        total_bytes = progress_data.get("total", 0)
        
        # 更新进度条显示实际进度
        if progress > 0:
            # 显示实际进度条，隐藏不确定进度条
            self.progress_bar.setVisible(False)
            self.download_progress_bar.setVisible(True)
            self.download_progress_bar.setValue(progress)
            
            # 计算下载速度和时间估计
            current_time = time.time()
            if not hasattr(self, '_download_start_time'):
                self._download_start_time = current_time
                self._last_downloaded = 0
                self._last_time = current_time
            
            # 计算平均速度和剩余时间
            elapsed_time = current_time - self._download_start_time
            if elapsed_time > 1.0:  # 至少1秒后再计算速度
                # 计算平均下载速度
                avg_download_speed = downloaded_bytes / elapsed_time  # bytes per second
                
                # 计算剩余时间
                remaining_bytes = total_bytes - downloaded_bytes
                if avg_download_speed > 0 and total_bytes > 0:
                    remaining_time = remaining_bytes / avg_download_speed
                    # 格式化剩余时间
                    if remaining_time > 3600:
                        eta_str = f"{remaining_time/3600:.1f}h"
                    elif remaining_time > 60:
                        eta_str = f"{remaining_time/60:.1f}m"
                    else:
                        eta_str = f"{remaining_time:.0f}s"
                else:
                    eta_str = "计算中"
                
                # 格式化文件大小
                def format_size(bytes_size):
                    if bytes_size >= 1024*1024*1024:
                        return f"{bytes_size/(1024*1024*1024):.2f} GB"
                    elif bytes_size >= 1024*1024:
                        return f"{bytes_size/(1024*1024):.2f} MB"
                    elif bytes_size >= 1024:
                        return f"{bytes_size/1024:.2f} KB"
                    else:
                        return f"{bytes_size} B"
                
                # 更新数字进度标签
                if hasattr(self, 'progress_label'):
                    downloaded_str = format_size(downloaded_bytes)
                    total_str = format_size(total_bytes)
                    speed_str = format_size(avg_download_speed) + "/s"
                    
                    self.progress_label.setText(
                        f"{progress}% - {downloaded_str}/{total_str} - {speed_str} - ETA: {eta_str}"
                    )
        
        if progress == 100:
            self.progress_bar.pause()
        
    def on_download_finished(self, result):
        # 停止进度条
        if result["status"] == "success":
            # 下载成功，立即开始应用更新
            self.progress_bar.pause()
            self.progress_bar.setVisible(False)
            self.download_progress_bar.setVisible(False)
            
            # 隐藏数字进度标签
            if hasattr(self, 'progress_label'):
                self.progress_label.setVisible(False)
            
            # 清理下载计时器变量
            if hasattr(self, '_download_start_time'):
                delattr(self, '_download_start_time')
            if hasattr(self, '_last_downloaded'):
                delattr(self, '_last_downloaded')
            if hasattr(self, '_last_time'):
                delattr(self, '_last_time')
            
            # 清理下载线程
            if hasattr(self, 'download_thread') and self.download_thread:
                if self.download_thread.downloader:
                    self.download_thread.downloader.cleanup()
                
                # 确保线程完全停止后再设置为None
                if self.download_thread.isRunning():
                    self.download_thread.quit()
                    self.download_thread.wait(2000)  # 最多等待2秒
                
                self.download_thread = None
            
            # 保存更新信息
            self.update_result = result
            
            # 显示应用更新进度
            self.update_status_label.setText("Applying updates...")
            
            # 使用IndeterminateProgressBar显示应用更新进度
            self.progress_bar.setVisible(True)
            self.progress_bar.start()
            
            # 立即执行更新应用
            self.apply_update()
            
        else:
            # 下载失败或取消
            if result["status"] == "cancelled":
                # 先将进度条设置为100%
                self.download_progress_bar.setValue(100)
                self.progress_label.setText("100%")
                QApplication.processEvents()  # 确保界面更新
                
                # 短暂延迟后显示取消状态
                QTimer.singleShot(500, lambda: self.show_cancelled_state())
            else:
                # 确保错误消息正确处理非ASCII字符
                try:
                    error_message = str(result['message'])
                    self.update_status_label.setText(f"❌ 下载失败: {error_message}")
                except Exception as e:
                    # 如果出现编码问题，显示基本错误信息
                    self.update_status_label.setText(f"❌ 下载失败: 处理错误消息时出现编码问题")
                
                self.progress_bar.setVisible(False)
                self.download_progress_bar.setVisible(False)
                
                # 隐藏数字进度标签
                if hasattr(self, 'progress_label'):
                    self.progress_label.setVisible(False)
                
                # 清理下载计时器变量
                if hasattr(self, '_download_start_time'):
                    delattr(self, '_download_start_time')
                if hasattr(self, '_last_downloaded'):
                    delattr(self, '_last_downloaded')
                if hasattr(self, '_last_time'):
                    delattr(self, '_last_time')
                
                # 恢复下载按钮
                self.download_button.setText("Download Update")
                self.download_button.clicked.disconnect()
                self.download_button.clicked.connect(self.download_update)
                self.download_button.setEnabled(True)
                self.download_button.setVisible(True)
                
                self.update_button.setEnabled(True)
    
    def show_cancelled_state(self):
        """显示取消下载的状态，恢复到初始形态"""
        self.update_status_label.setText("Ready to check for updates.")
        
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        self.download_progress_bar.setVisible(False)
        
        # 隐藏数字进度标签
        if hasattr(self, 'progress_label'):
            self.progress_label.setVisible(False)
        
        # 隐藏发布内容浏览器
        self.release_content_browser.setVisible(False)
        
        # 清理下载计时器变量
        if hasattr(self, '_download_start_time'):
            delattr(self, '_download_start_time')
        if hasattr(self, '_last_downloaded'):
            delattr(self, '_last_downloaded')
        if hasattr(self, '_last_time'):
            delattr(self, '_last_time')
        
        # Clean up downloader and thread
        if hasattr(self, 'download_thread') and self.download_thread:
            if self.download_thread.downloader:
                self.download_thread.downloader.cleanup()
            
            # 确保线程完全停止后再设置为None
            if self.download_thread.isRunning():
                self.download_thread.quit()
                self.download_thread.wait(2000)  # 最多等待2秒
            
            self.download_thread = None
        
        # 隐藏下载按钮，显示检查更新按钮
        self.download_button.setVisible(False)
        self.download_button.setEnabled(False)
        
        # 启用检查更新按钮
        self.update_button.setEnabled(True)
    
    def apply_update(self):
        """应用更新"""
        if hasattr(self, 'update_result'):
            # 新的下载流程已经自动应用了更新，所以这里只需要显示成功消息
            if self.update_result.get("status") == "success":
                # 更新状态显示
                self.update_status_label.setText("✅ Update applied successfully! Please restart the application.")
                
                # 显示重启按钮
                self.restart_button.setVisible(True)
                self.restart_button.setEnabled(True)
                
                # 停止进度条
                self.progress_bar.pause()
                self.progress_bar.setVisible(False)
            else:
                # 处理错误情况
                error_message = self.update_result.get("message", "Unknown error")
                self.update_status_label.setText(f"❌ Update failed: {error_message}")
                
                # 停止进度条
                self.progress_bar.pause()
                self.progress_bar.setVisible(False)
        else:
            print("❌ update_result属性不存在")
            self.update_status_label.setText("❌ Update information lost, please restart manually")
            

     
    def __del__(self):
        """析构函数，确保所有线程都被正确清理"""
        try:
            # 清理下载线程
            if hasattr(self, 'download_thread') and self.download_thread is not None:
                if self.download_thread.isRunning():
                    self.download_thread.quit()
                    if not self.download_thread.wait(1000):
                        self.download_thread.terminate()
                        self.download_thread.wait(500)
                
                # 清理下载器
                if hasattr(self.download_thread, 'downloader') and self.download_thread.downloader:
                    self.download_thread.downloader.cleanup()
                
                self.download_thread = None
            
            # 清理检查更新线程
            if hasattr(self, 'check_thread') and self.check_thread is not None:
                if self.check_thread.isRunning():
                    self.check_thread.quit()
                    if not self.check_thread.wait(1000):
                        self.check_thread.terminate()
                        self.check_thread.wait(500)
                
                self.check_thread = None
        except:
            # 在析构函数中忽略所有异常
            pass
    
    def closeEvent(self, event):
        """重写窗口关闭事件，下载时阻止关闭"""
        # 检查是否有下载正在进行
        if hasattr(self, 'download_thread') and self.download_thread is not None and self.download_thread.isRunning():
            # 下载正在进行，显示提示并阻止关闭
            reply = QMessageBox.question(
                self, 
                "下载进行中", 
                "正在下载更新，确定要关闭窗口吗？\n关闭窗口将取消下载。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 用户确认关闭，先取消下载
                self.cancel_download()
                
                # 等待更长时间确保线程完全停止
                max_wait_time = 5000  # 最多等待5秒
                wait_step = 500  # 每次等待500ms
                total_waited = 0
                
                while self.download_thread and self.download_thread.isRunning() and total_waited < max_wait_time:
                    QApplication.processEvents()  # 处理待处理的事件
                    self.download_thread.wait(wait_step)  # 等待一小段时间
                    total_waited += wait_step
                
                # 如果线程仍在运行，强制终止
                if self.download_thread and self.download_thread.isRunning():
                    self.download_thread.terminate()
                    self.download_thread.wait(1000)  # 再等待1秒
                    
                # 清理下载器
                if self.download_thread and self.download_thread.downloader:
                    self.download_thread.downloader.cleanup()
                
                self.download_thread = None
                
                # 允许关闭窗口
                event.accept()
            else:
                # 用户取消关闭，阻止窗口关闭
                event.ignore()
        else:
            # 没有下载在进行，检查是否有检查更新线程
            if hasattr(self, 'check_thread') and self.check_thread is not None and self.check_thread.isRunning():
                # 检查更新正在进行，取消它
                self.check_thread.quit()
                if not self.check_thread.wait(1000):  # 等待最多1秒
                    self.check_thread.terminate()
                    self.check_thread.wait(500)  # 再等待500ms
                self.check_thread = None
            
            # 允许正常关闭
            event.accept()
    
    def restart_application(self):
        """重启应用程序"""
        try:
            # 执行重启脚本
            restart_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "update", "restart.command")
            
            if os.path.exists(restart_script_path):
                # 执行重启脚本
                os.system(f"'{restart_script_path}' &")
                print(f"✅ 重启脚本已执行: {restart_script_path}")
                
                # 关闭当前应用程序
                QApplication.quit()
                
            else:
                print(f"❌ 重启脚本不存在: {restart_script_path}")
                self.update_status_label.setText("❌ Restart script not found, please restart manually")
                
        except Exception as e:
            print(f"❌ 执行重启脚本时出错: {e}")
            self.update_status_label.setText(f"❌ Restart failed: {e}")

def main():
    app = QApplication(sys.argv)
    window = UpdateDialog()
    window.resize(500, 350)  # 扩大窗口大小以容纳更多内容
    window.show()
    sys.exit(app.exec())