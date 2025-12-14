#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task manager module for Converter application
Handles task queue, concurrency, and progress tracking
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
import time
from PySide6.QtCore import QObject, Signal, QThread
import threading


class TaskStatus:
    """Enum for task status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task:
    """Task class to represent a conversion task"""
    
    def __init__(self, task_type, input_path, output_path, **kwargs):
        self.task_id = str(uuid.uuid4())
        self.task_type = task_type  # "image" or "arc"
        self.input_path = input_path
        self.output_path = output_path
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
        self.metadata = kwargs
        
    def __str__(self):
        return f"Task {self.task_id}: {self.task_type} - {self.status} ({self.progress}%)"


class TaskManager(QObject):
    """Task manager to handle task queue and concurrency"""
    
    # Signals for progress and status updates
    task_added = Signal(str, dict)  # task_id, task_info
    task_updated = Signal(str, dict)  # task_id, task_info
    task_completed = Signal(str, dict)  # task_id, task_info
    task_failed = Signal(str, dict, str)  # task_id, task_info, error
    progress_updated = Signal(str, int)  # task_id, progress
    
    def __init__(self, max_workers=4):
        super().__init__()
        self.tasks = {}
        self.task_queue = []
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}
        self.is_running = False
        self.lock = threading.Lock()
        
    def add_task(self, task_type, input_path, output_path, **kwargs):
        """Add a new task to the queue"""
        task = Task(task_type, input_path, output_path, **kwargs)
        
        with self.lock:
            self.tasks[task.task_id] = task
            self.task_queue.append(task)
        
        # Emit signal
        self.task_added.emit(task.task_id, self._get_task_info(task))
        
        # Start processing if not already running
        if not self.is_running:
            self._start_processing()
        
        return task.task_id
    
    def _start_processing(self):
        """Start processing tasks from the queue"""
        if self.is_running:
            return
        
        self.is_running = True
        
        def process_queue():
            while True:
                with self.lock:
                    if not self.task_queue:
                        self.is_running = False
                        break
                    
                    # Get next task
                    task = self.task_queue.pop(0)
                    task.status = TaskStatus.RUNNING
                    task.start_time = time.time()
                
                # Emit task updated signal
                self.task_updated.emit(task.task_id, self._get_task_info(task))
                
                # Submit task to executor
                future = self.executor.submit(self._execute_task, task)
                self.futures[future] = task.task_id
                
                # Handle task completion
                future.add_done_callback(self._handle_task_completion)
        
        # Start processing in a separate thread to avoid blocking the main thread
        threading.Thread(target=process_queue, daemon=True).start()
    
    def _execute_task(self, task):
        """Execute a task"""
        try:
            # Simulate task execution with progress updates
            # In real implementation, this would call the actual conversion function
            for i in range(101):
                time.sleep(0.1)  # Simulate work
                task.progress = i
                self.progress_updated.emit(task.task_id, i)
            
            task.status = TaskStatus.COMPLETED
            task.end_time = time.time()
            task.result = "Success"
            
            return task
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
            task.error = str(e)
            raise
    
    def _handle_task_completion(self, future):
        """Handle task completion"""
        task_id = self.futures.pop(future)
        
        try:
            task = future.result()
            task_info = self._get_task_info(task)
            
            if task.status == TaskStatus.COMPLETED:
                self.task_completed.emit(task_id, task_info)
            else:
                self.task_failed.emit(task_id, task_info, task.error)
        
        except Exception as e:
            with self.lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.end_time = time.time()
                    task.error = str(e)
            
            if task:
                task_info = self._get_task_info(task)
                self.task_failed.emit(task_id, task_info, str(e))
        
        # Emit task updated signal
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                self.task_updated.emit(task_id, self._get_task_info(task))
    
    def _get_task_info(self, task):
        """Get task information as a dictionary"""
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "input_path": task.input_path,
            "output_path": task.output_path,
            "status": task.status,
            "progress": task.progress,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "result": task.result,
            "error": task.error,
            "metadata": task.metadata
        }
    
    def get_task(self, task_id):
        """Get a task by its ID"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self):
        """Get all tasks"""
        with self.lock:
            return list(self.tasks.values())
    
    def get_active_tasks(self):
        """Get all active tasks"""
        with self.lock:
            return [task for task in self.tasks.values() 
                    if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]
    
    def get_completed_tasks(self):
        """Get all completed tasks"""
        with self.lock:
            return [task for task in self.tasks.values() 
                    if task.status == TaskStatus.COMPLETED]
    
    def cancel_task(self, task_id):
        """Cancel a task"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    task.status = TaskStatus.CANCELLED
                    # Remove from queue if pending
                    if task in self.task_queue:
                        self.task_queue.remove(task)
                    return True
        return False
    
    def clear_completed_tasks(self):
        """Clear all completed tasks"""
        with self.lock:
            completed_ids = [task.task_id for task in self.tasks.values() 
                           if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]]
            for task_id in completed_ids:
                del self.tasks[task_id]
    
    def shutdown(self):
        """Shutdown the task manager"""
        self.executor.shutdown(wait=True)
