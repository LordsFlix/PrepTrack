"""
ui/calendar_view.py — Custom Monthly Calendar View.
"""

import calendar
import datetime

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
)

from database import get_tasks_by_date, is_day_finalized, get_day_rating, get_active_day

STATE_ICONS = {
    "target": "🎯",
    "completed": "✅",
    "incomplete": "❌",
}

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
        super().paint(painter, option, index)
        accent_hex = index.data(Qt.ItemDataRole.UserRole + 1)
        if accent_hex:
            painter.save()
            painter.setBrush(QColor(accent_hex))
            painter.setPen(Qt.PenStyle.NoPen)
            rect = option.rect
            painter.drawRect(rect.left(), rect.top(), 4, rect.height())
            painter.restore()



class DayDetailsDialog(QDialog):
    """Popup window showing details for a specific day."""
    
    def __init__(self, date_str: str, conn, parent=None):
        super().__init__(parent)
        self.date_str = date_str
        self.conn = conn
        self.setWindowTitle(f"Day Details: {date_str}")
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #E0E0E0; font-family: "Inter", sans-serif; }
            QLabel { color: #FFFFFF; font-size: 16px; }
            QListWidget {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item {
                border-radius: 6px;
                padding: 12px 14px;
                margin: 6px 6px;
                color: palette(text);
            }
            QListWidget::item:hover {
                background-color: #2C2C2C;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"Details for {self.date_str}")
        header.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(header)
        
        # Stats
        is_finalized = is_day_finalized(self.conn, self.date_str)
        rating = get_day_rating(self.conn, self.date_str)
        
        if is_finalized and rating is not None:
            stats = QLabel(f"🔒 Finalized — Rating: {rating:.0f}%")
            stats.setStyleSheet("color: #BB86FC; font-weight: bold; font-size: 14px;")
        else:
            stats = QLabel("Ongoing / Not Finalized")
            stats.setStyleSheet("color: #888888; font-size: 14px;")
        layout.addWidget(stats)
        
        # Task List
        self.task_list = QListWidget()
        self.task_list.setItemDelegate(TaskItemDelegate(self.task_list))
        self.task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.task_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.task_list)
        
        tasks = get_tasks_by_date(self.conn, self.date_str)
        enabled_tasks = [t for t in tasks if t.get("is_enabled", 1) == 1]
        
        if not enabled_tasks:
            msg = "No enabled tasks recorded on this date." if tasks else "No tasks recorded on this date."
            item = QListWidgetItem(msg)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.task_list.addItem(item)
        else:
            for task in enabled_tasks:
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
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole + 1, bg) # Store accent color
                item.setText(display_text)
                item.setForeground(QColor(fg))
                item.setBackground(QColor(item_bg))
                item.setFont(font)
                self.task_list.addItem(item)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2C2C2C; }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.setMinimumWidth(615)
        self.resize(615,500)


class FullYearViewDialog(QDialog):
    """Scrollable window displaying 12 months starting from April."""
    
    def __init__(self, conn, start_year, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.start_year = start_year
        self.setWindowTitle(f"Full Year View ({start_year}-{start_year+1})")
        self.setMinimumSize(600, 800)
        self.setStyleSheet("background-color: #121212; color: #E0E0E0;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #121212; }")
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(40)
        
        # April (month 4) to March (month 3) of next year
        for i in range(12):
            month = 4 + i
            year = self.start_year
            if month > 12:
                month -= 12
                year += 1
                
            month_container = QWidget()
            month_layout = QVBoxLayout(month_container)
            
            month_name = calendar.month_name[month]
            title = QLabel(f"{month_name} {year}")
            title.setStyleSheet("font-size: 18px; font-weight: bold; color: #BB86FC; margin-bottom: 5px;")
            month_layout.addWidget(title)
            
            grid = QGridLayout()
            grid.setSpacing(4)
            
            # Days Header
            days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for col, d in enumerate(days_of_week):
                lbl = QLabel(d)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #888888; font-size: 11px;")
                grid.addWidget(lbl, 0, col)
                
            # Use logical active_day for today highlighting
            active_day_str = get_active_day(self.conn)
            try:
                d, m, y = map(int, active_day_str.split('-'))
                logical_today = datetime.date(y, m, d)
            except (ValueError, AttributeError):
                logical_today = datetime.date.today()

            month_calendar = calendar.monthcalendar(year, month)
            for row, week in enumerate(month_calendar):
                for col, day in enumerate(week):
                    if day != 0:
                        date_obj = datetime.date(year, month, day)
                        date_str = date_obj.strftime("%d-%m-%Y")
                        
                        is_finalized = is_day_finalized(self.conn, date_str)
                        rating = get_day_rating(self.conn, date_str)
                        is_today = (date_obj == logical_today)
                        
                        bg_color = "#1E1E1E"
                        if is_today and not is_finalized:
                            bg_color = "#BB86FC"
                        elif rating is not None:
                            if rating <= 20: bg_color = "#CF6679"
                            elif rating <= 40: bg_color = "#FF9800"
                            elif rating <= 60: bg_color = "#F4B400"
                            elif rating <= 80: bg_color = "#388E3C"
                            elif rating <= 90: bg_color = "#81C784"
                            else: bg_color = "#4CC9F0"
                            
                        tile = DayTile(day, is_today, bg_color, date_str, rating)
                        # We use a wrapper or direct call
                        tile.clicked.connect(lambda checked, d=date_str: self._show_details(d))
                        grid.addWidget(tile, row + 1, col)
            
            month_layout.addLayout(grid)
            container_layout.addWidget(month_container)
            
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("Close Full Year View")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _show_details(self, date_str):
        dialog = DayDetailsDialog(date_str, self.conn, parent=self)
        dialog.exec()


class DayTile(QPushButton):
    """Custom widget for a single day in the calendar grid."""

    def __init__(self, day: int, is_today: bool, bg_color: str, date_str: str, rating: float = None):
        super().__init__()
        self.setText(str(day))  # ensure date is written safely into the grid tile
        self.day = day
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(50, 50)
        
        # Tooltip
        rating_text = f"{rating:.0f}%" if rating is not None else "No data"
        self.setToolTip(f"Date: {date_str} | Rating: {rating_text}")
        
        border_css = "border: 2px solid cyan;" if is_today else "border: 1px solid #333333;"
        text_color = "#121212" if bg_color in ("#81C784", "#4CC9F0", "#F4B400") else "#E0E0E0"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                {border_css}
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                border: 2px solid #FFFFFF;
            }}
        """)


class CalendarView(QWidget):
    """Custom grid-based monthly calendar panel."""

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        # Initialize viewing date to active logical day
        active_day_str = get_active_day(self.conn)
        try:
            d, m, y = map(int, active_day_str.split('-'))
            self.current_date = datetime.date(y, m, d)
        except (ValueError, AttributeError):
            self.current_date = datetime.date.today()

        self._build_ui()
        self.populate_calendar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 28, 28, 28)
        layout.setSpacing(14)

        # Header: Month & Year
        header_layout = QHBoxLayout()
        
        nav_btn_style = """
            QPushButton {
                background-color: transparent;
                color: #E0E0E0;
                font-size: 24px;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                color: #BB86FC;
            }
        """

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(35, 35)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(nav_btn_style)
        self.prev_btn.clicked.connect(self._prev_month)
        header_layout.addWidget(self.prev_btn)

        self.month_label = QLabel()
        self.month_label.setObjectName("heading")
        self.month_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.month_label, stretch=1)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(35, 35)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(nav_btn_style)
        self.next_btn.clicked.connect(self._next_month)
        header_layout.addWidget(self.next_btn)

        layout.addLayout(header_layout)

        # Grid system
        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        layout.addLayout(self.grid)

        # Navigation Buttons
        nav_btns = QHBoxLayout()
        
        self.today_btn = QPushButton("Back to Present")
        self.today_btn.clicked.connect(self._go_to_today)
        nav_btns.addWidget(self.today_btn)
        
        self.year_btn = QPushButton("Full Year View")
        self.year_btn.clicked.connect(self._full_year_view)
        nav_btns.addWidget(self.year_btn)
        
        layout.addLayout(nav_btns)
        layout.addStretch()

    def populate_calendar(self):
        """Build the grid based on self.current_date."""
        # Clear existing grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        year = self.current_date.year
        month = self.current_date.month

        # Update title
        month_name = calendar.month_name[month]
        self.month_label.setText(f"{month_name} {year}")

        # Add Day of week headers
        days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, day_name in enumerate(days_of_week):
            lbl = QLabel(day_name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold;")
            self.grid.addWidget(lbl, 0, col)

        # Fetch logical today for highlighting
        active_day_str = get_active_day(self.conn)
        try:
            d, m, y = map(int, active_day_str.split('-'))
            logical_today = datetime.date(y, m, d)
        except (ValueError, AttributeError):
            logical_today = datetime.date.today()
            
        is_current_my = (year == logical_today.year and month == logical_today.month)

        # Render dates
        month_calendar = calendar.monthcalendar(year, month)
        
        for row, week in enumerate(month_calendar):
            for col, day in enumerate(week):
                if day != 0:
                    is_today = is_current_my and (day == logical_today.day)
                    
                    # Fetch metrics for tile
                    date_str = datetime.date(year, month, day).strftime("%d-%m-%Y")
                    is_finalized = is_day_finalized(self.conn, date_str)
                    rating = get_day_rating(self.conn, date_str)

                    # Determine Background Color Sequence
                    bg_color = "#1E1E1E" # No data
                    if is_today and not is_finalized:
                        bg_color = "#BB86FC" # Purple
                    elif rating is not None:
                        if rating <= 20: bg_color = "#CF6679" # Red
                        elif rating <= 40: bg_color = "#FF9800" # Orange
                        elif rating <= 60: bg_color = "#F4B400" # Yellow/Golden
                        elif rating <= 80: bg_color = "#388E3C" # Dark green
                        elif rating <= 90: bg_color = "#81C784" # Light green
                        else: bg_color = "#4CC9F0" # Light blue

                    tile = DayTile(day, is_today, bg_color, date_str, rating)
                    tile.clicked.connect(lambda checked, d=day: self._show_date_details(year, month, d))
                    self.grid.addWidget(tile, row + 1, col)

    def _show_date_details(self, year: int, month: int, day: int):
        date_str = datetime.date(year, month, day).strftime("%d-%m-%Y")
        dialog = DayDetailsDialog(date_str, self.conn, parent=self)
        dialog.exec()

    def _go_to_today(self):
        active_day_str = get_active_day(self.conn)
        try:
            d, m, y = map(int, active_day_str.split('-'))
            self.current_date = datetime.date(y, m, d)
        except (ValueError, AttributeError):
            self.current_date = datetime.date.today()
        self.populate_calendar()
        # Suggesting back to present really means back to the active logical day.

    def _full_year_view(self):
        # Determine start year. If current month < 4 (Apr), standard financial year starts last year.
        # But per user request "starting from april", we'll just start from the most recent or current April.
        year = self.current_date.year
        if self.current_date.month < 4:
            year -= 1
        
        dialog = FullYearViewDialog(self.conn, year, parent=self)
        dialog.exec()

    def _prev_month(self):
        year = self.current_date.year
        month = self.current_date.month
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
        self.current_date = datetime.date(year, month, 1)
        self.populate_calendar()

    def _next_month(self):
        year = self.current_date.year
        month = self.current_date.month
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        self.current_date = datetime.date(year, month, 1)
        self.populate_calendar()
