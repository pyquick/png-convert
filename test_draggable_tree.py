# coding:utf-8
"""
Unit tests for DraggableTreeView
Coverage target: >= 80%
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QModelIndex, QPoint, QRect, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication

from draggable_tree_view import DraggableTreeView, DragPosition, DragState


def create_mock_model():
    """Create a properly mocked model that can be set on TreeView"""
    model = MagicMock()
    model.data_store = {}
    model.rows = {}
    
    def mock_data(index, role):
        if not index.isValid():
            return None
        return f"item_{index.row()}"
    
    def mock_rowCount(parent=QModelIndex()):
        return 3
    
    def mock_columnCount(parent=QModelIndex()):
        return 4
    
    def mock_index(row, column, parent=QModelIndex()):
        mock_idx = Mock()
        mock_idx.isValid.return_value = True
        mock_idx.row.return_value = row
        mock_idx.column.return_value = column
        mock_idx.parent.return_value = parent
        return mock_idx
    
    def mock_parent(index):
        return QModelIndex()
    
    def mock_flags(index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled
    
    model.data = mock_data
    model.rowCount = mock_rowCount
    model.columnCount = mock_columnCount
    model.index = mock_index
    model.parent = mock_parent
    model.flags = mock_flags
    model.removeRow = Mock(return_value=True)
    model.insertRow = Mock(return_value=True)
    model.moveRow = Mock(return_value=True)
    model.mimeData = Mock(return_value=QMimeData())
    model.dropMimeData = Mock(return_value=True)
    
    return model


class TestDragPosition(unittest.TestCase):
    """Test DragPosition class"""
    
    def test_values(self):
        """Test that position values exist"""
        self.assertEqual(DragPosition.BEFORE, 0)
        self.assertEqual(DragPosition.AFTER, 1)
        self.assertEqual(DragPosition.ON, 2)


class TestDragState(unittest.TestCase):
    """Test DragState class"""
    
    def test_values(self):
        """Test that state values exist"""
        self.assertEqual(DragState.IDLE, "idle")
        self.assertEqual(DragState.DRAGGING, "dragging")
        self.assertEqual(DragState.VALID_DROP, "valid_drop")
        self.assertEqual(DragState.INVALID_DROP, "invalid_drop")


class TestDraggableTreeView(unittest.TestCase):
    """Test DraggableTreeView"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize QApplication"""
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()
            
    def setUp(self):
        self.tree_view = DraggableTreeView()
        self.model = create_mock_model()
        self.tree_view.setModel(self.model)
        
    def test_initial_state(self):
        """Test initial state of tree view"""
        self.assertEqual(self.tree_view._drag_state, DragState.IDLE)
        self.assertEqual(self.tree_view._dragged_indexes, [])
        self.assertIsNone(self.tree_view._drop_target)
        
    def test_drag_enabled(self):
        """Test that drag is enabled"""
        self.assertTrue(self.tree_view.dragEnabled())
        
    def test_drop_enabled(self):
        """Test that drop is enabled"""
        self.assertTrue(self.tree_view.acceptDrops())
        
    def test_multi_selection_enabled(self):
        """Test that multi-selection is enabled"""
        self.assertEqual(
            self.tree_view.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        
    def test_set_drag_enabled(self):
        """Test enabling/disabling drag"""
        self.tree_view.set_drag_enabled(False)
        self.assertFalse(self.tree_view.dragEnabled())
        
        self.tree_view.set_drag_enabled(True)
        self.assertTrue(self.tree_view.dragEnabled())
        
    def test_set_accept_drops_enabled(self):
        """Test enabling/disabling drops"""
        self.tree_view.set_accept_drops_enabled(False)
        self.assertFalse(self.tree_view.acceptDrops())
        
        self.tree_view.set_accept_drops_enabled(True)
        self.assertTrue(self.tree_view.acceptDrops())
        
    def test_is_ancestor_with_invalid_indices(self):
        """Test _is_ancestor with invalid indices"""
        result = self.tree_view._is_ancestor(QModelIndex(), QModelIndex())
        self.assertFalse(result)
