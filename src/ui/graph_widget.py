"""
ui/graph_widget.py — Reusable Matplotlib graph widget for PyQt6.
"""

from __future__ import annotations

import math
import datetime
from typing import Iterable

import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter, MultipleLocator
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QWidget, QVBoxLayout


class GraphWidget(QWidget):
    """Reusable graph container with dark theme and hover tooltips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = Figure(figsize=(6, 3), dpi=100, facecolor="#0f0f0f")
        self._ax = self._figure.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._tooltip = None
        self._hover_vline = None
        self._points = []
        self._scroll_enabled = False
        self._scroll_window_days = 30
        self._scroll_min = None
        self._scroll_max = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self._canvas.mpl_connect("scroll_event", self._on_scroll)
        self._style_axes("")

    def _style_axes(self, title: str):
        self._ax.clear()
        self._ax.set_axis_on()
        self._ax.set_facecolor("#0f0f0f")
        self._figure.patch.set_facecolor("#0f0f0f")
        self._ax.set_title(title, color="#FFFFFF", fontsize=12, fontweight="semibold", pad=12)
        self._ax.tick_params(axis="x", colors="#FFFFFF", labelsize=9, length=0)
        self._ax.tick_params(axis="y", colors="#FFFFFF", labelsize=9, length=0)
        self._ax.grid(True, color="#444444", alpha=0.2, linewidth=0.8)
        self._figure.subplots_adjust(left=0.08, right=0.98, top=0.82, bottom=0.22)
        for spine in self._ax.spines.values():
            spine.set_visible(False)

    def set_series(
        self,
        title: str,
        series: Iterable[dict],
        empty_message: str = "No data yet",
        x_formatter: str | None = None,
        x_limits: tuple | None = None,
        x_ticks: list | None = None,
        x_ticklabels: list | None = None,
        legend_loc: str = "upper left",
        legend_bbox: tuple | None = None,
        scroll_window_days: int | None = None,
        initial_window_end: datetime.datetime | datetime.date | None = None,
    ):
        """
        Plot one or more line series.

        Each series dict supports:
          - label: str
          - color: str
          - points: list[tuple[datetime/date, float, tooltip_text]]
        """
        self._style_axes(title)
        self._points = []

        has_data = False
        for s in series:
            points = s.get("points", [])
            if not points:
                continue
            has_data = True
            x_vals = [p[0] for p in points]
            y_vals = [p[1] for p in points]
            self._ax.plot(
                x_vals,
                y_vals,
                color=s.get("color", "#FFFFFF"),
                marker="o",
                markersize=4.5,
                linewidth=2.0,
                label=s.get("label", ""),
            )
            for p in points:
                self._points.append(
                    {
                        "x": p[0],
                        "y": p[1],
                        "text": p[2],
                    }
                )

        if has_data:
            self._ax.set_ylim(0, 100)
            self._ax.yaxis.set_major_locator(MultipleLocator(20))
            self._ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
            fmt = x_formatter or "%d %b %Y"
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
            self._ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
            if x_ticks:
                self._ax.set_xticks(x_ticks)
            if x_ticklabels:
                self._ax.set_xticklabels(x_ticklabels)
            if x_limits:
                self._ax.set_xlim(x_limits[0], x_limits[1])
            self._ax.margins(x=0)
            if x_ticklabels:
                for label in self._ax.get_xticklabels():
                    label.set_ha("center")
                self._figure.autofmt_xdate(rotation=0, ha="center")
            else:
                self._figure.autofmt_xdate(rotation=20, ha="right")
            if any(s.get("label") for s in series):
                legend_kwargs = {
                    "loc": legend_loc,
                    "frameon": True,
                    "facecolor": "#0f0f0f",
                    "edgecolor": "#444444",
                }
                if legend_bbox is not None:
                    # Reserve extra headroom when legend is anchored above the axes.
                    if len(legend_bbox) >= 2 and legend_bbox[1] >= 1.0:
                        self._figure.subplots_adjust(top=0.68)
                    legend_kwargs["bbox_to_anchor"] = legend_bbox
                    legend_kwargs["borderaxespad"] = 0.0
                leg = self._ax.legend(**legend_kwargs)
                for t in leg.get_texts():
                    t.set_color("#FFFFFF")

            # Optional month-window scrolling without visible scrollbars.
            self._scroll_enabled = bool(scroll_window_days)
            if self._scroll_enabled:
                self._scroll_window_days = max(1, int(scroll_window_days))
                x_nums = [mdates.date2num(p["x"]) for p in self._points]
                self._scroll_min = min(x_nums)
                self._scroll_max = max(x_nums)
                window = float(self._scroll_window_days)
                if initial_window_end is not None:
                    end_num = mdates.date2num(initial_window_end)
                else:
                    end_num = self._scroll_max
                end_num = max(self._scroll_min, min(end_num, self._scroll_max))
                start_num = end_num - window
                if start_num < self._scroll_min:
                    start_num = self._scroll_min
                    end_num = min(self._scroll_max, start_num + window)
                self._ax.set_xlim(mdates.num2date(start_num), mdates.num2date(end_num))
            else:
                self._scroll_min = None
                self._scroll_max = None
            self._hover_vline = self._ax.axvline(
                x=0,
                color="#8A8A8A",
                linewidth=1.0,
                linestyle="--",
                alpha=0.55,
                zorder=1,
            )
            self._hover_vline.set_visible(False)
        else:
            self._hover_vline = None
            self._ax.set_axis_off()
            self._ax.text(
                0.5,
                0.5,
                empty_message,
                color="#888888",
                fontsize=10,
                ha="center",
                va="center",
                transform=self._ax.transAxes,
            )

        # Recreate on every draw because _style_axes() clears previous artists.
        self._tooltip = self._ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            fontsize=9,
            color="#FFFFFF",
            bbox={"boxstyle": "round,pad=0.3", "fc": "#111111", "ec": "#666666", "alpha": 0.95},
            zorder=5,
        )
        self._tooltip.set_visible(False)

        self._canvas.draw_idle()

    def _on_scroll(self, event):
        if not self._scroll_enabled or event.inaxes != self._ax:
            return
        if self._scroll_min is None or self._scroll_max is None:
            return
        x0, x1 = self._ax.get_xlim()
        span = x1 - x0
        if span <= 0:
            return
        step_days = min(7.0, span / 2)
        # Scroll up -> newer dates, down -> older dates.
        direction = 1.0 if event.step > 0 else -1.0
        delta = direction * step_days
        new0 = x0 + delta
        new1 = x1 + delta
        if new0 < self._scroll_min:
            shift = self._scroll_min - new0
            new0 += shift
            new1 += shift
        if new1 > self._scroll_max:
            shift = new1 - self._scroll_max
            new0 -= shift
            new1 -= shift
        self._ax.set_xlim(new0, new1)
        self._canvas.draw_idle()

    def _on_mouse_move(self, event):
        if (
            event.inaxes != self._ax
            or event.xdata is None
            or self._hover_vline is None
        ):
            changed = False
            if self._hover_vline is not None and self._hover_vline.get_visible():
                self._hover_vline.set_visible(False)
                changed = True
            if self._tooltip is not None and self._tooltip.get_visible():
                self._tooltip.set_visible(False)
                changed = True
            if changed:
                self._canvas.draw_idle()
            return

        if not self._points:
            return

        nearest = None
        nearest_dist = None
        for p in self._points:
            px, py = self._ax.transData.transform((mdates.date2num(p["x"]), p["y"]))
            dist = math.hypot(px - event.x, py - event.y)
            if nearest_dist is None or dist < nearest_dist:
                nearest = p
                nearest_dist = dist

        if nearest is None:
            return

        nearest_x_num = mdates.date2num(nearest["x"])
        self._hover_vline.set_xdata([nearest_x_num, nearest_x_num])
        self._hover_vline.set_visible(True)
        self._tooltip.xy = (nearest["x"], nearest["y"])
        self._tooltip.set_text(nearest["text"])
        self._tooltip.set_visible(True)
        self._canvas.draw_idle()

