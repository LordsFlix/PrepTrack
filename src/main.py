"""
main.py — Entry point for the Todo application.
"""

import sys

import datetime
from PyQt6.QtWidgets import QApplication

from database import setup_database, get_active_day, set_active_day
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    conn = setup_database()
    
    # Initialize logical active_day if not set
    active_day = get_active_day(conn)
    if not active_day:
        active_day = datetime.date.today().strftime("%d-%m-%Y")
        set_active_day(conn, active_day)

    window = MainWindow(conn)
    window.show()

    exit_code = app.exec()
    conn.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
