#!/usr/bin/env python3
"""
Script to optimize arc_gui.py layout and add FluentIcon
"""

import re

# Read the file
with open('/Users/ghltbm/Documents/Converter/arc_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to match create_add_tab function
add_tab_pattern = r'(    def create_add_tab\(self\):.*?)(?=\n    def |\nclass |\Z)'

# New create_add_tab implementation
new_add_tab = '''    def create_add_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        tab_sizer.setSpacing(15)
        tab_sizer.setContentsMargins(20, 20, 20, 20)
        
        # Add to Archive Tab with icon
        self.notebook.addTab(tab_panel, "Add to Archive")
        self.notebook.setTabIcon(self.notebook.count() - 1, FluentIcon.FOLDER_ADD.qicon())

        # === Existing Archive Section ===
        archive_card = CardWidget()
        archive_layout = QVBoxLayout(archive_card)
        archive_layout.setSpacing(10)
        
        # Header with icon
        archive_header = QHBoxLayout()
        archive_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        archive_icon.setFixedSize(20, 20)
        archive_header.addWidget(archive_icon)
        archive_title = StrongBodyLabel("Existing Archive File")
        archive_header.addWidget(archive_title)
        archive_header.addStretch()
        archive_layout.addLayout(archive_header)
        
        # Archive path input
        archive_input_layout = QHBoxLayout()
        self.add_zip_text = LineEdit()
        self.add_zip_text.setPlaceholderText("Select existing archive file...")
        setCustomStyleSheet(self.add_zip_text, CON.qss_line, CON.qss_line)
        archive_input_layout.addWidget(self.add_zip_text, 1)
        
        zip_button = PushButton("Browse")
        zip_button.setIcon(FluentIcon.FOLDER.qicon())
        zip_button.clicked.connect(self.browse_add_archive)
        archive_input_layout.addWidget(zip_button)
        archive_layout.addLayout(archive_input_layout)
        
        tab_sizer.addWidget(archive_card)

        # === Files to Add Section ===
        files_card = CardWidget()
        files_layout = QVBoxLayout(files_card)
        files_layout.setSpacing(10)
        
        # Header with icon
        files_header = QHBoxLayout()
        files_icon = IconWidget(FluentIcon.DOCUMENT)
        files_icon.setFixedSize(20, 20)
        files_header.addWidget(files_icon)
        files_title = StrongBodyLabel("Files to Add")
        files_header.addWidget(files_title)
        files_header.addStretch()
        files_layout.addLayout(files_header)
        
        # File list
        self.add_files_listbox = ListWidget()
        self.add_files_listbox.setMinimumHeight(150)
        files_layout.addWidget(self.add_files_listbox, 1)
        
        # Browse button
        file_button = PushButton("Browse")
        file_button.setIcon(FluentIcon.FOLDER.qicon())
        file_button.clicked.connect(self.browse_add_file)
        files_layout.addWidget(file_button)
        
        tab_sizer.addWidget(files_card, 1)

        # === Progress Section ===
        progress_card = CardWidget()
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setSpacing(8)
        
        self.add_progress_label = BodyLabel("")
        progress_layout.addWidget(self.add_progress_label)
        
        self.add_progress = ProgressBar()
        self.add_progress.setRange(0, 100)
        self.add_progress.setValue(0)
        progress_layout.addWidget(self.add_progress)
        
        tab_sizer.addWidget(progress_card)

        # === Action Buttons ===
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)
        action_layout.addStretch()
        
        self.add_cancel_button = PushButton("Cancel")
        self.add_cancel_button.setIcon(FluentIcon.CANCEL.qicon())
        self.add_cancel_button.clicked.connect(self.cancel_add_to_archive)
        self.add_cancel_button.setEnabled(False)
        action_layout.addWidget(self.add_cancel_button)
        
        self.add_button = PrimaryPushButton("Add to Archive")
        self.add_button.setIcon(FluentIcon.ADD.qicon())
        self.add_button.clicked.connect(self.start_add_to_archive)
        action_layout.addWidget(self.add_button)
        
        tab_sizer.addLayout(action_layout)
        tab_sizer.addStretch(1)

'''

# Pattern to match create_list_tab function
list_tab_pattern = r'(    def create_list_tab\(self\):.*?)(?=\n    def |\nclass |\Z)'

# New create_list_tab implementation  
new_list_tab = '''    def create_list_tab(self):
        tab_panel = QWidget()
        tab_sizer = QVBoxLayout(tab_panel)
        tab_sizer.setSpacing(15)
        tab_sizer.setContentsMargins(20, 20, 20, 20)
        
        # List Contents Tab with icon
        self.notebook.addTab(tab_panel, "List Contents")
        self.notebook.setTabIcon(self.notebook.count() - 1, FluentIcon.LIST.qicon())

        # === Archive File Section ===
        archive_card = CardWidget()
        archive_layout = QVBoxLayout(archive_card)
        archive_layout.setSpacing(10)
        
        # Header with icon
        archive_header = QHBoxLayout()
        archive_icon = IconWidget(FluentIcon.ZIP_FOLDER)
        archive_icon.setFixedSize(20, 20)
        archive_header.addWidget(archive_icon)
        archive_title = StrongBodyLabel("Archive File")
        archive_header.addWidget(archive_title)
        archive_header.addStretch()
        archive_layout.addLayout(archive_header)
        
        # Archive path input
        archive_input_layout = QHBoxLayout()
        self.list_zip_text = LineEdit()
        self.list_zip_text.setPlaceholderText("Select archive file to list contents...")
        setCustomStyleSheet(self.list_zip_text, CON.qss_line, CON.qss_line)
        archive_input_layout.addWidget(self.list_zip_text, 1)
        
        zip_button = PushButton("Browse")
        zip_button.setIcon(FluentIcon.FOLDER.qicon())
        zip_button.clicked.connect(self.browse_list_archive)
        archive_input_layout.addWidget(zip_button)
        archive_layout.addLayout(archive_input_layout)
        
        tab_sizer.addWidget(archive_card)
        
        # === Password Status Section ===
        status_card = CardWidget()
        status_layout = QHBoxLayout(status_card)
        status_layout.setSpacing(10)
        
        status_icon = IconWidget(FluentIcon.INFO)
        status_icon.setFixedSize(18, 18)
        status_layout.addWidget(status_icon)
        
        self.password_status_label = BodyLabel("Archive Status: Unknown")
        status_layout.addWidget(self.password_status_label)
        
        self.password_status_icon = QLabel()
        self.password_status_icon.setFixedSize(16, 16)
        status_layout.addWidget(self.password_status_icon)
        status_layout.addStretch()
        
        tab_sizer.addWidget(status_card)
        
        # === Archive Contents Section ===
        contents_card = CardWidget()
        contents_layout = QVBoxLayout(contents_card)
        contents_layout.setSpacing(10)
        
        # Header with icon
        contents_header = QHBoxLayout()
        contents_icon = IconWidget(FluentIcon.LIST)
        contents_icon.setFixedSize(20, 20)
        contents_header.addWidget(contents_icon)
        contents_title = StrongBodyLabel("Archive Contents")
        contents_header.addWidget(contents_title)
        contents_header.addStretch()
        contents_layout.addLayout(contents_header)
        
        # Contents list
        self.contents_listbox = ListWidget()
        self.contents_listbox.setMinimumHeight(250)
        self.contents_listbox.setDragEnabled(True)
        self.contents_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        contents_layout.addWidget(self.contents_listbox, 1)
        
        tab_sizer.addWidget(contents_card, 2)

        # === Action Buttons ===
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)
        action_layout.addStretch()
        
        self.list_cancel_button = PushButton("Cancel")
        self.list_cancel_button.setIcon(FluentIcon.CANCEL.qicon())
        self.list_cancel_button.clicked.connect(self.cancel_list_archive_contents)
        self.list_cancel_button.setEnabled(False)
        action_layout.addWidget(self.list_cancel_button)
        
        self.list_button = PrimaryPushButton("List Contents")
        self.list_button.setIcon(FluentIcon.LIST.qicon())
        self.list_button.clicked.connect(self.start_list_archive_contents)
        action_layout.addWidget(self.list_button)
        
        tab_sizer.addLayout(action_layout)
        tab_sizer.addStretch(1)

'''

# Replace the functions
content = re.sub(add_tab_pattern, new_add_tab, content, flags=re.DOTALL)
content = re.sub(list_tab_pattern, new_list_tab, content, flags=re.DOTALL)

# Write the file
with open('/Users/ghltbm/Documents/Converter/arc_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("arc_gui.py optimization completed!")
