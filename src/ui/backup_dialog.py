"""
ui/backup_dialog.py — Export/Import Backup Window.
"""

import json
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QLabel,
)
from database import export_data, import_data

class BackupDialog(QDialog):
    """Simple dialog for exporting and importing database state."""
    
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Data Backup & Restore")
        self.setFixedSize(320, 220)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #E0E0E0; font-family: "Segoe UI", sans-serif; }
            QLabel { color: #888888; font-size: 13px; margin-bottom: 5px; }
            QPushButton {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2C2C2C; border: 1px solid #BB86FC; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        info = QLabel("Export your database to JSON or import from a previous backup.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        export_btn = QPushButton("📤 Export Data to JSON")
        export_btn.clicked.connect(self._export)
        layout.addWidget(export_btn)
        
        import_btn = QPushButton("📥 Import Data from JSON")
        import_btn.clicked.connect(self._import)
        layout.addWidget(import_btn)

    def _export(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Backup", "todo_backup.json", "JSON Files (*.json)"
        )
        if file_path:
            try:
                data = export_data(self.conn)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                QMessageBox.information(self, "Export Success", f"Data exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error exporting data: {e}")

    def _import(self):
        confirm = QMessageBox.question(
            self, "Confirm Import",
            "This will DELETE all current tasks, history, AND templates and replace them with the backup data. This cannot be undone.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Backup", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validation
                if not isinstance(data, dict):
                    raise ValueError("Invalid JSON: Root must be an object.")
                
                required_keys = ["tasks", "days", "templates", "template_tasks"]
                missing = [k for k in required_keys if k not in data]
                if missing:
                    raise ValueError(f"Invalid backup format. Missing: {', '.join(missing)}")
                    
                import_data(self.conn, data)
                QMessageBox.information(self, "Import Success", "Data and Templates have been restored successfully.")
                self.accept()
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Import Failed", "The selected file is not a valid JSON file.")
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Error importing data: {e}")
