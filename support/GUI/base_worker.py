#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Worker Classes for GUI Applications

This module provides base worker classes that can be used by both
image converter and archive manager applications.
"""

from PySide6.QtCore import QObject, Signal


class BaseWorker(QObject):
    """Base worker class with common signals and methods"""
    finished = Signal()
    progress_updated = Signal(str, int)  # message, percentage
    conversion_error = Signal(str)
    canceled = Signal()

    def __init__(self):
        super().__init__()
        self.is_stopped = False

    def stop(self):
        """Stop the worker process"""
        self.is_stopped = True
        self.progress_updated.emit("Canceling...", 0)

    def _check_canceled(self):
        """Check if the worker has been canceled"""
        if self.is_stopped:
            raise RuntimeError("Operation canceled by user")

    def _handle_exception(self, e):
        """Handle exceptions and emit appropriate signals"""
        if self.is_stopped:
            self.canceled.emit()
        else:
            error_msg = f"Error: {str(e)}"
            self.conversion_error.emit(error_msg)


class BatchWorker(BaseWorker):
    """Base worker class for batch operations"""
    file_processed = Signal(str, str, str, bool, str)  # filename, input_path, output_path, success, error_message
    total_progress_updated = Signal(int)  # overall progress percentage

    def __init__(self):
        super().__init__()
        self.is_cancelled = False

    def cancel(self):
        """Cancel the batch operation"""
        self.is_cancelled = True
        self.is_stopped = True

    def _check_canceled(self):
        """Check if the batch operation has been canceled"""
        if self.is_cancelled or self.is_stopped:
            raise Exception("Batch operation was cancelled")
