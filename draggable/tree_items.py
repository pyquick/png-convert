from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt


def make_tree_item(text, can_drop=True):
    """
    统一的 Item 工厂
    """
    item = QStandardItem(text)
    item.setEditable(False)

    flags = (
        Qt.ItemFlag.ItemIsEnabled |
        Qt.ItemFlag.ItemIsSelectable |
        Qt.ItemFlag.ItemIsDragEnabled
    )

    if can_drop:
        flags |= Qt.ItemFlag.ItemIsDropEnabled

    item.setFlags(flags)
    return item
