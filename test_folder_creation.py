#!/usr/bin/env python3
"""Test script for folder creation feature in Add to Archive"""

import sys
import os
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from arc_gui import ZipGUI, ArchiveTreeModel, CreateFolderMessageBox


class TestRunner:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.passed = 0
        self.failed = 0

    def test_column_widths(self):
        """Test that column widths are properly set"""
        print("=" * 60)
        print("Test 1: Column Widths")
        print("=" * 60)

        window = ZipGUI()

        # Check column widths
        widths = []
        for i in range(4):
            widths.append(window.add_unified_tree.columnWidth(i))

        print(f"Column widths: {widths}")

        # Verify name column is wide enough (should be 500)
        assert widths[0] >= 500, f"Name column width {widths[0]} is too small, expected >= 500"
        print("✓ Name column width is correct (>= 500)")

        window.close()
        window.deleteLater()
        print("Test 1 PASSED\n")

    def test_pending_files_structure(self):
        """Test that pending files with target paths create proper folder structure"""
        print("=" * 60)
        print("Test 2: Pending Files Folder Structure")
        print("=" * 60)

        # Create a temporary model
        model = ArchiveTreeModel()

        # Create test files
        test_files = [
            {'path': '/tmp/test_file1.txt', 'target': 'newfolder/test_file1.txt'},
            {'path': '/tmp/test_file2.txt', 'target': 'newfolder/test_file2.txt'},
        ]

        # Create actual test files
        for f in test_files:
            with open(f['path'], 'w') as fp:
                fp.write("test content")

        try:
            # Add pending items
            model.add_pending_items(test_files)

            # Check the structure
            root = model.invisibleRootItem()
            print(f"Root has {root.rowCount()} children")

            # Should have 1 folder node
            assert root.rowCount() == 1, f"Expected 1 child (folder), got {root.rowCount()}"

            folder_item = root.child(0, 0)
            print(f"Folder name: {folder_item.text()}")
            assert folder_item.text() == "newfolder", f"Expected folder name 'newfolder', got '{folder_item.text()}'"

            # Check folder has 2 files
            assert folder_item.rowCount() == 2, f"Expected 2 files in folder, got {folder_item.rowCount()}"

            file1 = folder_item.child(0, 0)
            file2 = folder_item.child(1, 0)
            print(f"Files in folder: {file1.text()}, {file2.text()}")

            print("✓ Folder structure is correct")
            print("Test 2 PASSED\n")

        finally:
            # Cleanup
            for f in test_files:
                if os.path.exists(f['path']):
                    os.remove(f['path'])

    def test_update_pending_files_for_folder(self):
        """Test _update_pending_files_for_folder method"""
        print("=" * 60)
        print("Test 3: Update Pending Files For Folder")
        print("=" * 60)

        window = ZipGUI()

        # Setup test data
        window._pending_files = [
            {'path': '/tmp/fileA.txt', 'target': ''},
            {'path': '/tmp/fileB.txt', 'target': ''},
        ]

        # Create test files
        for f in window._pending_files:
            with open(f['path'], 'w') as fp:
                fp.write("test content")

        try:
            # Call the update method
            window._update_pending_files_for_folder('fileA.txt', 'fileB.txt', 'newfolder')

            # Check that targets were updated
            assert window._pending_files[0]['target'] == 'newfolder/fileA.txt', \
                f"Expected 'newfolder/fileA.txt', got '{window._pending_files[0]['target']}'"
            assert window._pending_files[1]['target'] == 'newfolder/fileB.txt', \
                f"Expected 'newfolder/fileB.txt', got '{window._pending_files[1]['target']}'"

            print("✓ Pending files targets updated correctly")
            print("Test 3 PASSED\n")

        finally:
            # Cleanup
            for f in window._pending_files:
                if os.path.exists(f['path']):
                    os.remove(f['path'])
            window.close()
            window.deleteLater()

    def test_create_folder_and_move_files(self):
        """Test _create_folder_and_move_files method without full refresh"""
        print("=" * 60)
        print("Test 4: Create Folder And Move Files (No Full Refresh)")
        print("=" * 60)

        window = ZipGUI()

        # Create test files
        test_files = [
            {'path': '/tmp/fileA.txt', 'target': ''},
            {'path': '/tmp/fileB.txt', 'target': ''},
        ]

        for f in test_files:
            with open(f['path'], 'w') as fp:
                fp.write("test content")

        try:
            # Add files to pending list
            window._pending_files = test_files
            window._refresh_unified_tree()

            # Check initial state - should have 2 files at root
            root = window.add_unified_tree_model.invisibleRootItem()
            initial_count = root.rowCount()
            print(f"Initial root children: {initial_count}")

            # Create folder and move files
            window._create_folder_and_move_files('fileA.txt', 'fileB.txt', 'newfolder')

            # Check final state - should have 1 folder at root
            final_count = root.rowCount()
            print(f"Final root children: {final_count}")

            assert final_count == 1, f"Expected 1 folder at root, got {final_count}"

            folder_item = root.child(0, 0)
            print(f"Folder name: {folder_item.text()}")
            assert folder_item.text() == 'newfolder', f"Expected folder name 'newfolder', got '{folder_item.text()}'"

            # Check folder has 2 files
            assert folder_item.rowCount() == 2, f"Expected 2 files in folder, got {folder_item.rowCount()}"

            file1 = folder_item.child(0, 0)
            file2 = folder_item.child(1, 0)
            print(f"Files in folder: {file1.text()}, {file2.text()}")

            # Check file paths are updated
            path1 = file1.data(Qt.ItemDataRole.UserRole + 1)
            path2 = file2.data(Qt.ItemDataRole.UserRole + 1)
            print(f"File paths: {path1}, {path2}")

            assert 'newfolder' in path1, f"Expected path to contain 'newfolder', got '{path1}'"
            assert 'newfolder' in path2, f"Expected path to contain 'newfolder', got '{path2}'"

            print("✓ Folder created and files moved without full refresh")
            print("Test 4 PASSED\n")

        finally:
            for f in test_files:
                if os.path.exists(f['path']):
                    os.remove(f['path'])
            window.close()
            window.deleteLater()

    def test_refresh_unified_tree(self):
        """Test that _refresh_unified_tree properly clears and rebuilds the model"""
        print("=" * 60)
        print("Test 5: Refresh Unified Tree")
        print("=" * 60)

        window = ZipGUI()

        # Create test files
        test_files = [
            {'path': '/tmp/test_refresh1.txt', 'target': 'folder1/file1.txt'},
            {'path': '/tmp/test_refresh2.txt', 'target': 'folder1/file2.txt'},
        ]

        for f in test_files:
            with open(f['path'], 'w') as fp:
                fp.write("test content")

        try:
            window._pending_files = test_files

            # Call refresh
            window._refresh_unified_tree()

            # Check model is not empty
            root = window.add_unified_tree_model.invisibleRootItem()
            print(f"Root has {root.rowCount()} children after refresh")

            # Should have at least the folder
            assert root.rowCount() >= 1, f"Model should have children after refresh"

            print("✓ Refresh unified tree works correctly")
            print("Test 5 PASSED\n")

        finally:
            for f in test_files:
                if os.path.exists(f['path']):
                    os.remove(f['path'])
            window.close()
            window.deleteLater()

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "=" * 60)
        print("RUNNING ALL TESTS FOR FOLDER CREATION FEATURE")
        print("=" * 60 + "\n")

        tests = [
            self.test_column_widths,
            self.test_pending_files_structure,
            self.test_update_pending_files_for_folder,
            self.test_create_folder_and_move_files,
            self.test_refresh_unified_tree,
        ]

        for test in tests:
            try:
                test()
                self.passed += 1
            except Exception as e:
                import traceback
                print(f"✗ {test.__name__} FAILED: {e}")
                traceback.print_exc()
                print()
                self.failed += 1

        print("=" * 60)
        print(f"TEST RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 60)

        return self.failed == 0


if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
