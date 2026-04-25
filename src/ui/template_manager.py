"""
ui/template_manager.py — Template Management Window.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_templates,
    add_template,
    delete_template,
    rename_template,
    get_template_tasks,
    add_template_task,
    delete_template_task,
    rename_template_task,
)

class TemplateManagerWindow(QDialog):
    """Split-pane dialog to manage template collections and their tasks."""
    
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Manage Template Collections")
        self.setMinimumSize(700, 500)
        
        # We reuse the dark theme from the main window 
        # (Usually better to put it in a separate theme.py, but we'll stick to a simple consistent QSS here)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #E0E0E0; font-family: "Segoe UI", sans-serif; }
            QLabel { color: #FFFFFF; font-weight: bold; }
            QListWidget {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 5px;
                color: #E0E0E0;
            }
            QListWidget::item {
                background-color: #2C2C2C;
                border-radius: 6px;
                padding: 10px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #3A3A3A;
                border: 1px solid #BB86FC;
            }
            QPushButton {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QPushButton:hover { background-color: #2C2C2C; border: 1px solid #BB86FC; }
        """)
        
        self._build_ui()
        self._refresh_templates()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Left Column: Templates
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("Templates"))
        self.template_list = QListWidget()
        self.template_list.itemSelectionChanged.connect(self._on_template_selected)
        self.template_list.itemDoubleClicked.connect(self._rename_template)
        left_layout.addWidget(self.template_list)
        
        left_btns = QHBoxLayout()
        self.add_template_btn = QPushButton("Add Template")
        self.add_template_btn.clicked.connect(self._add_template)
        left_btns.addWidget(self.add_template_btn)
        
        self.del_template_btn = QPushButton("Delete")
        self.del_template_btn.clicked.connect(self._delete_template)
        left_btns.addWidget(self.del_template_btn)

        self.rename_template_btn = QPushButton("Rename")
        self.rename_template_btn.clicked.connect(self._rename_template)
        left_btns.addWidget(self.rename_template_btn)
        left_layout.addLayout(left_btns)
        
        main_layout.addWidget(left_panel, stretch=1)

        # Right Column: Tasks
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tasks_label = QLabel("Tasks in Collection")
        right_layout.addWidget(self.tasks_label)
        
        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(self._rename_task)
        right_layout.addWidget(self.task_list)
        
        right_btns = QHBoxLayout()
        self.add_task_btn = QPushButton("Add Task")
        self.add_task_btn.clicked.connect(self._add_task)
        self.add_task_btn.setEnabled(False)
        right_btns.addWidget(self.add_task_btn)
        
        self.del_task_btn = QPushButton("Delete")
        self.del_task_btn.clicked.connect(self._delete_task)
        self.del_task_btn.setEnabled(False)
        right_btns.addWidget(self.del_task_btn)

        self.rename_task_btn = QPushButton("Rename")
        self.rename_task_btn.clicked.connect(self._rename_task)
        self.rename_task_btn.setEnabled(False)
        right_btns.addWidget(self.rename_task_btn)
        right_layout.addLayout(right_btns)
        
        main_layout.addWidget(right_panel, stretch=2)

    def _refresh_templates(self):
        self.template_list.clear()
        self.task_list.clear()
        self.add_task_btn.setEnabled(False)
        self.del_task_btn.setEnabled(False)
        self.rename_task_btn.setEnabled(False)
        
        for t in get_templates(self.conn):
            item = QListWidgetItem(t["name"])
            item.setData(Qt.ItemDataRole.UserRole, t["id"])
            self.template_list.addItem(item)

    def _on_template_selected(self):
        items = self.template_list.selectedItems()
        if not items:
            self.task_list.clear()
            self.add_task_btn.setEnabled(False)
            self.del_task_btn.setEnabled(False)
            self.rename_task_btn.setEnabled(False)
            return
        
        tid = items[0].data(Qt.ItemDataRole.UserRole)
        self.tasks_label.setText(f"Tasks in: {items[0].text()}")
        self.add_task_btn.setEnabled(True)
        self.del_task_btn.setEnabled(True)
        self.rename_task_btn.setEnabled(True)
        self._refresh_tasks(tid)

    def _refresh_tasks(self, template_id):
        self.task_list.clear()
        for task in get_template_tasks(self.conn, template_id):
            # Display title is enough as it's already formatted
            item = QListWidgetItem(task["title"])
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            
            # Apply some basic coloring if possible (optional but nice)
            t_type = task.get("task_type", "regular")
            if t_type != "regular":
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                
            self.task_list.addItem(item)

    def _add_template(self):
        name, ok = QInputDialog.getText(self, "New Template", "Template Name:")
        if ok and name.strip():
            add_template(self.conn, name.strip())
            self._refresh_templates()

    def _delete_template(self):
        item = self.template_list.currentItem()
        if item:
            tid = item.data(Qt.ItemDataRole.UserRole)
            delete_template(self.conn, tid)
            self._refresh_templates()

    def _rename_template(self, item=None):
        current_item = item or self.template_list.currentItem()
        if not current_item:
            return
        tid = current_item.data(Qt.ItemDataRole.UserRole)
        current_name = current_item.text()
        new_name, ok = QInputDialog.getText(self, "Rename Template", "Template Name:", text=current_name)
        if ok and new_name.strip():
            rename_template(self.conn, tid, new_name.strip())
            self._refresh_templates()

    def _add_task(self):
        item = self.template_list.currentItem()
        if not item: return
        tid = item.data(Qt.ItemDataRole.UserRole)
        
        types = ["Regular Task", "DPP", "Test"]
        t_type_label, ok = QInputDialog.getItem(self, "Add Task to Template", "Select Type:", types, 0, False)
        if not ok: return

        if t_type_label == "Regular Task":
            title, ok = QInputDialog.getText(self, "Regular Task", "Task Title:")
            if ok and title.strip():
                add_template_task(self.conn, tid, title.strip(), task_type="regular")
        
        elif t_type_label == "DPP":
            subjects = ["Physics", "Chemistry", "Mathematics"]
            subj, ok = QInputDialog.getItem(self, "Add DPP", "Select Subject:", subjects, 0, False)
            if ok and subj:
                add_template_task(self.conn, tid, f"{subj} DPP", task_type="dpp", subject=subj)
        
        elif t_type_label == "Test":
            # Categories from main window logic
            categories = ["JEE Main", "JEE Advanced", "Short Test", "Full Test", "Regular Test"]
            cat, ok = QInputDialog.getItem(self, "Add Test", "Select Category:", categories, 0, False)
            if ok and cat:
                title = cat
                if cat == "Regular Test":
                    custom_title, ok2 = QInputDialog.getText(self, "Test Title", "Enter Test Name:")
                    if ok2 and custom_title:
                        title = custom_title
                    else: return
                add_template_task(self.conn, tid, title, task_type="test", test_category=cat)
        
        self._refresh_tasks(tid)

    def _delete_task(self):
        item = self.task_list.currentItem()
        if item:
            task_id = item.data(Qt.ItemDataRole.UserRole)
            tid = self.template_list.currentItem().data(Qt.ItemDataRole.UserRole)
            delete_template_task(self.conn, task_id)
            self._refresh_tasks(tid)

    def _rename_task(self, item=None):
        current_item = item or self.task_list.currentItem()
        template_item = self.template_list.currentItem()
        if not current_item or not template_item:
            return
        task_id = current_item.data(Qt.ItemDataRole.UserRole)
        tid = template_item.data(Qt.ItemDataRole.UserRole)
        current_title = current_item.text()
        new_title, ok = QInputDialog.getText(self, "Rename Task", "Task Title:", text=current_title)
        if ok and new_title.strip():
            rename_template_task(self.conn, task_id, new_title.strip())
            self._refresh_tasks(tid)
