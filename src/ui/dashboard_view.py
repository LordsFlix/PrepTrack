"""
ui/dashboard_view.py — Complete performance tracking and analytics dashboard.
"""

from PyQt6.QtCore import Qt, QDate, QPropertyAnimation, QEasingCurve, QRect, QSize, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QFrame,
    QSizePolicy,
    QTabWidget,
    QScrollArea,
    QComboBox,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtGui import QColor, QFont
import datetime
from database import get_active_day, get_day_metrics, is_attempted, is_future
from ui.calendar_view import DayDetailsDialog
from ui.graph_widget import GraphWidget

class DashboardView(QWidget):
    """Full performance analytics system with record-keeping."""
    
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._build_ui()
        
    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(10)
        
        # Header
        header = QLabel("Performance Analytics")
        header.setObjectName("heading")
        header.setStyleSheet("font-size: 24px; font-weight: bold; padding-bottom: 5px;")
        self.layout.addWidget(header)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border-top: 1px solid #333333;
                background: transparent;
            }
            QTabBar::tab {
                background-color: #1E1E1E;
                color: #888888;
                padding: 10px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2D2D2D;
                color: #BB86FC;
                border-bottom: 2px solid #BB86FC;
            }
            QTabBar::tab:hover {
                background-color: #252525;
            }
        """)
        
        self.overview_tab = QWidget()
        self.tests_tab = QWidget()
        self.dpp_tab = QWidget()
        
        self.tabs.addTab(self.overview_tab, "Overview")
        self.tabs.addTab(self.tests_tab, "Tests")
        self.tabs.addTab(self.dpp_tab, "DPP")
        
        self.layout.addWidget(self.tabs)
        
        # Build Each Tab
        self._setup_overview_tab()
        self._setup_tests_tab()
        self._setup_dpp_tab()
        
    # --- Tab Setups ---

    def _setup_overview_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            """
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                border-radius: 3px;
            }
            """
        )

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(16, 12, 16, 12)
        l.setSpacing(24)
        scroll.setWidget(container)

        outer_layout = QVBoxLayout(self.overview_tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(scroll)

        # KPI row
        cards_section = self._create_section_container()
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(16)

        self.ov_current_streak = self._create_stat_card("Streak", "---", "#FF9800")
        self.ov_best_streak = self._create_stat_card("Best Streak", "---", "#FFD700")
        self.ov_comp_rate = self._create_stat_card("Weekly Completion Rate", "---%", "#03DAC6")

        stats_row.addWidget(self.ov_current_streak, 1)
        stats_row.addWidget(self.ov_best_streak, 1)
        stats_row.addWidget(self.ov_comp_rate, 1)
        cards_section.layout().addLayout(stats_row)
        l.addWidget(cards_section)

        # Main graph section (primary focus)
        main_graph_section = self._create_section_container()
        main_graph_layout = main_graph_section.layout()
        self.test_trend_graph = GraphWidget()
        self.test_trend_graph.setMinimumHeight(280)
        self.test_trend_graph.setMaximumHeight(320)
        main_graph_layout.addWidget(self.test_trend_graph)
        l.addWidget(main_graph_section)

        # Secondary graph grid (2 columns)
        secondary_graphs_section = self._create_section_container()
        secondary_row = QHBoxLayout()
        secondary_row.setContentsMargins(0, 0, 0, 0)
        secondary_row.setSpacing(18)
        self.dpp_trend_graph = GraphWidget()
        self.dpp_trend_graph.setMinimumHeight(210)
        self.dpp_trend_graph.setMaximumHeight(240)
        self.weekly_completion_graph = GraphWidget()
        self.weekly_completion_graph.setMinimumHeight(210)
        self.weekly_completion_graph.setMaximumHeight(240)
        secondary_row.addWidget(self.dpp_trend_graph, 1)
        secondary_row.addWidget(self.weekly_completion_graph, 1)
        secondary_graphs_section.layout().addLayout(secondary_row)
        l.addWidget(secondary_graphs_section)
        
        # Recent performance section
        recent_section = self._create_section_container()
        recent_layout = recent_section.layout()
        trend_header = QLabel("Recent Activity (Last 7 Days)")
        trend_header.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 14px;")
        recent_layout.addWidget(trend_header)
        
        self.trend_list = QListWidget()
        self.trend_list.setStyleSheet(
            "background-color: #161616; border: none; border-radius: 10px; padding: 6px;"
        )
        self.trend_list.setSpacing(8)
        self.trend_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.trend_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.trend_list.viewport().installEventFilter(self)
        self.trend_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trend_list.setToolTip("Double click to view details")
        self.trend_list.itemDoubleClicked.connect(self._open_day_details_from_trend)
        recent_layout.addWidget(self.trend_list, stretch=1)
        l.addWidget(recent_section, stretch=1)
        l.addStretch()

    def _setup_tests_tab(self):
        l = QVBoxLayout(self.tests_tab)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        
        # Analytics
        analytics = QHBoxLayout()
        self.test_overall_avg = self._create_stat_card("Overall Avg", "---", "#BB86FC")
        self.test_best_score = self._create_stat_card("Best Score", "---", "#FFD700")
        analytics.addWidget(self.test_overall_avg)
        analytics.addWidget(self.test_best_score)
        l.addLayout(analytics)

        # Records List
        l.addSpacing(10)
        l.addWidget(QLabel("Full Track Record (Tests)"))
        
        self.test_results_list = QListWidget()
        self.test_results_list.setStyleSheet("background-color: #1E1E1E; border: 1px solid #333333; border-radius: 8px;")
        l.addWidget(self.test_results_list, stretch=1)

    def _setup_dpp_tab(self):
        l = QVBoxLayout(self.dpp_tab)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(15)
        
        # Analytics & Selector
        top_row = QHBoxLayout()
        self.month_selector = QComboBox()
        self._populate_months()
        self.month_selector.currentIndexChanged.connect(self.refresh)
        top_row.addWidget(self.month_selector)
        l.addLayout(top_row)
        
        analytics = QHBoxLayout()
        self.dpp_p_avg = self._create_mini_card("P-Avg", "---", "#4FC3F7")
        self.dpp_c_avg = self._create_mini_card("C-Avg", "---", "#81C784")
        self.dpp_m_avg = self._create_mini_card("M-Avg", "---", "#FFD54F")
        analytics.addWidget(self.dpp_p_avg)
        analytics.addWidget(self.dpp_c_avg)
        analytics.addWidget(self.dpp_m_avg)
        l.addLayout(analytics)

        # Records List
        l.addSpacing(10)
        l.addWidget(QLabel("DPP History"))
        self.dpp_list = QListWidget()
        self.dpp_list.setStyleSheet("background-color: #1E1E1E; border: 1px solid #333333; border-radius: 8px;")
        l.addWidget(self.dpp_list, stretch=1)

    # --- Analytics & Data Logic ---

    def refresh(self):
        """Update metrics and lists from the database."""
        self._populate_months()
        self._update_overview()
        self._update_tests()
        self._update_dpps()

    def _update_overview(self):
        # 1. Streak Calculation (Current and Best)
        try:
            active_day_str = get_active_day(self.conn)
            try:
                active_day = QDate.fromString(active_day_str, "dd-MM-yyyy")
                if not active_day.isValid():
                    active_day = QDate.currentDate()
            except Exception:
                active_day = QDate.currentDate()

            # For Current Streak (reverse chronological, anchored to logical active day).
            current_streak = 0
            probe = active_day
            while True:
                d = probe.toString("dd-MM-yyyy")
                day_metrics = get_day_metrics(self.conn, d, today=active_day_str)
                completion_pc = day_metrics["completion_percent"]
                if completion_pc is not None and completion_pc >= 60.0:
                    current_streak += 1
                    probe = probe.addDays(-1)
                else:
                    break

            # For Best Streak (chronological across known task date range to active day).
            cursor = self.conn.execute(
                "SELECT MIN(substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)) as min_iso "
                "FROM tasks"
            )
            min_iso = cursor.fetchone()["min_iso"]
            best_streak = 0
            if min_iso:
                min_day = QDate.fromString(min_iso, "yyyy-MM-dd")
                if min_day.isValid() and min_day <= active_day:
                    temp_streak = 0
                    iter_day = min_day
                    while iter_day <= active_day:
                        d = iter_day.toString("dd-MM-yyyy")
                        day_metrics = get_day_metrics(self.conn, d, today=active_day_str)
                        completion_pc = day_metrics["completion_percent"]
                        if completion_pc is not None and completion_pc >= 60.0:
                            temp_streak += 1
                        else:
                            best_streak = max(best_streak, temp_streak)
                            temp_streak = 0
                        iter_day = iter_day.addDays(1)
                    best_streak = max(best_streak, temp_streak)

            self.ov_current_streak.findChild(QLabel, "val").setText(f"{current_streak} Days")
            self.ov_best_streak.findChild(QLabel, "val").setText(f"{best_streak} Days")

            # 2. Weekly Completion Rate (Last 7 logical days, excluding no-task days)
            last_7_days = [(active_day.addDays(-i).toString("dd-MM-yyyy")) for i in range(7)]

            total_sum_pc = 0.0
            count_days = 0
            for d in last_7_days:
                day_metrics = get_day_metrics(self.conn, d, today=active_day_str)
                completion_pc = day_metrics["completion_percent"]
                if completion_pc is not None:
                    total_sum_pc += completion_pc
                    count_days += 1

            comp_val = self.ov_comp_rate.findChild(QLabel, "val")
            if count_days > 0:
                avg_pc = (total_sum_pc / count_days)
                comp_val.setText(f"{avg_pc:.1f}%")
            else:
                comp_val.setText("—")

            # 3. Recent Performance List (Last 7 Days)
            self.trend_list.clear()
            for d in last_7_days:
                day_metrics = get_day_metrics(self.conn, d, today=active_day_str)
                all_pc = day_metrics["completion_percent"]
                perf_pc = day_metrics["performance_percent"]
                item = QListWidgetItem()
                widget = self._create_recent_activity_card(d, all_pc, perf_pc)
                row_height = max(96, widget.sizeHint().height())
                item.setSizeHint(QSize(0, row_height))
                item.setData(Qt.ItemDataRole.UserRole, d)
                self.trend_list.addItem(item)
                self.trend_list.setItemWidget(item, widget)

            # Let the outer overview scroll area handle page scrolling.
            total_item_height = 0
            for i in range(self.trend_list.count()):
                total_item_height += self.trend_list.item(i).sizeHint().height()
            spacing = max(0, self.trend_list.count() - 1) * self.trend_list.spacing()
            margins = self.trend_list.contentsMargins()
            viewport_margins = self.trend_list.viewportMargins()
            frame_pad = (
                margins.top()
                + margins.bottom()
                + viewport_margins.top()
                + viewport_margins.bottom()
                + (2 * self.trend_list.frameWidth())
                + 48
            )
            self.trend_list.setFixedHeight(total_item_height + spacing + frame_pad)

            self._update_overview_graphs(active_day_str)
                
        except Exception as e:
            print(f"Overview error: {e}")

    def _create_recent_activity_card(self, date, overall_pc, performance_pc):
        """Build a modern recent-activity timeline card widget."""
        card = QFrame()
        card.setObjectName("recentActivityCard")
        card.setMinimumHeight(80)
        card.setStyleSheet(
            """
            QFrame#recentActivityCard {
                background-color: #1E1E1E;
                border-radius: 10px;
            }
            QFrame#recentActivityCard:hover {
                background-color: #2A2A2A;
            }
            """
        )

        root = QHBoxLayout(card)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(14)

        parsed_date = QDate.fromString(date, "dd-MM-yyyy")
        date_text = parsed_date.toString("dd MMM yyyy") if parsed_date.isValid() else date
        has_activity = overall_pc is not None or performance_pc is not None
        subtitle_text = "Active day" if has_activity else "No activity"

        safe_overall = max(0, min(100, int(round(overall_pc or 0))))
        if safe_overall <= 30:
            bar_color = "#EF5350"
        elif safe_overall < 70:
            bar_color = "#FFD54F"
        else:
            bar_color = "#66BB6A"

        if safe_overall == 0:
            status_icon = "❌"
        elif safe_overall >= 60:
            status_icon = "✅"
        else:
            status_icon = "⚠️"

        # Left section: date + status subtitle
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(1)
        date_lbl = QLabel(date_text)
        date_lbl.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700;")
        subtitle_lbl = QLabel(f"{status_icon} {subtitle_text}")
        subtitle_lbl.setStyleSheet("color: #B0B0B0; font-size: 12px;")
        left_col.addWidget(date_lbl)
        left_col.addWidget(subtitle_lbl)
        left_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        left_container = QWidget()
        left_container.setLayout(left_col)
        left_container.setMinimumWidth(220)

        # Center section: progress track + real fill frame
        center_col = QVBoxLayout()
        center_col.setContentsMargins(0, 0, 0, 0)
        center_col.setSpacing(0)
        bar_bg = QFrame()
        bar_bg.setStyleSheet("background-color: #2A2A2A; border-radius: 4px;")
        bar_bg.setFixedHeight(6)
        bar_width = 150
        bar_bg.setFixedWidth(bar_width)

        bar_fill = QFrame(bar_bg)
        bar_fill.setStyleSheet(f"background-color: {bar_color}; border-radius: 4px;")
        bar_fill.setFixedHeight(6)
        target_width = int(bar_width * (safe_overall / 100))
        bar_fill.setGeometry(QRect(0, 0, 0, 6))

        anim = QPropertyAnimation(bar_fill, b"geometry", card)
        anim.setDuration(350)
        anim.setStartValue(QRect(0, 0, 0, 6))
        anim.setEndValue(QRect(0, 0, target_width, 6))
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start()
        bar_fill._progress_anim = anim

        center_col.addWidget(bar_bg, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Right section: large percentage badge
        pct_lbl = QLabel(f"{safe_overall}%")
        pct_lbl.setStyleSheet(f"color: {bar_color}; font-size: 18px; font-weight: 700;")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pct_lbl.setMinimumWidth(54)

        root.addWidget(left_container, 4, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(center_col, 3)
        root.addWidget(pct_lbl, 1, alignment=Qt.AlignmentFlag.AlignVCenter)
        return card

    def _open_day_details_from_trend(self, item: QListWidgetItem):
        """Open existing day details dialog from a recent-performance row."""
        date_str = item.data(Qt.ItemDataRole.UserRole)
        if not date_str:
            return
        dialog = DayDetailsDialog(date_str, self.conn, parent=self)
        dialog.exec()

    def eventFilter(self, obj, event):
        """Prevent wheel-scrolling inside recent activity list."""
        if hasattr(self, "trend_list") and obj is self.trend_list.viewport():
            if event.type() == QEvent.Type.Wheel:
                return True
        return super().eventFilter(obj, event)

    def _update_overview_graphs(self, active_day_str: str):
        active_day = datetime.datetime.strptime(active_day_str, "%d-%m-%Y").date()

        # 1) Test Performance Trend
        test_rows = self.conn.execute(
            "SELECT date, obtained_marks, max_marks, status, is_enabled, task_type "
            "FROM tasks WHERE task_type='test' AND is_enabled=1"
        ).fetchall()
        test_points = []
        for row in test_rows:
            task = dict(row)
            if not is_attempted(task) or is_future(task, active_day):
                continue
            d = datetime.datetime.strptime(task["date"], "%d-%m-%Y").date()
            pc = (task["obtained_marks"] / task["max_marks"]) * 100
            test_points.append((d, pc, f"{task['date']} | {pc:.1f}%"))
        test_points.sort(key=lambda p: p[0])
        cycle_start_year = active_day.year if active_day.month >= 4 else active_day.year - 1
        cycle_start = datetime.datetime(cycle_start_year, 4, 1, 0, 0, 0)
        cycle_end = datetime.datetime(cycle_start_year + 1, 3, 31, 23, 59, 59)
        test_x_ticks = [
            datetime.datetime(cycle_start_year, 4, 1),
            datetime.datetime(cycle_start_year, 7, 1),
            datetime.datetime(cycle_start_year, 10, 1),
            datetime.datetime(cycle_start_year + 1, 1, 1),
            datetime.datetime(cycle_start_year + 1, 3, 1),
        ]
        test_x_ticklabels = [
            f"Apr {cycle_start_year}",
            "Jul",
            "Oct",
            "Jan",
            "Mar",
        ]
        self.test_trend_graph.set_series(
            "Test Performance Trend",
            [{"label": "Test", "color": "#facc15", "points": test_points}],
            x_formatter="%b",
            x_limits=(cycle_start, cycle_end),
            x_ticks=test_x_ticks,
            x_ticklabels=test_x_ticklabels,
            legend_loc="upper left",
            legend_bbox=(0.0, 0.99),
            scroll_window_days=365,
            initial_window_end=cycle_end,
        )

        # 2) DPP Subject-wise Trend
        dpp_rows = self.conn.execute(
            "SELECT date, subject, obtained_marks, max_marks, status, is_enabled, task_type "
            "FROM tasks WHERE task_type='dpp' AND is_enabled=1"
        ).fetchall()
        subjects = {
            "Physics": {"color": "#38bdf8", "points": []},
            "Chemistry": {"color": "#4ade80", "points": []},
            "Mathematics": {"color": "#fb923c", "points": []},
        }
        for row in dpp_rows:
            task = dict(row)
            if not is_attempted(task) or is_future(task, active_day):
                continue
            subj = task.get("subject")
            if subj not in subjects:
                continue
            d = datetime.datetime.strptime(task["date"], "%d-%m-%Y").date()
            pc = (task["obtained_marks"] / task["max_marks"]) * 100
            subjects[subj]["points"].append((d, pc, f"{task['date']} | {subj} | {pc:.1f}%"))
        dpp_series = []
        for name, cfg in subjects.items():
            cfg["points"].sort(key=lambda p: p[0])
            dpp_series.append({"label": name, "color": cfg["color"], "points": cfg["points"]})
        self.dpp_trend_graph.set_series(
            "DPP Performance Trend",
            dpp_series,
            x_formatter="%d %b",
            legend_loc="lower left",
            legend_bbox=(0.0, 1.0),
            scroll_window_days=30,
            initial_window_end=datetime.datetime.combine(active_day, datetime.time.max),
        )

        # 3) Last 7 days completion trend (daily points, weekday labels)
        last_7_dates = [active_day - datetime.timedelta(days=i) for i in range(6, -1, -1)]
        weekly_points = []
        x_ticks = []
        x_labels = []
        for day in last_7_dates:
            day_str = day.strftime("%d-%m-%Y")
            day_metrics = get_day_metrics(self.conn, day_str, today=active_day_str)
            completion_pc = day_metrics["completion_percent"]
            if completion_pc is None:
                completion_pc = 0.0
            day_dt = datetime.datetime.combine(day, datetime.time.min)
            weekly_points.append((day_dt, completion_pc, f"{day.strftime('%a')} | {completion_pc:.1f}%"))
            x_ticks.append(day_dt)
            x_labels.append(day.strftime("%a"))

        x_min = datetime.datetime.combine(last_7_dates[0], datetime.time.min)
        x_max = datetime.datetime.combine(last_7_dates[-1], datetime.time.max)
        self.weekly_completion_graph.set_series(
            "Weekly Completion Rate",
            [{"label": "Completion", "color": "#a970ff", "points": weekly_points}],
            x_formatter="%a",
            x_limits=(x_min, x_max),
            x_ticks=x_ticks,
            x_ticklabels=x_labels,
        )

    def _update_tests(self):
        self.test_results_list.clear()
        try:
            logical_today_str = get_active_day(self.conn)
            logical_today = QDate.fromString(logical_today_str, "dd-MM-yyyy")
            if not logical_today.isValid():
                logical_today = QDate.currentDate()

            # Full List
            cursor = self.conn.execute("SELECT * FROM tasks WHERE task_type='test' ORDER BY substr(date, 7, 4) DESC, substr(date, 4, 2) DESC, substr(date, 1, 2) DESC")
            tests = cursor.fetchall()
            
            completed = []
            upcoming = []
            metrics_dates = set()
            
            for t in tests:
                task = dict(t)
                has_result = is_attempted(task) and not is_future(task, logical_today_str)
                if has_result:
                    completed.append(t)
                    metrics_dates.add(t["date"])
                else:
                    test_date = QDate.fromString(t["date"], "dd-MM-yyyy")
                    if test_date.isValid() and test_date >= logical_today:
                        upcoming.append((test_date, t))

            upcoming.sort(key=lambda pair: pair[0])
            
            # 1. Analytics (Only Completed)
            overall_sum_obt = 0.0
            overall_sum_max = 0.0
            best_percentage = 0.0
            for d in metrics_dates:
                day_metrics = get_day_metrics(
                    self.conn,
                    d,
                    today=logical_today_str,
                    performance_task_types=("test",),
                )
                if day_metrics["performance_percent"] is not None:
                    best_percentage = max(best_percentage, day_metrics["performance_percent"])
                overall_sum_obt += day_metrics["performance_obtained"]
                overall_sum_max += day_metrics["performance_max"]
                
            avg = (overall_sum_obt / overall_sum_max * 100) if overall_sum_max > 0 else 0
            self.test_overall_avg.findChild(QLabel, "val").setText(f"{avg:.1f}%")
            self.test_best_score.findChild(QLabel, "val").setText(f"{best_percentage:.1f}%")
            
            # 2. Display List
            if upcoming:
                header = QListWidgetItem("📅 Upcoming Tests")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setForeground(QColor("#BB86FC"))
                self.test_results_list.addItem(header)
                
                for test_date, t in upcoming:
                    days_remaining = logical_today.daysTo(test_date)
                    if days_remaining == 0:
                        due_text = "today"
                    elif days_remaining == 1:
                        due_text = "in 1 day"
                    else:
                        due_text = f"in {days_remaining} days"

                    txt = f"{t['date']}  |  {t['title']}  |  (Scheduled, {due_text})"
                    item = QListWidgetItem(txt)
                    item.setForeground(QColor("#888888"))
                    f = item.font()
                    f.setItalic(True)
                    item.setFont(f)
                    self.test_results_list.addItem(item)
                
                self.test_results_list.addItem(QListWidgetItem("")) # Spacer

            if completed:
                header = QListWidgetItem("✅ Completed Tests")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setForeground(QColor("#03DAC6"))
                self.test_results_list.addItem(header)
                
                for t in completed:
                    obt = t["obtained_marks"]
                    mx = t["max_marks"]
                    txt = f"{t['date']}  |  {t['title']}  |  {obt}/{mx} ({ (obt/mx*100):.1f}%)"
                    item = QListWidgetItem(txt)
                    
                    # Sub-scores
                    subs = []
                    if t["physics_max"]: subs.append(f"P: {t['physics_score']}/{t['physics_max']}")
                    if t["chemistry_max"]: subs.append(f"C: {t['chemistry_score']}/{t['chemistry_max']}")
                    if t["math_max"]: subs.append(f"M: {t['math_score']}/{t['math_max']}")
                    if subs: item.setToolTip(" • ".join(subs))
                    
                    self.test_results_list.addItem(item)
            
        except Exception as e:
            print(f"Test update error: {e}")

    def _update_dpps(self):
        self.dpp_list.clear()
        selected_month = self.month_selector.currentData()
        active_day = get_active_day(self.conn)

        try:
            params = []
            query = (
                "SELECT * FROM tasks "
                "WHERE task_type='dpp' AND is_enabled=1"
            )
            if selected_month:
                query += " AND substr(date, 4, 7)=?"
                params.append(selected_month)
            query += " ORDER BY substr(date, 7, 4) DESC, substr(date, 4, 2) DESC, substr(date, 1, 2) DESC, id DESC"

            cursor = self.conn.execute(query, tuple(params))
            dpps = cursor.fetchall()
            
            subj_stats = {"Physics": [0,0], "Chemistry": [0,0], "Mathematics": [0,0]}
            
            for d in dpps:
                marks_missing = d["obtained_marks"] is None or d["max_marks"] is None or d["max_marks"] <= 0
                # Ignore active-day DPPs without marks from average calculations.
                skip_for_avg = d["date"] == active_day and marks_missing

                obt = d["obtained_marks"] or 0
                mx = d["max_marks"] or 1
                subj = d["subject"] or "Other"
                if subj in subj_stats and not skip_for_avg:
                    subj_stats[subj][0] += obt
                    subj_stats[subj][1] += mx
                
                txt = f"{d['date']}  |  {subj}  |  {obt}/{mx} ({ (obt/mx*100):.1f}%)"
                self.dpp_list.addItem(QListWidgetItem(txt))
            
            # Update mini cards
            for (s, lbl) in [("Physics", self.dpp_p_avg), ("Chemistry", self.dpp_c_avg), ("Mathematics", self.dpp_m_avg)]:
                vals = subj_stats[s]
                avg = (vals[0] / vals[1] * 100) if vals[1] > 0 else 0
                lbl.findChild(QLabel, "val").setText(f"{avg:.0f}%")
                
        except Exception as e:
            print(f"DPP update error: {e}")

    # --- Helpers ---

    def _populate_months(self):
        current_data = self.month_selector.currentData()
        self.month_selector.blockSignals(True)
        self.month_selector.clear()
        self.month_selector.addItem("All", None)
        try:
            cursor = self.conn.execute(
                "SELECT DISTINCT substr(date, 4, 7) as m "
                "FROM tasks WHERE task_type='dpp' AND is_enabled=1"
            )
            month_keys = [row["m"] for row in cursor.fetchall() if row["m"]]
            month_keys.sort(key=lambda x: (int(x[3:]), int(x[:2])), reverse=True)

            for month_key in month_keys:
                month_label = datetime.datetime.strptime(month_key, "%m-%Y").strftime("%B %Y")
                self.month_selector.addItem(month_label, month_key)

            if current_data:
                idx = self.month_selector.findData(current_data)
                self.month_selector.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                self.month_selector.setCurrentIndex(0)
        except Exception:
            pass
        finally:
            self.month_selector.blockSignals(False)

    def _create_stat_card(self, title, value, accent_color):
        card = QFrame()
        card.setMinimumHeight(78)
        card.setMaximumHeight(92)
        card.setStyleSheet(
            f"background-color: #161616; border: none; border-radius: 10px;"
        )
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 8, 12, 8)
        l.setSpacing(2)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #9A9A9A; font-size: 11px; font-weight: 600;")
        v_lbl = QLabel(value)
        v_lbl.setObjectName("val")
        v_lbl.setStyleSheet(f"color: {accent_color}; font-size: 20px; font-weight: 700;")
        l.addWidget(t_lbl)
        l.addWidget(v_lbl)
        return card

    def _create_section_container(self):
        section = QFrame()
        section.setStyleSheet(
            "QFrame { background-color: #161616; border: none; border-radius: 12px; }"
        )
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)
        return section

    def _create_mini_card(self, title, value, accent_color):
        card = QFrame()
        card.setStyleSheet(f"background-color: #2D2D2D; border: 1px solid #333333; border-left: 3px solid {accent_color}; border-radius: 6px;")
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        v_lbl = QLabel(value)
        v_lbl.setObjectName("val")
        v_lbl.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        l.addWidget(t_lbl)
        l.addWidget(v_lbl)
        return card
