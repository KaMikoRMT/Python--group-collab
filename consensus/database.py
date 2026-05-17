"""SQLite database helpers for the room-based consensus app.

Room code logic:
- Each group uses one room_code.
- Every table that stores group data includes room_code.
- Every SELECT/INSERT/UPDATE uses room_code so groups cannot see each other.
"""

import sqlite3
from pathlib import Path


DB_PATH = Path("consensus.db")


def get_connection():
    """Create and return a SQLite connection."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create required tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_code TEXT PRIMARY KEY,
            host_nickname TEXT NOT NULL,
            phase INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS room_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            nickname TEXT NOT NULL,
            UNIQUE(room_code, nickname)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            user_name TEXT NOT NULL,
            idea_title TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            user_name TEXT NOT NULL,
            project_idea TEXT NOT NULL,
            creativity INTEGER NOT NULL,
            feasibility INTEGER NOT NULL,
            practicality INTEGER NOT NULL,
            technical_depth INTEGER NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def create_room(room_code, host_nickname):
    """Create a room and register the host as the first member."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO rooms (room_code, host_nickname, phase) VALUES (?, ?, 1)",
        (room_code, host_nickname.strip()),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO room_members (room_code, nickname) VALUES (?, ?)",
        (room_code, host_nickname.strip()),
    )

    conn.commit()
    conn.close()


def room_exists(room_code):
    """Check whether a room exists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT room_code FROM rooms WHERE room_code = ?",
        (room_code.strip().upper(),),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def add_room_member(room_code, nickname):
    """Add a nickname to one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO room_members (room_code, nickname) VALUES (?, ?)",
        (room_code.strip().upper(), nickname.strip()),
    )
    conn.commit()
    conn.close()


def get_room_members(room_code):
    """Return members in one room only."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nickname FROM room_members WHERE room_code = ? ORDER BY id",
        (room_code,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_room_phase(room_code):
    """Return the current phase for one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT phase FROM rooms WHERE room_code = ?", (room_code,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return 1
    return row[0]


def update_room_phase(room_code, phase):
    """Update phase for one room. Only app.py allows host to call this."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE rooms SET phase = ? WHERE room_code = ?",
        (int(phase), room_code),
    )
    conn.commit()
    conn.close()


def get_room_host(room_code):
    """Return the host nickname for one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT host_nickname FROM rooms WHERE room_code = ?", (room_code,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return ""
    return row[0]


def delete_room_data(room_code):
    """Delete all data in one room only.

    The current UI does not expose delete buttons, but this function documents
    the safe DELETE pattern: always filter by room_code.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM evaluations WHERE room_code = ?", (room_code,))
    cursor.execute("DELETE FROM project_ideas WHERE room_code = ?", (room_code,))
    cursor.execute("DELETE FROM room_members WHERE room_code = ?", (room_code,))
    cursor.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
    conn.commit()
    conn.close()


def add_project_idea(room_code, user_name, idea_title):
    """Add one project idea in one room if it has not appeared in that room."""
    clean_title = idea_title.strip()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id FROM project_ideas
        WHERE room_code = ? AND lower(idea_title) = lower(?)
        """,
        (room_code, clean_title),
    )
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return False

    cursor.execute(
        """
        INSERT INTO project_ideas (room_code, user_name, idea_title)
        VALUES (?, ?, ?)
        """,
        (room_code, user_name.strip(), clean_title),
    )
    conn.commit()
    conn.close()
    return True


def get_project_ideas(room_code):
    """Return all project idea titles in one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT idea_title FROM project_ideas WHERE room_code = ? ORDER BY id",
        (room_code,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_idea_submitters(room_code):
    """Return distinct users who submitted project ideas in one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT user_name FROM project_ideas
        WHERE room_code = ?
        ORDER BY user_name
        """,
        (room_code,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def has_user_evaluated(room_code, user_name):
    """Check whether one user has already submitted evaluations in one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM evaluations
        WHERE room_code = ? AND lower(user_name) = lower(?)
        LIMIT 1
        """,
        (room_code, user_name.strip()),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_evaluations(room_code, user_name, evaluation_data):
    """Save one user's evaluations for all project ideas in one room."""
    conn = get_connection()
    cursor = conn.cursor()

    for project_idea, scores in evaluation_data.items():
        cursor.execute(
            """
            INSERT INTO evaluations (
                room_code,
                user_name,
                project_idea,
                creativity,
                feasibility,
                practicality,
                technical_depth
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room_code,
                user_name.strip(),
                project_idea,
                int(scores["creativity"]),
                int(scores["feasibility"]),
                int(scores["practicality"]),
                int(scores["technical_depth"]),
            ),
        )

    conn.commit()
    conn.close()


def get_evaluation_results(room_code):
    """Return total scores for each project idea in one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            project_idea,
            SUM(creativity) AS creativity,
            SUM(feasibility) AS feasibility,
            SUM(practicality) AS practicality,
            SUM(technical_depth) AS technical_depth
        FROM evaluations
        WHERE room_code = ?
        GROUP BY project_idea
        ORDER BY
            (SUM(creativity) + SUM(feasibility) + SUM(practicality) + SUM(technical_depth)) DESC,
            project_idea ASC
        """,
        (room_code,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_evaluators(room_code):
    """Return distinct users who submitted evaluations in one room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT user_name FROM evaluations
        WHERE room_code = ?
        ORDER BY user_name
        """,
        (room_code,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]
