"""
ui/main_window.py — Main application window.

Database is accessed only through functions in database.py.
"""

import datetime

from PyQt6.QtCore import Qt, QTimer, QSize

from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog,
    QFrame,
    QFormLayout,
    QSpinBox,
    QDialogButtonBox,
    QSizePolicy,
    QStyledItemDelegate,
    QStackedWidget,
)

from ui.calendar_view import CalendarView
from ui.dashboard_view import DashboardView
from ui.template_manager import TemplateManagerWindow
from ui.backup_dialog import BackupDialog

from database import (
    get_tasks_by_date,
    add_task,
    update_task_title,
    update_task_status,
    delete_task,
    disable_task,
    enable_task,
    finalize_day,
    is_day_finalized,
    get_templates,
    get_template_tasks,
    get_active_day,
    set_active_day,
    get_app_state,
    set_app_state,
)


# ── Dark-mode stylesheet ─────────────────────────────────────────

DARK_STYLE = """
QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
}

QLineEdit {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #BB86FC;
}

QPushButton {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #2C2C2C;
    border: 1px solid #BB86FC;
}
QPushButton:pressed {
    background-color: #3A3A3A;
}

QPushButton#addBtn {
    background-color: #BB86FC;
    color: #121212;
    border: none;
}
QPushButton#addBtn:hover {
    background-color: #CE93D8;
}

QPushButton#finalizeBtn {
    background-color: #CF6679;
    color: #121212;
    border: none;
}
QPushButton#finalizeBtn:hover {
    background-color: #E57373;
}

QListWidget {
    background-color: #1E1E1E;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}
QListWidget::item {
    background-color: #333333;
    border-radius: 6px;
    padding: 12px 14px;
    margin: 6px 6px;
    color: palette(text);
}
QListWidget::item:hover {
    background-color: #2C2C2C;
}
QListWidget::item:selected {
    background-color: transparent;
    border: 1px solid #BB86FC;
}

QLabel#heading {
    font-size: 24px;
    font-weight: bold;
    color: #FFFFFF;
}
QLabel#dateLabel {
    font-size: 14px;
    color: #888888;
    margin-bottom: 8px;
}

QMenu {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #333333;
}

QLabel#lateNightBadge {
    background-color: #7B1FA2;
    color: #FFFFFF;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
    margin-left: 5px;
}
"""

# ── Task Categories & Colors ────────────────────────────────────────

TASK_TYPE_COLORS = {
    "regular": "#2F3B52",
    "dpp": "#37474F",
    "test": "#4A2F5C",
}

DPP_COLORS = {
    "Physics": "#1565C0",
    "Chemistry": "#2E7D32",
    "Mathematics": "#EF6C00",
}

TEST_COLORS = {
    "JEE Main": "#00838F",
    "JEE Advanced": "#6A1B9A",
    "Short Test": "#F9A825",
    "Full Test": "#C62828",
    "Regular Test": "#455A64",
}

try:
    from test_schedule import TEST_SCHEDULE
except ImportError:
    TEST_SCHEDULE = []

# ── State badge helpers ───────────────────────────────────────────

STATE_ICONS = {
    "target": "🎯",
    "completed": "✅",
    "incomplete": "❌",
}


def _text_color_for_background(color_hex: str) -> str:
    """Pick a readable text color for a background color."""
    color = QColor(color_hex)
    brightness = ((color.red() * 299) + (color.green() * 587) + (color.blue() * 114)) / 1000
    return "#111111" if brightness >= 160 else "#F5F7FA"


def _task_colors(task: dict) -> tuple[str, str]:
    """Return accent and foreground colors for task list items."""
    task_type = task.get("task_type", "regular")
    background = TASK_TYPE_COLORS.get(task_type, TASK_TYPE_COLORS["regular"])

    if task_type == "dpp":
        background = DPP_COLORS.get(task.get("subject"), background)
    elif task_type == "test":
        background = TEST_COLORS.get(task.get("test_category"), background)

    return background, _text_color_for_background(background)
 
 
class TaskItemDelegate(QStyledItemDelegate):
    """Delegate to draw a 4px wide accent color bar on the left of each item."""
    def paint(self, painter, option, index):
        # Draw the standard item background and text
        super().paint(painter, option, index)
        
        # Get accent color from Qt.UserRole + 1
        accent_hex = index.data(Qt.ItemDataRole.UserRole + 1)
        if accent_hex:
            painter.save()
            painter.setBrush(QColor(accent_hex))
            painter.setPen(Qt.PenStyle.NoPen)
            # Draw 4px bar on the left of the item rectangle
            rect = option.rect
            painter.drawRect(rect.left(), rect.top(), 4, rect.height())
            painter.restore()




class TestMarksDialog(QDialog):
    """Dialog to record Physics, Chemistry, and Mathematics marks for a Test."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Test Marks")
        self.setStyleSheet(DARK_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        form = QFormLayout()
        
        # Physics
        self.p_max = QSpinBox(); self.p_max.setRange(1, 500); self.p_max.setValue(100)
        self.p_obt = QSpinBox(); self.p_obt.setRange(0, self.p_max.value()); self.p_obt.setValue(0)
        self.p_max.valueChanged.connect(self.p_obt.setMaximum)
        
        # Chemistry
        self.c_max = QSpinBox(); self.c_max.setRange(1, 500); self.c_max.setValue(100)
        self.c_obt = QSpinBox(); self.c_obt.setRange(0, self.c_max.value()); self.c_obt.setValue(0)
        self.c_max.valueChanged.connect(self.c_obt.setMaximum)
        
        # Mathematics
        self.m_max = QSpinBox(); self.m_max.setRange(1, 500); self.m_max.setValue(100)
        self.m_obt = QSpinBox(); self.m_obt.setRange(0, self.m_max.value()); self.m_obt.setValue(0)
        self.m_max.valueChanged.connect(self.m_obt.setMaximum)

        form.addRow("Physics Max:", self.p_max)
        form.addRow("Physics Score:", self.p_obt)
        form.addRow(QLabel("")) # Spacer
        form.addRow("Chemistry Max:", self.c_max)
        form.addRow("Chemistry Score:", self.c_obt)
        form.addRow(QLabel("")) # Spacer
        form.addRow("Mathematics Max:", self.m_max)
        form.addRow("Mathematics Score:", self.m_obt)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_marks(self):
        return {
            "p_max": self.p_max.value(), "p_score": self.p_obt.value(),
            "c_max": self.c_max.value(), "c_score": self.c_obt.value(),
            "m_max": self.m_max.value(), "m_score": self.m_obt.value(),
        }


class MainWindow(QWidget):
    """Primary application window."""

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        # Use logical day from database
        self.today = get_active_day(self.conn)
        if not self.today:
            self.today = datetime.date.today().strftime("%d-%m-%Y")
        self._sync_finalized_active_day_early_morning()

        self.setWindowTitle("PrepTrack by ~Shaurya~")
        self.setStyleSheet(DARK_STYLE)

        self._populate_test_schedule()
        self._build_ui()
        self._refresh_tasks()
        
        # Check for unfinished days from the past
        self._check_unfinished_day_popup()
        
        # Reminder system state
        self.reminder_shown = False
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_reminder)
        self.reminder_timer.start(5 * 60 * 1000)  # 5 minutes
        
        # Initial size
        self.setMinimumWidth(615)
        self.setMinimumHeight(700)
        self.resize(615, 700)
        

    # ── UI Construction ───────────────────────────────────────────

    def _build_ui(self):
        # Main horizontal wrapper
        wrapper = QHBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)
        
        # 1. Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(72)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setStyleSheet("""
            QFrame#sidebar {
                background-color: #121212;
                border-right: 1px solid #333333;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: #888888;
                font-size: 16px;
                padding: 10px;
                margin: 10px 10px;
            }
            QPushButton:hover {
                background-color: #2C2C2C;
                color: #FFFFFF;
            }
            QPushButton[active="true"] {
                background-color: #BB86FC22;
                color: #BB86FC;
                border-left: 3px solid #BB86FC;
                border-radius: 0px 8px 8px 0px;
                margin-left: 0px;
            }
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(10)
        
        self.home_btn = QPushButton("🏠")
        self.home_btn.setToolTip("Home")
        self.home_btn.setProperty("active", "true")
        self.home_btn.setMinimumWidth(72)
        self.home_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.home_btn.clicked.connect(lambda: self._switch_page(0))
        sidebar_layout.addWidget(self.home_btn)
        
        self.dash_btn = QPushButton("📊")
        self.dash_btn.setToolTip("Dashboard")
        self.dash_btn.setMinimumWidth(72)
        self.dash_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dash_btn.clicked.connect(lambda: self._switch_page(1))
        sidebar_layout.addWidget(self.dash_btn)
        
        sidebar_layout.addStretch()
        
        wrapper.addWidget(self.sidebar, 1)
        
        # 2. Stacked Content
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        wrapper.addWidget(self.stack, 4)
        
        # PAGE 1: Home (Existing tasks + calendar)
        self.home_page = QWidget()
        self.home_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        home_layout = QHBoxLayout(self.home_page)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(0)

        self.main_pane = QWidget()
        self.main_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self.main_pane)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(14)

        # Header
        heading = QLabel("Daily Tasks")
        heading.setObjectName("heading")
        root.addWidget(heading)

        date_row = QHBoxLayout()
        date_row.setSpacing(10)
        
        self.date_label = QLabel(f"📅  {self.today}")
        self.date_label.setObjectName("dateLabel")
        date_row.addWidget(self.date_label)
        
        self.late_night_badge = QLabel("🌙 Late Night Mode")
        self.late_night_badge.setObjectName("lateNightBadge")
        self.late_night_badge.setToolTip("Activates automatically between 12AM to 4AM.")
        self.late_night_badge.hide()
        date_row.addWidget(self.late_night_badge)
        date_row.addStretch()
        root.addLayout(date_row)

        # Task list
        self.task_list = QListWidget()
        self.task_list.setItemDelegate(TaskItemDelegate(self.task_list))
        self.task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.task_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self._show_context_menu)
        self.task_list.itemDoubleClicked.connect(self._rename_task)
        root.addWidget(self.task_list, stretch=1)

        # Hint
        hint = QLabel("Double-click to rename  •  Right-click for more options")
        hint.setObjectName("dateLabel")  # reuse the muted style
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        # Bottom buttons
        btn_row = QHBoxLayout()

        # --- Row 1: History, Add Task, Finalize Day ---
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        
        self.toggle_calendar_btn = QPushButton("🗓️ History")
        self.toggle_calendar_btn.clicked.connect(self._toggle_calendar)
        row1.addWidget(self.toggle_calendar_btn, stretch=1)
        
        self.add_btn = QPushButton("Add Task")
        self.add_btn.setObjectName("addBtn")
        
        add_menu = QMenu(self)
        reg_action = add_menu.addAction("Regular Task")
        reg_action.triggered.connect(lambda: self._add_task_type("regular"))
        dpp_action = add_menu.addAction("DPP")
        dpp_action.triggered.connect(lambda: self._add_task_type("dpp"))
        test_action = add_menu.addAction("Test")
        test_action.triggered.connect(lambda: self._add_task_type("test"))
        
        self.add_btn.setMenu(add_menu)
        row1.addWidget(self.add_btn, stretch=1)
        
        self.finalize_btn = QPushButton("Finalize Day")
        self.finalize_btn.setObjectName("finalizeBtn")
        self.finalize_btn.clicked.connect(self._finalize_day)
        row1.addWidget(self.finalize_btn, stretch=1)
        
        root.addLayout(row1)

        # --- Row 2: Add from Template, Manage Templates ---
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.apply_template_btn = QPushButton("📋 Add from Template")
        self.apply_template_btn.clicked.connect(self._add_from_template)
        row2.addWidget(self.apply_template_btn, stretch=1)

        self.manage_templates_btn = QPushButton("⚙️ Manage Templates")
        self.manage_templates_btn.clicked.connect(self._manage_templates)
        row2.addWidget(self.manage_templates_btn, stretch=1)
        
        self.backup_btn = QPushButton("📂 Backup")
        self.backup_btn.clicked.connect(self._open_backup_dialog)
        row2.addWidget(self.backup_btn, stretch=1)
        
        root.addLayout(row2)

        # (Hidden) Status label for error messages
        self.status_label = QLabel()
        self.status_label.setObjectName("dateLabel")
        self.status_label.setStyleSheet("color: #CF6679; font-weight: bold; padding-left: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()
        root.addWidget(self.status_label)

        self.calendar_pane = CalendarView(self.conn)
        self.calendar_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.calendar_pane.hide()

        home_layout.addWidget(self.main_pane, stretch=1)
        home_layout.addWidget(self.calendar_pane, stretch=1)
        
        self.stack.addWidget(self.home_page)
        
        # PAGE 2: Dashboard
        self.dashboard_page = DashboardView(self.conn)
        self.stack.addWidget(self.dashboard_page)

    def _switch_page(self, index):
        """Switch between Home and Dashboard."""
        self.stack.setCurrentIndex(index)
        
        # Update button states
        self.home_btn.setProperty("active", str(index == 0).lower())
        self.dash_btn.setProperty("active", str(index == 1).lower())
        
        # Re-apply styles
        self.home_btn.style().unpolish(self.home_btn)
        self.home_btn.style().polish(self.home_btn)
        self.dash_btn.style().unpolish(self.dash_btn)
        self.dash_btn.style().polish(self.dash_btn)
        
        if index == 1:
            self.dashboard_page.refresh()

    def _populate_test_schedule(self):
        """Pre-populate tests from the user-provided schedule if they don't exist."""
        # Get all existing tasks to avoid duplicates
        cursor = self.conn.execute("SELECT title, date FROM tasks WHERE task_type IN ('test', 'dpp')")
        existing = {(row["title"], row["date"]) for row in cursor.fetchall()}

        for date_str, name, category in TEST_SCHEDULE:
            # Convert YYYY-MM-DD to DD-MM-YYYY
            try:
                y, m, d = date_str.split("-")
                formatted_date = f"{d}-{m}-{y}"
            except (ValueError, AttributeError):
                # Fallback if format is somehow wrong
                formatted_date = date_str
            
            if (name, formatted_date) not in existing:
                add_task(
                    self.conn,
                    name,
                    formatted_date,
                    task_type="test",
                    test_category=category
                )

    # ── Actions ───────────────────────────────────────────────────

    def _toggle_calendar(self):
        if self.isMaximized():
            if self.calendar_pane.isHidden():
                self.calendar_pane.show()
            else:
                self.calendar_pane.hide()
            return

        sidebar_w = 80
        if self.calendar_pane.isHidden():
            self.calendar_pane.show()
            self.resize(1075 + sidebar_w, self.height())
        else:
            self.calendar_pane.hide()
            self.resize(615 + sidebar_w, self.height())



    def _add_from_template(self):
        """Show a dialog to select a template collection."""
        if is_day_finalized(self.conn, self.today):
            return
            
        templates = get_templates(self.conn)
        if not templates:
            QMessageBox.information(self, "No Templates", "No templates found. Create one in 'Manage Templates'.")
            return
            
        menu = QMenu(self)
        for t in templates:
            action = menu.addAction(f"Collection: {t['name']}")
            action.triggered.connect(lambda checked, tid=t['id']: self._apply_template(tid))
            
        self.apply_template_btn.setMenu(menu)
        self.apply_template_btn.showMenu()

    def _apply_template(self, template_id):
        tasks = get_template_tasks(self.conn, template_id)
        for t in tasks:
            add_task(
                self.conn, 
                t["title"], 
                self.today, 
                task_type=t.get("task_type", "regular"),
                subject=t.get("subject"),
                test_category=t.get("test_category")
            )
        self._refresh_tasks()
    

    def _manage_templates(self):
        dialog = TemplateManagerWindow(self.conn, self)
        dialog.exec()
        # Refresh might be needed if something global changed, 
        # but here it's just templates vs today's tasks.

    def _open_backup_dialog(self):
        dialog = BackupDialog(self.conn, self)
        if dialog.exec():
            # If import was successful (dialog.accept() called), 
            # we should refresh the UI to show imported data.
            self._refresh_tasks()
            self.calendar_pane.populate_calendar()

    def _check_reminder(self):
        """Check if it's late and the user hasn't finalized their logical day."""
        if self._sync_finalized_active_day_early_morning():
            if hasattr(self, 'date_label'):
                self.date_label.setText(f"📅  {self.today}")
            self._refresh_tasks()
        self._update_late_night_indicator()
        now = datetime.datetime.now()
        system_date = now.strftime("%d-%m-%Y")
        
        # Reset flag if system day has changed
        if not hasattr(self, '_last_system_check_date') or system_date != self._last_system_check_date:
            self._last_system_check_date = system_date
            self.reminder_shown = False
            
        # Optimization: only check if not already shown today
        if self.reminder_shown:
            return
            
        # Condition: Time is 23:59 or later - reminder for current active day
        if now.hour == 23 and now.minute >= 59:
            # Check database for finalized status
            if not is_day_finalized(self.conn, self.today):
                self.reminder_shown = True
                QMessageBox.information(
                    self, 
                    "Finalize Your Day", 
                    "It's almost midnight! Don't forget to finalize your day to save your rating and tasks."
                )

    def _sync_finalized_active_day_early_morning(self) -> bool:
        """
        Move logical day to system day if current logical day
        is already finalized and differs from today's date.
        """
        system_date = datetime.date.today().strftime("%d-%m-%Y")
        if self.today == system_date:
            return False

        if not is_day_finalized(self.conn, self.today):
            return False

        self.today = system_date
        set_active_day(self.conn, self.today)
        return True

    def _check_unfinished_day_popup(self):
        """Check if we should show the 'unfinished day' dialog based on 4 conditions."""
        system_date = datetime.date.today().strftime("%d-%m-%Y")
        active_day = self.today
        
        # 1. active_day != system_date
        if active_day == system_date:
            return
            
        # 2. active_day is not finalized
        if is_day_finalized(self.conn, active_day):
            return
            
        # 3. current time >= 8 AM
        now = datetime.datetime.now()
        if now.hour < 8:
            return
            
        # 4. popup not shown today
        last_popup_date = get_app_state(self.conn, 'last_unfinished_popup_date')
        if last_popup_date == system_date:
            return
            
        # All conditions met. Mark as shown today and ask user.
        set_app_state(self.conn, 'last_unfinished_popup_date', system_date)
        
        res = QMessageBox.question(
            self,
            "Unfinished Day",
            f"You didn't finalize your previous day ({active_day}).\nDo you want to finalize it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if res == QMessageBox.StandardButton.Yes:
            # Calculate rating and finalize the previous day
            tasks = get_tasks_by_date(self.conn, active_day)
            enabled = [t for t in tasks if t["is_enabled"] == 1]
            if not enabled:
                rating = 0.0
            else:
                comp = sum(1 for t in enabled if t["status"] == "completed")
                rating = (comp / len(enabled)) * 100
            
            from database import finalize_day
            finalize_day(self.conn, active_day, rating)
            
            # Jump to actual system today
            self.today = system_date
            set_active_day(self.conn, self.today)
            
            if hasattr(self, 'date_label'):
                self.date_label.setText(f"📅  {self.today}")
            self._refresh_tasks()
            
            QMessageBox.information(self, "Day Finalized", f"Previous day finalized ({rating:.0f}%). Moved to today.")

    def _update_late_night_indicator(self):
        """Toggle the visibility of the Late Night Mode badge."""
        now = datetime.datetime.now()
        system_date = now.strftime("%d-%m-%Y")
        # Conditions: System date has advanced past the logical day AND it's between 12 AM and 4 AM
        is_late_night = (system_date != self.today) and (0 <= now.hour < 4)
        if hasattr(self, 'late_night_badge'):
            self.late_night_badge.setVisible(is_late_night)

    def _add_task_type(self, t_type):
        """Handle specific task type creation."""
        if t_type == "regular":
            self._add_task()
        elif t_type == "dpp":
            self._add_dpp()
        elif t_type == "test":
            self._add_test()

    def _add_dpp(self):
        """Prompt for subject and add DPP."""
        subjects = ["Physics", "Chemistry", "Mathematics"]
        subj, ok = QInputDialog.getItem(self, "Add DPP", "Select Subject:", subjects, 0, False)
        if ok and subj:
            title = f"{subj} DPP"
            add_task(self.conn, title, self.today, task_type="dpp", subject=subj)
            self._refresh_tasks()

    def _add_test(self):
        """Prompt for category and add Test."""
        categories = list(TEST_COLORS.keys())
        cat, ok = QInputDialog.getItem(self, "Add Test", "Select Test Category:", categories, 0, False)
        if ok and cat:
            title = cat
            if cat == "Regular Test":
                custom_title, ok2 = QInputDialog.getText(self, "Test Title", "Enter Test Name:")
                if ok2 and custom_title:
                    title = custom_title
                else:
                    return # Cancelled
            
            add_task(self.conn, title, self.today, task_type="test", test_category=cat)
            self._refresh_tasks()

    def _add_task(self):
        """Insert a default 'New Task' and refresh the list."""
        add_task(self.conn, "New Task", self.today)
        self._refresh_tasks()

    def _rename_task(self, item: QListWidgetItem):
        """Double-click to rename a task via an input dialog."""
        if is_day_finalized(self.conn, self.today):
            return
            
        task_id = item.data(Qt.ItemDataRole.UserRole)
        # Find current title from DB
        tasks = {t["id"]: t for t in get_tasks_by_date(self.conn, self.today)}
        current_title = tasks[task_id]["title"]

        new_title, ok = QInputDialog.getText(
            self, "Rename Task", "New title:", text=current_title
        )
        if ok and new_title.strip():
            from database import update_task_title
            update_task_title(self.conn, task_id, new_title.strip())
            self._refresh_tasks()

    def _toggle_status(self, task_id: int):
        """Toggle task status between target and completed. Trigger marks for Test/DPP."""
        tasks = {t["id"]: t for t in get_tasks_by_date(self.conn, self.today)}
        task = tasks[task_id]

        if task["status"] == "target":
            if task["task_type"] == "dpp":
                self._record_marks(task_id)
            elif task["task_type"] == "test":
                self._record_test_marks(task_id)
            else:
                update_task_status(self.conn, task_id, "completed")
        else:
            update_task_status(self.conn, task_id, "target")
            
        self._refresh_tasks()

    def _record_test_marks(self, task_id: int):
        """Specialized dialog for Test marks (P, C, M)."""
        dialog = TestMarksDialog(self)
        if dialog.exec():
            res = dialog.get_marks()
            from database import update_test_marks
            update_test_marks(
                self.conn, task_id,
                res["p_max"], res["p_score"],
                res["c_max"], res["c_score"],
                res["m_max"], res["m_score"]
            )
            update_task_status(self.conn, task_id, "completed")
            self._refresh_tasks()

    def _delete_selected_task(self, task_id: int):
        """Delete a task and refresh."""
        delete_task(self.conn, task_id)
        self._refresh_tasks()

    def _disable_selected_task(self, task_id: int):
        """Disable a task and refresh."""
        disable_task(self.conn, task_id)
        self._refresh_tasks()

    def _enable_selected_task(self, task_id: int):
        """Enable a task and refresh."""
        enable_task(self.conn, task_id)
        self._refresh_tasks()

    def _show_context_menu(self, position):
        """Right-click context menu with Mark Complete/Incomplete and Delete."""
        if is_day_finalized(self.conn, self.today):
            return
            
        item = self.task_list.itemAt(position)
        if item is None:
            return

        task_id = item.data(Qt.ItemDataRole.UserRole)
        tasks = {t["id"]: t for t in get_tasks_by_date(self.conn, self.today)}
        current_status = tasks[task_id]["status"]

        menu = QMenu(self)

        # Toggle action
        if current_status == "completed":
            toggle_action = menu.addAction("🎯  Mark as Target")
        else:
            toggle_action = menu.addAction("✅  Mark as Completed")

        rename_action = menu.addAction("✏️  Rename")
        menu.addSeparator()
        
        is_enabled = tasks[task_id]["is_enabled"]
        task_type = tasks[task_id].get("task_type", "task")
        
        if is_enabled:
            disable_action = menu.addAction("🚫  Disable Task")
            enable_action = None
        else:
            enable_action = menu.addAction("🟢  Enable Task")
            disable_action = None

        delete_action = menu.addAction("🗑️  Delete")

        action = menu.exec(self.task_list.mapToGlobal(position))

        if action == toggle_action:
            self._toggle_status(task_id)
        elif action == rename_action:
            self._rename_task(item)
        elif disable_action and action == disable_action:
            self._disable_selected_task(task_id)
        elif enable_action and action == enable_action:
            self._enable_selected_task(task_id)
        elif action == delete_action:
            self._delete_selected_task(task_id)

    def _finalize_day(self):
        """Finalize the day and calculate rating."""
        tasks = get_tasks_by_date(self.conn, self.today)
        enabled_tasks = [t for t in tasks if t["is_enabled"] == 1]
        total_enabled = len(enabled_tasks)
        
        if total_enabled == 0:
            rating = 0.0
        else:
            completed_tasks = sum(1 for t in enabled_tasks if t["status"] == "completed")
            rating = (completed_tasks / total_enabled) * 100
            
        finalize_day(self.conn, self.today, rating)
        
        # Move to next logical day only if logical day is behind system today.
        system_today = datetime.date.today().strftime("%d-%m-%Y")
        if self.today != system_today:
            d, m, y = map(int, self.today.split('-'))
            current_dt = datetime.date(y, m, d)
            next_dt = current_dt + datetime.timedelta(days=1)
            self.today = next_dt.strftime("%d-%m-%Y")
        set_active_day(self.conn, self.today)
        
        # Update UI
        if hasattr(self, 'date_label'):
            self.date_label.setText(f"📅  {self.today}")
        
        self._update_late_night_indicator()
            
        self._refresh_tasks()
        
        QMessageBox.information(
            self,
            "Day Finalized",
            f"Day Finalized! Rating: {rating:.0f}%"
        )

    def _record_marks(self, task_id: int):
        """Dialog to record max and obtained marks."""
        # Fetch current marks
        cursor = self.conn.execute("SELECT max_marks, obtained_marks FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        curr_max = row["max_marks"] if row["max_marks"] is not None else 180
        curr_obt = row["obtained_marks"] if row["obtained_marks"] is not None else 0

        max_marks, ok1 = QInputDialog.getInt(self, "Record Marks", "Max Marks:", curr_max, 0, 1000)
        if not ok1: return
        
        obt_marks, ok2 = QInputDialog.getInt(self, "Record Marks", "Obtained Marks:", curr_obt, 0, max_marks)
        if not ok2: return

        from database import update_task_marks
        update_task_marks(self.conn, task_id, max_marks, obt_marks)
        update_task_status(self.conn, task_id, "completed")
        self._refresh_tasks()

    # ── Helpers ───────────────────────────────────────────────────

    def _refresh_tasks(self):
        """Reload the task list from the database."""
        self._update_late_night_indicator()
        self.task_list.clear()
        
        is_finalized = is_day_finalized(self.conn, self.today)
        self.add_btn.setDisabled(is_finalized)
        self.finalize_btn.setDisabled(is_finalized)
        
        if is_finalized:
            self.status_label.setText("🔒 Day Finalized")
            self.status_label.show()
        else:
            self.status_label.hide()
            
        tasks = get_tasks_by_date(self.conn, self.today)

        for task in tasks:
            icon = STATE_ICONS.get(task["status"], "")
            title = task["title"]
            
            # Naming & Meta
            task_type = task.get("task_type", "regular")
            subj = task.get("subject")
            cat = task.get("test_category")
            
            display_text = f"{icon}  {title}"
            
            # Formatting based on type
            if task_type == "dpp":
                if task["max_marks"] is not None:
                    display_text = f"{icon}  [{subj}] DPP ({task['obtained_marks']}/{task['max_marks']})"
                else:
                    display_text = f"{icon}  [{subj}] DPP"
            elif task_type == "test":
                if task["physics_max"] is not None:
                    display_text = (
                        f"{icon}  {title} | "
                        f"P: {task['physics_score']}/{task['physics_max']} | "
                        f"C: {task['chemistry_score']}/{task['chemistry_max']} | "
                        f"M: {task['math_score']}/{task['math_max']} | "
                        f"Total: {task['obtained_marks']}/{task['max_marks']}"
                    )
            
            # Fetch Styles
            bg, fg = _task_colors(task)
            
            # Background selection based on status
            status = task.get("status", "target")
            if status == "completed":
                item_bg = "#1F2A1F" # Soft Green
            elif status == "incomplete": # Hypothetical
                item_bg = "#2A1F1F" # Soft Red
            else:
                item_bg = "#262626" # Default Grey

            font = self.task_list.font()
            if task_type in ("dpp", "test"):
                font.setBold(True)
            if task.get("is_enabled") == 0:
                font.setStrikeOut(True)
            
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, bg) # Store accent color
            item.setText(display_text)
            item.setForeground(QColor(fg))
            item.setBackground(QColor(item_bg))
            item.setFont(font)
            self.task_list.addItem(item)
            
        if hasattr(self, 'calendar_pane'):
            self.calendar_pane.populate_calendar()
        if hasattr(self, "dashboard_page"):
            self.dashboard_page.refresh()
