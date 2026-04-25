import os
import sqlite3
import datetime

def get_db_path():
    """Get the persistent path to the database in LOCALAPPDATA."""
    app_data = os.environ.get("LOCALAPPDATA")
    if not app_data:
        app_data = os.path.expanduser("~")
        
    folder = os.path.join(app_data, "PrepTrack")
    if not os.path.exists(folder):
        os.makedirs(folder)
        
    return os.path.join(folder, "todo.db")

DB_PATH = get_db_path()


def setup_database():
    """Create the tasks and days tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'target',
            is_enabled  INTEGER NOT NULL DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS days (
            date        TEXT    PRIMARY KEY,
            finalized   INTEGER NOT NULL DEFAULT 0,
            rating      REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS template_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            title       TEXT NOT NULL,
            task_type   TEXT NOT NULL DEFAULT 'regular',
            subject     TEXT,
            test_category TEXT,
            FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE CASCADE
        )
    """)
    # Add new columns if they don't exist (Migration)
    columns = [
        ("task_type", "TEXT DEFAULT 'regular'"),
        ("max_marks", "INTEGER"),
        ("obtained_marks", "INTEGER"),
        ("test_category", "TEXT"),
        ("subject", "TEXT"),
        ("physics_max", "INTEGER"),
        ("physics_score", "INTEGER"),
        ("chemistry_max", "INTEGER"),
        ("chemistry_score", "INTEGER"),
        ("math_max", "INTEGER"),
        ("math_score", "INTEGER")
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            # Column already exists
            pass
            
    # Migration for template_tasks
    template_cols = [
        ("task_type", "TEXT DEFAULT 'regular'"),
        ("subject", "TEXT"),
        ("test_category", "TEXT")
    ]
    for col_name, col_type in template_cols:
        try:
            cursor.execute(f"ALTER TABLE template_tasks ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    return conn


def get_active_day(conn) -> str:
    """Return the current logical day 'DD-MM-YYYY' from app_state."""
    return get_app_state(conn, 'active_day')


def set_active_day(conn, date_str: str):
    """Set the logical day in 'DD-MM-YYYY' format."""
    set_app_state(conn, 'active_day', date_str)


def get_app_state(conn, key: str) -> str:
    """Return a value from app_state by key."""
    cursor = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row["value"] if row else None


def set_app_state(conn, key: str, value: str):
    """Set a value in app_state by key."""
    conn.execute(
        "INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()


def get_tasks_by_date(conn, date: str) -> list[dict]:
    """Return all active tasks for a given date as a list of dicts."""
    cursor = conn.execute(
        "SELECT * FROM tasks WHERE date = ? ORDER BY id",
        (date,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _to_date(value):
    """Parse supported date inputs to datetime.date."""
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            return None
    return None


def is_attempted(task) -> bool:
    """Return True when task is a completed test/DPP with valid marks."""
    if not task:
        return False
    return (
        task.get("status") == "completed"
        and task.get("task_type") in ("test", "dpp")
        and task.get("obtained_marks") is not None
        and task.get("max_marks") is not None
        and task.get("max_marks") > 0
    )


def is_future(task, today) -> bool:
    """Return True if task date is in the future of provided reference date."""
    task_day = _to_date(task.get("date") if task else None)
    today_day = _to_date(today)
    if not task_day or not today_day:
        return False
    return task_day > today_day


def get_day_metrics(conn, date_str: str, today=None, performance_task_types=None) -> dict:
    """
    Aggregate completion/performance metrics for one day.

    Returns keys:
      - completion_percent
      - performance_percent
      - completion_completed
      - completion_total
      - performance_obtained
      - performance_max
    """
    tasks = get_tasks_by_date(conn, date_str)

    completion_total = 0
    completion_completed = 0
    performance_obtained = 0
    performance_max = 0

    allowed_perf_types = set(performance_task_types) if performance_task_types else {"test", "dpp"}

    for task in tasks:
        if task.get("is_enabled", 1) != 1:
            continue
        if today is not None and is_future(task, today):
            continue

        completion_total += 1
        if task.get("status") == "completed":
            completion_completed += 1

        if is_attempted(task) and task.get("task_type") in allowed_perf_types:
            performance_obtained += task.get("obtained_marks") or 0
            performance_max += task.get("max_marks") or 0

    completion_percent = None
    if completion_total > 0:
        completion_percent = (completion_completed / completion_total) * 100.0

    performance_percent = None
    if performance_max > 0:
        performance_percent = (performance_obtained / performance_max) * 100.0

    return {
        "completion_percent": completion_percent,
        "performance_percent": performance_percent,
        "completion_completed": completion_completed,
        "completion_total": completion_total,
        "performance_obtained": performance_obtained,
        "performance_max": performance_max,
    }


def disable_task(conn, task_id: int):
    """Disable a task (set is_enabled = 0) to hide it from view."""
    conn.execute("UPDATE tasks SET is_enabled = 0 WHERE id = ?", (task_id,))
    conn.commit()


def enable_task(conn, task_id: int):
    """Enable a task (set is_enabled = 1)."""
    conn.execute("UPDATE tasks SET is_enabled = 1 WHERE id = ?", (task_id,))
    conn.commit()


def add_task(conn, title: str, date: str, task_type: str = "regular", subject: str = None, test_category: str = None) -> int:
    """Add a new task for the given date. Returns the new row id."""
    cursor = conn.execute(
        """INSERT INTO tasks (title, date, status, is_enabled, task_type, subject, test_category) 
           VALUES (?, ?, 'target', 1, ?, ?, ?)""",
        (title, date, task_type, subject, test_category),
    )
    conn.commit()
    return cursor.lastrowid


def update_task_marks(conn, task_id: int, max_m: int, obt_m: int):
    """Update simple marks for a DPP / Regular task. Clamp to valid range."""
    max_m = max(0, max_m)
    obt_m = max(0, min(obt_m, max_m))
    conn.execute(
        "UPDATE tasks SET max_marks = ?, obtained_marks = ? WHERE id = ?",
        (max_m, obt_m, task_id),
    )
    conn.commit()


def update_test_marks(conn, task_id: int, p_max, p_score, c_max, c_score, m_max, m_score):
    """Update subject-wise marks for a Test. Clamp all values to their respective max."""
    p_max = max(0, p_max)
    p_score = max(0, min(p_score, p_max))
    c_max = max(0, c_max)
    c_score = max(0, min(c_score, c_max))
    m_max = max(0, m_max)
    m_score = max(0, min(m_score, m_max))
    
    total_max = p_max + c_max + m_max
    total_obt = p_score + c_score + m_score
    conn.execute(
        """UPDATE tasks SET 
           physics_max = ?, physics_score = ?, 
           chemistry_max = ?, chemistry_score = ?, 
           math_max = ?, math_score = ?,
           max_marks = ?, obtained_marks = ?
           WHERE id = ?""",
        (p_max, p_score, c_max, c_score, m_max, m_score, total_max, total_obt, task_id),
    )
    conn.commit()


def update_task_title(conn, task_id: int, new_title: str):
    """Rename a task."""
    conn.execute(
        "UPDATE tasks SET title = ? WHERE id = ?",
        (new_title, task_id),
    )
    conn.commit()


def update_task_status(conn, task_id: int, new_status: str):
    """Change the status of a task (target / completed / incomplete)."""
    if new_status not in ("target", "completed", "incomplete"):
        raise ValueError(f"Invalid status: {new_status}")
    conn.execute(
        "UPDATE tasks SET status = ? WHERE id = ?",
        (new_status, task_id),
    )
    conn.commit()


def delete_task(conn, task_id: int):
    """Delete a task by id."""
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


def finalize_day(conn, date: str, rating: float):
    """Mark a day as finalized and store the rating. Also mark remaining enabled targets as incomplete."""
    conn.execute(
        "DELETE FROM tasks WHERE date = ? AND is_enabled = 0",
        (date,)
    )
    conn.execute(
        "UPDATE tasks SET status = 'incomplete' WHERE date = ? AND status = 'target' AND is_enabled = 1",
        (date,)
    )
    conn.execute(
        "INSERT OR REPLACE INTO days (date, finalized, rating) VALUES (?, 1, ?)",
        (date, rating)
    )
    conn.commit()


def is_day_finalized(conn, date: str) -> bool:
    """Check if the given date is already finalized."""
    cursor = conn.execute("SELECT finalized FROM days WHERE date = ?", (date,))
    row = cursor.fetchone()
    return row is not None and row["finalized"] == 1


def get_day_rating(conn, date: str):
    """Return the rating for a date if it exists, else None."""
    cursor = conn.execute("SELECT rating FROM days WHERE date = ?", (date,))
    row = cursor.fetchone()
    return row["rating"] if row else None


# --- Template Collection Functions ---

def get_templates(conn):
    """Return all templates."""
    cursor = conn.execute("SELECT id, name FROM templates ORDER BY name ASC")
    return [{"id": r["id"], "name": r["name"]} for r in cursor.fetchall()]

def add_template(conn, name: str):
    """Add a new template."""
    conn.execute("INSERT INTO templates (name) VALUES (?)", (name,))
    conn.commit()

def delete_template(conn, template_id: int):
    """Delete a template and its tasks (cascade)."""
    conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()

def rename_template(conn, template_id: int, new_name: str):
    """Rename a template."""
    conn.execute("UPDATE templates SET name = ? WHERE id = ?", (new_name, template_id))
    conn.commit()

def get_template_tasks(conn, template_id: int):
    """Return all tasks for a specific template."""
    cursor = conn.execute(
        "SELECT id, title, task_type, subject, test_category FROM template_tasks WHERE template_id = ? ORDER BY id ASC", 
        (template_id,)
    )
    return [dict(row) for row in cursor.fetchall()]

def add_template_task(conn, template_id: int, title: str, task_type: str = "regular", subject: str = None, test_category: str = None):
    """Add a task to a template."""
    conn.execute(
        "INSERT INTO template_tasks (template_id, title, task_type, subject, test_category) VALUES (?, ?, ?, ?, ?)",
        (template_id, title, task_type, subject, test_category)
    )
    conn.commit()

def delete_template_task(conn, task_id: int):
    """Delete a specific task from a template."""
    conn.execute("DELETE FROM template_tasks WHERE id = ?", (task_id,))
    conn.commit()

def rename_template_task(conn, task_id: int, new_title: str):
    """Rename a specific template task."""
    conn.execute("UPDATE template_tasks SET title = ? WHERE id = ?", (new_title, task_id))
    conn.commit()


# --- Backup / Sync Functions ---

def export_data(conn):
    """Export all tasks, days, templates, and template_tasks to a dictionary."""
    cursor = conn.cursor()
    
    # Export Tasks
    cursor.execute("SELECT * FROM tasks")
    tasks = [dict(row) for row in cursor.fetchall()]
    
    # Export Days
    cursor.execute("SELECT * FROM days")
    days = [dict(row) for row in cursor.fetchall()]

    # Export Templates
    cursor.execute("SELECT * FROM templates")
    templates = [dict(row) for row in cursor.fetchall()]

    # Export Template Tasks
    cursor.execute("SELECT * FROM template_tasks")
    template_tasks = [dict(row) for row in cursor.fetchall()]
    
    return {
        "tasks": tasks,
        "days": days,
        "templates": templates,
        "template_tasks": template_tasks
    }

def import_data(conn, data):
    """Clear all existing data and import from dictionary."""
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM tasks")
        cursor.execute("DELETE FROM days")
        cursor.execute("DELETE FROM template_tasks")
        cursor.execute("DELETE FROM templates")
        
        # Insert Tasks (Dynamic based on keys)
        if "tasks" in data:
            for t in data["tasks"]:
                keys = t.keys()
                placeholders = ", ".join(["?"] * len(keys))
                cols = ", ".join(keys)
                vals = [t[k] for k in keys]
                cursor.execute(f"INSERT INTO tasks ({cols}) VALUES ({placeholders})", vals)
        
        # Insert Days
        if "days" in data:
            for d in data["days"]:
                cursor.execute(
                    "INSERT INTO days (date, finalized, rating) VALUES (?, ?, ?)",
                    (d["date"], d["finalized"], d["rating"])
                )

        # Insert Templates
        if "templates" in data:
            for t in data["templates"]:
                cursor.execute("INSERT INTO templates (id, name) VALUES (?, ?)", (t["id"], t["name"]))

        # Insert Template Tasks
        if "template_tasks" in data:
            for tt in data["template_tasks"]:
                keys = tt.keys()
                placeholders = ", ".join(["?"] * len(keys))
                cols = ", ".join(keys)
                vals = [tt[k] for k in keys]
                cursor.execute(f"INSERT INTO template_tasks ({cols}) VALUES ({placeholders})", vals)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e

